"""Proactive household anomaly detection (Tier 4 Feature 13).

Runs as a daily scheduled job (see ``scheduler.run_anomaly_detection_tick``)
and emits ``parent_action_items`` rows of type ``anomaly_alert`` when
*deterministic* rules find something unusual enough to bother a parent
about. An AI layer then ranks and narrates the candidates — but the AI
can never *invent* an anomaly. Candidates come from the rules.

Design rules
------------
1. **Deterministic candidate generation is the source of truth.** The
   AI layer explains/ranks, never invents.
2. **Minimum significance threshold** — each rule emits a score in
   [0.0, 1.0]; anything below ``MIN_SIGNIFICANCE`` is silently dropped.
3. **Dedupe by (family, anomaly_type, window)** — the scheduler writes
   a ``ScheduledRun`` mutex row before inserting any ``parent_action_item``
   so re-runs on the same day are idempotent even if the underlying rule
   would still fire.
4. **Template fallback** — if the AI narrative call fails, we write a
   deterministic summary sentence pulled directly from the rule output.
5. **Bounded blast radius** — hard cap on how many anomaly rows any
   single tick can emit (``MAX_ANOMALIES_PER_TICK``) so a broken rule
   can't spam the inbox.

Candidate classes v1
--------------------
- ``stale_routine`` — a routine hasn't had a completed instance in
  ``STALE_ROUTINE_DAYS`` and historically was completing.
- ``routine_dropoff_child`` — a specific child's routine completion
  rate dropped meaningfully week-over-week.
- ``homework_dropoff`` — a child with recent homework activity has
  gone quiet for a week.
- ``meal_monotony`` — the same meal title appears ``MEAL_REPEAT_THRESHOLD``
  or more times in the trailing 14 days.
- ``inbox_buildup`` — unresolved ``parent_action_items`` count is
  above ``INBOX_BUILDUP_THRESHOLD`` with rows older than 7 days.
"""

from __future__ import annotations

import logging
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.action_items import ParentActionItem
from app.models.foundation import FamilyMember
from app.models.homework import HomeworkSession
from app.models.life_management import Routine, TaskInstance
from app.models.meals import Meal

logger = logging.getLogger("scout.ai.anomalies")


# Tunables — kept module-level so tests can monkeypatch.
STALE_ROUTINE_DAYS = 4
ROUTINE_DROPOFF_MIN_PCT = 0.35     # 35 percentage point drop WoW
HOMEWORK_LOOKBACK_DAYS = 14
HOMEWORK_RECENT_WINDOW_DAYS = 7
MEAL_REPEAT_THRESHOLD = 3          # same title 3+ times in 14 days
MEAL_LOOKBACK_DAYS = 14
INBOX_BUILDUP_THRESHOLD = 5        # 5+ pending items...
INBOX_BUILDUP_AGE_DAYS = 7         # ...at least this old
MIN_SIGNIFICANCE = 0.4
MAX_ANOMALIES_PER_TICK = 5


@dataclass
class AnomalyCandidate:
    """One deterministic anomaly finding. The ``anomaly_type`` is
    stable across runs so dedupe works, and the ``signature`` is a
    stable short string that uniquely identifies the specific
    *incident* (e.g. routine id, child id, meal title) so the same
    candidate doesn't flap back and forth."""

    anomaly_type: str
    signature: str
    significance: float        # 0.0..1.0; below MIN_SIGNIFICANCE → dropped
    summary: str               # one-line deterministic template summary
    facts: dict = field(default_factory=dict)
    suggested_action: str = ""


# ---------------------------------------------------------------------------
# Candidate generators — each is a pure function over the DB state.
# They never create action items; they just report.
# ---------------------------------------------------------------------------


def detect_stale_routines(
    db: Session, *, family_id: uuid.UUID, as_of: date
) -> list[AnomalyCandidate]:
    """Find routines with no completed instance in the last
    ``STALE_ROUTINE_DAYS`` days. Historical context matters: a
    brand-new routine with zero completions shouldn't trigger."""
    out: list[AnomalyCandidate] = []
    stale_cutoff = as_of - timedelta(days=STALE_ROUTINE_DAYS)
    history_cutoff = as_of - timedelta(days=STALE_ROUTINE_DAYS * 3)

    routines = list(
        db.scalars(
            select(Routine).where(Routine.family_id == family_id)
        ).all()
    )
    for r in routines:
        recent = db.scalars(
            select(TaskInstance)
            .where(TaskInstance.routine_id == r.id)
            .where(TaskInstance.family_id == family_id)
            .where(TaskInstance.is_completed.is_(True))
            .where(TaskInstance.instance_date >= stale_cutoff)
        ).first()
        if recent:
            continue

        # Historical baseline: did this routine ever complete in the
        # prior window? If not, it's a new routine, not a stale one.
        ever = db.scalars(
            select(TaskInstance)
            .where(TaskInstance.routine_id == r.id)
            .where(TaskInstance.family_id == family_id)
            .where(TaskInstance.is_completed.is_(True))
            .where(TaskInstance.instance_date >= history_cutoff)
            .where(TaskInstance.instance_date < stale_cutoff)
        ).first()
        if not ever:
            continue

        out.append(
            AnomalyCandidate(
                anomaly_type="stale_routine",
                signature=f"routine:{r.id}",
                significance=0.6,
                summary=(
                    f"Routine '{r.name}' has not been completed for "
                    f"{STALE_ROUTINE_DAYS}+ days."
                ),
                facts={
                    "routine_id": str(r.id),
                    "routine_name": r.name,
                    "days_stale": STALE_ROUTINE_DAYS,
                },
                suggested_action=(
                    "Check if this routine still fits the family's schedule, "
                    "or remind the child who owns it."
                ),
            )
        )
    return out


def detect_routine_dropoff_by_child(
    db: Session, *, family_id: uuid.UUID, as_of: date
) -> list[AnomalyCandidate]:
    """Per-child completion rate this week vs. last week. Significant
    drops emit a candidate."""
    out: list[AnomalyCandidate] = []
    this_week_end = as_of
    this_week_start = as_of - timedelta(days=6)
    last_week_end = this_week_start - timedelta(days=1)
    last_week_start = last_week_end - timedelta(days=6)

    children = list(
        db.scalars(
            select(FamilyMember)
            .where(FamilyMember.family_id == family_id)
            .where(FamilyMember.role == "child")
            .where(FamilyMember.is_active.is_(True))
        ).all()
    )
    for kid in children:
        tw_total, tw_done = _count_instances(
            db, family_id=family_id, member_id=kid.id,
            start=this_week_start, end=this_week_end,
        )
        lw_total, lw_done = _count_instances(
            db, family_id=family_id, member_id=kid.id,
            start=last_week_start, end=last_week_end,
        )
        if tw_total < 3 or lw_total < 3:
            continue
        tw_pct = tw_done / tw_total
        lw_pct = lw_done / lw_total
        delta = lw_pct - tw_pct
        if delta < ROUTINE_DROPOFF_MIN_PCT:
            continue
        out.append(
            AnomalyCandidate(
                anomaly_type="routine_dropoff_child",
                signature=f"child:{kid.id}:week:{this_week_start.isoformat()}",
                significance=min(0.5 + delta, 0.95),
                summary=(
                    f"{kid.first_name}'s routine completion dropped from "
                    f"{int(lw_pct * 100)}% last week to {int(tw_pct * 100)}% this week."
                ),
                facts={
                    "child_id": str(kid.id),
                    "child_name": kid.first_name,
                    "this_week_pct": round(tw_pct, 2),
                    "last_week_pct": round(lw_pct, 2),
                    "delta": round(delta, 2),
                },
                suggested_action=(
                    "Check in with the child and look for schedule conflicts "
                    "or anything disrupting their routine this week."
                ),
            )
        )
    return out


def detect_homework_dropoff(
    db: Session, *, family_id: uuid.UUID, as_of: date
) -> list[AnomalyCandidate]:
    """A child who was doing homework recently has gone silent. Uses
    the ai_homework_sessions table created in Tier 2."""
    out: list[AnomalyCandidate] = []
    now = datetime.combine(as_of, datetime.min.time())
    older_start = now - timedelta(days=HOMEWORK_LOOKBACK_DAYS)
    recent_start = now - timedelta(days=HOMEWORK_RECENT_WINDOW_DAYS)

    # For each child, count sessions in two windows.
    children = list(
        db.scalars(
            select(FamilyMember)
            .where(FamilyMember.family_id == family_id)
            .where(FamilyMember.role == "child")
            .where(FamilyMember.is_active.is_(True))
        ).all()
    )
    for kid in children:
        older = list(
            db.scalars(
                select(HomeworkSession)
                .where(HomeworkSession.family_id == family_id)
                .where(HomeworkSession.member_id == kid.id)
                .where(HomeworkSession.started_at >= older_start)
                .where(HomeworkSession.started_at < recent_start)
            ).all()
        )
        recent = list(
            db.scalars(
                select(HomeworkSession)
                .where(HomeworkSession.family_id == family_id)
                .where(HomeworkSession.member_id == kid.id)
                .where(HomeworkSession.started_at >= recent_start)
            ).all()
        )
        if len(older) < 2:
            continue
        if len(recent) > 0:
            continue
        out.append(
            AnomalyCandidate(
                anomaly_type="homework_dropoff",
                # Stable per-child signature so the suppression
                # ledger can silence repeat day-to-day alerts.
                signature=f"child:{kid.id}:homework",
                significance=0.55,
                summary=(
                    f"{kid.first_name} had {len(older)} homework sessions with "
                    f"Scout in the prior week but none in the last "
                    f"{HOMEWORK_RECENT_WINDOW_DAYS} days."
                ),
                facts={
                    "child_id": str(kid.id),
                    "child_name": kid.first_name,
                    "older_sessions": len(older),
                    "recent_sessions": 0,
                },
                suggested_action=(
                    "Ask the child if they have homework and whether they're "
                    "using Scout for it. Could be fine, could be they're stuck."
                ),
            )
        )
    return out


def detect_meal_monotony(
    db: Session, *, family_id: uuid.UUID, as_of: date
) -> list[AnomalyCandidate]:
    """Surface when the same meal shows up too many times in a short
    window. Parents often don't realize they've cooked taco night six
    times in two weeks."""
    out: list[AnomalyCandidate] = []
    start = as_of - timedelta(days=MEAL_LOOKBACK_DAYS)
    meals = list(
        db.scalars(
            select(Meal)
            .where(Meal.family_id == family_id)
            .where(Meal.meal_date >= start)
            .where(Meal.meal_date <= as_of)
        ).all()
    )
    counts = Counter(_normalize_meal_title(m.title) for m in meals if m.title)
    for title, cnt in counts.items():
        if cnt < MEAL_REPEAT_THRESHOLD:
            continue
        out.append(
            AnomalyCandidate(
                anomaly_type="meal_monotony",
                # Signature stays stable across days so the Tier 5
                # suppression ledger can silence repeat alerts for
                # the same meal. The previous shape embedded the
                # window start date and broke day-to-day dedupe.
                signature=f"meal:{title}",
                significance=min(0.4 + 0.1 * (cnt - MEAL_REPEAT_THRESHOLD), 0.8),
                summary=(
                    f"'{title}' has appeared on the menu {cnt} times in the "
                    f"last {MEAL_LOOKBACK_DAYS} days."
                ),
                facts={
                    "meal_title": title,
                    "count": cnt,
                    "window_days": MEAL_LOOKBACK_DAYS,
                },
                suggested_action=(
                    "Consider rotating a different meal in next week, or mark "
                    "it as a staple if it's genuinely on purpose."
                ),
            )
        )
    return out


def detect_inbox_buildup(
    db: Session, *, family_id: uuid.UUID, as_of: date
) -> list[AnomalyCandidate]:
    """Too many pending parent_action_items AND at least one of them
    has been sitting around for a while."""
    # parent_action_items.created_at is timestamptz → tz-aware when
    # read. Keep the cutoff tz-aware too so the comparison doesn't
    # raise on mixed naive/aware datetimes.
    import pytz as _pytz
    now_aware = _pytz.UTC.localize(datetime.combine(as_of, datetime.min.time()))
    age_cutoff = now_aware - timedelta(days=INBOX_BUILDUP_AGE_DAYS)
    pending = list(
        db.scalars(
            select(ParentActionItem)
            .where(ParentActionItem.family_id == family_id)
            .where(ParentActionItem.status == "pending")
            # Exclude anomaly/digest rows themselves so we don't feedback-loop.
            .where(
                ParentActionItem.action_type.notin_(
                    [
                        "anomaly_alert",
                        "moderation_digest",
                        "daily_brief",
                    ]
                )
            )
        ).all()
    )
    if len(pending) < INBOX_BUILDUP_THRESHOLD:
        return []
    old_ones = []
    for p in pending:
        created = p.created_at
        if created is None:
            continue
        if created.tzinfo is None:
            created = _pytz.UTC.localize(created)
        if created <= age_cutoff:
            old_ones.append(p)
    if not old_ones:
        return []
    return [
        AnomalyCandidate(
            anomaly_type="inbox_buildup",
            # Stable per-family so subsequent scans are silenced
            # by the suppression ledger.
            signature="inbox",
            significance=min(0.4 + 0.05 * len(pending), 0.85),
            summary=(
                f"{len(pending)} parent action items are pending, with "
                f"{len(old_ones)} older than {INBOX_BUILDUP_AGE_DAYS} days."
            ),
            facts={
                "pending_count": len(pending),
                "stale_count": len(old_ones),
                "age_threshold_days": INBOX_BUILDUP_AGE_DAYS,
            },
            suggested_action=(
                "Open the inbox and clear the oldest items, or dismiss them "
                "if they are no longer relevant."
            ),
        )
    ]


ALL_DETECTORS = [
    detect_stale_routines,
    detect_routine_dropoff_by_child,
    detect_homework_dropoff,
    detect_meal_monotony,
    detect_inbox_buildup,
]


# ---------------------------------------------------------------------------
# AI ranking + narration
# ---------------------------------------------------------------------------


def rank_candidates(
    candidates: list[AnomalyCandidate],
) -> list[AnomalyCandidate]:
    """Sort by significance desc, then cap at MAX_ANOMALIES_PER_TICK.
    Below MIN_SIGNIFICANCE is dropped entirely.

    Tier 5 F18: the module-level defaults are overridable via config
    (``anomaly_min_significance``, ``anomaly_max_per_tick``) so
    operators can tune noise without a code deploy. Falls back to
    the module constants if settings aren't available."""
    try:
        from app.config import settings
        min_sig = float(settings.anomaly_min_significance)
        max_n = int(settings.anomaly_max_per_tick)
    except Exception:
        min_sig = MIN_SIGNIFICANCE
        max_n = MAX_ANOMALIES_PER_TICK
    above = [c for c in candidates if c.significance >= min_sig]
    above.sort(key=lambda c: c.significance, reverse=True)
    return above[:max_n]


def narrate_candidate(candidate: AnomalyCandidate) -> tuple[str, str | None]:
    """Return (narrative, model_used). Tries AI; on any failure or
    missing key, returns the deterministic summary + None for model.
    Narrative is plain-language, 1-3 sentences, third person."""
    try:
        from app.config import settings
        if not settings.anthropic_api_key:
            return _template_narrative(candidate), None

        from app.ai.provider import get_provider
        system = (
            "You are writing a short plain-English notification for a family "
            "operations inbox. Tone: direct, calm, not alarmist. Third "
            "person. No emoji. 1 to 3 sentences. Do not invent facts beyond "
            "what the data shows. Include the suggested action naturally."
        )
        user = (
            f"Anomaly type: {candidate.anomaly_type}\n"
            f"Template summary: {candidate.summary}\n"
            f"Suggested action: {candidate.suggested_action}\n"
            f"Raw facts: {candidate.facts}\n\n"
            "Write the notification text now."
        )
        provider = get_provider()
        response = provider.chat(
            messages=[{"role": "user", "content": user}],
            system=system,
            model=settings.ai_classification_model or settings.ai_chat_model,
            max_tokens=200,
            temperature=0.3,
        )
        text = (response.content or "").strip().replace("\n", " ")
        if not text:
            return _template_narrative(candidate), None
        if len(text) > 400:
            text = text[:399].rstrip() + "…"
        return text, response.model
    except Exception as e:
        logger.warning("anomaly_narrate_failed type=%s err=%s", candidate.anomaly_type, str(e)[:200])
        return _template_narrative(candidate), None


def _template_narrative(c: AnomalyCandidate) -> str:
    if c.suggested_action:
        return f"{c.summary} {c.suggested_action}"
    return c.summary


# ---------------------------------------------------------------------------
# Full pipeline — called by the scheduler
# ---------------------------------------------------------------------------


def generate_anomaly_candidates(
    db: Session, *, family_id: uuid.UUID, as_of: date | None = None
) -> list[AnomalyCandidate]:
    """Run every detector and return the ranked, above-threshold list."""
    as_of = as_of or date.today()
    all_found: list[AnomalyCandidate] = []
    for detector in ALL_DETECTORS:
        try:
            all_found.extend(detector(db, family_id=family_id, as_of=as_of))
        except Exception as e:
            logger.warning(
                "anomaly_detector_failed name=%s family=%s err=%s",
                detector.__name__, family_id, str(e)[:200],
            )
    return rank_candidates(all_found)


def _count_instances(
    db: Session,
    *,
    family_id: uuid.UUID,
    member_id: uuid.UUID,
    start: date,
    end: date,
) -> tuple[int, int]:
    """(total, completed) count of TaskInstance rows for a member over
    a date range (inclusive). Used by the dropoff detector."""
    rows = list(
        db.scalars(
            select(TaskInstance)
            .where(TaskInstance.family_id == family_id)
            .where(TaskInstance.family_member_id == member_id)
            .where(TaskInstance.instance_date >= start)
            .where(TaskInstance.instance_date <= end)
        ).all()
    )
    total = len(rows)
    done = sum(1 for r in rows if r.is_completed)
    return total, done


def _normalize_meal_title(title: str) -> str:
    """Lowercase + strip trailing punctuation. Meal titles like 'Tacos'
    and 'tacos' should collapse. Keep it simple — the monotony detector
    doesn't need fuzzy matching."""
    return (title or "").strip().lower().rstrip(".!?")

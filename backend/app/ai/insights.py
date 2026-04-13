"""AI-generated household insights cached per family per day.

Today: one insight type, ``off_track`` — a one-sentence plain-English
explanation of the parent dashboard's household_health status.

Design
------
- The deterministic rule engine in ``dashboard_service._derive_household_health``
  remains the source of truth for the STATUS. The AI layer only generates
  a NARRATIVE that explains the status to humans. A bug in the AI layer
  can never change whether the family is on_track / at_risk / off_track.
- The narrative is cached in ``ai_daily_insights`` keyed by
  (family_id, insight_type, as_of_date). First dashboard load of the day
  generates and caches; subsequent loads read the cached row.
- On AI failure or missing API key, a rule-based fallback narrative is
  synthesized from the same reasons the rule engine produced. The fallback
  is NOT cached — next request retries the AI call.
- Narrative is constrained: ≤ 300 chars, no emoji, no questions, third
  person so it can be rendered as a banner caption.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.scheduled import AIDailyInsight

logger = logging.getLogger("scout.ai.insights")

INSIGHT_TYPE_OFF_TRACK = "off_track"
MAX_NARRATIVE_CHARS = 300


def get_off_track_insight(
    db: Session,
    *,
    family_id: uuid.UUID,
    health: dict,
    child_statuses: list[dict],
    as_of: date | None = None,
) -> dict:
    """Return a cached-or-freshly-generated off_track insight for the
    parent dashboard.

    ``health`` is the dict returned by ``_derive_household_health``:
    ``{"status": "...", "reasons": [...]}``. This function does not
    compute or override that status.
    """
    as_of = as_of or date.today()

    # Cache hit?
    cached = db.scalars(
        select(AIDailyInsight)
        .where(AIDailyInsight.family_id == family_id)
        .where(AIDailyInsight.insight_type == INSIGHT_TYPE_OFF_TRACK)
        .where(AIDailyInsight.as_of_date == as_of)
    ).first()
    if cached:
        return {
            "status": cached.status,
            "narrative": cached.content,
            "model": cached.model,
            "as_of": as_of.isoformat(),
            "source": "cached",
        }

    # Generate fresh
    narrative = None
    model_used: str | None = None
    ai_tried = False
    try:
        from app.config import settings
        if settings.anthropic_api_key:
            ai_tried = True
            narrative, model_used = _generate_narrative_with_ai(
                health=health, child_statuses=child_statuses
            )
    except Exception as e:
        logger.warning("off_track_insight_ai_failed: %s", str(e)[:200])
        narrative = None

    if narrative:
        # Cache successful AI generation inside a savepoint so a
        # spurious failure here doesn't corrupt the caller's
        # transaction boundary.
        try:
            with db.begin_nested():
                row = AIDailyInsight(
                    family_id=family_id,
                    insight_type=INSIGHT_TYPE_OFF_TRACK,
                    as_of_date=as_of,
                    status=health.get("status", "unknown"),
                    content=narrative,
                    model=model_used,
                )
                db.add(row)
                db.flush()
        except Exception:
            pass
        return {
            "status": health.get("status"),
            "narrative": narrative,
            "model": model_used,
            "as_of": as_of.isoformat(),
            "source": "ai",
        }

    # Fallback — deterministic narrative built from reasons.
    fallback = _rule_based_narrative(health=health, child_statuses=child_statuses)
    return {
        "status": health.get("status"),
        "narrative": fallback,
        "model": None,
        "as_of": as_of.isoformat(),
        "source": "fallback" if not ai_tried else "fallback_after_ai_fail",
    }


def invalidate_off_track_insight(
    db: Session, family_id: uuid.UUID, as_of: date | None = None
) -> None:
    """Drop today's cached insight so the next dashboard load regenerates.
    Called when underlying data (tasks, bills, action items) changes in
    ways that might materially affect the banner. Use sparingly.

    Transaction-neutral: caller decides when to commit.
    """
    as_of = as_of or date.today()
    row = db.scalars(
        select(AIDailyInsight)
        .where(AIDailyInsight.family_id == family_id)
        .where(AIDailyInsight.insight_type == INSIGHT_TYPE_OFF_TRACK)
        .where(AIDailyInsight.as_of_date == as_of)
    ).first()
    if row:
        db.delete(row)
        db.flush()


def _generate_narrative_with_ai(
    *, health: dict, child_statuses: list[dict]
) -> tuple[str, str]:
    """Call the AI provider to summarize the rule-engine data into a
    one-sentence caption. Returns (narrative, model_name) on success,
    raises on failure."""
    from app.ai.provider import get_provider

    reasons = health.get("reasons", [])
    reasons_lines = []
    for r in reasons[:8]:
        if r.get("type") == "incomplete_tasks":
            reasons_lines.append(
                f"- {r.get('child')} has {r.get('count')} incomplete tasks today"
            )
        elif r.get("type") == "pending_actions":
            reasons_lines.append(
                f"- {r.get('count')} pending action items"
            )
        elif r.get("type") == "pending_purchase_requests":
            reasons_lines.append(
                f"- {r.get('count')} pending purchase requests"
            )
        elif r.get("type") == "overdue_bills":
            reasons_lines.append(
                f"- {r.get('count')} overdue bills"
            )
        else:
            reasons_lines.append(f"- {r.get('type')}: {r}")

    child_lines = [
        f"- {c['name']}: {c.get('tasks_completed', 0)}/{c.get('tasks_total', 0)} tasks today, "
        f"{c.get('weekly_wins', 0)} daily wins this week"
        for c in child_statuses[:6]
    ]

    system = (
        "You are writing a one-sentence plain-English caption for a "
        "family ops dashboard banner. Tone: direct, factual, not cheerful. "
        "Rules: ONE sentence, max 220 characters, no emoji, no questions, "
        "no headings, no 'we' or 'you'; refer to the family in the third "
        "person. Do not repeat the status word. Do not invent new facts. "
        "If there are zero concerning reasons, produce a short positive "
        "sentence based on the data provided."
    )
    status = health.get("status", "unknown")
    user = (
        f"Household status (already decided, do not change): {status}\n"
        f"Reasons:\n" + ("\n".join(reasons_lines) if reasons_lines else "- none")
        + f"\nChildren today:\n" + ("\n".join(child_lines) if child_lines else "- none")
        + "\n\nWrite the banner sentence now."
    )

    provider = get_provider()
    # Use the classification (fast) model by default — the
    # orchestrator's normal chat model is heavier than we need for a
    # single sentence.
    from app.config import settings
    response = provider.chat(
        messages=[{"role": "user", "content": user}],
        system=system,
        model=settings.ai_classification_model or settings.ai_chat_model,
        max_tokens=200,
        temperature=0.2,
    )
    text = (response.content or "").strip()
    # Enforce length + one-line.
    text = text.replace("\n", " ").strip()
    if len(text) > MAX_NARRATIVE_CHARS:
        text = text[:MAX_NARRATIVE_CHARS - 1].rstrip() + "…"
    if not text:
        raise RuntimeError("AI returned empty narrative")
    return text, response.model


def _rule_based_narrative(*, health: dict, child_statuses: list[dict]) -> str:
    """Deterministic fallback used when the AI layer is unavailable or
    returns an error. Same facts, less eloquent phrasing."""
    reasons = health.get("reasons", [])
    if not reasons:
        done = sum(c.get("tasks_completed", 0) for c in child_statuses)
        total = sum(c.get("tasks_total", 0) for c in child_statuses)
        if total > 0 and done == total:
            return f"All {total} tasks are complete across the family today."
        return "Nothing pressing on the household right now."

    bits: list[str] = []
    for r in reasons:
        t = r.get("type")
        if t == "incomplete_tasks":
            bits.append(f"{r.get('child')} has {r.get('count')} tasks left")
        elif t == "pending_actions":
            bits.append(f"{r.get('count')} pending action items")
        elif t == "pending_purchase_requests":
            bits.append(f"{r.get('count')} purchase requests waiting for approval")
        elif t == "overdue_bills":
            bits.append(f"{r.get('count')} overdue bills")
    if not bits:
        return "Household has a few open items."
    sentence = ", ".join(bits[:3])
    if len(bits) > 3:
        sentence += f", plus {len(bits) - 3} more"
    sentence = sentence[:1].upper() + sentence[1:] + "."
    if len(sentence) > MAX_NARRATIVE_CHARS:
        sentence = sentence[:MAX_NARRATIVE_CHARS - 1].rstrip() + "…"
    return sentence

"""Sprint 05 Phase 1 - proactive nudges core engine.

Scanners (scan_overdue_tasks, scan_upcoming_events, scan_missed_routines)
return NudgeProposal dataclasses from pure read-only SQL. apply_proactivity
gates them per the caller's member_config['ai.personality'].proactivity
setting. resolve_occurrence_fields computes the immutable occurrence_at_utc
and occurrence_local_date (timezone-aware, from the family's configured
timezone) used for dedupe_key generation. dispatch_with_items is the sink
that writes parent nudge_dispatches + child nudge_dispatch_items rows,
creates a parent_action_items row, and calls push_service.send_push when
the member has an active device.

Idempotency is guaranteed by the UNIQUE (source_dedupe_key) constraint on
scout.nudge_dispatch_items. If every child row for a proposed dispatch
would conflict, the parent dispatch row is not written.

run_nudge_scan is the orchestration entry point: scan -> proactivity ->
resolve occurrence -> dispatch. run_nudge_scan_tick is the scheduler-facing
wrapper that run_nudge_scan + logs the result; exceptions propagate to the
tick's outer try/except so rollback happens cleanly per the existing
scheduler pattern.

Fixed copy templates ship here in Phase 1. Phase 3 replaces them with
AI-composed per-member copy.
"""

from __future__ import annotations

import json as _json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any

import pytz
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.action_items import ParentActionItem
from app.models.nudges import NudgeDispatch, NudgeDispatchItem
from app.models.push import PushDevice
from app.models.quiet_hours import QuietHoursFamily  # noqa: F401
from app.services import ai_personality_service, push_service

logger = logging.getLogger("scout.nudges")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@dataclass
class NudgeProposal:
    """A scanner's output before proactivity gate and dispatch.
    Serializable; easy to inspect in tests."""

    family_member_id: uuid.UUID
    trigger_kind: str          # overdue_task | upcoming_event | missed_routine
    trigger_entity_kind: str   # personal_task | event | task_instance
    trigger_entity_id: uuid.UUID | None
    scheduled_for: datetime
    severity: str = "normal"
    # Copy context (title, time string, etc.) used by the template renderer
    # and by dispatch for source_metadata on the child row.
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class OccurrenceFields:
    """Computed in resolve_occurrence_fields. Immutable for a given
    (member, trigger, entity, occurrence) tuple; never changes when
    quiet-hours delays delivery."""

    occurrence_at_utc: datetime
    occurrence_local_date: date
    source_dedupe_key: str


@dataclass
class ProposalBundle:
    """A group of NudgeProposals for the SAME family_member_id whose
    effective deliver_after times are within a small window. One
    parent NudgeDispatch is written per bundle; proposals become
    child nudge_dispatch_items. Singletons are also bundles (size 1)."""

    family_member_id: uuid.UUID
    proposals: list[NudgeProposal]

    @property
    def effective_deliver_after(self) -> datetime:
        return min(p.scheduled_for for p in self.proposals)


# ---------------------------------------------------------------------------
# Stubs. Each fills in via TDD in a later task (Tasks 4-9).
# ---------------------------------------------------------------------------


def scan_overdue_tasks(db: Session, now_utc: datetime) -> list[NudgeProposal]:
    """Emit one proposal per active personal_tasks row whose due_at
    has passed. Pure read; no side effects. scheduled_for is the
    original due_at so the dispatch dedupe_key uses the same moment
    regardless of when the scanner actually runs."""
    rows = db.execute(
        text(
            """
            SELECT id, assigned_to, title, due_at
            FROM personal_tasks
            WHERE status != 'done'
              AND due_at IS NOT NULL
              AND due_at < :now
            """
        ),
        {"now": now_utc},
    ).all()
    proposals: list[NudgeProposal] = []
    for row in rows:
        proposals.append(
            NudgeProposal(
                family_member_id=row.assigned_to,
                trigger_kind="overdue_task",
                trigger_entity_kind="personal_task",
                trigger_entity_id=row.id,
                scheduled_for=row.due_at,
                severity="normal",
                context={
                    "title": row.title,
                    "due_time": row.due_at.strftime("%I:%M %p"),
                    "occurrence_at_utc": row.due_at,
                },
            )
        )
    return proposals


def scan_upcoming_events(
    db: Session, now_utc: datetime, lead_minutes: int = 30
) -> list[NudgeProposal]:
    """Events starting within lead_minutes of now produce one proposal
    per attendee. Past, cancelled, and all-day events are excluded.
    scheduled_for = starts_at - lead_minutes so the proposal carries
    the intended lead intact through apply_proactivity."""
    horizon = now_utc + timedelta(minutes=lead_minutes)
    rows = db.execute(
        text(
            """
            SELECT e.id, e.title, e.starts_at, ea.family_member_id
            FROM events e
            JOIN event_attendees ea ON ea.event_id = e.id
            WHERE e.is_cancelled = false
              AND e.all_day = false
              AND e.starts_at > :now
              AND e.starts_at <= :horizon
            """
        ),
        {"now": now_utc, "horizon": horizon},
    ).all()
    proposals: list[NudgeProposal] = []
    for row in rows:
        proposals.append(
            NudgeProposal(
                family_member_id=row.family_member_id,
                trigger_kind="upcoming_event",
                trigger_entity_kind="event",
                trigger_entity_id=row.id,
                scheduled_for=row.starts_at - timedelta(minutes=lead_minutes),
                severity="normal",
                context={
                    "title": row.title,
                    "start_time": row.starts_at.strftime("%I:%M %p"),
                    "occurrence_at_utc": row.starts_at,
                },
            )
        )
    return proposals


def scan_missed_routines(
    db: Session, now_utc: datetime
) -> list[NudgeProposal]:
    """task_instances rows with routine_id (not chore_template) whose
    due_at has passed AND are not completed (respecting
    override_completed). severity='low' per revised plan Section 6.
    scheduled_for = due_at + 15 min (lead-after-miss; apply_proactivity
    may shift earlier)."""
    rows = db.execute(
        text(
            """
            SELECT ti.id,
                   ti.family_member_id,
                   ti.due_at,
                   r.name AS routine_name
            FROM task_instances ti
            JOIN routines r ON r.id = ti.routine_id
            WHERE ti.routine_id IS NOT NULL
              AND ti.is_completed = false
              AND COALESCE(ti.override_completed, false) = false
              AND ti.due_at < :now
            """
        ),
        {"now": now_utc},
    ).all()
    proposals: list[NudgeProposal] = []
    for row in rows:
        proposals.append(
            NudgeProposal(
                family_member_id=row.family_member_id,
                trigger_kind="missed_routine",
                trigger_entity_kind="task_instance",
                trigger_entity_id=row.id,
                scheduled_for=row.due_at + timedelta(minutes=15),
                severity="low",
                context={
                    "name": row.routine_name,
                    "due_time": row.due_at.strftime("%I:%M %p"),
                    "occurrence_at_utc": row.due_at,
                },
            )
        )
    return proposals


_FORTHCOMING_SHIFT_MINUTES = {
    "upcoming_event": 30,
    "missed_routine": 10,
    # overdue_task: 0 -- cannot fire before already-overdue
}


# Fixed Phase 1 copy. Phase 3 swaps these for AI-composed per-member copy.
_BODY_TEMPLATES = {
    "overdue_task":    "Reminder: {title} was due at {due_time}.",
    "upcoming_event":  "Heads up: {title} at {start_time}.",
    "missed_routine":  "{name} hasn't been checked off yet (was due at {due_time}).",
}

_INBOX_TITLE_PREFIX = {
    "overdue_task":    "Overdue",
    "upcoming_event":  "Starting soon",
    "missed_routine":  "Routine check",
}


def _render_body(proposal: "NudgeProposal") -> str:
    template = _BODY_TEMPLATES.get(proposal.trigger_kind, "Scout nudge")
    try:
        return template.format(**proposal.context)
    except KeyError as e:
        logger.warning(
            "nudge body template missing key=%s for trigger_kind=%s; using raw template",
            e, proposal.trigger_kind,
        )
        return template


def _render_inbox_title(proposal: "NudgeProposal") -> str:
    prefix = _INBOX_TITLE_PREFIX.get(proposal.trigger_kind, "Scout")
    source = proposal.context.get("title") or proposal.context.get("name") or ""
    return f"{prefix}: {source}" if source else prefix


def _render_bundle_body(proposals: list["NudgeProposal"]) -> str:
    """Render a composite body for a bundle. Singletons get the
    Phase 1 single-proposal body verbatim; multi-item bundles get
    a summary line so push notifications fit in a single OS banner."""
    if len(proposals) == 1:
        return _render_body(proposals[0])
    titles = [
        p.context.get("title") or p.context.get("name") or "(untitled)"
        for p in proposals
    ]
    if len(proposals) == 2:
        return f"You have 2 items to check: {titles[0]} and {titles[1]}."
    return (
        f"You have {len(proposals)} items to check: "
        f"{titles[0]}, {titles[1]}, and {len(proposals) - 2} more."
    )


def _render_bundle_inbox_title(proposals: list["NudgeProposal"]) -> str:
    """Short inbox title for a bundle. Singletons reuse Phase 1 title."""
    if len(proposals) == 1:
        return _render_inbox_title(proposals[0])
    return f"You have {len(proposals)} nudges"


_SEVERITY_ORDER = {"low": 0, "normal": 1, "high": 2}


def _bundle_severity(bundle: "ProposalBundle") -> str:
    """Bundle severity is the max of its children's severities.
    Order: low < normal < high. Drives the quiet-hours gate."""
    return max(
        (p.severity for p in bundle.proposals),
        key=lambda s: _SEVERITY_ORDER.get(s, 0),
    )


def _as_utc_aware(ts: datetime | None) -> datetime | None:
    """Attach UTC tzinfo to a naive datetime so psycopg2 writes it to
    a TIMESTAMPTZ column as a UTC moment rather than as the session's
    local time. The repo convention is naive-UTC everywhere in Python,
    but Postgres TIMESTAMPTZ columns treat naive literals as session-
    local; this helper is the write-time adapter."""
    if ts is None:
        return None
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def _family_id_for_member(db: Session, member_id: uuid.UUID) -> uuid.UUID:
    row = db.execute(
        text("SELECT family_id FROM family_members WHERE id = :mid"),
        {"mid": member_id},
    ).first()
    if row is None:
        raise ValueError(f"family_members row missing for {member_id}")
    return row[0]


def _route_hint(proposal: "NudgeProposal") -> str:
    if proposal.trigger_kind == "overdue_task" and proposal.trigger_entity_id:
        return f"/today?task={proposal.trigger_entity_id}"
    if proposal.trigger_kind == "upcoming_event" and proposal.trigger_entity_id:
        return f"/calendar?event={proposal.trigger_entity_id}"
    return "/today"


def apply_proactivity(
    db: Session, proposals: list[NudgeProposal], now_utc: datetime
) -> list[NudgeProposal]:
    """Gate + lead-time adjust per member proactivity setting. quiet
    drops proposals. balanced passes through unchanged. forthcoming
    shifts scheduled_for earlier for triggers that support it (see
    _FORTHCOMING_SHIFT_MINUTES). overdue_task is never shifted.

    Stamps the effective proactivity setting into proposal.context
    so dispatch_with_items can record it on the child row without a
    second DB roundtrip.

    Caches the member->setting lookup to one call per unique
    family_member_id per invocation."""
    out: list[NudgeProposal] = []
    settings_cache: dict[uuid.UUID, str] = {}
    for prop in proposals:
        setting = settings_cache.get(prop.family_member_id)
        if setting is None:
            resolved = ai_personality_service.get_resolved_config(
                db, prop.family_member_id
            )
            setting = resolved.get("proactivity", "balanced")
            settings_cache[prop.family_member_id] = setting

        if setting == "quiet":
            continue

        shifted_for = prop.scheduled_for
        if setting == "forthcoming":
            shift = _FORTHCOMING_SHIFT_MINUTES.get(prop.trigger_kind, 0)
            if shift > 0:
                shifted_for = prop.scheduled_for - timedelta(minutes=shift)

        new_context = {**prop.context, "proactivity": setting}
        out.append(
            NudgeProposal(
                family_member_id=prop.family_member_id,
                trigger_kind=prop.trigger_kind,
                trigger_entity_kind=prop.trigger_entity_kind,
                trigger_entity_id=prop.trigger_entity_id,
                scheduled_for=shifted_for,
                severity=prop.severity,
                context=new_context,
            )
        )
    return out


def batch_proposals(
    proposals: list[NudgeProposal], window_minutes: int = 10
) -> list[ProposalBundle]:
    """Group proposals per member; cluster each member's list into
    bundles where every member of a cluster is within window_minutes
    of the cluster's anchor (first proposal sorted by scheduled_for).

    Anchor semantics (not nearest-neighbor) prevent a chain like
    [0min, 8min, 15min, 22min] from collapsing into a single 22-min-wide
    bundle. The first cluster holds 0 and 8; 15 starts a new cluster
    because it is outside window_minutes of the 0-min anchor.
    """
    if not proposals:
        return []

    # Stable grouping by member (insertion order preserved)
    per_member: dict[uuid.UUID, list[NudgeProposal]] = {}
    for p in proposals:
        per_member.setdefault(p.family_member_id, []).append(p)

    bundles: list[ProposalBundle] = []
    window = timedelta(minutes=window_minutes)
    for member_id, items in per_member.items():
        items_sorted = sorted(items, key=lambda p: p.scheduled_for)
        cluster: list[NudgeProposal] = []
        anchor: datetime | None = None
        for p in items_sorted:
            if not cluster:
                cluster = [p]
                anchor = p.scheduled_for
                continue
            if (p.scheduled_for - anchor) <= window:
                cluster.append(p)
            else:
                bundles.append(ProposalBundle(member_id, cluster))
                cluster = [p]
                anchor = p.scheduled_for
        if cluster:
            bundles.append(ProposalBundle(member_id, cluster))
    return bundles


def _is_minute_in_window(current: int, start: int, end: int) -> bool:
    """Minute-of-day window. Handles wrap across midnight when end < start."""
    if start == end:
        return False
    if start < end:
        return start <= current < end
    # Wraps: start=1320 (22:00), end=420 (07:00)
    return current >= start or current < end


def _resolve_quiet_hours_window(
    db: Session, family_member_id: uuid.UUID
) -> tuple[int, int, str] | None:
    """Returns (start_minute, end_minute, family_timezone) or None if
    no quiet hours configured for the member (neither family default
    nor per-member override)."""
    member_row = db.execute(
        text(
            """
            SELECT fm.family_id, f.timezone
            FROM family_members fm
            JOIN families f ON f.id = fm.family_id
            WHERE fm.id = :mid
            """
        ),
        {"mid": family_member_id},
    ).first()
    if member_row is None or not member_row.timezone:
        return None
    tz_name = member_row.timezone
    family_id = member_row.family_id

    # Member override wins
    override_row = db.execute(
        text(
            """
            SELECT value
            FROM member_config
            WHERE family_member_id = :mid AND key = 'nudges.quiet_hours'
            """
        ),
        {"mid": family_member_id},
    ).first()
    if override_row and override_row.value:
        v = (
            override_row.value
            if isinstance(override_row.value, dict)
            else _json.loads(override_row.value)
        )
        return int(v["start_local_minute"]), int(v["end_local_minute"]), tz_name

    # Family default
    family_row = db.execute(
        text(
            """
            SELECT start_local_minute, end_local_minute
            FROM scout.quiet_hours_family
            WHERE family_id = :fid
            """
        ),
        {"fid": family_id},
    ).first()
    if family_row is None:
        return None
    return (
        int(family_row.start_local_minute),
        int(family_row.end_local_minute),
        tz_name,
    )


def _window_end_in_utc(
    now_utc: datetime, end_minute: int, tz_name: str
) -> datetime:
    """Return the next UTC moment matching end_minute in the family's
    local timezone. If end_minute hasn't occurred yet today in local
    time, return today's end; otherwise tomorrow's."""
    tz = pytz.timezone(tz_name)
    aware_utc = (
        pytz.utc.localize(now_utc) if now_utc.tzinfo is None
        else now_utc.astimezone(pytz.utc)
    )
    local_now = aware_utc.astimezone(tz)
    end_hour, end_min = divmod(end_minute, 60)
    candidate_local = local_now.replace(
        hour=end_hour, minute=end_min, second=0, microsecond=0
    )
    if candidate_local <= local_now:
        candidate_local += timedelta(days=1)
    return candidate_local.astimezone(pytz.utc).replace(tzinfo=None)


def should_suppress_for_quiet_hours(
    db: Session,
    family_member_id: uuid.UUID,
    severity: str,
    now_utc: datetime,
) -> tuple[str, datetime | None]:
    """Resolve quiet-hours gate per revised plan Section 4 step 5.

    Returns (decision, hold_until_utc). decision is one of:
      'deliver' - outside window, or high severity, or no config
      'drop' - inside window and low severity
      'hold' - inside window and normal severity; hold_until_utc is
               the UTC timestamp matching the window's end in family local
    """
    resolved = _resolve_quiet_hours_window(db, family_member_id)
    if resolved is None:
        return ("deliver", None)
    start_minute, end_minute, tz_name = resolved

    tz = pytz.timezone(tz_name)
    aware_utc = (
        pytz.utc.localize(now_utc) if now_utc.tzinfo is None
        else now_utc.astimezone(pytz.utc)
    )
    local_now = aware_utc.astimezone(tz)
    current_minute = local_now.hour * 60 + local_now.minute

    if not _is_minute_in_window(current_minute, start_minute, end_minute):
        return ("deliver", None)

    if severity == "high":
        return ("deliver", None)
    if severity == "low":
        return ("drop", None)
    # normal
    hold_utc = _window_end_in_utc(now_utc, end_minute, tz_name)
    return ("hold", hold_utc)


def resolve_deliver_after(
    db: Session, proposal: NudgeProposal, now_utc: datetime
) -> tuple[datetime, str | None]:
    """Compose scheduled_for with the quiet-hours gate into an effective
    deliver_after_utc + optional suppressed_reason. Per revised plan
    Section 6, never mutates occurrence_at_utc or occurrence_local_date."""
    decision, hold_utc = should_suppress_for_quiet_hours(
        db, proposal.family_member_id, proposal.severity, now_utc
    )
    if decision == "deliver":
        return (proposal.scheduled_for, None)
    if decision == "drop":
        return (proposal.scheduled_for, "quiet_hours")
    # hold
    effective = (
        max(proposal.scheduled_for, hold_utc)
        if hold_utc is not None
        else proposal.scheduled_for
    )
    return (effective, None)


def resolve_occurrence_fields(
    db: Session, proposal: NudgeProposal
) -> OccurrenceFields:
    """Compute the immutable occurrence triple. Reads the raw source
    timestamp from proposal.context['occurrence_at_utc'] (scanner
    stamps this), looks up the family's timezone, and converts the
    UTC moment to a local date. source_dedupe_key is stable across
    scheduler ticks and proactivity shifts because neither
    occurrence_at_utc nor the family timezone changes between ticks
    for the same source event."""
    occurrence_at = proposal.context.get("occurrence_at_utc")
    if occurrence_at is None:
        raise ValueError(
            f"proposal.context missing 'occurrence_at_utc' for "
            f"trigger_kind={proposal.trigger_kind}. The scanner for "
            f"this trigger must stamp the raw source timestamp."
        )

    row = db.execute(
        text(
            """
            SELECT f.timezone
            FROM family_members fm
            JOIN families f ON f.id = fm.family_id
            WHERE fm.id = :mid
            """
        ),
        {"mid": proposal.family_member_id},
    ).first()

    if row is None or not row.timezone:
        logger.warning(
            "resolve_occurrence_fields: no timezone for member=%s; "
            "falling back to UTC date.",
            proposal.family_member_id,
        )
        local_date = occurrence_at.date()
    else:
        try:
            tz = pytz.timezone(row.timezone)
            # Treat naive UTC as UTC (the repo convention for timestamptz
            # hydrated into naive Python datetimes)
            aware_utc = (
                pytz.utc.localize(occurrence_at)
                if occurrence_at.tzinfo is None
                else occurrence_at.astimezone(pytz.utc)
            )
            local_dt = aware_utc.astimezone(tz)
            local_date = local_dt.date()
        except pytz.UnknownTimeZoneError:
            logger.warning(
                "resolve_occurrence_fields: unknown timezone %r for member=%s; "
                "falling back to UTC date.",
                row.timezone,
                proposal.family_member_id,
            )
            local_date = occurrence_at.date()

    entity_part = (
        str(proposal.trigger_entity_id)
        if proposal.trigger_entity_id is not None
        else "null"
    )
    dedupe_key = (
        f"{proposal.family_member_id}:{proposal.trigger_kind}:"
        f"{entity_part}:{local_date.isoformat()}"
    )

    return OccurrenceFields(
        occurrence_at_utc=occurrence_at,
        occurrence_local_date=local_date,
        source_dedupe_key=dedupe_key,
    )


def dispatch_with_items(
    db: Session, bundles: list[ProposalBundle], now_utc: datetime
) -> int:
    """Per-bundle: resolve occurrence for each child -> pre-check dedupe ->
    quiet-hours gate on bundle severity -> SAVEPOINT -> parent dispatch +
    N child items + optional Inbox + optional push -> commit savepoint.

    Three quiet-hours decisions per bundle (revised plan Section 4 step 5):
      * deliver: status='delivered', Inbox row + push as usual
      * hold:    status='pending', deliver_after_utc=hold_until_utc, no
                 Inbox, no push. Children are still written so the
                 scanner's pre-check on the next tick skips re-dispatch.
      * drop:    status='suppressed', suppressed_reason='quiet_hours',
                 no Inbox, no push. Children written as an audit trail
                 and to prevent re-fire on subsequent ticks.

    Push errors are logged and swallowed so Inbox remains authoritative
    on the deliver path. UNIQUE (source_dedupe_key) is the authoritative
    dedupe boundary; IntegrityError inside the savepoint rolls back that
    bundle alone, leaving sibling bundles intact.

    Mixed-kind bundles (rare, e.g. overdue_task + missed_routine within
    10 min for the same member) use the FIRST proposal's trigger_kind
    for the Inbox action_type + push category. Stability over cleverness;
    v1 edge case.

    Returns an int counting every bundle that produced parent + child
    rows, i.e. delivered + held + suppressed bundles all contribute +1.
    Bundles where every child was already dispatched (dedupe) do not
    increment. Never calls db.commit() -- the caller (scheduler tick
    or test fixture) owns transaction boundaries."""
    written = 0
    for bundle in bundles:
        # Resolve occurrence + pre-check dedupe per child
        resolved_pairs: list[tuple[NudgeProposal, OccurrenceFields]] = []
        for proposal in bundle.proposals:
            try:
                fields = resolve_occurrence_fields(db, proposal)
            except ValueError as e:
                logger.warning("dispatch skipped: %s", e)
                continue
            existing = (
                db.query(NudgeDispatchItem)
                .filter_by(source_dedupe_key=fields.source_dedupe_key)
                .first()
            )
            if existing is not None:
                continue
            resolved_pairs.append((proposal, fields))

        if not resolved_pairs:
            # Entire bundle already dispatched on a prior tick.
            continue

        # Bundle severity drives the quiet-hours gate.
        bundle_sev = _bundle_severity(bundle)
        decision, hold_utc = should_suppress_for_quiet_hours(
            db, bundle.family_member_id, bundle_sev, now_utc
        )

        try:
            with db.begin_nested():
                proposals_only = [p for p, _ in resolved_pairs]
                body = _render_bundle_body(proposals_only)
                short_title = _render_bundle_inbox_title(proposals_only)
                first_kind = resolved_pairs[0][0].trigger_kind

                parent = NudgeDispatch(
                    family_member_id=bundle.family_member_id,
                    severity=bundle_sev,
                    source_count=len(resolved_pairs),
                    body=body,
                    delivered_channels=[],
                )
                if decision == "drop":
                    parent.status = "suppressed"
                    parent.suppressed_reason = "quiet_hours"
                    parent.deliver_after_utc = _as_utc_aware(
                        bundle.effective_deliver_after
                    )
                elif decision == "hold":
                    parent.status = "pending"
                    parent.deliver_after_utc = _as_utc_aware(hold_utc)
                else:  # deliver
                    parent.status = "delivered"
                    parent.deliver_after_utc = _as_utc_aware(
                        bundle.effective_deliver_after
                    )
                    parent.delivered_at_utc = _as_utc_aware(now_utc)
                db.add(parent)
                db.flush()

                # Children -- written for all three decisions. For hold
                # + drop these serve as the dedupe boundary so the next
                # scan tick's pre-check skips re-dispatch.
                for proposal, fields in resolved_pairs:
                    source_metadata = {
                        k: (
                            v.isoformat()
                            if isinstance(v, (datetime, date))
                            else str(v)
                        )
                        for k, v in proposal.context.items()
                        if k != "occurrence_at_utc"
                    }
                    child = NudgeDispatchItem(
                        dispatch_id=parent.id,
                        family_member_id=proposal.family_member_id,
                        trigger_kind=proposal.trigger_kind,
                        trigger_entity_kind=proposal.trigger_entity_kind,
                        trigger_entity_id=proposal.trigger_entity_id,
                        occurrence_at_utc=_as_utc_aware(
                            fields.occurrence_at_utc
                        ),
                        occurrence_local_date=fields.occurrence_local_date,
                        source_dedupe_key=fields.source_dedupe_key,
                        source_metadata=source_metadata,
                    )
                    db.add(child)
                db.flush()  # UNIQUE checks fire here

                if decision == "deliver":
                    family_id = _family_id_for_member(
                        db, bundle.family_member_id
                    )
                    # Migration 050 widened chk_parent_action_items_action_type
                    # to include nudge.<trigger_kind>. Mixed-kind bundles use
                    # the first child's trigger_kind (stability over cleverness).
                    inbox = ParentActionItem(
                        family_id=family_id,
                        created_by_member_id=bundle.family_member_id,
                        action_type=f"nudge.{first_kind}",
                        title=short_title,
                        detail=body,
                        entity_type=resolved_pairs[0][0].trigger_entity_kind,
                        entity_id=resolved_pairs[0][0].trigger_entity_id,
                        status="pending",
                    )
                    db.add(inbox)
                    db.flush()
                    parent.parent_action_item_id = inbox.id

                    delivered: list[str] = ["inbox"]
                    active_device = (
                        db.query(PushDevice)
                        .filter(
                            PushDevice.family_member_id
                            == bundle.family_member_id,
                            PushDevice.is_active == True,  # noqa: E712
                        )
                        .first()
                    )
                    if active_device is not None:
                        try:
                            result = push_service.send_push(
                                db,
                                family_member_id=bundle.family_member_id,
                                category=f"nudge.{first_kind}",
                                title=short_title,
                                body=body,
                                data={
                                    "route_hint": _route_hint(
                                        resolved_pairs[0][0]
                                    ),
                                    "trigger_kind": first_kind,
                                },
                                trigger_source="nudge_scan",
                            )
                            if getattr(result, "delivery_ids", None):
                                parent.push_delivery_id = result.delivery_ids[0]
                                delivered.append("push")
                        except Exception as push_err:
                            logger.exception(
                                "nudge push failed member=%s err=%s",
                                bundle.family_member_id, push_err,
                            )
                    parent.delivered_channels = delivered
                # hold + drop: delivered_channels stays [],
                # parent_action_item_id stays NULL, push_delivery_id stays NULL.
            written += 1
        except IntegrityError:
            # Race: UNIQUE on source_dedupe_key won. Savepoint auto-rolled
            # back so sibling bundles in this call remain intact.
            continue
    return written


# ---------------------------------------------------------------------------
# Orchestration entry points
# ---------------------------------------------------------------------------


def run_nudge_scan(db: Session, now_utc: datetime | None = None) -> int:
    """End-to-end: scan all three sources, apply proactivity gate,
    batch into bundles, dispatch. Returns count of new parent
    dispatches (delivered + held + suppressed)."""
    ts = now_utc or _utcnow()
    proposals: list[NudgeProposal] = []
    proposals.extend(scan_overdue_tasks(db, ts))
    proposals.extend(scan_upcoming_events(db, ts))
    proposals.extend(scan_missed_routines(db, ts))
    gated = apply_proactivity(db, proposals, ts)
    bundles = batch_proposals(gated)
    return dispatch_with_items(db, bundles, ts)


def run_nudge_scan_tick(db: Session, now_utc: datetime) -> None:
    """Scheduler tick entry point. Logs the count. Exceptions propagate
    to the scheduler's outer try/except/rollback so one failure does
    not poison neighbouring runners on the same tick. Never catch
    broadly here."""
    count = run_nudge_scan(db, now_utc=now_utc)
    logger.info("nudge_scan_tick count=%s", count)

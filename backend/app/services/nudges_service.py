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

import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

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


# ---------------------------------------------------------------------------
# Stubs. Each fills in via TDD in a later task (Tasks 4-9).
# ---------------------------------------------------------------------------


def scan_overdue_tasks(db: Session, now_utc: datetime) -> list[NudgeProposal]:
    """Emit one proposal per active personal_tasks row whose due_at has
    passed. Implemented in Task 4."""
    return []


def scan_upcoming_events(
    db: Session, now_utc: datetime, lead_minutes: int = 30
) -> list[NudgeProposal]:
    """Emit one proposal per attendee of a non-cancelled, non-all-day
    event starting within lead_minutes. Implemented in Task 5."""
    return []


def scan_missed_routines(db: Session, now_utc: datetime) -> list[NudgeProposal]:
    """Emit one proposal per task_instances row whose routine-based
    due_at has passed and is not completed (respecting
    override_completed). Implemented in Task 6."""
    return []


def apply_proactivity(
    db: Session, proposals: list[NudgeProposal], now_utc: datetime
) -> list[NudgeProposal]:
    """Gate + lead-time adjust per member proactivity. Implemented in
    Task 7."""
    return proposals


def resolve_occurrence_fields(
    db: Session, proposal: NudgeProposal
) -> OccurrenceFields:
    """Compute occurrence_at_utc + occurrence_local_date (from the
    family's timezone) + source_dedupe_key. Implemented in Task 8."""
    raise NotImplementedError("resolve_occurrence_fields ships in Task 8")


def dispatch_with_items(
    db: Session, proposals: list[NudgeProposal], now_utc: datetime
) -> int:
    """Write parent nudge_dispatches + child nudge_dispatch_items rows,
    call push_service.send_push when the member has an active device,
    write a parent_action_items row. Returns the count of newly-written
    parent dispatches. Implemented in Task 9."""
    return 0


# ---------------------------------------------------------------------------
# Orchestration entry points
# ---------------------------------------------------------------------------


def run_nudge_scan(db: Session, now_utc: datetime | None = None) -> int:
    """End-to-end: scan all three sources, apply proactivity gate,
    dispatch. Returns count of new parent dispatches."""
    ts = now_utc or _utcnow()
    proposals: list[NudgeProposal] = []
    proposals.extend(scan_overdue_tasks(db, ts))
    proposals.extend(scan_upcoming_events(db, ts))
    proposals.extend(scan_missed_routines(db, ts))
    gated = apply_proactivity(db, proposals, ts)
    return dispatch_with_items(db, gated, ts)


def run_nudge_scan_tick(db: Session, now_utc: datetime) -> None:
    """Scheduler tick entry point. Logs the count. Exceptions propagate
    to the scheduler's outer try/except/rollback so one failure does
    not poison neighbouring runners on the same tick. Never catch
    broadly here."""
    count = run_nudge_scan(db, now_utc=now_utc)
    logger.info("nudge_scan_tick count=%s", count)

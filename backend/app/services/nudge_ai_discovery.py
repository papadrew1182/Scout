"""Sprint 05 Phase 5 Task 2 - AI-driven nudge discovery service.

Orchestrates one discovery cycle per family per tick. Three responsibilities:

1. ``build_family_state_digest`` - read-only projection of the family's
   structured state (personal_tasks, events, task_instances, routines,
   family_members). Intentionally excludes ``ai_messages``, connector_*
   tables, and health_* tables per Phase 5 plan section 7.

2. ``_is_throttled`` / ``_mark_discovery_ran`` - in-memory per-family
   rate limit so we never call the AI nudge-discovery endpoint more
   than once per hour per family. Phase 5 ships NO migration, so this
   state intentionally lives in-process. A multi-worker deploy may
   call the AI up to one extra time per worker per hour; that is
   acceptable bounded blast radius until Phase 6 adds persistence.

3. ``propose_nudges`` - full pipeline: throttle check, weekly soft-cap
   check, build digest, short-circuit if nothing actionable, call
   ``orchestrator.propose_nudges_from_digest``, mark run, convert each
   ``DiscoveryProposal`` to a ``NudgeProposal`` with
   ``trigger_kind='ai_suggested'``. Does NOT dispatch; the scheduler
   will hand the returned proposals to the existing nudges pipeline
   in a later task.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import orchestrator
from app.config import settings
from app.models.calendar import Event, EventAttendee
from app.models.foundation import Family, FamilyMember
from app.models.life_management import Routine, TaskInstance
from app.models.personal_tasks import PersonalTask
from app.schemas.nudge_discovery import DiscoveryProposal
from app.services import nudges_service
from app.services.nudges_service import NudgeProposal

logger = logging.getLogger("scout.nudges.ai_discovery")


# ---------------------------------------------------------------------------
# Module-level throttle state
# ---------------------------------------------------------------------------

_last_ai_discovery_run_utc: dict[uuid.UUID, datetime] = {}
_RATE_LIMIT_SECONDS = 3600  # one AI discovery call per family per hour

# Cap every digest section so the prompt stays bounded even for power-user
# families. 25 is generous for a 24h window and still fits comfortably in
# the nudge-model context budget.
_SECTION_CAP = 25


# ---------------------------------------------------------------------------
# Throttle helpers
# ---------------------------------------------------------------------------


def _is_throttled(family_id: uuid.UUID, now_utc: datetime) -> bool:
    """Pure check: has this family run discovery within the rate window?

    Read-only. Does not mutate _last_ai_discovery_run_utc.
    """
    last = _last_ai_discovery_run_utc.get(family_id)
    if last is None:
        return False
    elapsed = (now_utc - last).total_seconds()
    return elapsed < _RATE_LIMIT_SECONDS


def _mark_discovery_ran(family_id: uuid.UUID, now_utc: datetime) -> None:
    """Record that this family just consumed its AI discovery budget.

    Call this AFTER a successful orchestrator.propose_nudges_from_digest
    round trip, so a failed AI call does not consume the hour.
    """
    _last_ai_discovery_run_utc[family_id] = now_utc


# ---------------------------------------------------------------------------
# State digest
# ---------------------------------------------------------------------------


def _strip_tz(dt: datetime | None) -> datetime | None:
    """Normalize to naive UTC (the shape Scout persists).

    The orchestrator receives now_utc as aware or naive depending on the
    caller; sqlalchemy returns naive datetimes for our columns. We compare
    with naive throughout.
    """
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.replace(tzinfo=None)
    return dt


def build_family_state_digest(
    db: Session,
    family_id: uuid.UUID,
    now_utc: datetime,
) -> dict[str, Any]:
    """Return a structured snapshot of the family's actionable state.

    Reads from personal_tasks, events, task_instances, routines, and
    family_members. Each list capped at _SECTION_CAP items.

    Explicitly does NOT read ai_messages, connector_* tables, or
    health_* tables. Phase 5 plan section 7 excludes those sources.
    """
    now_naive = _strip_tz(now_utc)
    assert now_naive is not None  # for type checker; now_utc is required

    window_end = now_naive + timedelta(hours=24)
    missed_cutoff = now_naive - timedelta(days=3)

    # Members (id, first_name, role) - used for member resolution in the
    # AI prompt. No PII beyond first name.
    members_rows = db.execute(
        select(FamilyMember.id, FamilyMember.first_name, FamilyMember.role)
        .where(FamilyMember.family_id == family_id)
        .where(FamilyMember.is_active.is_(True))
        .limit(_SECTION_CAP)
    ).all()
    members = [
        {"id": str(m.id), "first_name": m.first_name, "role": m.role}
        for m in members_rows
    ]

    # Overdue personal tasks.
    overdue_rows = db.execute(
        select(
            PersonalTask.id,
            PersonalTask.title,
            PersonalTask.assigned_to,
            PersonalTask.due_at,
        )
        .where(PersonalTask.family_id == family_id)
        .where(PersonalTask.status == "pending")
        .where(PersonalTask.due_at.is_not(None))
        .where(PersonalTask.due_at < now_naive)
        .order_by(PersonalTask.due_at.asc())
        .limit(_SECTION_CAP)
    ).all()
    overdue_tasks = []
    for r in overdue_rows:
        due_naive = _strip_tz(r.due_at)
        overdue_tasks.append(
            {
                "id": str(r.id),
                "title": r.title,
                "assigned_to": str(r.assigned_to),
                "due_at": due_naive.isoformat() if due_naive else None,
                "overdue_hours": round(
                    (now_naive - due_naive).total_seconds() / 3600.0, 2
                ) if due_naive else None,
            }
        )

    # Upcoming tasks due in the next 24h.
    upcoming_task_rows = db.execute(
        select(
            PersonalTask.id,
            PersonalTask.title,
            PersonalTask.assigned_to,
            PersonalTask.due_at,
        )
        .where(PersonalTask.family_id == family_id)
        .where(PersonalTask.status == "pending")
        .where(PersonalTask.due_at.is_not(None))
        .where(PersonalTask.due_at >= now_naive)
        .where(PersonalTask.due_at <= window_end)
        .order_by(PersonalTask.due_at.asc())
        .limit(_SECTION_CAP)
    ).all()
    upcoming_tasks_24h = []
    for r in upcoming_task_rows:
        due_naive = _strip_tz(r.due_at)
        upcoming_tasks_24h.append(
            {
                "id": str(r.id),
                "title": r.title,
                "assigned_to": str(r.assigned_to),
                "due_at": due_naive.isoformat() if due_naive else None,
            }
        )

    # Upcoming events in the next 24h (non-cancelled). Attendees joined in
    # a second pass to avoid a cartesian blow-up on large event rows.
    event_rows = db.execute(
        select(Event.id, Event.title, Event.starts_at)
        .where(Event.family_id == family_id)
        .where(Event.is_cancelled.is_(False))
        .where(Event.starts_at >= now_naive)
        .where(Event.starts_at <= window_end)
        .order_by(Event.starts_at.asc())
        .limit(_SECTION_CAP)
    ).all()
    event_ids = [r.id for r in event_rows]
    attendees_by_event: dict[uuid.UUID, list[str]] = {eid: [] for eid in event_ids}
    if event_ids:
        attendee_rows = db.execute(
            select(EventAttendee.event_id, EventAttendee.family_member_id)
            .where(EventAttendee.event_id.in_(event_ids))
        ).all()
        for ar in attendee_rows:
            attendees_by_event.setdefault(ar.event_id, []).append(
                str(ar.family_member_id)
            )
    upcoming_events_24h = []
    for r in event_rows:
        starts_naive = _strip_tz(r.starts_at)
        upcoming_events_24h.append(
            {
                "id": str(r.id),
                "title": r.title,
                "start_at_utc": starts_naive.isoformat() if starts_naive else None,
                "attendees": attendees_by_event.get(r.id, []),
            }
        )

    # Recent missed routine instances (last 3 days, not completed,
    # past their due_at). task_instances has no 'status' column in
    # Scout's schema; "missed" is derived from is_completed=false AND
    # override_completed IS NOT True AND due_at < now (same semantics
    # as scan_missed_routines in nudges_service.py).
    missed_rows = db.execute(
        select(
            TaskInstance.id,
            TaskInstance.due_at,
            TaskInstance.instance_date,
            Routine.name.label("routine_name"),
        )
        .join(Routine, Routine.id == TaskInstance.routine_id)
        .where(TaskInstance.family_id == family_id)
        .where(TaskInstance.routine_id.is_not(None))
        .where(TaskInstance.is_completed.is_(False))
        .where(TaskInstance.due_at < now_naive)
        .where(TaskInstance.due_at >= missed_cutoff)
        .order_by(TaskInstance.due_at.desc())
        .limit(_SECTION_CAP)
    ).all()
    recent_missed_routines_3d = []
    for r in missed_rows:
        due_naive = _strip_tz(r.due_at)
        recent_missed_routines_3d.append(
            {
                "id": str(r.id),
                "routine_name": r.routine_name,
                "scheduled_for": due_naive.isoformat() if due_naive else None,
            }
        )

    # Active routines (just names + cadence so AI knows what exists).
    routine_rows = db.execute(
        select(Routine.name, Routine.recurrence)
        .where(Routine.family_id == family_id)
        .where(Routine.is_active.is_(True))
        .order_by(Routine.name.asc())
        .limit(_SECTION_CAP)
    ).all()
    active_routines = [
        {"name": r.name, "cadence": r.recurrence} for r in routine_rows
    ]

    digest = {
        "family_id": str(family_id),
        "now_utc": now_naive.isoformat(),
        "members": members,
        "overdue_tasks": overdue_tasks,
        "upcoming_tasks_24h": upcoming_tasks_24h,
        "upcoming_events_24h": upcoming_events_24h,
        "recent_missed_routines_3d": recent_missed_routines_3d,
        "active_routines": active_routines,
    }

    logger.debug(
        "build_family_state_digest family_id=%s "
        "members=%s overdue=%s upcoming_tasks=%s events=%s missed=%s routines=%s",
        family_id,
        len(members),
        len(overdue_tasks),
        len(upcoming_tasks_24h),
        len(upcoming_events_24h),
        len(recent_missed_routines_3d),
        len(active_routines),
    )

    return digest


def _digest_has_actionable_items(digest: dict[str, Any]) -> bool:
    """Does the digest contain anything worth asking the AI about?

    Members and active_routines alone are NOT actionable; they are
    reference data. Only time-bound sections trigger a discovery call.
    """
    return any(
        digest.get(section)
        for section in (
            "overdue_tasks",
            "upcoming_tasks_24h",
            "upcoming_events_24h",
            "recent_missed_routines_3d",
        )
    )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def _convert_proposal(dp: DiscoveryProposal) -> NudgeProposal:
    """Map a DiscoveryProposal (AI output) to a NudgeProposal.

    Key decisions baked in here:

    - ``trigger_kind`` is always ``'ai_suggested'``. Downstream
      compose_body checks this to skip re-composition (the AI already
      produced final copy).
    - ``trigger_entity_kind``: if the AI pointed at a concrete entity
      (personal_task / event / task_instance) we preserve that string.
      When the AI said 'general' we remap to 'ai_discovery' so the
      dispatch pipeline can distinguish 'AI saw a task' vs 'AI had
      a general suggestion'. DiscoveryProposal's Literal values
      describe the UPSTREAM entity; NudgeProposal's trigger_entity_kind
      describes the DISPATCH kind. Distinct concepts that happen to
      share a field name.
    - ``context`` carries the AI-composed body verbatim plus a
      ``ai_generated: True`` flag so Phase 3's compose_body can bail
      out early and use dp.body as-is.
    """
    if dp.trigger_entity_kind == "general":
        trigger_entity_kind = "ai_discovery"
    else:
        trigger_entity_kind = dp.trigger_entity_kind

    return NudgeProposal(
        family_member_id=dp.member_id,
        trigger_kind="ai_suggested",
        trigger_entity_kind=trigger_entity_kind,
        trigger_entity_id=dp.trigger_entity_id,
        scheduled_for=dp.scheduled_for,
        severity=dp.severity,
        context={
            "body": dp.body,
            "ai_generated": True,
        },
    )


def propose_nudges(
    db: Session,
    family_id: uuid.UUID,
    now_utc: datetime,
) -> list[NudgeProposal]:
    """Run one AI discovery cycle for a family.

    Short-circuits (returns []) on any of:
      - throttled (< 1h since last call for this family)
      - weekly AI soft cap reached
      - digest has zero actionable items
      - orchestrator returns no proposals / all invalid

    On a successful AI call, marks the family as having used its hour
    BEFORE returning, whether or not any proposals came back. Rationale:
    the expensive thing is the AI round-trip; the in-memory marker
    should track "did we pay the cost" not "did we get useful output".
    """
    if _is_throttled(family_id, now_utc):
        logger.debug(
            "propose_nudges throttled family_id=%s (within 1h of last run)",
            family_id,
        )
        return []

    # Weekly soft-cap gate. Same call shape as compose_body in
    # nudges_service.py. Failure of the usage report itself is logged
    # but does not hard-block; a degraded cost observer should not kill
    # the discovery feature outright.
    try:
        from app.ai.pricing import build_usage_report
        report = build_usage_report(
            db=db,
            family_id=family_id,
            days=7,
            soft_cap_usd=settings.ai_weekly_soft_cap_usd,
        )
        if report.get("cap_warning"):
            logger.info(
                "propose_nudges skipped family_id=%s reason=soft_cap",
                family_id,
            )
            return []
    except Exception as exc:
        logger.warning(
            "propose_nudges soft_cap_check_failed family_id=%s err=%s",
            family_id,
            exc,
        )

    digest = build_family_state_digest(db, family_id, now_utc)
    if not _digest_has_actionable_items(digest):
        logger.debug(
            "propose_nudges skipped family_id=%s reason=empty_digest",
            family_id,
        )
        return []

    try:
        discovery_proposals = orchestrator.propose_nudges_from_digest(
            family_id=family_id,
            digest=digest,
            now_utc=now_utc,
        )
    except Exception as exc:
        # Orchestrator already swallows most provider errors and returns
        # []. This belt-and-suspenders except preserves that contract
        # if future edits regress it: discovery must never raise out of
        # this function.
        logger.warning(
            "propose_nudges orchestrator_failed family_id=%s err=%s",
            family_id,
            exc,
        )
        return []

    # Mark the run regardless of proposal count. We paid for the AI
    # call; the hour budget is spent.
    _mark_discovery_ran(family_id, now_utc)

    if not discovery_proposals:
        logger.info(
            "propose_nudges family_id=%s emitted=0 (AI returned nothing)",
            family_id,
        )
        return []

    converted = [_convert_proposal(dp) for dp in discovery_proposals]
    logger.info(
        "propose_nudges family_id=%s emitted=%s",
        family_id,
        len(converted),
    )
    return converted


# ---------------------------------------------------------------------------
# Scheduler tick entry point
# ---------------------------------------------------------------------------


def nudge_ai_discovery_tick(db: Session, now_utc: datetime) -> int:
    """Scheduler tick entry point for Phase 5 AI-driven discovery.

    Iterates all families in the system. For each family:
      - Calls propose_nudges(db, family.id, now_utc) which self-throttles
        to one AI call per hour per family.
      - Feeds returned proposals through the shared dispatch pipeline
        (apply_proactivity -> batch_proposals -> dispatch_with_items)
        so quiet hours, batching, and dedupe all apply consistently.

    Returns total count of new parent dispatches across all families.

    Exceptions from a single family are logged at WARN and the tick
    moves on to the next family; one bad family does not poison the
    whole cycle. The Family model has no is_active column (only
    FamilyMember does), so every row is considered in scope.
    """
    families = list(db.scalars(select(Family)).all())
    total_dispatches = 0
    families_processed = 0

    for fam in families:
        families_processed += 1
        try:
            proposals = propose_nudges(db, fam.id, now_utc)
            if not proposals:
                logger.debug(
                    "nudge_ai_discovery_tick family_id=%s proposals=0",
                    fam.id,
                )
                continue

            # resolve_occurrence_fields reads context['occurrence_at_utc']
            # as the source timestamp for dedupe_key generation. Built-in
            # scanners stamp this in scan_*; for AI-suggested proposals
            # the discovery service stamps it here from scheduled_for
            # (the AI's intended delivery time) so the existing dispatch
            # pipeline can consume these proposals unchanged.
            for p in proposals:
                if "occurrence_at_utc" not in p.context:
                    p.context["occurrence_at_utc"] = p.scheduled_for

            gated = nudges_service.apply_proactivity(db, proposals, now_utc)
            bundles = nudges_service.batch_proposals(gated)
            dispatched = nudges_service.dispatch_with_items(
                db, bundles, now_utc
            )
            total_dispatches += dispatched
        except Exception as exc:
            # Isolate per-family failures. One bad family must not
            # stall the cycle. Mirrors the per-job rollback boundaries
            # in scheduler._tick.
            logger.warning(
                "nudge_ai_discovery_tick family_failed family_id=%s err=%s",
                fam.id,
                exc,
            )
            continue

    logger.info(
        "nudge_ai_discovery_tick families=%s dispatches=%s",
        families_processed,
        total_dispatches,
    )
    return total_dispatches

"""Session 2 block 2 — canonical household generation + Daily Win recompute.

This service is what makes the canonical scout.* household tables
actually do work. Block 1 stood up the schema; this module:

  1. ``generate_task_occurrences_for_date(family_id, on_date)``
     materializes one ``scout.task_occurrences`` row per active
     routine_template (matching the recurrence) and per active
     task_template (after evaluating its assignment rule).
  2. ``resolve_assignment(rule_type, rule_params, on_date)``
     evaluates the four assignment rule types from migration 022:
     ``fixed``, ``day_parity``, ``week_rotation``,
     ``dog_walk_assistant`` (and ``custom``, which is a no-op
     placeholder for a per-family extension hook).
  3. ``recompute_daily_win(family_id, family_member_id, on_date)``
     reads the day's required occurrences for a member, counts
     completions, writes/updates ``scout.daily_win_results``, and
     returns ``(earned: bool, changed: bool)``.

Everything is schema-qualified. The service is pure-Python over a
SQLAlchemy session; route handlers and tests can drive it
directly without touching the routes.

The service is family-scoped on every call so it can never
accidentally cross tenant boundaries.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Iterable

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger("scout.canonical.household")


# ---------------------------------------------------------------------------
# Assignment rule evaluation
# ---------------------------------------------------------------------------


@dataclass
class AssignmentResolution:
    """Result of evaluating one task_assignment_rule. ``primary`` is
    the family_member who owns the occurrence; ``assistant`` is set
    only for rules that produce an assistant alongside the owner
    (currently dog_walk_assistant + week_rotation)."""

    primary: uuid.UUID | None
    assistant: uuid.UUID | None = None


def resolve_assignment(
    rule_type: str,
    rule_params: dict,
    on_date: date,
) -> AssignmentResolution:
    """Evaluate one task_assignment_rule against ``on_date``.

    Returns an AssignmentResolution with ``primary`` always set
    when the rule is well-formed. Unknown rule_type or malformed
    params return ``primary=None`` so the caller can mark the
    occurrence as unassigned rather than crashing.
    """
    try:
        if rule_type == "fixed":
            return AssignmentResolution(
                primary=_uuid_or_none(rule_params.get("family_member_id"))
            )
        if rule_type == "day_parity":
            parity = on_date.day % 2
            key = "odd" if parity == 1 else "even"
            return AssignmentResolution(
                primary=_uuid_or_none(rule_params.get(key))
            )
        if rule_type == "dog_walk_assistant":
            parity = on_date.day % 2
            assistant_key = "odd" if parity == 1 else "even"
            return AssignmentResolution(
                primary=_uuid_or_none(rule_params.get("lead")),
                assistant=_uuid_or_none(rule_params.get(assistant_key)),
            )
        if rule_type == "week_rotation":
            anchor_str = rule_params.get("anchor_date")
            if not anchor_str:
                return AssignmentResolution(primary=None)
            anchor = date.fromisoformat(anchor_str)
            period_weeks = int(rule_params.get("period_weeks", 8))
            weeks_since = (on_date - anchor).days // 7
            period_index = weeks_since // period_weeks
            owner = _uuid_or_none(rule_params.get("owner"))
            assistant = _uuid_or_none(rule_params.get("assistant"))
            if period_index % 2 == 0:
                return AssignmentResolution(primary=owner, assistant=assistant)
            return AssignmentResolution(primary=assistant, assistant=owner)
        if rule_type == "custom":
            # Reserved for per-family extensions. The rule_params
            # shape is opaque; first-pass returns unassigned.
            return AssignmentResolution(primary=None)
    except Exception:
        logger.exception(
            "rule_resolution_failed type=%s params=%s", rule_type, rule_params
        )
    return AssignmentResolution(primary=None)


def _uuid_or_none(v) -> uuid.UUID | None:
    if v is None:
        return None
    try:
        if isinstance(v, uuid.UUID):
            return v
        return uuid.UUID(str(v))
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Recurrence matching
# ---------------------------------------------------------------------------


def _recurrence_applies(recurrence: str, on_date: date) -> bool:
    """Charter recurrence vocabulary: daily / weekdays / weekends /
    weekly / one_off. ``weekly`` fires on Saturdays for the Roberts
    family (Power 60 + Backyard Poop Patrol)."""
    if recurrence == "daily":
        return True
    if recurrence == "weekdays":
        return on_date.weekday() < 5
    if recurrence == "weekends":
        return on_date.weekday() >= 5
    if recurrence == "weekly":
        # Default weekly anchor: Saturday. Future templates can
        # override via task_assignment_rule params.
        return on_date.weekday() == 5
    if recurrence == "one_off":
        return False
    return False


def _due_at(
    on_date: date,
    weekday_due: time | None,
    weekend_due: time | None,
    fallback: time | None = None,
) -> datetime:
    """Resolve the due-at timestamp for an occurrence. Falls back to
    ``20:00`` if nothing is set so the occurrence is never NULL."""
    is_weekend = on_date.weekday() >= 5
    chosen = weekend_due if is_weekend else weekday_due
    if chosen is None:
        chosen = fallback or time(20, 0)
    return datetime.combine(on_date, chosen)


# ---------------------------------------------------------------------------
# Occurrence generation
# ---------------------------------------------------------------------------


@dataclass
class GenerationResult:
    """Summary returned by generate_task_occurrences_for_date so
    tests and the route can report progress."""

    family_id: uuid.UUID
    on_date: date
    routines_generated: int = 0
    tasks_generated: int = 0
    skipped_unassigned: int = 0


def generate_task_occurrences_for_date(
    db: Session,
    *,
    family_id: uuid.UUID,
    on_date: date,
) -> GenerationResult:
    """Materialize the day's task_occurrences from active routine
    templates + task templates.

    Idempotent: re-running for the same date does NOT create
    duplicates. The generator looks up the existing occurrence by
    (template_id OR routine_id) + occurrence_date and skips if
    present. Status updates and completions are not touched.

    Returns a GenerationResult summarizing what was created.
    """
    result = GenerationResult(family_id=family_id, on_date=on_date)

    # ---- Routines -----------------------------------------------------
    routines = db.execute(
        text(
            """
            SELECT id, recurrence, due_time_weekday, due_time_weekend,
                   owner_family_member_id
            FROM scout.routine_templates
            WHERE family_id = :fid
            """
        ),
        {"fid": family_id},
    ).all()

    for r in routines:
        if not _recurrence_applies(r.recurrence, on_date):
            continue
        existing = db.execute(
            text(
                """
                SELECT id FROM scout.task_occurrences
                WHERE routine_template_id = :rid AND occurrence_date = :d
                """
            ),
            {"rid": r.id, "d": on_date},
        ).first()
        if existing:
            continue

        due_at = _due_at(on_date, r.due_time_weekday, r.due_time_weekend)
        db.execute(
            text(
                """
                INSERT INTO scout.task_occurrences
                    (id, family_id, routine_template_id, assigned_to,
                     occurrence_date, due_at, status, generated_at)
                VALUES
                    (:id, :fid, :rid, :assignee, :d, :due, 'open',
                     clock_timestamp())
                """
            ),
            {
                "id": uuid.uuid4(),
                "fid": family_id,
                "rid": r.id,
                "assignee": r.owner_family_member_id,
                "d": on_date,
                "due": due_at,
            },
        )
        result.routines_generated += 1

    # ---- Standalone task_templates ------------------------------------
    templates = db.execute(
        text(
            """
            SELECT tt.id, tt.recurrence, tt.due_time, tt.is_active,
                   tar.rule_type, tar.rule_params
            FROM scout.task_templates tt
            LEFT JOIN scout.task_assignment_rules tar
                ON tar.task_template_id = tt.id
            WHERE tt.family_id = :fid AND tt.is_active = TRUE
            ORDER BY tt.id, tar.priority DESC
            """
        ),
        {"fid": family_id},
    ).all()

    seen_template_ids: set[uuid.UUID] = set()
    for t in templates:
        # Take the first (highest-priority) assignment rule per
        # template. The ORDER BY above guarantees that ordering.
        if t.id in seen_template_ids:
            continue
        seen_template_ids.add(t.id)

        if not _recurrence_applies(t.recurrence, on_date):
            continue

        existing = db.execute(
            text(
                """
                SELECT id FROM scout.task_occurrences
                WHERE task_template_id = :tid AND occurrence_date = :d
                """
            ),
            {"tid": t.id, "d": on_date},
        ).first()
        if existing:
            continue

        resolution = AssignmentResolution(primary=None)
        if t.rule_type:
            resolution = resolve_assignment(
                t.rule_type, dict(t.rule_params or {}), on_date
            )

        if resolution.primary is None and t.rule_type:
            result.skipped_unassigned += 1
            continue

        due_at = _due_at(on_date, t.due_time, t.due_time)
        db.execute(
            text(
                """
                INSERT INTO scout.task_occurrences
                    (id, family_id, task_template_id, assigned_to,
                     occurrence_date, due_at, status, generated_at)
                VALUES
                    (:id, :fid, :tid, :assignee, :d, :due, 'open',
                     clock_timestamp())
                """
            ),
            {
                "id": uuid.uuid4(),
                "fid": family_id,
                "tid": t.id,
                "assignee": resolution.primary,
                "d": on_date,
                "due": due_at,
            },
        )
        result.tasks_generated += 1

    db.flush()
    return result


# ---------------------------------------------------------------------------
# Daily Win recompute
# ---------------------------------------------------------------------------


@dataclass
class DailyWinRecomputeResult:
    family_member_id: uuid.UUID
    on_date: date
    earned: bool
    changed: bool
    total_required: int
    total_complete: int
    missing: list[dict]


def recompute_daily_win(
    db: Session,
    *,
    family_id: uuid.UUID,
    family_member_id: uuid.UUID,
    on_date: date,
) -> DailyWinRecomputeResult:
    """Recompute the Daily Win row for one member on one date.

    A Daily Win is earned when every "required" occurrence for the
    member on that date has at least one completion row. Required
    occurrences are everything assigned to the member with status
    in ('open', 'complete', 'late'). 'skipped' and 'blocked' are
    excluded — those are operationally out-of-scope per the
    family file.

    Writes/updates one row in scout.daily_win_results and returns
    a structured result.
    """
    rows = db.execute(
        text(
            """
            SELECT
                tocc.id AS occ_id,
                tocc.status,
                COALESCE(tt.label, rt.label) AS label,
                tt.template_key,
                rt.routine_key,
                EXISTS (
                    SELECT 1 FROM scout.task_completions tc
                    WHERE tc.task_occurrence_id = tocc.id
                ) AS is_complete
            FROM scout.task_occurrences tocc
            LEFT JOIN scout.task_templates tt ON tt.id = tocc.task_template_id
            LEFT JOIN scout.routine_templates rt ON rt.id = tocc.routine_template_id
            WHERE tocc.family_id = :fid
              AND tocc.assigned_to = :mid
              AND tocc.occurrence_date = :d
              AND tocc.status IN ('open', 'complete', 'late')
            """
        ),
        {"fid": family_id, "mid": family_member_id, "d": on_date},
    ).all()

    total_required = len(rows)
    total_complete = sum(1 for r in rows if r.is_complete)
    earned = total_required > 0 and total_complete >= total_required

    missing = [
        {
            "label": r.label,
            "template_key": r.template_key,
            "routine_key": r.routine_key,
        }
        for r in rows
        if not r.is_complete
    ]

    # Upsert daily_win_results. Track whether the result actually
    # changed compared to any prior row so the route can return a
    # truthful daily_win_recomputed flag.
    prior = db.execute(
        text(
            """
            SELECT earned, total_required, total_complete
            FROM scout.daily_win_results
            WHERE family_member_id = :mid AND for_date = :d
            """
        ),
        {"mid": family_member_id, "d": on_date},
    ).first()

    changed = (
        prior is None
        or prior.earned != earned
        or prior.total_required != total_required
        or prior.total_complete != total_complete
    )

    if prior is None:
        db.execute(
            text(
                """
                INSERT INTO scout.daily_win_results
                    (family_id, family_member_id, for_date, earned,
                     total_required, total_complete, missing_items,
                     computed_at)
                VALUES
                    (:fid, :mid, :d, :earned, :req, :done,
                     :missing, clock_timestamp())
                """
            ),
            {
                "fid": family_id,
                "mid": family_member_id,
                "d": on_date,
                "earned": earned,
                "req": total_required,
                "done": total_complete,
                "missing": _to_jsonb(missing),
            },
        )
    else:
        db.execute(
            text(
                """
                UPDATE scout.daily_win_results
                SET earned = :earned,
                    total_required = :req,
                    total_complete = :done,
                    missing_items = :missing,
                    computed_at = clock_timestamp()
                WHERE family_member_id = :mid AND for_date = :d
                """
            ),
            {
                "mid": family_member_id,
                "d": on_date,
                "earned": earned,
                "req": total_required,
                "done": total_complete,
                "missing": _to_jsonb(missing),
            },
        )

    db.flush()
    return DailyWinRecomputeResult(
        family_member_id=family_member_id,
        on_date=on_date,
        earned=earned,
        changed=changed,
        total_required=total_required,
        total_complete=total_complete,
        missing=missing,
    )


def _to_jsonb(value) -> str:
    """psycopg2 wants a JSON string for jsonb-typed bind params."""
    import json

    return json.dumps(value)

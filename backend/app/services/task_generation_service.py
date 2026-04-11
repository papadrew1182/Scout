"""Generates task_instances from active routines and chore_templates for a given date.

Idempotent: uses ON CONFLICT DO NOTHING via unique constraints.
Creates step_completion rows only for routine-sourced task_instances.
"""

import uuid
from datetime import date, datetime, time

import pytz
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.life_management import (
    ChoreTemplate,
    Routine,
    RoutineStep,
    TaskInstance,
    TaskInstanceStepCompletion,
)
from app.services.chore_service import resolve_assignees
from app.services.tenant_guard import require_family


def _make_due_at(instance_date: date, due_time: time, timezone_str: str) -> datetime:
    tz = pytz.timezone(timezone_str)
    naive = datetime.combine(instance_date, due_time)
    return tz.localize(naive)


def _is_applicable_day(recurrence: str, target_date: date) -> bool:
    weekday = target_date.isoweekday()  # 1=Mon, 7=Sun
    is_weekday = weekday <= 5
    is_weekend = weekday > 5

    if recurrence == "daily":
        return True
    if recurrence == "weekdays":
        return is_weekday
    if recurrence == "weekends":
        return is_weekend
    if recurrence == "weekly":
        return False  # weekly chores need day_of_week from assignment_rule
    return False


def _is_weekly_applicable(template: ChoreTemplate, target_date: date) -> bool:
    if template.recurrence != "weekly":
        return False
    day_name = target_date.strftime("%A").lower()
    rule_day = template.assignment_rule.get("day_of_week", "").lower()
    return day_name == rule_day


def generate_for_date(db: Session, family_id: uuid.UUID, target_date: date) -> list[TaskInstance]:
    """Generate all task_instances for a family on a given date. Returns created instances."""
    family = require_family(db, family_id)
    timezone_str = family.timezone
    created: list[TaskInstance] = []

    # --- Routine-sourced instances ---
    routines = list(
        db.scalars(
            select(Routine)
            .where(Routine.family_id == family_id)
            .where(Routine.is_active.is_(True))
        ).all()
    )

    for routine in routines:
        if not _is_applicable_day(routine.recurrence, target_date):
            continue

        is_weekend = target_date.isoweekday() > 5
        due_time = routine.due_time_weekend if (is_weekend and routine.due_time_weekend) else routine.due_time_weekday
        due_at = _make_due_at(target_date, due_time, timezone_str)

        # Check idempotency
        exists = db.scalars(
            select(TaskInstance)
            .where(TaskInstance.family_member_id == routine.family_member_id)
            .where(TaskInstance.routine_id == routine.id)
            .where(TaskInstance.instance_date == target_date)
        ).first()
        if exists:
            continue

        instance = TaskInstance(
            family_id=family_id,
            family_member_id=routine.family_member_id,
            routine_id=routine.id,
            chore_template_id=None,
            instance_date=target_date,
            due_at=due_at,
        )
        db.add(instance)
        db.flush()  # get instance.id for step completions

        # Create step completion rows for routine-sourced instances
        active_steps = list(
            db.scalars(
                select(RoutineStep)
                .where(RoutineStep.routine_id == routine.id)
                .where(RoutineStep.is_active.is_(True))
                .order_by(RoutineStep.sort_order)
            ).all()
        )
        for step in active_steps:
            step_completion = TaskInstanceStepCompletion(
                task_instance_id=instance.id,
                routine_step_id=step.id,
            )
            db.add(step_completion)

        created.append(instance)

    # --- Chore-sourced instances ---
    chore_templates = list(
        db.scalars(
            select(ChoreTemplate)
            .where(ChoreTemplate.family_id == family_id)
            .where(ChoreTemplate.is_active.is_(True))
        ).all()
    )

    for template in chore_templates:
        if template.recurrence == "weekly":
            if not _is_weekly_applicable(template, target_date):
                continue
        elif not _is_applicable_day(template.recurrence, target_date):
            continue

        assignees = resolve_assignees(template, target_date.day)
        due_at = _make_due_at(target_date, template.due_time, timezone_str)

        for member_id in assignees:
            exists = db.scalars(
                select(TaskInstance)
                .where(TaskInstance.family_member_id == member_id)
                .where(TaskInstance.chore_template_id == template.id)
                .where(TaskInstance.instance_date == target_date)
            ).first()
            if exists:
                continue

            instance = TaskInstance(
                family_id=family_id,
                family_member_id=member_id,
                routine_id=None,
                chore_template_id=template.id,
                instance_date=target_date,
                due_at=due_at,
            )
            db.add(instance)
            created.append(instance)

    db.commit()
    return created

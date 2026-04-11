"""Personal tasks service.

Distinct from task_instances (the child routine/chore execution model).
Personal tasks are one-off, optionally due, optionally event-linked.
"""

import uuid
from datetime import date, datetime, time, timedelta

from fastapi import HTTPException, status as http_status
from sqlalchemy import case, select
from sqlalchemy.orm import Session

from app.models.calendar import Event
from app.models.personal_tasks import PersonalTask
from app.schemas.personal_tasks import PersonalTaskCreate, PersonalTaskUpdate
from app.services.tenant_guard import require_family, require_member_in_family

# priority ranking for ORDER BY
_PRIORITY_RANK = case(
    {"urgent": 4, "high": 3, "medium": 2, "low": 1},
    value=PersonalTask.priority,
    else_=0,
)

_INCOMPLETE_STATUSES = ("pending", "in_progress")


def _validate_status(value: str) -> None:
    if value not in ("pending", "in_progress", "done", "cancelled"):
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status: {value}",
        )


def _validate_priority(value: str) -> None:
    if value not in ("low", "medium", "high", "urgent"):
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid priority: {value}",
        )


def list_personal_tasks(
    db: Session,
    family_id: uuid.UUID,
    assigned_to: uuid.UUID | None = None,
    statuses: list[str] | None = None,
    incomplete_only: bool = False,
    due_before: datetime | None = None,
    due_after: datetime | None = None,
) -> list[PersonalTask]:
    require_family(db, family_id)
    stmt = select(PersonalTask).where(PersonalTask.family_id == family_id)
    if assigned_to:
        stmt = stmt.where(PersonalTask.assigned_to == assigned_to)
    if incomplete_only:
        stmt = stmt.where(PersonalTask.status.in_(_INCOMPLETE_STATUSES))
    elif statuses:
        stmt = stmt.where(PersonalTask.status.in_(statuses))
    if due_before:
        stmt = stmt.where(PersonalTask.due_at <= due_before)
    if due_after:
        stmt = stmt.where(PersonalTask.due_at >= due_after)

    stmt = stmt.order_by(
        _PRIORITY_RANK.desc(),
        PersonalTask.due_at.is_(None),  # NULLS LAST
        PersonalTask.due_at,
        PersonalTask.created_at,
    )
    return list(db.scalars(stmt).all())


def list_top_personal_tasks(
    db: Session,
    family_id: uuid.UUID,
    assigned_to: uuid.UUID,
    limit: int = 5,
) -> list[PersonalTask]:
    """Top N tasks for a family member: incomplete, ordered by priority then due."""
    require_member_in_family(db, family_id, assigned_to)
    stmt = (
        select(PersonalTask)
        .where(PersonalTask.family_id == family_id)
        .where(PersonalTask.assigned_to == assigned_to)
        .where(PersonalTask.status.in_(_INCOMPLETE_STATUSES))
        .order_by(
            _PRIORITY_RANK.desc(),
            PersonalTask.due_at.is_(None),
            PersonalTask.due_at,
            PersonalTask.created_at,
        )
        .limit(limit)
    )
    return list(db.scalars(stmt).all())


def list_due_today(
    db: Session,
    family_id: uuid.UUID,
    assigned_to: uuid.UUID | None = None,
    target_date: date | None = None,
) -> list[PersonalTask]:
    """Personal tasks due on the given date (default today), incomplete only."""
    require_family(db, family_id)
    target = target_date or date.today()
    start = datetime.combine(target, time.min)
    end = datetime.combine(target, time.max)

    stmt = (
        select(PersonalTask)
        .where(PersonalTask.family_id == family_id)
        .where(PersonalTask.status.in_(_INCOMPLETE_STATUSES))
        .where(PersonalTask.due_at >= start)
        .where(PersonalTask.due_at <= end)
    )
    if assigned_to:
        stmt = stmt.where(PersonalTask.assigned_to == assigned_to)
    stmt = stmt.order_by(_PRIORITY_RANK.desc(), PersonalTask.due_at)
    return list(db.scalars(stmt).all())


def get_personal_task(
    db: Session, family_id: uuid.UUID, task_id: uuid.UUID
) -> PersonalTask:
    task = db.get(PersonalTask, task_id)
    if not task or task.family_id != family_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Personal task not found",
        )
    return task


def create_personal_task(
    db: Session, family_id: uuid.UUID, payload: PersonalTaskCreate
) -> PersonalTask:
    require_family(db, family_id)
    require_member_in_family(db, family_id, payload.assigned_to)
    if payload.created_by:
        require_member_in_family(db, family_id, payload.created_by)
    _validate_status(payload.status)
    _validate_priority(payload.priority)

    if payload.event_id:
        event = db.get(Event, payload.event_id)
        if not event or event.family_id != family_id:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="event_id does not belong to this family",
            )

    completed_at = (
        datetime.now().astimezone() if payload.status == "done" else None
    )

    task = PersonalTask(
        family_id=family_id,
        assigned_to=payload.assigned_to,
        created_by=payload.created_by,
        title=payload.title,
        description=payload.description,
        notes=payload.notes,
        status=payload.status,
        priority=payload.priority,
        due_at=payload.due_at,
        completed_at=completed_at,
        event_id=payload.event_id,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def update_personal_task(
    db: Session,
    family_id: uuid.UUID,
    task_id: uuid.UUID,
    payload: PersonalTaskUpdate,
) -> PersonalTask:
    task = get_personal_task(db, family_id, task_id)
    data = payload.model_dump(exclude_unset=True)

    if "status" in data:
        _validate_status(data["status"])
    if "priority" in data:
        _validate_priority(data["priority"])
    if "assigned_to" in data and data["assigned_to"]:
        require_member_in_family(db, family_id, data["assigned_to"])
    if "event_id" in data and data["event_id"] is not None:
        event = db.get(Event, data["event_id"])
        if not event or event.family_id != family_id:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="event_id does not belong to this family",
            )

    # Drive completed_at from status to satisfy chk_personal_tasks_completed_consistency
    new_status = data.get("status", task.status)
    if new_status == "done" and task.status != "done":
        data["completed_at"] = datetime.now().astimezone()
    elif new_status != "done" and task.status == "done":
        data["completed_at"] = None

    for key, value in data.items():
        setattr(task, key, value)
    db.commit()
    db.refresh(task)
    return task


def delete_personal_task(
    db: Session, family_id: uuid.UUID, task_id: uuid.UUID
) -> None:
    task = get_personal_task(db, family_id, task_id)
    db.delete(task)
    db.commit()


def complete_personal_task(
    db: Session, family_id: uuid.UUID, task_id: uuid.UUID
) -> PersonalTask:
    task = get_personal_task(db, family_id, task_id)
    if task.status == "done":
        return task
    task.status = "done"
    task.completed_at = datetime.now().astimezone()
    db.commit()
    db.refresh(task)
    return task

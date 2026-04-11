"""Computes and materializes daily_wins from task_instances.

A Daily Win = all task_instances for a member on a date are effectively completed by deadline.
Effective completion uses override_completed when set, otherwise is_completed.
"""

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.life_management import DailyWin, TaskInstance
from app.services.tenant_guard import get_active_children, require_family


def _is_effectively_completed(instance: TaskInstance) -> bool:
    if instance.override_completed is not None:
        return instance.override_completed
    return instance.is_completed


def _is_completed_by_deadline(instance: TaskInstance) -> bool:
    if instance.override_completed is not None:
        return instance.override_completed
    return instance.is_completed and instance.completed_at is not None and instance.completed_at <= instance.due_at


def compute_daily_win(db: Session, family_id: uuid.UUID, member_id: uuid.UUID, win_date: date) -> DailyWin:
    """Compute and upsert a daily_win row for one member on one date."""
    instances = list(
        db.scalars(
            select(TaskInstance)
            .where(TaskInstance.family_id == family_id)
            .where(TaskInstance.family_member_id == member_id)
            .where(TaskInstance.instance_date == win_date)
        ).all()
    )

    task_count = len(instances)
    completed_count = sum(1 for i in instances if _is_effectively_completed(i))
    is_win = task_count > 0 and all(_is_completed_by_deadline(i) for i in instances)

    existing = db.scalars(
        select(DailyWin)
        .where(DailyWin.family_member_id == member_id)
        .where(DailyWin.win_date == win_date)
    ).first()

    if existing:
        existing.is_win = is_win
        existing.task_count = task_count
        existing.completed_count = completed_count
        db.commit()
        db.refresh(existing)
        return existing

    daily_win = DailyWin(
        family_id=family_id,
        family_member_id=member_id,
        win_date=win_date,
        is_win=is_win,
        task_count=task_count,
        completed_count=completed_count,
    )
    db.add(daily_win)
    db.commit()
    db.refresh(daily_win)
    return daily_win


def compute_for_family_date(db: Session, family_id: uuid.UUID, win_date: date) -> list[DailyWin]:
    """Compute daily_wins for all active children in a family on a date."""
    # Weekday check: isodow 1-5
    if win_date.isoweekday() > 5:
        return []

    require_family(db, family_id)
    children = get_active_children(db, family_id)
    return [compute_daily_win(db, family_id, child.id, win_date) for child in children]


def list_daily_wins(
    db: Session,
    family_id: uuid.UUID,
    member_id: uuid.UUID | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[DailyWin]:
    require_family(db, family_id)
    stmt = select(DailyWin).where(DailyWin.family_id == family_id)
    if member_id:
        stmt = stmt.where(DailyWin.family_member_id == member_id)
    if start_date:
        stmt = stmt.where(DailyWin.win_date >= start_date)
    if end_date:
        stmt = stmt.where(DailyWin.win_date <= end_date)
    stmt = stmt.order_by(DailyWin.win_date)
    return list(db.scalars(stmt).all())

"""Task instance operations: completion marking, step completion, parent override.

Does NOT contain daily win logic.
"""

import uuid
from datetime import date, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.life_management import TaskInstance, TaskInstanceStepCompletion
from app.schemas.life_management import TaskInstanceComplete, TaskInstanceOverride, StepCompletionUpdate
from app.services.tenant_guard import require_family, require_member_in_family


def list_task_instances(
    db: Session,
    family_id: uuid.UUID,
    instance_date: date | None = None,
    member_id: uuid.UUID | None = None,
) -> list[TaskInstance]:
    require_family(db, family_id)
    stmt = select(TaskInstance).where(TaskInstance.family_id == family_id)
    if instance_date:
        stmt = stmt.where(TaskInstance.instance_date == instance_date)
    if member_id:
        stmt = stmt.where(TaskInstance.family_member_id == member_id)
    stmt = stmt.order_by(TaskInstance.due_at)
    return list(db.scalars(stmt).all())


def get_task_instance(db: Session, family_id: uuid.UUID, instance_id: uuid.UUID) -> TaskInstance:
    instance = db.get(TaskInstance, instance_id)
    if not instance or instance.family_id != family_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task instance not found")
    return instance


def mark_completed(db: Session, family_id: uuid.UUID, instance_id: uuid.UUID, payload: TaskInstanceComplete) -> TaskInstance:
    instance = get_task_instance(db, family_id, instance_id)
    instance.is_completed = True
    instance.completed_at = payload.completed_at or datetime.now().astimezone()
    db.commit()
    db.refresh(instance)
    return instance


def apply_override(db: Session, family_id: uuid.UUID, instance_id: uuid.UUID, payload: TaskInstanceOverride) -> TaskInstance:
    instance = get_task_instance(db, family_id, instance_id)
    require_member_in_family(db, family_id, payload.override_by)
    instance.override_completed = payload.override_completed
    instance.override_by = payload.override_by
    instance.override_note = payload.override_note
    db.commit()
    db.refresh(instance)
    return instance


def list_step_completions(db: Session, family_id: uuid.UUID, instance_id: uuid.UUID) -> list[TaskInstanceStepCompletion]:
    instance = get_task_instance(db, family_id, instance_id)
    stmt = (
        select(TaskInstanceStepCompletion)
        .where(TaskInstanceStepCompletion.task_instance_id == instance.id)
    )
    return list(db.scalars(stmt).all())


def update_step_completion(
    db: Session,
    family_id: uuid.UUID,
    instance_id: uuid.UUID,
    step_completion_id: uuid.UUID,
    payload: StepCompletionUpdate,
) -> TaskInstanceStepCompletion:
    instance = get_task_instance(db, family_id, instance_id)
    completion = db.get(TaskInstanceStepCompletion, step_completion_id)
    if not completion or completion.task_instance_id != instance_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Step completion not found")
    completion.is_completed = payload.is_completed
    completion.completed_at = payload.completed_at

    # Rollup: parent task_instance reflects whether ALL steps are complete
    all_steps = list(
        db.scalars(
            select(TaskInstanceStepCompletion)
            .where(TaskInstanceStepCompletion.task_instance_id == instance_id)
        ).all()
    )
    all_done = all(s.is_completed for s in all_steps)
    instance.is_completed = all_done
    instance.completed_at = datetime.now().astimezone() if all_done else None

    db.commit()
    db.refresh(completion)
    return completion

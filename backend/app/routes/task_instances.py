import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth import Actor, get_current_actor
from app.database import get_db
from app.models.life_management import TaskInstance
from app.models.action_items import ParentActionItem
from app.schemas.life_management import (
    StepCompletionRead,
    StepCompletionUpdate,
    TaskInstanceComplete,
    TaskInstanceOverride,
    TaskInstanceRead,
)
from app.services import task_generation_service, task_instance_service

router = APIRouter(prefix="/families/{family_id}/task-instances", tags=["task-instances"])


@router.get("", response_model=list[TaskInstanceRead])
def list_task_instances(
    family_id: uuid.UUID,
    instance_date: date | None = Query(None),
    member_id: uuid.UUID | None = Query(None),
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_family(family_id)
    return task_instance_service.list_task_instances(db, family_id, instance_date, member_id)


@router.post("/generate", response_model=list[TaskInstanceRead], status_code=201)
def generate_tasks(family_id: uuid.UUID, target_date: date = Query(...), actor: Actor = Depends(get_current_actor), db: Session = Depends(get_db)):
    actor.require_family(family_id)
    actor.require_permission("chores.manage_config")
    return task_generation_service.generate_for_date(db, family_id, target_date)


@router.get("/{instance_id}", response_model=TaskInstanceRead)
def get_task_instance(family_id: uuid.UUID, instance_id: uuid.UUID, actor: Actor = Depends(get_current_actor), db: Session = Depends(get_db)):
    actor.require_family(family_id)
    return task_instance_service.get_task_instance(db, family_id, instance_id)


@router.post("/{instance_id}/complete", response_model=TaskInstanceRead)
def mark_completed(family_id: uuid.UUID, instance_id: uuid.UUID, payload: TaskInstanceComplete, actor: Actor = Depends(get_current_actor), db: Session = Depends(get_db)):
    actor.require_family(family_id)
    actor.require_permission("household.complete_own_task")
    return task_instance_service.mark_completed(db, family_id, instance_id, payload)


@router.post("/{instance_id}/override", response_model=TaskInstanceRead)
def apply_override(family_id: uuid.UUID, instance_id: uuid.UUID, payload: TaskInstanceOverride, actor: Actor = Depends(get_current_actor), db: Session = Depends(get_db)):
    actor.require_family(family_id)
    actor.require_permission("household.complete_any_task")
    return task_instance_service.apply_override(db, family_id, instance_id, payload)


@router.get("/{instance_id}/steps", response_model=list[StepCompletionRead])
def list_step_completions(family_id: uuid.UUID, instance_id: uuid.UUID, actor: Actor = Depends(get_current_actor), db: Session = Depends(get_db)):
    actor.require_family(family_id)
    return task_instance_service.list_step_completions(db, family_id, instance_id)


@router.patch("/{instance_id}/steps/{step_completion_id}", response_model=StepCompletionRead)
def update_step_completion(
    family_id: uuid.UUID,
    instance_id: uuid.UUID,
    step_completion_id: uuid.UUID,
    payload: StepCompletionUpdate,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_family(family_id)
    actor.require_permission("household.complete_own_task")
    return task_instance_service.update_step_completion(db, family_id, instance_id, step_completion_id, payload)


@router.post("/{instance_id}/dispute-scope", response_model=TaskInstanceRead)
def dispute_scope(
    family_id: uuid.UUID,
    instance_id: uuid.UUID,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_family(family_id)
    actor.require_permission("chore.complete_self")
    task = db.get(TaskInstance, instance_id)
    if not task or task.family_id != family_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task instance not found")
    if task.scope_dispute_opened_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Dispute already opened")
    task.scope_dispute_opened_at = datetime.now(timezone.utc)
    action_item = ParentActionItem(
        family_id=family_id,
        created_by_member_id=actor.member_id,
        action_type="chore_scope_dispute",
        title="Scope dispute on chore task",
        detail=f"Member disputed scope for task instance {instance_id}",
        entity_type="task_instance",
        entity_id=instance_id,
        status="pending",
    )
    db.add(action_item)
    db.commit()
    db.refresh(task)
    return task

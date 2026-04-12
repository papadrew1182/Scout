import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth import Actor, get_current_actor
from app.database import get_db
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
    return task_generation_service.generate_for_date(db, family_id, target_date)


@router.get("/{instance_id}", response_model=TaskInstanceRead)
def get_task_instance(family_id: uuid.UUID, instance_id: uuid.UUID, actor: Actor = Depends(get_current_actor), db: Session = Depends(get_db)):
    actor.require_family(family_id)
    return task_instance_service.get_task_instance(db, family_id, instance_id)


@router.post("/{instance_id}/complete", response_model=TaskInstanceRead)
def mark_completed(family_id: uuid.UUID, instance_id: uuid.UUID, payload: TaskInstanceComplete, actor: Actor = Depends(get_current_actor), db: Session = Depends(get_db)):
    actor.require_family(family_id)
    return task_instance_service.mark_completed(db, family_id, instance_id, payload)


@router.post("/{instance_id}/override", response_model=TaskInstanceRead)
def apply_override(family_id: uuid.UUID, instance_id: uuid.UUID, payload: TaskInstanceOverride, actor: Actor = Depends(get_current_actor), db: Session = Depends(get_db)):
    actor.require_family(family_id)
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
    return task_instance_service.update_step_completion(db, family_id, instance_id, step_completion_id, payload)

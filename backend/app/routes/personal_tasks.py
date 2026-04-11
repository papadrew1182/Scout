import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.personal_tasks import (
    PersonalTaskCreate,
    PersonalTaskRead,
    PersonalTaskUpdate,
)
from app.services import personal_tasks_service

router = APIRouter(prefix="/families/{family_id}/personal-tasks", tags=["personal-tasks"])


@router.get("", response_model=list[PersonalTaskRead])
def list_personal_tasks(
    family_id: uuid.UUID,
    assigned_to: uuid.UUID | None = Query(None),
    incomplete_only: bool = Query(False),
    due_before: datetime | None = Query(None),
    due_after: datetime | None = Query(None),
    db: Session = Depends(get_db),
):
    return personal_tasks_service.list_personal_tasks(
        db,
        family_id,
        assigned_to=assigned_to,
        incomplete_only=incomplete_only,
        due_before=due_before,
        due_after=due_after,
    )


@router.get("/top", response_model=list[PersonalTaskRead])
def list_top_personal_tasks(
    family_id: uuid.UUID,
    assigned_to: uuid.UUID = Query(...),
    limit: int = Query(5, ge=1, le=50),
    db: Session = Depends(get_db),
):
    return personal_tasks_service.list_top_personal_tasks(db, family_id, assigned_to, limit)


@router.get("/due-today", response_model=list[PersonalTaskRead])
def list_due_today(
    family_id: uuid.UUID,
    assigned_to: uuid.UUID | None = Query(None),
    target_date: date | None = Query(None),
    db: Session = Depends(get_db),
):
    return personal_tasks_service.list_due_today(db, family_id, assigned_to, target_date)


@router.post("", response_model=PersonalTaskRead, status_code=201)
def create_personal_task(
    family_id: uuid.UUID,
    payload: PersonalTaskCreate,
    db: Session = Depends(get_db),
):
    return personal_tasks_service.create_personal_task(db, family_id, payload)


@router.get("/{task_id}", response_model=PersonalTaskRead)
def get_personal_task(family_id: uuid.UUID, task_id: uuid.UUID, db: Session = Depends(get_db)):
    return personal_tasks_service.get_personal_task(db, family_id, task_id)


@router.patch("/{task_id}", response_model=PersonalTaskRead)
def update_personal_task(
    family_id: uuid.UUID,
    task_id: uuid.UUID,
    payload: PersonalTaskUpdate,
    db: Session = Depends(get_db),
):
    return personal_tasks_service.update_personal_task(db, family_id, task_id, payload)


@router.post("/{task_id}/complete", response_model=PersonalTaskRead)
def complete_personal_task(
    family_id: uuid.UUID, task_id: uuid.UUID, db: Session = Depends(get_db)
):
    return personal_tasks_service.complete_personal_task(db, family_id, task_id)


@router.delete("/{task_id}", status_code=204)
def delete_personal_task(family_id: uuid.UUID, task_id: uuid.UUID, db: Session = Depends(get_db)):
    personal_tasks_service.delete_personal_task(db, family_id, task_id)

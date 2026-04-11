import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.life_management import (
    RoutineCreate,
    RoutineRead,
    RoutineStepCreate,
    RoutineStepRead,
    RoutineWithStepsRead,
)
from app.services import routine_service

router = APIRouter(prefix="/families/{family_id}/routines", tags=["routines"])


@router.get("", response_model=list[RoutineRead])
def list_routines(
    family_id: uuid.UUID,
    member_id: uuid.UUID | None = Query(None),
    db: Session = Depends(get_db),
):
    return routine_service.list_routines(db, family_id, member_id)


@router.post("", response_model=RoutineRead, status_code=201)
def create_routine(family_id: uuid.UUID, payload: RoutineCreate, db: Session = Depends(get_db)):
    return routine_service.create_routine(db, family_id, payload)


@router.get("/{routine_id}", response_model=RoutineWithStepsRead)
def get_routine(family_id: uuid.UUID, routine_id: uuid.UUID, db: Session = Depends(get_db)):
    return routine_service.get_routine(db, family_id, routine_id)


@router.get("/{routine_id}/steps", response_model=list[RoutineStepRead])
def list_steps(family_id: uuid.UUID, routine_id: uuid.UUID, db: Session = Depends(get_db)):
    return routine_service.list_steps(db, family_id, routine_id)


@router.post("/{routine_id}/steps", response_model=RoutineStepRead, status_code=201)
def create_step(family_id: uuid.UUID, routine_id: uuid.UUID, payload: RoutineStepCreate, db: Session = Depends(get_db)):
    return routine_service.create_step(db, family_id, routine_id, payload)

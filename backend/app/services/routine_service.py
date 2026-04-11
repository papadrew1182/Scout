import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.life_management import Routine, RoutineStep
from app.schemas.life_management import RoutineCreate, RoutineStepCreate
from app.services.tenant_guard import require_family, require_member_in_family


def list_routines(db: Session, family_id: uuid.UUID, member_id: uuid.UUID | None = None) -> list[Routine]:
    require_family(db, family_id)
    stmt = select(Routine).where(Routine.family_id == family_id).where(Routine.is_active.is_(True))
    if member_id:
        stmt = stmt.where(Routine.family_member_id == member_id)
    return list(db.scalars(stmt).all())


def get_routine(db: Session, family_id: uuid.UUID, routine_id: uuid.UUID) -> Routine:
    routine = db.get(Routine, routine_id)
    if not routine or routine.family_id != family_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Routine not found")
    return routine


def create_routine(db: Session, family_id: uuid.UUID, payload: RoutineCreate) -> Routine:
    require_family(db, family_id)
    require_member_in_family(db, family_id, payload.family_member_id)
    routine = Routine(
        family_id=family_id,
        family_member_id=payload.family_member_id,
        name=payload.name,
        block=payload.block,
        recurrence=payload.recurrence,
        due_time_weekday=payload.due_time_weekday,
        due_time_weekend=payload.due_time_weekend,
    )
    db.add(routine)
    db.commit()
    db.refresh(routine)
    return routine


def list_steps(db: Session, family_id: uuid.UUID, routine_id: uuid.UUID) -> list[RoutineStep]:
    routine = get_routine(db, family_id, routine_id)
    stmt = (
        select(RoutineStep)
        .where(RoutineStep.routine_id == routine.id)
        .where(RoutineStep.is_active.is_(True))
        .order_by(RoutineStep.sort_order)
    )
    return list(db.scalars(stmt).all())


def create_step(db: Session, family_id: uuid.UUID, routine_id: uuid.UUID, payload: RoutineStepCreate) -> RoutineStep:
    routine = get_routine(db, family_id, routine_id)
    step = RoutineStep(routine_id=routine.id, name=payload.name, sort_order=payload.sort_order)
    db.add(step)
    db.commit()
    db.refresh(step)
    return step

import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth import Actor, get_current_actor
from app.database import get_db
from app.schemas.health_fitness import (
    ActivityRecordCreate,
    ActivityRecordRead,
    ActivityRecordUpdate,
    HealthSummaryCreate,
    HealthSummaryRead,
    HealthSummaryUpdate,
)
from app.services import health_fitness_service

router = APIRouter(prefix="/families/{family_id}/health", tags=["health-fitness"])


# --- Health Summaries ---

@router.get("/summaries", response_model=list[HealthSummaryRead])
def list_health_summaries(
    family_id: uuid.UUID,
    family_member_id: uuid.UUID | None = Query(None),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_family(family_id)
    return health_fitness_service.list_health_summaries(
        db, family_id, family_member_id, start_date, end_date
    )


@router.get("/summaries/latest", response_model=HealthSummaryRead | None)
def get_latest_summary(
    family_id: uuid.UUID,
    family_member_id: uuid.UUID = Query(...),
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_family(family_id)
    return health_fitness_service.get_latest_summary(db, family_id, family_member_id)


@router.post("/summaries", response_model=HealthSummaryRead, status_code=201)
def create_health_summary(
    family_id: uuid.UUID,
    payload: HealthSummaryCreate,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_family(family_id)
    # noqa: public-route — family-member-ingested health data; require_family() is the access boundary and no dedicated health.manage key exists yet (TODO: add in a follow-up migration when health surfaces get role-gated admin UI)
    return health_fitness_service.create_health_summary(db, family_id, payload)


@router.get("/summaries/{summary_id}", response_model=HealthSummaryRead)
def get_health_summary(
    family_id: uuid.UUID, summary_id: uuid.UUID, actor: Actor = Depends(get_current_actor), db: Session = Depends(get_db)
):
    actor.require_family(family_id)
    return health_fitness_service.get_health_summary(db, family_id, summary_id)


@router.patch("/summaries/{summary_id}", response_model=HealthSummaryRead)
def update_health_summary(
    family_id: uuid.UUID,
    summary_id: uuid.UUID,
    payload: HealthSummaryUpdate,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_family(family_id)
    # noqa: public-route — family-scoped; see create_health_summary note on pending health.manage key
    return health_fitness_service.update_health_summary(
        db, family_id, summary_id, payload
    )


@router.delete("/summaries/{summary_id}", status_code=204)
def delete_health_summary(
    family_id: uuid.UUID, summary_id: uuid.UUID, actor: Actor = Depends(get_current_actor), db: Session = Depends(get_db)
):
    actor.require_family(family_id)
    # noqa: public-route — family-scoped; see create_health_summary note
    health_fitness_service.delete_health_summary(db, family_id, summary_id)


# --- Activity Records ---

@router.get("/activity", response_model=list[ActivityRecordRead])
def list_activity_records(
    family_id: uuid.UUID,
    family_member_id: uuid.UUID | None = Query(None),
    activity_type: str | None = Query(None),
    start: datetime | None = Query(None),
    end: datetime | None = Query(None),
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_family(family_id)
    return health_fitness_service.list_activity_records(
        db, family_id, family_member_id, activity_type, start, end
    )


@router.get("/activity/recent", response_model=list[ActivityRecordRead])
def list_recent_activity(
    family_id: uuid.UUID,
    family_member_id: uuid.UUID = Query(...),
    limit: int = Query(10, ge=1, le=100),
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_family(family_id)
    return health_fitness_service.list_recent_activity(
        db, family_id, family_member_id, limit
    )


@router.post("/activity", response_model=ActivityRecordRead, status_code=201)
def create_activity_record(
    family_id: uuid.UUID,
    payload: ActivityRecordCreate,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_family(family_id)
    # noqa: public-route — family-scoped; see create_health_summary note
    return health_fitness_service.create_activity_record(db, family_id, payload)


@router.get("/activity/{activity_id}", response_model=ActivityRecordRead)
def get_activity_record(
    family_id: uuid.UUID, activity_id: uuid.UUID, actor: Actor = Depends(get_current_actor), db: Session = Depends(get_db)
):
    actor.require_family(family_id)
    return health_fitness_service.get_activity_record(db, family_id, activity_id)


@router.patch("/activity/{activity_id}", response_model=ActivityRecordRead)
def update_activity_record(
    family_id: uuid.UUID,
    activity_id: uuid.UUID,
    payload: ActivityRecordUpdate,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_family(family_id)
    # noqa: public-route — family-scoped; see create_health_summary note
    return health_fitness_service.update_activity_record(
        db, family_id, activity_id, payload
    )


@router.delete("/activity/{activity_id}", status_code=204)
def delete_activity_record(
    family_id: uuid.UUID, activity_id: uuid.UUID, actor: Actor = Depends(get_current_actor), db: Session = Depends(get_db)
):
    actor.require_family(family_id)
    # noqa: public-route — family-scoped; see create_health_summary note
    health_fitness_service.delete_activity_record(db, family_id, activity_id)

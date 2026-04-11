"""Health / fitness service.

No workout-program engine. No nutrition tracking. No sync engines.
Just CRUD + retrieval helpers over health_summaries and activity_records.
"""

import uuid
from datetime import date, datetime

from fastapi import HTTPException, status as http_status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.health_fitness import ActivityRecord, HealthSummary
from app.schemas.health_fitness import (
    ActivityRecordCreate,
    ActivityRecordUpdate,
    HealthSummaryCreate,
    HealthSummaryUpdate,
)
from app.services.tenant_guard import require_family, require_member_in_family

_VALID_SOURCES = ("scout", "apple_health", "nike_run_club")
_VALID_ACTIVITY_TYPES = (
    "run", "walk", "bike", "swim", "strength", "yoga", "other"
)


def _validate_source(value: str) -> None:
    if value not in _VALID_SOURCES:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid source: {value}",
        )


def _validate_activity_type(value: str) -> None:
    if value not in _VALID_ACTIVITY_TYPES:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid activity_type: {value}",
        )


# ---------------------------------------------------------------------------
# Health Summaries
# ---------------------------------------------------------------------------

def list_health_summaries(
    db: Session,
    family_id: uuid.UUID,
    family_member_id: uuid.UUID | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[HealthSummary]:
    require_family(db, family_id)
    stmt = select(HealthSummary).where(HealthSummary.family_id == family_id)
    if family_member_id:
        stmt = stmt.where(HealthSummary.family_member_id == family_member_id)
    if start_date:
        stmt = stmt.where(HealthSummary.summary_date >= start_date)
    if end_date:
        stmt = stmt.where(HealthSummary.summary_date <= end_date)
    stmt = stmt.order_by(HealthSummary.summary_date.desc())
    return list(db.scalars(stmt).all())


def get_latest_summary(
    db: Session, family_id: uuid.UUID, family_member_id: uuid.UUID
) -> HealthSummary | None:
    require_member_in_family(db, family_id, family_member_id)
    stmt = (
        select(HealthSummary)
        .where(HealthSummary.family_id == family_id)
        .where(HealthSummary.family_member_id == family_member_id)
        .order_by(HealthSummary.summary_date.desc())
        .limit(1)
    )
    return db.scalars(stmt).first()


def get_health_summary(
    db: Session, family_id: uuid.UUID, summary_id: uuid.UUID
) -> HealthSummary:
    summary = db.get(HealthSummary, summary_id)
    if not summary or summary.family_id != family_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Health summary not found",
        )
    return summary


def create_health_summary(
    db: Session, family_id: uuid.UUID, payload: HealthSummaryCreate
) -> HealthSummary:
    require_member_in_family(db, family_id, payload.family_member_id)
    _validate_source(payload.source)

    summary = HealthSummary(
        family_id=family_id,
        family_member_id=payload.family_member_id,
        summary_date=payload.summary_date,
        steps=payload.steps,
        active_minutes=payload.active_minutes,
        resting_heart_rate=payload.resting_heart_rate,
        sleep_minutes=payload.sleep_minutes,
        weight_grams=payload.weight_grams,
        source=payload.source,
        notes=payload.notes,
    )
    db.add(summary)
    db.commit()
    db.refresh(summary)
    return summary


def update_health_summary(
    db: Session,
    family_id: uuid.UUID,
    summary_id: uuid.UUID,
    payload: HealthSummaryUpdate,
) -> HealthSummary:
    summary = get_health_summary(db, family_id, summary_id)
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(summary, key, value)
    db.commit()
    db.refresh(summary)
    return summary


def delete_health_summary(
    db: Session, family_id: uuid.UUID, summary_id: uuid.UUID
) -> None:
    summary = get_health_summary(db, family_id, summary_id)
    db.delete(summary)
    db.commit()


# ---------------------------------------------------------------------------
# Activity Records
# ---------------------------------------------------------------------------

def list_activity_records(
    db: Session,
    family_id: uuid.UUID,
    family_member_id: uuid.UUID | None = None,
    activity_type: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[ActivityRecord]:
    require_family(db, family_id)
    stmt = select(ActivityRecord).where(ActivityRecord.family_id == family_id)
    if family_member_id:
        stmt = stmt.where(ActivityRecord.family_member_id == family_member_id)
    if activity_type:
        stmt = stmt.where(ActivityRecord.activity_type == activity_type)
    if start:
        stmt = stmt.where(ActivityRecord.started_at >= start)
    if end:
        stmt = stmt.where(ActivityRecord.started_at <= end)
    stmt = stmt.order_by(ActivityRecord.started_at.desc())
    return list(db.scalars(stmt).all())


def list_recent_activity(
    db: Session,
    family_id: uuid.UUID,
    family_member_id: uuid.UUID,
    limit: int = 10,
) -> list[ActivityRecord]:
    require_member_in_family(db, family_id, family_member_id)
    stmt = (
        select(ActivityRecord)
        .where(ActivityRecord.family_id == family_id)
        .where(ActivityRecord.family_member_id == family_member_id)
        .order_by(ActivityRecord.started_at.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt).all())


def get_activity_record(
    db: Session, family_id: uuid.UUID, activity_id: uuid.UUID
) -> ActivityRecord:
    record = db.get(ActivityRecord, activity_id)
    if not record or record.family_id != family_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Activity record not found",
        )
    return record


def create_activity_record(
    db: Session, family_id: uuid.UUID, payload: ActivityRecordCreate
) -> ActivityRecord:
    require_member_in_family(db, family_id, payload.family_member_id)
    _validate_source(payload.source)
    _validate_activity_type(payload.activity_type)
    if payload.ended_at and payload.ended_at < payload.started_at:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="ended_at must be >= started_at",
        )

    record = ActivityRecord(
        family_id=family_id,
        family_member_id=payload.family_member_id,
        activity_type=payload.activity_type,
        title=payload.title,
        started_at=payload.started_at,
        ended_at=payload.ended_at,
        duration_seconds=payload.duration_seconds,
        distance_meters=payload.distance_meters,
        calories=payload.calories,
        source=payload.source,
        notes=payload.notes,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def update_activity_record(
    db: Session,
    family_id: uuid.UUID,
    activity_id: uuid.UUID,
    payload: ActivityRecordUpdate,
) -> ActivityRecord:
    record = get_activity_record(db, family_id, activity_id)
    data = payload.model_dump(exclude_unset=True)

    new_ended = data.get("ended_at", record.ended_at)
    if new_ended is not None and new_ended < record.started_at:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="ended_at must be >= started_at",
        )

    for key, value in data.items():
        setattr(record, key, value)
    db.commit()
    db.refresh(record)
    return record


def delete_activity_record(
    db: Session, family_id: uuid.UUID, activity_id: uuid.UUID
) -> None:
    record = get_activity_record(db, family_id, activity_id)
    db.delete(record)
    db.commit()

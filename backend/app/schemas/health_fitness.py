import uuid
from datetime import date, datetime

from pydantic import BaseModel


# --- HealthSummary ---

class HealthSummaryCreate(BaseModel):
    family_member_id: uuid.UUID
    summary_date: date
    steps: int | None = None
    active_minutes: int | None = None
    resting_heart_rate: int | None = None
    sleep_minutes: int | None = None
    weight_grams: int | None = None
    source: str = "scout"
    notes: str | None = None


class HealthSummaryUpdate(BaseModel):
    steps: int | None = None
    active_minutes: int | None = None
    resting_heart_rate: int | None = None
    sleep_minutes: int | None = None
    weight_grams: int | None = None
    notes: str | None = None


class HealthSummaryRead(BaseModel):
    id: uuid.UUID
    family_id: uuid.UUID
    family_member_id: uuid.UUID
    summary_date: date
    steps: int | None
    active_minutes: int | None
    resting_heart_rate: int | None
    sleep_minutes: int | None
    weight_grams: int | None
    source: str
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- ActivityRecord ---

class ActivityRecordCreate(BaseModel):
    family_member_id: uuid.UUID
    activity_type: str
    title: str | None = None
    started_at: datetime
    ended_at: datetime | None = None
    duration_seconds: int | None = None
    distance_meters: int | None = None
    calories: int | None = None
    source: str = "scout"
    notes: str | None = None


class ActivityRecordUpdate(BaseModel):
    title: str | None = None
    ended_at: datetime | None = None
    duration_seconds: int | None = None
    distance_meters: int | None = None
    calories: int | None = None
    notes: str | None = None


class ActivityRecordRead(BaseModel):
    id: uuid.UUID
    family_id: uuid.UUID
    family_member_id: uuid.UUID
    activity_type: str
    title: str | None
    started_at: datetime
    ended_at: datetime | None
    duration_seconds: int | None
    distance_meters: int | None
    calories: int | None
    source: str
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

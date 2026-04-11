import uuid
from datetime import date, datetime

from pydantic import BaseModel


# --- Event ---

class EventCreate(BaseModel):
    created_by: uuid.UUID | None = None
    title: str
    description: str | None = None
    location: str | None = None
    starts_at: datetime
    ends_at: datetime
    all_day: bool = False
    recurrence_rule: str | None = None
    source: str = "scout"
    is_hearth_visible: bool = True
    task_instance_id: uuid.UUID | None = None


class EventInstanceCreate(BaseModel):
    """Create an edited instance of a recurring event."""
    recurrence_instance_date: date
    title: str
    description: str | None = None
    location: str | None = None
    starts_at: datetime
    ends_at: datetime
    all_day: bool = False
    is_cancelled: bool = False


class EventUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    location: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    all_day: bool | None = None
    is_hearth_visible: bool | None = None
    is_cancelled: bool | None = None


class EventRead(BaseModel):
    id: uuid.UUID
    family_id: uuid.UUID
    created_by: uuid.UUID | None
    title: str
    description: str | None
    location: str | None
    starts_at: datetime
    ends_at: datetime
    all_day: bool
    recurrence_rule: str | None
    recurrence_parent_id: uuid.UUID | None
    recurrence_instance_date: date | None
    source: str
    is_hearth_visible: bool
    task_instance_id: uuid.UUID | None
    is_cancelled: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- EventAttendee ---

class EventAttendeeCreate(BaseModel):
    family_member_id: uuid.UUID
    response_status: str = "pending"


class EventAttendeeUpdate(BaseModel):
    response_status: str


class EventAttendeeRead(BaseModel):
    id: uuid.UUID
    event_id: uuid.UUID
    family_member_id: uuid.UUID
    response_status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

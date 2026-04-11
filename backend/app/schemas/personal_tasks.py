import uuid
from datetime import datetime

from pydantic import BaseModel


class PersonalTaskCreate(BaseModel):
    assigned_to: uuid.UUID
    created_by: uuid.UUID | None = None
    title: str
    description: str | None = None
    notes: str | None = None
    status: str = "pending"
    priority: str = "medium"
    due_at: datetime | None = None
    event_id: uuid.UUID | None = None


class PersonalTaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    notes: str | None = None
    status: str | None = None
    priority: str | None = None
    due_at: datetime | None = None
    assigned_to: uuid.UUID | None = None
    event_id: uuid.UUID | None = None


class PersonalTaskRead(BaseModel):
    id: uuid.UUID
    family_id: uuid.UUID
    assigned_to: uuid.UUID
    created_by: uuid.UUID | None
    title: str
    description: str | None
    notes: str | None
    status: str
    priority: str
    due_at: datetime | None
    completed_at: datetime | None
    event_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

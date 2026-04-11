import uuid
from datetime import datetime

from pydantic import BaseModel


class NoteCreate(BaseModel):
    family_member_id: uuid.UUID
    title: str
    body: str = ""
    category: str | None = None


class NoteUpdate(BaseModel):
    title: str | None = None
    body: str | None = None
    category: str | None = None
    is_archived: bool | None = None


class NoteRead(BaseModel):
    id: uuid.UUID
    family_id: uuid.UUID
    family_member_id: uuid.UUID
    title: str
    body: str
    category: str | None
    is_archived: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

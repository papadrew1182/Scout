import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


# --- Family ---

class FamilyCreate(BaseModel):
    name: str
    timezone: str = "America/Chicago"


class FamilyRead(BaseModel):
    id: uuid.UUID
    name: str
    timezone: str
    allow_general_chat: bool = True
    allow_homework_help: bool = True
    home_location: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FamilyAISettingsRead(BaseModel):
    """Just the AI-related fields on the family, pulled out so the
    Settings UI doesn't need the full FamilyRead shape."""

    allow_general_chat: bool
    allow_homework_help: bool
    home_location: str | None = None

    model_config = {"from_attributes": True}


class FamilyAISettingsUpdate(BaseModel):
    allow_general_chat: bool | None = None
    allow_homework_help: bool | None = None
    home_location: str | None = Field(default=None, max_length=200)


# --- FamilyMember ---

class FamilyMemberCreate(BaseModel):
    first_name: str
    last_name: str | None = None
    role: str
    birthdate: date | None = None


class FamilyMemberRead(BaseModel):
    id: uuid.UUID
    family_id: uuid.UUID
    first_name: str
    last_name: str | None
    role: str
    birthdate: date | None
    grade_level: str | None = None
    learning_notes: str | None = None
    read_aloud_enabled: bool = False
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FamilyMemberLearningUpdate(BaseModel):
    grade_level: str | None = Field(default=None, max_length=40)
    learning_notes: str | None = Field(default=None, max_length=2000)
    read_aloud_enabled: bool | None = None

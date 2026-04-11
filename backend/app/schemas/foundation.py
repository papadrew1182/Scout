import uuid
from datetime import date, datetime

from pydantic import BaseModel


# --- Family ---

class FamilyCreate(BaseModel):
    name: str
    timezone: str = "America/Chicago"


class FamilyRead(BaseModel):
    id: uuid.UUID
    name: str
    timezone: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


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
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

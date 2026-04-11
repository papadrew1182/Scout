import uuid
from datetime import date, datetime

from pydantic import BaseModel


class BillCreate(BaseModel):
    created_by: uuid.UUID | None = None
    title: str
    description: str | None = None
    notes: str | None = None
    amount_cents: int
    due_date: date
    status: str = "upcoming"
    source: str = "scout"


class BillUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    notes: str | None = None
    amount_cents: int | None = None
    due_date: date | None = None
    status: str | None = None


class BillRead(BaseModel):
    id: uuid.UUID
    family_id: uuid.UUID
    created_by: uuid.UUID | None
    title: str
    description: str | None
    notes: str | None
    amount_cents: int
    due_date: date
    status: str
    paid_at: datetime | None
    source: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

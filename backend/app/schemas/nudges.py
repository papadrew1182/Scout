"""Pydantic read schemas for NudgeDispatch + NudgeDispatchItem.

Sprint 05 Phase 2 — backs GET /api/nudges/me (Recent-nudges UI on
/settings/ai). Read-only; no write schemas yet. Child items are
embedded so the UI does not need a second round-trip to render the
trigger list for a batched dispatch.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator


class NudgeDispatchItemRead(BaseModel):
    id: uuid.UUID
    trigger_kind: str
    trigger_entity_kind: str
    trigger_entity_id: uuid.UUID | None
    occurrence_at_utc: datetime
    occurrence_local_date: date
    source_metadata: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class NudgeDispatchRead(BaseModel):
    id: uuid.UUID
    family_member_id: uuid.UUID
    status: str
    severity: str
    suppressed_reason: str | None
    deliver_after_utc: datetime
    delivered_at_utc: datetime | None
    delivered_channels: list[str]
    source_count: int
    body: str | None
    items: list[NudgeDispatchItemRead]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class QuietHoursRead(BaseModel):
    """GET response. Returns the effective window for the family.
    When no row exists, the backend returns the system default
    (22*60=1320 start, 7*60=420 end) so the UI always has a value
    to render."""

    start_local_minute: int
    end_local_minute: int
    is_default: bool  # True when no quiet_hours_family row exists


class QuietHoursUpdate(BaseModel):
    start_local_minute: int = Field(ge=0, lt=1440)
    end_local_minute: int = Field(ge=0, lt=1440)

    @model_validator(mode="after")
    def _start_not_equal_end(self) -> "QuietHoursUpdate":
        if self.start_local_minute == self.end_local_minute:
            raise ValueError("start_local_minute must differ from end_local_minute")
        return self

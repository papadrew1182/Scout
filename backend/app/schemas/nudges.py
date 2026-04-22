"""Pydantic read schemas for NudgeDispatch + NudgeDispatchItem.

Sprint 05 Phase 2 — backs GET /api/nudges/me (Recent-nudges UI on
/settings/ai). Read-only; no write schemas yet. Child items are
embedded so the UI does not need a second round-trip to render the
trigger list for a batched dispatch.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel


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

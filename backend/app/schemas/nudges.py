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


# Sprint 05 Phase 4 -- admin rule engine


class NudgeRuleRead(BaseModel):
    """GET / list response shape."""

    id: uuid.UUID
    family_id: uuid.UUID
    name: str
    description: str | None
    is_active: bool
    source_kind: str
    template_sql: str | None
    canonical_sql: str | None
    template_params: dict
    trigger_kind: str
    default_lead_time_minutes: int
    severity: str
    created_by_family_member_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class NudgeRuleCreate(BaseModel):
    """POST body. template_sql is required for source_kind='sql_template'
    (the only v1 source_kind). canonical_sql is produced server-side by
    validate_rule_sql; clients do not submit it."""

    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    source_kind: str = Field(default="sql_template", pattern="^sql_template$")
    template_sql: str = Field(min_length=1, max_length=4000)
    template_params: dict = Field(default_factory=dict)
    default_lead_time_minutes: int = Field(default=0, ge=0, le=1440)
    severity: str = Field(default="normal", pattern="^(low|normal|high)$")
    is_active: bool = True

    model_config = {"extra": "forbid"}


class NudgeRulePatch(BaseModel):
    """PATCH body. All fields optional; server-side validation runs
    validate_rule_sql on any template_sql change and re-populates
    canonical_sql."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    template_sql: str | None = Field(default=None, min_length=1, max_length=4000)
    template_params: dict | None = None
    default_lead_time_minutes: int | None = Field(default=None, ge=0, le=1440)
    severity: str | None = Field(default=None, pattern="^(low|normal|high)$")
    is_active: bool | None = None

    model_config = {"extra": "forbid"}


class PreviewCountResponse(BaseModel):
    """POST /preview-count response. The count is capped at 200 in the
    rule executor; any higher value is returned as 200 with
    capped=true."""

    count: int
    capped: bool
    error: str | None = None  # populated when the rule's SQL fails to run

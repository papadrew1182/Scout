"""Pydantic schema for AI-driven nudge discovery output (Sprint 05 Phase 5).

The orchestrator returns JSON; pydantic validates each proposal. Malformed
items are dropped rather than raising so one bad AI hallucination does not
poison the whole tick.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DiscoveryProposal(BaseModel):
    """One AI-proposed nudge. Task 2 will convert this to NudgeProposal."""

    model_config = ConfigDict(extra="forbid")

    member_id: uuid.UUID = Field(description="Target family member")
    trigger_entity_kind: Literal[
        "personal_task", "event", "task_instance", "general"
    ] = Field(
        default="general",
        description="What structured entity this refers to; 'general' if none.",
    )
    trigger_entity_id: uuid.UUID | None = None
    scheduled_for: datetime = Field(
        description="When the nudge should deliver, naive-UTC."
    )
    severity: Literal["low", "normal", "high"] = "normal"
    body: str = Field(
        min_length=1, max_length=280,
        description="Pre-composed nudge body (Phase 3 composer skipped for AI-suggested; AI is trusted to produce final copy).",
    )

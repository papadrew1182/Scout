"""ORM models for Tier 5 schema.

Grouped in one file to keep the tier change set cohesive and the
migration review easy. Nothing here is cross-cutting — each model is
used by exactly one feature."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Float, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PlannerBundleApply(Base):
    """Idempotency + audit row for F16 atomic planner applies.

    One row per (family_id, bundle_apply_id). A duplicate apply call
    with the same key returns the original result instead of
    re-writing."""

    __tablename__ = "planner_bundle_applies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    bundle_apply_id: Mapped[str] = mapped_column(Text, nullable=False)
    family_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("families.id", ondelete="CASCADE"),
        nullable=False,
    )
    actor_member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("family_members.id", ondelete="CASCADE"),
        nullable=False,
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_conversations.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, default="applied")
    tasks_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    events_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    grocery_items_created: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    errors: Mapped[dict | None] = mapped_column(JSONB)
    summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.clock_timestamp()
    )


class AnomalySuppression(Base):
    """F18: suppression ledger for the anomaly scan.

    Unique on (family_id, anomaly_type, signature). When a detector
    fires a candidate it checks this table first — if a matching row
    exists with ``suppress_until`` in the future, the candidate is
    dropped and ``last_seen_at`` is bumped. Otherwise a new row (or
    refreshed row) is written with a ``suppress_until`` derived from
    the detector's configured suppression window."""

    __tablename__ = "scout_anomaly_suppressions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    family_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("families.id", ondelete="CASCADE"),
        nullable=False,
    )
    anomaly_type: Mapped[str] = mapped_column(Text, nullable=False)
    signature: Mapped[str] = mapped_column(Text, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.clock_timestamp()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.clock_timestamp()
    )
    suppress_until: Mapped[datetime] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.clock_timestamp()
    )


class ScoutMCPToken(Base):
    """F19: bearer tokens for the remote MCP transport.

    Scope is one of 'parent' (default) or 'child'. Parent tokens get
    the full read-only tool surface. Child tokens are restricted to
    safe subsets (schedule, tasks, meals, grocery) and never see the
    inbox, briefs, cost, or homework rollup.

    ``token_hash`` is a sha256 hex of the plaintext bearer — the
    plaintext is shown to the parent exactly once at creation and
    never stored."""

    __tablename__ = "scout_mcp_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    family_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("families.id", ondelete="CASCADE"),
        nullable=False,
    )
    member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("family_members.id", ondelete="CASCADE")
    )
    token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    label: Mapped[str | None] = mapped_column(Text)
    scope: Mapped[str] = mapped_column(Text, nullable=False, default="parent")
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    last_used_at: Mapped[datetime | None] = mapped_column()
    created_by_member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("family_members.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.clock_timestamp()
    )
    revoked_at: Mapped[datetime | None] = mapped_column()


class FamilyMemory(Base):
    """F20: persistent family preferences + planning defaults.

    Not the same as ``learning_notes`` (academic support context) or
    ``personality_notes`` (per-child tone/coaching). Memories are
    family-level or (optionally) member-level structured facts with
    a review lifecycle:

        proposed → active → archived

    Only ``active`` memories are injected into prompts, and the
    injection is bounded (see ``app.ai.memory``).
    """

    __tablename__ = "family_memories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    family_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("families.id", ondelete="CASCADE"),
        nullable=False,
    )
    member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("family_members.id", ondelete="CASCADE")
    )
    memory_type: Mapped[str] = mapped_column(Text, nullable=False)
    scope: Mapped[str] = mapped_column(Text, nullable=False, default="family")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    source_kind: Mapped[str] = mapped_column(
        Text, nullable=False, default="parent_edit"
    )
    source_conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_conversations.id", ondelete="SET NULL")
    )
    created_by_kind: Mapped[str] = mapped_column(
        Text, nullable=False, default="parent"
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    last_confirmed_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.clock_timestamp()
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.clock_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.clock_timestamp()
    )

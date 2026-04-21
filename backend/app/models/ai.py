import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AIConversation(Base):
    __tablename__ = "ai_conversations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("families.id", ondelete="CASCADE"), nullable=False)
    family_member_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("family_members.id", ondelete="CASCADE"), nullable=False)
    surface: Mapped[str] = mapped_column(String(20), nullable=False, default="personal")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    conversation_kind: Mapped[str] = mapped_column(
        String(20), nullable=False, default="chat", server_default="chat"
    )
    # Sprint 04 Phase 1 fields (migration 046)
    title: Mapped[str | None] = mapped_column(Text)
    last_active_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    is_pinned: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    messages: Mapped[list["AIMessage"]] = relationship(back_populates="conversation", cascade="all, delete-orphan", order_by="AIMessage.created_at")


class AIMessage(Base):
    __tablename__ = "ai_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ai_conversations.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str | None] = mapped_column(Text)
    tool_calls: Mapped[dict | None] = mapped_column(JSONB)
    tool_results: Mapped[dict | None] = mapped_column(JSONB)
    model: Mapped[str | None] = mapped_column(Text)
    token_usage: Mapped[dict | None] = mapped_column(JSONB)
    # Auxiliary per-message metadata. Current uses:
    #   attachment: {"attachment_path": "...", "attachment_url": "..."}
    # Added in migration 045. Named 'attachment_meta' because 'metadata'
    # is reserved by SQLAlchemy's Declarative API.
    attachment_meta: Mapped[dict | None] = mapped_column("metadata", JSONB)
    # clock_timestamp() returns wall-clock time at the moment of INSERT,
    # so multiple rows flushed in the same transaction get distinct
    # microsecond timestamps. Migration 017 switched ai_messages off
    # now() / transaction_timestamp() for this reason. See the
    # _load_conversation_messages replay for why monotonic ordering
    # matters.
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.clock_timestamp())

    conversation: Mapped["AIConversation"] = relationship(back_populates="messages")


class AIToolAudit(Base):
    __tablename__ = "ai_tool_audit"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("families.id", ondelete="CASCADE"), nullable=False)
    actor_member_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("family_members.id", ondelete="CASCADE"), nullable=False)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("ai_conversations.id", ondelete="SET NULL"))
    tool_name: Mapped[str] = mapped_column(Text, nullable=False)
    arguments: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    result_summary: Mapped[str | None] = mapped_column(Text)
    target_entity: Mapped[str | None] = mapped_column(Text)
    target_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="success")
    error_message: Mapped[str | None] = mapped_column(Text)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

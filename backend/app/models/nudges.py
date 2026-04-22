import uuid
from datetime import date, datetime

from sqlalchemy import Date, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class NudgeDispatch(Base):
    __tablename__ = "nudge_dispatches"
    __table_args__ = {"schema": "scout"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    family_member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("family_members.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    severity: Mapped[str] = mapped_column(String(10), nullable=False, default="normal")
    suppressed_reason: Mapped[str | None] = mapped_column(Text)
    deliver_after_utc: Mapped[datetime] = mapped_column(nullable=False)
    delivered_at_utc: Mapped[datetime | None] = mapped_column()
    parent_action_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("parent_action_items.id", ondelete="SET NULL"),
    )
    push_delivery_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scout.push_deliveries.id", ondelete="SET NULL"),
    )
    delivered_channels: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    source_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    body: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )

    items: Mapped[list["NudgeDispatchItem"]] = relationship(
        back_populates="dispatch", cascade="all, delete-orphan"
    )


class NudgeDispatchItem(Base):
    __tablename__ = "nudge_dispatch_items"
    __table_args__ = {"schema": "scout"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    dispatch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scout.nudge_dispatches.id", ondelete="CASCADE"),
        nullable=False,
    )
    family_member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("family_members.id", ondelete="CASCADE"),
        nullable=False,
    )
    trigger_kind: Mapped[str] = mapped_column(Text, nullable=False)
    trigger_entity_kind: Mapped[str] = mapped_column(Text, nullable=False)
    trigger_entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    occurrence_at_utc: Mapped[datetime] = mapped_column(nullable=False)
    occurrence_local_date: Mapped[date] = mapped_column(Date, nullable=False)
    source_dedupe_key: Mapped[str] = mapped_column(Text, nullable=False)
    source_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )

    dispatch: Mapped["NudgeDispatch"] = relationship(back_populates="items")

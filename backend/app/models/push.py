"""Push notification models.

Two tables back Phase 1 of the Expansion sprint:

- `PushDevice`: one row per physical device per member, keyed by Expo
  push token.
- `PushDelivery`: one row per (notification_group_id, device) pair, so a
  single logical notification fanned out to three devices produces three
  rows. Status transitions are driven by the push service
  (`provider_accepted`) and the receipt poller
  (`provider_handoff_ok` / `provider_error`).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PushDevice(Base):
    __tablename__ = "push_devices"
    __table_args__ = {"schema": "scout"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    family_member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("family_members.id", ondelete="CASCADE"),
        nullable=False,
    )
    expo_push_token: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    device_label: Mapped[str | None] = mapped_column(Text)
    platform: Mapped[str] = mapped_column(Text, nullable=False)
    app_version: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_registered_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
    last_successful_delivery_at: Mapped[datetime | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )


class PushDelivery(Base):
    __tablename__ = "push_deliveries"
    __table_args__ = {"schema": "scout"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    notification_group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    family_member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("family_members.id", ondelete="CASCADE"),
        nullable=False,
    )
    push_device_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scout.push_devices.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(Text, nullable=False, default="expo")
    category: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    trigger_source: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="queued")
    provider_ticket_id: Mapped[str | None] = mapped_column(Text)
    provider_receipt_status: Mapped[str | None] = mapped_column(Text)
    provider_receipt_payload: Mapped[dict | None] = mapped_column(JSONB)
    error_message: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column()
    receipt_checked_at: Mapped[datetime | None] = mapped_column()
    provider_handoff_at: Mapped[datetime | None] = mapped_column()
    tapped_at: Mapped[datetime | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )

    device: Mapped[PushDevice] = relationship("PushDevice")

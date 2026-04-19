import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class HomeZone(Base):
    __tablename__ = "home_zones"
    __table_args__ = {"schema": "scout"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("families.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    zone_type: Mapped[str] = mapped_column(Text, nullable=False, default="room")
    notes: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())


class HomeAsset(Base):
    __tablename__ = "home_assets"
    __table_args__ = {"schema": "scout"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("families.id", ondelete="CASCADE"), nullable=False)
    zone_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("scout.home_zones.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(Text, nullable=False)
    asset_type: Mapped[str | None] = mapped_column(Text)
    model: Mapped[str | None] = mapped_column(Text)
    serial: Mapped[str | None] = mapped_column(Text)
    purchase_date: Mapped[datetime | None] = mapped_column()
    warranty_expires_at: Mapped[datetime | None] = mapped_column()
    manual_url: Mapped[str | None] = mapped_column(Text)
    receipt_url: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())


class MaintenanceTemplate(Base):
    __tablename__ = "maintenance_templates"
    __table_args__ = {"schema": "scout"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("families.id", ondelete="CASCADE"), nullable=False)
    zone_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("scout.home_zones.id", ondelete="SET NULL"))
    asset_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("scout.home_assets.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    cadence_type: Mapped[str] = mapped_column(Text, nullable=False, default="monthly")
    rotation_month_mod: Mapped[int | None] = mapped_column(Integer)
    included: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    not_included: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    done_means_done: Mapped[str | None] = mapped_column(Text)
    supplies: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    estimated_duration_minutes: Mapped[int | None] = mapped_column(Integer)
    default_owner_member_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("family_members.id", ondelete="SET NULL"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())


class MaintenanceInstance(Base):
    __tablename__ = "maintenance_instances"
    __table_args__ = {"schema": "scout"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("families.id", ondelete="CASCADE"), nullable=False)
    template_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scout.maintenance_templates.id", ondelete="CASCADE"), nullable=False)
    owner_member_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("family_members.id", ondelete="CASCADE"), nullable=False)
    scheduled_for: Mapped[datetime] = mapped_column(nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column()
    completed_by_member_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("family_members.id", ondelete="SET NULL"))
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

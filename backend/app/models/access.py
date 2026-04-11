import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RoleTier(Base):
    __tablename__ = "role_tiers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(10), nullable=False, unique=True)
    permissions: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    behavior_config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())


class RoleTierOverride(Base):
    __tablename__ = "role_tier_overrides"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_member_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("family_members.id", ondelete="CASCADE"), nullable=False)
    role_tier_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("role_tiers.id", ondelete="RESTRICT"), nullable=False)
    override_permissions: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    override_behavior: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

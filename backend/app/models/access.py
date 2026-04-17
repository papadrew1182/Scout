import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class HouseholdRule(Base):
    """Canonical family-level key/value configuration (scout.household_rules).

    This is the authoritative home for all family config — supersedes the
    retired public.family_config table (dropped in migration 035).
    """

    __tablename__ = "household_rules"
    __table_args__ = {"schema": "scout"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("families.id", ondelete="CASCADE"), nullable=False)
    rule_key: Mapped[str] = mapped_column(Text, nullable=False)
    rule_value: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())


class RoleTier(Base):
    __tablename__ = "role_tiers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    permissions: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    behavior_config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())


class RoleTierOverride(Base):
    __tablename__ = "role_tier_overrides"
    __table_args__ = (UniqueConstraint("family_member_id", name="uq_role_tier_overrides_member"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_member_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("family_members.id", ondelete="CASCADE"), nullable=False)
    role_tier_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("role_tiers.id", ondelete="RESTRICT"), nullable=False)
    override_permissions: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    override_behavior: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())


class MemberConfig(Base):
    __tablename__ = "member_config"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_member_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("family_members.id", ondelete="CASCADE"), nullable=False)
    key: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("family_members.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

"""SQLAlchemy ORM models for the scout.* canonical tables introduced by
migration 022.

Models here are schema-qualified to ``scout`` via ``__table_args__``.
All tables live in the ``scout`` schema; public.* foreign keys are
referenced with the full ``public.`` prefix in ForeignKey() strings.
"""

import uuid
from datetime import date, datetime, time

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RoutineTemplate(Base):
    """scout.routine_templates — per-member routine definitions."""

    __tablename__ = "routine_templates"
    __table_args__ = {"schema": "scout"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    family_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("families.id", ondelete="CASCADE"),
        nullable=False,
    )
    routine_key: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    block_label: Mapped[str] = mapped_column(Text, nullable=False)
    recurrence: Mapped[str] = mapped_column(Text, nullable=False, default="daily")
    due_time_weekday: Mapped[time | None] = mapped_column()
    due_time_weekend: Mapped[time | None] = mapped_column()
    owner_family_member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("family_members.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )


class RewardPolicy(Base):
    """scout.reward_policies — per-member allowance policies."""

    __tablename__ = "reward_policies"
    __table_args__ = {"schema": "scout"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    family_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("families.id", ondelete="CASCADE"),
        nullable=False,
    )
    family_member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("family_members.id", ondelete="CASCADE"),
        nullable=True,
    )
    policy_key: Mapped[str] = mapped_column(Text, nullable=False)
    baseline_amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    payout_schedule: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    wins_required: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=list
    )
    extras_allowed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )


class Connector(Base):
    """scout.connectors — connector registry (seeded by migration 022)."""

    __tablename__ = "connectors"
    __table_args__ = {"schema": "scout"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    connector_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    tier: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    decision_gated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )


class ConnectorAccount(Base):
    """scout.connector_accounts — per-family connection status rows."""

    __tablename__ = "connector_accounts"
    __table_args__ = {"schema": "scout"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    connector_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scout.connectors.id", ondelete="CASCADE"),
        nullable=False,
    )
    family_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("families.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user_accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    account_label: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="configured"
    )
    last_success_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_error_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )

import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class NudgeRule(Base):
    """Admin-configurable nudge trigger rule (Sprint 05 Phase 4).

    v1 supports source_kind='sql_template' only: template_sql is
    a Postgres SELECT that returns (member_id, entity_id, entity_kind,
    scheduled_for) rows. The rule scanner calls it each scheduler tick
    under READ ONLY + statement_timeout + lock_timeout. canonical_sql
    is the re-serialized form produced by validate_rule_sql at CRUD
    write time; the scheduler executes that, never the raw template.
    """

    __tablename__ = "nudge_rules"
    __table_args__ = {"schema": "scout"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    family_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("families.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    source_kind: Mapped[str] = mapped_column(
        String(20), nullable=False, default="sql_template"
    )
    template_sql: Mapped[str | None] = mapped_column(Text)
    canonical_sql: Mapped[str | None] = mapped_column(Text)
    template_params: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    trigger_kind: Mapped[str] = mapped_column(
        String(30), nullable=False, default="custom_rule"
    )
    default_lead_time_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    severity: Mapped[str] = mapped_column(
        String(10), nullable=False, default="normal"
    )
    created_by_family_member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("family_members.id", ondelete="SET NULL"),
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )

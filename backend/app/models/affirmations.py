import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Affirmation(Base):
    __tablename__ = "affirmations"
    __table_args__ = {"schema": "scout"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    tone: Mapped[str | None] = mapped_column(Text)
    philosophy: Mapped[str | None] = mapped_column(Text)
    audience_type: Mapped[str] = mapped_column(Text, nullable=False, default="general")
    length_class: Mapped[str] = mapped_column(Text, nullable=False, default="short")
    active: Mapped[bool] = mapped_column(nullable=False, default=True)
    source_type: Mapped[str] = mapped_column(Text, nullable=False, default="curated")
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("family_members.id", ondelete="SET NULL"))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("family_members.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())


class AffirmationFeedback(Base):
    __tablename__ = "affirmation_feedback"
    __table_args__ = {"schema": "scout"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_member_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("family_members.id", ondelete="CASCADE"), nullable=False)
    affirmation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scout.affirmations.id", ondelete="CASCADE"), nullable=False)
    reaction_type: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())


class AffirmationDeliveryLog(Base):
    __tablename__ = "affirmation_delivery_log"
    __table_args__ = {"schema": "scout"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_member_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("family_members.id", ondelete="CASCADE"), nullable=False)
    affirmation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scout.affirmations.id", ondelete="CASCADE"), nullable=False)
    surfaced_at: Mapped[datetime] = mapped_column(nullable=False)
    surfaced_in: Mapped[str] = mapped_column(Text, nullable=False)
    dismissed_at: Mapped[datetime | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

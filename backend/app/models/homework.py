"""Homework session model for kid-specific progress tracking."""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class HomeworkSession(Base):
    """One row per detected kid homework activity, grouped by conversation
    and recent-window. Parent dashboard rollups read from here.

    Subject is auto-detected from the child's message(s) via a cheap
    keyword + classifier hybrid; grade_level_at_time snapshots the
    child's ``family_members.grade_level`` at session-start so the
    rollup remains meaningful after promotion to the next grade.
    """

    __tablename__ = "ai_homework_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    family_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("families.id", ondelete="CASCADE"), nullable=False
    )
    member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("family_members.id", ondelete="CASCADE"), nullable=False
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_conversations.id", ondelete="SET NULL")
    )
    subject: Mapped[str] = mapped_column(Text, nullable=False, default="other")
    summary: Mapped[str | None] = mapped_column(Text)
    grade_level_at_time: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.clock_timestamp()
    )
    ended_at: Mapped[datetime | None] = mapped_column()
    turn_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    session_length_sec: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.clock_timestamp()
    )

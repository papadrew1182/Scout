import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class QuietHoursFamily(Base):
    """Family-wide quiet-hours window for Scout nudges.

    Stored as minutes-from-local-midnight so a single int pair expresses
    any wall-clock start/end without caring about timezone conversion at
    write time; the service layer resolves against family.timezone when
    gating each proposal.

    Unique on (family_id) -- each family has at most one row. Per-member
    override lives in member_config['nudges.quiet_hours'] and wins when
    set, per revised plan Section 4 step 5.
    """

    __tablename__ = "quiet_hours_family"
    __table_args__ = {"schema": "scout"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    family_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("families.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    start_local_minute: Mapped[int] = mapped_column(
        Integer, nullable=False, default=22 * 60
    )
    end_local_minute: Mapped[int] = mapped_column(
        Integer, nullable=False, default=7 * 60
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )

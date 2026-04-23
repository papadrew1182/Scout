import uuid
from datetime import date, datetime, time

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String, Text, Time, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Routine(Base):
    __tablename__ = "routines"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("families.id", ondelete="CASCADE"), nullable=False)
    family_member_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("family_members.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    block: Mapped[str] = mapped_column(String(20), nullable=False)
    recurrence: Mapped[str] = mapped_column(String(10), nullable=False, default="daily")
    due_time_weekday: Mapped[time] = mapped_column(Time, nullable=False)
    due_time_weekend: Mapped[time | None] = mapped_column(Time)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    steps: Mapped[list["RoutineStep"]] = relationship(back_populates="routine", cascade="all, delete-orphan", order_by="RoutineStep.sort_order")


class RoutineStep(Base):
    __tablename__ = "routine_steps"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    routine_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("routines.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    routine: Mapped["Routine"] = relationship(back_populates="steps")


class ChoreTemplate(Base):
    __tablename__ = "chore_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("families.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    recurrence: Mapped[str] = mapped_column(String(10), nullable=False, default="daily")
    due_time: Mapped[time] = mapped_column(Time, nullable=False)
    assignment_type: Mapped[str] = mapped_column(String(20), nullable=False)
    assignment_rule: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    included: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    not_included: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    done_means_done: Mapped[str | None] = mapped_column(Text)
    supplies: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # Stores the Supabase Storage PATH (e.g. "{family_id}/{member_id}/{date}/{file}"),
    # NOT a signed URL. Signed URLs expire in 1 hour; persisting one
    # would go stale within an hour. Consumers resolve the path to a
    # fresh signed URL at read time via GET /api/storage/signed-url.
    # Column name kept as photo_example_url for backward compatibility
    # even though the contents are now a path string.
    photo_example_url: Mapped[str | None] = mapped_column(Text)
    estimated_duration_minutes: Mapped[int | None] = mapped_column()
    consequence_on_miss: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())


class TaskInstance(Base):
    __tablename__ = "task_instances"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("families.id", ondelete="CASCADE"), nullable=False)
    family_member_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("family_members.id", ondelete="CASCADE"), nullable=False)
    routine_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("routines.id", ondelete="RESTRICT"))
    chore_template_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("chore_templates.id", ondelete="RESTRICT"))
    instance_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_at: Mapped[datetime] = mapped_column(nullable=False)
    is_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    completed_at: Mapped[datetime | None] = mapped_column()
    override_completed: Mapped[bool | None] = mapped_column(Boolean)
    override_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("family_members.id", ondelete="RESTRICT"))
    override_note: Mapped[str | None] = mapped_column(Text)
    in_scope_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    scope_dispute_opened_at: Mapped[datetime | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    step_completions: Mapped[list["TaskInstanceStepCompletion"]] = relationship(back_populates="task_instance", cascade="all, delete-orphan")

    @property
    def effective_completed(self) -> bool:
        if self.override_completed is not None:
            return self.override_completed
        return self.is_completed


class TaskInstanceStepCompletion(Base):
    __tablename__ = "task_instance_step_completions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_instance_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("task_instances.id", ondelete="CASCADE"), nullable=False)
    routine_step_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("routine_steps.id", ondelete="RESTRICT"), nullable=False)
    is_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    completed_at: Mapped[datetime | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    task_instance: Mapped["TaskInstance"] = relationship(back_populates="step_completions")


class DailyWin(Base):
    __tablename__ = "daily_wins"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("families.id", ondelete="CASCADE"), nullable=False)
    family_member_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("family_members.id", ondelete="CASCADE"), nullable=False)
    win_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_win: Mapped[bool] = mapped_column(Boolean, nullable=False)
    task_count: Mapped[int] = mapped_column(Integer, nullable=False)
    completed_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())


class AllowanceLedger(Base):
    __tablename__ = "allowance_ledger"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("families.id", ondelete="CASCADE"), nullable=False)
    family_member_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("family_members.id", ondelete="CASCADE"), nullable=False)
    entry_type: Mapped[str] = mapped_column(String(20), nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    week_start: Mapped[date | None] = mapped_column(Date)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

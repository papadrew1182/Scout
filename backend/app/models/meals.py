import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class MealPlan(Base):
    __tablename__ = "meal_plans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("families.id", ondelete="CASCADE"), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("family_members.id", ondelete="SET NULL"))
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    meals: Mapped[list["Meal"]] = relationship(back_populates="meal_plan")


class Meal(Base):
    __tablename__ = "meals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("families.id", ondelete="CASCADE"), nullable=False)
    meal_plan_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("meal_plans.id", ondelete="SET NULL"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("family_members.id", ondelete="SET NULL"))
    meal_date: Mapped[date] = mapped_column(Date, nullable=False)
    meal_type: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    is_base_cook: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    base_cook_yield_servings: Mapped[int | None] = mapped_column(Integer)
    base_cook_keeps_days: Mapped[int | None] = mapped_column(Integer)
    storage_notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    meal_plan: Mapped["MealPlan | None"] = relationship(back_populates="meals")


class DietaryPreference(Base):
    __tablename__ = "dietary_preferences"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_member_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("family_members.id", ondelete="CASCADE"), nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())


class WeeklyMealPlan(Base):
    __tablename__ = "weekly_meal_plans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("families.id", ondelete="CASCADE"), nullable=False)
    created_by_member_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("family_members.id", ondelete="CASCADE"), nullable=False)
    week_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="ai")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    title: Mapped[str | None] = mapped_column(Text)
    constraints_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    week_plan: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    prep_plan: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    grocery_plan: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    plan_summary: Mapped[str | None] = mapped_column(Text)
    approved_by_member_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("family_members.id", ondelete="SET NULL"))
    approved_at: Mapped[datetime | None] = mapped_column()
    archived_at: Mapped[datetime | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())


class MealReview(Base):
    __tablename__ = "meal_reviews"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("families.id", ondelete="CASCADE"), nullable=False)
    weekly_plan_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("weekly_meal_plans.id", ondelete="SET NULL"))
    reviewed_by_member_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("family_members.id", ondelete="CASCADE"), nullable=False)
    linked_meal_ref: Mapped[str | None] = mapped_column(Text)
    meal_title: Mapped[str] = mapped_column(Text, nullable=False)
    rating_overall: Mapped[int] = mapped_column(Integer, nullable=False)
    kid_acceptance: Mapped[int | None] = mapped_column(Integer)
    effort: Mapped[int | None] = mapped_column(Integer)
    cleanup: Mapped[int | None] = mapped_column(Integer)
    leftovers: Mapped[str | None] = mapped_column(String(10))
    repeat_decision: Mapped[str] = mapped_column(String(10), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

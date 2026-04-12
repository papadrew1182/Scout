import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


# --- MealPlan ---

class MealPlanCreate(BaseModel):
    week_start: date
    created_by: uuid.UUID | None = None
    notes: str | None = None


class MealPlanUpdate(BaseModel):
    notes: str | None = None


class MealPlanRead(BaseModel):
    id: uuid.UUID
    family_id: uuid.UUID
    created_by: uuid.UUID | None
    week_start: date
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Meal ---

class MealCreate(BaseModel):
    meal_plan_id: uuid.UUID | None = None
    created_by: uuid.UUID | None = None
    meal_date: date
    meal_type: str
    title: str
    description: str | None = None
    notes: str | None = None


class MealUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    notes: str | None = None
    meal_plan_id: uuid.UUID | None = None


class MealRead(BaseModel):
    id: uuid.UUID
    family_id: uuid.UUID
    meal_plan_id: uuid.UUID | None
    created_by: uuid.UUID | None
    meal_date: date
    meal_type: str
    title: str
    description: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- DietaryPreference ---

class DietaryPreferenceCreate(BaseModel):
    label: str
    kind: str
    notes: str | None = None


class DietaryPreferenceRead(BaseModel):
    id: uuid.UUID
    family_member_id: uuid.UUID
    label: str
    kind: str
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Weekly meal plans (AI-generated, persisted)
# ---------------------------------------------------------------------------
# week_plan, prep_plan, grocery_plan are validated structured JSON. The contract
# is enforced in weekly_meal_plan_service.validate_plan_payload — not via nested
# Pydantic models — because the AI output is variable shape and we prefer one
# crisp validator over scattered schema classes.


class WeeklyMealPlanGenerateRequest(BaseModel):
    member_id: uuid.UUID
    week_start_date: date
    constraints: dict[str, Any] | None = None
    answers: dict[str, Any] | None = None


class ClarifyingQuestion(BaseModel):
    key: str
    question: str
    hint: str | None = None


class WeeklyMealPlanGenerateResponse(BaseModel):
    status: str = Field(pattern="^(needs_clarification|ready)$")
    questions: list[ClarifyingQuestion] | None = None
    plan_id: uuid.UUID | None = None
    summary: str | None = None


class WeeklyMealPlanRead(BaseModel):
    id: uuid.UUID
    family_id: uuid.UUID
    created_by_member_id: uuid.UUID
    week_start_date: date
    source: str
    status: str
    title: str | None
    constraints_snapshot: dict[str, Any]
    week_plan: dict[str, Any]
    prep_plan: dict[str, Any]
    grocery_plan: dict[str, Any]
    plan_summary: str | None
    approved_by_member_id: uuid.UUID | None
    approved_at: datetime | None
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WeeklyMealPlanUpdate(BaseModel):
    title: str | None = None
    week_plan: dict[str, Any] | None = None
    prep_plan: dict[str, Any] | None = None
    grocery_plan: dict[str, Any] | None = None
    plan_summary: str | None = None


class WeeklyMealPlanApprove(BaseModel):
    member_id: uuid.UUID


class WeeklyMealPlanRegenerateDay(BaseModel):
    member_id: uuid.UUID
    day: str
    meal_types: list[str] | None = None


# ---------------------------------------------------------------------------
# Meal reviews
# ---------------------------------------------------------------------------


class MealReviewCreate(BaseModel):
    member_id: uuid.UUID
    weekly_plan_id: uuid.UUID | None = None
    linked_meal_ref: str | None = None
    meal_title: str = Field(min_length=1)
    rating_overall: int = Field(ge=1, le=5)
    kid_acceptance: int | None = Field(default=None, ge=1, le=5)
    effort: int | None = Field(default=None, ge=1, le=5)
    cleanup: int | None = Field(default=None, ge=1, le=5)
    leftovers: str | None = Field(default=None, pattern="^(none|some|plenty)$")
    repeat_decision: str = Field(pattern="^(repeat|tweak|retire)$")
    notes: str | None = None


class MealReviewRead(BaseModel):
    id: uuid.UUID
    family_id: uuid.UUID
    weekly_plan_id: uuid.UUID | None
    reviewed_by_member_id: uuid.UUID
    linked_meal_ref: str | None
    meal_title: str
    rating_overall: int
    kid_acceptance: int | None
    effort: int | None
    cleanup: int | None
    leftovers: str | None
    repeat_decision: str
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MealReviewSummary(BaseModel):
    total_reviews: int
    high_rated: list[str]
    retired: list[str]
    low_kid_acceptance: list[str]
    good_leftovers: list[str]
    low_effort_favorites: list[str]

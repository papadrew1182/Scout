import uuid
from datetime import date, datetime

from pydantic import BaseModel


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

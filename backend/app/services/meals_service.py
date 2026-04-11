"""Meals service: meal plans, meals, dietary preferences.

No grocery, no nutrition tracking, no recipe relationships.
"""

import uuid
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.meals import DietaryPreference, Meal, MealPlan
from app.schemas.meals import (
    DietaryPreferenceCreate,
    MealCreate,
    MealPlanCreate,
    MealPlanUpdate,
    MealUpdate,
)
from app.services.tenant_guard import require_family, require_member_in_family


# ---------------------------------------------------------------------------
# Meal Plans
# ---------------------------------------------------------------------------

def list_meal_plans(db: Session, family_id: uuid.UUID) -> list[MealPlan]:
    require_family(db, family_id)
    stmt = (
        select(MealPlan)
        .where(MealPlan.family_id == family_id)
        .order_by(MealPlan.week_start.desc())
    )
    return list(db.scalars(stmt).all())


def get_meal_plan(db: Session, family_id: uuid.UUID, plan_id: uuid.UUID) -> MealPlan:
    plan = db.get(MealPlan, plan_id)
    if not plan or plan.family_id != family_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meal plan not found")
    return plan


def create_meal_plan(db: Session, family_id: uuid.UUID, payload: MealPlanCreate) -> MealPlan:
    require_family(db, family_id)
    if payload.created_by:
        require_member_in_family(db, family_id, payload.created_by)
    if payload.week_start.isoweekday() != 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="week_start must be a Monday",
        )

    plan = MealPlan(
        family_id=family_id,
        created_by=payload.created_by,
        week_start=payload.week_start,
        notes=payload.notes,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def update_meal_plan(
    db: Session,
    family_id: uuid.UUID,
    plan_id: uuid.UUID,
    payload: MealPlanUpdate,
) -> MealPlan:
    plan = get_meal_plan(db, family_id, plan_id)
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(plan, key, value)
    db.commit()
    db.refresh(plan)
    return plan


def delete_meal_plan(db: Session, family_id: uuid.UUID, plan_id: uuid.UUID) -> None:
    plan = get_meal_plan(db, family_id, plan_id)
    db.delete(plan)
    db.commit()


# ---------------------------------------------------------------------------
# Meals
# ---------------------------------------------------------------------------

def list_meals(
    db: Session,
    family_id: uuid.UUID,
    meal_date: date | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    meal_plan_id: uuid.UUID | None = None,
) -> list[Meal]:
    require_family(db, family_id)
    stmt = select(Meal).where(Meal.family_id == family_id)
    if meal_date:
        stmt = stmt.where(Meal.meal_date == meal_date)
    if start_date:
        stmt = stmt.where(Meal.meal_date >= start_date)
    if end_date:
        stmt = stmt.where(Meal.meal_date <= end_date)
    if meal_plan_id:
        stmt = stmt.where(Meal.meal_plan_id == meal_plan_id)
    stmt = stmt.order_by(Meal.meal_date, Meal.meal_type)
    return list(db.scalars(stmt).all())


def get_meal(db: Session, family_id: uuid.UUID, meal_id: uuid.UUID) -> Meal:
    meal = db.get(Meal, meal_id)
    if not meal or meal.family_id != family_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meal not found")
    return meal


def create_meal(db: Session, family_id: uuid.UUID, payload: MealCreate) -> Meal:
    require_family(db, family_id)
    if payload.created_by:
        require_member_in_family(db, family_id, payload.created_by)
    if payload.meal_plan_id:
        plan = db.get(MealPlan, payload.meal_plan_id)
        if not plan or plan.family_id != family_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="meal_plan_id does not belong to this family",
            )

    meal = Meal(
        family_id=family_id,
        meal_plan_id=payload.meal_plan_id,
        created_by=payload.created_by,
        meal_date=payload.meal_date,
        meal_type=payload.meal_type,
        title=payload.title,
        description=payload.description,
        notes=payload.notes,
    )
    db.add(meal)
    db.commit()
    db.refresh(meal)
    return meal


def update_meal(
    db: Session,
    family_id: uuid.UUID,
    meal_id: uuid.UUID,
    payload: MealUpdate,
) -> Meal:
    meal = get_meal(db, family_id, meal_id)
    data = payload.model_dump(exclude_unset=True)

    if "meal_plan_id" in data and data["meal_plan_id"] is not None:
        plan = db.get(MealPlan, data["meal_plan_id"])
        if not plan or plan.family_id != family_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="meal_plan_id does not belong to this family",
            )

    for key, value in data.items():
        setattr(meal, key, value)
    db.commit()
    db.refresh(meal)
    return meal


def delete_meal(db: Session, family_id: uuid.UUID, meal_id: uuid.UUID) -> None:
    meal = get_meal(db, family_id, meal_id)
    db.delete(meal)
    db.commit()


# ---------------------------------------------------------------------------
# Dietary Preferences
# ---------------------------------------------------------------------------

def list_dietary_preferences(
    db: Session, family_id: uuid.UUID, member_id: uuid.UUID
) -> list[DietaryPreference]:
    require_member_in_family(db, family_id, member_id)
    stmt = select(DietaryPreference).where(DietaryPreference.family_member_id == member_id)
    return list(db.scalars(stmt).all())


def add_dietary_preference(
    db: Session,
    family_id: uuid.UUID,
    member_id: uuid.UUID,
    payload: DietaryPreferenceCreate,
) -> DietaryPreference:
    require_member_in_family(db, family_id, member_id)
    pref = DietaryPreference(
        family_member_id=member_id,
        label=payload.label,
        kind=payload.kind,
        notes=payload.notes,
    )
    db.add(pref)
    db.commit()
    db.refresh(pref)
    return pref


def remove_dietary_preference(
    db: Session,
    family_id: uuid.UUID,
    member_id: uuid.UUID,
    preference_id: uuid.UUID,
) -> None:
    require_member_in_family(db, family_id, member_id)
    pref = db.get(DietaryPreference, preference_id)
    if not pref or pref.family_member_id != member_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dietary preference not found")
    db.delete(pref)
    db.commit()

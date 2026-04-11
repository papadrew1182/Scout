import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.meals import (
    DietaryPreferenceCreate,
    DietaryPreferenceRead,
    MealCreate,
    MealPlanCreate,
    MealPlanRead,
    MealPlanUpdate,
    MealRead,
    MealUpdate,
)
from app.services import meals_service

router = APIRouter(prefix="/families/{family_id}", tags=["meals"])


# --- Meal Plans ---

@router.get("/meal-plans", response_model=list[MealPlanRead])
def list_meal_plans(family_id: uuid.UUID, db: Session = Depends(get_db)):
    return meals_service.list_meal_plans(db, family_id)


@router.post("/meal-plans", response_model=MealPlanRead, status_code=201)
def create_meal_plan(family_id: uuid.UUID, payload: MealPlanCreate, db: Session = Depends(get_db)):
    return meals_service.create_meal_plan(db, family_id, payload)


@router.get("/meal-plans/{plan_id}", response_model=MealPlanRead)
def get_meal_plan(family_id: uuid.UUID, plan_id: uuid.UUID, db: Session = Depends(get_db)):
    return meals_service.get_meal_plan(db, family_id, plan_id)


@router.patch("/meal-plans/{plan_id}", response_model=MealPlanRead)
def update_meal_plan(
    family_id: uuid.UUID,
    plan_id: uuid.UUID,
    payload: MealPlanUpdate,
    db: Session = Depends(get_db),
):
    return meals_service.update_meal_plan(db, family_id, plan_id, payload)


@router.delete("/meal-plans/{plan_id}", status_code=204)
def delete_meal_plan(family_id: uuid.UUID, plan_id: uuid.UUID, db: Session = Depends(get_db)):
    meals_service.delete_meal_plan(db, family_id, plan_id)


# --- Meals ---

@router.get("/meals", response_model=list[MealRead])
def list_meals(
    family_id: uuid.UUID,
    meal_date: date | None = Query(None),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    meal_plan_id: uuid.UUID | None = Query(None),
    db: Session = Depends(get_db),
):
    return meals_service.list_meals(db, family_id, meal_date, start_date, end_date, meal_plan_id)


@router.post("/meals", response_model=MealRead, status_code=201)
def create_meal(family_id: uuid.UUID, payload: MealCreate, db: Session = Depends(get_db)):
    return meals_service.create_meal(db, family_id, payload)


@router.get("/meals/{meal_id}", response_model=MealRead)
def get_meal(family_id: uuid.UUID, meal_id: uuid.UUID, db: Session = Depends(get_db)):
    return meals_service.get_meal(db, family_id, meal_id)


@router.patch("/meals/{meal_id}", response_model=MealRead)
def update_meal(
    family_id: uuid.UUID,
    meal_id: uuid.UUID,
    payload: MealUpdate,
    db: Session = Depends(get_db),
):
    return meals_service.update_meal(db, family_id, meal_id, payload)


@router.delete("/meals/{meal_id}", status_code=204)
def delete_meal(family_id: uuid.UUID, meal_id: uuid.UUID, db: Session = Depends(get_db)):
    meals_service.delete_meal(db, family_id, meal_id)


# --- Dietary Preferences ---

@router.get(
    "/members/{member_id}/dietary-preferences",
    response_model=list[DietaryPreferenceRead],
)
def list_dietary_preferences(
    family_id: uuid.UUID, member_id: uuid.UUID, db: Session = Depends(get_db)
):
    return meals_service.list_dietary_preferences(db, family_id, member_id)


@router.post(
    "/members/{member_id}/dietary-preferences",
    response_model=DietaryPreferenceRead,
    status_code=201,
)
def add_dietary_preference(
    family_id: uuid.UUID,
    member_id: uuid.UUID,
    payload: DietaryPreferenceCreate,
    db: Session = Depends(get_db),
):
    return meals_service.add_dietary_preference(db, family_id, member_id, payload)


@router.delete(
    "/members/{member_id}/dietary-preferences/{preference_id}",
    status_code=204,
)
def remove_dietary_preference(
    family_id: uuid.UUID,
    member_id: uuid.UUID,
    preference_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    meals_service.remove_dietary_preference(db, family_id, member_id, preference_id)

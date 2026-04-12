import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth import Actor, get_current_actor
from app.database import get_db
from app.schemas.grocery import GroceryItemRead
from app.schemas.meals import (
    DietaryPreferenceCreate,
    DietaryPreferenceRead,
    MealCreate,
    MealPlanCreate,
    MealPlanRead,
    MealPlanUpdate,
    MealRead,
    MealReviewCreate,
    MealReviewRead,
    MealReviewSummary,
    MealUpdate,
    WeeklyMealPlanGenerateRequest,
    WeeklyMealPlanGenerateResponse,
    WeeklyMealPlanRead,
    WeeklyMealPlanRegenerateDay,
    WeeklyMealPlanUpdate,
)
from app.services import meals_service, weekly_meal_plan_service

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


# ---------------------------------------------------------------------------
# Weekly meal plans — MUST be registered before /meals/{meal_id} routes
# ---------------------------------------------------------------------------


@router.post("/meals/weekly/generate", response_model=WeeklyMealPlanGenerateResponse)
def generate_weekly_plan(
    family_id: uuid.UUID,
    payload: WeeklyMealPlanGenerateRequest,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_family(family_id)
    result = weekly_meal_plan_service.generate_weekly_meal_plan(
        db,
        family_id,
        actor.member_id,
        week_start_date=payload.week_start_date,
        extra_constraints=payload.constraints,
        answers=payload.answers,
    )
    if result["status"] == "needs_clarification":
        return WeeklyMealPlanGenerateResponse(
            status="needs_clarification", questions=result["questions"]
        )
    return WeeklyMealPlanGenerateResponse(
        status="ready", plan_id=result["plan_id"], summary=result.get("summary")
    )


@router.get("/meals/weekly", response_model=list[WeeklyMealPlanRead])
def list_weekly_plans(
    family_id: uuid.UUID,
    include_archived: bool = Query(False),
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_family(family_id)
    return weekly_meal_plan_service.list_weekly_meal_plans(
        db, family_id, include_archived, actor_member_id=actor.member_id,
    )


@router.get("/meals/weekly/current", response_model=WeeklyMealPlanRead)
def get_current_weekly_plan(
    family_id: uuid.UUID,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_family(family_id)
    plan = weekly_meal_plan_service.get_current_weekly_meal_plan(
        db, family_id, actor_member_id=actor.member_id,
    )
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No weekly meal plan found")
    return plan


@router.get("/meals/weekly/{plan_id}", response_model=WeeklyMealPlanRead)
def get_weekly_plan(
    family_id: uuid.UUID,
    plan_id: uuid.UUID,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_family(family_id)
    return weekly_meal_plan_service.get_weekly_meal_plan(
        db, family_id, plan_id, actor_member_id=actor.member_id,
    )


@router.patch("/meals/weekly/{plan_id}", response_model=WeeklyMealPlanRead)
def update_weekly_plan(
    family_id: uuid.UUID,
    plan_id: uuid.UUID,
    payload: WeeklyMealPlanUpdate = ...,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_family(family_id)
    return weekly_meal_plan_service.update_weekly_meal_plan(
        db, family_id, actor.member_id, plan_id, payload
    )


@router.post("/meals/weekly/{plan_id}/approve", response_model=WeeklyMealPlanRead)
def approve_weekly_plan(
    family_id: uuid.UUID,
    plan_id: uuid.UUID,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_family(family_id)
    return weekly_meal_plan_service.approve_weekly_meal_plan(
        db, family_id, actor.member_id, plan_id
    )


@router.post("/meals/weekly/{plan_id}/archive", response_model=WeeklyMealPlanRead)
def archive_weekly_plan(
    family_id: uuid.UUID,
    plan_id: uuid.UUID,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_family(family_id)
    return weekly_meal_plan_service.archive_weekly_meal_plan(
        db, family_id, actor.member_id, plan_id
    )


@router.post("/meals/weekly/{plan_id}/regenerate-day", response_model=WeeklyMealPlanRead)
def regenerate_weekly_plan_day(
    family_id: uuid.UUID,
    plan_id: uuid.UUID,
    payload: WeeklyMealPlanRegenerateDay,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_family(family_id)
    return weekly_meal_plan_service.regenerate_day(
        db,
        family_id,
        actor.member_id,
        plan_id,
        day=payload.day,
        meal_types=payload.meal_types,
    )


@router.get(
    "/meals/weekly/{plan_id}/groceries",
    response_model=list[GroceryItemRead],
)
def list_weekly_plan_groceries(
    family_id: uuid.UUID, plan_id: uuid.UUID, db: Session = Depends(get_db)
):
    return weekly_meal_plan_service.list_plan_grocery_items(db, family_id, plan_id)


# ---------------------------------------------------------------------------
# Meal reviews
# ---------------------------------------------------------------------------


@router.post("/meals/reviews", response_model=MealReviewRead, status_code=201)
def create_meal_review(
    family_id: uuid.UUID,
    payload: MealReviewCreate,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_family(family_id)
    # Override member_id with authenticated actor
    payload.member_id = actor.member_id
    return weekly_meal_plan_service.create_meal_review(db, family_id, payload)


@router.get("/meals/reviews", response_model=list[MealReviewRead])
def list_meal_reviews(
    family_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return weekly_meal_plan_service.list_meal_reviews(db, family_id, limit)


@router.get("/meals/reviews/summary", response_model=MealReviewSummary)
def get_meal_review_summary(
    family_id: uuid.UUID, db: Session = Depends(get_db)
):
    return weekly_meal_plan_service.get_meal_review_summary(db, family_id)


# --- Individual Meals (catch-all {meal_id} — MUST come after /meals/weekly and /meals/reviews) ---

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

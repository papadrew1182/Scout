"""Tests for meals_service.

Covers:
- meal plan create with Monday validation
- meal create (with and without parent plan)
- list meals by date / range
- one-meal-per-type-per-day enforcement
- dietary preferences CRUD
- tenant isolation
"""

import uuid
from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.foundation import Family
from app.schemas.meals import (
    DietaryPreferenceCreate,
    MealCreate,
    MealPlanCreate,
    MealPlanUpdate,
    MealUpdate,
)
from app.services.meals_service import (
    add_dietary_preference,
    create_meal,
    create_meal_plan,
    delete_meal,
    get_meal,
    get_meal_plan,
    list_dietary_preferences,
    list_meal_plans,
    list_meals,
    remove_dietary_preference,
    update_meal,
    update_meal_plan,
)


class TestMealPlan:
    def test_create_meal_plan_on_monday(self, db: Session, family, adults):
        plan = create_meal_plan(
            db, family.id,
            MealPlanCreate(
                week_start=date(2026, 4, 6),  # Monday
                created_by=adults["robert"].id,
                notes="Test plan",
            ),
        )
        assert plan.id is not None
        assert plan.week_start == date(2026, 4, 6)
        assert plan.notes == "Test plan"

    def test_create_meal_plan_non_monday_rejected(self, db: Session, family):
        with pytest.raises(HTTPException) as exc:
            create_meal_plan(
                db, family.id,
                MealPlanCreate(week_start=date(2026, 4, 7)),  # Tuesday
            )
        assert exc.value.status_code == 400

    def test_duplicate_week_rejected(self, db: Session, family):
        create_meal_plan(db, family.id, MealPlanCreate(week_start=date(2026, 4, 6)))
        with pytest.raises(IntegrityError):
            create_meal_plan(db, family.id, MealPlanCreate(week_start=date(2026, 4, 6)))

    def test_update_meal_plan_notes(self, db: Session, family):
        plan = create_meal_plan(db, family.id, MealPlanCreate(week_start=date(2026, 4, 6)))
        updated = update_meal_plan(
            db, family.id, plan.id, MealPlanUpdate(notes="Updated notes")
        )
        assert updated.notes == "Updated notes"


class TestMeals:
    def test_create_meal_without_plan(self, db: Session, family):
        meal = create_meal(
            db, family.id,
            MealCreate(
                meal_date=date(2026, 4, 9),
                meal_type="dinner",
                title="Pizza",
            ),
        )
        assert meal.id is not None
        assert meal.meal_plan_id is None
        assert meal.title == "Pizza"

    def test_create_meal_with_plan(self, db: Session, family):
        plan = create_meal_plan(db, family.id, MealPlanCreate(week_start=date(2026, 4, 6)))
        meal = create_meal(
            db, family.id,
            MealCreate(
                meal_plan_id=plan.id,
                meal_date=date(2026, 4, 9),
                meal_type="lunch",
                title="Sandwich",
            ),
        )
        assert meal.meal_plan_id == plan.id

    def test_invalid_meal_type_rejected_at_db(self, db: Session, family):
        with pytest.raises(IntegrityError):
            create_meal(
                db, family.id,
                MealCreate(
                    meal_date=date(2026, 4, 9),
                    meal_type="midnight_snack",
                    title="Cookies",
                ),
            )

    def test_duplicate_meal_type_per_day_rejected(self, db: Session, family):
        create_meal(
            db, family.id,
            MealCreate(meal_date=date(2026, 4, 9), meal_type="breakfast", title="Pancakes"),
        )
        with pytest.raises(IntegrityError):
            create_meal(
                db, family.id,
                MealCreate(meal_date=date(2026, 4, 9), meal_type="breakfast", title="Eggs"),
            )

    def test_list_meals_by_date(self, db: Session, family):
        create_meal(db, family.id, MealCreate(meal_date=date(2026, 4, 9), meal_type="breakfast", title="A"))
        create_meal(db, family.id, MealCreate(meal_date=date(2026, 4, 9), meal_type="lunch", title="B"))
        create_meal(db, family.id, MealCreate(meal_date=date(2026, 4, 10), meal_type="breakfast", title="C"))

        results = list_meals(db, family.id, meal_date=date(2026, 4, 9))
        assert len(results) == 2
        titles = {m.title for m in results}
        assert titles == {"A", "B"}

    def test_list_meals_by_range(self, db: Session, family):
        for d in [4, 6, 8, 10]:
            create_meal(
                db, family.id,
                MealCreate(meal_date=date(2026, 4, d), meal_type="dinner", title=f"D{d}"),
            )
        results = list_meals(
            db, family.id, start_date=date(2026, 4, 6), end_date=date(2026, 4, 9)
        )
        titles = {m.title for m in results}
        assert titles == {"D6", "D8"}

    def test_update_meal(self, db: Session, family):
        meal = create_meal(
            db, family.id,
            MealCreate(meal_date=date(2026, 4, 9), meal_type="dinner", title="Original"),
        )
        updated = update_meal(db, family.id, meal.id, MealUpdate(title="Renamed"))
        assert updated.title == "Renamed"

    def test_delete_meal(self, db: Session, family):
        meal = create_meal(
            db, family.id,
            MealCreate(meal_date=date(2026, 4, 9), meal_type="dinner", title="X"),
        )
        delete_meal(db, family.id, meal.id)
        with pytest.raises(HTTPException) as exc:
            get_meal(db, family.id, meal.id)
        assert exc.value.status_code == 404


class TestDietaryPreferences:
    def test_add_and_list(self, db: Session, family, children):
        river = children["river"]
        add_dietary_preference(
            db, family.id, river.id,
            DietaryPreferenceCreate(label="tree_nuts", kind="allergy", notes="EpiPen at school"),
        )
        prefs = list_dietary_preferences(db, family.id, river.id)
        assert len(prefs) == 1
        assert prefs[0].label == "tree_nuts"
        assert prefs[0].kind == "allergy"

    def test_invalid_kind_rejected(self, db: Session, family, children):
        with pytest.raises(IntegrityError):
            add_dietary_preference(
                db, family.id, children["river"].id,
                DietaryPreferenceCreate(label="anything", kind="dislike"),
            )

    def test_remove_preference(self, db: Session, family, children):
        sadie = children["sadie"]
        pref = add_dietary_preference(
            db, family.id, sadie.id,
            DietaryPreferenceCreate(label="cilantro", kind="preference"),
        )
        remove_dietary_preference(db, family.id, sadie.id, pref.id)
        prefs = list_dietary_preferences(db, family.id, sadie.id)
        assert len(prefs) == 0


class TestTenantIsolation:
    def test_get_meal_from_wrong_family_404(self, db: Session, family):
        other = Family(name="Other", timezone="America/New_York")
        db.add(other)
        db.flush()
        meal = create_meal(
            db, other.id,
            MealCreate(meal_date=date(2026, 4, 9), meal_type="dinner", title="Theirs"),
        )
        with pytest.raises(HTTPException) as exc:
            get_meal(db, family.id, meal.id)
        assert exc.value.status_code == 404

    def test_list_meals_only_returns_own_family(self, db: Session, family):
        other = Family(name="Other", timezone="America/New_York")
        db.add(other)
        db.flush()
        create_meal(db, family.id, MealCreate(meal_date=date(2026, 4, 9), meal_type="dinner", title="Mine"))
        create_meal(db, other.id, MealCreate(meal_date=date(2026, 4, 9), meal_type="dinner", title="Theirs"))

        results = list_meals(db, family.id, meal_date=date(2026, 4, 9))
        titles = {m.title for m in results}
        assert "Mine" in titles
        assert "Theirs" not in titles

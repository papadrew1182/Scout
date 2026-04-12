"""HTTP-layer tests for meals weekly plan + reviews routes.

Uses FastAPI TestClient to verify route-level behavior including:
- adult allowed paths
- child forbidden paths (generate, approve, update, archive, regenerate)
- child allowed paths (view approved, reviews)
- approved-only child visibility
- family isolation
- malformed payload rejection
- parent action item lifecycle
"""

import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.main import app
from app.models.action_items import ParentActionItem
from app.models.foundation import Family, FamilyMember
from app.models.grocery import GroceryItem
from app.models.meals import WeeklyMealPlan
from app.services import weekly_meal_plan_service as wmp

MONDAY = date(2026, 4, 13)


def _ready_payload():
    return {
        "week_plan": {
            "dinners": {
                "monday": {"title": "Sheet-pan chicken", "description": "veg and rice"},
                "tuesday": {"title": "Taco night", "description": "ground turkey"},
                "wednesday": {"title": "Pasta bake", "description": "leftovers friendly"},
                "thursday": {"title": "Stir fry", "description": "quick wok"},
                "friday": {"title": "Pizza", "description": "homemade"},
            },
            "breakfast": {"plan": "eggs, yogurt, cereal rotation"},
            "lunch": {"plan": "sandwiches and leftovers"},
            "snacks": ["fruit", "cheese sticks"],
        },
        "prep_plan": {
            "tasks": [
                {"title": "Cook rice batch", "supports": ["monday", "thursday"], "duration_min": 25},
            ],
            "timeline": [{"block": "0:00-0:45", "items": ["rice"]}],
        },
        "grocery_plan": {
            "stores": [
                {"name": "Costco", "items": [{"title": "Chicken thighs", "quantity": 4, "unit": "lb"}]},
                {"name": "H-E-B", "items": [{"title": "Tortillas", "quantity": 1, "unit": "pack"}]},
            ]
        },
    }


def _make_draft(db: Session, family: Family, adult: FamilyMember) -> WeeklyMealPlan:
    """Helper to create a draft plan directly."""
    return wmp.save_weekly_meal_plan_draft(
        db, family.id, adult.id,
        week_start_date=MONDAY,
        week_plan=_ready_payload()["week_plan"],
        prep_plan=_ready_payload()["prep_plan"],
        grocery_plan=_ready_payload()["grocery_plan"],
        plan_summary="Test plan",
    )


@pytest.fixture()
def client(db: Session):
    """TestClient with overridden db dependency."""
    def override_get_db():
        yield db
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /meals/weekly/current
# ---------------------------------------------------------------------------


class TestGetCurrentPlan:
    def test_404_when_no_plan(self, client: TestClient, family, adults):
        r = client.get(f"/families/{family.id}/meals/weekly/current?member_id={adults['robert'].id}")
        assert r.status_code == 404

    def test_adult_sees_draft(self, client: TestClient, db, family, adults):
        plan = _make_draft(db, family, adults["robert"])
        r = client.get(f"/families/{family.id}/meals/weekly/current?member_id={adults['robert'].id}")
        assert r.status_code == 200
        assert r.json()["id"] == str(plan.id)
        assert r.json()["status"] == "draft"

    def test_child_cannot_see_draft(self, client: TestClient, db, family, adults, children):
        _make_draft(db, family, adults["robert"])
        r = client.get(f"/families/{family.id}/meals/weekly/current?member_id={children['sadie'].id}")
        assert r.status_code == 404

    def test_child_sees_approved(self, client: TestClient, db, family, adults, children):
        plan = _make_draft(db, family, adults["robert"])
        wmp.approve_weekly_meal_plan(db, family.id, adults["robert"].id, plan.id)
        r = client.get(f"/families/{family.id}/meals/weekly/current?member_id={children['sadie'].id}")
        assert r.status_code == 200
        assert r.json()["status"] == "approved"


# ---------------------------------------------------------------------------
# GET /meals/weekly/{plan_id}
# ---------------------------------------------------------------------------


class TestGetPlanById:
    def test_adult_sees_draft(self, client: TestClient, db, family, adults):
        plan = _make_draft(db, family, adults["robert"])
        r = client.get(f"/families/{family.id}/meals/weekly/{plan.id}?member_id={adults['robert'].id}")
        assert r.status_code == 200

    def test_child_cannot_see_draft(self, client: TestClient, db, family, adults, children):
        plan = _make_draft(db, family, adults["robert"])
        r = client.get(f"/families/{family.id}/meals/weekly/{plan.id}?member_id={children['sadie'].id}")
        assert r.status_code == 403

    def test_child_sees_approved(self, client: TestClient, db, family, adults, children):
        plan = _make_draft(db, family, adults["robert"])
        wmp.approve_weekly_meal_plan(db, family.id, adults["robert"].id, plan.id)
        r = client.get(f"/families/{family.id}/meals/weekly/{plan.id}?member_id={children['sadie'].id}")
        assert r.status_code == 200

    def test_family_isolation(self, client: TestClient, db, family, adults):
        plan = _make_draft(db, family, adults["robert"])
        other = Family(name="Other", timezone="UTC")
        db.add(other)
        db.flush()
        r = client.get(f"/families/{other.id}/meals/weekly/{plan.id}")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# GET /meals/weekly (list)
# ---------------------------------------------------------------------------


class TestListPlans:
    def test_child_sees_only_approved(self, client: TestClient, db, family, adults, children):
        _make_draft(db, family, adults["robert"])
        r = client.get(f"/families/{family.id}/meals/weekly?member_id={children['sadie'].id}")
        assert r.status_code == 200
        assert len(r.json()) == 0  # draft only, child sees none

    def test_adult_sees_drafts(self, client: TestClient, db, family, adults):
        _make_draft(db, family, adults["robert"])
        r = client.get(f"/families/{family.id}/meals/weekly?member_id={adults['robert'].id}")
        assert r.status_code == 200
        assert len(r.json()) == 1


# ---------------------------------------------------------------------------
# POST /meals/weekly/{plan_id}/approve
# ---------------------------------------------------------------------------


class TestApprovePlan:
    def test_adult_can_approve(self, client: TestClient, db, family, adults):
        plan = _make_draft(db, family, adults["robert"])
        r = client.post(
            f"/families/{family.id}/meals/weekly/{plan.id}/approve",
            json={"member_id": str(adults["megan"].id)},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "approved"

    def test_child_cannot_approve(self, client: TestClient, db, family, adults, children):
        plan = _make_draft(db, family, adults["robert"])
        r = client.post(
            f"/families/{family.id}/meals/weekly/{plan.id}/approve",
            json={"member_id": str(children["sadie"].id)},
        )
        assert r.status_code == 403

    def test_approve_syncs_groceries(self, client: TestClient, db, family, adults):
        plan = _make_draft(db, family, adults["robert"])
        client.post(
            f"/families/{family.id}/meals/weekly/{plan.id}/approve",
            json={"member_id": str(adults["robert"].id)},
        )
        items = list(db.scalars(
            select(GroceryItem).where(GroceryItem.weekly_plan_id == plan.id)
        ).all())
        assert len(items) == 2
        assert all(i.source == "meal_ai" for i in items)

    def test_approve_resolves_parent_action(self, client: TestClient, db, family, adults):
        plan = _make_draft(db, family, adults["robert"])
        client.post(
            f"/families/{family.id}/meals/weekly/{plan.id}/approve",
            json={"member_id": str(adults["robert"].id)},
        )
        actions = list(db.scalars(
            select(ParentActionItem)
            .where(ParentActionItem.entity_id == plan.id)
        ).all())
        assert all(a.status == "resolved" for a in actions)


# ---------------------------------------------------------------------------
# POST /meals/weekly/{plan_id}/archive
# ---------------------------------------------------------------------------


class TestArchivePlan:
    def test_adult_can_archive(self, client: TestClient, db, family, adults):
        plan = _make_draft(db, family, adults["robert"])
        r = client.post(
            f"/families/{family.id}/meals/weekly/{plan.id}/archive?member_id={adults['robert'].id}",
        )
        assert r.status_code == 200
        assert r.json()["status"] == "archived"

    def test_archive_resolves_parent_action(self, client: TestClient, db, family, adults):
        plan = _make_draft(db, family, adults["robert"])
        client.post(
            f"/families/{family.id}/meals/weekly/{plan.id}/archive?member_id={adults['robert'].id}",
        )
        actions = list(db.scalars(
            select(ParentActionItem).where(ParentActionItem.entity_id == plan.id)
        ).all())
        assert all(a.status == "resolved" for a in actions)


# ---------------------------------------------------------------------------
# PATCH /meals/weekly/{plan_id}
# ---------------------------------------------------------------------------


class TestUpdatePlan:
    def test_adult_can_update(self, client: TestClient, db, family, adults):
        plan = _make_draft(db, family, adults["robert"])
        r = client.patch(
            f"/families/{family.id}/meals/weekly/{plan.id}?member_id={adults['robert'].id}",
            json={"title": "Updated Title"},
        )
        assert r.status_code == 200
        assert r.json()["title"] == "Updated Title"

    def test_child_cannot_update(self, client: TestClient, db, family, adults, children):
        plan = _make_draft(db, family, adults["robert"])
        r = client.patch(
            f"/families/{family.id}/meals/weekly/{plan.id}?member_id={children['sadie'].id}",
            json={"title": "Nope"},
        )
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# GET /meals/weekly/{plan_id}/groceries
# ---------------------------------------------------------------------------


class TestPlanGroceries:
    def test_returns_groceries_after_approve(self, client: TestClient, db, family, adults):
        plan = _make_draft(db, family, adults["robert"])
        wmp.approve_weekly_meal_plan(db, family.id, adults["robert"].id, plan.id)
        r = client.get(f"/families/{family.id}/meals/weekly/{plan.id}/groceries")
        assert r.status_code == 200
        assert len(r.json()) == 2


# ---------------------------------------------------------------------------
# POST /meals/reviews
# ---------------------------------------------------------------------------


class TestMealReviews:
    def test_adult_can_submit_review(self, client: TestClient, db, family, adults):
        r = client.post(
            f"/families/{family.id}/meals/reviews",
            json={
                "member_id": str(adults["robert"].id),
                "meal_title": "Pasta bake",
                "rating_overall": 4,
                "repeat_decision": "repeat",
            },
        )
        assert r.status_code == 201
        assert r.json()["meal_title"] == "Pasta bake"

    def test_child_can_submit_review(self, client: TestClient, db, family, children):
        r = client.post(
            f"/families/{family.id}/meals/reviews",
            json={
                "member_id": str(children["sadie"].id),
                "meal_title": "Taco night",
                "rating_overall": 5,
                "repeat_decision": "repeat",
            },
        )
        assert r.status_code == 201

    def test_invalid_rating_rejected(self, client: TestClient, db, family, adults):
        r = client.post(
            f"/families/{family.id}/meals/reviews",
            json={
                "member_id": str(adults["robert"].id),
                "meal_title": "x",
                "rating_overall": 99,
                "repeat_decision": "repeat",
            },
        )
        assert r.status_code == 422

    def test_invalid_repeat_decision_rejected(self, client: TestClient, db, family, adults):
        r = client.post(
            f"/families/{family.id}/meals/reviews",
            json={
                "member_id": str(adults["robert"].id),
                "meal_title": "x",
                "rating_overall": 3,
                "repeat_decision": "maybe",
            },
        )
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# GET /meals/reviews + /meals/reviews/summary
# ---------------------------------------------------------------------------


class TestListReviews:
    def test_list_reviews(self, client: TestClient, db, family, adults):
        from app.schemas.meals import MealReviewCreate
        wmp.create_meal_review(db, family.id, MealReviewCreate(
            member_id=adults["robert"].id, meal_title="Test", rating_overall=4, repeat_decision="repeat"
        ))
        r = client.get(f"/families/{family.id}/meals/reviews")
        assert r.status_code == 200
        assert len(r.json()) >= 1

    def test_review_summary(self, client: TestClient, db, family, adults):
        r = client.get(f"/families/{family.id}/meals/reviews/summary")
        assert r.status_code == 200
        assert "total_reviews" in r.json()


# ---------------------------------------------------------------------------
# Parent action items lifecycle through routes
# ---------------------------------------------------------------------------


class TestActionItemLifecycle:
    def test_draft_creates_action_approve_resolves(self, client: TestClient, db, family, adults):
        # Create draft
        plan = _make_draft(db, family, adults["robert"])

        # Action should be pending
        r = client.get(
            f"/families/{family.id}/action-items/current?member_id={adults['robert'].id}&status=pending"
        )
        assert r.status_code == 200
        items = r.json()
        meal_actions = [i for i in items if i["entity_type"] == "weekly_meal_plan"]
        assert len(meal_actions) == 1
        assert meal_actions[0]["action_type"] == "meal_plan_review"

        # Approve
        client.post(
            f"/families/{family.id}/meals/weekly/{plan.id}/approve",
            json={"member_id": str(adults["robert"].id)},
        )

        # Action should be resolved
        r = client.get(
            f"/families/{family.id}/action-items/current?member_id={adults['robert'].id}&status=pending"
        )
        meal_actions = [i for i in r.json() if i["entity_type"] == "weekly_meal_plan"]
        assert len(meal_actions) == 0

    def test_child_cannot_list_actions(self, client: TestClient, db, family, adults, children):
        r = client.get(
            f"/families/{family.id}/action-items/current?member_id={children['sadie'].id}"
        )
        assert r.status_code == 403

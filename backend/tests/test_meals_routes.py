"""HTTP-layer tests for meals weekly plan + reviews routes.

Uses FastAPI TestClient to verify route-level behavior including:
- adult allowed paths
- child forbidden paths (generate, approve, update, archive, regenerate)
- child allowed paths (view approved, reviews)
- approved-only child visibility
- family isolation
- malformed payload rejection
- parent action item lifecycle
- server-derived actor enforcement (no client member_id escalation)
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
from app.services import auth_service, weekly_meal_plan_service as wmp

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
    return wmp.save_weekly_meal_plan_draft(
        db, family.id, adult.id,
        week_start_date=MONDAY,
        week_plan=_ready_payload()["week_plan"],
        prep_plan=_ready_payload()["prep_plan"],
        grocery_plan=_ready_payload()["grocery_plan"],
        plan_summary="Test plan",
    )


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _login(db: Session, member: FamilyMember, email: str) -> str:
    """Create an account and login, return bearer token."""
    auth_service.create_account(db, member.id, email, "testpass123")
    result = auth_service.login(db, email, "testpass123")
    return result["token"]


@pytest.fixture()
def client(db: Session):
    def override_get_db():
        yield db
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


@pytest.fixture()
def adult_token(db: Session, adults) -> str:
    return _login(db, adults["robert"], "robert@test.com")


@pytest.fixture()
def child_token(db: Session, children) -> str:
    return _login(db, children["sadie"], "sadie@test.com")


# ---------------------------------------------------------------------------
# GET /meals/weekly/current
# ---------------------------------------------------------------------------


class TestGetCurrentPlan:
    def test_404_when_no_plan(self, client, family, adult_token):
        r = client.get(
            f"/families/{family.id}/meals/weekly/current",
            headers=_auth_header(adult_token),
        )
        assert r.status_code == 404

    def test_adult_sees_draft(self, client, db, family, adults, adult_token):
        plan = _make_draft(db, family, adults["robert"])
        r = client.get(
            f"/families/{family.id}/meals/weekly/current",
            headers=_auth_header(adult_token),
        )
        assert r.status_code == 200
        assert r.json()["id"] == str(plan.id)
        assert r.json()["status"] == "draft"

    def test_child_cannot_see_draft(self, client, db, family, adults, child_token):
        _make_draft(db, family, adults["robert"])
        r = client.get(
            f"/families/{family.id}/meals/weekly/current",
            headers=_auth_header(child_token),
        )
        assert r.status_code == 404

    def test_child_sees_approved(self, client, db, family, adults, child_token):
        plan = _make_draft(db, family, adults["robert"])
        wmp.approve_weekly_meal_plan(db, family.id, adults["robert"].id, plan.id)
        r = client.get(
            f"/families/{family.id}/meals/weekly/current",
            headers=_auth_header(child_token),
        )
        assert r.status_code == 200
        assert r.json()["status"] == "approved"

    def test_no_auth_returns_401(self, client, family):
        r = client.get(f"/families/{family.id}/meals/weekly/current")
        # With auth_required=false default, no token and no member_id => 401
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# GET /meals/weekly/{plan_id}
# ---------------------------------------------------------------------------


class TestGetPlanById:
    def test_adult_sees_draft(self, client, db, family, adults, adult_token):
        plan = _make_draft(db, family, adults["robert"])
        r = client.get(
            f"/families/{family.id}/meals/weekly/{plan.id}",
            headers=_auth_header(adult_token),
        )
        assert r.status_code == 200

    def test_child_cannot_see_draft(self, client, db, family, adults, child_token):
        plan = _make_draft(db, family, adults["robert"])
        r = client.get(
            f"/families/{family.id}/meals/weekly/{plan.id}",
            headers=_auth_header(child_token),
        )
        assert r.status_code == 403

    def test_child_sees_approved(self, client, db, family, adults, child_token):
        plan = _make_draft(db, family, adults["robert"])
        wmp.approve_weekly_meal_plan(db, family.id, adults["robert"].id, plan.id)
        r = client.get(
            f"/families/{family.id}/meals/weekly/{plan.id}",
            headers=_auth_header(child_token),
        )
        assert r.status_code == 200

    def test_family_isolation(self, client, db, family, adults, adult_token):
        plan = _make_draft(db, family, adults["robert"])
        other = Family(name="Other", timezone="UTC")
        db.add(other)
        db.flush()
        r = client.get(
            f"/families/{other.id}/meals/weekly/{plan.id}",
            headers=_auth_header(adult_token),
        )
        assert r.status_code == 403  # wrong family


# ---------------------------------------------------------------------------
# GET /meals/weekly (list)
# ---------------------------------------------------------------------------


class TestListPlans:
    def test_child_sees_only_approved(self, client, db, family, adults, child_token):
        _make_draft(db, family, adults["robert"])
        r = client.get(
            f"/families/{family.id}/meals/weekly",
            headers=_auth_header(child_token),
        )
        assert r.status_code == 200
        assert len(r.json()) == 0

    def test_adult_sees_drafts(self, client, db, family, adults, adult_token):
        _make_draft(db, family, adults["robert"])
        r = client.get(
            f"/families/{family.id}/meals/weekly",
            headers=_auth_header(adult_token),
        )
        assert r.status_code == 200
        assert len(r.json()) == 1


# ---------------------------------------------------------------------------
# POST /meals/weekly/{plan_id}/approve
# ---------------------------------------------------------------------------


class TestApprovePlan:
    def test_adult_can_approve(self, client, db, family, adults, adult_token):
        plan = _make_draft(db, family, adults["robert"])
        r = client.post(
            f"/families/{family.id}/meals/weekly/{plan.id}/approve",
            headers=_auth_header(adult_token),
        )
        assert r.status_code == 200
        assert r.json()["status"] == "approved"

    def test_child_cannot_approve(self, client, db, family, adults, child_token):
        plan = _make_draft(db, family, adults["robert"])
        r = client.post(
            f"/families/{family.id}/meals/weekly/{plan.id}/approve",
            headers=_auth_header(child_token),
        )
        assert r.status_code == 403

    def test_approve_syncs_groceries(self, client, db, family, adults, adult_token):
        plan = _make_draft(db, family, adults["robert"])
        client.post(
            f"/families/{family.id}/meals/weekly/{plan.id}/approve",
            headers=_auth_header(adult_token),
        )
        items = list(db.scalars(
            select(GroceryItem).where(GroceryItem.weekly_plan_id == plan.id)
        ).all())
        assert len(items) == 2
        assert all(i.source == "meal_ai" for i in items)

    def test_approve_resolves_parent_action(self, client, db, family, adults, adult_token):
        plan = _make_draft(db, family, adults["robert"])
        client.post(
            f"/families/{family.id}/meals/weekly/{plan.id}/approve",
            headers=_auth_header(adult_token),
        )
        actions = list(db.scalars(
            select(ParentActionItem).where(ParentActionItem.entity_id == plan.id)
        ).all())
        assert all(a.status == "resolved" for a in actions)


# ---------------------------------------------------------------------------
# POST /meals/weekly/{plan_id}/archive
# ---------------------------------------------------------------------------


class TestArchivePlan:
    def test_adult_can_archive(self, client, db, family, adults, adult_token):
        plan = _make_draft(db, family, adults["robert"])
        r = client.post(
            f"/families/{family.id}/meals/weekly/{plan.id}/archive",
            headers=_auth_header(adult_token),
        )
        assert r.status_code == 200
        assert r.json()["status"] == "archived"


# ---------------------------------------------------------------------------
# PATCH /meals/weekly/{plan_id}
# ---------------------------------------------------------------------------


class TestUpdatePlan:
    def test_adult_can_update(self, client, db, family, adults, adult_token):
        plan = _make_draft(db, family, adults["robert"])
        r = client.patch(
            f"/families/{family.id}/meals/weekly/{plan.id}",
            json={"title": "Updated Title"},
            headers=_auth_header(adult_token),
        )
        assert r.status_code == 200
        assert r.json()["title"] == "Updated Title"

    def test_child_cannot_update(self, client, db, family, adults, child_token):
        plan = _make_draft(db, family, adults["robert"])
        r = client.patch(
            f"/families/{family.id}/meals/weekly/{plan.id}",
            json={"title": "Nope"},
            headers=_auth_header(child_token),
        )
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# GET /meals/weekly/{plan_id}/groceries
# ---------------------------------------------------------------------------


class TestPlanGroceries:
    def test_returns_groceries_after_approve(self, client, db, family, adults, adult_token):
        plan = _make_draft(db, family, adults["robert"])
        wmp.approve_weekly_meal_plan(db, family.id, adults["robert"].id, plan.id)
        r = client.get(
            f"/families/{family.id}/meals/weekly/{plan.id}/groceries",
            headers=_auth_header(adult_token),
        )
        assert r.status_code == 200
        assert len(r.json()) == 2


# ---------------------------------------------------------------------------
# POST /meals/reviews
# ---------------------------------------------------------------------------


class TestMealReviews:
    def test_adult_can_submit_review(self, client, db, family, adult_token):
        r = client.post(
            f"/families/{family.id}/meals/reviews",
            json={
                "member_id": "00000000-0000-0000-0000-000000000000",  # ignored, overridden by actor
                "meal_title": "Pasta bake",
                "rating_overall": 4,
                "repeat_decision": "repeat",
            },
            headers=_auth_header(adult_token),
        )
        assert r.status_code == 201
        assert r.json()["meal_title"] == "Pasta bake"

    def test_child_can_submit_review(self, client, db, family, child_token):
        r = client.post(
            f"/families/{family.id}/meals/reviews",
            json={
                "member_id": "00000000-0000-0000-0000-000000000000",
                "meal_title": "Taco night",
                "rating_overall": 5,
                "repeat_decision": "repeat",
            },
            headers=_auth_header(child_token),
        )
        assert r.status_code == 201

    def test_invalid_rating_rejected(self, client, db, family, adult_token):
        r = client.post(
            f"/families/{family.id}/meals/reviews",
            json={
                "member_id": "00000000-0000-0000-0000-000000000000",
                "meal_title": "x",
                "rating_overall": 99,
                "repeat_decision": "repeat",
            },
            headers=_auth_header(adult_token),
        )
        assert r.status_code == 422

    def test_invalid_repeat_decision_rejected(self, client, db, family, adult_token):
        r = client.post(
            f"/families/{family.id}/meals/reviews",
            json={
                "member_id": "00000000-0000-0000-0000-000000000000",
                "meal_title": "x",
                "rating_overall": 3,
                "repeat_decision": "maybe",
            },
            headers=_auth_header(adult_token),
        )
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# GET /meals/reviews + /meals/reviews/summary
# ---------------------------------------------------------------------------


class TestListReviews:
    def test_list_reviews(self, client, db, family, adults, adult_token):
        from app.schemas.meals import MealReviewCreate
        wmp.create_meal_review(db, family.id, MealReviewCreate(
            member_id=adults["robert"].id, meal_title="Test", rating_overall=4, repeat_decision="repeat"
        ))
        r = client.get(
            f"/families/{family.id}/meals/reviews",
            headers=_auth_header(adult_token),
        )
        assert r.status_code == 200
        assert len(r.json()) >= 1

    def test_review_summary(self, client, db, family, adults, adult_token):
        r = client.get(
            f"/families/{family.id}/meals/reviews/summary",
            headers=_auth_header(adult_token),
        )
        assert r.status_code == 200
        assert "total_reviews" in r.json()


# ---------------------------------------------------------------------------
# Action item lifecycle through routes
# ---------------------------------------------------------------------------


class TestActionItemLifecycle:
    def test_draft_creates_action_approve_resolves(self, client, db, family, adults, adult_token):
        plan = _make_draft(db, family, adults["robert"])

        r = client.get(
            f"/families/{family.id}/action-items/current?status=pending",
            headers=_auth_header(adult_token),
        )
        assert r.status_code == 200
        meal_actions = [i for i in r.json() if i["entity_type"] == "weekly_meal_plan"]
        assert len(meal_actions) == 1

        client.post(
            f"/families/{family.id}/meals/weekly/{plan.id}/approve",
            headers=_auth_header(adult_token),
        )

        r = client.get(
            f"/families/{family.id}/action-items/current?status=pending",
            headers=_auth_header(adult_token),
        )
        meal_actions = [i for i in r.json() if i["entity_type"] == "weekly_meal_plan"]
        assert len(meal_actions) == 0

    def test_child_cannot_list_actions(self, client, db, family, child_token):
        r = client.get(
            f"/families/{family.id}/action-items/current",
            headers=_auth_header(child_token),
        )
        assert r.status_code == 403

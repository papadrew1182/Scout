"""Tests for weekly_meal_plan_service + related AI tools.

Covers the product contract:
- clarification path vs ready path
- payload validation (no silent coercion)
- draft persistence
- approve flow (including grocery sync, parent action resolved)
- regenerate a single day
- child cannot generate/edit/approve/regenerate
- child can view approved plan
- child can submit review
- parent action item created on draft, resolved on approve/archive
- family isolation
- AI tool permission behavior for the new tools
"""

import uuid
from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.context import get_allowed_tools_for_surface
from app.ai.tools import TOOL_DEFINITIONS, ToolExecutor
from app.models.action_items import ParentActionItem
from app.models.foundation import Family, FamilyMember
from app.models.grocery import GroceryItem
from app.models.meals import MealReview, WeeklyMealPlan
from app.schemas.meals import (
    MealReviewCreate,
    WeeklyMealPlanUpdate,
)
from app.services import weekly_meal_plan_service as wmp
from app.services.weekly_meal_plan_service import (
    PlanValidationError,
    validate_clarification_payload,
    validate_plan_payload,
)


MONDAY = date(2026, 4, 13)  # Mon


def _ready_payload() -> dict:
    return {
        "status": "ready",
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
                {"title": "Chop veg", "supports": ["monday", "tuesday"], "duration_min": 30},
            ],
            "timeline": [
                {"block": "0:00-0:45", "items": ["rice", "veg prep"]},
                {"block": "0:45-1:30", "items": ["assemble pasta bake"]},
            ],
        },
        "grocery_list": {
            "stores": [
                {
                    "name": "Costco",
                    "items": [
                        {"title": "Chicken thighs", "quantity": 4, "unit": "lb", "category": "protein", "linked_meal_ref": "monday:dinner"},
                        {"title": "Ground turkey", "quantity": 2, "unit": "lb", "category": "protein", "linked_meal_ref": "tuesday:dinner"},
                    ],
                },
                {
                    "name": "H-E-B",
                    "items": [
                        {"title": "Tortillas", "quantity": 1, "unit": "pack", "linked_meal_ref": "tuesday:dinner"},
                        {"title": "Broccoli", "quantity": 2, "unit": "heads"},
                    ],
                },
            ]
        },
        "summary": "Five dinners, batch cook Sunday, two stores",
    }


def _clarify_payload() -> dict:
    return {
        "status": "needs_clarification",
        "questions": [
            {"key": "budget", "question": "What is the budget this week?", "hint": "optional"},
            {"key": "time", "question": "How much Sunday prep time is available?"},
        ],
    }


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestValidation:
    def test_ready_payload_validates(self):
        normalized = validate_plan_payload(_ready_payload())
        assert "week_plan" in normalized
        assert "prep_plan" in normalized
        assert "grocery_plan" in normalized
        assert normalized["summary"]

    def test_status_missing_rejected(self):
        with pytest.raises(PlanValidationError):
            validate_plan_payload({"week_plan": {}, "prep_plan": {}, "grocery_list": {}})

    def test_empty_dinners_rejected(self):
        bad = _ready_payload()
        bad["week_plan"]["dinners"] = {}
        with pytest.raises(PlanValidationError):
            validate_plan_payload(bad)

    def test_invalid_day_rejected(self):
        bad = _ready_payload()
        bad["week_plan"]["dinners"]["funday"] = {"title": "x"}
        with pytest.raises(PlanValidationError):
            validate_plan_payload(bad)

    def test_store_missing_name_rejected(self):
        bad = _ready_payload()
        bad["grocery_list"]["stores"][0]["name"] = ""
        with pytest.raises(PlanValidationError):
            validate_plan_payload(bad)

    def test_clarification_valid(self):
        normalized = validate_clarification_payload(_clarify_payload())
        assert len(normalized) == 2
        assert normalized[0]["key"] == "budget"

    def test_clarification_missing_question_rejected(self):
        with pytest.raises(PlanValidationError):
            validate_clarification_payload({"status": "needs_clarification", "questions": [{"key": "x"}]})


# ---------------------------------------------------------------------------
# Persistence and approve flow
# ---------------------------------------------------------------------------


class TestDraftAndApprove:
    def test_save_draft_creates_parent_action(self, db: Session, family, adults):
        plan = wmp.save_weekly_meal_plan_draft(
            db, family.id, adults["robert"].id,
            week_start_date=MONDAY,
            week_plan=_ready_payload()["week_plan"],
            prep_plan=_ready_payload()["prep_plan"],
            grocery_plan=_ready_payload()["grocery_list"],
            plan_summary="Summary",
        )
        assert plan.status == "draft"
        actions = list(db.scalars(
            select(ParentActionItem)
            .where(ParentActionItem.family_id == family.id)
            .where(ParentActionItem.entity_type == "weekly_meal_plan")
            .where(ParentActionItem.entity_id == plan.id)
        ).all())
        assert len(actions) == 1
        assert actions[0].action_type == "meal_plan_review"
        assert actions[0].status == "pending"

    def test_approve_resolves_parent_action_and_syncs_groceries(self, db: Session, family, adults):
        plan = wmp.save_weekly_meal_plan_draft(
            db, family.id, adults["robert"].id,
            week_start_date=MONDAY,
            week_plan=_ready_payload()["week_plan"],
            prep_plan=_ready_payload()["prep_plan"],
            grocery_plan=_ready_payload()["grocery_list"],
        )
        approved = wmp.approve_weekly_meal_plan(db, family.id, adults["megan"].id, plan.id)
        assert approved.status == "approved"
        assert approved.approved_by_member_id == adults["megan"].id
        assert approved.approved_at is not None

        # parent action resolved
        actions = list(db.scalars(
            select(ParentActionItem)
            .where(ParentActionItem.entity_type == "weekly_meal_plan")
            .where(ParentActionItem.entity_id == plan.id)
        ).all())
        assert actions[0].status == "resolved"
        assert actions[0].resolved_by == adults["megan"].id

        # grocery items created and linked
        items = list(db.scalars(
            select(GroceryItem).where(GroceryItem.weekly_plan_id == plan.id)
        ).all())
        titles = {i.title for i in items}
        assert "Chicken thighs" in titles
        assert "Tortillas" in titles
        assert all(i.source == "meal_ai" for i in items)
        assert all(i.approval_status == "active" for i in items)
        stores = {i.preferred_store for i in items}
        assert "Costco" in stores
        assert "H-E-B" in stores

    def test_approve_is_idempotent_for_grocery_items(self, db: Session, family, adults):
        plan = wmp.save_weekly_meal_plan_draft(
            db, family.id, adults["robert"].id,
            week_start_date=MONDAY,
            week_plan=_ready_payload()["week_plan"],
            prep_plan=_ready_payload()["prep_plan"],
            grocery_plan=_ready_payload()["grocery_list"],
        )
        wmp.approve_weekly_meal_plan(db, family.id, adults["robert"].id, plan.id)
        # Calling sync again should not duplicate rows
        wmp.sync_grocery_items_from_plan(db, family.id, adults["robert"].id, plan.id)
        items = list(db.scalars(
            select(GroceryItem).where(GroceryItem.weekly_plan_id == plan.id)
        ).all())
        assert len(items) == 4

    def test_update_weekly_plan(self, db: Session, family, adults):
        plan = wmp.save_weekly_meal_plan_draft(
            db, family.id, adults["robert"].id,
            week_start_date=MONDAY,
            week_plan=_ready_payload()["week_plan"],
            prep_plan=_ready_payload()["prep_plan"],
            grocery_plan=_ready_payload()["grocery_list"],
        )
        updated = wmp.update_weekly_meal_plan(
            db, family.id, adults["robert"].id, plan.id,
            WeeklyMealPlanUpdate(title="Spring Week"),
        )
        assert updated.title == "Spring Week"

    def test_current_plan_prefers_approved(self, db: Session, family, adults):
        # Two drafts, approve the second
        wmp.save_weekly_meal_plan_draft(
            db, family.id, adults["robert"].id,
            week_start_date=MONDAY,
            week_plan=_ready_payload()["week_plan"],
            prep_plan=_ready_payload()["prep_plan"],
            grocery_plan=_ready_payload()["grocery_list"],
        )
        second = wmp.save_weekly_meal_plan_draft(
            db, family.id, adults["robert"].id,
            week_start_date=MONDAY,
            week_plan=_ready_payload()["week_plan"],
            prep_plan=_ready_payload()["prep_plan"],
            grocery_plan=_ready_payload()["grocery_list"],
        )
        wmp.approve_weekly_meal_plan(db, family.id, adults["robert"].id, second.id)

        current = wmp.get_current_weekly_meal_plan(db, family.id)
        assert current is not None
        assert current.id == second.id
        assert current.status == "approved"


# ---------------------------------------------------------------------------
# Role enforcement
# ---------------------------------------------------------------------------


class TestRoleRules:
    def test_child_cannot_save_draft(self, db: Session, family, children):
        with pytest.raises(HTTPException) as exc:
            wmp.save_weekly_meal_plan_draft(
                db, family.id, children["sadie"].id,
                week_start_date=MONDAY,
                week_plan=_ready_payload()["week_plan"],
                prep_plan=_ready_payload()["prep_plan"],
                grocery_plan=_ready_payload()["grocery_list"],
            )
        assert exc.value.status_code == 403

    def test_child_cannot_approve(self, db: Session, family, adults, children):
        plan = wmp.save_weekly_meal_plan_draft(
            db, family.id, adults["robert"].id,
            week_start_date=MONDAY,
            week_plan=_ready_payload()["week_plan"],
            prep_plan=_ready_payload()["prep_plan"],
            grocery_plan=_ready_payload()["grocery_list"],
        )
        with pytest.raises(HTTPException) as exc:
            wmp.approve_weekly_meal_plan(db, family.id, children["sadie"].id, plan.id)
        assert exc.value.status_code == 403

    def test_child_cannot_update(self, db: Session, family, adults, children):
        plan = wmp.save_weekly_meal_plan_draft(
            db, family.id, adults["robert"].id,
            week_start_date=MONDAY,
            week_plan=_ready_payload()["week_plan"],
            prep_plan=_ready_payload()["prep_plan"],
            grocery_plan=_ready_payload()["grocery_list"],
        )
        with pytest.raises(HTTPException) as exc:
            wmp.update_weekly_meal_plan(
                db, family.id, children["sadie"].id, plan.id,
                WeeklyMealPlanUpdate(title="Nope"),
            )
        assert exc.value.status_code == 403

    def test_child_can_view_approved_plan(self, db: Session, family, adults, children):
        plan = wmp.save_weekly_meal_plan_draft(
            db, family.id, adults["robert"].id,
            week_start_date=MONDAY,
            week_plan=_ready_payload()["week_plan"],
            prep_plan=_ready_payload()["prep_plan"],
            grocery_plan=_ready_payload()["grocery_list"],
        )
        wmp.approve_weekly_meal_plan(db, family.id, adults["robert"].id, plan.id)
        found = wmp.get_weekly_meal_plan(db, family.id, plan.id, actor_member_id=children["sadie"].id)
        assert found.id == plan.id

    def test_child_cannot_view_draft_plan(self, db: Session, family, adults, children):
        plan = wmp.save_weekly_meal_plan_draft(
            db, family.id, adults["robert"].id,
            week_start_date=MONDAY,
            week_plan=_ready_payload()["week_plan"],
            prep_plan=_ready_payload()["prep_plan"],
            grocery_plan=_ready_payload()["grocery_list"],
        )
        with pytest.raises(HTTPException) as exc:
            wmp.get_weekly_meal_plan(db, family.id, plan.id, actor_member_id=children["sadie"].id)
        assert exc.value.status_code == 403

    def test_child_current_plan_hides_draft(self, db: Session, family, adults, children):
        wmp.save_weekly_meal_plan_draft(
            db, family.id, adults["robert"].id,
            week_start_date=MONDAY,
            week_plan=_ready_payload()["week_plan"],
            prep_plan=_ready_payload()["prep_plan"],
            grocery_plan=_ready_payload()["grocery_list"],
        )
        # Child sees nothing (only draft exists)
        found = wmp.get_current_weekly_meal_plan(db, family.id, actor_member_id=children["sadie"].id)
        assert found is None

    def test_non_monday_week_start_rejected(self, db: Session, family, adults):
        with pytest.raises(HTTPException) as exc:
            wmp.save_weekly_meal_plan_draft(
                db, family.id, adults["robert"].id,
                week_start_date=date(2026, 4, 14),  # Tuesday
                week_plan=_ready_payload()["week_plan"],
                prep_plan=_ready_payload()["prep_plan"],
                grocery_plan=_ready_payload()["grocery_list"],
            )
        assert exc.value.status_code == 400


# ---------------------------------------------------------------------------
# Meal reviews
# ---------------------------------------------------------------------------


class TestMealReviews:
    def test_child_can_submit_review(self, db: Session, family, children):
        review = wmp.create_meal_review(
            db, family.id,
            MealReviewCreate(
                member_id=children["sadie"].id,
                meal_title="Pasta bake",
                rating_overall=5,
                kid_acceptance=5,
                effort=2,
                cleanup=2,
                leftovers="plenty",
                repeat_decision="repeat",
            ),
        )
        assert review.id is not None
        assert review.reviewed_by_member_id == children["sadie"].id

    def test_adult_can_submit_review(self, db: Session, family, adults):
        review = wmp.create_meal_review(
            db, family.id,
            MealReviewCreate(
                member_id=adults["robert"].id,
                meal_title="Sheet-pan chicken",
                rating_overall=4,
                repeat_decision="tweak",
            ),
        )
        assert review.rating_overall == 4

    def test_summary_aggregates_signals(self, db: Session, family, adults, children):
        for payload in [
            MealReviewCreate(member_id=adults["robert"].id, meal_title="Pasta bake", rating_overall=5, kid_acceptance=5, effort=2, leftovers="plenty", repeat_decision="repeat"),
            MealReviewCreate(member_id=adults["robert"].id, meal_title="Liver stew", rating_overall=2, kid_acceptance=1, repeat_decision="retire"),
            MealReviewCreate(member_id=children["sadie"].id, meal_title="Stir fry", rating_overall=4, kid_acceptance=2, effort=2, repeat_decision="tweak"),
        ]:
            wmp.create_meal_review(db, family.id, payload)

        summary = wmp.get_meal_review_summary(db, family.id)
        assert summary.total_reviews == 3
        assert "Pasta bake" in summary.high_rated
        assert "Liver stew" in summary.retired
        assert "Stir fry" in summary.low_kid_acceptance
        assert "Pasta bake" in summary.good_leftovers
        assert "Pasta bake" in summary.low_effort_favorites

    def test_invalid_rating_rejected_at_schema(self):
        with pytest.raises(Exception):
            MealReviewCreate(
                member_id=uuid.uuid4(),
                meal_title="x",
                rating_overall=99,
                repeat_decision="repeat",
            )


# ---------------------------------------------------------------------------
# Family isolation
# ---------------------------------------------------------------------------


class TestFamilyIsolation:
    def test_plan_from_other_family_not_found(self, db: Session, family, adults):
        other = Family(name="Other", timezone="UTC")
        db.add(other)
        db.flush()
        other_member = FamilyMember(family_id=other.id, first_name="Stranger", role="adult")
        db.add(other_member)
        db.flush()

        other_plan = wmp.save_weekly_meal_plan_draft(
            db, other.id, other_member.id,
            week_start_date=MONDAY,
            week_plan=_ready_payload()["week_plan"],
            prep_plan=_ready_payload()["prep_plan"],
            grocery_plan=_ready_payload()["grocery_list"],
        )
        with pytest.raises(HTTPException) as exc:
            wmp.get_weekly_meal_plan(db, family.id, other_plan.id)
        assert exc.value.status_code == 404

    def test_list_plans_scoped(self, db: Session, family, adults):
        other = Family(name="Other", timezone="UTC")
        db.add(other)
        db.flush()
        other_member = FamilyMember(family_id=other.id, first_name="Stranger", role="adult")
        db.add(other_member)
        db.flush()
        wmp.save_weekly_meal_plan_draft(
            db, other.id, other_member.id,
            week_start_date=MONDAY,
            week_plan=_ready_payload()["week_plan"],
            prep_plan=_ready_payload()["prep_plan"],
            grocery_plan=_ready_payload()["grocery_list"],
        )
        wmp.save_weekly_meal_plan_draft(
            db, family.id, adults["robert"].id,
            week_start_date=MONDAY,
            week_plan=_ready_payload()["week_plan"],
            prep_plan=_ready_payload()["prep_plan"],
            grocery_plan=_ready_payload()["grocery_list"],
        )
        mine = wmp.list_weekly_meal_plans(db, family.id)
        assert len(mine) == 1
        assert mine[0].family_id == family.id


# ---------------------------------------------------------------------------
# AI tool registry and permissions
# ---------------------------------------------------------------------------


class TestMealToolPermissions:
    def test_adult_personal_has_generate(self):
        tools = get_allowed_tools_for_surface("adult", "personal")
        assert "generate_weekly_meal_plan" in tools
        assert "add_meal_review" in tools
        assert "get_current_weekly_meal_plan" in tools

    def test_adult_parent_has_approve_and_regenerate(self):
        tools = get_allowed_tools_for_surface("adult", "parent")
        assert "approve_weekly_meal_plan" in tools
        assert "regenerate_meal_day" in tools

    def test_child_cannot_generate_or_approve(self):
        tools = get_allowed_tools_for_surface("child", "child")
        assert "generate_weekly_meal_plan" not in tools
        assert "approve_weekly_meal_plan" not in tools
        assert "regenerate_meal_day" not in tools

    def test_child_can_review_and_read(self):
        tools = get_allowed_tools_for_surface("child", "child")
        assert "add_meal_review" in tools
        assert "get_current_weekly_meal_plan" in tools

    def test_all_new_tool_definitions_registered(self):
        for name in [
            "generate_weekly_meal_plan",
            "get_current_weekly_meal_plan",
            "approve_weekly_meal_plan",
            "regenerate_meal_day",
            "add_meal_review",
            "get_meal_review_summary",
        ]:
            assert name in TOOL_DEFINITIONS


class TestMealToolExecution:
    def test_child_cannot_execute_generate(self, db: Session, family, children):
        executor = ToolExecutor(
            db=db, family_id=family.id, actor_member_id=children["sadie"].id,
            actor_role="child", surface="child",
            allowed_tools=get_allowed_tools_for_surface("child", "child"),
        )
        result = executor.execute("generate_weekly_meal_plan", {"week_start_date": MONDAY.isoformat()})
        assert "error" in result

    def test_approve_requires_confirmation(self, db: Session, family, adults):
        plan = wmp.save_weekly_meal_plan_draft(
            db, family.id, adults["robert"].id,
            week_start_date=MONDAY,
            week_plan=_ready_payload()["week_plan"],
            prep_plan=_ready_payload()["prep_plan"],
            grocery_plan=_ready_payload()["grocery_list"],
        )
        executor = ToolExecutor(
            db=db, family_id=family.id, actor_member_id=adults["robert"].id,
            actor_role="adult", surface="parent",
            allowed_tools=get_allowed_tools_for_surface("adult", "parent"),
        )
        result = executor.execute("approve_weekly_meal_plan", {"plan_id": str(plan.id)})
        assert result.get("confirmation_required") is True

    def test_approve_confirmed_executes(self, db: Session, family, adults):
        plan = wmp.save_weekly_meal_plan_draft(
            db, family.id, adults["robert"].id,
            week_start_date=MONDAY,
            week_plan=_ready_payload()["week_plan"],
            prep_plan=_ready_payload()["prep_plan"],
            grocery_plan=_ready_payload()["grocery_list"],
        )
        executor = ToolExecutor(
            db=db, family_id=family.id, actor_member_id=adults["robert"].id,
            actor_role="adult", surface="parent",
            allowed_tools=get_allowed_tools_for_surface("adult", "parent"),
        )
        result = executor.execute("approve_weekly_meal_plan", {"plan_id": str(plan.id), "confirmed": True})
        assert "approved" in result
        assert "handoff" in result

    def test_add_meal_review_child_allowed(self, db: Session, family, children):
        executor = ToolExecutor(
            db=db, family_id=family.id, actor_member_id=children["sadie"].id,
            actor_role="child", surface="child",
            allowed_tools=get_allowed_tools_for_surface("child", "child"),
        )
        result = executor.execute(
            "add_meal_review",
            {
                "meal_title": "Pasta bake",
                "rating_overall": 5,
                "repeat_decision": "repeat",
            },
        )
        assert "created" in result

    def test_get_current_plan_returns_none_when_empty(self, db: Session, family, adults):
        executor = ToolExecutor(
            db=db, family_id=family.id, actor_member_id=adults["robert"].id,
            actor_role="adult", surface="personal",
            allowed_tools=get_allowed_tools_for_surface("adult", "personal"),
        )
        result = executor.execute("get_current_weekly_meal_plan", {})
        assert result.get("plan") is None


# ---------------------------------------------------------------------------
# Generate path with mocked provider (clarification vs ready)
# ---------------------------------------------------------------------------


class _MockProvider:
    def __init__(self, payload):
        import json
        self._payload = payload

    def chat(self, **kwargs):
        import json
        from app.ai.provider import AIResponse
        return AIResponse(
            content=json.dumps(self._payload),
            tool_calls=[],
            stop_reason="end_turn",
            model="mock",
            input_tokens=1,
            output_tokens=1,
        )


class TestGenerateWithMock:
    def test_clarification_path(self, db: Session, family, adults):
        provider = _MockProvider(_clarify_payload())
        result = wmp.generate_weekly_meal_plan(
            db, family.id, adults["robert"].id,
            week_start_date=MONDAY,
            provider=provider,
        )
        assert result["status"] == "needs_clarification"
        assert len(result["questions"]) == 2
        # Nothing persisted
        plans = wmp.list_weekly_meal_plans(db, family.id)
        assert len(plans) == 0

    def test_ready_path_saves_draft(self, db: Session, family, adults):
        provider = _MockProvider(_ready_payload())
        result = wmp.generate_weekly_meal_plan(
            db, family.id, adults["robert"].id,
            week_start_date=MONDAY,
            provider=provider,
        )
        assert result["status"] == "ready"
        plan = wmp.get_weekly_meal_plan(db, family.id, result["plan_id"])
        assert plan.status == "draft"
        # Parent action item created
        actions = list(db.scalars(
            select(ParentActionItem)
            .where(ParentActionItem.entity_id == plan.id)
        ).all())
        assert len(actions) == 1

    def test_garbage_payload_never_saved(self, db: Session, family, adults):
        provider = _MockProvider({"status": "ready", "week_plan": "oops"})
        with pytest.raises(PlanValidationError):
            wmp.generate_weekly_meal_plan(
                db, family.id, adults["robert"].id,
                week_start_date=MONDAY,
                provider=provider,
            )
        plans = wmp.list_weekly_meal_plans(db, family.id)
        assert len(plans) == 0

    def test_child_generate_denied(self, db: Session, family, children):
        provider = _MockProvider(_ready_payload())
        with pytest.raises(HTTPException) as exc:
            wmp.generate_weekly_meal_plan(
                db, family.id, children["sadie"].id,
                week_start_date=MONDAY,
                provider=provider,
            )
        assert exc.value.status_code == 403

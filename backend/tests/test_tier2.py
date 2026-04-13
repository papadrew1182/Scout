"""Tests for Tier 2 features: weekly retro, homework sessions, receipt
extraction, handoff detection fix, meal plan prompt."""

import uuid
from datetime import date, datetime, time, timedelta

import pytest
import pytz
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.homework import (
    classify_homework,
    homework_summary,
    record_homework_turn,
)
from app.ai.orchestrator import _detect_handoff
from app.ai.receipt import _parse_proposals
from app.ai.retro import (
    build_retro_context,
    _template_narrative,
)
from app.models.action_items import ParentActionItem
from app.models.ai import AIConversation
from app.models.foundation import FamilyMember
from app.models.homework import HomeworkSession
from app.models.scheduled import ScheduledRun
from app.scheduler import run_weekly_retro_for_family, run_weekly_retro_tick


# ---------------------------------------------------------------------------
# Feature 7: Weekly retro
# ---------------------------------------------------------------------------


class TestWeeklyRetro:
    def test_template_narrative_has_all_sections_when_data_present(self):
        ctx = {
            "week_start": "2026-04-13",
            "week_end": "2026-04-19",
            "children": [
                {
                    "name": "Sadie",
                    "tasks_total": 10,
                    "tasks_completed": 8,
                    "tasks_missed": 2,
                    "daily_wins": 4,
                    "allowance_delta_cents": 500,
                    "homework_sessions": 2,
                    "homework_subjects": {"math": 1, "reading": 1},
                },
            ],
            "household": {
                "bills_paid": 3,
                "meal_reviews": 2,
                "grocery_items_added": 7,
                "purchase_requests_created": 1,
                "unresolved_inbox_items": 2,
            },
            "ai_usage": {
                "turns": 12,
                "tool_invocations": 4,
                "moderation_blocks": 1,
            },
        }
        text = _template_narrative(ctx)
        assert "Sadie" in text
        assert "8/10 tasks" in text
        assert "Bills paid" in text
        assert "Safety blocks" in text
        assert "2026-04-13" in text

    def test_template_narrative_quiet_week(self):
        ctx = {
            "week_start": "2026-04-13",
            "week_end": "2026-04-19",
            "children": [],
            "household": {},
            "ai_usage": {},
        }
        text = _template_narrative(ctx)
        assert "quiet" in text.lower() or "2026-04-13" in text

    def test_build_retro_context_zero_state(self, db: Session, family):
        ctx = build_retro_context(
            db, family_id=family.id, week_start=date(2026, 4, 13)
        )
        # Empty family → all zero counts, no children
        assert ctx["household"]["bills_paid"] == 0
        assert ctx["ai_usage"]["turns"] == 0
        assert ctx["children"] == []

    def test_run_weekly_retro_is_idempotent_per_week(
        self, db: Session, family, adults, monkeypatch
    ):
        # Stub AI so the retro uses template fallback (no provider call)
        from app.config import settings
        monkeypatch.setattr(settings, "anthropic_api_key", "")

        week = date(2026, 4, 13)  # Monday
        first = run_weekly_retro_for_family(
            db, family_id=family.id, week_start=week
        )
        assert first["status"] == "success"

        second = run_weekly_retro_for_family(
            db, family_id=family.id, week_start=week
        )
        assert second["status"] == "skipped"
        assert second["reason"] == "already_ran_this_week"

        items = list(db.scalars(
            select(ParentActionItem)
            .where(ParentActionItem.family_id == family.id)
            .where(ParentActionItem.action_type == "weekly_retro")
        ).all())
        assert len(items) == 1
        assert items[0].detail  # non-empty narrative

    def test_run_weekly_retro_tick_fires_only_on_friday_6pm_local(
        self, db: Session, family, adults, monkeypatch
    ):
        from app.config import settings
        monkeypatch.setattr(settings, "anthropic_api_key", "")

        tz = pytz.timezone("America/Chicago")

        # Wednesday 6pm local → no retro
        wed = tz.localize(datetime(2026, 4, 15, 18, 0, 0)).astimezone(pytz.UTC)
        assert run_weekly_retro_tick(db, now_utc=wed) == []

        # Friday 2pm local → no retro (wrong hour)
        fri_2pm = tz.localize(datetime(2026, 4, 17, 14, 0, 0)).astimezone(pytz.UTC)
        assert run_weekly_retro_tick(db, now_utc=fri_2pm) == []

        # Friday 6pm local → fires
        fri_6pm = tz.localize(datetime(2026, 4, 17, 18, 0, 0)).astimezone(pytz.UTC)
        results = run_weekly_retro_tick(db, now_utc=fri_6pm)
        assert any(r["status"] == "success" for r in results)


# ---------------------------------------------------------------------------
# Feature 8: Homework detection
# ---------------------------------------------------------------------------


class TestHomeworkClassifier:
    def test_math_by_keyword(self):
        r = classify_homework("help me with this fraction problem")
        assert r.is_homework and r.subject == "math"

    def test_math_by_inline_expression(self):
        r = classify_homework("what is 12 * 7")
        assert r.is_homework and r.subject == "math"

    def test_reading(self):
        r = classify_homework("I need a summary of the main character")
        assert r.is_homework and r.subject == "reading"

    def test_science_photosynthesis(self):
        r = classify_homework("explain photosynthesis for my science class")
        assert r.is_homework and r.subject == "science"

    def test_generic_homework_is_other(self):
        r = classify_homework("help me with my homework")
        assert r.is_homework and r.subject == "other"

    def test_non_homework_passes(self):
        r = classify_homework("what chores do I have today")
        assert r.is_homework is False

    def test_empty_message(self):
        r = classify_homework("")
        assert r.is_homework is False


class TestHomeworkSessions:
    def test_child_first_homework_turn_creates_session(
        self, db: Session, family, children
    ):
        sadie = children["sadie"]
        conv = AIConversation(
            family_id=family.id, family_member_id=sadie.id, surface="child",
        )
        db.add(conv); db.flush()

        session = record_homework_turn(
            db,
            family_id=family.id,
            member_id=sadie.id,
            conversation_id=conv.id,
            message="help me with long division",
            role="child",
            surface="child",
        )
        assert session is not None
        assert session.subject == "math"
        assert session.turn_count == 1

    def test_second_turn_in_same_conversation_extends_session(
        self, db: Session, family, children
    ):
        sadie = children["sadie"]
        conv = AIConversation(
            family_id=family.id, family_member_id=sadie.id, surface="child",
        )
        db.add(conv); db.flush()

        s1 = record_homework_turn(
            db, family_id=family.id, member_id=sadie.id,
            conversation_id=conv.id, message="show me 846 / 6",
            role="child", surface="child",
        )
        s2 = record_homework_turn(
            db, family_id=family.id, member_id=sadie.id,
            conversation_id=conv.id, message="try 924 / 4 next",
            role="child", surface="child",
        )
        assert s1.id == s2.id
        assert s2.turn_count == 2

    def test_adult_turn_does_not_create_session(
        self, db: Session, family, adults
    ):
        andrew = adults["robert"]
        conv = AIConversation(
            family_id=family.id, family_member_id=andrew.id, surface="personal",
        )
        db.add(conv); db.flush()

        result = record_homework_turn(
            db, family_id=family.id, member_id=andrew.id,
            conversation_id=conv.id, message="what is 2 + 2",
            role="adult", surface="personal",
        )
        assert result is None

    def test_non_homework_turn_does_not_create_session(
        self, db: Session, family, children
    ):
        sadie = children["sadie"]
        conv = AIConversation(
            family_id=family.id, family_member_id=sadie.id, surface="child",
        )
        db.add(conv); db.flush()

        result = record_homework_turn(
            db, family_id=family.id, member_id=sadie.id,
            conversation_id=conv.id, message="what chores do I have",
            role="child", surface="child",
        )
        assert result is None

    def test_homework_summary_rollup(
        self, db: Session, family, children
    ):
        sadie = children["sadie"]
        townes = children["townes"]

        # Seed a few sessions across two kids and two subjects
        db.add(HomeworkSession(
            family_id=family.id, member_id=sadie.id,
            conversation_id=None, subject="math",
            started_at=datetime.now(pytz.UTC),
            turn_count=3, session_length_sec=120,
        ))
        db.add(HomeworkSession(
            family_id=family.id, member_id=sadie.id,
            conversation_id=None, subject="reading",
            started_at=datetime.now(pytz.UTC),
            turn_count=2, session_length_sec=60,
        ))
        db.add(HomeworkSession(
            family_id=family.id, member_id=townes.id,
            conversation_id=None, subject="math",
            started_at=datetime.now(pytz.UTC),
            turn_count=1, session_length_sec=30,
        ))
        db.flush()

        summary = homework_summary(db, family_id=family.id, days=7)
        assert summary["total_sessions"] == 3
        names = {c["first_name"] for c in summary["children"]}
        assert "Sadie" in names and "Townes" in names
        sadie_row = next(c for c in summary["children"] if c["first_name"] == "Sadie")
        assert sadie_row["sessions"] == 2
        assert sadie_row["subjects"]["math"] == 1
        assert sadie_row["subjects"]["reading"] == 1


# ---------------------------------------------------------------------------
# Feature 6: Receipt extraction — parser
# ---------------------------------------------------------------------------


class TestReceiptParser:
    def test_clean_json_array(self):
        text = '[{"title": "Milk", "quantity": 1, "unit": "gal", "category": "dairy", "confidence": 0.9}]'
        items = _parse_proposals(text)
        assert len(items) == 1
        assert items[0].title == "Milk"
        assert items[0].quantity == 1.0
        assert items[0].unit == "gal"
        assert items[0].category == "dairy"
        assert items[0].confidence == 0.9

    def test_wrapped_in_prose(self):
        text = (
            "Here are the items from the receipt:\n\n"
            '[{"title": "Bananas", "quantity": null, "unit": null, "category": "produce", "confidence": 0.8}, '
            '{"title": "Bread", "quantity": 2, "unit": "loaf", "category": "bakery", "confidence": 0.7}]\n\n'
            "Let me know if you want any changes."
        )
        items = _parse_proposals(text)
        assert len(items) == 2
        assert items[0].title == "Bananas"
        assert items[0].quantity is None
        assert items[1].quantity == 2.0

    def test_malformed_returns_empty(self):
        items = _parse_proposals("oops, not json at all")
        assert items == []

    def test_missing_title_skipped(self):
        text = '[{"quantity": 1}, {"title": "OK"}]'
        items = _parse_proposals(text)
        assert len(items) == 1
        assert items[0].title == "OK"


# ---------------------------------------------------------------------------
# Orchestrator handoff detection fix
# ---------------------------------------------------------------------------


class TestHandoffDetectionFix:
    def test_nested_handoff_is_detected(self):
        # This is the pattern every tool in app.ai.tools actually uses.
        tool_result = {
            "created": {"id": "xyz"},
            "handoff": {
                "entity_type": "personal_task",
                "entity_id": "abc-123",
                "route_hint": "/personal",
                "summary": "Task created",
            },
        }
        h = _detect_handoff(tool_result)
        assert h is not None
        assert h["entity_type"] == "personal_task"
        assert h["route_hint"] == "/personal"

    def test_flat_handoff_still_works(self):
        # Legacy pattern: the tool result IS the handoff dict itself.
        tool_result = {
            "entity_type": "event",
            "entity_id": "evt-1",
            "route_hint": "/calendar",
            "summary": "Event created",
        }
        h = _detect_handoff(tool_result)
        assert h is not None
        assert h["entity_type"] == "event"

    def test_no_handoff_returns_none(self):
        assert _detect_handoff({"status": "ok"}) is None
        assert _detect_handoff(None) is None
        assert _detect_handoff({"handoff": {"random": "dict"}}) is None

    def test_meal_plan_tool_shape_is_detected(self):
        # Exact shape returned by _generate_weekly_meal_plan
        tool_result = {
            "status": "ready",
            "plan_id": "plan-1",
            "summary": "Five dinners planned.",
            "handoff": {
                "entity_type": "weekly_meal_plan",
                "entity_id": "plan-1",
                "route_hint": "/meals/this-week",
                "summary": "Weekly meal plan draft saved. Review and approve.",
            },
        }
        h = _detect_handoff(tool_result)
        assert h is not None
        assert h["entity_type"] == "weekly_meal_plan"
        assert h["route_hint"] == "/meals/this-week"


# ---------------------------------------------------------------------------
# Meal plan system prompt block
# ---------------------------------------------------------------------------


class TestMealPlanPrompt:
    def test_adult_prompt_includes_meal_plan_block(self, db: Session, family, adults):
        from app.ai.context import build_system_prompt, load_member_context

        andrew = adults["robert"]
        ctx = load_member_context(db, family.id, andrew.id)
        prompt = build_system_prompt(ctx, "personal")
        # All three parts of the structure rule must be referenced
        assert "Meal plan for the week" in prompt
        assert "Sunday batch cook plan" in prompt
        assert "Grocery list split by store" in prompt
        # Em dash rule
        assert "em dashes" in prompt.lower()
        # Clarification-first rule
        assert "clarifying questions" in prompt.lower()

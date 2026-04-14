"""Tests for Tier 4 features:
 13. Proactive anomaly detection
 14. Read-only MCP server (import + tool dispatch)
 15. Multi-turn weekly planner intent routing + bulk-confirm tool
"""

import uuid
from datetime import date, datetime, timedelta

import pytest
import pytz
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import anomalies
from app.ai.anomalies import (
    AnomalyCandidate,
    _template_narrative,
    detect_homework_dropoff,
    detect_inbox_buildup,
    detect_meal_monotony,
    detect_routine_dropoff_by_child,
    detect_stale_routines,
    generate_anomaly_candidates,
    rank_candidates,
)
from app.ai.context import build_system_prompt, load_member_context
from app.ai.orchestrator import (
    MAX_PLANNER_ROUNDS,
    MAX_TOOL_ROUNDS,
    _append_planner_suffix,
    _rounds_for_intent,
)
from app.ai.tools import CONFIRMATION_REQUIRED, TOOL_DEFINITIONS, ToolExecutor
from app.models.action_items import ParentActionItem
from app.models.homework import HomeworkSession
from app.models.life_management import Routine, TaskInstance
from app.models.meals import Meal
from app.scheduler import (
    ANOMALY_SCAN_HOUR,
    run_anomaly_scan_for_family,
    run_anomaly_scan_tick,
)


# ---------------------------------------------------------------------------
# Feature 13 — Anomaly detection
# ---------------------------------------------------------------------------


class TestAnomalyCandidateGeneration:
    def test_rank_filters_below_significance_and_caps_count(self):
        cands = [
            AnomalyCandidate("t", "a", 0.1, "low"),
            AnomalyCandidate("t", "b", 0.6, "ok"),
            AnomalyCandidate("t", "c", 0.9, "top"),
            AnomalyCandidate("t", "d", 0.3, "below"),
        ]
        out = rank_candidates(cands)
        assert [c.signature for c in out] == ["c", "b"]

    def test_template_narrative_includes_action(self):
        c = AnomalyCandidate(
            "stale_routine", "s", 0.7, "Routine X is stale.",
            suggested_action="Check it.",
        )
        text = _template_narrative(c)
        assert "stale" in text.lower()
        assert "Check it." in text

    def test_stale_routine_needs_historical_completions(
        self, db: Session, family, children, sadie_routines
    ):
        # With only brand-new routines and zero historical completions,
        # the stale detector should NOT fire. That prevents new routines
        # from immediately flagging as stale.
        out = detect_stale_routines(
            db, family_id=family.id, as_of=date(2026, 4, 13)
        )
        assert out == []

    def test_stale_routine_fires_when_history_then_silence(
        self, db: Session, family, children, sadie_routines
    ):
        sadie = children["sadie"]
        morning = sadie_routines[0]
        # Seed a completion 12 days ago (in the historical window).
        old = TaskInstance(
            family_id=family.id,
            family_member_id=sadie.id,
            routine_id=morning.id,
            instance_date=date(2026, 4, 1),
            due_at=datetime(2026, 4, 1, 7, 25),
            is_completed=True,
            completed_at=datetime(2026, 4, 1, 7, 30),
        )
        db.add(old)
        db.flush()

        out = detect_stale_routines(
            db, family_id=family.id, as_of=date(2026, 4, 13)
        )
        # Should flag the routine as stale now — was completing, now isn't.
        assert any(c.signature == f"routine:{morning.id}" for c in out)

    def test_meal_monotony(self, db: Session, family, adults):
        # Seed 4 tacos meals in the last 14 days.
        robert = adults["robert"]
        for i in range(4):
            db.add(
                Meal(
                    family_id=family.id,
                    created_by=robert.id,
                    meal_date=date(2026, 4, 13) - timedelta(days=i * 2),
                    meal_type="dinner",
                    title="Tacos",
                )
            )
        db.flush()
        out = detect_meal_monotony(
            db, family_id=family.id, as_of=date(2026, 4, 13)
        )
        assert len(out) == 1
        assert "tacos" in out[0].summary.lower()
        assert out[0].facts["count"] == 4

    def test_meal_monotony_ignores_below_threshold(
        self, db: Session, family, adults
    ):
        robert = adults["robert"]
        for i in range(2):
            db.add(
                Meal(
                    family_id=family.id,
                    created_by=robert.id,
                    meal_date=date(2026, 4, 13) - timedelta(days=i),
                    meal_type="dinner",
                    title="Pasta",
                )
            )
        db.flush()
        out = detect_meal_monotony(
            db, family_id=family.id, as_of=date(2026, 4, 13)
        )
        assert out == []

    def test_homework_dropoff_fires(self, db: Session, family, children):
        sadie = children["sadie"]
        # Seed 3 older sessions, 0 recent.
        now = datetime(2026, 4, 13, 16, 0, 0)
        for i in range(3):
            db.add(
                HomeworkSession(
                    family_id=family.id,
                    member_id=sadie.id,
                    subject="math",
                    started_at=now - timedelta(days=8 + i),
                    turn_count=5,
                )
            )
        db.flush()
        out = detect_homework_dropoff(
            db, family_id=family.id, as_of=date(2026, 4, 13)
        )
        assert len(out) == 1
        assert out[0].facts["child_name"] == "Sadie"

    def test_homework_dropoff_silent_when_recent_activity(
        self, db: Session, family, children
    ):
        sadie = children["sadie"]
        now = datetime(2026, 4, 13, 16, 0, 0)
        for i in range(3):
            db.add(
                HomeworkSession(
                    family_id=family.id,
                    member_id=sadie.id,
                    subject="math",
                    started_at=now - timedelta(days=8 + i),
                    turn_count=5,
                )
            )
        db.add(
            HomeworkSession(
                family_id=family.id,
                member_id=sadie.id,
                subject="reading",
                started_at=now - timedelta(days=2),
                turn_count=3,
            )
        )
        db.flush()
        out = detect_homework_dropoff(
            db, family_id=family.id, as_of=date(2026, 4, 13)
        )
        assert out == []

    def test_inbox_buildup(self, db: Session, family, adults):
        robert = adults["robert"]
        # Seed 6 stale pending items. created_at is now() via server
        # default — use raw SQL to backdate.
        for i in range(6):
            item = ParentActionItem(
                family_id=family.id,
                created_by_member_id=robert.id,
                action_type="grocery_review",
                title=f"review item {i}",
                status="pending",
                created_at=datetime(2026, 4, 1, 9, 0, 0),
            )
            db.add(item)
        db.flush()
        out = detect_inbox_buildup(
            db, family_id=family.id, as_of=date(2026, 4, 13)
        )
        assert len(out) == 1
        assert out[0].facts["pending_count"] == 6


class TestAnomalyScanScheduler:
    def test_dedupe_via_scheduled_runs(
        self, db: Session, family, adults, monkeypatch
    ):
        # No actual candidates — just verify the mutex dedupes.
        first = run_anomaly_scan_for_family(
            db, family_id=family.id, run_date=date(2026, 4, 13)
        )
        assert first["status"] == "success"

        second = run_anomaly_scan_for_family(
            db, family_id=family.id, run_date=date(2026, 4, 13)
        )
        assert second["status"] == "skipped"
        assert second["reason"] == "already_ran_today"

    def test_scan_creates_action_item_for_candidate_with_template_fallback(
        self, db: Session, family, adults, monkeypatch
    ):
        # Force template fallback path by blanking the key.
        from app.config import settings
        monkeypatch.setattr(settings, "anthropic_api_key", "")

        # Seed enough tacos to fire meal_monotony.
        robert = adults["robert"]
        for i in range(4):
            db.add(
                Meal(
                    family_id=family.id,
                    created_by=robert.id,
                    meal_date=date(2026, 4, 13) - timedelta(days=i * 2),
                    meal_type="dinner",
                    title="Tacos",
                )
            )
        db.flush()

        out = run_anomaly_scan_for_family(
            db, family_id=family.id, run_date=date(2026, 4, 13)
        )
        assert out["status"] == "success"
        assert out["candidates"] >= 1
        assert out["created"] >= 1

        items = list(
            db.scalars(
                select(ParentActionItem)
                .where(ParentActionItem.family_id == family.id)
                .where(ParentActionItem.action_type == "anomaly_alert")
            ).all()
        )
        assert len(items) >= 1
        # Template fallback must include the suggested action text.
        assert any("Consider rotating" in (i.detail or "") for i in items)

    def test_tick_fires_only_at_local_hour(
        self, db: Session, family, adults
    ):
        family.timezone = "America/Chicago"
        db.flush()
        tz = pytz.timezone("America/Chicago")

        noon = tz.localize(datetime(2026, 4, 13, 12, 0, 0)).astimezone(pytz.UTC)
        assert run_anomaly_scan_tick(db, now_utc=noon) == []

        local_hit = tz.localize(
            datetime(2026, 4, 13, ANOMALY_SCAN_HOUR, 0, 0)
        ).astimezone(pytz.UTC)
        results = run_anomaly_scan_tick(db, now_utc=local_hit)
        assert len(results) == 1


class TestAnomalyIntegrationWithGenerate:
    def test_generate_anomaly_candidates_includes_meal_monotony(
        self, db: Session, family, adults
    ):
        robert = adults["robert"]
        for i in range(4):
            db.add(
                Meal(
                    family_id=family.id,
                    created_by=robert.id,
                    meal_date=date(2026, 4, 13) - timedelta(days=i * 2),
                    meal_type="dinner",
                    title="Tacos",
                )
            )
        db.flush()
        cands = generate_anomaly_candidates(
            db, family_id=family.id, as_of=date(2026, 4, 13)
        )
        assert any(c.anomaly_type == "meal_monotony" for c in cands)


# ---------------------------------------------------------------------------
# Feature 14 — MCP server
# ---------------------------------------------------------------------------


class TestMCPServerWiring:
    def test_server_imports_and_builds(self, family):
        """The server module imports the mcp package; instantiating
        build_server should succeed without touching the DB."""
        from scout_mcp.server import build_server

        server = build_server(family.id)
        assert server is not None
        # Server exposes a name attribute per MCP spec.
        assert getattr(server, "name", None) == "scout-readonly"

    def test_boot_rejects_missing_token(self, monkeypatch):
        from scout_mcp.server import _BootError, _load_family_id

        monkeypatch.delenv("SCOUT_MCP_TOKEN", raising=False)
        monkeypatch.setenv("SCOUT_MCP_FAMILY_ID", str(uuid.uuid4()))
        with pytest.raises(_BootError):
            _load_family_id()

    def test_boot_rejects_missing_family_id(self, monkeypatch):
        from scout_mcp.server import _BootError, _load_family_id

        monkeypatch.setenv("SCOUT_MCP_TOKEN", "test")
        monkeypatch.delenv("SCOUT_MCP_FAMILY_ID", raising=False)
        with pytest.raises(_BootError):
            _load_family_id()

    def test_boot_rejects_invalid_family_uuid(self, monkeypatch):
        from scout_mcp.server import _BootError, _load_family_id

        monkeypatch.setenv("SCOUT_MCP_TOKEN", "test")
        monkeypatch.setenv("SCOUT_MCP_FAMILY_ID", "not-a-uuid")
        with pytest.raises(_BootError):
            _load_family_id()

    def test_boot_accepts_valid_env(self, monkeypatch):
        from scout_mcp.server import _load_family_id

        fam_id = uuid.uuid4()
        monkeypatch.setenv("SCOUT_MCP_TOKEN", "test")
        monkeypatch.setenv("SCOUT_MCP_FAMILY_ID", str(fam_id))
        assert _load_family_id() == fam_id

    def test_action_inbox_redacts_moderation_alerts(
        self, db: Session, family, adults, monkeypatch
    ):
        from scout_mcp.server import _get_action_inbox

        # Redirect _session to the test's transactional session so the
        # MCP read function sees our seeded rows.
        class _Ctx:
            def __enter__(self_inner):
                return db

            def __exit__(self_inner, *a):
                return False

        monkeypatch.setattr("scout_mcp.server._session", lambda: _Ctx())

        robert = adults["robert"]
        db.add(
            ParentActionItem(
                family_id=family.id,
                created_by_member_id=robert.id,
                action_type="moderation_alert",
                title="Scout blocked a sensitive message (profanity)",
                detail="RAW CHILD TEXT SHOULD NOT LEAK",
                entity_type="ai_conversation",
                entity_id=uuid.uuid4(),
                status="pending",
            )
        )
        db.add(
            ParentActionItem(
                family_id=family.id,
                created_by_member_id=robert.id,
                action_type="grocery_review",
                title="Review groceries",
                detail="safe detail",
                status="pending",
            )
        )
        db.flush()

        result = _get_action_inbox(family.id)
        mod_items = [i for i in result["items"] if i["action_type"] == "moderation_alert"]
        groc_items = [i for i in result["items"] if i["action_type"] == "grocery_review"]

        assert len(mod_items) == 1
        assert mod_items[0]["detail"] is None
        assert "RAW CHILD TEXT" not in str(mod_items[0])

        assert len(groc_items) == 1
        assert groc_items[0]["detail"] == "safe detail"


# ---------------------------------------------------------------------------
# Feature 15 — Weekly planner intent
# ---------------------------------------------------------------------------


class TestPlannerIntentRouting:
    def test_intent_chat_uses_short_round_cap(self):
        assert _rounds_for_intent("chat") == MAX_TOOL_ROUNDS

    def test_intent_weekly_plan_unlocks_longer_cap(self):
        assert _rounds_for_intent("weekly_plan") == MAX_PLANNER_ROUNDS
        assert MAX_PLANNER_ROUNDS > MAX_TOOL_ROUNDS

    def test_unknown_intent_falls_back_to_chat(self):
        assert _rounds_for_intent("bogus") == MAX_TOOL_ROUNDS
        assert _rounds_for_intent(None) == MAX_TOOL_ROUNDS

    def test_planner_suffix_injected_for_weekly_plan(
        self, db: Session, family, adults
    ):
        robert = adults["robert"]
        ctx = load_member_context(db, family_id=family.id, member_id=robert.id)
        base = build_system_prompt(ctx, surface="personal")
        planned = _append_planner_suffix(base)
        assert "WEEKLY PLANNING MODE" in planned
        assert "apply_weekly_plan_bundle" in planned

    def test_planner_suffix_preserves_meal_rules(
        self, db: Session, family, adults
    ):
        robert = adults["robert"]
        ctx = load_member_context(db, family_id=family.id, member_id=robert.id)
        base = build_system_prompt(ctx, surface="personal")
        planned = _append_planner_suffix(base)
        # The base meal-plan block has the three-part + no-em-dash rules.
        # Planning mode must NOT erase them — the suffix only adds.
        assert "three-part" in planned or "three parts" in planned.lower()
        assert "em dash" in planned.lower()
        assert "Sunday batch cook plan" in planned


class TestBulkConfirmationTool:
    def test_bundle_tool_is_confirmation_gated(self):
        assert "apply_weekly_plan_bundle" in CONFIRMATION_REQUIRED
        assert "apply_weekly_plan_bundle" in TOOL_DEFINITIONS

    def test_bundle_first_call_returns_confirmation_required(
        self, db: Session, family, adults
    ):
        robert = adults["robert"]
        executor = ToolExecutor(
            db=db,
            family_id=family.id,
            actor_member_id=robert.id,
            actor_role="adult",
            surface="personal",
            conversation_id=None,
            allowed_tools=["apply_weekly_plan_bundle"],
        )
        args = {
            "summary": "4 tasks, 2 events, 5 grocery items",
            "tasks": [{"title": "plan dinner Monday"}],
            "events": [],
            "grocery_items": [{"title": "bananas"}],
        }
        result = executor.execute("apply_weekly_plan_bundle", args)
        assert result.get("confirmation_required") is True
        assert result.get("tool_name") == "apply_weekly_plan_bundle"
        # Nothing should have been written yet.
        from app.services import personal_tasks_service

        tasks = personal_tasks_service.list_personal_tasks(db, family.id)
        assert not any(t.title == "plan dinner Monday" for t in tasks)

    def test_bundle_confirmed_writes_atomically(
        self, db: Session, family, adults
    ):
        robert = adults["robert"]
        executor = ToolExecutor(
            db=db,
            family_id=family.id,
            actor_member_id=robert.id,
            actor_role="adult",
            surface="personal",
            conversation_id=None,
            allowed_tools=["apply_weekly_plan_bundle"],
        )
        args = {
            "summary": "weekly plan",
            "tasks": [
                {"title": "plan dinner Monday", "priority": "medium"},
                {"title": "pack lunches Sunday", "priority": "high"},
            ],
            "events": [],
            "grocery_items": [
                {"title": "bananas"},
                {"title": "oat milk"},
            ],
            "confirmed": True,
        }
        result = executor.execute("apply_weekly_plan_bundle", args)
        assert result.get("status") == "applied"
        assert result.get("errors") == []
        assert result["applied"]["tasks_created"] == 2
        assert result["applied"]["grocery_items_created"] == 2
        assert result.get("handoff") is not None

        from app.services import personal_tasks_service
        tasks = personal_tasks_service.list_personal_tasks(db, family.id)
        titles = {t.title for t in tasks}
        assert "plan dinner Monday" in titles
        assert "pack lunches Sunday" in titles

    def test_bundle_ignores_invalid_entries(
        self, db: Session, family, adults
    ):
        robert = adults["robert"]
        executor = ToolExecutor(
            db=db,
            family_id=family.id,
            actor_member_id=robert.id,
            actor_role="adult",
            surface="personal",
            conversation_id=None,
            allowed_tools=["apply_weekly_plan_bundle"],
        )
        args = {
            "summary": "partial input",
            "tasks": [
                {"title": "good task"},
                {"description": "no title at all"},  # bad
                "not a dict",                        # bad
            ],
            "grocery_items": [
                {"title": "milk"},
                {},  # bad
            ],
            "confirmed": True,
        }
        result = executor.execute("apply_weekly_plan_bundle", args)
        assert result["applied"]["tasks_created"] == 1
        assert result["applied"]["grocery_items_created"] == 1

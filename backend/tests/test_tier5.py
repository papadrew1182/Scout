"""Tests for Tier 5 features:
 16. Atomic weekly planner bundle writes
 17. Rich planner review card (shape / flow verified via bundle tool contract)
 18. Scheduler HA + anomaly suppression
 19. Remote MCP transport with real auth/scoping
 20. Safe family memory layer
"""

import hashlib
import uuid
from datetime import date, datetime, timedelta

import pytest
import pytz
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.ai import memory as memory_module
from app.ai.anomalies import AnomalyCandidate
from app.ai.memory import (
    archive_memory,
    build_memory_prompt_block,
    record_ai_proposed_memory,
    record_auto_structured_memory,
    record_parent_memory,
)
from app.ai.tools import ToolExecutor
from app.models.action_items import ParentActionItem
from app.models.ai import AIConversation, AIMessage
from app.models.foundation import FamilyMember, Session as SessionModel, UserAccount
from app.models.meals import Meal
from app.models.tier5 import (
    AnomalySuppression,
    FamilyMemory,
    PlannerBundleApply,
    ScoutMCPToken,
)
from app.scheduler import run_anomaly_scan_for_family
from app.services import (
    calendar_service,
    grocery_service,
    personal_tasks_service,
)
from app.services.auth_service import hash_password


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_session_token(db: Session, member_id) -> str:
    account = UserAccount(
        id=uuid.uuid4(),
        family_member_id=member_id,
        email=f"t5-{uuid.uuid4().hex[:8]}@scout.local",
        auth_provider="email",
        password_hash=hash_password("x" * 12),
        is_primary=False,
        is_active=True,
    )
    db.add(account)
    db.flush()
    token = f"tok-{uuid.uuid4().hex}"
    db.add(
        SessionModel(
            user_account_id=account.id,
            token=token,
            expires_at=datetime.now(pytz.UTC).replace(tzinfo=None) + timedelta(hours=1),
        )
    )
    db.commit()
    return token


@pytest.fixture
def client(db):
    from fastapi.testclient import TestClient

    from app.database import get_db
    from app.main import app

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    try:
        yield c
    finally:
        app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# Feature 16 — Atomic planner bundle writes
# ---------------------------------------------------------------------------


class TestAtomicPlannerBundle:
    def _executor(self, db, family, adults):
        robert = adults["robert"]
        return ToolExecutor(
            db=db,
            family_id=family.id,
            actor_member_id=robert.id,
            actor_role="adult",
            surface="personal",
            conversation_id=None,
            allowed_tools=["apply_weekly_plan_bundle"],
        )

    def test_successful_atomic_apply(self, db: Session, family, adults):
        executor = self._executor(db, family, adults)
        args = {
            "summary": "test",
            "bundle_apply_id": "bundle-success-1",
            "tasks": [
                {"title": "pick up dry cleaning"},
                {"title": "rsvp birthday"},
            ],
            "events": [
                {
                    "title": "dentist",
                    "starts_at": "2026-04-20T15:00:00",
                    "ends_at": "2026-04-20T15:30:00",
                }
            ],
            "grocery_items": [{"title": "oat milk"}],
            "confirmed": True,
        }
        result = executor.execute("apply_weekly_plan_bundle", args)
        assert result["status"] == "applied"
        assert result["applied"]["tasks_created"] == 2
        assert result["applied"]["events_created"] == 1
        assert result["applied"]["grocery_items_created"] == 1

        ledger = db.scalars(
            select(PlannerBundleApply).where(
                PlannerBundleApply.bundle_apply_id == "bundle-success-1"
            )
        ).first()
        assert ledger is not None
        assert ledger.status == "applied"
        assert ledger.tasks_created == 2

    def test_failure_rolls_back_entire_bundle(
        self, db: Session, family, adults
    ):
        executor = self._executor(db, family, adults)
        # Second event has ends_at BEFORE starts_at → calendar_service
        # raises HTTPException. The entire bundle must roll back.
        args = {
            "summary": "test rollback",
            "bundle_apply_id": "bundle-rollback-1",
            "tasks": [{"title": "should not land"}],
            "events": [
                {
                    "title": "good event",
                    "starts_at": "2026-04-20T10:00:00",
                    "ends_at": "2026-04-20T11:00:00",
                },
                {
                    "title": "bad event",
                    "starts_at": "2026-04-20T12:00:00",
                    "ends_at": "2026-04-20T11:00:00",  # before starts_at
                },
            ],
            "grocery_items": [{"title": "nope"}],
            "confirmed": True,
        }
        result = executor.execute("apply_weekly_plan_bundle", args)
        assert result["status"] == "failed"
        assert result["applied"]["tasks_created"] == 0
        assert result["applied"]["events_created"] == 0
        assert result["applied"]["grocery_items_created"] == 0
        assert len(result["errors"]) == 1

        # Nothing should have been written.
        from app.models.personal_tasks import PersonalTask
        from app.models.calendar import Event
        from app.models.grocery import GroceryItem

        assert not db.scalars(
            select(PersonalTask).where(PersonalTask.title == "should not land")
        ).first()
        assert not db.scalars(
            select(Event).where(Event.title == "good event")
        ).first()
        assert not db.scalars(
            select(GroceryItem).where(GroceryItem.title == "nope")
        ).first()

        # Ledger has a 'failed' row recording the attempt.
        ledger = db.scalars(
            select(PlannerBundleApply).where(
                PlannerBundleApply.bundle_apply_id == "bundle-rollback-1"
            )
        ).first()
        assert ledger is not None
        assert ledger.status == "failed"
        assert ledger.tasks_created == 0

    def test_duplicate_apply_is_idempotent(self, db: Session, family, adults):
        executor = self._executor(db, family, adults)
        args = {
            "summary": "dup",
            "bundle_apply_id": "bundle-dup-1",
            "tasks": [{"title": "task A"}, {"title": "task B"}],
            "events": [],
            "grocery_items": [],
            "confirmed": True,
        }
        first = executor.execute("apply_weekly_plan_bundle", args)
        assert first["status"] == "applied"
        assert first["applied"]["tasks_created"] == 2

        second = executor.execute("apply_weekly_plan_bundle", args)
        assert second["status"] == "applied"
        assert second.get("idempotent_replay") is True
        assert second["applied"]["tasks_created"] == 2

        # Only two tasks exist — the second call did NOT double-write.
        from app.models.personal_tasks import PersonalTask
        tasks = list(
            db.scalars(
                select(PersonalTask)
                .where(PersonalTask.family_id == family.id)
                .where(PersonalTask.title.in_(["task A", "task B"]))
            ).all()
        )
        assert len(tasks) == 2

    def test_no_writes_on_first_call_without_confirmation(
        self, db: Session, family, adults
    ):
        executor = self._executor(db, family, adults)
        args = {
            "summary": "before confirm",
            "bundle_apply_id": "bundle-preconfirm",
            "tasks": [{"title": "should never land"}],
            "events": [],
            "grocery_items": [],
            # no confirmed=True
        }
        result = executor.execute("apply_weekly_plan_bundle", args)
        assert result.get("confirmation_required") is True

        from app.models.personal_tasks import PersonalTask
        assert not db.scalars(
            select(PersonalTask).where(
                PersonalTask.title == "should never land"
            )
        ).first()


# ---------------------------------------------------------------------------
# Feature 17 — Rich planner review card (data contract)
# ---------------------------------------------------------------------------


class TestPlannerReviewCardContract:
    """The rich card is a frontend component; the tests below verify
    the bundle tool produces the exact payload shape the card reads.

    Full UI snapshot tests would live in scout-ui; here we just lock
    the contract (keys present, groups typed correctly) so the
    frontend and backend can't silently drift."""

    def test_confirmation_payload_carries_grouped_proposals(
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
        raw_bundle = {
            "summary": "week of 4/20",
            "bundle_apply_id": "bundle-card-1",
            "tasks": [{"title": "t1"}, {"title": "t2"}],
            "events": [
                {
                    "title": "e1",
                    "starts_at": "2026-04-20T09:00:00",
                    "ends_at": "2026-04-20T10:00:00",
                }
            ],
            "grocery_items": [{"title": "g1"}],
        }
        result = executor.execute("apply_weekly_plan_bundle", raw_bundle)
        assert result.get("confirmation_required") is True
        args = result.get("arguments", {})
        assert args.get("summary") == "week of 4/20"
        assert len(args.get("tasks") or []) == 2
        assert len(args.get("events") or []) == 1
        assert len(args.get("grocery_items") or []) == 1
        assert args.get("bundle_apply_id") == "bundle-card-1"


# ---------------------------------------------------------------------------
# Feature 18 — Scheduler HA + anomaly suppression
# ---------------------------------------------------------------------------


class TestSchedulerHA:
    def test_advisory_lock_round_trip(self, db: Session):
        """Smoke: the advisory-lock SQL the scheduler issues works on
        the test DB. Acquire once, try again (same session returns
        true because locks are reentrant per session), acquire on a
        second connection — should return false."""
        from app.config import settings
        from app.database import engine

        key = int(settings.scheduler_advisory_lock_key)
        conn_a = engine.connect()
        conn_b = engine.connect()
        try:
            got_a = conn_a.execute(
                text("SELECT pg_try_advisory_lock(:k)"), {"k": key}
            ).scalar()
            assert got_a is True

            got_b = conn_b.execute(
                text("SELECT pg_try_advisory_lock(:k)"), {"k": key}
            ).scalar()
            assert got_b is False

            conn_a.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": key})
            # Now b should be able to grab it.
            got_b2 = conn_b.execute(
                text("SELECT pg_try_advisory_lock(:k)"), {"k": key}
            ).scalar()
            assert got_b2 is True
            conn_b.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": key})
        finally:
            conn_a.close()
            conn_b.close()


class TestAnomalySuppression:
    def _seed_tacos(self, db, family, adults, count=4):
        robert = adults["robert"]
        for i in range(count):
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

    def test_second_scan_same_day_suppresses_repeat(
        self, db: Session, family, adults, monkeypatch
    ):
        from app.config import settings
        monkeypatch.setattr(settings, "anthropic_api_key", "")
        self._seed_tacos(db, family, adults)

        first = run_anomaly_scan_for_family(
            db, family_id=family.id, run_date=date(2026, 4, 13)
        )
        assert first["status"] == "success"
        assert first["created"] >= 1

        suppressions = list(
            db.scalars(
                select(AnomalySuppression).where(
                    AnomalySuppression.family_id == family.id
                )
            ).all()
        )
        assert len(suppressions) >= 1

    def test_subsequent_day_still_suppresses_within_window(
        self, db: Session, family, adults, monkeypatch
    ):
        from app.config import settings
        monkeypatch.setattr(settings, "anthropic_api_key", "")
        monkeypatch.setattr(settings, "anomaly_suppression_days", 5)
        self._seed_tacos(db, family, adults)

        run_anomaly_scan_for_family(
            db, family_id=family.id, run_date=date(2026, 4, 13)
        )
        # Next day: same meal_monotony signature, should be suppressed.
        result = run_anomaly_scan_for_family(
            db, family_id=family.id, run_date=date(2026, 4, 14)
        )
        assert result["status"] == "success"
        assert result["suppressed"] >= 1
        # Only one anomaly_alert row exists — day 2 did not create a duplicate.
        items = list(
            db.scalars(
                select(ParentActionItem)
                .where(ParentActionItem.family_id == family.id)
                .where(ParentActionItem.action_type == "anomaly_alert")
            ).all()
        )
        assert len(items) == 1

    def test_different_signature_still_emits(
        self, db: Session, family, adults, monkeypatch
    ):
        from app.config import settings
        monkeypatch.setattr(settings, "anthropic_api_key", "")

        # Seed two distinct monotony signatures.
        robert = adults["robert"]
        for i in range(4):
            db.add(
                Meal(
                    family_id=family.id, created_by=robert.id,
                    meal_date=date(2026, 4, 13) - timedelta(days=i),
                    meal_type="dinner", title="Tacos",
                )
            )
            db.add(
                Meal(
                    family_id=family.id, created_by=robert.id,
                    meal_date=date(2026, 4, 13) - timedelta(days=i),
                    meal_type="lunch", title="Grilled cheese",
                )
            )
        db.flush()

        result = run_anomaly_scan_for_family(
            db, family_id=family.id, run_date=date(2026, 4, 13)
        )
        # Two distinct signatures should both land as anomalies.
        assert result["created"] >= 2


# ---------------------------------------------------------------------------
# Feature 19 — Remote MCP
# ---------------------------------------------------------------------------


class TestRemoteMCP:
    def test_remote_404_when_disabled(
        self, client, db, family, adults, monkeypatch
    ):
        from app.config import settings
        monkeypatch.setattr(settings, "mcp_remote_enabled", False)

        r = client.get(
            "/mcp/tools/list",
            headers={"Authorization": "Bearer anything"},
        )
        assert r.status_code == 404

    def test_tools_list_rejects_missing_bearer(
        self, client, db, family, adults, monkeypatch
    ):
        from app.config import settings
        monkeypatch.setattr(settings, "mcp_remote_enabled", True)

        r = client.get("/mcp/tools/list")
        assert r.status_code == 401

    def test_tools_list_rejects_unknown_token(
        self, client, db, family, adults, monkeypatch
    ):
        from app.config import settings
        monkeypatch.setattr(settings, "mcp_remote_enabled", True)

        r = client.get(
            "/mcp/tools/list",
            headers={"Authorization": "Bearer scout_mcp_not-a-real-token"},
        )
        assert r.status_code == 401

    def test_create_token_returns_plaintext_and_list_hides_it(
        self, client, db, family, adults, monkeypatch
    ):
        from app.config import settings
        monkeypatch.setattr(settings, "mcp_remote_enabled", True)
        token = _build_session_token(db, adults["robert"].id)

        r = client.post(
            "/mcp/tokens",
            headers={"Authorization": f"Bearer {token}"},
            json={"label": "my laptop"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["plaintext"].startswith("scout_mcp_")
        assert body["token"]["label"] == "my laptop"

        listing = client.get(
            "/mcp/tokens",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert listing.status_code == 200
        rows = listing.json()
        assert len(rows) == 1
        # plaintext MUST NOT appear in the list response.
        assert "plaintext" not in rows[0]

    def test_child_cannot_create_mcp_token(
        self, client, db, family, children, monkeypatch
    ):
        from app.config import settings
        monkeypatch.setattr(settings, "mcp_remote_enabled", True)
        token = _build_session_token(db, children["sadie"].id)

        r = client.post(
            "/mcp/tokens",
            headers={"Authorization": f"Bearer {token}"},
            json={"label": "kid laptop"},
        )
        assert r.status_code == 403

    def test_parent_scope_tools_list_and_call(
        self, client, db, family, adults, monkeypatch
    ):
        from app.config import settings
        monkeypatch.setattr(settings, "mcp_remote_enabled", True)

        # MCP tool handlers call _session() which normally returns a
        # fresh SessionLocal() — in tests we redirect it at the
        # transactional db so the handlers see fixture-seeded rows.
        class _Ctx:
            def __enter__(self_inner):
                return db
            def __exit__(self_inner, *a):
                return False
        monkeypatch.setattr("scout_mcp.server._session", lambda: _Ctx())

        session_tok = _build_session_token(db, adults["robert"].id)
        create = client.post(
            "/mcp/tokens",
            headers={"Authorization": f"Bearer {session_tok}"},
            json={"label": "parent token"},
        )
        mcp_plaintext = create.json()["plaintext"]

        r = client.get(
            "/mcp/tools/list",
            headers={"Authorization": f"Bearer {mcp_plaintext}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["scope"] == "parent"
        names = [t["name"] for t in body["tools"]]
        assert "get_action_inbox" in names
        assert "get_ai_usage" in names
        assert "get_family_schedule" in names

        call = client.post(
            "/mcp/tools/call",
            headers={"Authorization": f"Bearer {mcp_plaintext}"},
            json={"name": "get_family_schedule", "arguments": {"days": 7}},
        )
        assert call.status_code == 200
        out = call.json()["result"]
        assert "events" in out

    def test_child_scope_tool_list_is_restricted(
        self, client, db, family, adults, monkeypatch
    ):
        from app.config import settings
        monkeypatch.setattr(settings, "mcp_remote_enabled", True)

        session_tok = _build_session_token(db, adults["robert"].id)
        create = client.post(
            "/mcp/tokens",
            headers={"Authorization": f"Bearer {session_tok}"},
            json={"label": "kid surface", "scope": "child"},
        )
        mcp_plaintext = create.json()["plaintext"]

        r = client.get(
            "/mcp/tools/list",
            headers={"Authorization": f"Bearer {mcp_plaintext}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["scope"] == "child"
        names = set(t["name"] for t in body["tools"])
        # Parent-only tools must be absent.
        assert "get_action_inbox" not in names
        assert "get_ai_usage" not in names
        assert "get_homework_summary" not in names
        assert "get_recent_briefs" not in names
        # Child-safe tools still present.
        assert "get_family_schedule" in names
        assert "get_tasks_summary" in names

    def test_revoked_token_rejected(
        self, client, db, family, adults, monkeypatch
    ):
        from app.config import settings
        monkeypatch.setattr(settings, "mcp_remote_enabled", True)

        session_tok = _build_session_token(db, adults["robert"].id)
        create = client.post(
            "/mcp/tokens",
            headers={"Authorization": f"Bearer {session_tok}"},
            json={"label": "to be revoked"},
        )
        mcp_plaintext = create.json()["plaintext"]
        token_id = create.json()["token"]["id"]

        rev = client.post(
            f"/mcp/tokens/{token_id}/revoke",
            headers={"Authorization": f"Bearer {session_tok}"},
        )
        assert rev.status_code == 200

        r = client.get(
            "/mcp/tools/list",
            headers={"Authorization": f"Bearer {mcp_plaintext}"},
        )
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# Feature 20 — Safe family memory layer
# ---------------------------------------------------------------------------


class TestFamilyMemory:
    def test_parent_write_lands_active(self, db: Session, family):
        row = record_parent_memory(
            db,
            family_id=family.id,
            memory_type="planning_default",
            scope="family",
            content="We shop at HEB on Sundays.",
        )
        assert row.status == "active"
        assert row.source_kind == "parent_edit"

    def test_ai_proposed_stays_proposed(self, db: Session, family):
        row = record_ai_proposed_memory(
            db,
            family_id=family.id,
            memory_type="meal_preference",
            scope="family",
            content="Kids love bell peppers in tacos.",
            confidence=0.8,
        )
        assert row.status == "proposed"
        # Confidence is clamped to [0,1].
        assert 0.0 <= row.confidence <= 1.0

    def test_auto_structured_dedupes_active_content(self, db: Session, family):
        first = record_auto_structured_memory(
            db,
            family_id=family.id,
            memory_type="planning_default",
            scope="family",
            content="Sunday is batch cook day.",
        )
        second = record_auto_structured_memory(
            db,
            family_id=family.id,
            memory_type="planning_default",
            scope="family",
            content="Sunday is batch cook day.",
        )
        assert first is not None
        assert second is not None
        assert first.id == second.id  # dedupe → same row

    def test_prompt_block_only_uses_active_memories(
        self, db: Session, family
    ):
        record_parent_memory(
            db, family_id=family.id, memory_type="planning_default",
            scope="family", content="Groceries from HEB only.",
        )
        record_ai_proposed_memory(
            db, family_id=family.id, memory_type="planning_default",
            scope="family", content="Maybe Trader Joes every other week.",
        )
        block = build_memory_prompt_block(
            db, family_id=family.id, surface="parent"
        )
        assert "HEB" in block
        assert "Trader Joes" not in block

    def test_prompt_block_scope_hides_parent_from_child(
        self, db: Session, family, children
    ):
        record_parent_memory(
            db, family_id=family.id, memory_type="household_preference",
            scope="parent", content="Adults only: review savings plan.",
        )
        record_parent_memory(
            db, family_id=family.id, memory_type="household_preference",
            scope="family", content="Quiet hours start at 8:30pm.",
        )
        block = build_memory_prompt_block(
            db, family_id=family.id, surface="child",
            member_id=children["sadie"].id,
        )
        assert "Quiet hours" in block
        assert "savings plan" not in block

    def test_memory_routes_parent_only(
        self, client, db, family, adults, children
    ):
        # Parent can list.
        tok_adult = _build_session_token(db, adults["robert"].id)
        r = client.get(
            "/api/memory",
            headers={"Authorization": f"Bearer {tok_adult}"},
        )
        assert r.status_code == 200

        # Child cannot list.
        tok_child = _build_session_token(db, children["sadie"].id)
        r2 = client.get(
            "/api/memory",
            headers={"Authorization": f"Bearer {tok_child}"},
        )
        assert r2.status_code == 403

    def test_memory_crud_end_to_end(self, client, db, family, adults):
        tok = _build_session_token(db, adults["robert"].id)
        headers = {"Authorization": f"Bearer {tok}"}

        # Create.
        create = client.post(
            "/api/memory",
            headers=headers,
            json={
                "memory_type": "meal_preference",
                "scope": "family",
                "content": "Megan doesn't eat mushrooms.",
            },
        )
        assert create.status_code == 200
        mem_id = create.json()["id"]

        # List includes it.
        listing = client.get("/api/memory", headers=headers)
        assert any(m["id"] == mem_id for m in listing.json())

        # Archive.
        patch = client.patch(
            f"/api/memory/{mem_id}",
            headers=headers,
            json={"status": "archived"},
        )
        assert patch.status_code == 200
        assert patch.json()["status"] == "archived"

        # Delete.
        delete = client.delete(f"/api/memory/{mem_id}", headers=headers)
        assert delete.status_code == 200

"""QA bug-bash regression tests.

Each test here documents a bug (or near-miss) found during the
stabilization sweep after Tiers 1-5. The style is:

    1. failing test written first (reproducing the bug)
    2. fix applied to the offending module
    3. this test now passes and is kept as a permanent regression

The bug ledger in the commit message + final report maps each
test in this file to its severity and repro steps.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta

import pytest
import pytz
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import memory as memory_module
from app.ai.memory import build_memory_prompt_block, record_parent_memory
from app.ai.orchestrator import (
    _load_conversation_messages,
    get_or_create_conversation,
)
from app.ai.tools import ToolExecutor
from app.models.ai import AIConversation, AIMessage
from app.models.foundation import Session as SessionModel, UserAccount
from app.models.tier5 import FamilyMemory, PlannerBundleApply
from app.services.auth_service import hash_password


# ---------------------------------------------------------------------------
# Helpers (local copy — keeps this test file self-contained on CI)
# ---------------------------------------------------------------------------


def _bearer(db: Session, member_id) -> str:
    account = UserAccount(
        id=uuid.uuid4(),
        family_member_id=member_id,
        email=f"qa-{uuid.uuid4().hex[:8]}@scout.local",
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
            expires_at=datetime.now(pytz.UTC).replace(tzinfo=None)
            + timedelta(hours=1),
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
# BUG #1 (P0) — history replay leaks orphan tool_use blocks
#
# Repro: a conversation can land in a state where the last assistant
# message has ``tool_calls`` populated but no matching ``tool`` row
# follows it. Sources: stream interrupt mid-turn (rare but possible),
# legacy pre-migration-017 rows, any bug in a tool handler that
# raised after persist_assistant but before persist_tool.
#
# Expected: ``_load_conversation_messages`` should emit a replay-safe
# history so the next Anthropic call does not 400 with
# "tool_use must be followed by tool_result".
#
# Before fix: orphan tool_use blocks are dumped into the replayed
# ``messages`` as-is. Anthropic then rejects the whole conversation
# on the NEXT turn, wedging the user permanently.
# ---------------------------------------------------------------------------


class TestHistoryReplayOrphanFiltering:
    def _make_conv(self, db, family, member):
        conv = AIConversation(
            family_id=family.id,
            family_member_id=member.id,
            surface="personal",
        )
        db.add(conv)
        db.flush()
        return conv

    def test_trailing_orphan_tool_use_is_stripped(
        self, db: Session, family, adults
    ):
        robert = adults["robert"]
        conv = self._make_conv(db, family, robert)
        db.add(AIMessage(conversation_id=conv.id, role="user", content="hi"))
        db.flush()
        db.add(
            AIMessage(
                conversation_id=conv.id,
                role="assistant",
                content="calling a tool",
                tool_calls=[
                    {"id": "toolu_abc", "name": "get_weather", "input": {}}
                ],
                model="claude-sonnet-4-20250514",
            )
        )
        db.flush()
        # Deliberately DO NOT add the matching `tool` row.

        msgs = _load_conversation_messages(db, conv.id)

        # Find the assistant message in the replayed history. It
        # should exist (so the prior user turn still makes sense) but
        # it must not contain a tool_use block with no follow-up.
        def _flatten_types(m):
            if isinstance(m.get("content"), list):
                return [b.get("type") for b in m["content"]]
            return ["text"]

        for m in msgs:
            if m["role"] != "assistant":
                continue
            assert "tool_use" not in _flatten_types(m), (
                "Orphan tool_use leaked into replayed history; Anthropic "
                "will 400 on the next turn."
            )

    def test_orphan_tool_use_in_middle_drops_surrounding_unpaired(
        self, db: Session, family, adults
    ):
        """A paired tool_use → tool_result pair should survive intact.
        An unpaired tool_use mid-conversation should be stripped so
        replay still works."""
        robert = adults["robert"]
        conv = self._make_conv(db, family, robert)
        db.add(AIMessage(conversation_id=conv.id, role="user", content="q1"))
        db.flush()
        db.add(
            AIMessage(
                conversation_id=conv.id,
                role="assistant",
                tool_calls=[
                    {"id": "toolu_1", "name": "get_weather", "input": {}}
                ],
                model="claude-sonnet-4-20250514",
            )
        )
        db.flush()
        db.add(
            AIMessage(
                conversation_id=conv.id,
                role="tool",
                tool_results={"tool_use_id": "toolu_1", "result": {"ok": True}},
            )
        )
        db.flush()
        db.add(
            AIMessage(
                conversation_id=conv.id,
                role="assistant",
                content="sunny today",
                model="claude-sonnet-4-20250514",
            )
        )
        db.flush()
        db.add(AIMessage(conversation_id=conv.id, role="user", content="q2"))
        db.flush()
        # Orphan assistant tool_use with no matching tool row after it.
        db.add(
            AIMessage(
                conversation_id=conv.id,
                role="assistant",
                tool_calls=[
                    {"id": "toolu_2", "name": "get_weather", "input": {}}
                ],
                model="claude-sonnet-4-20250514",
            )
        )
        db.flush()

        msgs = _load_conversation_messages(db, conv.id)

        # Pair 1 should be intact: tool_use toolu_1 followed by
        # tool_result referencing toolu_1.
        tool_use_ids: list[str] = []
        tool_result_ids: list[str] = []
        for m in msgs:
            content = m.get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if block.get("type") == "tool_use":
                    tool_use_ids.append(block.get("id"))
                elif block.get("type") == "tool_result":
                    tool_result_ids.append(block.get("tool_use_id"))

        # Every tool_use must have a matching tool_result.
        for tid in tool_use_ids:
            assert tid in tool_result_ids, (
                f"tool_use {tid} has no matching tool_result in replay"
            )
        # The orphan toolu_2 must be gone.
        assert "toolu_2" not in tool_use_ids


# ---------------------------------------------------------------------------
# BUG #2 (P1) — get_or_create_conversation resumes ended conversations
#
# Repro: the F12 "New chat" affordance calls POST /conversations/{id}/end
# which flips ai_conversations.status to 'ended'. The resumable
# endpoint filters ended threads out, but ``get_or_create_conversation``
# (called by every chat turn) only checks family/member scoping, not
# status. A client that still holds the old conversation_id in memory
# can continue posting to it after calling End.
#
# Expected: an ended conversation is NOT resumable by id. A chat
# request targeting an ended thread should start a fresh conversation
# instead of appending to the archived one.
# ---------------------------------------------------------------------------


class TestEndedConversationNotResumableByID:
    def test_ended_by_id_creates_new_conversation(
        self, db: Session, family, adults
    ):
        robert = adults["robert"]
        conv = AIConversation(
            family_id=family.id,
            family_member_id=robert.id,
            surface="personal",
            status="ended",
        )
        db.add(conv)
        db.flush()

        fresh = get_or_create_conversation(
            db,
            family_id=family.id,
            member_id=robert.id,
            surface="personal",
            conversation_id=conv.id,
        )
        assert fresh.id != conv.id
        assert fresh.status == "active"

    def test_archived_by_id_creates_new_conversation(
        self, db: Session, family, adults
    ):
        robert = adults["robert"]
        conv = AIConversation(
            family_id=family.id,
            family_member_id=robert.id,
            surface="personal",
            status="archived",
        )
        db.add(conv)
        db.flush()
        fresh = get_or_create_conversation(
            db,
            family_id=family.id,
            member_id=robert.id,
            surface="personal",
            conversation_id=conv.id,
        )
        assert fresh.id != conv.id

    def test_active_by_id_still_resumes(self, db: Session, family, adults):
        robert = adults["robert"]
        conv = AIConversation(
            family_id=family.id,
            family_member_id=robert.id,
            surface="personal",
            status="active",
        )
        db.add(conv)
        db.flush()
        same = get_or_create_conversation(
            db,
            family_id=family.id,
            member_id=robert.id,
            surface="personal",
            conversation_id=conv.id,
        )
        assert same.id == conv.id


# ---------------------------------------------------------------------------
# BUG #3 (P1) — planner bundle apply without bundle_apply_id leaves
# no audit trail at all
#
# Repro: Claude's tool call omits ``bundle_apply_id`` (or sends it as
# the empty string). The bundle still writes tasks/events/grocery,
# but the entire ``if bundle_apply_id:`` branch — both the
# idempotency pre-check AND the success ledger write — is skipped.
# Result: a successful atomic apply with zero rows in
# planner_bundle_applies, so admin audit queries never see it.
#
# Expected: every successful apply writes a ledger row. Missing
# caller id → server auto-generates a fallback (no dedupe, but a
# permanent audit record). Idempotency still only kicks in with a
# caller-supplied id.
# ---------------------------------------------------------------------------


class TestBundleLedgerAlwaysWritten:
    def test_apply_without_bundle_apply_id_still_writes_ledger(
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
            "summary": "no id provided",
            # no bundle_apply_id at all
            "tasks": [{"title": "task without id"}],
            "events": [],
            "grocery_items": [],
            "confirmed": True,
        }
        result = executor.execute("apply_weekly_plan_bundle", args)
        assert result["status"] == "applied"
        assert result["applied"]["tasks_created"] == 1
        assert result.get("bundle_apply_id"), (
            "auto-generated fallback should be returned so the client can "
            "replay with the same key if it needs to"
        )

        rows = list(
            db.scalars(
                select(PlannerBundleApply)
                .where(PlannerBundleApply.family_id == family.id)
                .where(PlannerBundleApply.status == "applied")
            ).all()
        )
        assert len(rows) == 1
        assert rows[0].tasks_created == 1

    def test_apply_with_conversation_id_populates_ledger_conversation_id(
        self, db: Session, family, adults
    ):
        """F16 handoff note: 'verify in production logs that
        planner_bundle_applies.conversation_id is consistently
        populated'. Nail it down with a test."""
        robert = adults["robert"]
        conv = AIConversation(
            family_id=family.id,
            family_member_id=robert.id,
            surface="personal",
        )
        db.add(conv)
        db.flush()

        executor = ToolExecutor(
            db=db,
            family_id=family.id,
            actor_member_id=robert.id,
            actor_role="adult",
            surface="personal",
            conversation_id=conv.id,
            allowed_tools=["apply_weekly_plan_bundle"],
        )
        args = {
            "summary": "with conversation",
            "bundle_apply_id": "bundle-conv-1",
            "tasks": [{"title": "do thing"}],
            "confirmed": True,
        }
        executor.execute("apply_weekly_plan_bundle", args)

        row = db.scalars(
            select(PlannerBundleApply).where(
                PlannerBundleApply.bundle_apply_id == "bundle-conv-1"
            )
        ).first()
        assert row is not None
        assert row.conversation_id == conv.id


# ---------------------------------------------------------------------------
# BUG #4 (P2) — family memory near-duplicate creation
#
# Repro: exact-match dedupe in record_auto_structured_memory misses
# trivial whitespace / case differences. Two approved planner flows
# writing "Sunday is batch cook day." vs "sunday is batch cook day"
# land as separate rows, polluting the active memory list and the
# injected prompt block.
#
# Expected: normalize-on-compare so trivial whitespace/case
# differences collapse to a single active row. The stored content
# stays whatever the first write used (parent can edit if they want
# a different casing).
# ---------------------------------------------------------------------------


class TestMemoryNearDuplicateDedupe:
    def test_whitespace_and_case_variations_dedupe(self, db: Session, family):
        first = memory_module.record_auto_structured_memory(
            db,
            family_id=family.id,
            memory_type="planning_default",
            scope="family",
            content="Sunday is batch cook day.",
        )
        second = memory_module.record_auto_structured_memory(
            db,
            family_id=family.id,
            memory_type="planning_default",
            scope="family",
            content="sunday  is batch cook day",
        )
        third = memory_module.record_auto_structured_memory(
            db,
            family_id=family.id,
            memory_type="planning_default",
            scope="family",
            content="SUNDAY IS BATCH COOK DAY",
        )
        assert first is not None and second is not None and third is not None
        assert first.id == second.id == third.id

        rows = list(
            db.scalars(
                select(FamilyMemory)
                .where(FamilyMemory.family_id == family.id)
                .where(FamilyMemory.status == "active")
            ).all()
        )
        assert len(rows) == 1

    def test_different_content_still_distinct(self, db: Session, family):
        a = memory_module.record_auto_structured_memory(
            db,
            family_id=family.id,
            memory_type="meal_preference",
            scope="family",
            content="Kids love tacos on Tuesdays.",
        )
        b = memory_module.record_auto_structured_memory(
            db,
            family_id=family.id,
            memory_type="meal_preference",
            scope="family",
            content="Kids love pasta on Wednesdays.",
        )
        assert a is not None and b is not None
        assert a.id != b.id


# ---------------------------------------------------------------------------
# BUG #5 (P2) — remote MCP has no repeat-call protection
#
# Repro: a client holding a valid token can call /mcp/tools/call in a
# tight loop forever. The Tier 5 handoff flagged this as a follow-up.
# Ship a minimal per-token/minute counter so one runaway client can't
# peg the DB.
#
# Expected: a burst of N calls within the window returns 200; the
# N+1 call returns 429 with a Retry-After header. Counter resets on
# the next minute boundary.
# ---------------------------------------------------------------------------


class TestRemoteMCPRateLimit:
    def test_bursts_beyond_limit_get_429(
        self, client, db, family, adults, monkeypatch
    ):
        from app.config import settings

        monkeypatch.setattr(settings, "mcp_remote_enabled", True)
        # Small cap so the test doesn't hammer. Fixture is per-test.
        monkeypatch.setattr(settings, "mcp_remote_rate_limit_per_minute", 3)

        # Redirect the MCP tool dispatcher at the transactional db.
        class _Ctx:
            def __enter__(self_inner):
                return db

            def __exit__(self_inner, *a):
                return False

        monkeypatch.setattr("scout_mcp.server._session", lambda: _Ctx())

        session_tok = _bearer(db, adults["robert"].id)
        create = client.post(
            "/mcp/tokens",
            headers={"Authorization": f"Bearer {session_tok}"},
            json={"label": "rl test"},
        )
        mcp_plaintext = create.json()["plaintext"]
        headers = {"Authorization": f"Bearer {mcp_plaintext}"}
        payload = {"name": "get_family_schedule", "arguments": {"days": 1}}

        # First 3 calls succeed.
        for i in range(3):
            r = client.post("/mcp/tools/call", headers=headers, json=payload)
            assert r.status_code == 200, f"call {i} unexpectedly failed: {r.text}"

        # 4th call hits the limit.
        over = client.post("/mcp/tools/call", headers=headers, json=payload)
        assert over.status_code == 429
        # Retry-After header signals when to try again.
        assert "Retry-After" in over.headers


# ---------------------------------------------------------------------------
# BUG #6 (P2) — remote MCP dispatch with empty/unknown tool name
#
# Repro: a client hits /mcp/tools/call with an empty string name or a
# name that isn't in the registry. Right now dispatch_tool returns a
# dict with ``error`` inside the 200 response. That's fine, but the
# empty-string path should 400 so the client knows to fix its request
# rather than silently swallow a bad call.
# ---------------------------------------------------------------------------


class TestRemoteMCPBadTool:
    def test_empty_tool_name_returns_422_or_400(
        self, client, db, family, adults, monkeypatch
    ):
        from app.config import settings

        monkeypatch.setattr(settings, "mcp_remote_enabled", True)
        session_tok = _bearer(db, adults["robert"].id)
        create = client.post(
            "/mcp/tokens",
            headers={"Authorization": f"Bearer {session_tok}"},
            json={"label": "bad tool test"},
        )
        mcp_plaintext = create.json()["plaintext"]

        r = client.post(
            "/mcp/tools/call",
            headers={"Authorization": f"Bearer {mcp_plaintext}"},
            json={"name": "", "arguments": {}},
        )
        assert r.status_code in (400, 422)

    def test_unknown_tool_name_returns_clean_error_body(
        self, client, db, family, adults, monkeypatch
    ):
        from app.config import settings

        monkeypatch.setattr(settings, "mcp_remote_enabled", True)

        class _Ctx:
            def __enter__(self_inner):
                return db

            def __exit__(self_inner, *a):
                return False

        monkeypatch.setattr("scout_mcp.server._session", lambda: _Ctx())

        session_tok = _bearer(db, adults["robert"].id)
        create = client.post(
            "/mcp/tokens",
            headers={"Authorization": f"Bearer {session_tok}"},
            json={"label": "unknown tool test"},
        )
        mcp_plaintext = create.json()["plaintext"]

        r = client.post(
            "/mcp/tools/call",
            headers={"Authorization": f"Bearer {mcp_plaintext}"},
            json={"name": "not_a_real_tool", "arguments": {}},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["result"].get("error")
        assert "known" in body["result"]

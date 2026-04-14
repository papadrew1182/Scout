"""Tests for Tier 3 features:
  9. Parent coaching via personality_notes
 10. Daily moderation digest
 11. AI cost dashboard / usage rollup
 12. Conversation resume across panel opens
"""

import uuid
from datetime import date, datetime, timedelta

import pytest
import pytz
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.context import (
    _sanitize_parent_notes,
    build_system_prompt,
    load_member_context,
)
from app.ai.pricing import (
    MODEL_PRICING,
    build_usage_report,
    estimate_cost_usd,
)
from app.models.action_items import ParentActionItem
from app.models.ai import AIConversation, AIMessage
from app.models.foundation import FamilyMember, UserAccount
from app.models.scheduled import ScheduledRun
from app.scheduler import (
    MODERATION_DIGEST_HOUR,
    _extract_category,
    _format_12h,
    run_moderation_digest_for_family,
    run_moderation_digest_tick,
)
from app.services.auth_service import hash_password


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_session_token(db: Session, member_id) -> str:
    """Create a user_account + session row and return the bearer token.
    Used by TestClient-based tests that need to hit authenticated
    routes as a specific family member."""
    from app.models.foundation import Session as SessionModel

    account = UserAccount(
        id=uuid.uuid4(),
        family_member_id=member_id,
        email=f"t3-{uuid.uuid4().hex[:8]}@scout.local",
        auth_provider="email",
        password_hash=hash_password("x" * 12),
        is_primary=False,
        is_active=True,
    )
    db.add(account)
    db.flush()

    token = f"tok-{uuid.uuid4().hex}"
    sess = SessionModel(
        user_account_id=account.id,
        token=token,
        expires_at=datetime.now(pytz.UTC).replace(tzinfo=None) + timedelta(hours=1),
    )
    db.add(sess)
    db.commit()
    return token


@pytest.fixture
def client(db):
    """TestClient wired to the per-test transactional session so the
    endpoint sees the same rows the tests inserted."""
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
# Feature 9 — Parent coaching (personality_notes)
# ---------------------------------------------------------------------------


class TestPersonalityNotesSanitizer:
    def test_empty_and_none(self):
        assert _sanitize_parent_notes(None) == ""
        assert _sanitize_parent_notes("") == ""
        assert _sanitize_parent_notes("   ") == ""

    def test_strips_control_chars_and_collapses_whitespace(self):
        raw = "Be gentle.\nUse encouragement.\r\nAvoid sarcasm.\t\tSlow down."
        out = _sanitize_parent_notes(raw)
        # Control chars become spaces, runs collapse.
        assert "\n" not in out
        assert "\r" not in out
        assert "\t" not in out
        assert "  " not in out
        assert "Be gentle." in out
        assert "Avoid sarcasm." in out

    def test_caps_length_and_suffixes_ellipsis(self):
        raw = "x" * 2000
        out = _sanitize_parent_notes(raw)
        assert len(out) <= 801  # 800 + single-char ellipsis
        assert out.endswith("…")


class TestPersonalityNotesInPrompt:
    def test_child_surface_includes_personality_notes(
        self, db: Session, family, children
    ):
        sadie = children["sadie"]
        sadie.personality_notes = "Very sensitive to failure. Celebrate small wins."
        sadie.learning_notes = "Strong reader, weak at long division."
        db.flush()

        ctx = load_member_context(db, family_id=family.id, member_id=sadie.id)
        prompt = build_system_prompt(ctx, surface="child")
        assert "Very sensitive to failure" in prompt
        assert "Celebrate small wins" in prompt
        # Learning notes still present.
        assert "weak at long division" in prompt

    def test_adult_surface_does_not_leak_child_personality_notes(
        self, db: Session, family, adults, children
    ):
        # Set personality notes on Sadie, then load the ADULT's
        # context. Adults never pull child personality notes into
        # their own system prompt.
        sadie = children["sadie"]
        sadie.personality_notes = "Very sensitive to failure."
        db.flush()

        robert = adults["robert"]
        ctx = load_member_context(db, family_id=family.id, member_id=robert.id)
        prompt = build_system_prompt(ctx, surface="personal")
        assert "sensitive to failure" not in prompt

    def test_empty_personality_notes_do_not_add_block(
        self, db: Session, family, children
    ):
        sadie = children["sadie"]
        sadie.personality_notes = None
        db.flush()

        ctx = load_member_context(db, family_id=family.id, member_id=sadie.id)
        prompt = build_system_prompt(ctx, surface="child")
        assert "Coaching notes from this child's parents" not in prompt


class TestPersonalityNotesRoute:
    def test_adult_can_set_personality_notes(self, client, db, family, adults, children):
        robert = adults["robert"]
        sadie = children["sadie"]
        token = _build_session_token(db, robert.id)

        r = client.patch(
            f"/families/{family.id}/members/{sadie.id}/learning",
            headers={"Authorization": f"Bearer {token}"},
            json={"personality_notes": "Use humor. Never pressure."},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["personality_notes"] == "Use humor. Never pressure."

    def test_child_cannot_set_personality_notes(
        self, client, db, family, children
    ):
        sadie = children["sadie"]
        token = _build_session_token(db, sadie.id)

        r = client.patch(
            f"/families/{family.id}/members/{sadie.id}/learning",
            headers={"Authorization": f"Bearer {token}"},
            json={"personality_notes": "I want to edit my own notes"},
        )
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# Feature 10 — Daily moderation digest
# ---------------------------------------------------------------------------


def _seed_moderation_alerts(
    db: Session, *, family_id, child_member_id, category: str, count: int
):
    """Insert N moderation_alert rows so the digest aggregator has
    something to roll up. Uses the exact title format the orchestrator
    creates so the category parser works end-to-end."""
    rows = []
    for _ in range(count):
        a = ParentActionItem(
            family_id=family_id,
            created_by_member_id=child_member_id,
            action_type="moderation_alert",
            title=f"Scout blocked a sensitive message ({category})",
            detail="(private)",
            entity_type="ai_conversation",
            entity_id=uuid.uuid4(),
        )
        db.add(a)
        rows.append(a)
    db.flush()
    return rows


class TestModerationDigest:
    def test_extract_category_parses_trailing_parens(self):
        assert _extract_category(
            "Scout blocked a sensitive message (profanity)"
        ) == "profanity"
        assert _extract_category("untagged title") == "unknown"
        assert _extract_category("") == "unknown"

    def test_format_12h_no_leading_zero(self):
        dt = datetime(2026, 4, 13, 9, 5)
        assert _format_12h(dt) == "9:05 AM"
        dt2 = datetime(2026, 4, 13, 18, 42)
        assert _format_12h(dt2) == "6:42 PM"

    def test_zero_events_creates_no_digest(self, db: Session, family, adults):
        out = run_moderation_digest_for_family(
            db, family_id=family.id, run_date=date(2026, 4, 13), tz=pytz.UTC
        )
        assert out["status"] == "success"
        assert out["created_digest"] is False
        assert out["event_count"] == 0

        digests = list(
            db.scalars(
                select(ParentActionItem)
                .where(ParentActionItem.family_id == family.id)
                .where(ParentActionItem.action_type == "moderation_digest")
            ).all()
        )
        assert digests == []

    def test_one_event_creates_no_digest(
        self, db: Session, family, adults, children
    ):
        _seed_moderation_alerts(
            db, family_id=family.id, child_member_id=children["sadie"].id,
            category="profanity", count=1,
        )
        out = run_moderation_digest_for_family(
            db, family_id=family.id, run_date=date.today(), tz=pytz.UTC
        )
        assert out["created_digest"] is False
        assert out["event_count"] == 1
        # No digest row.
        digests = list(
            db.scalars(
                select(ParentActionItem)
                .where(ParentActionItem.family_id == family.id)
                .where(ParentActionItem.action_type == "moderation_digest")
            ).all()
        )
        assert digests == []

    def test_two_plus_events_creates_digest_without_raw_text(
        self, db: Session, family, adults, children
    ):
        _seed_moderation_alerts(
            db, family_id=family.id, child_member_id=children["sadie"].id,
            category="profanity", count=2,
        )
        _seed_moderation_alerts(
            db, family_id=family.id, child_member_id=children["townes"].id,
            category="nsfw_redirect", count=1,
        )
        # 3 total events → above threshold → should create digest.
        out = run_moderation_digest_for_family(
            db, family_id=family.id, run_date=date.today(), tz=pytz.UTC
        )
        assert out["created_digest"] is True
        assert out["event_count"] == 3

        digest = db.scalars(
            select(ParentActionItem)
            .where(ParentActionItem.family_id == family.id)
            .where(ParentActionItem.action_type == "moderation_digest")
        ).first()
        assert digest is not None
        assert "3" in digest.title
        # Privacy: detail must not echo any part of the raw
        # title-unfortunately-there's no "raw content" in seeding, but
        # we assert the aggregator doesn't copy alert titles verbatim.
        assert "Scout blocked a sensitive message" not in (digest.detail or "")
        # Must mention both children and both categories.
        assert "Sadie" in (digest.detail or "")
        assert "Townes" in (digest.detail or "")
        assert "profanity" in (digest.detail or "")
        assert "nsfw_redirect" in (digest.detail or "")

    def test_dedupe_via_scheduled_runs(
        self, db: Session, family, adults, children
    ):
        _seed_moderation_alerts(
            db, family_id=family.id, child_member_id=children["sadie"].id,
            category="profanity", count=3,
        )
        run_date = date.today()

        first = run_moderation_digest_for_family(
            db, family_id=family.id, run_date=run_date, tz=pytz.UTC
        )
        assert first["status"] == "success"

        second = run_moderation_digest_for_family(
            db, family_id=family.id, run_date=run_date, tz=pytz.UTC
        )
        assert second["status"] == "skipped"
        assert second["reason"] == "already_ran_today"

        # Only one digest row even after second invocation.
        digests = list(
            db.scalars(
                select(ParentActionItem)
                .where(ParentActionItem.family_id == family.id)
                .where(ParentActionItem.action_type == "moderation_digest")
            ).all()
        )
        assert len(digests) == 1

    def test_tick_fires_only_at_local_hour(
        self, db: Session, family, adults, children
    ):
        # Seed enough alerts to trigger a digest if the tick fires.
        _seed_moderation_alerts(
            db, family_id=family.id, child_member_id=children["sadie"].id,
            category="profanity", count=3,
        )
        family.timezone = "America/Chicago"
        db.flush()

        tz = pytz.timezone("America/Chicago")

        # Wrong hour -> no results.
        noon = tz.localize(datetime(2026, 4, 13, 12, 0, 0)).astimezone(pytz.UTC)
        assert run_moderation_digest_tick(db, now_utc=noon) == []

        # Right hour -> one result for our single family.
        local = tz.localize(
            datetime(2026, 4, 13, MODERATION_DIGEST_HOUR, 0, 0)
        ).astimezone(pytz.UTC)
        results = run_moderation_digest_tick(db, now_utc=local)
        assert len(results) == 1
        assert results[0]["status"] == "success"


# ---------------------------------------------------------------------------
# Feature 11 — AI cost dashboard
# ---------------------------------------------------------------------------


def _seed_ai_message(
    db: Session,
    *,
    conversation_id,
    role: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    content: str = "ok",
):
    msg = AIMessage(
        conversation_id=conversation_id,
        role=role,
        content=content,
        model=model,
        token_usage={"input": input_tokens, "output": output_tokens},
    )
    db.add(msg)
    db.flush()
    return msg


class TestCostEstimator:
    def test_known_model_uses_registered_rate(self):
        # Sonnet 4 is 3/15 per 1M. 1M in + 1M out = $18.
        cost = estimate_cost_usd("claude-sonnet-4-20250514", 1_000_000, 1_000_000)
        assert abs(cost - 18.0) < 0.001

    def test_unknown_model_falls_back_to_default(self):
        # Fallback rate is 3/15 in the built-in table.
        cost = estimate_cost_usd("totally-made-up-model", 1_000_000, 1_000_000)
        assert cost > 0

    def test_zero_tokens_is_zero_cost(self):
        assert estimate_cost_usd("claude-sonnet-4-20250514", 0, 0) == 0.0


class TestUsageReport:
    def test_empty_family_returns_zeroed_window(self, db: Session, family):
        report = build_usage_report(db, family_id=family.id, days=7)
        assert report["total_messages"] == 0
        assert report["total_tokens"] == {"input": 0, "output": 0}
        assert report["approx_cost_usd"] == 0.0
        assert len(report["by_day"]) == 7
        # All days present and zero.
        for d in report["by_day"]:
            assert d["messages"] == 0

    def test_rollup_by_day_model_and_member(
        self, db: Session, family, adults
    ):
        robert = adults["robert"]
        megan = adults["megan"]
        conv1 = AIConversation(
            family_id=family.id,
            family_member_id=robert.id,
            surface="personal",
        )
        conv2 = AIConversation(
            family_id=family.id,
            family_member_id=megan.id,
            surface="personal",
        )
        db.add_all([conv1, conv2])
        db.flush()

        _seed_ai_message(
            db, conversation_id=conv1.id, role="assistant",
            model="claude-sonnet-4-20250514",
            input_tokens=1000, output_tokens=500,
        )
        _seed_ai_message(
            db, conversation_id=conv1.id, role="assistant",
            model="claude-sonnet-4-20250514",
            input_tokens=2000, output_tokens=800,
        )
        _seed_ai_message(
            db, conversation_id=conv2.id, role="assistant",
            model="claude-sonnet-4-20250514",
            input_tokens=500, output_tokens=200,
        )
        # User + tool rows must NOT be counted.
        _seed_ai_message(
            db, conversation_id=conv1.id, role="user",
            model=None, input_tokens=0, output_tokens=0, content="hi",
        )

        report = build_usage_report(db, family_id=family.id, days=7)
        assert report["total_messages"] == 3
        assert report["total_tokens"]["input"] == 3500
        assert report["total_tokens"]["output"] == 1500
        # At least one by_model row, ordered by cost desc.
        assert len(report["by_model"]) >= 1
        assert report["by_model"][0]["model"] == "claude-sonnet-4-20250514"
        # Both members attributed.
        names = {m["first_name"] for m in report["by_member"]}
        assert names == {"Robert", "Megan"}

    def test_missing_token_usage_handled(self, db: Session, family, adults):
        robert = adults["robert"]
        conv = AIConversation(
            family_id=family.id, family_member_id=robert.id, surface="personal"
        )
        db.add(conv)
        db.flush()
        msg = AIMessage(
            conversation_id=conv.id,
            role="assistant",
            content="no usage recorded",
            model=None,
            token_usage=None,  # legacy row
        )
        db.add(msg)
        db.flush()

        report = build_usage_report(db, family_id=family.id, days=7)
        # It's counted but with zero tokens / zero cost.
        assert report["total_messages"] == 1
        assert report["total_tokens"] == {"input": 0, "output": 0}
        assert report["approx_cost_usd"] == 0.0

    def test_soft_cap_warning_flag(self, db: Session, family, adults):
        robert = adults["robert"]
        conv = AIConversation(
            family_id=family.id, family_member_id=robert.id, surface="personal"
        )
        db.add(conv)
        db.flush()
        # 10M in + 10M out at sonnet rates = $180
        _seed_ai_message(
            db, conversation_id=conv.id, role="assistant",
            model="claude-sonnet-4-20250514",
            input_tokens=10_000_000, output_tokens=10_000_000,
        )
        report = build_usage_report(
            db, family_id=family.id, days=7, soft_cap_usd=5.0
        )
        assert report["cap_warning"] is True
        assert report["approx_cost_usd"] >= 5.0


class TestUsageRouteParentOnly:
    def test_adult_can_read_usage(self, client, db, family, adults):
        token = _build_session_token(db, adults["robert"].id)
        r = client.get(
            "/api/ai/usage",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert "total_messages" in body
        assert "approx_cost_usd" in body

    def test_child_cannot_read_usage(self, client, db, family, children):
        token = _build_session_token(db, children["sadie"].id)
        r = client.get(
            "/api/ai/usage",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# Feature 12 — Conversation resume
# ---------------------------------------------------------------------------


class TestResumableConversation:
    def _seed_conversation(
        self,
        db: Session,
        *,
        family_id,
        member_id,
        surface: str = "personal",
        kind: str = "chat",
        status: str = "active",
        updated_minutes_ago: int = 5,
        user_message: str = "hi scout",
        assistant_message: str = "hi back",
        last_model: str = "claude-sonnet-4-20250514",
    ) -> AIConversation:
        # Set updated_at on INSERT — the trg_ai_conversations_updated_at
        # BEFORE UPDATE trigger stomps any post-insert mutation, so we
        # have to pass the backdated value through the constructor.
        now = datetime.now(pytz.UTC).replace(tzinfo=None)
        backdated = now - timedelta(minutes=updated_minutes_ago)
        conv = AIConversation(
            family_id=family_id,
            family_member_id=member_id,
            surface=surface,
            conversation_kind=kind,
            status=status,
            created_at=backdated,
            updated_at=backdated,
        )
        db.add(conv)
        db.flush()

        db.add(
            AIMessage(
                conversation_id=conv.id,
                role="user",
                content=user_message,
            )
        )
        db.flush()
        db.add(
            AIMessage(
                conversation_id=conv.id,
                role="assistant",
                content=assistant_message,
                model=last_model,
                token_usage={"input": 50, "output": 20},
            )
        )
        db.flush()
        return conv

    def test_resumes_recent_safe_conversation(
        self, client, db, family, adults
    ):
        robert = adults["robert"]
        conv = self._seed_conversation(
            db, family_id=family.id, member_id=robert.id,
            updated_minutes_ago=5, user_message="plan my week",
        )
        token = _build_session_token(db, robert.id)
        r = client.get(
            "/api/ai/conversations/resumable?surface=personal",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["conversation_id"] == str(conv.id)
        assert "plan my week" in (body["preview"] or "")

    def test_stale_conversation_not_resumed(
        self, client, db, family, adults
    ):
        robert = adults["robert"]
        self._seed_conversation(
            db, family_id=family.id, member_id=robert.id,
            updated_minutes_ago=120,  # way past the 30 min window
        )
        token = _build_session_token(db, robert.id)
        r = client.get(
            "/api/ai/conversations/resumable?surface=personal",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        assert r.json()["conversation_id"] is None

    def test_moderation_conversation_excluded(
        self, client, db, family, adults
    ):
        robert = adults["robert"]
        self._seed_conversation(
            db, family_id=family.id, member_id=robert.id,
            kind="moderation",
        )
        token = _build_session_token(db, robert.id)
        r = client.get(
            "/api/ai/conversations/resumable?surface=personal",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.json()["conversation_id"] is None

    def test_ended_conversation_excluded(
        self, client, db, family, adults
    ):
        robert = adults["robert"]
        self._seed_conversation(
            db, family_id=family.id, member_id=robert.id,
            status="ended",
        )
        token = _build_session_token(db, robert.id)
        r = client.get(
            "/api/ai/conversations/resumable?surface=personal",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.json()["conversation_id"] is None

    def test_pending_confirmation_excluded(
        self, client, db, family, adults
    ):
        robert = adults["robert"]
        backdated = datetime.now(pytz.UTC).replace(tzinfo=None) - timedelta(minutes=2)
        conv = AIConversation(
            family_id=family.id,
            family_member_id=robert.id,
            surface="personal",
            conversation_kind="tool",
            created_at=backdated,
            updated_at=backdated,
        )
        db.add(conv)
        db.flush()
        db.add(
            AIMessage(
                conversation_id=conv.id,
                role="user",
                content="delete all meals",
            )
        )
        db.flush()
        db.add(
            AIMessage(
                conversation_id=conv.id,
                role="assistant",
                content="I need to confirm…",
                tool_calls=[{"id": "t1", "name": "destructive_tool", "input": {}}],
                model="claude-sonnet-4-20250514",
            )
        )
        db.flush()
        db.add(
            AIMessage(
                conversation_id=conv.id,
                role="tool",
                tool_results={
                    "tool_use_id": "t1",
                    "result": {"confirmation_required": True},
                },
            )
        )
        db.flush()

        token = _build_session_token(db, robert.id)
        r = client.get(
            "/api/ai/conversations/resumable?surface=personal",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.json()["conversation_id"] is None

    def test_end_conversation_flips_status(
        self, client, db, family, adults
    ):
        robert = adults["robert"]
        conv = self._seed_conversation(
            db, family_id=family.id, member_id=robert.id,
        )
        token = _build_session_token(db, robert.id)
        r = client.post(
            f"/api/ai/conversations/{conv.id}/end",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "ended"

        # And the row is actually updated in the DB.
        db.refresh(conv)
        assert conv.status == "ended"

    def test_different_surfaces_dont_cross_pollinate(
        self, client, db, family, adults
    ):
        robert = adults["robert"]
        self._seed_conversation(
            db, family_id=family.id, member_id=robert.id, surface="parent",
        )
        token = _build_session_token(db, robert.id)
        r = client.get(
            "/api/ai/conversations/resumable?surface=personal",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.json()["conversation_id"] is None

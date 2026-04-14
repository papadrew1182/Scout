"""Tests for Tier 1 proactive features: scheduler, morning brief,
off-track insight, transcribe endpoint."""

import uuid
from datetime import date, datetime, timedelta

import pytest
import pytz
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.insights import (
    _rule_based_narrative,
    get_off_track_insight,
    invalidate_off_track_insight,
)
from app.models.action_items import ParentActionItem
from app.models.foundation import UserAccount
from app.models.scheduled import AIDailyInsight, ScheduledRun
from app.scheduler import (
    run_morning_brief_for_member,
    run_morning_brief_tick,
)
from app.services.auth_service import hash_password


# ---------------------------------------------------------------------------
# Scheduler: morning brief idempotency, timezone, dedupe
# ---------------------------------------------------------------------------


class _FakeBrief:
    @staticmethod
    def generate_daily_brief(db, family_id, member_id):
        return {
            "brief": f"Brief for {member_id} on {date.today().isoformat()}",
            "date": date.today().isoformat(),
            "model": "fake-haiku",
        }


@pytest.fixture
def fake_brief(monkeypatch):
    """Replace orchestrator.generate_daily_brief so tests never hit
    Claude. The scheduler is wired to import orchestrator lazily, so
    we patch the module attribute after import."""
    import app.ai.orchestrator as orchestrator_mod

    monkeypatch.setattr(
        orchestrator_mod,
        "generate_daily_brief",
        _FakeBrief.generate_daily_brief,
    )
    yield


class TestMorningBriefIdempotency:
    def test_run_creates_action_item_and_mutex(
        self, db: Session, family, adults, fake_brief
    ):
        andrew = adults["robert"]
        run_date = date(2026, 4, 13)

        result = run_morning_brief_for_member(
            db,
            family_id=family.id,
            member_id=andrew.id,
            run_date=run_date,
        )

        assert result["status"] == "success"
        assert result["model"] == "fake-haiku"

        # Mutex row exists with success status
        mutex = db.scalars(
            select(ScheduledRun)
            .where(ScheduledRun.job_name == "morning_brief")
            .where(ScheduledRun.family_id == family.id)
            .where(ScheduledRun.member_id == andrew.id)
            .where(ScheduledRun.run_date == run_date)
        ).first()
        assert mutex is not None
        assert mutex.status == "success"

        # Action item exists
        action = db.scalars(
            select(ParentActionItem)
            .where(ParentActionItem.family_id == family.id)
            .where(ParentActionItem.action_type == "daily_brief")
        ).first()
        assert action is not None
        assert action.title == "Morning brief ready"
        assert action.detail  # non-empty

    def test_rerun_same_day_is_skipped(
        self, db: Session, family, adults, fake_brief
    ):
        andrew = adults["robert"]
        run_date = date(2026, 4, 13)

        first = run_morning_brief_for_member(
            db, family_id=family.id, member_id=andrew.id, run_date=run_date,
        )
        assert first["status"] == "success"

        # Second call for the same (member, day) must skip via the mutex.
        second = run_morning_brief_for_member(
            db, family_id=family.id, member_id=andrew.id, run_date=run_date,
        )
        assert second["status"] == "skipped"
        assert second["reason"] == "already_ran_today"

        # Only one action item row exists.
        actions = list(db.scalars(
            select(ParentActionItem)
            .where(ParentActionItem.action_type == "daily_brief")
        ).all())
        assert len(actions) == 1

    def test_different_days_both_run(
        self, db: Session, family, adults, fake_brief
    ):
        andrew = adults["robert"]

        r1 = run_morning_brief_for_member(
            db, family_id=family.id, member_id=andrew.id, run_date=date(2026, 4, 13)
        )
        r2 = run_morning_brief_for_member(
            db, family_id=family.id, member_id=andrew.id, run_date=date(2026, 4, 14)
        )
        assert r1["status"] == "success"
        assert r2["status"] == "success"

        actions = list(db.scalars(
            select(ParentActionItem)
            .where(ParentActionItem.action_type == "daily_brief")
        ).all())
        assert len(actions) == 2


class TestMorningBriefTick:
    def test_tick_at_6am_local_creates_briefs(
        self, db: Session, family, adults, fake_brief
    ):
        # Chicago family: 6 AM local = 11 AM UTC
        family.timezone = "America/Chicago"
        db.flush()

        central = pytz.timezone("America/Chicago")
        local_6am = central.localize(datetime(2026, 4, 13, 6, 0, 0))
        now_utc = local_6am.astimezone(pytz.UTC)

        results = run_morning_brief_tick(db, now_utc=now_utc)

        # Two adults in the fixture → two briefs
        successes = [r for r in results if r["status"] == "success"]
        assert len(successes) == 2

    def test_tick_at_wrong_hour_does_nothing(
        self, db: Session, family, adults, fake_brief
    ):
        family.timezone = "America/Chicago"
        db.flush()

        central = pytz.timezone("America/Chicago")
        local_noon = central.localize(datetime(2026, 4, 13, 12, 0, 0))
        now_utc = local_noon.astimezone(pytz.UTC)

        results = run_morning_brief_tick(db, now_utc=now_utc)
        assert results == []

        # No action items created
        actions = list(db.scalars(
            select(ParentActionItem)
            .where(ParentActionItem.action_type == "daily_brief")
        ).all())
        assert len(actions) == 0

    def test_tick_respects_different_timezones(
        self, db: Session, family, adults, fake_brief
    ):
        # Put the Roberts family in Tokyo. 6 AM Tokyo = 21:00 previous
        # day UTC. A tick at that UTC time should fire for Tokyo but
        # not for anyone else.
        family.timezone = "Asia/Tokyo"
        db.flush()

        tokyo = pytz.timezone("Asia/Tokyo")
        local_6am = tokyo.localize(datetime(2026, 4, 13, 6, 0, 0))
        now_utc = local_6am.astimezone(pytz.UTC)

        results = run_morning_brief_tick(db, now_utc=now_utc)
        successes = [r for r in results if r["status"] == "success"]
        assert len(successes) == 2  # both adults


class TestBriefFailureCaptured:
    def test_ai_failure_records_error_mutex_no_action_item(
        self, db: Session, family, adults, monkeypatch
    ):
        import app.ai.orchestrator as orchestrator_mod

        def boom(*a, **kw):
            raise RuntimeError("anthropic unreachable")

        monkeypatch.setattr(orchestrator_mod, "generate_daily_brief", boom)

        andrew = adults["robert"]
        result = run_morning_brief_for_member(
            db, family_id=family.id, member_id=andrew.id, run_date=date(2026, 4, 13),
        )
        assert result["status"] == "error"

        # Mutex row exists with status=error — prevents a retry storm.
        err = db.scalars(
            select(ScheduledRun)
            .where(ScheduledRun.job_name == "morning_brief")
            .where(ScheduledRun.status == "error")
        ).first()
        assert err is not None

        # No action item should have been created.
        actions = list(db.scalars(
            select(ParentActionItem)
            .where(ParentActionItem.action_type == "daily_brief")
        ).all())
        assert len(actions) == 0


# ---------------------------------------------------------------------------
# Off-track insight: caching, fallback, content constraints
# ---------------------------------------------------------------------------


class TestOffTrackInsight:
    def test_fallback_used_when_no_anthropic_key(
        self, db: Session, family, monkeypatch
    ):
        # Force ai_available = False by blanking the key
        from app.config import settings
        monkeypatch.setattr(settings, "anthropic_api_key", "")

        health = {
            "status": "at_risk",
            "reasons": [
                {"type": "overdue_bills", "count": 2},
                {"type": "pending_actions", "count": 5},
            ],
        }
        children = [
            {"id": "x", "name": "Sadie", "tasks_total": 4, "tasks_completed": 1, "weekly_wins": 2},
        ]

        r = get_off_track_insight(
            db,
            family_id=family.id,
            health=health,
            child_statuses=children,
            as_of=date(2026, 4, 13),
        )
        assert r["status"] == "at_risk"
        assert r["source"] == "fallback"
        assert "overdue bills" in r["narrative"].lower()

    def test_cached_result_returned_on_second_call(
        self, db: Session, family, monkeypatch
    ):
        from app.config import settings
        monkeypatch.setattr(settings, "anthropic_api_key", "")

        health = {"status": "on_track", "reasons": []}
        children = []

        # First call → fallback + NOT cached (fallbacks intentionally
        # aren't cached so they'll retry next time the AI might work).
        r1 = get_off_track_insight(
            db, family_id=family.id, health=health,
            child_statuses=children, as_of=date(2026, 4, 13),
        )
        assert r1["source"].startswith("fallback")

        # Now force-insert a cached row to simulate a previous AI success.
        row = AIDailyInsight(
            family_id=family.id,
            insight_type="off_track",
            as_of_date=date(2026, 4, 13),
            status="on_track",
            content="All quiet today.",
            model="fake",
        )
        db.add(row)
        db.commit()

        r2 = get_off_track_insight(
            db, family_id=family.id, health=health,
            child_statuses=children, as_of=date(2026, 4, 13),
        )
        assert r2["source"] == "cached"
        assert r2["narrative"] == "All quiet today."

    def test_ai_success_caches_result(
        self, db: Session, family, monkeypatch
    ):
        # Inject a fake provider so the AI branch runs.
        from app.config import settings
        monkeypatch.setattr(settings, "anthropic_api_key", "fake")

        class _FakeProvider:
            def chat(self, **kwargs):
                class R:
                    content = "Two tasks remain and three action items need review."
                    model = "fake-haiku"
                return R()

        import app.ai.provider as provider_mod
        monkeypatch.setattr(provider_mod, "get_provider", lambda: _FakeProvider())

        health = {
            "status": "at_risk",
            "reasons": [
                {"type": "incomplete_tasks", "child": "Sadie", "count": 2},
                {"type": "pending_actions", "count": 3},
            ],
        }
        children = [{"id": "x", "name": "Sadie", "tasks_total": 4, "tasks_completed": 2, "weekly_wins": 1}]

        r = get_off_track_insight(
            db, family_id=family.id, health=health,
            child_statuses=children, as_of=date(2026, 4, 13),
        )
        assert r["source"] == "ai"
        assert "tasks" in r["narrative"].lower()
        assert r["model"] == "fake-haiku"

        # Cache row exists
        cached = db.scalars(
            select(AIDailyInsight)
            .where(AIDailyInsight.family_id == family.id)
            .where(AIDailyInsight.as_of_date == date(2026, 4, 13))
        ).first()
        assert cached is not None
        assert cached.content == r["narrative"]

    def test_rule_based_narrative_for_on_track_shape(self):
        health = {"status": "on_track", "reasons": []}
        children = [
            {"id": "x", "name": "Sadie", "tasks_total": 3, "tasks_completed": 3, "weekly_wins": 3},
        ]
        text = _rule_based_narrative(health=health, child_statuses=children)
        assert "complete" in text.lower() or "quiet" in text.lower()


# ---------------------------------------------------------------------------
# Transcribe endpoint: 501 when no key, contract when stubbed
# ---------------------------------------------------------------------------


class TestTranscribeEndpointGate:
    def test_501_when_key_not_set(self, client, db, family, adults, monkeypatch):
        from app.config import settings
        monkeypatch.setattr(settings, "transcribe_api_key", "")

        # Build a dummy auth session for the adult.
        andrew = adults["robert"]
        token = _build_session(db, andrew.id)

        r = client.post(
            "/api/ai/transcribe",
            files={"audio": ("v.webm", b"\x00\x01\x02", "audio/webm")},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 501

    def test_empty_upload_400(self, client, db, family, adults, monkeypatch):
        from app.config import settings
        monkeypatch.setattr(settings, "transcribe_api_key", "fake-key")

        andrew = adults["robert"]
        token = _build_session(db, andrew.id)

        r = client.post(
            "/api/ai/transcribe",
            files={"audio": ("v.webm", b"", "audio/webm")},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 400

    def test_success_with_stubbed_provider(
        self, client, db, family, adults, monkeypatch
    ):
        from app.config import settings
        monkeypatch.setattr(settings, "transcribe_api_key", "fake-key")

        from app.ai import transcribe as transcribe_mod

        class _StubResult:
            text = "hello from the stub"
            provider = "stub"
            model = "whisper-large-v3"
            duration_ms = 42

        def fake_transcribe(audio, content_type):
            return _StubResult()

        monkeypatch.setattr(transcribe_mod, "transcribe_audio", fake_transcribe)

        andrew = adults["robert"]
        token = _build_session(db, andrew.id)

        r = client.post(
            "/api/ai/transcribe",
            files={"audio": ("v.webm", b"\x00\x01\x02\x03", "audio/webm")},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["text"] == "hello from the stub"
        assert body["provider"] == "stub"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_session(db: Session, member_id) -> str:
    """Create a user_account + session token for tests that need to
    hit authenticated routes via the TestClient."""
    from app.models.foundation import Session as SessionModel

    account = UserAccount(
        id=uuid.uuid4(),
        family_member_id=member_id,
        email=f"test-{uuid.uuid4().hex[:8]}@scout.local",
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
    """FastAPI TestClient wired to the existing per-test transactional
    Session so the endpoint sees the same rows tests have inserted."""
    from fastapi.testclient import TestClient
    from app.main import app
    from app.database import get_db

    def override_get_db():
        try:
            yield db
        finally:
            pass  # do not close — conftest manages it

    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    try:
        yield c
    finally:
        app.dependency_overrides.pop(get_db, None)

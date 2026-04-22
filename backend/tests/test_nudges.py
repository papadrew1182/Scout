"""Sprint 05 Phase 1 - nudges engine tests."""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, time, timedelta, timezone

import pytest
import pytz
from sqlalchemy.orm import Session

from app.models.action_items import ParentActionItem
from app.models.calendar import Event, EventAttendee
from app.models.foundation import Session as SessionModel, UserAccount
from app.models.life_management import ChoreTemplate, Routine, TaskInstance
from app.models.nudges import NudgeDispatch, NudgeDispatchItem
from app.models.personal_tasks import PersonalTask
from app.models.push import PushDelivery, PushDevice
from app.models.quiet_hours import QuietHoursFamily
from app.services import ai_personality_service, nudges_service
from app.services.auth_service import hash_password


def _utcnow() -> datetime:
    # tz-aware; compare-safe against Postgres-hydrated timestamptz values
    return datetime.now(timezone.utc)


def _make_account_and_token(db: Session, member_id, email: str) -> str:
    """Create a UserAccount + Session and return the bearer token.

    Lifted from test_ai_conversation_resume.py (Sprint 04 Phase 1) so
    HTTP tests in this file can authenticate without depending on
    that module's fixture.
    """
    account = UserAccount(
        id=uuid.uuid4(),
        family_member_id=member_id,
        email=email,
        auth_provider="email",
        password_hash=hash_password("x" * 12),
        is_primary=True,
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
    """TestClient with the request-scoped db session overridden so the
    route sees the same data the test seeds."""
    from fastapi.testclient import TestClient

    from app.database import get_db
    from app.main import app

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    try:
        yield c
    finally:
        app.dependency_overrides.clear()


def _force_compose_fallback(monkeypatch):
    """Force compose_body's orchestrator call to raise so tests that
    assert on specific body text deterministically hit the fixed-template
    fallback path. Used by TestDispatchBundles and TestCrossMidnightDedupe
    cases that care about body content regardless of whether the test
    env has an AI key configured."""
    from app.ai import orchestrator as orch

    def raising(**kwargs):
        raise RuntimeError("test: force fallback")

    monkeypatch.setattr(orch, "generate_nudge_body", raising)


class TestScanOverdueTasks:
    def test_overdue_task_produces_one_proposal_for_the_assignee(
        self, db: Session, family, adults
    ):
        andrew = adults["robert"]
        now = _utcnow()
        task = PersonalTask(
            family_id=family.id,
            assigned_to=andrew.id,
            title="Take out the trash",
            status="pending",
            due_at=now - timedelta(hours=1),
        )
        db.add(task)
        db.commit()

        proposals = nudges_service.scan_overdue_tasks(db, now)

        assert len(proposals) == 1
        p = proposals[0]
        assert p.family_member_id == andrew.id
        assert p.trigger_kind == "overdue_task"
        assert p.trigger_entity_kind == "personal_task"
        assert p.trigger_entity_id == task.id
        assert p.context["title"] == "Take out the trash"
        assert p.severity == "normal"

    def test_completed_task_is_ignored(self, db: Session, family, adults):
        andrew = adults["robert"]
        now = _utcnow()
        db.add(
            PersonalTask(
                family_id=family.id,
                assigned_to=andrew.id,
                title="Already done",
                status="done",
                due_at=now - timedelta(hours=2),
                completed_at=now - timedelta(hours=1),
            )
        )
        db.commit()

        assert nudges_service.scan_overdue_tasks(db, now) == []

    def test_future_task_is_ignored(self, db: Session, family, adults):
        andrew = adults["robert"]
        now = _utcnow()
        db.add(
            PersonalTask(
                family_id=family.id,
                assigned_to=andrew.id,
                title="Later",
                status="pending",
                due_at=now + timedelta(hours=3),
            )
        )
        db.commit()

        assert nudges_service.scan_overdue_tasks(db, now) == []


class TestScanUpcomingEvents:
    def test_event_within_lead_window_produces_proposal_for_each_attendee(
        self, db: Session, family, adults
    ):
        andrew = adults["robert"]
        megan = adults["megan"]
        now = _utcnow()
        event = Event(
            family_id=family.id,
            title="Pediatrician appointment",
            starts_at=now + timedelta(minutes=20),
            ends_at=now + timedelta(minutes=50),
        )
        db.add(event)
        db.flush()
        db.add_all(
            [
                EventAttendee(event_id=event.id, family_member_id=andrew.id),
                EventAttendee(event_id=event.id, family_member_id=megan.id),
            ]
        )
        db.commit()

        proposals = nudges_service.scan_upcoming_events(db, now, lead_minutes=30)

        assert len(proposals) == 2
        member_ids = {p.family_member_id for p in proposals}
        assert member_ids == {andrew.id, megan.id}
        for p in proposals:
            assert p.trigger_kind == "upcoming_event"
            assert p.trigger_entity_kind == "event"
            assert p.trigger_entity_id == event.id
            assert p.context["title"] == "Pediatrician appointment"
            assert p.severity == "normal"

    def test_event_outside_lead_window_is_ignored(
        self, db: Session, family, adults
    ):
        andrew = adults["robert"]
        now = _utcnow()
        event = Event(
            family_id=family.id,
            title="Way out",
            starts_at=now + timedelta(hours=5),
            ends_at=now + timedelta(hours=6),
        )
        db.add(event)
        db.flush()
        db.add(EventAttendee(event_id=event.id, family_member_id=andrew.id))
        db.commit()

        assert nudges_service.scan_upcoming_events(db, now, lead_minutes=30) == []

    def test_past_event_is_ignored(self, db: Session, family, adults):
        andrew = adults["robert"]
        now = _utcnow()
        event = Event(
            family_id=family.id,
            title="Already happened",
            starts_at=now - timedelta(hours=1),
            ends_at=now - timedelta(minutes=30),
        )
        db.add(event)
        db.flush()
        db.add(EventAttendee(event_id=event.id, family_member_id=andrew.id))
        db.commit()

        assert nudges_service.scan_upcoming_events(db, now, lead_minutes=30) == []

    def test_cancelled_event_is_ignored(self, db: Session, family, adults):
        andrew = adults["robert"]
        now = _utcnow()
        event = Event(
            family_id=family.id,
            title="Cancelled",
            starts_at=now + timedelta(minutes=15),
            ends_at=now + timedelta(minutes=45),
            is_cancelled=True,
        )
        db.add(event)
        db.flush()
        db.add(EventAttendee(event_id=event.id, family_member_id=andrew.id))
        db.commit()

        assert nudges_service.scan_upcoming_events(db, now, lead_minutes=30) == []

    def test_all_day_event_is_ignored(self, db: Session, family, adults):
        """all-day events have no meaningful heads-up moment."""
        andrew = adults["robert"]
        now = _utcnow()
        event = Event(
            family_id=family.id,
            title="All day",
            starts_at=now + timedelta(minutes=15),
            ends_at=now + timedelta(hours=12),
            all_day=True,
        )
        db.add(event)
        db.flush()
        db.add(EventAttendee(event_id=event.id, family_member_id=andrew.id))
        db.commit()

        assert nudges_service.scan_upcoming_events(db, now, lead_minutes=30) == []


class TestScanMissedRoutines:
    def _make_routine(self, db, family, member, name="Morning routine"):
        r = Routine(
            family_id=family.id,
            family_member_id=member.id,
            name=name,
            block="morning",
            recurrence="daily",
            due_time_weekday=time(7, 30),
            due_time_weekend=time(9, 0),
        )
        db.add(r)
        db.flush()
        return r

    def test_missed_routine_today_produces_proposal(
        self, db: Session, family, children
    ):
        sadie = children["sadie"]
        routine = self._make_routine(db, family, sadie)
        now = _utcnow()
        instance = TaskInstance(
            family_id=family.id,
            family_member_id=sadie.id,
            routine_id=routine.id,
            instance_date=now.date(),
            due_at=now - timedelta(minutes=20),
            is_completed=False,
        )
        db.add(instance)
        db.commit()

        proposals = nudges_service.scan_missed_routines(db, now)

        assert len(proposals) == 1
        p = proposals[0]
        assert p.family_member_id == sadie.id
        assert p.trigger_kind == "missed_routine"
        assert p.trigger_entity_kind == "task_instance"
        assert p.trigger_entity_id == instance.id
        assert p.context["name"] == "Morning routine"
        assert p.severity == "low"  # revised plan Section 6

    def test_completed_routine_is_ignored(
        self, db: Session, family, children
    ):
        sadie = children["sadie"]
        routine = self._make_routine(db, family, sadie)
        now = _utcnow()
        db.add(
            TaskInstance(
                family_id=family.id,
                family_member_id=sadie.id,
                routine_id=routine.id,
                instance_date=now.date(),
                due_at=now - timedelta(minutes=20),
                is_completed=True,
                completed_at=now - timedelta(minutes=5),
            )
        )
        db.commit()

        assert nudges_service.scan_missed_routines(db, now) == []

    def test_override_completed_is_treated_as_completed(
        self, db: Session, family, children, adults
    ):
        sadie = children["sadie"]
        parent = adults["robert"]
        routine = self._make_routine(db, family, sadie)
        now = _utcnow()
        db.add(
            TaskInstance(
                family_id=family.id,
                family_member_id=sadie.id,
                routine_id=routine.id,
                instance_date=now.date(),
                due_at=now - timedelta(minutes=20),
                is_completed=False,
                override_completed=True,
                override_by=parent.id,
            )
        )
        db.commit()

        assert nudges_service.scan_missed_routines(db, now) == []

    def test_future_due_routine_is_ignored(
        self, db: Session, family, children
    ):
        sadie = children["sadie"]
        routine = self._make_routine(db, family, sadie)
        now = _utcnow()
        db.add(
            TaskInstance(
                family_id=family.id,
                family_member_id=sadie.id,
                routine_id=routine.id,
                instance_date=now.date(),
                due_at=now + timedelta(minutes=30),
                is_completed=False,
            )
        )
        db.commit()

        assert nudges_service.scan_missed_routines(db, now) == []

    def test_chore_template_instance_ignored(
        self, db: Session, family, children
    ):
        """scan_missed_routines is routine-only. Ignore task_instances
        rows whose routine_id is NULL."""
        sadie = children["sadie"]
        now = _utcnow()
        chore = ChoreTemplate(
            family_id=family.id,
            name="Sweep",
            recurrence="daily",
            due_time=time(19, 0),
            assignment_type="fixed",
            assignment_rule={"assigned_to": str(sadie.id)},
        )
        db.add(chore)
        db.flush()
        db.add(
            TaskInstance(
                family_id=family.id,
                family_member_id=sadie.id,
                routine_id=None,
                chore_template_id=chore.id,
                instance_date=now.date(),
                due_at=now - timedelta(minutes=20),
                is_completed=False,
            )
        )
        db.commit()

        assert nudges_service.scan_missed_routines(db, now) == []


def _set_proactivity(db, member_id, value):
    ai_personality_service.upsert_personality(
        db, family_member_id=member_id, payload={"proactivity": value}
    )


class TestApplyProactivity:
    def test_quiet_drops_all_proposals(self, db: Session, family, adults):
        andrew = adults["robert"]
        _set_proactivity(db, andrew.id, "quiet")
        now = _utcnow()
        prop = nudges_service.NudgeProposal(
            family_member_id=andrew.id,
            trigger_kind="overdue_task",
            trigger_entity_kind="personal_task",
            trigger_entity_id=None,
            scheduled_for=now,
        )

        out = nudges_service.apply_proactivity(db, [prop], now)
        assert out == []

    def test_balanced_is_passthrough(self, db: Session, family, adults):
        andrew = adults["robert"]
        _set_proactivity(db, andrew.id, "balanced")
        now = _utcnow()
        original = now + timedelta(minutes=30)
        prop = nudges_service.NudgeProposal(
            family_member_id=andrew.id,
            trigger_kind="upcoming_event",
            trigger_entity_kind="event",
            trigger_entity_id=None,
            scheduled_for=original,
        )

        out = nudges_service.apply_proactivity(db, [prop], now)
        assert len(out) == 1
        assert out[0].scheduled_for == original
        assert out[0].context["proactivity"] == "balanced"

    def test_forthcoming_shifts_upcoming_event_30_min_earlier(
        self, db: Session, family, adults
    ):
        andrew = adults["robert"]
        _set_proactivity(db, andrew.id, "forthcoming")
        now = _utcnow()
        original = now  # start_at - 30 = now
        prop = nudges_service.NudgeProposal(
            family_member_id=andrew.id,
            trigger_kind="upcoming_event",
            trigger_entity_kind="event",
            trigger_entity_id=None,
            scheduled_for=original,
        )

        out = nudges_service.apply_proactivity(db, [prop], now)
        assert len(out) == 1
        assert out[0].scheduled_for == original - timedelta(minutes=30)
        assert out[0].context["proactivity"] == "forthcoming"

    def test_forthcoming_shifts_missed_routine_10_min_earlier(
        self, db: Session, family, adults
    ):
        andrew = adults["robert"]
        _set_proactivity(db, andrew.id, "forthcoming")
        now = _utcnow()
        original = now  # due_at + 15, which is also now
        prop = nudges_service.NudgeProposal(
            family_member_id=andrew.id,
            trigger_kind="missed_routine",
            trigger_entity_kind="task_instance",
            trigger_entity_id=None,
            scheduled_for=original,
            severity="low",
        )

        out = nudges_service.apply_proactivity(db, [prop], now)
        assert len(out) == 1
        assert out[0].scheduled_for == original - timedelta(minutes=10)

    def test_forthcoming_does_not_shift_overdue_task(
        self, db: Session, family, adults
    ):
        andrew = adults["robert"]
        _set_proactivity(db, andrew.id, "forthcoming")
        now = _utcnow()
        original = now - timedelta(hours=1)
        prop = nudges_service.NudgeProposal(
            family_member_id=andrew.id,
            trigger_kind="overdue_task",
            trigger_entity_kind="personal_task",
            trigger_entity_id=None,
            scheduled_for=original,
        )

        out = nudges_service.apply_proactivity(db, [prop], now)
        assert len(out) == 1
        assert out[0].scheduled_for == original

    def test_caches_member_lookup(self, db: Session, family, adults, monkeypatch):
        """If one member has two proposals, get_resolved_config is called
        only once for that member."""
        andrew = adults["robert"]
        _set_proactivity(db, andrew.id, "balanced")
        now = _utcnow()
        prop_a = nudges_service.NudgeProposal(
            family_member_id=andrew.id,
            trigger_kind="overdue_task",
            trigger_entity_kind="personal_task",
            trigger_entity_id=None,
            scheduled_for=now,
        )
        prop_b = nudges_service.NudgeProposal(
            family_member_id=andrew.id,
            trigger_kind="upcoming_event",
            trigger_entity_kind="event",
            trigger_entity_id=None,
            scheduled_for=now,
        )

        call_count = {"n": 0}
        real = ai_personality_service.get_resolved_config

        def counting(db_arg, family_member_id):
            call_count["n"] += 1
            return real(db_arg, family_member_id)

        monkeypatch.setattr(
            ai_personality_service, "get_resolved_config", counting
        )

        out = nudges_service.apply_proactivity(db, [prop_a, prop_b], now)
        assert len(out) == 2
        assert call_count["n"] == 1


import pytz


class TestResolveOccurrenceFields:
    def test_overdue_task_resolves_family_timezone_correctly(
        self, db: Session, family, adults
    ):
        """Families.timezone=America/Chicago. An event at 2026-04-21
        03:30 UTC is 2026-04-20 22:30 local (CDT, UTC-5) - so
        occurrence_local_date is 2026-04-20."""
        andrew = adults["robert"]
        family.timezone = "America/Chicago"
        db.commit()

        event_id = __import__("uuid").uuid4()
        prop = nudges_service.NudgeProposal(
            family_member_id=andrew.id,
            trigger_kind="overdue_task",
            trigger_entity_kind="personal_task",
            trigger_entity_id=event_id,
            scheduled_for=datetime(2026, 4, 21, 3, 30),
            severity="normal",
            context={
                "title": "T",
                "occurrence_at_utc": datetime(2026, 4, 21, 3, 30),
            },
        )

        fields = nudges_service.resolve_occurrence_fields(db, prop)

        assert fields.occurrence_at_utc == datetime(2026, 4, 21, 3, 30)
        assert fields.occurrence_local_date.isoformat() == "2026-04-20"
        assert fields.source_dedupe_key == f"{andrew.id}:overdue_task:{event_id}:2026-04-20"

    def test_upcoming_event_uses_local_date_not_utc_date(
        self, db: Session, family, adults
    ):
        andrew = adults["robert"]
        family.timezone = "America/Los_Angeles"  # UTC-7/8
        db.commit()

        event_id = __import__("uuid").uuid4()
        # 2026-04-21 06:00 UTC = 2026-04-20 23:00 PDT
        prop = nudges_service.NudgeProposal(
            family_member_id=andrew.id,
            trigger_kind="upcoming_event",
            trigger_entity_kind="event",
            trigger_entity_id=event_id,
            scheduled_for=datetime(2026, 4, 21, 5, 30),
            severity="normal",
            context={
                "title": "T",
                "occurrence_at_utc": datetime(2026, 4, 21, 6, 0),
            },
        )

        fields = nudges_service.resolve_occurrence_fields(db, prop)
        assert fields.occurrence_local_date.isoformat() == "2026-04-20"

    def test_missing_occurrence_at_utc_raises_value_error(
        self, db: Session, family, adults
    ):
        andrew = adults["robert"]
        prop = nudges_service.NudgeProposal(
            family_member_id=andrew.id,
            trigger_kind="overdue_task",
            trigger_entity_kind="personal_task",
            trigger_entity_id=__import__("uuid").uuid4(),
            scheduled_for=_utcnow(),
            severity="normal",
            context={},  # missing occurrence_at_utc
        )

        with pytest.raises(ValueError, match="occurrence_at_utc"):
            nudges_service.resolve_occurrence_fields(db, prop)


class TestAISuggestedDedupeKey:
    """Sprint 05 Phase 5 Task 3 - dedupe_key for ai_suggested proposals
    with no trigger_entity_id must be derived from the proposal body so
    two distinct AI suggestions on the same day don't collapse to the
    same literal 'null' slot and get dropped by the child-row UNIQUE
    constraint."""

    def _make_prop(
        self,
        member_id,
        *,
        trigger_kind: str = "ai_suggested",
        trigger_entity_id=None,
        context_extra: dict | None = None,
    ) -> "nudges_service.NudgeProposal":
        ctx: dict = {"occurrence_at_utc": datetime(2026, 4, 21, 12, 0)}
        if context_extra:
            ctx.update(context_extra)
        return nudges_service.NudgeProposal(
            family_member_id=member_id,
            trigger_kind=trigger_kind,
            trigger_entity_kind="family",
            trigger_entity_id=trigger_entity_id,
            scheduled_for=datetime(2026, 4, 21, 12, 0),
            severity="normal",
            context=ctx,
        )

    def test_ai_suggested_with_none_entity_and_body_uses_body_hash(
        self, db: Session, family, adults
    ):
        import hashlib as _hashlib

        andrew = adults["robert"]
        family.timezone = "UTC"
        db.commit()

        body = "Remember trash day"
        prop = self._make_prop(andrew.id, context_extra={"body": body})

        fields = nudges_service.resolve_occurrence_fields(db, prop)

        assert ":ai:" in fields.source_dedupe_key
        assert ":null:" not in fields.source_dedupe_key
        expected_hash = _hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]
        assert expected_hash in fields.source_dedupe_key
        assert fields.source_dedupe_key == (
            f"{andrew.id}:ai_suggested:ai:{expected_hash}:2026-04-21"
        )

    def test_ai_suggested_different_bodies_get_different_keys(
        self, db: Session, family, adults
    ):
        andrew = adults["robert"]
        family.timezone = "UTC"
        db.commit()

        prop_a = self._make_prop(andrew.id, context_extra={"body": "Call the dentist"})
        prop_b = self._make_prop(
            andrew.id, context_extra={"body": "Pick up the dry cleaning"}
        )

        key_a = nudges_service.resolve_occurrence_fields(db, prop_a).source_dedupe_key
        key_b = nudges_service.resolve_occurrence_fields(db, prop_b).source_dedupe_key

        assert key_a != key_b

    def test_ai_suggested_same_body_gets_same_key(
        self, db: Session, family, adults
    ):
        andrew = adults["robert"]
        family.timezone = "UTC"
        db.commit()

        body = "Top up the MetroCard"
        prop_a = self._make_prop(andrew.id, context_extra={"body": body})
        prop_b = self._make_prop(andrew.id, context_extra={"body": body})

        key_a = nudges_service.resolve_occurrence_fields(db, prop_a).source_dedupe_key
        key_b = nudges_service.resolve_occurrence_fields(db, prop_b).source_dedupe_key

        assert key_a == key_b

    def test_ai_suggested_with_none_entity_and_no_body_uses_context_hash(
        self, db: Session, family, adults
    ):
        andrew = adults["robert"]
        family.timezone = "UTC"
        db.commit()

        # No 'body' key in context, just an unrelated field.
        prop_a = self._make_prop(andrew.id, context_extra={"foo": "bar"})
        prop_b = self._make_prop(andrew.id, context_extra={"foo": "bar"})

        key_a = nudges_service.resolve_occurrence_fields(db, prop_a).source_dedupe_key
        key_b = nudges_service.resolve_occurrence_fields(db, prop_b).source_dedupe_key

        assert ":null:" not in key_a
        assert ":ai:" in key_a
        # Stable: same context -> same key on repeat invocation.
        assert key_a == key_b

    def test_builtin_proposal_still_uses_null_for_none_entity(
        self, db: Session, family, adults
    ):
        """Built-in P1 trigger kinds keep the 'null' literal so their
        dedupe behavior is unchanged by the AI fix."""
        andrew = adults["robert"]
        family.timezone = "UTC"
        db.commit()

        prop = self._make_prop(
            andrew.id,
            trigger_kind="overdue_task",
            trigger_entity_id=None,
            context_extra={},
        )

        fields = nudges_service.resolve_occurrence_fields(db, prop)
        assert ":null:" in fields.source_dedupe_key
        assert fields.source_dedupe_key == (
            f"{andrew.id}:overdue_task:null:2026-04-21"
        )

    def test_builtin_proposal_with_real_entity_unchanged(
        self, db: Session, family, adults
    ):
        andrew = adults["robert"]
        family.timezone = "UTC"
        db.commit()

        entity_id = uuid.uuid4()
        prop = self._make_prop(
            andrew.id,
            trigger_kind="overdue_task",
            trigger_entity_id=entity_id,
        )

        fields = nudges_service.resolve_occurrence_fields(db, prop)
        assert str(entity_id) in fields.source_dedupe_key
        assert fields.source_dedupe_key == (
            f"{andrew.id}:overdue_task:{entity_id}:2026-04-21"
        )

    def test_ai_suggested_empty_body_uses_body_hash_not_context(
        self, db: Session, family, adults
    ):
        """Batch-1 PR 1 Item 2: an empty-string body must hit the
        body-hash branch, not silently fall through to the
        context-hash fallback.

        Pydantic's DiscoveryProposal.min_length=1 prevents the empty
        case on the normal path, but a direct dataclass caller could
        construct a NudgeProposal with context['body']=''. The
        resolver now uses 'is not None' so the body-hash branch
        fires, and all empty-body proposals collapse to the same
        stable dedupe key regardless of other context differences.
        """
        import hashlib as _hashlib

        andrew = adults["robert"]
        family.timezone = "UTC"
        db.commit()

        empty_body_hash = _hashlib.sha256(b"").hexdigest()[:16]
        expected_entity_part = f"ai:{empty_body_hash}"

        # Two proposals with empty body but otherwise different
        # context. Under the old truthy check they would have fallen
        # to the context-hash branch and produced DIFFERENT keys.
        # Under the new 'is not None' check they share the body-hash
        # key and collapse, which is the semantically correct
        # behavior for two content-free suggestions on the same day.
        prop_a = self._make_prop(
            andrew.id,
            context_extra={"body": "", "variant": "a"},
        )
        prop_b = self._make_prop(
            andrew.id,
            context_extra={"body": "", "variant": "b"},
        )

        key_a = nudges_service.resolve_occurrence_fields(
            db, prop_a
        ).source_dedupe_key
        key_b = nudges_service.resolve_occurrence_fields(
            db, prop_b
        ).source_dedupe_key

        assert expected_entity_part in key_a
        assert expected_entity_part in key_b
        assert key_a == key_b, (
            "empty-body proposals must collapse to the same key "
            "regardless of other context keys"
        )


class TestP1P5DedupeBoundary:
    """Sprint 05 Phase 5 Task 5 - lock in the P1 vs P5 dedupe boundary.

    P1 (built-in scanners) emit trigger_kind='overdue_task' (or
    'upcoming_event' / 'missed_routine'). P5 (AI discovery) emits
    trigger_kind='ai_suggested'. source_dedupe_key is
    '{member}:{trigger_kind}:{entity_part}:{local_date}' -- trigger_kind
    is part of the key, so a P1 and a P5 proposal for the SAME entity
    on the SAME day for the SAME member produce DIFFERENT keys and BOTH
    dispatch today. This is deliberate: cross-kind dedupe is NOT
    enforced at the source_dedupe_key layer; the plan's mitigation is
    that both paths share the UNIQUE (source_dedupe_key) constraint,
    not that they dedupe across kinds.

    These tests pin that contract so it becomes a conscious choice.
    If the team later decides cross-kind dedupe should be enforced at
    an upper layer (route_hint suppression, a composer-side guard,
    etc.), test_dispatch_writes_both_p1_and_p5_for_same_task will fail
    and force the design-change conversation.
    """

    def _make_p1(
        self,
        member_id,
        *,
        entity_id,
        occurrence: datetime,
    ) -> "nudges_service.NudgeProposal":
        return nudges_service.NudgeProposal(
            family_member_id=member_id,
            trigger_kind="overdue_task",
            trigger_entity_kind="personal_task",
            trigger_entity_id=entity_id,
            scheduled_for=occurrence,
            severity="normal",
            context={
                "title": "Trash",
                "due_time": "08:00 AM",
                "occurrence_at_utc": occurrence,
            },
        )

    def _make_p5(
        self,
        member_id,
        *,
        entity_id,
        occurrence: datetime,
        body: str = "Remember to take out the trash",
    ) -> "nudges_service.NudgeProposal":
        return nudges_service.NudgeProposal(
            family_member_id=member_id,
            trigger_kind="ai_suggested",
            trigger_entity_kind="personal_task",
            trigger_entity_id=entity_id,
            scheduled_for=occurrence,
            severity="normal",
            context={
                "body": body,
                "occurrence_at_utc": occurrence,
            },
        )

    def test_p1_and_p5_same_entity_produce_different_keys_today(
        self, db: Session, family, adults
    ):
        """Same member, same entity, same day, different trigger_kind.
        Current behavior: keys differ because trigger_kind is in the
        source_dedupe_key format. That means BOTH would dispatch today
        and cross-kind dedupe is NOT enforced at this layer. This test
        documents that contract.
        """
        andrew = adults["robert"]
        family.timezone = "UTC"
        db.commit()

        occurrence = datetime(2026, 4, 21, 12, 0)
        task_id = uuid.uuid4()
        p1 = self._make_p1(andrew.id, entity_id=task_id, occurrence=occurrence)
        p5 = self._make_p5(andrew.id, entity_id=task_id, occurrence=occurrence)

        key_p1 = nudges_service.resolve_occurrence_fields(db, p1).source_dedupe_key
        key_p5 = nudges_service.resolve_occurrence_fields(db, p5).source_dedupe_key

        assert key_p1 != key_p5
        # Shape check: only the trigger_kind segment differs.
        assert key_p1 == f"{andrew.id}:overdue_task:{task_id}:2026-04-21"
        assert key_p5 == f"{andrew.id}:ai_suggested:{task_id}:2026-04-21"

    def test_p1_duplicate_same_day_dedupes(
        self, db: Session, family, adults
    ):
        """Two P1 proposals for the same task + member + day collapse
        to an identical source_dedupe_key. Proves same-kind dedupe
        within P1 still works (and is not accidentally broken by the
        P5 changes)."""
        andrew = adults["robert"]
        family.timezone = "UTC"
        db.commit()

        occurrence = datetime(2026, 4, 21, 12, 0)
        task_id = uuid.uuid4()
        p1_a = self._make_p1(andrew.id, entity_id=task_id, occurrence=occurrence)
        p1_b = self._make_p1(andrew.id, entity_id=task_id, occurrence=occurrence)

        key_a = nudges_service.resolve_occurrence_fields(db, p1_a).source_dedupe_key
        key_b = nudges_service.resolve_occurrence_fields(db, p1_b).source_dedupe_key

        assert key_a == key_b

    def test_p5_duplicate_same_day_dedupes(
        self, db: Session, family, adults
    ):
        """Two P5 proposals with the same body + member + day (no
        trigger_entity_id) collapse to an identical source_dedupe_key
        via the body-hash entity_part. Proves the Task 3 body-hash
        dedupe works."""
        andrew = adults["robert"]
        family.timezone = "UTC"
        db.commit()

        occurrence = datetime(2026, 4, 21, 12, 0)
        body = "Remember to take out the trash"
        p5_a = self._make_p5(
            andrew.id, entity_id=None, occurrence=occurrence, body=body
        )
        p5_b = self._make_p5(
            andrew.id, entity_id=None, occurrence=occurrence, body=body
        )

        key_a = nudges_service.resolve_occurrence_fields(db, p5_a).source_dedupe_key
        key_b = nudges_service.resolve_occurrence_fields(db, p5_b).source_dedupe_key

        assert key_a == key_b

    def test_p1_and_p5_different_entities_produce_different_keys(
        self, db: Session, family, adults
    ):
        """P1 about task A and P5 about an unrelated task B should
        produce different keys (sanity check -- the tests above focus
        on same-entity cross-kind; this pins the easy case)."""
        andrew = adults["robert"]
        family.timezone = "UTC"
        db.commit()

        occurrence = datetime(2026, 4, 21, 12, 0)
        task_a = uuid.uuid4()
        task_b = uuid.uuid4()
        p1 = self._make_p1(andrew.id, entity_id=task_a, occurrence=occurrence)
        p5 = self._make_p5(andrew.id, entity_id=task_b, occurrence=occurrence)

        key_p1 = nudges_service.resolve_occurrence_fields(db, p1).source_dedupe_key
        key_p5 = nudges_service.resolve_occurrence_fields(db, p5).source_dedupe_key

        assert key_p1 != key_p5

    def test_dispatch_writes_both_p1_and_p5_for_same_task(
        self, db: Session, family, adults, monkeypatch
    ):
        """End-to-end: seed a pending PersonalTask overdue by 1 hour.
        scan_overdue_tasks emits a P1 proposal. Separately build a P5
        proposal for the same task. Run both through apply_proactivity
        -> batch_proposals -> dispatch_with_items. Assert TWO rows in
        nudge_dispatch_items for this task (one per trigger_kind).

        This test pins the documented behavior that cross-kind dedupe
        is not enforced at the dispatch layer. If an upper layer (e.g.
        route_hint suppression in the composer) is added later to block
        double-fires, this test will fail and force a deliberate change.
        """
        _force_compose_fallback(monkeypatch)
        andrew = adults["robert"]
        now = _utcnow().replace(tzinfo=None)
        due = now - timedelta(hours=1)

        task = PersonalTask(
            family_id=family.id,
            assigned_to=andrew.id,
            title="Take out the trash",
            status="pending",
            due_at=due,
        )
        db.add(task)
        db.commit()

        # P1: from the scanner.
        p1_props = nudges_service.scan_overdue_tasks(db, now)
        assert len(p1_props) == 1
        assert p1_props[0].trigger_kind == "overdue_task"
        assert p1_props[0].trigger_entity_id == task.id

        # P5: AI discovery proposal for the SAME task.
        p5_prop = nudges_service.NudgeProposal(
            family_member_id=andrew.id,
            trigger_kind="ai_suggested",
            trigger_entity_kind="personal_task",
            trigger_entity_id=task.id,
            scheduled_for=now,
            severity="normal",
            context={
                "body": "Heads up: trash is still waiting on you.",
                "occurrence_at_utc": due,
            },
        )

        combined = list(p1_props) + [p5_prop]
        # Normalize scheduled_for to naive-UTC across both proposal paths
        # so batch_proposals' sort doesn't mix tz-aware (timestamptz from
        # DB via scan_overdue_tasks) with naive (constructed in-test).
        # Mirrors run_nudge_scan's normalization step.
        for p in combined:
            if p.scheduled_for is not None and p.scheduled_for.tzinfo is not None:
                p.scheduled_for = p.scheduled_for.astimezone(
                    timezone.utc
                ).replace(tzinfo=None)
        gated = nudges_service.apply_proactivity(db, combined, now)
        bundles = nudges_service.batch_proposals(gated)
        written = nudges_service.dispatch_with_items(db, bundles, now)

        # Both proposals survive dedupe and dispatch. May be 1 bundle
        # (same member within batching window) or 2 bundles; either
        # way, two child rows must exist.
        assert written >= 1

        children = (
            db.query(NudgeDispatchItem)
            .filter_by(trigger_entity_id=task.id, family_member_id=andrew.id)
            .all()
        )
        trigger_kinds = sorted(c.trigger_kind for c in children)
        assert trigger_kinds == ["ai_suggested", "overdue_task"], (
            "Expected BOTH P1 (overdue_task) and P5 (ai_suggested) child rows "
            "for the same task. If only one is present, cross-kind dedupe "
            "has been added at an upper layer -- update this test and the "
            "plan docs to reflect the new contract."
        )

        # Both rows reference the same member + entity; only the
        # trigger_kind (and hence source_dedupe_key) differ.
        dedupe_keys = {c.source_dedupe_key for c in children}
        assert len(dedupe_keys) == 2


class TestScannerStampsOccurrence:
    """Confirm each scanner stamps context['occurrence_at_utc'].

    These tests use a fixed deterministic `now` (not _utcnow()) so
    the date comparison cannot drift with real wall-clock time. The
    flake documented across Sprint 05 phases 2-5 handoffs under the
    name test_overdue_task_scanner_stamps_due_at was traced to the
    original use of _utcnow() against a Postgres session running
    America/Chicago TIME ZONE; at certain wall-clock hours the
    naive-datetime roundtrip + `.date()` assertion would differ.
    Batch-1 PR 4 swaps to a fixed datetime and compares on full
    wall-clock value, not date, so the test is time-independent.
    """

    # Fixed mid-afternoon UTC; safe from the 00:00-06:00 UTC window
    # where the America/Chicago session TZ could shift the roundtripped
    # .date() vs the naive `due.date()`. Using midday ensures both
    # sides agree under any Postgres session timezone policy.
    _FIXED_NOW = datetime(2026, 4, 22, 15, 0, 0)

    def _normalize_naive(self, dt: datetime) -> datetime:
        """Drop tzinfo so aware (roundtripped) and naive (constructed)
        datetimes compare by wall-clock. Postgres timestamptz with a
        session TZ returns aware values; the test constructs naive
        inputs. Both represent the same instant expressed as the
        session's local clock, so stripping tzinfo yields matching
        naive datetimes."""
        return dt.replace(tzinfo=None) if dt.tzinfo is not None else dt

    def test_overdue_task_scanner_stamps_due_at(
        self, db: Session, family, adults
    ):
        andrew = adults["robert"]
        now = self._FIXED_NOW
        due = now - timedelta(hours=1)
        db.add(
            PersonalTask(
                family_id=family.id,
                assigned_to=andrew.id,
                title="t",
                status="pending",
                due_at=due,
            )
        )
        db.commit()

        proposals = nudges_service.scan_overdue_tasks(db, now)
        assert len(proposals) == 1
        assert "occurrence_at_utc" in proposals[0].context
        # Full wall-clock equality (not .date()) so a roundtrip bug
        # cannot be masked by a coincidentally-matching date.
        actual = self._normalize_naive(proposals[0].context["occurrence_at_utc"])
        assert actual.replace(microsecond=0) == due.replace(microsecond=0), (
            f"expected occurrence_at_utc to round-trip due_at; got {actual} vs {due}"
        )

    def test_upcoming_event_scanner_stamps_starts_at(
        self, db: Session, family, adults
    ):
        andrew = adults["robert"]
        now = self._FIXED_NOW
        starts = now + timedelta(minutes=15)
        ev = Event(
            family_id=family.id,
            title="t",
            starts_at=starts,
            ends_at=starts + timedelta(minutes=30),
        )
        db.add(ev)
        db.flush()
        db.add(EventAttendee(event_id=ev.id, family_member_id=andrew.id))
        db.commit()

        proposals = nudges_service.scan_upcoming_events(db, now)
        assert len(proposals) == 1
        assert "occurrence_at_utc" in proposals[0].context
        actual = self._normalize_naive(proposals[0].context["occurrence_at_utc"])
        assert actual.replace(microsecond=0) == starts.replace(microsecond=0), (
            f"expected occurrence_at_utc to round-trip starts_at; got {actual} vs {starts}"
        )

    def test_missed_routine_scanner_stamps_due_at(
        self, db: Session, family, adults, children
    ):
        sadie = children["sadie"]
        parent = adults["robert"]
        now = self._FIXED_NOW
        due = now - timedelta(minutes=20)
        from datetime import time as dtime

        r = Routine(
            family_id=family.id,
            family_member_id=sadie.id,
            name="t",
            block="morning",
            recurrence="daily",
            due_time_weekday=dtime(7, 30),
            due_time_weekend=dtime(9, 0),
        )
        db.add(r)
        db.flush()
        db.add(
            TaskInstance(
                family_id=family.id,
                family_member_id=sadie.id,
                routine_id=r.id,
                instance_date=now.date(),
                due_at=due,
                is_completed=False,
            )
        )
        db.commit()

        proposals = nudges_service.scan_missed_routines(db, now)
        assert len(proposals) == 1
        assert "occurrence_at_utc" in proposals[0].context
        actual = self._normalize_naive(proposals[0].context["occurrence_at_utc"])
        assert actual.replace(microsecond=0) == due.replace(microsecond=0), (
            f"expected occurrence_at_utc to round-trip due_at; got {actual} vs {due}"
        )


class TestDispatchWithItems:
    def _base_proposal(self, andrew_id, occurrence, scheduled=None, kind="overdue_task", entity_id=None):
        return nudges_service.NudgeProposal(
            family_member_id=andrew_id,
            trigger_kind=kind,
            trigger_entity_kind="personal_task" if kind == "overdue_task" else ("event" if kind == "upcoming_event" else "task_instance"),
            trigger_entity_id=entity_id or __import__("uuid").uuid4(),
            scheduled_for=scheduled or occurrence,
            severity="normal" if kind != "missed_routine" else "low",
            context={
                "title": "Take out bins",
                "due_time": "08:00 AM",
                "occurrence_at_utc": occurrence,
                "proactivity": "balanced",
            },
        )

    def test_writes_parent_child_and_inbox_rows(
        self, db: Session, family, adults, monkeypatch
    ):
        andrew = adults["robert"]
        now = _utcnow()
        occurrence = now.replace(tzinfo=None) - timedelta(hours=1)
        prop = self._base_proposal(andrew.id, occurrence)
        bundle = nudges_service.ProposalBundle(
            family_member_id=prop.family_member_id, proposals=[prop]
        )

        # No push device => no push; test the Inbox path clean
        written = nudges_service.dispatch_with_items(db, [bundle], now.replace(tzinfo=None))

        assert written == 1
        parents = list(db.query(NudgeDispatch).filter_by(family_member_id=andrew.id).all())
        children = list(db.query(NudgeDispatchItem).filter_by(family_member_id=andrew.id).all())
        assert len(parents) == 1
        assert len(children) == 1
        assert children[0].dispatch_id == parents[0].id
        assert parents[0].parent_action_item_id is not None
        assert "inbox" in parents[0].delivered_channels
        assert "push" not in parents[0].delivered_channels
        inbox = db.get(ParentActionItem, parents[0].parent_action_item_id)
        assert inbox is not None
        # Phase 2 + migration 050: chk_parent_action_items_action_type now
        # allows nudge.* values. action_type reflects the trigger_kind.
        assert inbox.action_type == "nudge.overdue_task"
        assert inbox.entity_type == "personal_task"
        assert "Take out bins" in inbox.title or "Take out bins" in (inbox.detail or "")

    def test_dedupe_on_repeat(self, db: Session, family, adults):
        andrew = adults["robert"]
        now = _utcnow()
        occurrence = now.replace(tzinfo=None) - timedelta(hours=1)
        entity_id = __import__("uuid").uuid4()
        prop = self._base_proposal(andrew.id, occurrence, entity_id=entity_id)
        bundle = nudges_service.ProposalBundle(
            family_member_id=prop.family_member_id, proposals=[prop]
        )

        first = nudges_service.dispatch_with_items(db, [bundle], now.replace(tzinfo=None))
        second = nudges_service.dispatch_with_items(db, [bundle], now.replace(tzinfo=None))

        assert first == 1
        assert second == 0
        count = db.query(NudgeDispatchItem).filter_by(family_member_id=andrew.id).count()
        assert count == 1

    def test_push_sent_when_active_device_exists(
        self, db: Session, family, adults, monkeypatch
    ):
        andrew = adults["robert"]
        now = _utcnow().replace(tzinfo=None)
        device = PushDevice(
            family_member_id=andrew.id,
            expo_push_token="ExponentPushToken[fake]",
            device_label="iPhone",
            platform="ios",
            is_active=True,
            last_registered_at=now,
        )
        db.add(device)
        db.commit()

        sent: list[dict] = []

        # The fake writes a real PushDelivery so that the FK from
        # nudge_dispatches.push_delivery_id -> scout.push_deliveries.id
        # resolves. dispatch_with_items records the first delivery id
        # on the parent row.
        def fake_send_push(db_arg, **kwargs):
            sent.append(kwargs)
            group_id = __import__("uuid").uuid4()
            delivery = PushDelivery(
                notification_group_id=group_id,
                family_member_id=andrew.id,
                push_device_id=device.id,
                provider="expo",
                category=kwargs["category"],
                title=kwargs["title"],
                body=kwargs["body"],
                data=kwargs.get("data") or {},
                trigger_source=kwargs["trigger_source"],
                status="provider_accepted",
            )
            db_arg.add(delivery)
            db_arg.flush()
            from types import SimpleNamespace
            return SimpleNamespace(
                delivery_ids=[delivery.id],
                accepted_count=1,
                error_count=0,
                notification_group_id=group_id,
            )

        from app.services import push_service as ps
        monkeypatch.setattr(ps, "send_push", fake_send_push)

        occurrence = now - timedelta(hours=1)
        prop = self._base_proposal(andrew.id, occurrence)
        bundle = nudges_service.ProposalBundle(
            family_member_id=prop.family_member_id, proposals=[prop]
        )
        nudges_service.dispatch_with_items(db, [bundle], now)

        assert len(sent) == 1
        parent = db.query(NudgeDispatch).filter_by(family_member_id=andrew.id).one()
        assert "push" in parent.delivered_channels
        assert parent.push_delivery_id is not None

    def test_no_push_when_no_active_device(
        self, db: Session, family, adults, monkeypatch
    ):
        andrew = adults["robert"]
        now = _utcnow().replace(tzinfo=None)

        def fake_send_push(db_arg, **kwargs):
            raise AssertionError("should not be called")

        from app.services import push_service as ps
        monkeypatch.setattr(ps, "send_push", fake_send_push)

        occurrence = now - timedelta(hours=1)
        prop = self._base_proposal(andrew.id, occurrence)
        bundle = nudges_service.ProposalBundle(
            family_member_id=prop.family_member_id, proposals=[prop]
        )
        nudges_service.dispatch_with_items(db, [bundle], now)

        parent = db.query(NudgeDispatch).filter_by(family_member_id=andrew.id).one()
        assert parent.push_delivery_id is None
        assert "push" not in parent.delivered_channels
        assert "inbox" in parent.delivered_channels

    def test_push_error_does_not_poison_inbox(
        self, db: Session, family, adults, monkeypatch
    ):
        """If push_service.send_push raises, the Inbox row + parent +
        child rows are still written. delivered_channels reflects reality."""
        andrew = adults["robert"]
        now = _utcnow().replace(tzinfo=None)
        db.add(
            PushDevice(
                family_member_id=andrew.id,
                expo_push_token="ExponentPushToken[fake]",
                device_label="iPhone",
                platform="ios",
                is_active=True,
                last_registered_at=now,
            )
        )
        db.commit()

        def fake_send_push(db_arg, **kwargs):
            raise RuntimeError("expo is down")

        from app.services import push_service as ps
        monkeypatch.setattr(ps, "send_push", fake_send_push)

        occurrence = now - timedelta(hours=1)
        prop = self._base_proposal(andrew.id, occurrence)
        bundle = nudges_service.ProposalBundle(
            family_member_id=prop.family_member_id, proposals=[prop]
        )
        written = nudges_service.dispatch_with_items(db, [bundle], now)

        assert written == 1
        parent = db.query(NudgeDispatch).filter_by(family_member_id=andrew.id).one()
        assert "inbox" in parent.delivered_channels
        assert "push" not in parent.delivered_channels
        assert parent.push_delivery_id is None

    def test_one_proposal_dedupe_does_not_undo_siblings(
        self, db: Session, family, adults
    ):
        """Two proposals (as separate bundles) in one call. First
        succeeds, second has a pre-existing dedupe row (simulated by
        dispatching it first). Per-bundle SAVEPOINT ensures the first
        stays committed."""
        andrew = adults["robert"]
        now = _utcnow().replace(tzinfo=None)
        e1 = __import__("uuid").uuid4()
        e2 = __import__("uuid").uuid4()
        occurrence = now - timedelta(hours=1)

        prop_first = self._base_proposal(andrew.id, occurrence, entity_id=e1)
        prop_second = self._base_proposal(andrew.id, occurrence, entity_id=e2)
        bundle_first = nudges_service.ProposalBundle(
            family_member_id=prop_first.family_member_id, proposals=[prop_first]
        )
        bundle_second = nudges_service.ProposalBundle(
            family_member_id=prop_second.family_member_id, proposals=[prop_second]
        )

        # Pre-seed dedupe for prop_second
        nudges_service.dispatch_with_items(db, [bundle_second], now)
        assert db.query(NudgeDispatchItem).count() == 1

        written = nudges_service.dispatch_with_items(
            db, [bundle_first, bundle_second], now
        )

        # First is new (+1), second is deduped (no change)
        assert written == 1
        assert db.query(NudgeDispatchItem).count() == 2


class TestTickBenchmark:
    def test_tick_completes_under_10_seconds_with_realistic_fixture(
        self, db: Session, family, adults, children, monkeypatch
    ):
        """Revised plan §5: a single tick must complete in under 10
        seconds even with a realistic family size. 50+ personal_tasks,
        20+ events. Push calls are stubbed out (push is not our
        bottleneck under test)."""
        import time as _time

        now = _utcnow().replace(tzinfo=None)
        andrew = adults["robert"]
        megan = adults["megan"]
        sadie = children["sadie"]

        # 50 overdue personal_tasks split across adults
        for i in range(50):
            owner = andrew if i % 2 == 0 else megan
            db.add(
                PersonalTask(
                    family_id=family.id,
                    assigned_to=owner.id,
                    title=f"Task {i}",
                    status="pending",
                    due_at=now - timedelta(minutes=30 + i),
                )
            )

        # 20 upcoming events, one attendee each
        for i in range(20):
            owner = andrew if i % 2 == 0 else megan
            ev = Event(
                family_id=family.id,
                title=f"Event {i}",
                starts_at=now + timedelta(minutes=5 + i),
                ends_at=now + timedelta(minutes=35 + i),
            )
            db.add(ev)
            db.flush()
            db.add(EventAttendee(event_id=ev.id, family_member_id=owner.id))

        db.commit()

        # Stub push so it's not a bottleneck
        from types import SimpleNamespace

        def fake_send_push(db_arg, **kwargs):
            pd = __import__("app.models.push", fromlist=["PushDelivery"]).PushDelivery(
                family_member_id=kwargs["family_member_id"],
                category=kwargs["category"],
                title=kwargs["title"],
                body=kwargs["body"],
                data=kwargs.get("data") or {},
                trigger_source=kwargs.get("trigger_source", "nudge_scan"),
                status="provider_accepted",
                provider="expo",
                notification_group_id=__import__("uuid").uuid4(),
            )
            db_arg.add(pd)
            db_arg.flush()
            return SimpleNamespace(
                delivery_ids=[pd.id],
                accepted_count=1,
                error_count=0,
                notification_group_id=pd.notification_group_id,
            )

        from app.services import push_service as ps

        monkeypatch.setattr(ps, "send_push", fake_send_push)

        t0 = _time.monotonic()
        written = nudges_service.run_nudge_scan(db, now_utc=now)
        elapsed = _time.monotonic() - t0

        # Phase 2: run_nudge_scan now batches per member, so 70 proposals
        # collapse into a handful of bundles (4 members with overdue +
        # upcoming within 10-min anchors). Benchmark asserts the tick
        # produced something and stayed under budget. Per-child item
        # counts are covered in dedicated dispatch + batch tests.
        assert written >= 1, f"expected >=1 bundle dispatched, got {written}"
        child_count = db.query(NudgeDispatchItem).count()
        assert child_count >= 50, (
            f"expected >=50 child items written, got {child_count}"
        )
        assert elapsed < 10.0, f"tick took {elapsed:.2f}s (budget 10.0s)"


class TestQuietHoursGate:
    def _set_family_quiet_hours(self, db, family, start_minute, end_minute):
        db.add(
            QuietHoursFamily(
                family_id=family.id,
                start_local_minute=start_minute,
                end_local_minute=end_minute,
            )
        )
        db.commit()

    def _set_member_override(self, db, member_id, start_minute, end_minute):
        from sqlalchemy import text as _t
        db.execute(
            _t(
                """
                INSERT INTO member_config (family_member_id, key, value)
                VALUES (:mid, 'nudges.quiet_hours', CAST(:v AS JSONB))
                ON CONFLICT (family_member_id, key)
                DO UPDATE SET value = EXCLUDED.value
                """
            ),
            {
                "mid": member_id,
                "v": json.dumps(
                    {
                        "start_local_minute": start_minute,
                        "end_local_minute": end_minute,
                    }
                ),
            },
        )
        db.commit()

    def test_no_quiet_hours_configured_delivers(
        self, db: Session, family, adults
    ):
        andrew = adults["robert"]
        family.timezone = "America/Chicago"
        db.commit()
        now = _utcnow().replace(tzinfo=None)

        decision, hold = nudges_service.should_suppress_for_quiet_hours(
            db, andrew.id, "normal", now
        )
        assert decision == "deliver"
        assert hold is None

    def test_outside_window_delivers(
        self, db: Session, family, adults
    ):
        andrew = adults["robert"]
        family.timezone = "America/Chicago"
        db.commit()
        # 14:00 UTC on 2026-04-21 is 09:00 CDT (UTC-5, DST). Window 22-07.
        self._set_family_quiet_hours(db, family, 22 * 60, 7 * 60)
        now = __import__("datetime").datetime(2026, 4, 21, 14, 0)

        decision, hold = nudges_service.should_suppress_for_quiet_hours(
            db, andrew.id, "normal", now
        )
        assert decision == "deliver"
        assert hold is None

    def test_inside_window_low_severity_drops(
        self, db: Session, family, adults
    ):
        andrew = adults["robert"]
        family.timezone = "America/Chicago"
        db.commit()
        self._set_family_quiet_hours(db, family, 22 * 60, 7 * 60)
        # 06:00 UTC on 2026-04-21 = 01:00 CDT -- inside window
        now = __import__("datetime").datetime(2026, 4, 21, 6, 0)

        decision, hold = nudges_service.should_suppress_for_quiet_hours(
            db, andrew.id, "low", now
        )
        assert decision == "drop"
        assert hold is None

    def test_inside_window_high_severity_delivers(
        self, db: Session, family, adults
    ):
        andrew = adults["robert"]
        family.timezone = "America/Chicago"
        db.commit()
        self._set_family_quiet_hours(db, family, 22 * 60, 7 * 60)
        now = __import__("datetime").datetime(2026, 4, 21, 6, 0)

        decision, hold = nudges_service.should_suppress_for_quiet_hours(
            db, andrew.id, "high", now
        )
        assert decision == "deliver"
        assert hold is None

    def test_inside_window_normal_holds_until_window_end(
        self, db: Session, family, adults
    ):
        andrew = adults["robert"]
        family.timezone = "America/Chicago"
        db.commit()
        self._set_family_quiet_hours(db, family, 22 * 60, 7 * 60)
        # 06:00 UTC 2026-04-21 = 01:00 CDT -> hold until 07:00 CDT = 12:00 UTC same day
        now = __import__("datetime").datetime(2026, 4, 21, 6, 0)

        decision, hold = nudges_service.should_suppress_for_quiet_hours(
            db, andrew.id, "normal", now
        )
        assert decision == "hold"
        assert hold is not None
        # End-of-window is 07:00 local = 12:00 UTC (CDT = UTC-5)
        assert hold == __import__("datetime").datetime(2026, 4, 21, 12, 0)

    def test_member_override_beats_family_default(
        self, db: Session, family, adults
    ):
        """Family says 22-07; Andrew overrides to 23-05. At 06:00 CDT
        (= 11:00 UTC), family rule says 'inside' but Andrew's override
        says 'outside'. Override wins."""
        andrew = adults["robert"]
        family.timezone = "America/Chicago"
        db.commit()
        self._set_family_quiet_hours(db, family, 22 * 60, 7 * 60)
        self._set_member_override(db, andrew.id, 23 * 60, 5 * 60)
        # 11:00 UTC = 06:00 CDT. Family window (22-07) would include it.
        # Andrew's window (23-05) does not.
        now = __import__("datetime").datetime(2026, 4, 21, 11, 0)

        decision, hold = nudges_service.should_suppress_for_quiet_hours(
            db, andrew.id, "normal", now
        )
        assert decision == "deliver"

    def test_resolve_deliver_after_passes_through_when_deliver(
        self, db: Session, family, adults
    ):
        andrew = adults["robert"]
        family.timezone = "America/Chicago"
        db.commit()
        now = __import__("datetime").datetime(2026, 4, 21, 14, 0)
        prop = nudges_service.NudgeProposal(
            family_member_id=andrew.id,
            trigger_kind="overdue_task",
            trigger_entity_kind="personal_task",
            trigger_entity_id=__import__("uuid").uuid4(),
            scheduled_for=now,
            severity="normal",
            context={"occurrence_at_utc": now},
        )

        deliver_after, reason = nudges_service.resolve_deliver_after(db, prop, now)
        assert deliver_after == now
        assert reason is None

    def test_resolve_deliver_after_returns_suppressed_reason_on_drop(
        self, db: Session, family, adults
    ):
        andrew = adults["robert"]
        family.timezone = "America/Chicago"
        db.commit()
        self._set_family_quiet_hours(db, family, 22 * 60, 7 * 60)
        now = __import__("datetime").datetime(2026, 4, 21, 6, 0)
        prop = nudges_service.NudgeProposal(
            family_member_id=andrew.id,
            trigger_kind="missed_routine",
            trigger_entity_kind="task_instance",
            trigger_entity_id=__import__("uuid").uuid4(),
            scheduled_for=now,
            severity="low",
            context={"occurrence_at_utc": now},
        )

        deliver_after, reason = nudges_service.resolve_deliver_after(db, prop, now)
        assert reason == "quiet_hours"

    def test_resolve_deliver_after_pushes_hold_across_midnight(
        self, db: Session, family, adults
    ):
        """normal-severity proposal at 01:00 local on 2026-04-21 holds
        to 07:00 local same morning (12:00 UTC)."""
        andrew = adults["robert"]
        family.timezone = "America/Chicago"
        db.commit()
        self._set_family_quiet_hours(db, family, 22 * 60, 7 * 60)
        now = __import__("datetime").datetime(2026, 4, 21, 6, 0)
        prop = nudges_service.NudgeProposal(
            family_member_id=andrew.id,
            trigger_kind="overdue_task",
            trigger_entity_kind="personal_task",
            trigger_entity_id=__import__("uuid").uuid4(),
            scheduled_for=now,
            severity="normal",
            context={"occurrence_at_utc": now},
        )

        deliver_after, reason = nudges_service.resolve_deliver_after(db, prop, now)
        assert reason is None
        assert deliver_after == __import__("datetime").datetime(2026, 4, 21, 12, 0)


class TestBatchProposals:
    def _mk(self, member_id, scheduled_offset_seconds, kind="overdue_task", entity_id=None):
        """Helper: proposal at now + offset seconds."""
        return nudges_service.NudgeProposal(
            family_member_id=member_id,
            trigger_kind=kind,
            trigger_entity_kind="personal_task",
            trigger_entity_id=entity_id or __import__("uuid").uuid4(),
            scheduled_for=datetime(2026, 4, 21, 12, 0) + timedelta(seconds=scheduled_offset_seconds),
            severity="normal",
            context={},
        )

    def test_empty_list_returns_empty(self):
        assert nudges_service.batch_proposals([]) == []

    def test_single_proposal_becomes_singleton_bundle(
        self, db: Session, family, adults
    ):
        andrew = adults["robert"]
        p = self._mk(andrew.id, 0)
        bundles = nudges_service.batch_proposals([p])
        assert len(bundles) == 1
        assert bundles[0].family_member_id == andrew.id
        assert len(bundles[0].proposals) == 1

    def test_two_proposals_within_window_collapse(
        self, db: Session, family, adults
    ):
        andrew = adults["robert"]
        p1 = self._mk(andrew.id, 0)
        p2 = self._mk(andrew.id, 120)  # +2 min
        bundles = nudges_service.batch_proposals([p1, p2], window_minutes=10)
        assert len(bundles) == 1
        assert len(bundles[0].proposals) == 2

    def test_two_proposals_outside_window_stay_separate(
        self, db: Session, family, adults
    ):
        andrew = adults["robert"]
        p1 = self._mk(andrew.id, 0)
        p2 = self._mk(andrew.id, 15 * 60)  # +15 min, outside 10-min window
        bundles = nudges_service.batch_proposals([p1, p2], window_minutes=10)
        assert len(bundles) == 2

    def test_different_members_never_collapse(
        self, db: Session, family, adults
    ):
        andrew = adults["robert"]
        megan = adults["megan"]
        p1 = self._mk(andrew.id, 0)
        p2 = self._mk(megan.id, 30)  # same time, different member
        bundles = nudges_service.batch_proposals([p1, p2])
        assert len(bundles) == 2
        assert {b.family_member_id for b in bundles} == {andrew.id, megan.id}

    def test_three_proposals_all_within_anchor_window(
        self, db: Session, family, adults
    ):
        """Anchor is the first proposal's scheduled_for. Second and
        third both measure against it."""
        andrew = adults["robert"]
        p1 = self._mk(andrew.id, 0)
        p2 = self._mk(andrew.id, 4 * 60)
        p3 = self._mk(andrew.id, 8 * 60)
        bundles = nudges_service.batch_proposals([p1, p2, p3], window_minutes=10)
        assert len(bundles) == 1
        assert len(bundles[0].proposals) == 3

    def test_chain_that_would_drift_is_broken_at_anchor_window(
        self, db: Session, family, adults
    ):
        """Anchor semantics: p1 at 0, p2 at 8min, p3 at 15min. p2 is
        within 10 of p1 (anchor=p1). p3 is 15 from anchor p1 -- outside
        window. New cluster starts at p3. Prevents indefinite drift
        from greedy neighbor-linking."""
        andrew = adults["robert"]
        p1 = self._mk(andrew.id, 0)
        p2 = self._mk(andrew.id, 8 * 60)
        p3 = self._mk(andrew.id, 15 * 60)
        bundles = nudges_service.batch_proposals([p1, p2, p3], window_minutes=10)
        assert len(bundles) == 2
        assert len(bundles[0].proposals) == 2
        assert len(bundles[1].proposals) == 1

    def test_effective_deliver_after_is_earliest_in_bundle(
        self, db: Session, family, adults
    ):
        andrew = adults["robert"]
        p1 = self._mk(andrew.id, 120)   # +2 min
        p2 = self._mk(andrew.id, 0)     # baseline
        p3 = self._mk(andrew.id, 300)   # +5 min
        bundles = nudges_service.batch_proposals([p1, p2, p3], window_minutes=10)
        assert len(bundles) == 1
        assert bundles[0].effective_deliver_after == datetime(2026, 4, 21, 12, 0)


class TestDispatchBundles:
    def test_single_item_bundle_matches_phase_1_shape(
        self, db: Session, family, adults, monkeypatch
    ):
        _force_compose_fallback(monkeypatch)
        andrew = adults["robert"]
        now = _utcnow().replace(tzinfo=None)
        occurrence = now - timedelta(hours=1)
        prop = nudges_service.NudgeProposal(
            family_member_id=andrew.id,
            trigger_kind="overdue_task",
            trigger_entity_kind="personal_task",
            trigger_entity_id=__import__("uuid").uuid4(),
            scheduled_for=occurrence,
            severity="normal",
            context={
                "title": "Trash",
                "due_time": "08:00 AM",
                "occurrence_at_utc": occurrence,
                "proactivity": "balanced",
            },
        )
        bundle = nudges_service.ProposalBundle(andrew.id, [prop])

        written = nudges_service.dispatch_with_items(db, [bundle], now)

        assert written == 1
        parent = db.query(NudgeDispatch).filter_by(family_member_id=andrew.id).one()
        assert parent.source_count == 1
        assert parent.status == "delivered"
        assert parent.body == "Reminder: Trash was due at 08:00 AM."
        assert parent.parent_action_item_id is not None
        inbox = db.get(ParentActionItem, parent.parent_action_item_id)
        assert inbox.action_type == "nudge.overdue_task"

    def test_multi_item_bundle_writes_composite(
        self, db: Session, family, adults, monkeypatch
    ):
        _force_compose_fallback(monkeypatch)
        andrew = adults["robert"]
        now = _utcnow().replace(tzinfo=None)
        occurrence = now - timedelta(hours=1)
        props = [
            nudges_service.NudgeProposal(
                family_member_id=andrew.id,
                trigger_kind="overdue_task",
                trigger_entity_kind="personal_task",
                trigger_entity_id=__import__("uuid").uuid4(),
                scheduled_for=occurrence + timedelta(seconds=i * 30),
                severity="normal",
                context={
                    "title": f"Task {i}",
                    "due_time": "08:00 AM",
                    "occurrence_at_utc": occurrence + timedelta(seconds=i * 30),
                    "proactivity": "balanced",
                },
            )
            for i in range(3)
        ]
        bundle = nudges_service.ProposalBundle(andrew.id, props)

        written = nudges_service.dispatch_with_items(db, [bundle], now)

        assert written == 1
        parent = db.query(NudgeDispatch).filter_by(family_member_id=andrew.id).one()
        assert parent.source_count == 3
        assert "3 items to check" in parent.body
        assert "Task 0" in parent.body and "Task 1" in parent.body
        assert "1 more" in parent.body
        children = db.query(NudgeDispatchItem).filter_by(
            dispatch_id=parent.id
        ).all()
        assert len(children) == 3
        inbox = db.get(ParentActionItem, parent.parent_action_item_id)
        assert inbox.title == "You have 3 nudges"

    def test_mixed_kind_bundle_uses_first_childs_kind_for_action_type(
        self, db: Session, family, adults, monkeypatch
    ):
        """Batch-1 PR 1 Item 1: document the mixed-kind bundle contract.

        A bundle containing children of DIFFERENT trigger_kinds writes a
        single ParentActionItem. By convention the action_type comes
        from the first child's trigger_kind (stability over cleverness).
        This test pins that convention so a future silent change has to
        also update the test + the handoff. Migration 050 widened the
        CHECK to allow nudge.<trigger_kind> values; a formalized
        nudge.mixed would require another migration and is not in
        scope here.
        """
        _force_compose_fallback(monkeypatch)
        andrew = adults["robert"]
        now = _utcnow().replace(tzinfo=None)
        occurrence = now - timedelta(hours=1)

        overdue = nudges_service.NudgeProposal(
            family_member_id=andrew.id,
            trigger_kind="overdue_task",
            trigger_entity_kind="personal_task",
            trigger_entity_id=__import__("uuid").uuid4(),
            scheduled_for=occurrence,
            severity="normal",
            context={
                "title": "Trash",
                "due_time": "08:00 AM",
                "occurrence_at_utc": occurrence,
                "proactivity": "balanced",
            },
        )
        missed_routine = nudges_service.NudgeProposal(
            family_member_id=andrew.id,
            trigger_kind="missed_routine",
            trigger_entity_kind="task_instance",
            trigger_entity_id=__import__("uuid").uuid4(),
            scheduled_for=occurrence + timedelta(seconds=30),
            severity="normal",
            context={
                "title": "Morning routine",
                "due_time": "07:00 AM",
                "occurrence_at_utc": occurrence + timedelta(seconds=30),
                "proactivity": "balanced",
            },
        )
        bundle = nudges_service.ProposalBundle(
            andrew.id, [overdue, missed_routine]
        )

        written = nudges_service.dispatch_with_items(db, [bundle], now)

        assert written == 1
        parent = db.query(NudgeDispatch).filter_by(
            family_member_id=andrew.id
        ).one()
        inbox = db.get(ParentActionItem, parent.parent_action_item_id)
        assert inbox.action_type == "nudge.overdue_task", (
            "Mixed-kind bundles must use the first child's trigger_kind; "
            "if this changes, update nudges_service.py line ~941 comment "
            "and the handoff notes."
        )
        children = db.query(NudgeDispatchItem).filter_by(
            dispatch_id=parent.id
        ).all()
        kinds = {c.trigger_kind for c in children}
        assert kinds == {"overdue_task", "missed_routine"}, (
            "children must preserve both trigger_kinds so the bundle is "
            "demonstrably mixed"
        )

    def test_hold_path_writes_pending_no_inbox(
        self, db: Session, family, adults, monkeypatch
    ):
        andrew = adults["robert"]
        family.timezone = "America/Chicago"
        db.add(
            QuietHoursFamily(
                family_id=family.id,
                start_local_minute=22 * 60,
                end_local_minute=7 * 60,
            )
        )
        db.commit()

        def no_push(db_arg, **kw):
            raise AssertionError("should not push during hold")

        from app.services import push_service as ps
        monkeypatch.setattr(ps, "send_push", no_push)

        # 06:00 UTC 2026-04-21 = 01:00 CDT, inside quiet window
        now = datetime(2026, 4, 21, 6, 0)
        occurrence = now - timedelta(hours=1)
        prop = nudges_service.NudgeProposal(
            family_member_id=andrew.id,
            trigger_kind="overdue_task",
            trigger_entity_kind="personal_task",
            trigger_entity_id=__import__("uuid").uuid4(),
            scheduled_for=now,
            severity="normal",
            context={
                "title": "t",
                "due_time": "05:00 AM",
                "occurrence_at_utc": occurrence,
                "proactivity": "balanced",
            },
        )
        bundle = nudges_service.ProposalBundle(andrew.id, [prop])

        nudges_service.dispatch_with_items(db, [bundle], now)

        parent = db.query(NudgeDispatch).filter_by(family_member_id=andrew.id).one()
        assert parent.status == "pending"
        assert parent.parent_action_item_id is None
        assert parent.delivered_at_utc is None
        assert parent.delivered_channels == []
        # Held to window end: 07:00 local = 12:00 UTC. The column is
        # TIMESTAMPTZ, so psycopg2 hydrates the row as tz-aware in the
        # session's timezone; compare the UTC moment rather than the
        # naive wall-clock to stay robust to the session TZ.
        expected_hold_utc = datetime(2026, 4, 21, 12, 0, tzinfo=timezone.utc)
        actual = parent.deliver_after_utc
        if actual.tzinfo is None:
            actual = actual.replace(tzinfo=timezone.utc)
        assert actual.astimezone(timezone.utc) == expected_hold_utc
        child_count = db.query(NudgeDispatchItem).filter_by(
            dispatch_id=parent.id
        ).count()
        assert child_count == 1

    def test_drop_path_writes_suppressed_no_inbox(
        self, db: Session, family, adults, monkeypatch
    ):
        """Low severity inside window -> suppressed audit row, no Inbox."""
        andrew = adults["robert"]
        family.timezone = "America/Chicago"
        db.add(
            QuietHoursFamily(
                family_id=family.id,
                start_local_minute=22 * 60,
                end_local_minute=7 * 60,
            )
        )
        db.commit()

        def no_push(db_arg, **kw):
            raise AssertionError("should not push during drop")

        from app.services import push_service as ps
        monkeypatch.setattr(ps, "send_push", no_push)

        now = datetime(2026, 4, 21, 6, 0)
        occurrence = now - timedelta(hours=1)
        prop = nudges_service.NudgeProposal(
            family_member_id=andrew.id,
            trigger_kind="missed_routine",
            trigger_entity_kind="task_instance",
            trigger_entity_id=__import__("uuid").uuid4(),
            scheduled_for=now,
            severity="low",
            context={
                "name": "Morning",
                "due_time": "01:00 AM",
                "occurrence_at_utc": occurrence,
                "proactivity": "balanced",
            },
        )
        bundle = nudges_service.ProposalBundle(andrew.id, [prop])

        nudges_service.dispatch_with_items(db, [bundle], now)

        parent = db.query(NudgeDispatch).filter_by(family_member_id=andrew.id).one()
        assert parent.status == "suppressed"
        assert parent.suppressed_reason == "quiet_hours"
        assert parent.parent_action_item_id is None
        assert parent.delivered_channels == []
        child_count = db.query(NudgeDispatchItem).filter_by(
            dispatch_id=parent.id
        ).count()
        assert child_count == 1

    def test_high_severity_bypasses_quiet_hours(
        self, db: Session, family, adults
    ):
        andrew = adults["robert"]
        family.timezone = "America/Chicago"
        db.add(
            QuietHoursFamily(
                family_id=family.id,
                start_local_minute=22 * 60,
                end_local_minute=7 * 60,
            )
        )
        db.commit()

        now = datetime(2026, 4, 21, 6, 0)
        occurrence = now - timedelta(hours=1)
        prop = nudges_service.NudgeProposal(
            family_member_id=andrew.id,
            trigger_kind="overdue_task",
            trigger_entity_kind="personal_task",
            trigger_entity_id=__import__("uuid").uuid4(),
            scheduled_for=now,
            severity="high",
            context={
                "title": "urgent",
                "due_time": "05:00 AM",
                "occurrence_at_utc": occurrence,
                "proactivity": "balanced",
            },
        )
        bundle = nudges_service.ProposalBundle(andrew.id, [prop])

        nudges_service.dispatch_with_items(db, [bundle], now)

        parent = db.query(NudgeDispatch).filter_by(family_member_id=andrew.id).one()
        assert parent.status == "delivered"
        assert parent.parent_action_item_id is not None


class TestCrossMidnightDedupe:
    def test_held_proposal_rescanned_does_not_double_dispatch(
        self, db: Session, family, adults, monkeypatch
    ):
        """Scanner emits the same proposal on two back-to-back ticks
        while the first dispatch is held. Second tick's pre-check finds
        the existing child item and skips. Only one parent + one child
        exists at the end."""
        andrew = adults["robert"]
        family.timezone = "America/Chicago"
        db.add(
            QuietHoursFamily(
                family_id=family.id,
                start_local_minute=22 * 60,
                end_local_minute=7 * 60,
            )
        )
        db.commit()

        def no_push(db_arg, **kw):
            raise AssertionError("should not push during hold")

        from app.services import push_service as ps
        monkeypatch.setattr(ps, "send_push", no_push)

        now = datetime(2026, 4, 21, 6, 0)
        occurrence = now - timedelta(hours=1)
        entity_id = __import__("uuid").uuid4()
        def make_prop():
            return nudges_service.NudgeProposal(
                family_member_id=andrew.id,
                trigger_kind="overdue_task",
                trigger_entity_kind="personal_task",
                trigger_entity_id=entity_id,
                scheduled_for=now,
                severity="normal",
                context={
                    "title": "t",
                    "due_time": "05:00 AM",
                    "occurrence_at_utc": occurrence,
                    "proactivity": "balanced",
                },
            )

        # Tick 1: held
        bundle1 = nudges_service.ProposalBundle(andrew.id, [make_prop()])
        nudges_service.dispatch_with_items(db, [bundle1], now)

        # Tick 2 (5 min later, still inside window): scanner re-emits.
        # Pre-check finds the existing child source_dedupe_key. Skip.
        later = now + timedelta(minutes=5)
        bundle2 = nudges_service.ProposalBundle(andrew.id, [make_prop()])
        nudges_service.dispatch_with_items(db, [bundle2], later)

        parent_count = db.query(NudgeDispatch).filter_by(
            family_member_id=andrew.id
        ).count()
        child_count = db.query(NudgeDispatchItem).filter_by(
            family_member_id=andrew.id
        ).count()
        assert parent_count == 1
        assert child_count == 1


class TestNudgesMeRoute:
    def test_returns_empty_list_when_no_dispatches(
        self, db: Session, family, adults, client
    ):
        andrew = adults["robert"]
        token = _make_account_and_token(db, andrew.id, "andrew-nudges@test.app")

        r = client.get(
            "/api/nudges/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        assert r.json() == []

    def test_returns_callers_recent_dispatches(
        self, db: Session, family, adults, client, monkeypatch
    ):
        andrew = adults["robert"]
        token = _make_account_and_token(db, andrew.id, "andrew-nudges@test.app")

        now = _utcnow().replace(tzinfo=None)
        occurrence = now - timedelta(hours=1)
        prop = nudges_service.NudgeProposal(
            family_member_id=andrew.id,
            trigger_kind="overdue_task",
            trigger_entity_kind="personal_task",
            trigger_entity_id=__import__("uuid").uuid4(),
            scheduled_for=occurrence,
            severity="normal",
            context={
                "title": "T",
                "due_time": "08:00 AM",
                "occurrence_at_utc": occurrence,
                "proactivity": "balanced",
            },
        )
        bundle = nudges_service.ProposalBundle(andrew.id, [prop])
        nudges_service.dispatch_with_items(db, [bundle], now)
        db.commit()

        r = client.get(
            "/api/nudges/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert len(body) == 1
        assert body[0]["status"] == "delivered"
        assert body[0]["severity"] == "normal"
        assert body[0]["source_count"] == 1
        assert len(body[0]["items"]) == 1
        assert body[0]["items"][0]["trigger_kind"] == "overdue_task"

    def test_self_scoped_does_not_leak_other_members(
        self, db: Session, family, adults, client
    ):
        """Andrew's call only sees Andrew's dispatches, never Megan's."""
        andrew = adults["robert"]
        megan = adults["megan"]
        token_andrew = _make_account_and_token(db, andrew.id, "andrew-nudges@test.app")

        now = _utcnow().replace(tzinfo=None)
        occurrence = now - timedelta(hours=1)

        # Megan has a dispatch; Andrew does not.
        megan_prop = nudges_service.NudgeProposal(
            family_member_id=megan.id,
            trigger_kind="overdue_task",
            trigger_entity_kind="personal_task",
            trigger_entity_id=__import__("uuid").uuid4(),
            scheduled_for=occurrence,
            severity="normal",
            context={
                "title": "M",
                "due_time": "08:00 AM",
                "occurrence_at_utc": occurrence,
                "proactivity": "balanced",
            },
        )
        nudges_service.dispatch_with_items(
            db, [nudges_service.ProposalBundle(megan.id, [megan_prop])], now
        )
        db.commit()

        r = client.get(
            "/api/nudges/me",
            headers={"Authorization": f"Bearer {token_andrew}"},
        )
        assert r.status_code == 200
        assert r.json() == []

    def test_limit_query_param_respected(
        self, db: Session, family, adults, client
    ):
        andrew = adults["robert"]
        token = _make_account_and_token(db, andrew.id, "andrew-nudges@test.app")
        now = _utcnow().replace(tzinfo=None)

        for i in range(5):
            occurrence = now - timedelta(hours=1 + i)
            prop = nudges_service.NudgeProposal(
                family_member_id=andrew.id,
                trigger_kind="overdue_task",
                trigger_entity_kind="personal_task",
                trigger_entity_id=__import__("uuid").uuid4(),
                scheduled_for=occurrence,
                severity="normal",
                context={
                    "title": f"T{i}",
                    "due_time": "08:00 AM",
                    "occurrence_at_utc": occurrence,
                    "proactivity": "balanced",
                },
            )
            nudges_service.dispatch_with_items(
                db, [nudges_service.ProposalBundle(andrew.id, [prop])], now
            )
        db.commit()

        r = client.get(
            "/api/nudges/me?limit=3",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        assert len(r.json()) == 3

    def test_unauthenticated_returns_401(self, client):
        r = client.get("/api/nudges/me")
        assert r.status_code == 401


class TestAdminQuietHoursRoute:
    def test_get_returns_default_when_unset(
        self, db: Session, family, adults, client
    ):
        """Family has no quiet_hours_family row -> default 22/07."""
        andrew = adults["robert"]
        token = _make_account_and_token(db, andrew.id, "andrew-qh@test.app")

        r = client.get(
            "/api/admin/family-config/quiet-hours",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["start_local_minute"] == 22 * 60
        assert body["end_local_minute"] == 7 * 60
        assert body["is_default"] is True

    def test_put_creates_row_and_subsequent_get_returns_it(
        self, db: Session, family, adults, client
    ):
        andrew = adults["robert"]
        token = _make_account_and_token(db, andrew.id, "andrew-qh@test.app")

        r = client.put(
            "/api/admin/family-config/quiet-hours",
            json={"start_local_minute": 21 * 60, "end_local_minute": 6 * 60},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["start_local_minute"] == 21 * 60
        assert body["end_local_minute"] == 6 * 60
        assert body["is_default"] is False

        r2 = client.get(
            "/api/admin/family-config/quiet-hours",
            headers={"Authorization": f"Bearer {token}"},
        )
        body2 = r2.json()
        assert body2["start_local_minute"] == 21 * 60
        assert body2["is_default"] is False

    def test_put_updates_existing_row(
        self, db: Session, family, adults, client
    ):
        """Calling PUT twice upserts -- second call wins, no duplicate rows."""
        andrew = adults["robert"]
        token = _make_account_and_token(db, andrew.id, "andrew-qh@test.app")
        client.put(
            "/api/admin/family-config/quiet-hours",
            json={"start_local_minute": 21 * 60, "end_local_minute": 6 * 60},
            headers={"Authorization": f"Bearer {token}"},
        )
        r = client.put(
            "/api/admin/family-config/quiet-hours",
            json={"start_local_minute": 23 * 60, "end_local_minute": 7 * 60},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        assert r.json()["start_local_minute"] == 23 * 60
        count = db.query(QuietHoursFamily).filter_by(family_id=family.id).count()
        assert count == 1

    def test_put_rejects_equal_start_end(
        self, db: Session, family, adults, client
    ):
        andrew = adults["robert"]
        token = _make_account_and_token(db, andrew.id, "andrew-qh@test.app")
        r = client.put(
            "/api/admin/family-config/quiet-hours",
            json={"start_local_minute": 22 * 60, "end_local_minute": 22 * 60},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 422

    def test_put_rejects_out_of_range_minute(
        self, db: Session, family, adults, client
    ):
        andrew = adults["robert"]
        token = _make_account_and_token(db, andrew.id, "andrew-qh@test.app")
        r = client.put(
            "/api/admin/family-config/quiet-hours",
            json={"start_local_minute": 1500, "end_local_minute": 7 * 60},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 422

    def test_non_admin_cannot_access(
        self, db: Session, family, adults, children, client
    ):
        """A child-role member should NOT have quiet_hours.manage (only
        PARENT + PRIMARY_PARENT got it from migration 050)."""
        sadie = children["sadie"]
        token = _make_account_and_token(db, sadie.id, "sadie-qh@test.app")

        r = client.get(
            "/api/admin/family-config/quiet-hours",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 403

        r = client.put(
            "/api/admin/family-config/quiet-hours",
            json={"start_local_minute": 22 * 60, "end_local_minute": 7 * 60},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# Sprint 05 Phase 3 Task 2 - compose_body four-fallback matrix
# ---------------------------------------------------------------------------


class TestComposeBody:
    """compose_body wraps orchestrator.generate_nudge_body and falls back
    to the fixed templates on any of four failure conditions per revised
    plan Section 5:
      1. ai_available is false
      2. weekly soft cap hit
      3. moderation / refusal from provider (RuntimeError)
      4. timeout or any other composer exception

    Each fallback logs at INFO with a reason tag. Note: ``ai_available``
    is a read-only ``@property`` on Settings. We force it True in happy-
    path tests by setting its inputs (enable_ai=True + anthropic_api_key
    non-empty) and force it False by clearing enable_ai. This matches the
    existing pattern in test_scheduler_tier1 + test_tier2 + test_tier5.
    """

    def _force_ai_available(self, monkeypatch) -> None:
        from app.config import settings
        monkeypatch.setattr(settings, "enable_ai", True)
        monkeypatch.setattr(settings, "anthropic_api_key", "sk-test")

    def test_empty_proposals_returns_empty_string(
        self, db: Session, family, adults
    ):
        assert nudges_service.compose_body(db, family.id, [], _utcnow()) == ""

    def test_happy_path_returns_composer_output(
        self, db: Session, family, adults, monkeypatch
    ):
        self._force_ai_available(monkeypatch)
        andrew = adults["robert"]
        now = _utcnow().replace(tzinfo=None)
        prop = nudges_service.NudgeProposal(
            family_member_id=andrew.id,
            trigger_kind="overdue_task",
            trigger_entity_kind="personal_task",
            trigger_entity_id=uuid.uuid4(),
            scheduled_for=now,
            severity="normal",
            context={
                "title": "Take out bins",
                "due_time": "08:00 AM",
                "occurrence_at_utc": now,
            },
        )

        captured = {}

        def fake_generate(**kwargs):
            captured.update(kwargs)
            return "Reminder: take out the trash, please."

        from app.ai import orchestrator as orch
        monkeypatch.setattr(orch, "generate_nudge_body", fake_generate)

        body = nudges_service.compose_body(db, family.id, [prop], now)
        assert body == "Reminder: take out the trash, please."
        assert captured["family_member_id"] == andrew.id
        assert captured["proposal_summaries"][0]["trigger_kind"] == "overdue_task"
        assert captured["proposal_summaries"][0]["title"] == "Take out bins"

    def test_fallback_when_ai_unavailable(
        self, db: Session, family, adults, monkeypatch
    ):
        """Force ai_available=False by clearing enable_ai. The orchestrator
        must not be invoked on this path."""
        andrew = adults["robert"]
        now = _utcnow().replace(tzinfo=None)
        prop = nudges_service.NudgeProposal(
            family_member_id=andrew.id,
            trigger_kind="overdue_task",
            trigger_entity_kind="personal_task",
            trigger_entity_id=uuid.uuid4(),
            scheduled_for=now,
            severity="normal",
            context={"title": "T", "due_time": "08:00 AM", "occurrence_at_utc": now},
        )

        from app.config import settings
        monkeypatch.setattr(settings, "enable_ai", False)
        monkeypatch.setattr(settings, "anthropic_api_key", "")

        def fake_generate(**kwargs):
            raise AssertionError(
                "orchestrator should not be called when ai_available=False"
            )

        from app.ai import orchestrator as orch
        monkeypatch.setattr(orch, "generate_nudge_body", fake_generate)

        body = nudges_service.compose_body(db, family.id, [prop], now)
        assert body == "Reminder: T was due at 08:00 AM."

    def test_fallback_when_soft_cap_hit(
        self, db: Session, family, adults, monkeypatch
    ):
        self._force_ai_available(monkeypatch)
        andrew = adults["robert"]
        now = _utcnow().replace(tzinfo=None)
        prop = nudges_service.NudgeProposal(
            family_member_id=andrew.id,
            trigger_kind="overdue_task",
            trigger_entity_kind="personal_task",
            trigger_entity_id=uuid.uuid4(),
            scheduled_for=now,
            severity="normal",
            context={"title": "T", "due_time": "08:00 AM", "occurrence_at_utc": now},
        )

        from app.ai import pricing
        monkeypatch.setattr(
            pricing, "build_usage_report",
            lambda **kwargs: {"cap_warning": True, "approx_cost_usd": 9999},
        )

        called = []

        def fake_generate(**kwargs):
            called.append(1)
            return "should not be returned"

        from app.ai import orchestrator as orch
        monkeypatch.setattr(orch, "generate_nudge_body", fake_generate)

        body = nudges_service.compose_body(db, family.id, [prop], now)
        assert body == "Reminder: T was due at 08:00 AM."
        assert called == []

    def test_fallback_on_composer_runtime_error_moderation(
        self, db: Session, family, adults, monkeypatch
    ):
        """orchestrator raises RuntimeError when stop_reason is moderation
        or refusal. compose_body falls back to the fixed template."""
        self._force_ai_available(monkeypatch)
        andrew = adults["robert"]
        now = _utcnow().replace(tzinfo=None)
        prop = nudges_service.NudgeProposal(
            family_member_id=andrew.id,
            trigger_kind="overdue_task",
            trigger_entity_kind="personal_task",
            trigger_entity_id=uuid.uuid4(),
            scheduled_for=now,
            severity="normal",
            context={"title": "T", "due_time": "08:00 AM", "occurrence_at_utc": now},
        )

        def raising(**kwargs):
            raise RuntimeError("moderation rejected output")

        from app.ai import orchestrator as orch
        monkeypatch.setattr(orch, "generate_nudge_body", raising)

        body = nudges_service.compose_body(db, family.id, [prop], now)
        assert body == "Reminder: T was due at 08:00 AM."

    def test_fallback_on_composer_timeout(
        self, db: Session, family, adults, monkeypatch
    ):
        """A timeout (or any other exception) also routes to fallback."""
        self._force_ai_available(monkeypatch)
        andrew = adults["robert"]
        now = _utcnow().replace(tzinfo=None)
        prop = nudges_service.NudgeProposal(
            family_member_id=andrew.id,
            trigger_kind="overdue_task",
            trigger_entity_kind="personal_task",
            trigger_entity_id=uuid.uuid4(),
            scheduled_for=now,
            severity="normal",
            context={"title": "T", "due_time": "08:00 AM", "occurrence_at_utc": now},
        )

        def raising(**kwargs):
            raise TimeoutError("deadline exceeded")

        from app.ai import orchestrator as orch
        monkeypatch.setattr(orch, "generate_nudge_body", raising)

        body = nudges_service.compose_body(db, family.id, [prop], now)
        assert body == "Reminder: T was due at 08:00 AM."

    def test_multi_proposal_bundle_falls_back_to_composite_template(
        self, db: Session, family, adults, monkeypatch
    ):
        """2 proposals + AI failure -> multi-item template, not single-item."""
        self._force_ai_available(monkeypatch)
        andrew = adults["robert"]
        now = _utcnow().replace(tzinfo=None)
        props = [
            nudges_service.NudgeProposal(
                family_member_id=andrew.id,
                trigger_kind="overdue_task",
                trigger_entity_kind="personal_task",
                trigger_entity_id=uuid.uuid4(),
                scheduled_for=now,
                severity="normal",
                context={
                    "title": f"Task {i}",
                    "due_time": "08:00 AM",
                    "occurrence_at_utc": now,
                },
            )
            for i in range(2)
        ]

        def raising(**kwargs):
            raise RuntimeError("composer down")

        from app.ai import orchestrator as orch
        monkeypatch.setattr(orch, "generate_nudge_body", raising)

        body = nudges_service.compose_body(db, family.id, props, now)
        assert "2 items to check" in body
        assert "Task 0" in body
        assert "Task 1" in body

    def test_compose_body_preserves_ai_generated_body(
        self, db: Session, family, adults
    ):
        """AI-discovery proposals carry a pre-composed body in
        context['body']. compose_body must return it verbatim instead of
        re-running the P3 composer or falling to the '_render_body'
        template (which has no 'ai_suggested' entry and would return
        'Scout nudge').
        """
        andrew = adults["robert"]
        now = _utcnow().replace(tzinfo=None)

        p = nudges_service.NudgeProposal(
            family_member_id=andrew.id,
            trigger_kind="ai_suggested",
            trigger_entity_kind="ai_discovery",
            trigger_entity_id=None,
            scheduled_for=now,
            severity="normal",
            context={
                "body": "Sally has soccer at 4pm today; pack cleats.",
                "ai_generated": True,
                "occurrence_at_utc": now,
            },
        )
        body = nudges_service.compose_body(db, family.id, [p], now)
        assert body == "Sally has soccer at 4pm today; pack cleats."

    def test_compose_body_skips_ai_shortcut_for_mixed_bundles(
        self, db: Session, family, adults
    ):
        """When the bundle has more than one proposal (mixed AI +
        scanner), the AI shortcut does NOT fire; the normal composer path
        runs so multi-item nudges get summarized correctly.
        """
        andrew = adults["robert"]
        now = _utcnow().replace(tzinfo=None)

        p_ai = nudges_service.NudgeProposal(
            family_member_id=andrew.id,
            trigger_kind="ai_suggested",
            trigger_entity_kind="ai_discovery",
            trigger_entity_id=None,
            scheduled_for=now,
            severity="normal",
            context={
                "body": "AI body here",
                "ai_generated": True,
                "occurrence_at_utc": now,
            },
        )
        p_scanner = nudges_service.NudgeProposal(
            family_member_id=andrew.id,
            trigger_kind="overdue_task",
            trigger_entity_kind="personal_task",
            trigger_entity_id=uuid.uuid4(),
            scheduled_for=now,
            severity="normal",
            context={"title": "trash", "occurrence_at_utc": now},
        )
        body = nudges_service.compose_body(
            db, family.id, [p_ai, p_scanner], now
        )
        # Shortcut should NOT fire; either the composer runs or the
        # template fallback - both acceptable. The only non-acceptable
        # outcome is returning "AI body here" from the shortcut.
        assert body != "AI body here"


class TestPersonalitySubstringMatrix:
    """Per revised plan Section 8 acceptance criterion: >=3
    personalities asserting the composed body carries tone-marker
    substrings from the preamble. Mocks orchestrator.generate_nudge_body
    to return preamble-derived text so we can assert deterministically."""

    def _force_ai_available(self, monkeypatch) -> None:
        from app.config import settings
        monkeypatch.setattr(settings, "enable_ai", True)
        monkeypatch.setattr(settings, "anthropic_api_key", "sk-test")

    def _compose_for_member(self, db, member_id, proposal_context=None):
        """Build a minimal proposal and call compose_body."""
        now = _utcnow().replace(tzinfo=None)
        ctx = proposal_context or {
            "title": "Dishes",
            "due_time": "08:00 AM",
            "occurrence_at_utc": now,
        }
        prop = nudges_service.NudgeProposal(
            family_member_id=member_id,
            trigger_kind="overdue_task",
            trigger_entity_kind="personal_task",
            trigger_entity_id=__import__("uuid").uuid4(),
            scheduled_for=now,
            severity="normal",
            context=ctx,
        )
        return prop, now

    def test_terse_personality_body_reflects_tone(
        self, db: Session, family, adults, monkeypatch
    ):
        self._force_ai_available(monkeypatch)
        andrew = adults["robert"]
        from app.services import ai_personality_service
        # Tone=direct, verbosity=short -> terse profile
        ai_personality_service.upsert_personality(
            db,
            family_member_id=andrew.id,
            payload={"tone": "direct", "verbosity": "short"},
        )

        captured = {}

        def fake_generate(**kwargs):
            captured.update(kwargs)
            preamble = kwargs.get("personality_preamble", "")
            # Return something that clearly reflects the preamble tone
            return f"[terse-reply] tone:{'direct' in preamble} short:{'short' in preamble}"

        from app.ai import orchestrator as orch
        monkeypatch.setattr(orch, "generate_nudge_body", fake_generate)

        prop, now = self._compose_for_member(db, andrew.id)
        body = nudges_service.compose_body(db, family.id, [prop], now)

        assert "direct" in captured["personality_preamble"]
        assert "short" in captured["personality_preamble"]
        assert "tone:True" in body
        assert "short:True" in body

    def test_warm_personality_body_reflects_tone(
        self, db: Session, family, adults, monkeypatch
    ):
        self._force_ai_available(monkeypatch)
        megan = adults["megan"]
        from app.services import ai_personality_service
        ai_personality_service.upsert_personality(
            db,
            family_member_id=megan.id,
            payload={"tone": "warm", "humor": "light"},
        )

        captured = {}

        def fake_generate(**kwargs):
            captured.update(kwargs)
            return "[warm-reply]"

        from app.ai import orchestrator as orch
        monkeypatch.setattr(orch, "generate_nudge_body", fake_generate)

        prop, now = self._compose_for_member(db, megan.id)
        body = nudges_service.compose_body(db, family.id, [prop], now)

        assert "warm" in captured["personality_preamble"]
        assert "light" in captured["personality_preamble"]
        assert body == "[warm-reply]"

    def test_formal_personality_body_reflects_tone(
        self, db: Session, family, adults, monkeypatch
    ):
        self._force_ai_available(monkeypatch)
        andrew = adults["robert"]
        from app.services import ai_personality_service
        ai_personality_service.upsert_personality(
            db,
            family_member_id=andrew.id,
            payload={"tone": "professional", "formality": "formal"},
        )

        captured = {}

        def fake_generate(**kwargs):
            captured.update(kwargs)
            return "[formal-reply]"

        from app.ai import orchestrator as orch
        monkeypatch.setattr(orch, "generate_nudge_body", fake_generate)

        prop, now = self._compose_for_member(db, andrew.id)
        body = nudges_service.compose_body(db, family.id, [prop], now)

        assert "professional" in captured["personality_preamble"]
        assert "formal" in captured["personality_preamble"]
        assert body == "[formal-reply]"


class TestDispatchUsesComposeBody:
    def _force_ai_available(self, monkeypatch) -> None:
        from app.config import settings
        monkeypatch.setattr(settings, "enable_ai", True)
        monkeypatch.setattr(settings, "anthropic_api_key", "sk-test")

    def test_dispatch_writes_ai_composed_body_when_available(
        self, db: Session, family, adults, monkeypatch
    ):
        """dispatch_with_items -> compose_body -> generate_nudge_body
        when AI is available. The parent.body reflects the composer
        return value (mocked)."""
        self._force_ai_available(monkeypatch)
        andrew = adults["robert"]
        now = _utcnow().replace(tzinfo=None)
        prop = nudges_service.NudgeProposal(
            family_member_id=andrew.id,
            trigger_kind="overdue_task",
            trigger_entity_kind="personal_task",
            trigger_entity_id=__import__("uuid").uuid4(),
            scheduled_for=now - timedelta(hours=1),
            severity="normal",
            context={
                "title": "Dishes",
                "due_time": "08:00 AM",
                "occurrence_at_utc": now - timedelta(hours=1),
                "proactivity": "balanced",
            },
        )
        bundle = nudges_service.ProposalBundle(andrew.id, [prop])

        def fake_generate(**kwargs):
            return "Custom AI copy here."

        from app.ai import orchestrator as orch
        monkeypatch.setattr(orch, "generate_nudge_body", fake_generate)

        nudges_service.dispatch_with_items(db, [bundle], now)

        parent = db.query(NudgeDispatch).filter_by(
            family_member_id=andrew.id
        ).one()
        assert parent.body == "Custom AI copy here."

    def test_dispatch_falls_back_when_composer_raises(
        self, db: Session, family, adults, monkeypatch
    ):
        """When the composer raises, dispatch still writes the parent
        + child with the fixed-template body."""
        self._force_ai_available(monkeypatch)
        andrew = adults["robert"]
        now = _utcnow().replace(tzinfo=None)
        prop = nudges_service.NudgeProposal(
            family_member_id=andrew.id,
            trigger_kind="overdue_task",
            trigger_entity_kind="personal_task",
            trigger_entity_id=__import__("uuid").uuid4(),
            scheduled_for=now - timedelta(hours=1),
            severity="normal",
            context={
                "title": "Dishes",
                "due_time": "08:00 AM",
                "occurrence_at_utc": now - timedelta(hours=1),
                "proactivity": "balanced",
            },
        )
        bundle = nudges_service.ProposalBundle(andrew.id, [prop])

        def raising(**kwargs):
            raise RuntimeError("composer down")

        from app.ai import orchestrator as orch
        monkeypatch.setattr(orch, "generate_nudge_body", raising)

        nudges_service.dispatch_with_items(db, [bundle], now)

        parent = db.query(NudgeDispatch).filter_by(
            family_member_id=andrew.id
        ).one()
        assert parent.body == "Reminder: Dishes was due at 08:00 AM."


class TestProcessPendingDispatches:
    def test_returns_zero_when_no_pending_eligible(
        self, db: Session, family, adults
    ):
        now = _utcnow().replace(tzinfo=None)
        written = nudges_service.process_pending_dispatches(db, now)
        assert written == 0

    def test_surfaces_eligible_held_dispatch(
        self, db: Session, family, adults, monkeypatch
    ):
        """A held dispatch whose deliver_after_utc has arrived gets
        an Inbox row, push call, status='delivered'."""
        andrew = adults["robert"]
        family.timezone = "America/Chicago"
        db.add(
            QuietHoursFamily(
                family_id=family.id,
                start_local_minute=22 * 60,
                end_local_minute=7 * 60,
            )
        )
        db.commit()

        _force_compose_fallback(monkeypatch)

        # Tick 1: 06:00 UTC inside quiet window -> held
        t1 = datetime(2026, 4, 21, 6, 0)
        occurrence = t1 - timedelta(hours=1)
        prop = nudges_service.NudgeProposal(
            family_member_id=andrew.id,
            trigger_kind="overdue_task",
            trigger_entity_kind="personal_task",
            trigger_entity_id=__import__("uuid").uuid4(),
            scheduled_for=t1,
            severity="normal",
            context={
                "title": "Trash",
                "due_time": "05:00 AM",
                "occurrence_at_utc": occurrence,
                "proactivity": "balanced",
            },
        )
        bundle = nudges_service.ProposalBundle(andrew.id, [prop])
        nudges_service.dispatch_with_items(db, [bundle], t1)

        parent = db.query(NudgeDispatch).filter_by(family_member_id=andrew.id).one()
        assert parent.status == "pending"
        # TIMESTAMPTZ hydrates aware in session TZ; compare the UTC moment.
        expected_hold_utc = datetime(2026, 4, 21, 12, 0, tzinfo=timezone.utc)
        actual_after = parent.deliver_after_utc
        if actual_after.tzinfo is None:
            actual_after = actual_after.replace(tzinfo=timezone.utc)
        assert actual_after.astimezone(timezone.utc) == expected_hold_utc
        assert parent.parent_action_item_id is None

        # Tick 2: 12:30 UTC past the window end
        fake_delivery_id = __import__("uuid").uuid4()

        # Seed active device so push fires
        from app.models.push import PushDevice
        device = PushDevice(
            family_member_id=andrew.id,
            expo_push_token="ExponentPushToken[fake]",
            device_label="iPhone",
            platform="ios",
            is_active=True,
            last_registered_at=t1,
        )
        db.add(device)
        db.commit()

        device_id = device.id

        def fake_send_push(db_arg, **kwargs):
            pd = __import__("app.models.push", fromlist=["PushDelivery"]).PushDelivery(
                family_member_id=kwargs["family_member_id"],
                push_device_id=device_id,
                category=kwargs["category"],
                title=kwargs["title"],
                body=kwargs["body"],
                data=kwargs.get("data") or {},
                trigger_source=kwargs.get("trigger_source", "nudge_deliver_pending"),
                status="provider_accepted",
                provider="expo",
                notification_group_id=__import__("uuid").uuid4(),
            )
            db_arg.add(pd)
            db_arg.flush()
            from types import SimpleNamespace
            return SimpleNamespace(
                delivery_ids=[pd.id],
                accepted_count=1,
                error_count=0,
                notification_group_id=pd.notification_group_id,
            )

        from app.services import push_service as ps
        monkeypatch.setattr(ps, "send_push", fake_send_push)

        t2 = datetime(2026, 4, 21, 12, 30)
        written = nudges_service.process_pending_dispatches(db, t2)
        assert written == 1

        db.refresh(parent)
        assert parent.status == "delivered"
        # TIMESTAMPTZ hydrates aware in session TZ; compare UTC moment.
        actual_delivered = parent.delivered_at_utc
        if actual_delivered.tzinfo is None:
            actual_delivered = actual_delivered.replace(tzinfo=timezone.utc)
        assert actual_delivered.astimezone(timezone.utc) == t2.replace(
            tzinfo=timezone.utc
        )
        assert parent.parent_action_item_id is not None
        assert "inbox" in parent.delivered_channels
        assert "push" in parent.delivered_channels

    def test_not_yet_eligible_held_is_skipped(
        self, db: Session, family, adults, monkeypatch
    ):
        """deliver_after_utc is in the future -> do nothing."""
        andrew = adults["robert"]
        family.timezone = "America/Chicago"
        db.add(
            QuietHoursFamily(
                family_id=family.id,
                start_local_minute=22 * 60,
                end_local_minute=7 * 60,
            )
        )
        db.commit()

        _force_compose_fallback(monkeypatch)

        t1 = datetime(2026, 4, 21, 6, 0)
        occurrence = t1 - timedelta(hours=1)
        prop = nudges_service.NudgeProposal(
            family_member_id=andrew.id,
            trigger_kind="overdue_task",
            trigger_entity_kind="personal_task",
            trigger_entity_id=__import__("uuid").uuid4(),
            scheduled_for=t1,
            severity="normal",
            context={
                "title": "T",
                "due_time": "05:00 AM",
                "occurrence_at_utc": occurrence,
                "proactivity": "balanced",
            },
        )
        bundle = nudges_service.ProposalBundle(andrew.id, [prop])
        nudges_service.dispatch_with_items(db, [bundle], t1)

        # Tick at 08:00 UTC -- still before 12:00 UTC window end
        written = nudges_service.process_pending_dispatches(db, datetime(2026, 4, 21, 8, 0))
        assert written == 0

        parent = db.query(NudgeDispatch).filter_by(family_member_id=andrew.id).one()
        assert parent.status == "pending"

    def test_delivered_rows_are_not_reprocessed(
        self, db: Session, family, adults, monkeypatch
    ):
        andrew = adults["robert"]
        now = _utcnow().replace(tzinfo=None)
        occurrence = now - timedelta(hours=1)

        _force_compose_fallback(monkeypatch)

        def fake_send_push(db_arg, **kwargs):
            from types import SimpleNamespace
            return SimpleNamespace(
                delivery_ids=[],
                accepted_count=0,
                error_count=0,
                notification_group_id=__import__("uuid").uuid4(),
            )

        from app.services import push_service as ps
        monkeypatch.setattr(ps, "send_push", fake_send_push)

        # Fresh dispatch at "deliver" path -> status='delivered' already
        prop = nudges_service.NudgeProposal(
            family_member_id=andrew.id,
            trigger_kind="overdue_task",
            trigger_entity_kind="personal_task",
            trigger_entity_id=__import__("uuid").uuid4(),
            scheduled_for=now,
            severity="normal",
            context={
                "title": "T",
                "due_time": "08:00 AM",
                "occurrence_at_utc": occurrence,
                "proactivity": "balanced",
            },
        )
        bundle = nudges_service.ProposalBundle(andrew.id, [prop])
        nudges_service.dispatch_with_items(db, [bundle], now)

        parent = db.query(NudgeDispatch).filter_by(family_member_id=andrew.id).one()
        assert parent.status == "delivered"
        original_inbox_id = parent.parent_action_item_id

        # Now call process_pending_dispatches -- the delivered row must not
        # be touched.
        written = nudges_service.process_pending_dispatches(db, now + timedelta(hours=1))
        assert written == 0

        db.refresh(parent)
        assert parent.parent_action_item_id == original_inbox_id
        inbox_count = db.query(ParentActionItem).filter_by(
            entity_id=prop.trigger_entity_id
        ).count()
        assert inbox_count == 1  # no duplicate

    def test_suppressed_rows_are_not_processed(
        self, db: Session, family, adults, monkeypatch
    ):
        """status='suppressed' (low severity inside quiet window) stays
        suppressed; no Inbox row is ever written for it."""
        andrew = adults["robert"]
        family.timezone = "America/Chicago"
        db.add(
            QuietHoursFamily(
                family_id=family.id,
                start_local_minute=22 * 60,
                end_local_minute=7 * 60,
            )
        )
        db.commit()

        _force_compose_fallback(monkeypatch)

        t1 = datetime(2026, 4, 21, 6, 0)
        occurrence = t1 - timedelta(hours=1)
        prop = nudges_service.NudgeProposal(
            family_member_id=andrew.id,
            trigger_kind="missed_routine",
            trigger_entity_kind="task_instance",
            trigger_entity_id=__import__("uuid").uuid4(),
            scheduled_for=t1,
            severity="low",
            context={
                "name": "Morning",
                "due_time": "01:00 AM",
                "occurrence_at_utc": occurrence,
                "proactivity": "balanced",
            },
        )
        bundle = nudges_service.ProposalBundle(andrew.id, [prop])
        nudges_service.dispatch_with_items(db, [bundle], t1)

        parent = db.query(NudgeDispatch).filter_by(family_member_id=andrew.id).one()
        assert parent.status == "suppressed"

        # Call the worker WAY later
        written = nudges_service.process_pending_dispatches(db, t1 + timedelta(days=7))
        assert written == 0

        db.refresh(parent)
        assert parent.status == "suppressed"
        assert parent.parent_action_item_id is None

    def test_push_error_does_not_poison_inbox_write(
        self, db: Session, family, adults, monkeypatch
    ):
        """If push raises, the Inbox still lands and status goes to
        'delivered' with delivered_channels = ['inbox'] only."""
        andrew = adults["robert"]
        family.timezone = "America/Chicago"
        db.add(
            QuietHoursFamily(
                family_id=family.id,
                start_local_minute=22 * 60,
                end_local_minute=7 * 60,
            )
        )
        db.commit()

        _force_compose_fallback(monkeypatch)

        t1 = datetime(2026, 4, 21, 6, 0)
        occurrence = t1 - timedelta(hours=1)
        prop = nudges_service.NudgeProposal(
            family_member_id=andrew.id,
            trigger_kind="overdue_task",
            trigger_entity_kind="personal_task",
            trigger_entity_id=__import__("uuid").uuid4(),
            scheduled_for=t1,
            severity="normal",
            context={
                "title": "T",
                "due_time": "05:00 AM",
                "occurrence_at_utc": occurrence,
                "proactivity": "balanced",
            },
        )
        bundle = nudges_service.ProposalBundle(andrew.id, [prop])
        nudges_service.dispatch_with_items(db, [bundle], t1)

        from app.models.push import PushDevice
        db.add(
            PushDevice(
                family_member_id=andrew.id,
                expo_push_token="ExponentPushToken[fake]",
                device_label="iPhone",
                platform="ios",
                is_active=True,
                last_registered_at=t1,
            )
        )
        db.commit()

        def raising(db_arg, **kwargs):
            raise RuntimeError("expo is down")

        from app.services import push_service as ps
        monkeypatch.setattr(ps, "send_push", raising)

        t2 = datetime(2026, 4, 21, 12, 30)
        written = nudges_service.process_pending_dispatches(db, t2)
        assert written == 1

        parent = db.query(NudgeDispatch).filter_by(family_member_id=andrew.id).one()
        assert parent.status == "delivered"
        assert parent.parent_action_item_id is not None
        assert parent.delivered_channels == ["inbox"]
        assert parent.push_delivery_id is None


class TestProcessPendingDispatchesTick:
    def test_end_to_end_tick_surfaces_held_dispatch(
        self, db: Session, family, adults, monkeypatch
    ):
        """Simulated two-tick flow without the real scheduler:
        - tick 1: run_nudge_scan writes a held dispatch (in window)
        - tick 2: process_pending_dispatches surfaces it (after window)
        Verifies the functions chain correctly as the scheduler will
        call them on the same 5-min tick."""
        andrew = adults["robert"]
        family.timezone = "America/Chicago"
        db.add(
            QuietHoursFamily(
                family_id=family.id,
                start_local_minute=22 * 60,
                end_local_minute=7 * 60,
            )
        )
        db.commit()

        _force_compose_fallback(monkeypatch)

        # Seed active device so push path fires post-window
        db.add(
            PushDevice(
                family_member_id=andrew.id,
                expo_push_token="ExponentPushToken[fake]",
                device_label="iPhone",
                platform="ios",
                is_active=True,
                last_registered_at=datetime(2026, 4, 20, 12, 0),
            )
        )

        # Create an overdue task
        t1 = datetime(2026, 4, 21, 6, 0)
        db.add(
            PersonalTask(
                family_id=family.id,
                assigned_to=andrew.id,
                title="T",
                status="pending",
                due_at=t1 - timedelta(hours=1),
            )
        )
        db.commit()

        def fake_send_push(db_arg, **kwargs):
            device = db_arg.query(PushDevice).filter_by(
                family_member_id=kwargs["family_member_id"],
                is_active=True,
            ).first()
            assert device is not None
            pd = __import__("app.models.push", fromlist=["PushDelivery"]).PushDelivery(
                family_member_id=kwargs["family_member_id"],
                push_device_id=device.id,
                category=kwargs["category"],
                title=kwargs["title"],
                body=kwargs["body"],
                data=kwargs.get("data") or {},
                trigger_source=kwargs.get("trigger_source", "nudge"),
                status="provider_accepted",
                provider="expo",
                notification_group_id=__import__("uuid").uuid4(),
            )
            db_arg.add(pd)
            db_arg.flush()
            from types import SimpleNamespace
            return SimpleNamespace(
                delivery_ids=[pd.id],
                accepted_count=1,
                error_count=0,
                notification_group_id=pd.notification_group_id,
            )

        from app.services import push_service as ps
        monkeypatch.setattr(ps, "send_push", fake_send_push)

        # Tick 1: in quiet window -> dispatch is held
        written = nudges_service.run_nudge_scan(db, now_utc=t1)
        assert written >= 1
        parent = db.query(NudgeDispatch).filter_by(family_member_id=andrew.id).one()
        assert parent.status == "pending"
        assert parent.parent_action_item_id is None

        # Tick 2 at window end: process_pending_dispatches_tick surfaces it
        t2 = datetime(2026, 4, 21, 12, 30)
        nudges_service.process_pending_dispatches_tick(db, now_utc=t2)
        db.commit()

        db.refresh(parent)
        assert parent.status == "delivered"
        assert parent.parent_action_item_id is not None
        assert "inbox" in parent.delivered_channels
        assert "push" in parent.delivered_channels


class TestExecuteValidatedRuleSQL:
    def _make_rule_input_tables(self, db, family, member):
        """Seed a couple of rows in approved tables so a rule can find them."""
        now = _utcnow().replace(tzinfo=None)
        db.add(PersonalTask(
            family_id=family.id,
            assigned_to=member.id,
            title="Rule-test-task",
            status="pending",
            due_at=now - timedelta(hours=1),
        ))
        db.commit()

    def test_happy_path_returns_rows(self, db: Session, family, adults):
        andrew = adults["robert"]
        self._make_rule_input_tables(db, family, andrew)

        canonical = (
            "SELECT assigned_to AS member_id, id AS entity_id, "
            "'personal_task' AS entity_kind, due_at AS scheduled_for "
            "FROM personal_tasks WHERE status = 'pending' LIMIT 100"
        )
        rows = nudges_service.execute_validated_rule_sql(db, canonical, {})
        assert len(rows) >= 1
        assert "member_id" in rows[0]
        assert "entity_id" in rows[0]
        assert "entity_kind" in rows[0]
        assert "scheduled_for" in rows[0]

    def test_caps_at_200_rows(self, db: Session, family, adults):
        """Seed 250 personal_tasks; rule SELECT returns 200 rows capped."""
        andrew = adults["robert"]
        now = _utcnow().replace(tzinfo=None)
        for i in range(250):
            db.add(PersonalTask(
                family_id=family.id,
                assigned_to=andrew.id,
                title=f"Task {i}",
                status="pending",
                due_at=now - timedelta(hours=1),
            ))
        db.commit()

        canonical = (
            "SELECT assigned_to AS member_id, id AS entity_id, "
            "'personal_task' AS entity_kind, due_at AS scheduled_for "
            "FROM personal_tasks"
        )
        rows = nudges_service.execute_validated_rule_sql(db, canonical, {})
        assert len(rows) == 200

    def test_missing_required_column_raises_schema_error(
        self, db: Session, family, adults
    ):
        """Rule SQL that doesn't include all four required columns."""
        andrew = adults["robert"]
        # Still need a row to reach the row-shape check
        db.add(PersonalTask(
            family_id=family.id,
            assigned_to=andrew.id,
            title="t",
            status="pending",
            due_at=_utcnow().replace(tzinfo=None) - timedelta(hours=1),
        ))
        db.commit()

        # Missing entity_kind and scheduled_for
        canonical = "SELECT assigned_to AS member_id, id AS entity_id FROM personal_tasks LIMIT 1"
        from app.services.nudge_rule_validator import RuleExecutionError
        with pytest.raises(RuleExecutionError, match=r"^\[schema\]"):
            nudges_service.execute_validated_rule_sql(db, canonical, {})

    def test_bind_parameters(self, db: Session, family, adults):
        andrew = adults["robert"]
        now = _utcnow().replace(tzinfo=None)
        db.add(PersonalTask(
            family_id=family.id,
            assigned_to=andrew.id,
            title="Rule-test-task",
            status="pending",
            due_at=now - timedelta(hours=1),
        ))
        db.commit()

        canonical = (
            "SELECT assigned_to AS member_id, id AS entity_id, "
            "'personal_task' AS entity_kind, due_at AS scheduled_for "
            "FROM personal_tasks WHERE status = :wanted LIMIT 100"
        )
        rows = nudges_service.execute_validated_rule_sql(
            db, canonical, {"wanted": "pending"}
        )
        assert len(rows) >= 1

    def test_statement_timeout_is_honored(self, db: Session, family, adults):
        """A pg_sleep-style query would fail validation, but a self-cross-join
        style slow query is harder to build in the allowlist. Assert timeout
        behavior by using an extremely short timeout on a query that will
        reliably exceed it."""
        andrew = adults["robert"]
        # Force a self-join that scans every row twice.
        now = _utcnow().replace(tzinfo=None)
        for i in range(500):
            db.add(PersonalTask(
                family_id=family.id,
                assigned_to=andrew.id,
                title=f"t{i}",
                status="pending",
                due_at=now,
            ))
        db.commit()

        canonical = (
            "SELECT a.assigned_to AS member_id, a.id AS entity_id, "
            "'personal_task' AS entity_kind, a.due_at AS scheduled_for "
            "FROM personal_tasks a JOIN personal_tasks b "
            "ON a.assigned_to = b.assigned_to"
        )
        from app.services.nudge_rule_validator import RuleExecutionError
        with pytest.raises(RuleExecutionError, match=r"^\[timeout\]|^\[db_error\]"):
            # 1ms -- nearly any real query exceeds this
            nudges_service.execute_validated_rule_sql(
                db, canonical, {}, statement_timeout_ms=1
            )


class TestScanRuleTriggers:
    def test_no_active_rules_returns_empty(
        self, db: Session, family, adults
    ):
        now = _utcnow().replace(tzinfo=None)
        assert nudges_service.scan_rule_triggers(db, now) == []

    def test_active_rule_emits_proposals(
        self, db: Session, family, adults
    ):
        from app.models.nudge_rules import NudgeRule
        andrew = adults["robert"]
        now = _utcnow().replace(tzinfo=None)

        db.add(PersonalTask(
            family_id=family.id,
            assigned_to=andrew.id,
            title="task A",
            status="pending",
            due_at=now - timedelta(hours=1),
        ))
        db.add(NudgeRule(
            family_id=family.id,
            name="overdue-test-rule",
            is_active=True,
            source_kind="sql_template",
            template_sql="SELECT 1",  # unused at scan time
            canonical_sql=(
                "SELECT assigned_to AS member_id, id AS entity_id, "
                "'personal_task' AS entity_kind, due_at AS scheduled_for "
                "FROM personal_tasks WHERE status = 'pending' LIMIT 100"
            ),
            trigger_kind="custom_rule",
            default_lead_time_minutes=0,
            severity="normal",
        ))
        db.commit()

        proposals = nudges_service.scan_rule_triggers(db, now)
        assert len(proposals) >= 1
        p = proposals[0]
        assert p.family_member_id == andrew.id
        assert p.trigger_kind == "custom_rule"
        assert p.trigger_entity_kind == "personal_task"
        assert p.severity == "normal"

    def test_rule_cannot_emit_member_from_other_family(
        self, db: Session, family, adults
    ):
        """Family-scope enforcement: a rule authored in Family A whose
        canonical SQL names a Family B member's id must have that row
        dropped before a NudgeProposal is emitted. This is the
        regression test for the admin-rule cross-tenant leak.
        """
        from app.models.foundation import Family, FamilyMember
        from app.models.nudge_rules import NudgeRule

        now = _utcnow().replace(tzinfo=None)

        # Seed Family B with one member whose id the attacker-rule will
        # try to emit. Family A is the `family` fixture (authoring tenant).
        other_family = Family(name="Other", timezone="UTC")
        db.add(other_family)
        db.flush()
        other_member = FamilyMember(
            family_id=other_family.id,
            first_name="Outsider",
            last_name="X",
            role="adult",
            birthdate=date(1990, 1, 1),
        )
        db.add(other_member)
        db.flush()

        # Rule belongs to Family A, but its canonical SQL selects the
        # Family B member's id verbatim. The allowlist permits
        # family_members, so the validator-canonicalized form reads it
        # back directly. Hardcoding the UUID via f-string is fine here;
        # this test exercises the scanner's filter, not the validator.
        canonical = (
            "SELECT id AS member_id, id AS entity_id, "
            "'personal_task' AS entity_kind, now() AS scheduled_for "
            f"FROM family_members WHERE id = '{other_member.id}'"
        )
        db.add(NudgeRule(
            family_id=family.id,
            name="cross-family-attempt",
            is_active=True,
            source_kind="sql_template",
            template_sql="SELECT 1",  # unused at scan time
            canonical_sql=canonical,
            trigger_kind="custom_rule",
            default_lead_time_minutes=0,
            severity="normal",
        ))
        db.commit()

        proposals = nudges_service.scan_rule_triggers(db, now)
        # No proposal may carry a Family B member_id, even though the
        # rule's SQL explicitly named one.
        assert not any(
            p.family_member_id == other_member.id for p in proposals
        ), "cross-family member_id leaked into proposals"
        # With only this one rule, the rule contributed no proposals.
        assert proposals == []

    def test_inactive_rule_is_skipped(
        self, db: Session, family, adults
    ):
        from app.models.nudge_rules import NudgeRule
        andrew = adults["robert"]
        now = _utcnow().replace(tzinfo=None)
        db.add(PersonalTask(
            family_id=family.id,
            assigned_to=andrew.id,
            title="task A",
            status="pending",
            due_at=now - timedelta(hours=1),
        ))
        db.add(NudgeRule(
            family_id=family.id,
            name="disabled-rule",
            is_active=False,
            source_kind="sql_template",
            template_sql="SELECT 1",
            canonical_sql=(
                "SELECT assigned_to AS member_id, id AS entity_id, "
                "'personal_task' AS entity_kind, due_at AS scheduled_for "
                "FROM personal_tasks WHERE status = 'pending' LIMIT 100"
            ),
            trigger_kind="custom_rule",
            severity="normal",
        ))
        db.commit()

        proposals = nudges_service.scan_rule_triggers(db, now)
        assert proposals == []

    def test_lead_time_shifts_scheduled_for(
        self, db: Session, family, adults
    ):
        from app.models.nudge_rules import NudgeRule
        andrew = adults["robert"]
        now = _utcnow().replace(tzinfo=None)
        # tz-aware insert so the timestamptz round-trip yields the same
        # UTC moment back regardless of the DB session's default TimeZone.
        # We compare after normalizing both sides to naive UTC.
        fixed_due_aware = _utcnow() - timedelta(hours=1)
        fixed_due = fixed_due_aware.astimezone(timezone.utc).replace(tzinfo=None)
        db.add(PersonalTask(
            family_id=family.id,
            assigned_to=andrew.id,
            title="task A",
            status="pending",
            due_at=fixed_due_aware,
        ))
        db.add(NudgeRule(
            family_id=family.id,
            name="leaded-rule",
            is_active=True,
            source_kind="sql_template",
            template_sql="SELECT 1",
            canonical_sql=(
                "SELECT assigned_to AS member_id, id AS entity_id, "
                "'personal_task' AS entity_kind, due_at AS scheduled_for "
                "FROM personal_tasks WHERE status = 'pending' LIMIT 100"
            ),
            trigger_kind="custom_rule",
            default_lead_time_minutes=15,
            severity="normal",
        ))
        db.commit()

        proposals = nudges_service.scan_rule_triggers(db, now)
        assert len(proposals) >= 1
        # scheduled_for should be fixed_due - 15 min
        delta = fixed_due - proposals[0].scheduled_for
        assert delta == timedelta(minutes=15)

    def test_one_bad_rule_does_not_poison_tick(
        self, db: Session, family, adults, monkeypatch
    ):
        """A rule whose canonical SQL raises at execution time is logged
        and skipped. A healthy rule in the same tick still emits."""
        from app.models.nudge_rules import NudgeRule
        andrew = adults["robert"]
        now = _utcnow().replace(tzinfo=None)

        db.add(PersonalTask(
            family_id=family.id,
            assigned_to=andrew.id,
            title="t",
            status="pending",
            due_at=now - timedelta(hours=1),
        ))
        db.add(NudgeRule(
            family_id=family.id,
            name="bad-rule",
            is_active=True,
            source_kind="sql_template",
            template_sql="SELECT 1",
            canonical_sql=(
                # Missing required columns -> RuleExecutionError [schema]
                "SELECT id FROM personal_tasks LIMIT 1"
            ),
            trigger_kind="custom_rule",
            severity="normal",
        ))
        db.add(NudgeRule(
            family_id=family.id,
            name="good-rule",
            is_active=True,
            source_kind="sql_template",
            template_sql="SELECT 1",
            canonical_sql=(
                "SELECT assigned_to AS member_id, id AS entity_id, "
                "'personal_task' AS entity_kind, due_at AS scheduled_for "
                "FROM personal_tasks WHERE status = 'pending' LIMIT 100"
            ),
            trigger_kind="custom_rule",
            severity="normal",
        ))
        db.commit()

        proposals = nudges_service.scan_rule_triggers(db, now)
        # bad-rule contributed zero; good-rule contributed 1+
        assert len(proposals) >= 1
        names_from_context = {p.context.get("title", "") for p in proposals}
        assert any("good-rule" in t for t in names_from_context)

    def test_budget_stops_iteration(
        self, db: Session, family, adults, monkeypatch
    ):
        """If total wall-clock budget is exceeded, subsequent rules are
        skipped. Verify by monkeypatching execute_validated_rule_sql to
        sleep inside, and using budget_seconds=0.05."""
        from app.models.nudge_rules import NudgeRule
        import time as _time

        andrew = adults["robert"]
        now = _utcnow().replace(tzinfo=None)

        for i in range(3):
            db.add(NudgeRule(
                family_id=family.id,
                name=f"slow-rule-{i}",
                is_active=True,
                source_kind="sql_template",
                template_sql="SELECT 1",
                canonical_sql=(
                    "SELECT assigned_to AS member_id, id AS entity_id, "
                    "'personal_task' AS entity_kind, due_at AS scheduled_for "
                    "FROM personal_tasks LIMIT 1"
                ),
                trigger_kind="custom_rule",
                severity="normal",
            ))
        db.commit()

        calls = []
        real_exec = nudges_service.execute_validated_rule_sql

        def slow_exec(db_arg, canonical_sql, params, **kwargs):
            calls.append(canonical_sql)
            _time.sleep(0.1)
            return real_exec(db_arg, canonical_sql, params, **kwargs)

        monkeypatch.setattr(
            nudges_service, "execute_validated_rule_sql", slow_exec
        )

        proposals = nudges_service.scan_rule_triggers(db, now, budget_seconds=0.05)
        # First rule runs (puts us over budget); subsequent two should be
        # skipped. Expect exactly 1 exec call.
        assert len(calls) == 1


class TestRunNudgeScanWithRules:
    def test_rule_triggered_proposal_flows_through_pipeline(
        self, db: Session, family, adults, monkeypatch
    ):
        """Active rule produces a row -> scan_rule_triggers emits a
        NudgeProposal -> apply_proactivity passes it through (balanced)
        -> batch_proposals wraps it -> dispatch_with_items writes a
        NudgeDispatch with trigger_kind='custom_rule' on the child."""
        from app.models.nudge_rules import NudgeRule
        andrew = adults["robert"]
        now = _utcnow().replace(tzinfo=None)

        _force_compose_fallback(monkeypatch)

        db.add(PersonalTask(
            family_id=family.id,
            assigned_to=andrew.id,
            title="rule-matched",
            status="pending",
            due_at=now - timedelta(hours=1),
        ))
        db.add(NudgeRule(
            family_id=family.id,
            name="overdue-wrapper",
            is_active=True,
            source_kind="sql_template",
            template_sql="SELECT 1",
            canonical_sql=(
                "SELECT assigned_to AS member_id, id AS entity_id, "
                "'personal_task' AS entity_kind, due_at AS scheduled_for "
                "FROM personal_tasks WHERE status = 'pending' LIMIT 100"
            ),
            trigger_kind="custom_rule",
            severity="normal",
        ))
        db.commit()

        written = nudges_service.run_nudge_scan(db, now_utc=now)
        assert written >= 1

        child = db.query(NudgeDispatchItem).filter_by(
            trigger_kind="custom_rule"
        ).first()
        assert child is not None
        assert child.family_member_id == andrew.id

    def test_rule_errors_do_not_break_tick(
        self, db: Session, family, adults, monkeypatch
    ):
        """A broken rule raising in scan_rule_triggers is logged + skipped
        (already proven in TestScanRuleTriggers); here we confirm that
        run_nudge_scan still returns based on built-in scanners + healthy
        rules."""
        from app.models.nudge_rules import NudgeRule
        andrew = adults["robert"]
        now = _utcnow().replace(tzinfo=None)

        _force_compose_fallback(monkeypatch)

        db.add(PersonalTask(
            family_id=family.id,
            assigned_to=andrew.id,
            title="built-in-task",
            status="pending",
            due_at=now - timedelta(hours=1),
        ))
        db.add(NudgeRule(
            family_id=family.id,
            name="broken",
            is_active=True,
            source_kind="sql_template",
            template_sql="SELECT 1",
            canonical_sql="SELECT 1",  # missing required columns -> [schema] raise
            trigger_kind="custom_rule",
            severity="normal",
        ))
        db.commit()

        # Should not raise; built-in scanner still produces at least 1
        written = nudges_service.run_nudge_scan(db, now_utc=now)
        assert written >= 1

    def test_budget_caps_rule_scan_time(
        self, db: Session, family, adults, monkeypatch
    ):
        """If rule scanning exceeds budget_seconds, scan_rule_triggers
        stops. run_nudge_scan still completes with built-in-only proposals
        plus whatever rules ran before the budget expired."""
        from app.models.nudge_rules import NudgeRule
        import time as _time

        andrew = adults["robert"]
        now = _utcnow().replace(tzinfo=None)

        _force_compose_fallback(monkeypatch)

        db.add(PersonalTask(
            family_id=family.id,
            assigned_to=andrew.id,
            title="t",
            status="pending",
            due_at=now - timedelta(hours=1),
        ))
        for i in range(3):
            db.add(NudgeRule(
                family_id=family.id,
                name=f"slow-{i}",
                is_active=True,
                source_kind="sql_template",
                template_sql="SELECT 1",
                canonical_sql=(
                    "SELECT assigned_to AS member_id, id AS entity_id, "
                    "'personal_task' AS entity_kind, due_at AS scheduled_for "
                    "FROM personal_tasks LIMIT 1"
                ),
                trigger_kind="custom_rule",
                severity="normal",
            ))
        db.commit()

        exec_calls = []
        real_exec = nudges_service.execute_validated_rule_sql

        def slow_exec(db_arg, canonical_sql, params, **kwargs):
            exec_calls.append(1)
            _time.sleep(0.1)
            return real_exec(db_arg, canonical_sql, params, **kwargs)

        monkeypatch.setattr(
            nudges_service, "execute_validated_rule_sql", slow_exec
        )

        written = nudges_service.run_nudge_scan(
            db, now_utc=now, rule_scan_budget_seconds=0.05
        )
        # Built-in produced 1; rule scan capped -> at most 1 rule exec
        assert written >= 1
        assert len(exec_calls) <= 1


class TestAdminNudgeRulesRoutes:
    _BASIC_SQL = (
        "SELECT assigned_to AS member_id, id AS entity_id, "
        "'personal_task' AS entity_kind, due_at AS scheduled_for "
        "FROM personal_tasks WHERE status = 'pending' LIMIT 100"
    )

    def test_list_empty_when_no_rules(self, db, family, adults, client):
        andrew = adults["robert"]
        token = _make_account_and_token(db, andrew.id, "andrew-rules@test.app")
        r = client.get(
            "/api/admin/nudges/rules",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        assert r.json() == []

    def test_post_creates_rule_with_canonical_sql(
        self, db, family, adults, client
    ):
        andrew = adults["robert"]
        token = _make_account_and_token(db, andrew.id, "andrew-rules@test.app")
        r = client.post(
            "/api/admin/nudges/rules",
            json={
                "name": "overdue rule",
                "template_sql": self._BASIC_SQL,
                "severity": "normal",
                "default_lead_time_minutes": 5,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["name"] == "overdue rule"
        assert body["canonical_sql"] is not None
        assert body["canonical_sql"].lower().startswith("select")
        assert body["trigger_kind"] == "custom_rule"

    def test_post_rejects_bad_sql_with_422(
        self, db, family, adults, client
    ):
        andrew = adults["robert"]
        token = _make_account_and_token(db, andrew.id, "andrew-rules@test.app")
        r = client.post(
            "/api/admin/nudges/rules",
            json={
                "name": "bad",
                "template_sql": "DROP TABLE personal_tasks",
                "severity": "normal",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 422
        assert "[" in r.json()["detail"]  # tagged error

    def test_patch_revalidates_on_sql_change(
        self, db, family, adults, client
    ):
        from app.models.nudge_rules import NudgeRule
        from app.services.nudge_rule_validator import validate_rule_sql

        andrew = adults["robert"]
        token = _make_account_and_token(db, andrew.id, "andrew-rules@test.app")
        canonical = validate_rule_sql(self._BASIC_SQL).canonical_sql
        rule = NudgeRule(
            family_id=family.id,
            name="r",
            source_kind="sql_template",
            template_sql=self._BASIC_SQL,
            canonical_sql=canonical,
            severity="normal",
        )
        db.add(rule)
        db.commit()

        r = client.patch(
            f"/api/admin/nudges/rules/{rule.id}",
            json={"template_sql": "SELECT COUNT(*) FROM personal_tasks"},
            headers={"Authorization": f"Bearer {token}"},
        )
        # COUNT is allowed but schema check on the rule executor won't
        # run at PATCH time; only at scan/preview time. PATCH should
        # succeed here since validate_rule_sql passes SELECT COUNT(*).
        assert r.status_code == 200
        assert r.json()["canonical_sql"].lower().startswith("select")

    def test_patch_rejects_invalid_sql_and_keeps_old_canonical(
        self, db, family, adults, client
    ):
        from app.models.nudge_rules import NudgeRule
        from app.services.nudge_rule_validator import validate_rule_sql

        andrew = adults["robert"]
        token = _make_account_and_token(db, andrew.id, "andrew-rules@test.app")
        original = validate_rule_sql(self._BASIC_SQL).canonical_sql
        rule = NudgeRule(
            family_id=family.id,
            name="r",
            source_kind="sql_template",
            template_sql=self._BASIC_SQL,
            canonical_sql=original,
            severity="normal",
        )
        db.add(rule)
        db.commit()

        r = client.patch(
            f"/api/admin/nudges/rules/{rule.id}",
            json={"template_sql": "DELETE FROM personal_tasks"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 422
        db.refresh(rule)
        assert rule.canonical_sql == original  # unchanged

    def test_delete_removes_rule(self, db, family, adults, client):
        from app.models.nudge_rules import NudgeRule
        from app.services.nudge_rule_validator import validate_rule_sql

        andrew = adults["robert"]
        token = _make_account_and_token(db, andrew.id, "andrew-rules@test.app")
        rule = NudgeRule(
            family_id=family.id,
            name="r",
            source_kind="sql_template",
            template_sql=self._BASIC_SQL,
            canonical_sql=validate_rule_sql(self._BASIC_SQL).canonical_sql,
            severity="normal",
        )
        db.add(rule)
        db.commit()

        r = client.delete(
            f"/api/admin/nudges/rules/{rule.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 204
        assert db.get(NudgeRule, rule.id) is None

    def test_preview_count_returns_count(
        self, db, family, adults, client
    ):
        from app.models.nudge_rules import NudgeRule
        from app.services.nudge_rule_validator import validate_rule_sql

        andrew = adults["robert"]
        now = _utcnow().replace(tzinfo=None)
        for i in range(3):
            db.add(PersonalTask(
                family_id=family.id,
                assigned_to=andrew.id,
                title=f"T{i}",
                status="pending",
                due_at=now - timedelta(hours=1),
            ))
        rule = NudgeRule(
            family_id=family.id,
            name="r",
            source_kind="sql_template",
            template_sql=self._BASIC_SQL,
            canonical_sql=validate_rule_sql(self._BASIC_SQL).canonical_sql,
            severity="normal",
        )
        db.add(rule)
        db.commit()

        token = _make_account_and_token(db, andrew.id, "andrew-rules@test.app")
        r = client.post(
            f"/api/admin/nudges/rules/{rule.id}/preview-count",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["count"] >= 3
        assert body["capped"] is False
        assert body["error"] is None

    def test_preview_count_does_not_leak_cross_family_rows(
        self, db, family, adults, client
    ):
        """Regression: /preview-count must apply the same family-scope
        filter as scan_rule_triggers so a rule authored in Family A
        cannot enumerate rows belonging to Family B.
        """
        from app.models.foundation import Family, FamilyMember
        from app.models.nudge_rules import NudgeRule

        andrew = adults["robert"]

        # Seed Family B with one member whose id the attacker-rule
        # explicitly names. Family A is the `family` fixture.
        other_family = Family(name="Other", timezone="UTC")
        db.add(other_family)
        db.flush()
        other_member = FamilyMember(
            family_id=other_family.id,
            first_name="Outsider",
            last_name="X",
            role="adult",
            birthdate=date(1990, 1, 1),
        )
        db.add(other_member)
        db.flush()

        # Rule belongs to Family A but its canonical SQL names the
        # Family B member's id. The validator would accept the raw form
        # (family_members is on the allowlist); we store the canonical
        # hand-rolled here because the test targets the route's filter,
        # not the validator.
        canonical = (
            "SELECT id AS member_id, id AS entity_id, "
            "'personal_task' AS entity_kind, now() AS scheduled_for "
            f"FROM family_members WHERE id = '{other_member.id}'"
        )
        rule = NudgeRule(
            family_id=family.id,
            name="cross-family-preview",
            source_kind="sql_template",
            template_sql="SELECT 1",
            canonical_sql=canonical,
            severity="normal",
        )
        db.add(rule)
        db.commit()

        token = _make_account_and_token(
            db, andrew.id, "andrew-cross-family@test.app"
        )
        r = client.post(
            f"/api/admin/nudges/rules/{rule.id}/preview-count",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        body = r.json()
        # The raw SQL would return 1 row (the Family B member). The
        # filter drops it so the response count is 0 and no cross-
        # tenant size is disclosed.
        assert body["count"] == 0, (
            f"preview-count leaked cross-family row count: {body}"
        )
        assert body["error"] is None

    def test_non_admin_cannot_access_routes(
        self, db, family, adults, children, client
    ):
        """Child-role members lack nudges.configure -> 403."""
        sadie = children["sadie"]
        token = _make_account_and_token(db, sadie.id, "sadie-rules@test.app")

        for path in [
            ("GET", "/api/admin/nudges/rules", None),
            ("POST", "/api/admin/nudges/rules",
             {"name": "x", "template_sql": "SELECT 1 AS member_id, 1 AS entity_id, 'x' AS entity_kind, now() AS scheduled_for LIMIT 1", "severity": "normal"}),
        ]:
            method, url, body = path
            if method == "GET":
                r = client.get(url, headers={"Authorization": f"Bearer {token}"})
            else:
                r = client.post(url, json=body, headers={"Authorization": f"Bearer {token}"})
            assert r.status_code == 403

    def test_cross_family_rule_returns_404(
        self, db, family, adults, client
    ):
        """A rule from another family must return 404 for this actor."""
        from app.models.nudge_rules import NudgeRule
        from app.models.foundation import Family
        from app.services.nudge_rule_validator import validate_rule_sql

        # Separate family with one rule
        other = Family(name="Other", timezone="UTC")
        db.add(other)
        db.flush()
        rule = NudgeRule(
            family_id=other.id,
            name="r",
            source_kind="sql_template",
            template_sql=self._BASIC_SQL,
            canonical_sql=validate_rule_sql(self._BASIC_SQL).canonical_sql,
            severity="normal",
        )
        db.add(rule)
        db.commit()

        andrew = adults["robert"]
        token = _make_account_and_token(db, andrew.id, "andrew-rules@test.app")

        r = client.patch(
            f"/api/admin/nudges/rules/{rule.id}",
            json={"name": "hijacked"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 404

        r = client.delete(
            f"/api/admin/nudges/rules/{rule.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 404

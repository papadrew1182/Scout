"""Sprint 05 Phase 1 - nudges engine tests."""

from __future__ import annotations

import json
from datetime import datetime, time, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from app.models.action_items import ParentActionItem
from app.models.calendar import Event, EventAttendee
from app.models.life_management import ChoreTemplate, Routine, TaskInstance
from app.models.nudges import NudgeDispatch, NudgeDispatchItem
from app.models.personal_tasks import PersonalTask
from app.models.push import PushDelivery, PushDevice
from app.models.quiet_hours import QuietHoursFamily
from app.services import ai_personality_service, nudges_service


def _utcnow() -> datetime:
    # tz-aware; compare-safe against Postgres-hydrated timestamptz values
    return datetime.now(timezone.utc)


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

    def test_null_trigger_entity_id_uses_null_literal_in_key(
        self, db: Session, family, adults
    ):
        """AI-suggested proposals may have no entity id. The key uses
        the string 'null' in that slot so it still stays stable
        across ticks."""
        andrew = adults["robert"]
        family.timezone = "UTC"
        db.commit()

        prop = nudges_service.NudgeProposal(
            family_member_id=andrew.id,
            trigger_kind="ai_suggested",
            trigger_entity_kind="family",
            trigger_entity_id=None,
            scheduled_for=datetime(2026, 4, 21, 12, 0),
            severity="normal",
            context={"occurrence_at_utc": datetime(2026, 4, 21, 12, 0)},
        )

        fields = nudges_service.resolve_occurrence_fields(db, prop)
        assert fields.source_dedupe_key == f"{andrew.id}:ai_suggested:null:2026-04-21"

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


class TestScannerStampsOccurrence:
    """Confirm each scanner stamps context['occurrence_at_utc']."""

    def test_overdue_task_scanner_stamps_due_at(
        self, db: Session, family, adults
    ):
        andrew = adults["robert"]
        now = _utcnow()
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
        # Ignore microseconds / tz parity; the underlying due_at round-trips
        assert proposals[0].context["occurrence_at_utc"].date() == due.date()

    def test_upcoming_event_scanner_stamps_starts_at(
        self, db: Session, family, adults
    ):
        andrew = adults["robert"]
        now = _utcnow()
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

    def test_missed_routine_scanner_stamps_due_at(
        self, db: Session, family, adults, children
    ):
        sadie = children["sadie"]
        parent = adults["robert"]
        now = _utcnow()
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
                due_at=now - timedelta(minutes=20),
                is_completed=False,
            )
        )
        db.commit()

        proposals = nudges_service.scan_missed_routines(db, now)
        assert len(proposals) == 1
        assert "occurrence_at_utc" in proposals[0].context


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

        # No push device => no push; test the Inbox path clean
        written = nudges_service.dispatch_with_items(db, [prop], now.replace(tzinfo=None))

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
        # action_type falls back to 'general' until chk_parent_action_items_action_type
        # is widened (migration pending). entity_type carries the trigger kind.
        assert inbox.action_type == "general"
        assert inbox.entity_type == "personal_task"
        assert "Take out bins" in inbox.title or "Take out bins" in (inbox.detail or "")

    def test_dedupe_on_repeat(self, db: Session, family, adults):
        andrew = adults["robert"]
        now = _utcnow()
        occurrence = now.replace(tzinfo=None) - timedelta(hours=1)
        entity_id = __import__("uuid").uuid4()
        prop = self._base_proposal(andrew.id, occurrence, entity_id=entity_id)

        first = nudges_service.dispatch_with_items(db, [prop], now.replace(tzinfo=None))
        second = nudges_service.dispatch_with_items(db, [prop], now.replace(tzinfo=None))

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
        nudges_service.dispatch_with_items(db, [prop], now)

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
        nudges_service.dispatch_with_items(db, [prop], now)

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
        written = nudges_service.dispatch_with_items(db, [prop], now)

        assert written == 1
        parent = db.query(NudgeDispatch).filter_by(family_member_id=andrew.id).one()
        assert "inbox" in parent.delivered_channels
        assert "push" not in parent.delivered_channels
        assert parent.push_delivery_id is None

    def test_one_proposal_dedupe_does_not_undo_siblings(
        self, db: Session, family, adults
    ):
        """Two proposals in one call. First succeeds, second has a
        pre-existing dedupe row (simulated by dispatching it first).
        Per-proposal SAVEPOINT ensures the first stays committed."""
        andrew = adults["robert"]
        now = _utcnow().replace(tzinfo=None)
        e1 = __import__("uuid").uuid4()
        e2 = __import__("uuid").uuid4()
        occurrence = now - timedelta(hours=1)

        prop_first = self._base_proposal(andrew.id, occurrence, entity_id=e1)
        prop_second = self._base_proposal(andrew.id, occurrence, entity_id=e2)

        # Pre-seed dedupe for prop_second
        nudges_service.dispatch_with_items(db, [prop_second], now)
        assert db.query(NudgeDispatchItem).count() == 1

        written = nudges_service.dispatch_with_items(
            db, [prop_first, prop_second], now
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

        # Everyone defaults to balanced proactivity, so 70 proposals should dispatch
        assert written >= 50, f"expected >=50 dispatches, got {written}"
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

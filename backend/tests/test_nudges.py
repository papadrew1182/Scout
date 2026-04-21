"""Sprint 05 Phase 1 - nudges engine tests."""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from app.models.calendar import Event, EventAttendee
from app.models.life_management import ChoreTemplate, Routine, TaskInstance
from app.models.personal_tasks import PersonalTask
from app.services import nudges_service


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

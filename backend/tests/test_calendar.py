"""Tests for calendar_service.

Covers:
- create one-off event
- list events in date range
- create recurring series + edited instance override
- attendee CRUD
- tenant isolation
- ends_at validation
"""

import uuid
from datetime import date, datetime, timedelta

import pytest
import pytz
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.calendar import Event
from app.models.foundation import Family, FamilyMember
from app.schemas.calendar import (
    EventAttendeeCreate,
    EventAttendeeUpdate,
    EventCreate,
    EventInstanceCreate,
    EventUpdate,
)
from app.services.calendar_service import (
    add_attendee,
    create_event,
    create_recurrence_instance,
    delete_event,
    get_event,
    list_attendees,
    list_events,
    remove_attendee,
    update_attendee_response,
    update_event,
)


def _dt(y, m, d, h=12, minute=0):
    return pytz.timezone("America/Chicago").localize(datetime(y, m, d, h, minute))


class TestEventCreate:
    def test_create_one_off_event(self, db: Session, family, adults):
        andrew = adults["robert"]  # foundation conftest uses "robert" key
        payload = EventCreate(
            created_by=andrew.id,
            title="Family Dinner",
            starts_at=_dt(2026, 4, 10, 18),
            ends_at=_dt(2026, 4, 10, 20),
        )
        event = create_event(db, family.id, payload)
        assert event.id is not None
        assert event.title == "Family Dinner"
        assert event.recurrence_rule is None
        assert event.recurrence_parent_id is None

    def test_create_recurring_event(self, db: Session, family, adults):
        andrew = adults["robert"]
        payload = EventCreate(
            created_by=andrew.id,
            title="Soccer Practice",
            starts_at=_dt(2026, 4, 7, 17),
            ends_at=_dt(2026, 4, 7, 18, 30),
            recurrence_rule="FREQ=WEEKLY;BYDAY=TU,TH",
        )
        event = create_event(db, family.id, payload)
        assert event.recurrence_rule == "FREQ=WEEKLY;BYDAY=TU,TH"

    def test_ends_before_starts_rejected(self, db: Session, family, adults):
        payload = EventCreate(
            title="Bad",
            starts_at=_dt(2026, 4, 10, 20),
            ends_at=_dt(2026, 4, 10, 18),
        )
        with pytest.raises(HTTPException) as exc:
            create_event(db, family.id, payload)
        assert exc.value.status_code == 400


class TestEventList:
    def test_list_filters_by_date_range(self, db: Session, family, adults):
        andrew = adults["robert"]
        for day in [5, 10, 15]:
            create_event(
                db,
                family.id,
                EventCreate(
                    created_by=andrew.id,
                    title=f"Event {day}",
                    starts_at=_dt(2026, 4, day, 12),
                    ends_at=_dt(2026, 4, day, 13),
                ),
            )

        results = list_events(
            db, family.id, start=_dt(2026, 4, 8, 0), end=_dt(2026, 4, 12, 23)
        )
        titles = {e.title for e in results}
        assert "Event 10" in titles
        assert "Event 5" not in titles
        assert "Event 15" not in titles

    def test_list_hearth_visible_only(self, db: Session, family, adults):
        andrew = adults["robert"]
        create_event(
            db,
            family.id,
            EventCreate(
                created_by=andrew.id,
                title="Public",
                starts_at=_dt(2026, 4, 10, 12),
                ends_at=_dt(2026, 4, 10, 13),
                is_hearth_visible=True,
            ),
        )
        create_event(
            db,
            family.id,
            EventCreate(
                created_by=andrew.id,
                title="Private",
                starts_at=_dt(2026, 4, 10, 14),
                ends_at=_dt(2026, 4, 10, 15),
                is_hearth_visible=False,
            ),
        )

        all_events = list_events(db, family.id)
        visible_only = list_events(db, family.id, hearth_visible_only=True)
        assert len(all_events) == 2
        assert len(visible_only) == 1
        assert visible_only[0].title == "Public"


class TestRecurrenceInstance:
    def test_create_edited_instance(self, db: Session, family, adults):
        andrew = adults["robert"]
        parent = create_event(
            db,
            family.id,
            EventCreate(
                created_by=andrew.id,
                title="Soccer",
                starts_at=_dt(2026, 4, 7, 17),
                ends_at=_dt(2026, 4, 7, 18, 30),
                recurrence_rule="FREQ=WEEKLY;BYDAY=TU,TH",
            ),
        )

        instance = create_recurrence_instance(
            db,
            family.id,
            parent.id,
            EventInstanceCreate(
                recurrence_instance_date=date(2026, 4, 14),
                title="Soccer — CANCELLED",
                starts_at=_dt(2026, 4, 14, 17),
                ends_at=_dt(2026, 4, 14, 18, 30),
                is_cancelled=True,
            ),
        )
        assert instance.recurrence_parent_id == parent.id
        assert instance.recurrence_instance_date == date(2026, 4, 14)
        assert instance.is_cancelled is True
        assert instance.recurrence_rule is None

    def test_instance_on_non_recurring_parent_rejected(self, db: Session, family, adults):
        andrew = adults["robert"]
        parent = create_event(
            db,
            family.id,
            EventCreate(
                created_by=andrew.id,
                title="One-off",
                starts_at=_dt(2026, 4, 10, 12),
                ends_at=_dt(2026, 4, 10, 13),
            ),
        )
        with pytest.raises(HTTPException) as exc:
            create_recurrence_instance(
                db,
                family.id,
                parent.id,
                EventInstanceCreate(
                    recurrence_instance_date=date(2026, 4, 10),
                    title="Override",
                    starts_at=_dt(2026, 4, 10, 12),
                    ends_at=_dt(2026, 4, 10, 13),
                ),
            )
        assert exc.value.status_code == 400


class TestEventUpdateDelete:
    def test_update_event(self, db: Session, family, adults):
        event = create_event(
            db,
            family.id,
            EventCreate(
                title="Original",
                starts_at=_dt(2026, 4, 10, 12),
                ends_at=_dt(2026, 4, 10, 13),
            ),
        )
        updated = update_event(
            db, family.id, event.id, EventUpdate(title="Renamed")
        )
        assert updated.title == "Renamed"

    def test_delete_event(self, db: Session, family, adults):
        event = create_event(
            db,
            family.id,
            EventCreate(
                title="To Delete",
                starts_at=_dt(2026, 4, 10, 12),
                ends_at=_dt(2026, 4, 10, 13),
            ),
        )
        delete_event(db, family.id, event.id)
        with pytest.raises(HTTPException) as exc:
            get_event(db, family.id, event.id)
        assert exc.value.status_code == 404


class TestAttendees:
    def test_add_and_list_attendees(self, db: Session, family, adults, children):
        event = create_event(
            db,
            family.id,
            EventCreate(
                title="Soccer",
                starts_at=_dt(2026, 4, 10, 17),
                ends_at=_dt(2026, 4, 10, 18),
            ),
        )
        sadie = children["sadie"]
        add_attendee(
            db, family.id, event.id,
            EventAttendeeCreate(family_member_id=sadie.id, response_status="accepted"),
        )
        attendees = list_attendees(db, family.id, event.id)
        assert len(attendees) == 1
        assert attendees[0].family_member_id == sadie.id
        assert attendees[0].response_status == "accepted"

    def test_update_attendee_response(self, db: Session, family, children):
        event = create_event(
            db,
            family.id,
            EventCreate(
                title="Soccer",
                starts_at=_dt(2026, 4, 10, 17),
                ends_at=_dt(2026, 4, 10, 18),
            ),
        )
        sadie = children["sadie"]
        attendee = add_attendee(
            db, family.id, event.id,
            EventAttendeeCreate(family_member_id=sadie.id),
        )
        updated = update_attendee_response(
            db, family.id, event.id, attendee.id,
            EventAttendeeUpdate(response_status="declined"),
        )
        assert updated.response_status == "declined"

    def test_remove_attendee(self, db: Session, family, children):
        event = create_event(
            db,
            family.id,
            EventCreate(
                title="Soccer",
                starts_at=_dt(2026, 4, 10, 17),
                ends_at=_dt(2026, 4, 10, 18),
            ),
        )
        sadie = children["sadie"]
        attendee = add_attendee(
            db, family.id, event.id,
            EventAttendeeCreate(family_member_id=sadie.id),
        )
        remove_attendee(db, family.id, event.id, attendee.id)
        attendees = list_attendees(db, family.id, event.id)
        assert len(attendees) == 0


class TestTenantIsolation:
    def test_get_event_from_wrong_family_404(self, db: Session, family):
        other_family = Family(name="Other", timezone="America/New_York")
        db.add(other_family)
        db.flush()

        other_event = Event(
            family_id=other_family.id,
            title="Outside",
            starts_at=_dt(2026, 4, 10, 12),
            ends_at=_dt(2026, 4, 10, 13),
        )
        db.add(other_event)
        db.flush()

        with pytest.raises(HTTPException) as exc:
            get_event(db, family.id, other_event.id)
        assert exc.value.status_code == 404

    def test_list_events_only_returns_own_family(self, db: Session, family):
        other_family = Family(name="Other", timezone="America/New_York")
        db.add(other_family)
        db.flush()

        create_event(
            db, family.id,
            EventCreate(title="Mine", starts_at=_dt(2026, 4, 10, 12), ends_at=_dt(2026, 4, 10, 13)),
        )
        other_event = Event(
            family_id=other_family.id,
            title="Theirs",
            starts_at=_dt(2026, 4, 10, 12),
            ends_at=_dt(2026, 4, 10, 13),
        )
        db.add(other_event)
        db.flush()

        results = list_events(db, family.id)
        titles = {e.title for e in results}
        assert "Mine" in titles
        assert "Theirs" not in titles

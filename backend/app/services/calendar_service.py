"""Calendar service: events and event_attendees CRUD.

Recurrence expansion is intentionally NOT performed here. List queries return
the raw event rows: series roots, edited instances, and one-off events.
Application or UI layer is responsible for expanding RRULE strings into
visible occurrences and applying edited-instance overrides.
"""

import uuid
from datetime import date, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.calendar import Event, EventAttendee
from app.schemas.calendar import (
    EventAttendeeCreate,
    EventAttendeeUpdate,
    EventCreate,
    EventInstanceCreate,
    EventUpdate,
)
from app.services.tenant_guard import require_family, require_member_in_family


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

def list_events(
    db: Session,
    family_id: uuid.UUID,
    start: datetime | None = None,
    end: datetime | None = None,
    hearth_visible_only: bool = False,
) -> list[Event]:
    require_family(db, family_id)
    stmt = select(Event).where(Event.family_id == family_id)
    if start:
        stmt = stmt.where(Event.ends_at >= start)
    if end:
        stmt = stmt.where(Event.starts_at <= end)
    if hearth_visible_only:
        stmt = stmt.where(Event.is_hearth_visible.is_(True))
    stmt = stmt.order_by(Event.starts_at)
    return list(db.scalars(stmt).all())


def get_event(db: Session, family_id: uuid.UUID, event_id: uuid.UUID) -> Event:
    event = db.get(Event, event_id)
    if not event or event.family_id != family_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return event


def create_event_nocommit(db: Session, family_id: uuid.UUID, payload: EventCreate) -> Event:
    """Validate + insert an event WITHOUT committing. See
    ``personal_tasks_service.create_personal_task_nocommit`` for
    context — used by the planner bundle apply path."""
    require_family(db, family_id)
    if payload.created_by:
        require_member_in_family(db, family_id, payload.created_by)
    if payload.ends_at < payload.starts_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ends_at must be >= starts_at",
        )

    event = Event(
        family_id=family_id,
        created_by=payload.created_by,
        title=payload.title,
        description=payload.description,
        location=payload.location,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        all_day=payload.all_day,
        recurrence_rule=payload.recurrence_rule,
        source=payload.source,
        is_hearth_visible=payload.is_hearth_visible,
        task_instance_id=payload.task_instance_id,
    )
    db.add(event)
    db.flush()
    return event


def create_event(db: Session, family_id: uuid.UUID, payload: EventCreate) -> Event:
    event = create_event_nocommit(db, family_id, payload)
    db.commit()
    db.refresh(event)
    return event


def update_event(
    db: Session,
    family_id: uuid.UUID,
    event_id: uuid.UUID,
    payload: EventUpdate,
) -> Event:
    event = get_event(db, family_id, event_id)

    data = payload.model_dump(exclude_unset=True)
    new_starts = data.get("starts_at", event.starts_at)
    new_ends = data.get("ends_at", event.ends_at)
    if new_ends < new_starts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ends_at must be >= starts_at",
        )

    for key, value in data.items():
        setattr(event, key, value)
    db.commit()
    db.refresh(event)
    return event


def delete_event(db: Session, family_id: uuid.UUID, event_id: uuid.UUID) -> None:
    event = get_event(db, family_id, event_id)
    db.delete(event)
    db.commit()


def create_recurrence_instance(
    db: Session,
    family_id: uuid.UUID,
    parent_event_id: uuid.UUID,
    payload: EventInstanceCreate,
) -> Event:
    """Create an edited single occurrence of a recurring series."""
    parent = get_event(db, family_id, parent_event_id)
    if parent.recurrence_rule is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Parent event has no recurrence_rule; cannot create an instance override",
        )
    if parent.recurrence_parent_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Parent event must be a series root, not itself an edited instance",
        )
    if payload.ends_at < payload.starts_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ends_at must be >= starts_at",
        )

    instance = Event(
        family_id=family_id,
        created_by=parent.created_by,
        title=payload.title,
        description=payload.description,
        location=payload.location,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        all_day=payload.all_day,
        recurrence_rule=None,
        recurrence_parent_id=parent.id,
        recurrence_instance_date=payload.recurrence_instance_date,
        source=parent.source,
        is_hearth_visible=parent.is_hearth_visible,
        task_instance_id=None,
        is_cancelled=payload.is_cancelled,
    )
    db.add(instance)
    db.commit()
    db.refresh(instance)
    return instance


# ---------------------------------------------------------------------------
# Event Attendees
# ---------------------------------------------------------------------------

def list_attendees(
    db: Session, family_id: uuid.UUID, event_id: uuid.UUID
) -> list[EventAttendee]:
    event = get_event(db, family_id, event_id)
    stmt = select(EventAttendee).where(EventAttendee.event_id == event.id)
    return list(db.scalars(stmt).all())


def add_attendee(
    db: Session,
    family_id: uuid.UUID,
    event_id: uuid.UUID,
    payload: EventAttendeeCreate,
) -> EventAttendee:
    event = get_event(db, family_id, event_id)
    require_member_in_family(db, family_id, payload.family_member_id)

    attendee = EventAttendee(
        event_id=event.id,
        family_member_id=payload.family_member_id,
        response_status=payload.response_status,
    )
    db.add(attendee)
    db.commit()
    db.refresh(attendee)
    return attendee


def update_attendee_response(
    db: Session,
    family_id: uuid.UUID,
    event_id: uuid.UUID,
    attendee_id: uuid.UUID,
    payload: EventAttendeeUpdate,
) -> EventAttendee:
    get_event(db, family_id, event_id)
    attendee = db.get(EventAttendee, attendee_id)
    if not attendee or attendee.event_id != event_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attendee not found")
    attendee.response_status = payload.response_status
    db.commit()
    db.refresh(attendee)
    return attendee


def remove_attendee(
    db: Session,
    family_id: uuid.UUID,
    event_id: uuid.UUID,
    attendee_id: uuid.UUID,
) -> None:
    get_event(db, family_id, event_id)
    attendee = db.get(EventAttendee, attendee_id)
    if not attendee or attendee.event_id != event_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attendee not found")
    db.delete(attendee)
    db.commit()

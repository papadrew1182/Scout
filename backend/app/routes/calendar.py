import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.calendar import (
    EventAttendeeCreate,
    EventAttendeeRead,
    EventAttendeeUpdate,
    EventCreate,
    EventInstanceCreate,
    EventRead,
    EventUpdate,
)
from app.services import calendar_service

router = APIRouter(prefix="/families/{family_id}/events", tags=["calendar"])


# --- Events ---

@router.get("", response_model=list[EventRead])
def list_events(
    family_id: uuid.UUID,
    start: datetime | None = Query(None),
    end: datetime | None = Query(None),
    hearth_visible_only: bool = Query(False),
    db: Session = Depends(get_db),
):
    return calendar_service.list_events(db, family_id, start, end, hearth_visible_only)


@router.post("", response_model=EventRead, status_code=201)
def create_event(family_id: uuid.UUID, payload: EventCreate, db: Session = Depends(get_db)):
    return calendar_service.create_event(db, family_id, payload)


@router.get("/{event_id}", response_model=EventRead)
def get_event(family_id: uuid.UUID, event_id: uuid.UUID, db: Session = Depends(get_db)):
    return calendar_service.get_event(db, family_id, event_id)


@router.patch("/{event_id}", response_model=EventRead)
def update_event(
    family_id: uuid.UUID,
    event_id: uuid.UUID,
    payload: EventUpdate,
    db: Session = Depends(get_db),
):
    return calendar_service.update_event(db, family_id, event_id, payload)


@router.delete("/{event_id}", status_code=204)
def delete_event(family_id: uuid.UUID, event_id: uuid.UUID, db: Session = Depends(get_db)):
    calendar_service.delete_event(db, family_id, event_id)


@router.post("/{event_id}/instances", response_model=EventRead, status_code=201)
def create_recurrence_instance(
    family_id: uuid.UUID,
    event_id: uuid.UUID,
    payload: EventInstanceCreate,
    db: Session = Depends(get_db),
):
    return calendar_service.create_recurrence_instance(db, family_id, event_id, payload)


# --- Attendees ---

@router.get("/{event_id}/attendees", response_model=list[EventAttendeeRead])
def list_attendees(family_id: uuid.UUID, event_id: uuid.UUID, db: Session = Depends(get_db)):
    return calendar_service.list_attendees(db, family_id, event_id)


@router.post("/{event_id}/attendees", response_model=EventAttendeeRead, status_code=201)
def add_attendee(
    family_id: uuid.UUID,
    event_id: uuid.UUID,
    payload: EventAttendeeCreate,
    db: Session = Depends(get_db),
):
    return calendar_service.add_attendee(db, family_id, event_id, payload)


@router.patch("/{event_id}/attendees/{attendee_id}", response_model=EventAttendeeRead)
def update_attendee(
    family_id: uuid.UUID,
    event_id: uuid.UUID,
    attendee_id: uuid.UUID,
    payload: EventAttendeeUpdate,
    db: Session = Depends(get_db),
):
    return calendar_service.update_attendee_response(db, family_id, event_id, attendee_id, payload)


@router.delete("/{event_id}/attendees/{attendee_id}", status_code=204)
def remove_attendee(
    family_id: uuid.UUID,
    event_id: uuid.UUID,
    attendee_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    calendar_service.remove_attendee(db, family_id, event_id, attendee_id)

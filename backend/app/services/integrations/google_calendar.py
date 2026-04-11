"""Google Calendar ingestion v1.

Accepts a mocked Google Calendar event payload and upserts it into the
events table via connector_mappings.

No real Google API calls. No OAuth. No webhook receiver. No sync scheduling.
This is a synchronous payload-handler only.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.calendar import Event
from app.services.integrations.base import upsert_via_mapping
from app.services.tenant_guard import require_family

CONNECTOR_NAME = "google_calendar"
INTERNAL_TABLE = "events"
EVENT_SOURCE = "google_cal"


class GoogleCalendarEventPayload(BaseModel):
    """Mocked subset of a Google Calendar event payload."""
    external_id: str
    title: str
    description: str | None = None
    location: str | None = None
    starts_at: datetime
    ends_at: datetime
    all_day: bool = False
    is_cancelled: bool = False


def ingest_event(
    db: Session,
    family_id: uuid.UUID,
    payload: GoogleCalendarEventPayload,
) -> tuple[Event, bool]:
    """Ingest a single Google Calendar event payload.

    Returns (event, created) where created is True if a new event was made.
    """
    require_family(db, family_id)

    def fetch_by_id(internal_id: uuid.UUID) -> Event | None:
        row = db.get(Event, internal_id)
        if row and row.family_id == family_id:
            return row
        return None

    def create_fn() -> Event:
        event = Event(
            family_id=family_id,
            created_by=None,
            title=payload.title,
            description=payload.description,
            location=payload.location,
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
            all_day=payload.all_day,
            is_cancelled=payload.is_cancelled,
            source=EVENT_SOURCE,
        )
        db.add(event)
        db.flush()
        return event

    def update_fn(event: Event) -> None:
        event.title = payload.title
        event.description = payload.description
        event.location = payload.location
        event.starts_at = payload.starts_at
        event.ends_at = payload.ends_at
        event.all_day = payload.all_day
        event.is_cancelled = payload.is_cancelled

    event, created = upsert_via_mapping(
        db,
        connector_name=CONNECTOR_NAME,
        internal_table=INTERNAL_TABLE,
        external_id=payload.external_id,
        expected_source=EVENT_SOURCE,
        fetch_by_id=fetch_by_id,
        create_fn=create_fn,
        update_fn=update_fn,
        metadata={"resource_type": "event"},
    )
    db.commit()
    db.refresh(event)
    return event, created


def ingest_events_batch(
    db: Session,
    family_id: uuid.UUID,
    payloads: list[GoogleCalendarEventPayload],
) -> list[tuple[Event, bool]]:
    """Ingest multiple events. Each is processed independently."""
    results = []
    for payload in payloads:
        results.append(ingest_event(db, family_id, payload))
    return results

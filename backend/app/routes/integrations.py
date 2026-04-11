"""Integrations ingestion routes.

These are internal/testing endpoints. They accept payloads that mock the
shape of external system records and run them through the synchronous
ingestion services. There is no auth, no scheduling, no webhook receiving.
"""

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.calendar import EventRead
from app.schemas.finance import BillRead
from app.services.integrations.google_calendar import (
    GoogleCalendarEventPayload,
    ingest_event,
)
from app.services.integrations.ynab import (
    YnabScheduledTransactionPayload,
    ingest_scheduled_transaction,
)

router = APIRouter(prefix="/integrations", tags=["integrations"])


class GoogleCalendarIngestRequest(BaseModel):
    family_id: uuid.UUID
    payload: GoogleCalendarEventPayload


class GoogleCalendarIngestResponse(BaseModel):
    event: EventRead
    created: bool


class YnabIngestRequest(BaseModel):
    family_id: uuid.UUID
    payload: YnabScheduledTransactionPayload


class YnabIngestResponse(BaseModel):
    bill: BillRead
    created: bool


@router.post("/google-calendar/ingest", response_model=GoogleCalendarIngestResponse)
def google_calendar_ingest(
    body: GoogleCalendarIngestRequest,
    db: Session = Depends(get_db),
):
    event, created = ingest_event(db, body.family_id, body.payload)
    return GoogleCalendarIngestResponse(event=event, created=created)


@router.post("/ynab/ingest", response_model=YnabIngestResponse)
def ynab_ingest(
    body: YnabIngestRequest,
    db: Session = Depends(get_db),
):
    bill, created = ingest_scheduled_transaction(db, body.family_id, body.payload)
    return YnabIngestResponse(bill=bill, created=created)

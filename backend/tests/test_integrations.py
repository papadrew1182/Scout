"""Tests for the integrations layer.

Covers:
- Google Calendar ingestion creates a new event + mapping
- Re-ingesting the same external_id updates the existing event
- Source-of-truth: cannot ingest external payload onto a scout-source row
- YNAB ingestion creates a new bill + mapping
- YNAB re-ingestion preserves status / paid_at
- Tenant isolation: ingestion against family A does not touch family B
"""

import uuid
from datetime import date, datetime

import pytest
import pytz
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.calendar import Event
from app.models.connectors import ConnectorMapping
from app.models.finance import Bill
from app.models.foundation import Family
from app.services.integrations.base import SourceConflictError
from app.services.integrations.google_calendar import (
    GoogleCalendarEventPayload,
    ingest_event,
)
from app.services.integrations.ynab import (
    YnabScheduledTransactionPayload,
    ingest_scheduled_transaction,
)


def _dt(y, m, d, h=12, minute=0):
    return pytz.timezone("America/Chicago").localize(datetime(y, m, d, h, minute))


# ---------------------------------------------------------------------------
# Google Calendar
# ---------------------------------------------------------------------------

class TestGoogleCalendarIngest:
    def test_first_ingestion_creates_event_and_mapping(self, db: Session, family):
        payload = GoogleCalendarEventPayload(
            external_id="gcal_event_xyz_001",
            title="Q2 Planning",
            location="Conference Room A",
            starts_at=_dt(2026, 4, 13, 14),
            ends_at=_dt(2026, 4, 13, 16),
        )
        event, created = ingest_event(db, family.id, payload)

        assert created is True
        assert event.id is not None
        assert event.title == "Q2 Planning"
        assert event.source == "google_cal"
        assert event.family_id == family.id

        # Mapping was created
        mapping = db.scalars(
            select(ConnectorMapping)
            .where(ConnectorMapping.connector_name == "google_calendar")
            .where(ConnectorMapping.external_id == "gcal_event_xyz_001")
        ).first()
        assert mapping is not None
        assert mapping.internal_id == event.id
        assert mapping.internal_table == "events"

    def test_reingestion_updates_existing_event(self, db: Session, family):
        payload = GoogleCalendarEventPayload(
            external_id="gcal_event_xyz_002",
            title="Original",
            starts_at=_dt(2026, 4, 13, 14),
            ends_at=_dt(2026, 4, 13, 15),
        )
        event_v1, created_v1 = ingest_event(db, family.id, payload)
        original_id = event_v1.id
        assert created_v1 is True

        # Same external_id, updated title and time
        payload_v2 = GoogleCalendarEventPayload(
            external_id="gcal_event_xyz_002",
            title="Renamed",
            starts_at=_dt(2026, 4, 13, 15),
            ends_at=_dt(2026, 4, 13, 17),
        )
        event_v2, created_v2 = ingest_event(db, family.id, payload_v2)

        assert created_v2 is False
        assert event_v2.id == original_id
        assert event_v2.title == "Renamed"
        assert event_v2.starts_at == _dt(2026, 4, 13, 15)

        # Still only one mapping row
        mappings = list(
            db.scalars(
                select(ConnectorMapping)
                .where(ConnectorMapping.connector_name == "google_calendar")
                .where(ConnectorMapping.external_id == "gcal_event_xyz_002")
            ).all()
        )
        assert len(mappings) == 1

    def test_no_duplicate_events_on_repeat(self, db: Session, family):
        payload = GoogleCalendarEventPayload(
            external_id="gcal_event_xyz_003",
            title="Stable",
            starts_at=_dt(2026, 4, 13, 14),
            ends_at=_dt(2026, 4, 13, 15),
        )
        for _ in range(3):
            ingest_event(db, family.id, payload)

        events = list(
            db.scalars(
                select(Event)
                .where(Event.family_id == family.id)
                .where(Event.title == "Stable")
            ).all()
        )
        assert len(events) == 1

    def test_source_conflict_blocks_external_overwrite_of_scout_row(
        self, db: Session, family, adults
    ):
        # Create a Scout-authored event without going through ingestion
        scout_event = Event(
            family_id=family.id,
            created_by=adults["robert"].id,
            title="Scout-owned",
            starts_at=_dt(2026, 4, 13, 14),
            ends_at=_dt(2026, 4, 13, 15),
            source="scout",
        )
        db.add(scout_event)
        db.flush()

        # Manually plant a mapping pointing the external_id at this scout row
        # (simulating a misconfiguration / hostile sync attempt)
        mapping = ConnectorMapping(
            connector_name="google_calendar",
            internal_table="events",
            internal_id=scout_event.id,
            external_id="gcal_hostile_001",
            metadata_={"resource_type": "event"},
        )
        db.add(mapping)
        db.flush()

        payload = GoogleCalendarEventPayload(
            external_id="gcal_hostile_001",
            title="Hostile rewrite",
            starts_at=_dt(2026, 4, 13, 14),
            ends_at=_dt(2026, 4, 13, 15),
        )
        with pytest.raises(SourceConflictError):
            ingest_event(db, family.id, payload)


# ---------------------------------------------------------------------------
# YNAB
# ---------------------------------------------------------------------------

class TestYnabIngest:
    def test_first_ingestion_creates_bill_and_mapping(self, db: Session, family):
        payload = YnabScheduledTransactionPayload(
            external_id="ynab_txn_electric_001",
            title="Electric",
            amount_cents=14523,
            due_date=date(2026, 4, 22),
        )
        bill, created = ingest_scheduled_transaction(db, family.id, payload)

        assert created is True
        assert bill.title == "Electric"
        assert bill.source == "ynab"
        assert bill.status == "upcoming"
        assert bill.paid_at is None

        mapping = db.scalars(
            select(ConnectorMapping)
            .where(ConnectorMapping.connector_name == "ynab")
            .where(ConnectorMapping.external_id == "ynab_txn_electric_001")
        ).first()
        assert mapping is not None
        assert mapping.internal_id == bill.id

    def test_reingestion_preserves_paid_status(self, db: Session, family):
        payload = YnabScheduledTransactionPayload(
            external_id="ynab_txn_water_001",
            title="Water",
            amount_cents=6234,
            due_date=date(2026, 4, 3),
        )
        bill_v1, _ = ingest_scheduled_transaction(db, family.id, payload)

        # Parent marked it paid via Scout (simulate by updating directly)
        from app.services.finance_service import mark_bill_paid
        mark_bill_paid(db, family.id, bill_v1.id)

        # YNAB sends an updated payload (e.g. amount fix). Status should NOT revert.
        payload_v2 = YnabScheduledTransactionPayload(
            external_id="ynab_txn_water_001",
            title="Water (corrected)",
            amount_cents=6500,
            due_date=date(2026, 4, 3),
        )
        bill_v2, created_v2 = ingest_scheduled_transaction(db, family.id, payload_v2)

        assert created_v2 is False
        assert bill_v2.title == "Water (corrected)"
        assert bill_v2.amount_cents == 6500
        assert bill_v2.status == "paid"
        assert bill_v2.paid_at is not None

    def test_no_duplicate_bills_on_repeat(self, db: Session, family):
        payload = YnabScheduledTransactionPayload(
            external_id="ynab_txn_internet_001",
            title="Internet",
            amount_cents=8999,
            due_date=date(2026, 4, 18),
        )
        for _ in range(3):
            ingest_scheduled_transaction(db, family.id, payload)

        bills = list(
            db.scalars(
                select(Bill)
                .where(Bill.family_id == family.id)
                .where(Bill.title == "Internet")
            ).all()
        )
        assert len(bills) == 1


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------

class TestTenantIsolation:
    def test_ingestion_into_family_a_does_not_create_in_family_b(self, db: Session, family):
        other = Family(name="Other", timezone="America/New_York")
        db.add(other)
        db.flush()

        payload = GoogleCalendarEventPayload(
            external_id="gcal_event_isolation_001",
            title="Family A only",
            starts_at=_dt(2026, 4, 13, 14),
            ends_at=_dt(2026, 4, 13, 15),
        )
        ingest_event(db, family.id, payload)

        family_a_events = list(
            db.scalars(select(Event).where(Event.family_id == family.id)).all()
        )
        family_b_events = list(
            db.scalars(select(Event).where(Event.family_id == other.id)).all()
        )
        assert any(e.title == "Family A only" for e in family_a_events)
        assert not any(e.title == "Family A only" for e in family_b_events)

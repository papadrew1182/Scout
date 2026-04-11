"""YNAB ingestion v1.

Accepts a mocked YNAB scheduled-transaction payload and upserts it into
the bills table via connector_mappings.

No real YNAB API calls. No OAuth. No webhook receiver.
"""

import uuid
from datetime import date

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.finance import Bill
from app.services.integrations.base import upsert_via_mapping
from app.services.tenant_guard import require_family

CONNECTOR_NAME = "ynab"
INTERNAL_TABLE = "bills"
BILL_SOURCE = "ynab"


class YnabScheduledTransactionPayload(BaseModel):
    """Mocked subset of a YNAB scheduled transaction payload."""
    external_id: str
    title: str
    description: str | None = None
    amount_cents: int
    due_date: date


def ingest_scheduled_transaction(
    db: Session,
    family_id: uuid.UUID,
    payload: YnabScheduledTransactionPayload,
) -> tuple[Bill, bool]:
    """Ingest a single YNAB scheduled transaction.

    Returns (bill, created) where created is True if a new bill was made.
    """
    require_family(db, family_id)

    def fetch_by_id(internal_id: uuid.UUID) -> Bill | None:
        row = db.get(Bill, internal_id)
        if row and row.family_id == family_id:
            return row
        return None

    def create_fn() -> Bill:
        bill = Bill(
            family_id=family_id,
            created_by=None,
            title=payload.title,
            description=payload.description,
            amount_cents=payload.amount_cents,
            due_date=payload.due_date,
            status="upcoming",
            source=BILL_SOURCE,
        )
        db.add(bill)
        db.flush()
        return bill

    def update_fn(bill: Bill) -> None:
        # YNAB ingestion does NOT touch status / paid_at — those are Scout-side state.
        bill.title = payload.title
        bill.description = payload.description
        bill.amount_cents = payload.amount_cents
        bill.due_date = payload.due_date

    bill, created = upsert_via_mapping(
        db,
        connector_name=CONNECTOR_NAME,
        internal_table=INTERNAL_TABLE,
        external_id=payload.external_id,
        expected_source=BILL_SOURCE,
        fetch_by_id=fetch_by_id,
        create_fn=create_fn,
        update_fn=update_fn,
        metadata={"resource_type": "scheduled_transaction"},
    )
    db.commit()
    db.refresh(bill)
    return bill, created


def ingest_scheduled_transactions_batch(
    db: Session,
    family_id: uuid.UUID,
    payloads: list[YnabScheduledTransactionPayload],
) -> list[tuple[Bill, bool]]:
    results = []
    for payload in payloads:
        results.append(ingest_scheduled_transaction(db, family_id, payload))
    return results

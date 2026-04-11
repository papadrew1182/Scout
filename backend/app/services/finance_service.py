"""Finance service: bills CRUD + retrieval helpers.

No budget engine, no account reconciliation, no recurring expansion.
A recurring monthly bill is just multiple one-off bill rows.
"""

import uuid
from datetime import date, datetime, timedelta

from fastapi import HTTPException, status as http_status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.finance import Bill
from app.schemas.finance import BillCreate, BillUpdate
from app.services.tenant_guard import require_family, require_member_in_family

_VALID_STATUSES = ("upcoming", "paid", "overdue", "cancelled")
_VALID_SOURCES = ("scout", "ynab")
_UNPAID_STATUSES = ("upcoming", "overdue")


def _validate_status(value: str) -> None:
    if value not in _VALID_STATUSES:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status: {value}",
        )


def _validate_source(value: str) -> None:
    if value not in _VALID_SOURCES:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid source: {value}",
        )


def list_bills(
    db: Session,
    family_id: uuid.UUID,
    statuses: list[str] | None = None,
    due_before: date | None = None,
    due_after: date | None = None,
) -> list[Bill]:
    require_family(db, family_id)
    stmt = select(Bill).where(Bill.family_id == family_id)
    if statuses:
        stmt = stmt.where(Bill.status.in_(statuses))
    if due_before:
        stmt = stmt.where(Bill.due_date <= due_before)
    if due_after:
        stmt = stmt.where(Bill.due_date >= due_after)
    stmt = stmt.order_by(Bill.due_date, Bill.created_at)
    return list(db.scalars(stmt).all())


def list_upcoming_bills(
    db: Session,
    family_id: uuid.UUID,
    within_days: int = 30,
) -> list[Bill]:
    """Unpaid bills due between today and today+within_days inclusive."""
    require_family(db, family_id)
    today = date.today()
    horizon = today + timedelta(days=within_days)
    stmt = (
        select(Bill)
        .where(Bill.family_id == family_id)
        .where(Bill.status == "upcoming")
        .where(Bill.due_date >= today)
        .where(Bill.due_date <= horizon)
        .order_by(Bill.due_date, Bill.created_at)
    )
    return list(db.scalars(stmt).all())


def list_overdue_bills(
    db: Session, family_id: uuid.UUID, today: date | None = None
) -> list[Bill]:
    """Bills with due_date in the past that are not yet paid or cancelled.

    Includes both bills explicitly flagged 'overdue' and 'upcoming' bills
    whose due_date has passed.
    """
    require_family(db, family_id)
    cutoff = today or date.today()
    stmt = (
        select(Bill)
        .where(Bill.family_id == family_id)
        .where(Bill.status.in_(_UNPAID_STATUSES))
        .where(Bill.due_date < cutoff)
        .order_by(Bill.due_date)
    )
    return list(db.scalars(stmt).all())


def list_unpaid_bills(db: Session, family_id: uuid.UUID) -> list[Bill]:
    """All bills with status in (upcoming, overdue)."""
    require_family(db, family_id)
    stmt = (
        select(Bill)
        .where(Bill.family_id == family_id)
        .where(Bill.status.in_(_UNPAID_STATUSES))
        .order_by(Bill.due_date)
    )
    return list(db.scalars(stmt).all())


def get_bill(db: Session, family_id: uuid.UUID, bill_id: uuid.UUID) -> Bill:
    bill = db.get(Bill, bill_id)
    if not bill or bill.family_id != family_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Bill not found",
        )
    return bill


def create_bill(db: Session, family_id: uuid.UUID, payload: BillCreate) -> Bill:
    require_family(db, family_id)
    if payload.created_by:
        require_member_in_family(db, family_id, payload.created_by)
    _validate_status(payload.status)
    _validate_source(payload.source)
    if payload.amount_cents < 0:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="amount_cents must be non-negative",
        )

    paid_at = (
        datetime.now().astimezone() if payload.status == "paid" else None
    )

    bill = Bill(
        family_id=family_id,
        created_by=payload.created_by,
        title=payload.title,
        description=payload.description,
        notes=payload.notes,
        amount_cents=payload.amount_cents,
        due_date=payload.due_date,
        status=payload.status,
        paid_at=paid_at,
        source=payload.source,
    )
    db.add(bill)
    db.commit()
    db.refresh(bill)
    return bill


def update_bill(
    db: Session,
    family_id: uuid.UUID,
    bill_id: uuid.UUID,
    payload: BillUpdate,
) -> Bill:
    bill = get_bill(db, family_id, bill_id)
    data = payload.model_dump(exclude_unset=True)

    if "status" in data:
        _validate_status(data["status"])
    if "amount_cents" in data and data["amount_cents"] is not None and data["amount_cents"] < 0:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="amount_cents must be non-negative",
        )

    # Drive paid_at from status to satisfy chk_bills_paid_consistency
    new_status = data.get("status", bill.status)
    if new_status == "paid" and bill.status != "paid":
        data["paid_at"] = datetime.now().astimezone()
    elif new_status != "paid" and bill.status == "paid":
        data["paid_at"] = None

    for key, value in data.items():
        setattr(bill, key, value)
    db.commit()
    db.refresh(bill)
    return bill


def mark_bill_paid(db: Session, family_id: uuid.UUID, bill_id: uuid.UUID) -> Bill:
    bill = get_bill(db, family_id, bill_id)
    if bill.status == "paid":
        return bill
    bill.status = "paid"
    bill.paid_at = datetime.now().astimezone()
    db.commit()
    db.refresh(bill)
    return bill


def mark_bill_unpaid(db: Session, family_id: uuid.UUID, bill_id: uuid.UUID) -> Bill:
    """Revert a paid bill to upcoming. Clears paid_at."""
    bill = get_bill(db, family_id, bill_id)
    if bill.status != "paid":
        return bill
    bill.status = "upcoming"
    bill.paid_at = None
    db.commit()
    db.refresh(bill)
    return bill


def delete_bill(db: Session, family_id: uuid.UUID, bill_id: uuid.UUID) -> None:
    bill = get_bill(db, family_id, bill_id)
    db.delete(bill)
    db.commit()

"""Tests for finance_service.

Covers:
- create / read / update / delete
- status & source validation
- amount non-negative validation
- paid_at consistency CHECK + transitions
- mark paid / unpaid
- title not blank
- list filters (status, due window)
- upcoming / overdue / unpaid helpers
- tenant isolation
"""

import uuid
from datetime import date, datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.finance import Bill
from app.models.foundation import Family
from app.schemas.finance import BillCreate, BillUpdate
from app.services.finance_service import (
    create_bill,
    delete_bill,
    get_bill,
    list_bills,
    list_overdue_bills,
    list_unpaid_bills,
    list_upcoming_bills,
    mark_bill_paid,
    mark_bill_unpaid,
    update_bill,
)


class TestCreate:
    def test_create_basic(self, db: Session, family, adults):
        andrew = adults["robert"]
        bill = create_bill(
            db, family.id,
            BillCreate(
                created_by=andrew.id,
                title="Mortgage",
                amount_cents=245000,
                due_date=date(2026, 5, 1),
            ),
        )
        assert bill.id is not None
        assert bill.status == "upcoming"
        assert bill.paid_at is None
        assert bill.source == "scout"

    def test_create_paid_sets_paid_at(self, db: Session, family, adults):
        bill = create_bill(
            db, family.id,
            BillCreate(
                title="Already paid",
                amount_cents=1000,
                due_date=date(2026, 4, 1),
                status="paid",
            ),
        )
        assert bill.status == "paid"
        assert bill.paid_at is not None

    def test_invalid_status_rejected(self, db: Session, family):
        with pytest.raises(HTTPException) as exc:
            create_bill(
                db, family.id,
                BillCreate(
                    title="Bad",
                    amount_cents=100,
                    due_date=date(2026, 5, 1),
                    status="floating",
                ),
            )
        assert exc.value.status_code == 400

    def test_invalid_source_rejected(self, db: Session, family):
        with pytest.raises(HTTPException) as exc:
            create_bill(
                db, family.id,
                BillCreate(
                    title="Bad",
                    amount_cents=100,
                    due_date=date(2026, 5, 1),
                    source="venmo",
                ),
            )
        assert exc.value.status_code == 400

    def test_negative_amount_rejected(self, db: Session, family):
        with pytest.raises(HTTPException) as exc:
            create_bill(
                db, family.id,
                BillCreate(
                    title="Bad",
                    amount_cents=-500,
                    due_date=date(2026, 5, 1),
                ),
            )
        assert exc.value.status_code == 400

    def test_blank_title_rejected_at_db(self, db: Session, family):
        bad = Bill(
            family_id=family.id,
            title="   ",
            amount_cents=100,
            due_date=date(2026, 5, 1),
        )
        db.add(bad)
        with pytest.raises(IntegrityError):
            db.flush()

    def test_db_paid_consistency_check(self, db: Session, family):
        bad = Bill(
            family_id=family.id,
            title="Inconsistent",
            amount_cents=100,
            due_date=date(2026, 5, 1),
            status="upcoming",
            paid_at=datetime.now().astimezone(),
        )
        db.add(bad)
        with pytest.raises(IntegrityError):
            db.flush()


class TestUpdateAndPayment:
    def test_mark_paid(self, db: Session, family):
        bill = create_bill(
            db, family.id,
            BillCreate(title="Electric", amount_cents=10000, due_date=date(2026, 5, 1)),
        )
        paid = mark_bill_paid(db, family.id, bill.id)
        assert paid.status == "paid"
        assert paid.paid_at is not None

    def test_mark_unpaid_clears_paid_at(self, db: Session, family):
        bill = create_bill(
            db, family.id,
            BillCreate(title="X", amount_cents=100, due_date=date(2026, 5, 1), status="paid"),
        )
        reverted = mark_bill_unpaid(db, family.id, bill.id)
        assert reverted.status == "upcoming"
        assert reverted.paid_at is None

    def test_update_status_to_paid_sets_paid_at(self, db: Session, family):
        bill = create_bill(
            db, family.id,
            BillCreate(title="X", amount_cents=100, due_date=date(2026, 5, 1)),
        )
        updated = update_bill(db, family.id, bill.id, BillUpdate(status="paid"))
        assert updated.status == "paid"
        assert updated.paid_at is not None

    def test_update_paid_to_cancelled_clears_paid_at(self, db: Session, family):
        bill = create_bill(
            db, family.id,
            BillCreate(title="X", amount_cents=100, due_date=date(2026, 5, 1), status="paid"),
        )
        updated = update_bill(db, family.id, bill.id, BillUpdate(status="cancelled"))
        assert updated.status == "cancelled"
        assert updated.paid_at is None

    def test_delete(self, db: Session, family):
        bill = create_bill(
            db, family.id,
            BillCreate(title="X", amount_cents=100, due_date=date(2026, 5, 1)),
        )
        delete_bill(db, family.id, bill.id)
        with pytest.raises(HTTPException) as exc:
            get_bill(db, family.id, bill.id)
        assert exc.value.status_code == 404


class TestRetrievalHelpers:
    def test_upcoming_within_horizon(self, db: Session, family):
        today = date.today()
        # Inside horizon
        b1 = create_bill(
            db, family.id,
            BillCreate(title="Soon", amount_cents=100, due_date=today + timedelta(days=10)),
        )
        # Outside horizon
        create_bill(
            db, family.id,
            BillCreate(title="Far", amount_cents=100, due_date=today + timedelta(days=60)),
        )
        # Already paid (excluded)
        create_bill(
            db, family.id,
            BillCreate(title="Paid", amount_cents=100, due_date=today + timedelta(days=5), status="paid"),
        )

        results = list_upcoming_bills(db, family.id, within_days=30)
        titles = {b.title for b in results}
        assert titles == {"Soon"}

    def test_overdue_helper(self, db: Session, family):
        today = date.today()
        # Past due, still upcoming
        create_bill(
            db, family.id,
            BillCreate(title="Past upcoming", amount_cents=100, due_date=today - timedelta(days=5)),
        )
        # Explicitly overdue
        create_bill(
            db, family.id,
            BillCreate(title="Overdue flagged", amount_cents=100, due_date=today - timedelta(days=10), status="overdue"),
        )
        # Past due but paid
        create_bill(
            db, family.id,
            BillCreate(title="Past paid", amount_cents=100, due_date=today - timedelta(days=2), status="paid"),
        )
        # Future
        create_bill(
            db, family.id,
            BillCreate(title="Future", amount_cents=100, due_date=today + timedelta(days=5)),
        )

        results = list_overdue_bills(db, family.id)
        titles = {b.title for b in results}
        assert titles == {"Past upcoming", "Overdue flagged"}

    def test_unpaid_helper(self, db: Session, family):
        today = date.today()
        create_bill(db, family.id, BillCreate(title="U", amount_cents=100, due_date=today))
        create_bill(db, family.id, BillCreate(title="O", amount_cents=100, due_date=today, status="overdue"))
        create_bill(db, family.id, BillCreate(title="P", amount_cents=100, due_date=today, status="paid"))
        create_bill(db, family.id, BillCreate(title="C", amount_cents=100, due_date=today, status="cancelled"))

        results = list_unpaid_bills(db, family.id)
        titles = {b.title for b in results}
        assert titles == {"U", "O"}

    def test_list_filters_by_status(self, db: Session, family):
        today = date.today()
        create_bill(db, family.id, BillCreate(title="P", amount_cents=100, due_date=today, status="paid"))
        create_bill(db, family.id, BillCreate(title="U", amount_cents=100, due_date=today))

        results = list_bills(db, family.id, statuses=["paid"])
        titles = {b.title for b in results}
        assert titles == {"P"}


class TestTenantIsolation:
    def test_get_bill_from_wrong_family_404(self, db: Session, family):
        other = Family(name="Other", timezone="America/New_York")
        db.add(other)
        db.flush()
        bill = create_bill(
            db, other.id,
            BillCreate(title="Theirs", amount_cents=100, due_date=date(2026, 5, 1)),
        )
        with pytest.raises(HTTPException) as exc:
            get_bill(db, family.id, bill.id)
        assert exc.value.status_code == 404

    def test_list_bills_only_returns_own_family(self, db: Session, family):
        other = Family(name="Other", timezone="America/New_York")
        db.add(other)
        db.flush()
        create_bill(db, family.id, BillCreate(title="Mine", amount_cents=100, due_date=date(2026, 5, 1)))
        create_bill(db, other.id, BillCreate(title="Theirs", amount_cents=100, due_date=date(2026, 5, 1)))

        results = list_bills(db, family.id)
        titles = {b.title for b in results}
        assert "Mine" in titles
        assert "Theirs" not in titles

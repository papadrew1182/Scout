"""Tests for the parent-initiated allowance adjustment endpoint.

Covers:
    - bonus writes a positive-amount_cents row with entry_type='adjustment'
      and a note prefixed ``[bonus]``
    - penalty writes a negative-amount_cents row with note prefixed
      ``[penalty]``
    - balance sums include the signed adjustment
    - validation: cents must be > 0, kind must be bonus/penalty, reason
      must be non-empty
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.life_management import AllowanceLedger
from app.schemas.life_management import AllowanceAdjustmentCreate
from app.services.payout_service import create_adjustment, get_balance


class TestAdjustmentShape:
    def test_bonus_writes_positive_ledger_row(self, db: Session, family, children):
        sadie = children["sadie"]
        payload = AllowanceAdjustmentCreate(
            family_member_id=sadie.id,
            cents=500,
            reason="Helped cook dinner",
            kind="bonus",
        )
        entry = create_adjustment(db, family.id, payload)

        assert entry.entry_type == "adjustment"
        assert entry.amount_cents == 500  # bonus = positive
        assert entry.family_member_id == sadie.id
        assert entry.note == "[bonus] Helped cook dinner"
        assert entry.week_start is None

        # Persisted row is queryable
        row = db.scalars(
            select(AllowanceLedger).where(AllowanceLedger.id == entry.id)
        ).one()
        assert row.amount_cents == 500

    def test_penalty_writes_negative_ledger_row(self, db: Session, family, children):
        sadie = children["sadie"]
        payload = AllowanceAdjustmentCreate(
            family_member_id=sadie.id,
            cents=300,
            reason="Skipped chores",
            kind="penalty",
        )
        entry = create_adjustment(db, family.id, payload)

        assert entry.entry_type == "adjustment"
        assert entry.amount_cents == -300  # penalty = negative
        assert entry.note == "[penalty] Skipped chores"

    def test_reason_is_stripped(self, db: Session, family, children):
        sadie = children["sadie"]
        payload = AllowanceAdjustmentCreate(
            family_member_id=sadie.id,
            cents=100,
            reason="  extra whitespace  ",
            kind="bonus",
        )
        entry = create_adjustment(db, family.id, payload)
        assert entry.note == "[bonus] extra whitespace"


class TestBalanceImpact:
    def test_bonus_increases_balance(self, db: Session, family, children):
        sadie = children["sadie"]
        before = get_balance(db, family.id, sadie.id)
        create_adjustment(
            db,
            family.id,
            AllowanceAdjustmentCreate(
                family_member_id=sadie.id,
                cents=250,
                reason="Read a book",
                kind="bonus",
            ),
        )
        after = get_balance(db, family.id, sadie.id)
        assert after - before == 250

    def test_penalty_decreases_balance(self, db: Session, family, children):
        sadie = children["sadie"]
        before = get_balance(db, family.id, sadie.id)
        create_adjustment(
            db,
            family.id,
            AllowanceAdjustmentCreate(
                family_member_id=sadie.id,
                cents=150,
                reason="Back talk",
                kind="penalty",
            ),
        )
        after = get_balance(db, family.id, sadie.id)
        assert after - before == -150

    def test_bonus_then_penalty_nets_to_difference(
        self, db: Session, family, children
    ):
        sadie = children["sadie"]
        before = get_balance(db, family.id, sadie.id)
        create_adjustment(
            db, family.id,
            AllowanceAdjustmentCreate(
                family_member_id=sadie.id, cents=500, reason="a", kind="bonus",
            ),
        )
        create_adjustment(
            db, family.id,
            AllowanceAdjustmentCreate(
                family_member_id=sadie.id, cents=200, reason="b", kind="penalty",
            ),
        )
        after = get_balance(db, family.id, sadie.id)
        assert after - before == 300


class TestValidation:
    def test_cents_must_be_positive(self):
        with pytest.raises(ValueError):
            AllowanceAdjustmentCreate(
                family_member_id="00000000-0000-0000-0000-000000000001",
                cents=0,
                reason="zero",
                kind="bonus",
            )

    def test_cents_cannot_be_negative(self):
        with pytest.raises(ValueError):
            AllowanceAdjustmentCreate(
                family_member_id="00000000-0000-0000-0000-000000000001",
                cents=-100,
                reason="neg",
                kind="bonus",
            )

    def test_kind_must_be_bonus_or_penalty(self):
        with pytest.raises(ValueError):
            AllowanceAdjustmentCreate(
                family_member_id="00000000-0000-0000-0000-000000000001",
                cents=100,
                reason="x",
                kind="reward",  # not in {bonus, penalty}
            )

    def test_reason_cannot_be_empty(self):
        with pytest.raises(ValueError):
            AllowanceAdjustmentCreate(
                family_member_id="00000000-0000-0000-0000-000000000001",
                cents=100,
                reason="",
                kind="bonus",
            )

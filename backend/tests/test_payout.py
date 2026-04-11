"""Tests for payout_service.

Covers:
- payout tiers: 5/5, 4/5, 3/5, ≤2 wins
- duplicate payout prevention
- week_start must be Monday
"""

from datetime import date, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.life_management import AllowanceLedger, DailyWin
from app.services.payout_service import compute_payout, create_weekly_payout


def _seed_wins(db: Session, family_id, member_id, week_start: date, win_days: list[bool]):
    """Seed daily_wins for Mon-Fri. win_days is a 5-element list of booleans."""
    for i, is_win in enumerate(win_days):
        d = week_start + timedelta(days=i)
        db.add(DailyWin(
            family_id=family_id,
            family_member_id=member_id,
            win_date=d,
            is_win=is_win,
            task_count=5,
            completed_count=5 if is_win else 3,
        ))
    db.flush()


class TestPayoutTiers:
    WEEK = date(2026, 3, 30)  # Monday
    BASELINE = 1200  # $12.00

    def test_5_wins_100_pct(self, db: Session, family, children):
        sadie = children["sadie"]
        _seed_wins(db, family.id, sadie.id, self.WEEK, [True, True, True, True, True])
        result = compute_payout(db, family.id, sadie.id, self.WEEK, self.BASELINE)
        assert result.win_count == 5
        assert result.tier_pct == 1.0
        assert result.amount_cents == 1200

    def test_4_wins_80_pct(self, db: Session, family, children):
        sadie = children["sadie"]
        _seed_wins(db, family.id, sadie.id, self.WEEK, [True, True, True, True, False])
        result = compute_payout(db, family.id, sadie.id, self.WEEK, self.BASELINE)
        assert result.win_count == 4
        assert result.tier_pct == 0.8
        assert result.amount_cents == 960

    def test_3_wins_60_pct(self, db: Session, family, children):
        sadie = children["sadie"]
        _seed_wins(db, family.id, sadie.id, self.WEEK, [True, True, True, False, False])
        result = compute_payout(db, family.id, sadie.id, self.WEEK, self.BASELINE)
        assert result.win_count == 3
        assert result.tier_pct == 0.6
        assert result.amount_cents == 720

    def test_2_wins_0_pct(self, db: Session, family, children):
        sadie = children["sadie"]
        _seed_wins(db, family.id, sadie.id, self.WEEK, [True, True, False, False, False])
        result = compute_payout(db, family.id, sadie.id, self.WEEK, self.BASELINE)
        assert result.win_count == 2
        assert result.tier_pct == 0.0
        assert result.amount_cents == 0

    def test_0_wins_0_pct(self, db: Session, family, children):
        sadie = children["sadie"]
        _seed_wins(db, family.id, sadie.id, self.WEEK, [False, False, False, False, False])
        result = compute_payout(db, family.id, sadie.id, self.WEEK, self.BASELINE)
        assert result.amount_cents == 0


class TestPayoutCreation:
    WEEK = date(2026, 3, 30)

    def test_create_weekly_payout_writes_ledger(self, db: Session, family, children):
        sadie = children["sadie"]
        _seed_wins(db, family.id, sadie.id, self.WEEK, [True, True, True, True, True])
        computation = compute_payout(db, family.id, sadie.id, self.WEEK, 1200)
        entry = create_weekly_payout(db, family.id, computation)

        assert entry.entry_type == "weekly_payout"
        assert entry.amount_cents == 1200
        assert entry.week_start == self.WEEK

    def test_duplicate_payout_raises(self, db: Session, family, children):
        sadie = children["sadie"]
        _seed_wins(db, family.id, sadie.id, self.WEEK, [True, True, True, True, True])
        computation = compute_payout(db, family.id, sadie.id, self.WEEK, 1200)
        create_weekly_payout(db, family.id, computation)

        with pytest.raises(Exception):
            create_weekly_payout(db, family.id, computation)


class TestWeekStartValidation:
    def test_non_monday_raises(self, db: Session, family, children):
        sadie = children["sadie"]
        tuesday = date(2026, 3, 31)
        with pytest.raises(HTTPException) as exc_info:
            compute_payout(db, family.id, sadie.id, tuesday, 1200)
        assert exc_info.value.status_code == 400

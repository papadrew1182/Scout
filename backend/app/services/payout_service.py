"""Computes weekly payouts from daily_wins and writes to allowance_ledger.

Payout computation is separated from ledger-entry creation.
"""

import uuid
from dataclasses import dataclass
from datetime import date, timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.life_management import AllowanceLedger, DailyWin
from app.schemas.life_management import AllowanceAdjustmentCreate, AllowanceLedgerCreate
from app.services.tenant_guard import require_family, require_member_in_family

PAYOUT_TIERS = {5: 1.0, 4: 0.8, 3: 0.6}  # 2 or fewer = 0


@dataclass
class PayoutComputation:
    family_member_id: uuid.UUID
    week_start: date
    win_count: int
    tier_pct: float
    baseline_cents: int
    amount_cents: int


def compute_payout(
    db: Session,
    family_id: uuid.UUID,
    member_id: uuid.UUID,
    week_start: date,
    baseline_cents: int,
) -> PayoutComputation:
    """Compute payout amount without writing to the ledger."""
    if week_start.isoweekday() != 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="week_start must be a Monday")

    week_end = week_start + timedelta(days=4)  # Friday

    win_count_result = db.scalar(
        select(func.count())
        .select_from(DailyWin)
        .where(DailyWin.family_id == family_id)
        .where(DailyWin.family_member_id == member_id)
        .where(DailyWin.win_date >= week_start)
        .where(DailyWin.win_date <= week_end)
        .where(DailyWin.is_win.is_(True))
    )
    win_count = win_count_result or 0
    tier_pct = PAYOUT_TIERS.get(win_count, 0.0)
    amount_cents = int(baseline_cents * tier_pct)

    return PayoutComputation(
        family_member_id=member_id,
        week_start=week_start,
        win_count=win_count,
        tier_pct=tier_pct,
        baseline_cents=baseline_cents,
        amount_cents=amount_cents,
    )


def create_weekly_payout(db: Session, family_id: uuid.UUID, computation: PayoutComputation) -> AllowanceLedger:
    """Write a weekly payout to the ledger. Returns 409 if a payout already exists for this member+week."""
    existing = db.scalars(
        select(AllowanceLedger)
        .where(AllowanceLedger.family_member_id == computation.family_member_id)
        .where(AllowanceLedger.week_start == computation.week_start)
        .where(AllowanceLedger.entry_type == "weekly_payout")
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Weekly payout already exists for member {computation.family_member_id} week {computation.week_start}",
        )

    entry = AllowanceLedger(
        family_id=family_id,
        family_member_id=computation.family_member_id,
        entry_type="weekly_payout",
        amount_cents=computation.amount_cents,
        week_start=computation.week_start,
        note=f"{computation.win_count}/5 Daily Wins — {int(computation.tier_pct * 100)}% of ${computation.baseline_cents / 100:.2f}",
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def create_manual_entry(db: Session, family_id: uuid.UUID, payload: AllowanceLedgerCreate) -> AllowanceLedger:
    """Create a school_reward, extra, or adjustment ledger entry."""
    require_family(db, family_id)
    require_member_in_family(db, family_id, payload.family_member_id)

    if payload.entry_type == "weekly_payout":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Use the weekly payout endpoint for weekly_payout entries",
        )

    entry = AllowanceLedger(
        family_id=family_id,
        family_member_id=payload.family_member_id,
        entry_type=payload.entry_type,
        amount_cents=payload.amount_cents,
        week_start=payload.week_start,
        note=payload.note,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def create_adjustment(
    db: Session, family_id: uuid.UUID, payload: AllowanceAdjustmentCreate
) -> AllowanceLedger:
    """Create a parent-initiated bonus or penalty ledger entry.

    ``cents`` is always positive; the sign is derived from ``kind``.
    The note field captures ``[bonus]`` / ``[penalty]`` plus the
    parent-supplied reason, so readers can categorize without adding
    another column.
    """
    require_family(db, family_id)
    require_member_in_family(db, family_id, payload.family_member_id)

    signed_cents = payload.cents if payload.kind == "bonus" else -payload.cents
    entry = AllowanceLedger(
        family_id=family_id,
        family_member_id=payload.family_member_id,
        entry_type="adjustment",
        amount_cents=signed_cents,
        note=f"[{payload.kind}] {payload.reason.strip()}",
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def list_ledger(
    db: Session,
    family_id: uuid.UUID,
    member_id: uuid.UUID | None = None,
) -> list[AllowanceLedger]:
    require_family(db, family_id)
    stmt = select(AllowanceLedger).where(AllowanceLedger.family_id == family_id)
    if member_id:
        stmt = stmt.where(AllowanceLedger.family_member_id == member_id)
    stmt = stmt.order_by(AllowanceLedger.created_at.desc())
    return list(db.scalars(stmt).all())


def get_balance(db: Session, family_id: uuid.UUID, member_id: uuid.UUID) -> int:
    require_family(db, family_id)
    require_member_in_family(db, family_id, member_id)
    result = db.scalar(
        select(func.coalesce(func.sum(AllowanceLedger.amount_cents), 0))
        .where(AllowanceLedger.family_id == family_id)
        .where(AllowanceLedger.family_member_id == member_id)
    )
    return result or 0

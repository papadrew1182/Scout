import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth import Actor, get_current_actor
from app.database import get_db
from app.schemas.life_management import (
    AllowanceLedgerCreate,
    AllowanceLedgerRead,
    BalanceRead,
)
from app.services import payout_service

router = APIRouter(prefix="/families/{family_id}/allowance", tags=["allowance"])


@router.get("/ledger", response_model=list[AllowanceLedgerRead])
def list_ledger(
    family_id: uuid.UUID,
    member_id: uuid.UUID | None = Query(None),
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_family(family_id)
    return payout_service.list_ledger(db, family_id, member_id)


@router.post("/ledger", response_model=AllowanceLedgerRead, status_code=201)
def create_manual_entry(
    family_id: uuid.UUID,
    payload: AllowanceLedgerCreate,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_family(family_id)
    return payout_service.create_manual_entry(db, family_id, payload)


@router.post("/weekly-payout", response_model=AllowanceLedgerRead, status_code=201)
def create_weekly_payout(
    family_id: uuid.UUID,
    member_id: uuid.UUID = Query(...),
    baseline_cents: int = Query(...),
    week_start: date = Query(...),
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_family(family_id)
    actor.require_permission("allowance.run_payout")
    computation = payout_service.compute_payout(db, family_id, member_id, week_start, baseline_cents)
    return payout_service.create_weekly_payout(db, family_id, computation)


@router.get("/balance/{member_id}", response_model=BalanceRead)
def get_balance(family_id: uuid.UUID, member_id: uuid.UUID, actor: Actor = Depends(get_current_actor), db: Session = Depends(get_db)):
    actor.require_family(family_id)
    balance = payout_service.get_balance(db, family_id, member_id)
    return BalanceRead(family_member_id=member_id, balance_cents=balance)

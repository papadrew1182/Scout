import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth import Actor, get_current_actor
from app.database import get_db
from app.schemas.finance import BillCreate, BillRead, BillUpdate
from app.services import finance_service

router = APIRouter(prefix="/families/{family_id}/bills", tags=["finance"])


@router.get("", response_model=list[BillRead])
def list_bills(
    family_id: uuid.UUID,
    status: list[str] | None = Query(None),
    due_before: date | None = Query(None),
    due_after: date | None = Query(None),
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_family(family_id)
    return finance_service.list_bills(db, family_id, status, due_before, due_after)


@router.get("/upcoming", response_model=list[BillRead])
def list_upcoming(
    family_id: uuid.UUID,
    within_days: int = Query(30, ge=1, le=365),
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_family(family_id)
    return finance_service.list_upcoming_bills(db, family_id, within_days)


@router.get("/overdue", response_model=list[BillRead])
def list_overdue(family_id: uuid.UUID, actor: Actor = Depends(get_current_actor), db: Session = Depends(get_db)):
    actor.require_family(family_id)
    return finance_service.list_overdue_bills(db, family_id)


@router.get("/unpaid", response_model=list[BillRead])
def list_unpaid(family_id: uuid.UUID, actor: Actor = Depends(get_current_actor), db: Session = Depends(get_db)):
    actor.require_family(family_id)
    return finance_service.list_unpaid_bills(db, family_id)


@router.post("", response_model=BillRead, status_code=201)
def create_bill(family_id: uuid.UUID, payload: BillCreate, actor: Actor = Depends(get_current_actor), db: Session = Depends(get_db)):
    actor.require_family(family_id)
    actor.require_permission("admin.manage_config")
    return finance_service.create_bill(db, family_id, payload)


@router.get("/{bill_id}", response_model=BillRead)
def get_bill(family_id: uuid.UUID, bill_id: uuid.UUID, actor: Actor = Depends(get_current_actor), db: Session = Depends(get_db)):
    actor.require_family(family_id)
    return finance_service.get_bill(db, family_id, bill_id)


@router.patch("/{bill_id}", response_model=BillRead)
def update_bill(
    family_id: uuid.UUID,
    bill_id: uuid.UUID,
    payload: BillUpdate,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_family(family_id)
    actor.require_permission("admin.manage_config")
    return finance_service.update_bill(db, family_id, bill_id, payload)


@router.post("/{bill_id}/pay", response_model=BillRead)
def pay_bill(family_id: uuid.UUID, bill_id: uuid.UUID, actor: Actor = Depends(get_current_actor), db: Session = Depends(get_db)):
    actor.require_family(family_id)
    actor.require_permission("admin.manage_config")
    return finance_service.mark_bill_paid(db, family_id, bill_id)


@router.post("/{bill_id}/unpay", response_model=BillRead)
def unpay_bill(family_id: uuid.UUID, bill_id: uuid.UUID, actor: Actor = Depends(get_current_actor), db: Session = Depends(get_db)):
    actor.require_family(family_id)
    actor.require_permission("admin.manage_config")
    return finance_service.mark_bill_unpaid(db, family_id, bill_id)


@router.delete("/{bill_id}", status_code=204)
def delete_bill(family_id: uuid.UUID, bill_id: uuid.UUID, actor: Actor = Depends(get_current_actor), db: Session = Depends(get_db)):
    actor.require_family(family_id)
    actor.require_permission("admin.manage_config")
    finance_service.delete_bill(db, family_id, bill_id)

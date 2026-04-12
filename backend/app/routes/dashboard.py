"""Dashboard aggregation + action inbox routes."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import dashboard_service

router = APIRouter(prefix="/families/{family_id}", tags=["dashboard"])


@router.get("/dashboard/personal")
def personal_dashboard(
    family_id: uuid.UUID,
    member_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
):
    return dashboard_service.personal_dashboard(db, family_id, member_id)


@router.get("/dashboard/parent")
def parent_dashboard(
    family_id: uuid.UUID,
    member_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
):
    return dashboard_service.parent_dashboard(db, family_id, member_id)


@router.get("/dashboard/child")
def child_dashboard(
    family_id: uuid.UUID,
    member_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
):
    return dashboard_service.child_dashboard(db, family_id, member_id)


@router.get("/action-items/current")
def list_current_action_items(
    family_id: uuid.UUID,
    member_id: uuid.UUID = Query(...),
    status: str = Query("pending"),
    db: Session = Depends(get_db),
):
    return dashboard_service.list_action_items(db, family_id, member_id, status)

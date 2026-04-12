"""Dashboard aggregation + action inbox routes."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth import Actor, get_current_actor
from app.database import get_db
from app.services import dashboard_service

router = APIRouter(prefix="/families/{family_id}", tags=["dashboard"])


@router.get("/dashboard/personal")
def personal_dashboard(
    family_id: uuid.UUID,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_family(family_id)
    return dashboard_service.personal_dashboard(db, family_id, actor.member_id)


@router.get("/dashboard/parent")
def parent_dashboard(
    family_id: uuid.UUID,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_family(family_id)
    return dashboard_service.parent_dashboard(db, family_id, actor.member_id)


@router.get("/dashboard/child")
def child_dashboard(
    family_id: uuid.UUID,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_family(family_id)
    return dashboard_service.child_dashboard(db, family_id, actor.member_id)


@router.get("/action-items/current")
def list_current_action_items(
    family_id: uuid.UUID,
    status: str = Query("pending"),
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_family(family_id)
    return dashboard_service.list_action_items(db, family_id, actor.member_id, status)

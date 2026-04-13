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


@router.get("/dashboard/parent/insight")
def parent_dashboard_insight(
    family_id: uuid.UUID,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    """AI-generated off_track narrative for the parent dashboard.
    Cached per day. Fallback to a rule-based sentence if AI fails.
    Called as a parallel request by the frontend so the main dashboard
    render is not blocked on a Claude round-trip."""
    from fastapi import HTTPException, status as http_status
    from app.ai.insights import get_off_track_insight
    from app.models.foundation import FamilyMember

    actor.require_family(family_id)
    member = db.get(FamilyMember, actor.member_id)
    if not member or member.role != "adult":
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Parent insight requires adult role",
        )

    # Recompute the rule engine data inline using the existing service
    # so insights can never drift from the source-of-truth banner.
    payload = dashboard_service.parent_dashboard(db, family_id, actor.member_id)
    health = payload.get("household_health", {"status": "unknown", "reasons": []})
    child_statuses = payload.get("children", [])

    result = get_off_track_insight(
        db,
        family_id=family_id,
        health=health,
        child_statuses=child_statuses,
    )
    db.commit()
    return result


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


@router.get("/action-items/{item_id}")
def get_action_item(
    family_id: uuid.UUID,
    item_id: uuid.UUID,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    """Fetch one action item by id. Family-scoped."""
    from fastapi import HTTPException
    from app.models.action_items import ParentActionItem

    actor.require_family(family_id)
    item = db.get(ParentActionItem, item_id)
    if not item or item.family_id != family_id:
        raise HTTPException(status_code=404, detail="Action item not found")
    return {
        "id": str(item.id),
        "family_id": str(item.family_id),
        "action_type": item.action_type,
        "title": item.title,
        "detail": item.detail,
        "entity_type": item.entity_type,
        "entity_id": str(item.entity_id) if item.entity_id else None,
        "status": item.status,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


@router.post("/action-items/{item_id}/resolve")
def resolve_action_item(
    family_id: uuid.UUID,
    item_id: uuid.UUID,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    from fastapi import HTTPException
    from app.models.action_items import ParentActionItem

    actor.require_family(family_id)
    item = db.get(ParentActionItem, item_id)
    if not item or item.family_id != family_id:
        raise HTTPException(status_code=404, detail="Action item not found")
    item.status = "resolved"
    db.commit()
    return {"ok": True, "status": item.status}

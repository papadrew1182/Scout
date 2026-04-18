"""Admin routes for affirmation management.

All endpoints require affirmations.manage_config permission.

  GET    /admin/affirmations              — list library with filters
  POST   /admin/affirmations              — create affirmation
  PUT    /admin/affirmations/{id}         — update affirmation
  PATCH  /admin/affirmations/{id}/active  — toggle active
  GET    /admin/affirmations/analytics    — aggregate stats
  GET    /admin/affirmations/config       — read governance config
  PUT    /admin/affirmations/config       — update governance config
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select as sa_select
from sqlalchemy.orm import Session

from app.auth import Actor, get_current_actor
from app.database import get_db
from app.models.affirmations import Affirmation
from app.models.access import HouseholdRule
from app.services.affirmation_engine import get_affirmation_analytics

router = APIRouter(prefix="/admin/affirmations", tags=["admin-affirmations"])

PERMISSION = "affirmations.manage_config"


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class AffirmationItem(BaseModel):
    id: str
    text: str
    category: str | None = None
    tags: list = []
    tone: str | None = None
    philosophy: str | None = None
    audience_type: str = "general"
    length_class: str = "short"
    active: bool = True
    source_type: str = "curated"
    created_at: str | None = None
    updated_at: str | None = None


class AffirmationCreatePayload(BaseModel):
    text: str
    category: str | None = None
    tags: list = []
    tone: str | None = None
    philosophy: str | None = None
    audience_type: str = "general"
    length_class: str = "short"


class AffirmationUpdatePayload(BaseModel):
    text: str | None = None
    category: str | None = None
    tags: list | None = None
    tone: str | None = None
    philosophy: str | None = None
    audience_type: str | None = None
    length_class: str | None = None


class ActivePayload(BaseModel):
    active: bool


class ConfigPayload(BaseModel):
    value: dict


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_item(a: Affirmation) -> AffirmationItem:
    return AffirmationItem(
        id=str(a.id),
        text=a.text,
        category=a.category,
        tags=a.tags or [],
        tone=a.tone,
        philosophy=a.philosophy,
        audience_type=a.audience_type,
        length_class=a.length_class,
        active=a.active,
        source_type=a.source_type,
        created_at=a.created_at.isoformat() if a.created_at else None,
        updated_at=a.updated_at.isoformat() if a.updated_at else None,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=list[AffirmationItem])
def list_affirmations(
    category: str | None = Query(None),
    tone: str | None = Query(None),
    audience_type: str | None = Query(None),
    active: bool | None = Query(None),
    q: str | None = Query(None),
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_permission(PERMISSION)
    query = sa_select(Affirmation)
    if category:
        query = query.where(Affirmation.category == category)
    if tone:
        query = query.where(Affirmation.tone == tone)
    if audience_type:
        query = query.where(Affirmation.audience_type == audience_type)
    if active is not None:
        query = query.where(Affirmation.active == active)
    if q:
        query = query.where(Affirmation.text.ilike(f"%{q}%"))
    query = query.order_by(Affirmation.created_at.desc())
    rows = db.execute(query).scalars().all()
    return [_to_item(a) for a in rows]


@router.post("", response_model=AffirmationItem, status_code=201)
def create_affirmation(
    payload: AffirmationCreatePayload,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_permission(PERMISSION)
    aff = Affirmation(
        text=payload.text,
        category=payload.category,
        tags=payload.tags,
        tone=payload.tone,
        philosophy=payload.philosophy,
        audience_type=payload.audience_type,
        length_class=payload.length_class,
        created_by=actor.member_id,
        updated_by=actor.member_id,
    )
    db.add(aff)
    db.commit()
    db.refresh(aff)
    return _to_item(aff)


@router.put("/{affirmation_id}", response_model=AffirmationItem)
def update_affirmation(
    affirmation_id: uuid.UUID,
    payload: AffirmationUpdatePayload,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_permission(PERMISSION)
    aff = db.get(Affirmation, affirmation_id)
    if not aff:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Affirmation not found")
    for field in ("text", "category", "tags", "tone", "philosophy", "audience_type", "length_class"):
        val = getattr(payload, field)
        if val is not None:
            setattr(aff, field, val)
    aff.updated_by = actor.member_id
    aff.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(aff)
    return _to_item(aff)


@router.patch("/{affirmation_id}/active", response_model=AffirmationItem)
def toggle_active(
    affirmation_id: uuid.UUID,
    payload: ActivePayload,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_permission(PERMISSION)
    aff = db.get(Affirmation, affirmation_id)
    if not aff:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Affirmation not found")
    aff.active = payload.active
    aff.updated_by = actor.member_id
    aff.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(aff)
    return _to_item(aff)


@router.get("/analytics")
def analytics(
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_permission(PERMISSION)
    return get_affirmation_analytics(db, actor.family_id)


@router.get("/config")
def get_config(
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_permission(PERMISSION)
    row = (
        db.query(HouseholdRule)
        .filter_by(family_id=actor.family_id, rule_key="affirmations.config")
        .first()
    )
    if row:
        return {"key": "affirmations.config", "value": row.rule_value}
    return {
        "key": "affirmations.config",
        "value": {
            "enabled": True,
            "cooldown_days": 3,
            "max_repeat_window_days": 30,
            "dynamic_generation_enabled": False,
            "moderation_required": False,
            "default_audience": "general",
            "weight_heart_boost": 1.5,
            "weight_preference_match": 1.3,
        },
    }


@router.put("/config")
def update_config(
    payload: ConfigPayload,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_permission(PERMISSION)
    row = (
        db.query(HouseholdRule)
        .filter_by(family_id=actor.family_id, rule_key="affirmations.config")
        .first()
    )
    if row:
        row.rule_value = payload.value
    else:
        row = HouseholdRule(
            family_id=actor.family_id,
            rule_key="affirmations.config",
            rule_value=payload.value,
        )
        db.add(row)
    db.commit()
    return {"key": "affirmations.config", "value": row.rule_value}

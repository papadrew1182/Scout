"""User-facing affirmation routes.

  GET  /affirmations/current       — select today's affirmation
  POST /affirmations/{id}/feedback — submit a reaction
  GET  /affirmations/preferences   — get preferences
  PUT  /affirmations/preferences   — update preferences
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import Actor, get_current_actor
from app.database import get_db
from app.models.affirmations import Affirmation, AffirmationFeedback
from app.models.access import MemberConfig
from app.services.affirmation_engine import select_affirmation

router = APIRouter(prefix="/affirmations", tags=["affirmations"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class AffirmationOut(BaseModel):
    id: str
    text: str
    category: str | None = None
    tone: str | None = None

class AffirmationDeliveryOut(BaseModel):
    affirmation: AffirmationOut | None
    delivered_at: str | None = None
    delivery_id: str | None = None

class FeedbackPayload(BaseModel):
    reaction_type: str
    context: str | None = None

class PreferencesPayload(BaseModel):
    preferred_tones: list[str] = []
    preferred_philosophies: list[str] = []
    excluded_themes: list[str] = []
    preferred_length: str = "short"

class PreferencesOut(BaseModel):
    enabled: bool = True
    preferred_tones: list[str] = []
    preferred_philosophies: list[str] = []
    excluded_themes: list[str] = []
    preferred_length: str = "short"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/current", response_model=AffirmationDeliveryOut)
def get_current(
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    result = select_affirmation(db, actor.member_id, actor.family_id)
    if result is None:
        return AffirmationDeliveryOut(affirmation=None)
    db.commit()
    return AffirmationDeliveryOut(**result)


@router.post("/{affirmation_id}/feedback", status_code=201)
def submit_feedback(
    affirmation_id: uuid.UUID,
    payload: FeedbackPayload,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    if payload.reaction_type not in ("heart", "thumbs_down", "skip", "reshow"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="reaction_type must be one of: heart, thumbs_down, skip, reshow",
        )
    aff = db.get(Affirmation, affirmation_id)
    if not aff:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Affirmation not found")

    fb = AffirmationFeedback(
        family_member_id=actor.member_id,
        affirmation_id=affirmation_id,
        reaction_type=payload.reaction_type,
        context=payload.context,
    )
    db.add(fb)
    db.commit()
    return {"status": "ok", "reaction_type": payload.reaction_type}


@router.get("/preferences", response_model=PreferencesOut)
def get_preferences(
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    row = (
        db.query(MemberConfig)
        .filter_by(family_member_id=actor.member_id, key="affirmations.preferences")
        .first()
    )
    if row:
        return PreferencesOut(**row.value)
    return PreferencesOut()


@router.put("/preferences", response_model=PreferencesOut)
def update_preferences(
    payload: PreferencesPayload,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    row = (
        db.query(MemberConfig)
        .filter_by(family_member_id=actor.member_id, key="affirmations.preferences")
        .first()
    )
    value = {
        "enabled": True,
        "preferred_tones": payload.preferred_tones,
        "preferred_philosophies": payload.preferred_philosophies,
        "excluded_themes": payload.excluded_themes,
        "preferred_length": payload.preferred_length,
    }
    if row:
        row.value = value
    else:
        row = MemberConfig(
            family_member_id=actor.member_id,
            key="affirmations.preferences",
            value=value,
            updated_by=actor.member_id,
        )
        db.add(row)
    db.commit()
    return PreferencesOut(**value)

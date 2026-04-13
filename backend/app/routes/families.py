import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import Actor, get_current_actor
from app.database import get_db
from app.models.foundation import Family, FamilyMember
from app.schemas.foundation import (
    FamilyAISettingsRead,
    FamilyAISettingsUpdate,
    FamilyCreate,
    FamilyMemberCreate,
    FamilyMemberLearningUpdate,
    FamilyMemberRead,
    FamilyRead,
)
from app.services import family_service

router = APIRouter(prefix="/families", tags=["families"])


@router.get("", response_model=list[FamilyRead])
def list_families(actor: Actor = Depends(get_current_actor), db: Session = Depends(get_db)):
    return family_service.list_families(db)


@router.post("", response_model=FamilyRead, status_code=201)
def create_family(payload: FamilyCreate, actor: Actor = Depends(get_current_actor), db: Session = Depends(get_db)):
    return family_service.create_family(db, payload)


@router.get("/{family_id}", response_model=FamilyRead)
def get_family(family_id: uuid.UUID, actor: Actor = Depends(get_current_actor), db: Session = Depends(get_db)):
    actor.require_family(family_id)
    return family_service.get_family(db, family_id)


@router.get("/{family_id}/members", response_model=list[FamilyMemberRead])
def list_members(family_id: uuid.UUID, actor: Actor = Depends(get_current_actor), db: Session = Depends(get_db)):
    actor.require_family(family_id)
    return family_service.list_members(db, family_id)


@router.post("/{family_id}/members", response_model=FamilyMemberRead, status_code=201)
def create_member(family_id: uuid.UUID, payload: FamilyMemberCreate, actor: Actor = Depends(get_current_actor), db: Session = Depends(get_db)):
    actor.require_family(family_id)
    return family_service.create_member(db, family_id, payload)


@router.get("/{family_id}/members/{member_id}", response_model=FamilyMemberRead)
def get_member(family_id: uuid.UUID, member_id: uuid.UUID, actor: Actor = Depends(get_current_actor), db: Session = Depends(get_db)):
    actor.require_family(family_id)
    return family_service.get_member(db, family_id, member_id)


# ---------------------------------------------------------------------------
# AI settings (adult-only) — gates general chat, homework help, home location
# ---------------------------------------------------------------------------

def _require_adult(actor: Actor, db: Session) -> None:
    """Gate write endpoints to adults only. Children can read settings but
    cannot change them."""
    member = db.get(FamilyMember, actor.member_id)
    if not member or member.role != "adult":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only adults can change this setting.",
        )


@router.get("/{family_id}/ai-settings", response_model=FamilyAISettingsRead)
def get_ai_settings(
    family_id: uuid.UUID,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_family(family_id)
    fam = db.get(Family, family_id)
    if not fam:
        raise HTTPException(status_code=404, detail="Family not found")
    return fam


@router.patch("/{family_id}/ai-settings", response_model=FamilyAISettingsRead)
def update_ai_settings(
    family_id: uuid.UUID,
    payload: FamilyAISettingsUpdate,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_family(family_id)
    _require_adult(actor, db)
    fam = db.get(Family, family_id)
    if not fam:
        raise HTTPException(status_code=404, detail="Family not found")
    if payload.allow_general_chat is not None:
        fam.allow_general_chat = payload.allow_general_chat
    if payload.allow_homework_help is not None:
        fam.allow_homework_help = payload.allow_homework_help
    if payload.home_location is not None:
        fam.home_location = payload.home_location.strip() or None
    db.commit()
    db.refresh(fam)
    return fam


@router.patch(
    "/{family_id}/members/{member_id}/learning",
    response_model=FamilyMemberRead,
)
def update_member_learning(
    family_id: uuid.UUID,
    member_id: uuid.UUID,
    payload: FamilyMemberLearningUpdate,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_family(family_id)
    _require_adult(actor, db)
    member = db.get(FamilyMember, member_id)
    if not member or member.family_id != family_id:
        raise HTTPException(status_code=404, detail="Member not found")
    if payload.grade_level is not None:
        member.grade_level = payload.grade_level.strip() or None
    if payload.learning_notes is not None:
        member.learning_notes = payload.learning_notes.strip() or None
    if payload.read_aloud_enabled is not None:
        member.read_aloud_enabled = bool(payload.read_aloud_enabled)
    db.commit()
    db.refresh(member)
    return member

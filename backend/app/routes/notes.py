import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth import Actor, get_current_actor
from app.database import get_db
from app.schemas.notes import NoteCreate, NoteRead, NoteUpdate
from app.services import notes_service

router = APIRouter(prefix="/families/{family_id}/notes", tags=["notes"])


@router.get("", response_model=list[NoteRead])
def list_notes(
    family_id: uuid.UUID,
    family_member_id: uuid.UUID | None = Query(None),
    category: str | None = Query(None),
    include_archived: bool = Query(False),
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_family(family_id)
    return notes_service.list_notes(
        db, family_id, family_member_id, category, include_archived
    )


@router.get("/recent", response_model=list[NoteRead])
def list_recent_notes(
    family_id: uuid.UUID,
    family_member_id: uuid.UUID | None = Query(None),
    limit: int = Query(10, ge=1, le=100),
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_family(family_id)
    return notes_service.list_recent_notes(db, family_id, family_member_id, limit)


@router.get("/search", response_model=list[NoteRead])
def search_notes(
    family_id: uuid.UUID,
    q: str = Query(..., min_length=1),
    family_member_id: uuid.UUID | None = Query(None),
    include_archived: bool = Query(False),
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_family(family_id)
    return notes_service.search_notes(
        db, family_id, q, family_member_id, include_archived
    )


@router.post("", response_model=NoteRead, status_code=201)
def create_note(family_id: uuid.UUID, payload: NoteCreate, actor: Actor = Depends(get_current_actor), db: Session = Depends(get_db)):
    actor.require_family(family_id)
    return notes_service.create_note(db, family_id, payload)


@router.get("/{note_id}", response_model=NoteRead)
def get_note(family_id: uuid.UUID, note_id: uuid.UUID, actor: Actor = Depends(get_current_actor), db: Session = Depends(get_db)):
    actor.require_family(family_id)
    return notes_service.get_note(db, family_id, note_id)


@router.patch("/{note_id}", response_model=NoteRead)
def update_note(
    family_id: uuid.UUID,
    note_id: uuid.UUID,
    payload: NoteUpdate,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_family(family_id)
    return notes_service.update_note(db, family_id, note_id, payload)


@router.post("/{note_id}/archive", response_model=NoteRead)
def archive_note(family_id: uuid.UUID, note_id: uuid.UUID, actor: Actor = Depends(get_current_actor), db: Session = Depends(get_db)):
    actor.require_family(family_id)
    return notes_service.archive_note(db, family_id, note_id)


@router.post("/{note_id}/unarchive", response_model=NoteRead)
def unarchive_note(family_id: uuid.UUID, note_id: uuid.UUID, actor: Actor = Depends(get_current_actor), db: Session = Depends(get_db)):
    actor.require_family(family_id)
    return notes_service.unarchive_note(db, family_id, note_id)


@router.delete("/{note_id}", status_code=204)
def delete_note(family_id: uuid.UUID, note_id: uuid.UUID, actor: Actor = Depends(get_current_actor), db: Session = Depends(get_db)):
    actor.require_family(family_id)
    notes_service.delete_note(db, family_id, note_id)

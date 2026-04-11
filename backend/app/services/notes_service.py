"""Notes service: minimal second-brain CRUD + retrieval helpers.

Search is ILIKE-based against title and body. No full-text indexing
or vector store yet.
"""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.notes import Note
from app.schemas.notes import NoteCreate, NoteUpdate
from app.services.tenant_guard import require_family, require_member_in_family


def list_notes(
    db: Session,
    family_id: uuid.UUID,
    family_member_id: uuid.UUID | None = None,
    category: str | None = None,
    include_archived: bool = False,
) -> list[Note]:
    require_family(db, family_id)
    stmt = select(Note).where(Note.family_id == family_id)
    if family_member_id:
        stmt = stmt.where(Note.family_member_id == family_member_id)
    if category:
        stmt = stmt.where(Note.category == category)
    if not include_archived:
        stmt = stmt.where(Note.is_archived.is_(False))
    stmt = stmt.order_by(Note.updated_at.desc())
    return list(db.scalars(stmt).all())


def list_recent_notes(
    db: Session,
    family_id: uuid.UUID,
    family_member_id: uuid.UUID | None = None,
    limit: int = 10,
) -> list[Note]:
    require_family(db, family_id)
    stmt = (
        select(Note)
        .where(Note.family_id == family_id)
        .where(Note.is_archived.is_(False))
    )
    if family_member_id:
        stmt = stmt.where(Note.family_member_id == family_member_id)
    stmt = stmt.order_by(Note.updated_at.desc()).limit(limit)
    return list(db.scalars(stmt).all())


def search_notes(
    db: Session,
    family_id: uuid.UUID,
    query: str,
    family_member_id: uuid.UUID | None = None,
    include_archived: bool = False,
) -> list[Note]:
    require_family(db, family_id)
    if not query or not query.strip():
        return []

    pattern = f"%{query.strip()}%"
    stmt = (
        select(Note)
        .where(Note.family_id == family_id)
        .where(or_(Note.title.ilike(pattern), Note.body.ilike(pattern)))
    )
    if family_member_id:
        stmt = stmt.where(Note.family_member_id == family_member_id)
    if not include_archived:
        stmt = stmt.where(Note.is_archived.is_(False))
    stmt = stmt.order_by(Note.updated_at.desc())
    return list(db.scalars(stmt).all())


def get_note(db: Session, family_id: uuid.UUID, note_id: uuid.UUID) -> Note:
    note = db.get(Note, note_id)
    if not note or note.family_id != family_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    return note


def create_note(db: Session, family_id: uuid.UUID, payload: NoteCreate) -> Note:
    require_member_in_family(db, family_id, payload.family_member_id)

    note = Note(
        family_id=family_id,
        family_member_id=payload.family_member_id,
        title=payload.title,
        body=payload.body,
        category=payload.category,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


def update_note(
    db: Session,
    family_id: uuid.UUID,
    note_id: uuid.UUID,
    payload: NoteUpdate,
) -> Note:
    note = get_note(db, family_id, note_id)
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(note, key, value)
    db.commit()
    db.refresh(note)
    return note


def archive_note(db: Session, family_id: uuid.UUID, note_id: uuid.UUID) -> Note:
    note = get_note(db, family_id, note_id)
    note.is_archived = True
    db.commit()
    db.refresh(note)
    return note


def unarchive_note(db: Session, family_id: uuid.UUID, note_id: uuid.UUID) -> Note:
    note = get_note(db, family_id, note_id)
    note.is_archived = False
    db.commit()
    db.refresh(note)
    return note


def delete_note(db: Session, family_id: uuid.UUID, note_id: uuid.UUID) -> None:
    note = get_note(db, family_id, note_id)
    db.delete(note)
    db.commit()

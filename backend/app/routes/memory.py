"""Parent-facing family memory management routes (Tier 5 F20).

All routes are adult-only. Memories are soft data: deletion is a
real DELETE, not a tombstone, because the status column already
provides the archival lifecycle."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.ai import memory as memory_module
from app.auth import Actor, get_current_actor
from app.database import get_db

router = APIRouter(prefix="/api/memory", tags=["memory"])


class MemoryCreate(BaseModel):
    memory_type: str = Field(min_length=1, max_length=40)
    scope: str = Field(default="family", pattern="^(parent|family|child)$")
    content: str = Field(min_length=1, max_length=2000)
    member_id: uuid.UUID | None = None
    tags: list[str] | None = None


class MemoryUpdate(BaseModel):
    memory_type: str | None = Field(default=None, max_length=40)
    scope: str | None = Field(default=None, pattern="^(parent|family|child)$")
    content: str | None = Field(default=None, max_length=2000)
    status: str | None = Field(default=None, pattern="^(proposed|active|archived)$")
    tags: list[str] | None = None


class MemoryRead(BaseModel):
    id: uuid.UUID
    family_id: uuid.UUID
    member_id: uuid.UUID | None
    memory_type: str
    scope: str
    content: str
    tags: list
    source_kind: str
    status: str
    confidence: float

    model_config = {"from_attributes": True}


@router.get("", response_model=list[MemoryRead])
def list_memories(
    status_filter: str | None = Query(
        None, alias="status", pattern="^(proposed|active|archived)$"
    ),
    memory_type: str | None = Query(None),
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_adult()
    rows = memory_module.list_family_memories(
        db,
        family_id=actor.family_id,
        status=status_filter,
        memory_type=memory_type,
    )
    return rows


@router.post("", response_model=MemoryRead)
def create_memory(
    payload: MemoryCreate,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_adult()
    row = memory_module.record_parent_memory(
        db,
        family_id=actor.family_id,
        memory_type=payload.memory_type,
        scope=payload.scope,
        content=payload.content,
        member_id=payload.member_id,
        tags=payload.tags,
    )
    db.commit()
    db.refresh(row)
    return row


@router.patch("/{memory_id}", response_model=MemoryRead)
def update_memory(
    memory_id: uuid.UUID,
    payload: MemoryUpdate,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_adult()
    row = memory_module.update_memory_content(
        db,
        memory_id,
        actor.family_id,
        content=payload.content,
        memory_type=payload.memory_type,
        scope=payload.scope,
        tags=payload.tags,
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found"
        )
    # Status transitions are separate so 'approve' / 'archive'
    # intent is explicit in the payload.
    if payload.status == "active":
        row = memory_module.approve_memory(db, memory_id, actor.family_id) or row
    elif payload.status == "archived":
        row = memory_module.archive_memory(db, memory_id, actor.family_id) or row
    db.commit()
    db.refresh(row)
    return row


@router.delete("/{memory_id}")
def delete_memory(
    memory_id: uuid.UUID,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_adult()
    ok = memory_module.delete_memory(db, memory_id, actor.family_id)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found"
        )
    db.commit()
    return {"deleted": True}

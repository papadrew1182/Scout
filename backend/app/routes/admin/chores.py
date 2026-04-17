"""Admin routes for chore routine management.

Endpoints (all scoped to actor's family, require chores.manage_config):

  GET  /admin/chores/routines
       — list all routine_templates for the family, grouped by member

  PUT  /admin/chores/routines/{member_id}
       — upsert a full routine set for a member (replaces all existing
         routines for that member with the submitted list)

  DELETE /admin/chores/routines/{routine_id}
       — delete a single routine template by id
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import Actor, get_current_actor
from app.database import get_db
from app.models.foundation import FamilyMember
from app.services import chores_canonical
from sqlalchemy import select

router = APIRouter(prefix="/admin/chores", tags=["admin-chores"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class RoutineItem(BaseModel):
    """A single routine template as returned by the API."""
    id: str
    routine_key: str
    label: str
    block_label: str
    recurrence: str
    owner_family_member_id: str | None


class MemberRoutinesGroup(BaseModel):
    """All routines for a single family member."""
    member_id: str
    member_name: str
    routines: list[RoutineItem]


class RoutineUpsertItem(BaseModel):
    """Shape of a single routine in the PUT body."""
    routine_key: str
    label: str
    recurrence: str = "daily"
    block_label: str = "Chores"


class RoutinesUpsertPayload(BaseModel):
    routines: list[RoutineUpsertItem]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_member(db: Session, member_id: uuid.UUID, actor: Actor) -> FamilyMember:
    member = db.get(FamilyMember, member_id)
    if not member or not member.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    if member.family_id != actor.family_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Member not in your family")
    return member


def _to_item(rt) -> RoutineItem:
    return RoutineItem(
        id=str(rt.id),
        routine_key=rt.routine_key,
        label=rt.label,
        block_label=rt.block_label,
        recurrence=rt.recurrence,
        owner_family_member_id=str(rt.owner_family_member_id) if rt.owner_family_member_id else None,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/routines", response_model=list[MemberRoutinesGroup])
def list_routines(
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    """Return all routine templates for the actor's family, grouped by member.

    Requires chores.manage_config.
    """
    actor.require_permission("chores.manage_config")

    templates = chores_canonical.get_family_chore_routines(db, actor.family_id)

    # Build member lookup
    members = list(
        db.scalars(
            select(FamilyMember)
            .where(FamilyMember.family_id == actor.family_id)
            .where(FamilyMember.is_active.is_(True))
        ).all()
    )
    member_map = {m.id: m for m in members}

    # Group by owner
    groups: dict[uuid.UUID | None, list] = {}
    for t in templates:
        key = t.owner_family_member_id
        groups.setdefault(key, []).append(_to_item(t))

    result = []
    for member_id_key, routines in groups.items():
        member = member_map.get(member_id_key)
        result.append(
            MemberRoutinesGroup(
                member_id=str(member_id_key) if member_id_key else "",
                member_name=member.first_name if member else "Unknown",
                routines=routines,
            )
        )
    return result


@router.put("/routines/{member_id}", response_model=MemberRoutinesGroup)
def upsert_member_routines(
    member_id: uuid.UUID,
    payload: RoutinesUpsertPayload,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    """Upsert all routines for a specific member.

    Inserts or updates each routine in the payload. Does NOT delete routines
    absent from the payload (use DELETE for removal). Requires chores.manage_config.
    """
    actor.require_permission("chores.manage_config")
    member = _resolve_member(db, member_id, actor)

    results = []
    for item in payload.routines:
        rt = chores_canonical.upsert_chore_routine(
            db,
            family_id=actor.family_id,
            member_id=member_id,
            routine_key=item.routine_key,
            label=item.label,
            recurrence=item.recurrence,
            block_label=item.block_label,
        )
        results.append(_to_item(rt))

    db.commit()
    return MemberRoutinesGroup(
        member_id=str(member.id),
        member_name=member.first_name,
        routines=results,
    )


@router.delete("/routines/{routine_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_routine(
    routine_id: uuid.UUID,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    """Delete a single routine template by id.

    Scoped to the actor's family. Returns 404 if not found.
    Requires chores.manage_config.
    """
    actor.require_permission("chores.manage_config")

    deleted = chores_canonical.delete_chore_routine(db, actor.family_id, routine_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Routine not found",
        )
    db.commit()

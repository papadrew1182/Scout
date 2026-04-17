"""Admin configuration API routes.

Endpoints:
  GET    /admin/config/family                   — all family config (requires admin.view_config)
  PUT    /admin/config/family/{key}             — upsert family config (requires admin.manage_config)
  DELETE /admin/config/family/{key}             — delete family config (requires admin.manage_config)
  GET    /admin/config/member/{member_id}       — all member config (requires admin.view_config)
  PUT    /admin/config/member/{member_id}/{key} — upsert member config (requires admin.manage_config)
  DELETE /admin/config/member/{member_id}/{key} — delete member config (requires admin.manage_config)
  GET    /admin/config/members/{key}            — all member_config rows matching key (requires admin.view_config)
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import Actor, get_current_actor
from app.database import get_db
from app.models.access import FamilyConfig, MemberConfig
from app.models.foundation import FamilyMember
from app.services.permissions import (
    delete_family_config,
    delete_member_config,
    set_family_config,
    set_member_config,
)

router = APIRouter(prefix="/admin/config", tags=["admin-config"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ConfigRow(BaseModel):
    key: str
    value: Any


class ConfigUpsertPayload(BaseModel):
    value: Any


# ---------------------------------------------------------------------------
# Family config endpoints
# ---------------------------------------------------------------------------

@router.get("/family", response_model=list[ConfigRow])
def get_family_config_all(
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    """Return all family_config rows for the actor's family.

    Requires admin.view_config.
    """
    actor.require_permission("admin.view_config")

    rows = db.scalars(
        select(FamilyConfig)
        .where(FamilyConfig.family_id == actor.family_id)
        .order_by(FamilyConfig.key)
    ).all()

    return [ConfigRow(key=row.key, value=row.value) for row in rows]


@router.put("/family/{key}", response_model=ConfigRow)
def upsert_family_config(
    key: str,
    payload: ConfigUpsertPayload,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    """Upsert a family_config key for the actor's family.

    Requires admin.manage_config.
    """
    actor.require_permission("admin.manage_config")

    row = set_family_config(
        db,
        family_id=actor.family_id,
        key=key,
        value=payload.value,
        updated_by=actor.member_id,
    )
    db.commit()
    return ConfigRow(key=row.key, value=row.value)


@router.delete("/family/{key}", status_code=status.HTTP_204_NO_CONTENT)
def delete_family_config_key(
    key: str,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    """Delete a family_config key for the actor's family.

    Requires admin.manage_config. Returns 404 if key does not exist.
    """
    actor.require_permission("admin.manage_config")

    deleted = delete_family_config(db, family_id=actor.family_id, key=key)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Config key not found: {key}")
    db.commit()


# ---------------------------------------------------------------------------
# Member config endpoints
# ---------------------------------------------------------------------------

def _resolve_member(db: Session, member_id: uuid.UUID, actor: Actor) -> FamilyMember:
    """Resolve and validate the target member. Must be active and in actor's family."""
    member = db.get(FamilyMember, member_id)
    if not member or not member.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    if member.family_id != actor.family_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Member is not in your family")
    return member


@router.get("/member/{member_id}", response_model=list[ConfigRow])
def get_member_config_all(
    member_id: uuid.UUID,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    """Return all member_config rows for the specified member.

    Requires admin.view_config AND the target member must be in the actor's family.
    """
    actor.require_permission("admin.view_config")
    _resolve_member(db, member_id, actor)

    rows = db.scalars(
        select(MemberConfig)
        .where(MemberConfig.family_member_id == member_id)
        .order_by(MemberConfig.key)
    ).all()

    return [ConfigRow(key=row.key, value=row.value) for row in rows]


@router.put("/member/{member_id}/{key}", response_model=ConfigRow)
def upsert_member_config(
    member_id: uuid.UUID,
    key: str,
    payload: ConfigUpsertPayload,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    """Upsert a member_config key for the specified member.

    Requires admin.manage_config AND the target member must be in the actor's family.
    """
    actor.require_permission("admin.manage_config")
    _resolve_member(db, member_id, actor)

    row = set_member_config(
        db,
        family_member_id=member_id,
        key=key,
        value=payload.value,
        updated_by=actor.member_id,
    )
    db.commit()
    return ConfigRow(key=row.key, value=row.value)


@router.delete("/member/{member_id}/{key}", status_code=status.HTTP_204_NO_CONTENT)
def delete_member_config_key(
    member_id: uuid.UUID,
    key: str,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    """Delete a member_config key for the specified member.

    Requires admin.manage_config AND the target member must be in the actor's family.
    Returns 404 if key does not exist.
    """
    actor.require_permission("admin.manage_config")
    _resolve_member(db, member_id, actor)

    deleted = delete_member_config(db, family_member_id=member_id, key=key)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Config key not found: {key}")
    db.commit()


# ---------------------------------------------------------------------------
# Bulk member config — all members, single key
# ---------------------------------------------------------------------------


class MemberConfigRow(BaseModel):
    member_id: str
    key: str
    value: Any


@router.get("/members/{key}", response_model=list[MemberConfigRow])
def get_all_member_config_for_key(
    key: str,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    """Return member_config rows for *all* active family members that have `key` set.

    Scoped to the actor's family. Requires admin.view_config.
    Returns an empty list (not 404) if no members have the key set.
    """
    actor.require_permission("admin.view_config")

    # Join through family_members to enforce family-scoping without a
    # subquery — keeps the result set tight.
    from app.models.foundation import FamilyMember as FM  # local import avoids circular
    rows = db.scalars(
        select(MemberConfig)
        .join(FM, FM.id == MemberConfig.family_member_id)
        .where(FM.family_id == actor.family_id)
        .where(FM.is_active.is_(True))
        .where(MemberConfig.key == key)
        .order_by(FM.first_name)
    ).all()

    return [
        MemberConfigRow(member_id=str(row.family_member_id), key=row.key, value=row.value)
        for row in rows
    ]

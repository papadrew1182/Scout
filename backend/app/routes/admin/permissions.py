"""Admin permissions API routes.

Endpoints:
  GET  /admin/permissions/registry           — all known permission keys (requires admin.view_permissions)
  GET  /admin/permissions/members            — per-member effective permissions (requires admin.view_permissions)
  PATCH /admin/permissions/members/{member_id} — update tier + overrides (requires admin.manage_permissions)
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
from app.models.access import RoleTier, RoleTierOverride
from app.models.foundation import FamilyMember
from app.services.permissions import resolve_effective_permissions

router = APIRouter(prefix="/admin/permissions", tags=["admin-permissions"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class PermissionRegistryEntry(BaseModel):
    key: str
    tiers_granting: list[str]


class MemberPermissionsRead(BaseModel):
    member_id: uuid.UUID
    first_name: str
    role: str
    tier_name: str | None
    effective_permissions: dict[str, bool]


class TierUpdatePayload(BaseModel):
    tier_name: str | None = None
    override_permissions: dict[str, bool] | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/registry", response_model=list[PermissionRegistryEntry])
def get_permission_registry(
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    """Return the union of all permission keys across all tiers.

    Each entry shows which tiers grant that permission by default.
    Requires admin.view_permissions.
    """
    actor.require_permission("admin.view_permissions")

    tiers = db.scalars(select(RoleTier)).all()

    # Build: key -> list of tier names that grant it
    registry: dict[str, list[str]] = {}
    for tier in tiers:
        if isinstance(tier.permissions, dict):
            for key, val in tier.permissions.items():
                if val:
                    if key not in registry:
                        registry[key] = []
                    registry[key].append(tier.name)

    return [
        PermissionRegistryEntry(key=key, tiers_granting=sorted(names))
        for key, names in sorted(registry.items())
    ]


@router.get("/members", response_model=list[MemberPermissionsRead])
def get_members_permissions(
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    """Return effective permissions for all active members in the actor's family.

    Requires admin.view_permissions.
    """
    actor.require_permission("admin.view_permissions")

    members = db.scalars(
        select(FamilyMember)
        .where(FamilyMember.family_id == actor.family_id)
        .where(FamilyMember.is_active.is_(True))
    ).all()

    results = []
    for member in members:
        # Get tier name if override row exists
        override = db.scalars(
            select(RoleTierOverride)
            .where(RoleTierOverride.family_member_id == member.id)
        ).first()

        tier_name: str | None = None
        if override:
            tier = db.get(RoleTier, override.role_tier_id)
            if tier:
                tier_name = tier.name

        effective = resolve_effective_permissions(db, member.id)
        results.append(
            MemberPermissionsRead(
                member_id=member.id,
                first_name=member.first_name,
                role=member.role,
                tier_name=tier_name,
                effective_permissions=effective,
            )
        )

    return results


@router.patch("/members/{member_id}", response_model=MemberPermissionsRead)
def update_member_permissions(
    member_id: uuid.UUID,
    payload: TierUpdatePayload,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    """Update a member's tier assignment and/or per-member permission overrides.

    Requires admin.manage_permissions. The target member must be in the
    actor's family.
    """
    actor.require_permission("admin.manage_permissions")

    # Verify target member is in the same family
    member = db.get(FamilyMember, member_id)
    if not member or not member.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    if member.family_id != actor.family_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Member is not in your family")

    # Resolve new tier if requested
    new_tier: RoleTier | None = None
    if payload.tier_name is not None:
        new_tier = db.scalars(
            select(RoleTier).where(RoleTier.name == payload.tier_name)
        ).first()
        if not new_tier:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown tier: {payload.tier_name}",
            )

    # Get or create override row
    override = db.scalars(
        select(RoleTierOverride)
        .where(RoleTierOverride.family_member_id == member_id)
    ).first()

    if override is None:
        if new_tier is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Member has no tier assigned. Provide tier_name to set one.",
            )
        override = RoleTierOverride(
            family_member_id=member_id,
            role_tier_id=new_tier.id,
            override_permissions={},
            override_behavior={},
        )
        db.add(override)
    else:
        if new_tier is not None:
            override.role_tier_id = new_tier.id

    if payload.override_permissions is not None:
        override.override_permissions = payload.override_permissions

    db.flush()

    # Invalidate the actor's own permission cache in case they modified themselves
    if member_id == actor.member_id:
        actor._permission_cache = None

    # Build response
    tier = db.get(RoleTier, override.role_tier_id)
    effective = resolve_effective_permissions(db, member_id)

    db.commit()

    return MemberPermissionsRead(
        member_id=member.id,
        first_name=member.first_name,
        role=member.role,
        tier_name=tier.name if tier else None,
        effective_permissions=effective,
    )

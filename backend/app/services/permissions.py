"""Permissions and configuration service.

Provides helpers for resolving effective permissions (tier + overrides),
and get/set helpers for family_config and member_config.

These are the canonical sources of truth for the permission model —
Actor.effective_permissions delegates to resolve_effective_permissions()
so the same logic is reusable from admin API routes.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.access import FamilyConfig, MemberConfig, RoleTier, RoleTierOverride
from app.models.foundation import FamilyMember

# Legacy role → tier name mapping used when no explicit tier override exists.
# Ensures backward compatibility: members created before the tier-assignment
# migration still get sensible permissions based on their legacy role field.
_ROLE_TIER_FALLBACK: dict[str, str] = {
    "adult": "admin",
    "child": "child",
}


def resolve_effective_permissions(db: Session, member_id: uuid.UUID) -> dict[str, bool]:
    """Resolve the effective permission dict for a family member.

    Algorithm:
      1. Look up the member's RoleTierOverride row (may not exist).
      2. If found, load the referenced RoleTier and get its permissions dict.
      3. Merge: start with tier permissions, then apply override_permissions
         on top (override wins on collision — can add OR revoke).
      4. If no override row exists, fall back to the member's legacy `role`
         field and load the matching tier by name (adult → admin, child → child).
         This ensures members without explicit tier assignments still get
         correct permissions during the Phase 2 migration period.

    Returns a flat dict {str: bool}. Only keys with True values grant access;
    callers should treat missing keys as False.
    """
    stmt = (
        select(RoleTierOverride, RoleTier)
        .join(RoleTier, RoleTierOverride.role_tier_id == RoleTier.id)
        .where(RoleTierOverride.family_member_id == member_id)
    )
    row = db.execute(stmt).first()

    if row is None:
        # No explicit tier assignment — fall back to role-based tier lookup.
        member = db.get(FamilyMember, member_id)
        if member is None:
            return {}
        tier_name = _ROLE_TIER_FALLBACK.get(member.role)
        if tier_name is None:
            return {}
        tier = db.scalars(select(RoleTier).where(RoleTier.name == tier_name)).first()
        if tier is None:
            return {}
        merged: dict[str, bool] = {}
        if isinstance(tier.permissions, dict):
            for k, v in tier.permissions.items():
                merged[k] = bool(v)
        return merged

    override, tier = row

    # Merge: tier base permissions, then layer per-member overrides on top.
    merged = {}
    if isinstance(tier.permissions, dict):
        for k, v in tier.permissions.items():
            merged[k] = bool(v)

    if isinstance(override.override_permissions, dict):
        for k, v in override.override_permissions.items():
            merged[k] = bool(v)

    return merged


# ---------------------------------------------------------------------------
# family_config helpers
# ---------------------------------------------------------------------------

def get_family_config(
    db: Session,
    family_id: uuid.UUID,
    key: str,
    default=None,
):
    """Return the value for a family config key, or default if not set."""
    row = db.scalars(
        select(FamilyConfig)
        .where(FamilyConfig.family_id == family_id)
        .where(FamilyConfig.key == key)
    ).first()
    if row is None:
        return default
    return row.value


def set_family_config(
    db: Session,
    family_id: uuid.UUID,
    key: str,
    value,
    updated_by: uuid.UUID | None = None,
) -> FamilyConfig:
    """Upsert a family config key/value pair.

    Creates the row if it doesn't exist; updates value + updated_by if it does.
    Caller is responsible for db.commit().
    """
    row = db.scalars(
        select(FamilyConfig)
        .where(FamilyConfig.family_id == family_id)
        .where(FamilyConfig.key == key)
    ).first()

    if row is None:
        row = FamilyConfig(
            family_id=family_id,
            key=key,
            value=value,
            updated_by=updated_by,
        )
        db.add(row)
    else:
        row.value = value
        row.updated_by = updated_by

    db.flush()
    return row


def delete_family_config(
    db: Session,
    family_id: uuid.UUID,
    key: str,
) -> bool:
    """Delete a family config row. Returns True if deleted, False if not found."""
    row = db.scalars(
        select(FamilyConfig)
        .where(FamilyConfig.family_id == family_id)
        .where(FamilyConfig.key == key)
    ).first()

    if row is None:
        return False

    db.delete(row)
    db.flush()
    return True


# ---------------------------------------------------------------------------
# member_config helpers
# ---------------------------------------------------------------------------

def get_member_config(
    db: Session,
    family_member_id: uuid.UUID,
    key: str,
    default=None,
):
    """Return the value for a member config key, or default if not set."""
    row = db.scalars(
        select(MemberConfig)
        .where(MemberConfig.family_member_id == family_member_id)
        .where(MemberConfig.key == key)
    ).first()
    if row is None:
        return default
    return row.value


def set_member_config(
    db: Session,
    family_member_id: uuid.UUID,
    key: str,
    value,
    updated_by: uuid.UUID | None = None,
) -> MemberConfig:
    """Upsert a member config key/value pair.

    Creates the row if it doesn't exist; updates value + updated_by if it does.
    Caller is responsible for db.commit().
    """
    row = db.scalars(
        select(MemberConfig)
        .where(MemberConfig.family_member_id == family_member_id)
        .where(MemberConfig.key == key)
    ).first()

    if row is None:
        row = MemberConfig(
            family_member_id=family_member_id,
            key=key,
            value=value,
            updated_by=updated_by,
        )
        db.add(row)
    else:
        row.value = value
        row.updated_by = updated_by

    db.flush()
    return row


def delete_member_config(
    db: Session,
    family_member_id: uuid.UUID,
    key: str,
) -> bool:
    """Delete a member config row. Returns True if deleted, False if not found."""
    row = db.scalars(
        select(MemberConfig)
        .where(MemberConfig.family_member_id == family_member_id)
        .where(MemberConfig.key == key)
    ).first()

    if row is None:
        return False

    db.delete(row)
    db.flush()
    return True

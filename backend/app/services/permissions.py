"""Permissions and configuration service.

Provides helpers for resolving effective permissions (tier + overrides),
and get/set helpers for family_config and member_config.

These are the canonical sources of truth for the permission model —
Actor.effective_permissions delegates to resolve_effective_permissions()
so the same logic is reusable from admin API routes.

Permission architecture (post-034 reconciliation):
  - Canonical permissions live in scout.permissions (keyed by permission_key).
  - Tier → permission mapping lives in scout.role_tier_permissions (join table).
  - public.role_tiers.permissions (JSONB) is retired and always empty.
  - Per-member overrides remain in public.role_tier_overrides.override_permissions
    (JSONB, can add or revoke individual keys on top of the tier grant).
"""

from __future__ import annotations

import uuid

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.access import FamilyConfig, MemberConfig, RoleTier, RoleTierOverride
from app.models.foundation import FamilyMember

# Legacy role → canonical tier name mapping used when no explicit tier override
# exists.  Ensures backward compatibility: members created before the
# tier-assignment migration still get sensible permissions based on their
# legacy role field.  Lowercase tier names from PR #15 have been deleted by
# migration 034; the fallback now targets the 022 UPPERCASE canonical names.
_ROLE_TIER_FALLBACK: dict[str, str] = {
    "adult": "PRIMARY_PARENT",
    "child": "CHILD",
}


def resolve_effective_permissions(db: Session, member_id: uuid.UUID) -> dict[str, bool]:
    """Resolve the effective permission dict for a family member.

    Algorithm:
      1. Look up the member's RoleTierOverride row (may not exist).
      2. If found, use the referenced role_tier_id to query
         scout.role_tier_permissions JOIN scout.permissions — the normalized
         join table is now the sole source of truth for tier grants.
         (The JSONB permissions column on role_tiers is retired and empty.)
      3. Merge: start with normalized tier permissions, then apply
         override_permissions JSONB on top (overrides win on collision —
         can add OR revoke individual keys).
      4. If no override row exists, fall back to the member's legacy `role`
         field, look up the canonical tier by name (adult → PRIMARY_PARENT,
         child → CHILD), and query the same normalized join table.

    Returns a flat dict {str: bool}.  Only keys present in the dict matter;
    callers should treat missing keys as False.
    """
    # --- Resolve override row (if any) ---
    override = db.scalars(
        select(RoleTierOverride).where(RoleTierOverride.family_member_id == member_id)
    ).first()

    if override is not None:
        tier_id = override.role_tier_id
    else:
        # Fall back to role-based canonical tier lookup.
        member = db.get(FamilyMember, member_id)
        if member is None:
            return {}
        tier_name = _ROLE_TIER_FALLBACK.get(member.role)
        if tier_name is None:
            return {}
        tier = db.scalars(select(RoleTier).where(RoleTier.name == tier_name)).first()
        if tier is None:
            return {}
        tier_id = tier.id

    # --- Query normalized permissions for the resolved tier ---
    rows = db.execute(
        text(
            """
            SELECT p.permission_key
            FROM scout.role_tier_permissions rtp
            JOIN scout.permissions p ON p.id = rtp.permission_id
            WHERE rtp.role_tier_id = :tier_id
            """
        ),
        {"tier_id": tier_id},
    ).all()

    merged: dict[str, bool] = {row.permission_key: True for row in rows}

    # --- Layer per-member overrides on top ---
    if override is not None and isinstance(override.override_permissions, dict):
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

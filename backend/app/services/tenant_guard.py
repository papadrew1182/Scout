"""Shared tenant-boundary enforcement helpers.

Every tenant-sensitive service should use these instead of writing inline
family_id checks. This keeps the tenant boundary in one place.
"""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.foundation import Family, FamilyMember


def require_family(db: Session, family_id: uuid.UUID) -> Family:
    family = db.get(Family, family_id)
    if not family:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Family not found")
    return family


def require_member_in_family(db: Session, family_id: uuid.UUID, member_id: uuid.UUID) -> FamilyMember:
    member = db.get(FamilyMember, member_id)
    if not member or member.family_id != family_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Family member not found in this family")
    if not member.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Family member is inactive")
    return member


def get_active_children(db: Session, family_id: uuid.UUID) -> list[FamilyMember]:
    stmt = (
        select(FamilyMember)
        .where(FamilyMember.family_id == family_id)
        .where(FamilyMember.role == "child")
        .where(FamilyMember.is_active.is_(True))
    )
    return list(db.scalars(stmt).all())


def validate_family_id_matches_member(db: Session, family_id: uuid.UUID, member_id: uuid.UUID) -> None:
    """Enforce denormalized family_id consistency on write paths."""
    member = db.get(FamilyMember, member_id)
    if not member or member.family_id != family_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="family_id does not match the member's family",
        )

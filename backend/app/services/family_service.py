import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.foundation import Family, FamilyMember
from app.schemas.foundation import FamilyCreate, FamilyMemberCreate
from app.services.tenant_guard import require_family, require_member_in_family


def list_families(db: Session) -> list[Family]:
    return list(db.scalars(select(Family)).all())


def get_family(db: Session, family_id: uuid.UUID) -> Family:
    return require_family(db, family_id)


def create_family(db: Session, payload: FamilyCreate) -> Family:
    family = Family(name=payload.name, timezone=payload.timezone)
    db.add(family)
    db.commit()
    db.refresh(family)
    return family


def list_members(db: Session, family_id: uuid.UUID) -> list[FamilyMember]:
    require_family(db, family_id)
    stmt = select(FamilyMember).where(FamilyMember.family_id == family_id)
    return list(db.scalars(stmt).all())


def get_member(db: Session, family_id: uuid.UUID, member_id: uuid.UUID) -> FamilyMember:
    return require_member_in_family(db, family_id, member_id)


def create_member(db: Session, family_id: uuid.UUID, payload: FamilyMemberCreate) -> FamilyMember:
    require_family(db, family_id)
    member = FamilyMember(
        family_id=family_id,
        first_name=payload.first_name,
        last_name=payload.last_name,
        role=payload.role,
        birthdate=payload.birthdate,
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return member

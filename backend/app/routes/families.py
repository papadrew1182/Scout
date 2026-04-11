import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.foundation import FamilyCreate, FamilyMemberCreate, FamilyMemberRead, FamilyRead
from app.services import family_service

router = APIRouter(prefix="/families", tags=["families"])


@router.get("", response_model=list[FamilyRead])
def list_families(db: Session = Depends(get_db)):
    return family_service.list_families(db)


@router.post("", response_model=FamilyRead, status_code=201)
def create_family(payload: FamilyCreate, db: Session = Depends(get_db)):
    return family_service.create_family(db, payload)


@router.get("/{family_id}", response_model=FamilyRead)
def get_family(family_id: uuid.UUID, db: Session = Depends(get_db)):
    return family_service.get_family(db, family_id)


@router.get("/{family_id}/members", response_model=list[FamilyMemberRead])
def list_members(family_id: uuid.UUID, db: Session = Depends(get_db)):
    return family_service.list_members(db, family_id)


@router.post("/{family_id}/members", response_model=FamilyMemberRead, status_code=201)
def create_member(family_id: uuid.UUID, payload: FamilyMemberCreate, db: Session = Depends(get_db)):
    return family_service.create_member(db, family_id, payload)


@router.get("/{family_id}/members/{member_id}", response_model=FamilyMemberRead)
def get_member(family_id: uuid.UUID, member_id: uuid.UUID, db: Session = Depends(get_db)):
    return family_service.get_member(db, family_id, member_id)

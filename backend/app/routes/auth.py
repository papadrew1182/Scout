"""Authentication routes: login, logout, current user, account bootstrap."""

import uuid

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import Actor, get_current_actor
from app.database import get_db
from app.models.foundation import FamilyMember
from app.services import auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class LoginRequest(BaseModel):
    email: str = Field(min_length=1)
    password: str = Field(min_length=1)


class LoginResponse(BaseModel):
    token: str
    expires_at: str
    member: dict


class MeResponse(BaseModel):
    member_id: str
    family_id: str
    first_name: str
    last_name: str | None
    role: str
    family_name: str


class CreateAccountRequest(BaseModel):
    family_member_id: uuid.UUID
    email: str = Field(min_length=1)
    password: str = Field(min_length=6)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    result = auth_service.login(db, body.email, body.password)
    return LoginResponse(**result)


@router.post("/logout")
def logout(request: Request, db: Session = Depends(get_db)):
    """Invalidate the current session."""
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        auth_service.logout(db, auth[7:])
    return {"status": "ok"}


@router.get("/me", response_model=MeResponse)
def get_me(actor: Actor = Depends(get_current_actor)):
    return MeResponse(
        member_id=str(actor.member_id),
        family_id=str(actor.family_id),
        first_name=actor.member.first_name,
        last_name=actor.member.last_name,
        role=actor.role,
        family_name=actor.family.name,
    )


@router.post("/accounts", status_code=201)
def create_account(
    body: CreateAccountRequest,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    """Bootstrap a user account for a family member. Adults only, same family."""
    actor.require_adult()
    target = db.get(FamilyMember, body.family_member_id)
    if target:
        actor.require_family(target.family_id)
    account = auth_service.create_account(
        db, body.family_member_id, body.email, body.password,
    )
    return {"id": str(account.id), "email": account.email}

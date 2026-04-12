"""Authentication routes: login, logout, me, password, sessions, accounts, bootstrap."""

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


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=6)


class AdminResetPasswordRequest(BaseModel):
    account_id: uuid.UUID
    new_password: str = Field(min_length=6)


class BootstrapRequest(BaseModel):
    email: str = Field(min_length=1)
    password: str = Field(min_length=6)


# ---------------------------------------------------------------------------
# Public routes
# ---------------------------------------------------------------------------


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"
    result = auth_service.login(db, body.email, body.password, client_ip=client_ip)
    return LoginResponse(**result)


@router.post("/bootstrap")
def bootstrap(body: BootstrapRequest, db: Session = Depends(get_db)):
    """Create the first account when no accounts exist.
    Only available when SCOUT_ENABLE_BOOTSTRAP=true and zero accounts exist."""
    from app.config import settings
    if not settings.enable_bootstrap:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bootstrap is disabled")
    return auth_service.bootstrap_first_account(db, body.email, body.password)


# ---------------------------------------------------------------------------
# Authenticated routes — current user
# ---------------------------------------------------------------------------


@router.post("/logout")
def logout(request: Request, db: Session = Depends(get_db)):
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


@router.post("/password/change")
def change_password(
    body: ChangePasswordRequest,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    auth_service.change_password(db, actor.account.id, body.current_password, body.new_password)
    return {"status": "ok"}


@router.get("/sessions")
def list_my_sessions(
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    return auth_service.list_sessions(db, actor.account.id)


@router.post("/sessions/{session_id}/revoke")
def revoke_session(
    session_id: uuid.UUID,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    auth_service.revoke_session(db, actor.account.id, session_id)
    return {"status": "ok"}


@router.post("/sessions/revoke-others")
def revoke_other_sessions(
    request: Request,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    token = ""
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        token = auth[7:]
    count = auth_service.revoke_other_sessions(db, actor.account.id, token)
    return {"status": "ok", "revoked": count}


# ---------------------------------------------------------------------------
# Admin routes — adults only, same family
# ---------------------------------------------------------------------------


@router.get("/accounts")
def list_accounts(
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    """List family members with account status. Adults only."""
    actor.require_adult()
    return auth_service.list_family_accounts(db, actor.family_id)


@router.post("/accounts", status_code=201)
def create_account(
    body: CreateAccountRequest,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    """Create a user account for a family member. Adults only, same family."""
    actor.require_adult()
    target = db.get(FamilyMember, body.family_member_id)
    if target:
        actor.require_family(target.family_id)
    account = auth_service.create_account(db, body.family_member_id, body.email, body.password)
    return {"id": str(account.id), "email": account.email}


@router.post("/accounts/{account_id}/reset-password")
def admin_reset_password(
    account_id: uuid.UUID,
    body: AdminResetPasswordRequest,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    """Reset a family member's password. Adults only."""
    actor.require_adult()
    from app.models.foundation import UserAccount
    target_account = db.get(UserAccount, account_id)
    if target_account:
        target_member = db.get(FamilyMember, target_account.family_member_id)
        if target_member:
            actor.require_family(target_member.family_id)
    auth_service.admin_reset_password(db, actor.member_id, account_id, body.new_password)
    return {"status": "ok"}


@router.post("/accounts/{account_id}/deactivate")
def deactivate_account(
    account_id: uuid.UUID,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    """Deactivate an account and revoke all sessions. Adults only."""
    actor.require_adult()
    auth_service.deactivate_account(db, account_id)
    return {"status": "ok"}


@router.post("/accounts/{account_id}/activate")
def activate_account(
    account_id: uuid.UUID,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    """Reactivate a deactivated account. Adults only."""
    actor.require_adult()
    auth_service.activate_account(db, account_id)
    return {"status": "ok"}


@router.post("/accounts/{account_id}/revoke-sessions")
def revoke_account_sessions(
    account_id: uuid.UUID,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    """Revoke all sessions for a family member's account. Adults only."""
    actor.require_adult()
    count = auth_service.revoke_account_sessions(db, account_id)
    return {"status": "ok", "revoked": count}

"""Authentication and session management.

Provides login, logout, session lookup, and current-actor resolution.
Uses the existing UserAccount and Session models from foundation.
"""

import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from app.models.foundation import Family, FamilyMember, Session, UserAccount

logger = logging.getLogger("scout.auth")

SESSION_TTL_HOURS = 72  # 3 days


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ---------------------------------------------------------------------------
# Login / logout
# ---------------------------------------------------------------------------


def login(db: DBSession, email: str, password: str) -> dict:
    """Authenticate by email + password. Returns session token + actor info."""
    account = db.scalars(
        select(UserAccount)
        .where(UserAccount.email == email)
        .where(UserAccount.is_active.is_(True))
    ).first()
    if not account or not account.password_hash:
        logger.warning("login_failed email=%s reason=not_found", email)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    if not verify_password(password, account.password_hash):
        logger.warning("login_failed email=%s reason=bad_password", email)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    member = db.get(FamilyMember, account.family_member_id)
    if not member or not member.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is linked to an inactive member")

    # Create session
    token = secrets.token_urlsafe(48)
    expires = datetime.now(timezone.utc) + timedelta(hours=SESSION_TTL_HOURS)
    session = Session(
        user_account_id=account.id,
        token=token,
        expires_at=expires,
    )
    db.add(session)
    account.last_login_at = datetime.now(timezone.utc)
    db.commit()

    logger.info("login_success email=%s member=%s family=%s", email, member.id, member.family_id)

    return {
        "token": token,
        "expires_at": expires.isoformat(),
        "member": {
            "id": str(member.id),
            "family_id": str(member.family_id),
            "first_name": member.first_name,
            "last_name": member.last_name,
            "role": member.role,
        },
    }


def logout(db: DBSession, token: str) -> None:
    """Invalidate a session token by deleting it."""
    session = db.scalars(
        select(Session).where(Session.token == token)
    ).first()
    if session:
        db.delete(session)
        db.commit()
        logger.info("logout session=%s", session.id)


# ---------------------------------------------------------------------------
# Session resolution
# ---------------------------------------------------------------------------


def resolve_session(db: DBSession, token: str) -> tuple[UserAccount, FamilyMember, Family]:
    """Resolve a bearer token to (account, member, family). Raises 401 on failure."""
    session = db.scalars(
        select(Session).where(Session.token == token)
    ).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session")

    if session.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        db.delete(session)
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")

    account = db.get(UserAccount, session.user_account_id)
    if not account or not account.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account inactive")

    member = db.get(FamilyMember, account.family_member_id)
    if not member or not member.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Member inactive")

    family = db.get(Family, member.family_id)
    if not family:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Family not found")

    return account, member, family


# ---------------------------------------------------------------------------
# Account bootstrap (for private launch seeding)
# ---------------------------------------------------------------------------


def create_account(
    db: DBSession,
    family_member_id: uuid.UUID,
    email: str,
    password: str,
    is_primary: bool = True,
) -> UserAccount:
    """Create an email/password account for an existing family member."""
    member = db.get(FamilyMember, family_member_id)
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Family member not found")

    existing = db.scalars(
        select(UserAccount).where(UserAccount.email == email)
    ).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    account = UserAccount(
        family_member_id=family_member_id,
        email=email,
        auth_provider="email",
        password_hash=hash_password(password),
        is_primary=is_primary,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    logger.info("account_created email=%s member=%s", email, family_member_id)
    return account

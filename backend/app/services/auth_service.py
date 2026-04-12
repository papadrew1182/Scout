"""Authentication and session management.

Provides login, logout, session lookup, current-actor resolution,
password management, session management, rate limiting, and bootstrap.
Uses the existing UserAccount and Session models from foundation.
"""

import logging
import secrets
import time
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DBSession

from app.models.foundation import Family, FamilyMember, Session, UserAccount

logger = logging.getLogger("scout.auth")

SESSION_TTL_HOURS = 72


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ---------------------------------------------------------------------------
# Login rate limiting (in-memory, lightweight)
# ---------------------------------------------------------------------------

_login_attempts: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT_WINDOW = 300  # 5 minutes
RATE_LIMIT_MAX = 10  # max attempts per window


def _check_rate_limit(key: str) -> None:
    """Raise 429 if too many login attempts for this key."""
    now = time.monotonic()
    attempts = _login_attempts[key]
    # Prune old entries
    _login_attempts[key] = [t for t in attempts if now - t < RATE_LIMIT_WINDOW]
    if len(_login_attempts[key]) >= RATE_LIMIT_MAX:
        logger.warning("rate_limit_hit key=%s", key)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Try again in a few minutes.",
        )


def _record_attempt(key: str) -> None:
    _login_attempts[key].append(time.monotonic())


# ---------------------------------------------------------------------------
# Login / logout
# ---------------------------------------------------------------------------


def login(db: DBSession, email: str, password: str, client_ip: str = "unknown") -> dict:
    """Authenticate by email + password. Returns session token + actor info."""
    _check_rate_limit(f"ip:{client_ip}")
    _check_rate_limit(f"email:{email.lower()}")

    account = db.scalars(
        select(UserAccount)
        .where(UserAccount.email == email)
        .where(UserAccount.is_active.is_(True))
    ).first()
    if not account or not account.password_hash:
        _record_attempt(f"ip:{client_ip}")
        _record_attempt(f"email:{email.lower()}")
        logger.warning("login_failed email=%s reason=not_found ip=%s", email, client_ip)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    if not verify_password(password, account.password_hash):
        _record_attempt(f"ip:{client_ip}")
        _record_attempt(f"email:{email.lower()}")
        logger.warning("login_failed email=%s reason=bad_password ip=%s", email, client_ip)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    member = db.get(FamilyMember, account.family_member_id)
    if not member or not member.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is linked to an inactive member")

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
    session = db.scalars(select(Session).where(Session.token == token)).first()
    if session:
        db.delete(session)
        db.commit()
        logger.info("logout session=%s", session.id)


# ---------------------------------------------------------------------------
# Session resolution
# ---------------------------------------------------------------------------


def resolve_session(db: DBSession, token: str) -> tuple[UserAccount, FamilyMember, Family]:
    session = db.scalars(select(Session).where(Session.token == token)).first()
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
# Password management
# ---------------------------------------------------------------------------


def change_password(db: DBSession, account_id: uuid.UUID, current_password: str, new_password: str) -> None:
    """Authenticated user changes own password. Validates current password first."""
    account = db.get(UserAccount, account_id)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    if not account.password_hash or not verify_password(current_password, account.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Current password is incorrect")
    if len(new_password) < 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 6 characters")

    account.password_hash = hash_password(new_password)
    # Invalidate other sessions
    _revoke_other_sessions(db, account.id, exclude_token=None)
    db.commit()
    logger.info("password_changed account=%s", account_id)


def admin_reset_password(
    db: DBSession,
    admin_member_id: uuid.UUID,
    target_account_id: uuid.UUID,
    new_password: str,
) -> None:
    """Adult admin resets another family member's password."""
    account = db.get(UserAccount, target_account_id)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    if len(new_password) < 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 6 characters")

    account.password_hash = hash_password(new_password)
    # Revoke all sessions for the target account
    _revoke_all_sessions(db, account.id)
    db.commit()
    logger.info("admin_password_reset admin=%s target_account=%s", admin_member_id, target_account_id)


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------


def list_sessions(db: DBSession, account_id: uuid.UUID) -> list[dict]:
    now = datetime.now(timezone.utc)
    sessions = list(db.scalars(
        select(Session)
        .where(Session.user_account_id == account_id)
        .where(Session.expires_at > now)
        .order_by(Session.created_at.desc())
    ).all())
    return [
        {
            "id": str(s.id),
            "created_at": s.created_at.isoformat(),
            "expires_at": s.expires_at.isoformat(),
        }
        for s in sessions
    ]


def revoke_session(db: DBSession, account_id: uuid.UUID, session_id: uuid.UUID) -> None:
    session = db.get(Session, session_id)
    if not session or session.user_account_id != account_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    db.delete(session)
    db.commit()
    logger.info("session_revoked account=%s session=%s", account_id, session_id)


def revoke_other_sessions(db: DBSession, account_id: uuid.UUID, current_token: str) -> int:
    """Revoke all sessions except the current one. Returns count revoked."""
    return _revoke_other_sessions(db, account_id, exclude_token=current_token)


def _revoke_other_sessions(db: DBSession, account_id: uuid.UUID, exclude_token: str | None) -> int:
    sessions = list(db.scalars(
        select(Session).where(Session.user_account_id == account_id)
    ).all())
    count = 0
    for s in sessions:
        if exclude_token and s.token == exclude_token:
            continue
        db.delete(s)
        count += 1
    db.flush()
    return count


def _revoke_all_sessions(db: DBSession, account_id: uuid.UUID) -> int:
    sessions = list(db.scalars(
        select(Session).where(Session.user_account_id == account_id)
    ).all())
    for s in sessions:
        db.delete(s)
    db.flush()
    return len(sessions)


# ---------------------------------------------------------------------------
# Account management (admin)
# ---------------------------------------------------------------------------


def create_account(
    db: DBSession,
    family_member_id: uuid.UUID,
    email: str,
    password: str,
    is_primary: bool = True,
) -> UserAccount:
    member = db.get(FamilyMember, family_member_id)
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Family member not found")
    if len(password) < 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 6 characters")

    existing = db.scalars(select(UserAccount).where(UserAccount.email == email)).first()
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


def list_family_accounts(db: DBSession, family_id: uuid.UUID) -> list[dict]:
    """List all members with their account status for a family."""
    members = list(db.scalars(
        select(FamilyMember)
        .where(FamilyMember.family_id == family_id)
        .order_by(FamilyMember.role, FamilyMember.first_name)
    ).all())

    result = []
    for m in members:
        accounts = list(db.scalars(
            select(UserAccount).where(UserAccount.family_member_id == m.id)
        ).all())
        account = accounts[0] if accounts else None
        session_count = 0
        if account:
            now = datetime.now(timezone.utc)
            session_count = db.scalar(
                select(func.count()).select_from(Session)
                .where(Session.user_account_id == account.id)
                .where(Session.expires_at > now)
            ) or 0
        result.append({
            "member_id": str(m.id),
            "first_name": m.first_name,
            "last_name": m.last_name,
            "role": m.role,
            "is_active": m.is_active,
            "has_account": account is not None,
            "account_id": str(account.id) if account else None,
            "email": account.email if account else None,
            "account_active": account.is_active if account else None,
            "last_login_at": account.last_login_at.isoformat() if account and account.last_login_at else None,
            "active_sessions": session_count,
        })
    return result


def deactivate_account(db: DBSession, account_id: uuid.UUID) -> None:
    account = db.get(UserAccount, account_id)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    account.is_active = False
    _revoke_all_sessions(db, account.id)
    db.commit()
    logger.info("account_deactivated account=%s", account_id)


def activate_account(db: DBSession, account_id: uuid.UUID) -> None:
    account = db.get(UserAccount, account_id)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    account.is_active = True
    db.commit()
    logger.info("account_activated account=%s", account_id)


def revoke_account_sessions(db: DBSession, account_id: uuid.UUID) -> int:
    """Admin revokes all sessions for a managed account."""
    account = db.get(UserAccount, account_id)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    count = _revoke_all_sessions(db, account.id)
    db.commit()
    logger.info("admin_sessions_revoked account=%s count=%d", account_id, count)
    return count


# ---------------------------------------------------------------------------
# Bootstrap (first account creation)
# ---------------------------------------------------------------------------


def bootstrap_first_account(db: DBSession, email: str, password: str) -> dict:
    """Create the first admin account. Only works when zero accounts exist."""
    existing_count = db.scalar(select(func.count()).select_from(UserAccount)) or 0
    if existing_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bootstrap not available: accounts already exist",
        )

    # Find the first adult member
    adult = db.scalars(
        select(FamilyMember)
        .where(FamilyMember.role == "adult")
        .where(FamilyMember.is_active.is_(True))
        .order_by(FamilyMember.created_at)
    ).first()
    if not adult:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No adult family member found. Seed family data first.",
        )

    account = create_account(db, adult.id, email, password)
    logger.info("bootstrap_complete email=%s member=%s", email, adult.id)
    return {
        "account_id": str(account.id),
        "member_id": str(adult.id),
        "email": email,
        "first_name": adult.first_name,
        "message": "First account created. Sign in to manage other accounts.",
    }

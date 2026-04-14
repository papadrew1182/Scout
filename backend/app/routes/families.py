import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import Actor, get_current_actor
from app.database import get_db
from app.models.foundation import Family, FamilyMember, UserAccount
from app.schemas.foundation import (
    FamilyAISettingsRead,
    FamilyAISettingsUpdate,
    FamilyCreate,
    FamilyMemberCoreUpdate,
    FamilyMemberCreate,
    FamilyMemberLearningUpdate,
    FamilyMemberRead,
    FamilyRead,
    UserAccountCreate,
    UserAccountRead,
    UserAccountUpdate,
)
from app.services import family_service
from app.services.auth_service import hash_password

router = APIRouter(prefix="/families", tags=["families"])


@router.get("", response_model=list[FamilyRead])
def list_families(actor: Actor = Depends(get_current_actor), db: Session = Depends(get_db)):
    return family_service.list_families(db)


@router.post("", response_model=FamilyRead, status_code=201)
def create_family(payload: FamilyCreate, actor: Actor = Depends(get_current_actor), db: Session = Depends(get_db)):
    return family_service.create_family(db, payload)


@router.get("/{family_id}", response_model=FamilyRead)
def get_family(family_id: uuid.UUID, actor: Actor = Depends(get_current_actor), db: Session = Depends(get_db)):
    actor.require_family(family_id)
    return family_service.get_family(db, family_id)


@router.get("/{family_id}/members", response_model=list[FamilyMemberRead])
def list_members(family_id: uuid.UUID, actor: Actor = Depends(get_current_actor), db: Session = Depends(get_db)):
    actor.require_family(family_id)
    return family_service.list_members(db, family_id)


@router.post("/{family_id}/members", response_model=FamilyMemberRead, status_code=201)
def create_member(family_id: uuid.UUID, payload: FamilyMemberCreate, actor: Actor = Depends(get_current_actor), db: Session = Depends(get_db)):
    actor.require_family(family_id)
    _require_adult(actor, db)
    return family_service.create_member(db, family_id, payload)


@router.get("/{family_id}/members/{member_id}", response_model=FamilyMemberRead)
def get_member(family_id: uuid.UUID, member_id: uuid.UUID, actor: Actor = Depends(get_current_actor), db: Session = Depends(get_db)):
    actor.require_family(family_id)
    return family_service.get_member(db, family_id, member_id)


# ---------------------------------------------------------------------------
# AI settings (adult-only) — gates general chat, homework help, home location
# ---------------------------------------------------------------------------

def _require_adult(actor: Actor, db: Session) -> None:
    """Gate write endpoints to adults only. Children can read settings but
    cannot change them."""
    member = db.get(FamilyMember, actor.member_id)
    if not member or member.role != "adult":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only adults can change this setting.",
        )


@router.get("/{family_id}/ai-settings", response_model=FamilyAISettingsRead)
def get_ai_settings(
    family_id: uuid.UUID,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_family(family_id)
    fam = db.get(Family, family_id)
    if not fam:
        raise HTTPException(status_code=404, detail="Family not found")
    return fam


@router.patch("/{family_id}/ai-settings", response_model=FamilyAISettingsRead)
def update_ai_settings(
    family_id: uuid.UUID,
    payload: FamilyAISettingsUpdate,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_family(family_id)
    _require_adult(actor, db)
    fam = db.get(Family, family_id)
    if not fam:
        raise HTTPException(status_code=404, detail="Family not found")
    if payload.allow_general_chat is not None:
        fam.allow_general_chat = payload.allow_general_chat
    if payload.allow_homework_help is not None:
        fam.allow_homework_help = payload.allow_homework_help
    if payload.home_location is not None:
        fam.home_location = payload.home_location.strip() or None
    db.commit()
    db.refresh(fam)
    return fam


@router.patch(
    "/{family_id}/members/{member_id}/learning",
    response_model=FamilyMemberRead,
)
def update_member_learning(
    family_id: uuid.UUID,
    member_id: uuid.UUID,
    payload: FamilyMemberLearningUpdate,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_family(family_id)
    _require_adult(actor, db)
    member = db.get(FamilyMember, member_id)
    if not member or member.family_id != family_id:
        raise HTTPException(status_code=404, detail="Member not found")
    if payload.grade_level is not None:
        member.grade_level = payload.grade_level.strip() or None
    if payload.learning_notes is not None:
        member.learning_notes = payload.learning_notes.strip() or None
    if payload.personality_notes is not None:
        member.personality_notes = payload.personality_notes.strip() or None
    if payload.read_aloud_enabled is not None:
        member.read_aloud_enabled = bool(payload.read_aloud_enabled)
    db.commit()
    db.refresh(member)
    return member


# ---------------------------------------------------------------------------
# Family member maintenance (adult-only)
# ---------------------------------------------------------------------------
#
# Fills the "can't edit users in the app" gap flagged during the
# 2026-04-14 maintenance pass. Endpoints below cover:
#   - PATCH  /families/{fid}/members/{mid}                  core fields
#   - GET    /families/{fid}/members/{mid}/accounts         list logins
#   - POST   /families/{fid}/members/{mid}/accounts         add a login
#   - PATCH  /families/{fid}/members/{mid}/accounts/{aid}   edit a login
#
# Every write gates on _require_adult and enforces the family-access
# invariant below so you can't accidentally lock the whole family out.


def _family_has_signin(db: Session, family_id: uuid.UUID) -> bool:
    """True iff the family has at least one active adult member who
    has at least one active user_account. Used as an invariant check
    after every member/account mutation. If this would be false after
    a proposed change, the change is rejected with 409."""
    row = db.execute(
        select(FamilyMember.id)
        .join(UserAccount, UserAccount.family_member_id == FamilyMember.id)
        .where(FamilyMember.family_id == family_id)
        .where(FamilyMember.role == "adult")
        .where(FamilyMember.is_active.is_(True))
        .where(UserAccount.is_active.is_(True))
        .limit(1)
    ).first()
    return row is not None


def _assert_signin_invariant(db: Session, family_id: uuid.UUID) -> None:
    if not _family_has_signin(db, family_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Refusing change: at least one active adult member with an "
                "active login must remain for the family to stay accessible."
            ),
        )


@router.patch(
    "/{family_id}/members/{member_id}",
    response_model=FamilyMemberRead,
)
def update_member_core(
    family_id: uuid.UUID,
    member_id: uuid.UUID,
    payload: FamilyMemberCoreUpdate,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    """Edit core identity fields on a family member — first_name,
    last_name, birthdate, role, is_active. Adult-only. Refuses any
    change that would leave the family with no active adult who has
    an active login.

    Applies the mutation inside a savepoint so a failing invariant
    rolls back cleanly without leaving the session half-flushed.
    """
    actor.require_family(family_id)
    _require_adult(actor, db)
    member = db.get(FamilyMember, member_id)
    if not member or member.family_id != family_id:
        raise HTTPException(status_code=404, detail="Member not found")

    if payload.first_name is not None and not payload.first_name.strip():
        raise HTTPException(status_code=400, detail="first_name cannot be blank")

    with db.begin_nested():
        if payload.first_name is not None:
            member.first_name = payload.first_name.strip()
        if payload.last_name is not None:
            member.last_name = payload.last_name.strip() or None
        if payload.birthdate is not None:
            member.birthdate = payload.birthdate
        if payload.role is not None:
            member.role = payload.role
        if payload.is_active is not None:
            member.is_active = bool(payload.is_active)
        db.flush()
        _assert_signin_invariant(db, family_id)

    db.commit()
    db.refresh(member)
    return member


@router.get(
    "/{family_id}/members/{member_id}/accounts",
    response_model=list[UserAccountRead],
)
def list_member_accounts(
    family_id: uuid.UUID,
    member_id: uuid.UUID,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    """List all user_accounts (logins) attached to a family member.
    Adult-only: accounts are sensitive credentials, children don't
    need to see the list."""
    actor.require_family(family_id)
    _require_adult(actor, db)
    member = db.get(FamilyMember, member_id)
    if not member or member.family_id != family_id:
        raise HTTPException(status_code=404, detail="Member not found")
    rows = list(
        db.scalars(
            select(UserAccount)
            .where(UserAccount.family_member_id == member_id)
            .order_by(UserAccount.is_active.desc(), UserAccount.email)
        ).all()
    )
    return rows


@router.post(
    "/{family_id}/members/{member_id}/accounts",
    response_model=UserAccountRead,
    status_code=201,
)
def create_member_account(
    family_id: uuid.UUID,
    member_id: uuid.UUID,
    payload: UserAccountCreate,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    """Attach a new login account to an existing family member.
    Adult-only. Password is hashed with the same helper the rest of
    the auth flow uses. Email uniqueness is enforced at the DB layer;
    a duplicate surfaces as 409 here."""
    actor.require_family(family_id)
    _require_adult(actor, db)
    member = db.get(FamilyMember, member_id)
    if not member or member.family_id != family_id:
        raise HTTPException(status_code=404, detail="Member not found")

    account = UserAccount(
        family_member_id=member_id,
        email=payload.email.strip(),
        auth_provider="email",
        password_hash=hash_password(payload.password),
        is_primary=bool(payload.is_primary),
        is_active=True,
    )
    db.add(account)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That email is already in use.",
        )
    db.commit()
    db.refresh(account)
    return account


@router.patch(
    "/{family_id}/members/{member_id}/accounts/{account_id}",
    response_model=UserAccountRead,
)
def update_member_account(
    family_id: uuid.UUID,
    member_id: uuid.UUID,
    account_id: uuid.UUID,
    payload: UserAccountUpdate,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    """Rotate email, toggle active/primary, or reset password on an
    existing account. Adult-only. Refuses any change that would leave
    the family with no signed-in adults (invariant)."""
    actor.require_family(family_id)
    _require_adult(actor, db)
    member = db.get(FamilyMember, member_id)
    if not member or member.family_id != family_id:
        raise HTTPException(status_code=404, detail="Member not found")
    account = db.get(UserAccount, account_id)
    if not account or account.family_member_id != member_id:
        raise HTTPException(status_code=404, detail="Account not found")

    # Wrap mutation + invariant in a savepoint so a failing check
    # rolls back cleanly instead of leaving the session half-flushed.
    try:
        with db.begin_nested():
            if payload.email is not None:
                account.email = payload.email.strip()
            if payload.is_active is not None:
                account.is_active = bool(payload.is_active)
            if payload.is_primary is not None:
                account.is_primary = bool(payload.is_primary)
            if payload.new_password is not None:
                account.password_hash = hash_password(payload.new_password)
            db.flush()
            _assert_signin_invariant(db, family_id)
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That email is already in use.",
        )

    db.commit()
    db.refresh(account)
    return account

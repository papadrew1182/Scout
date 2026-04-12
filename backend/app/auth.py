"""FastAPI dependencies for authentication and current-actor resolution.

Usage in routes:
    from app.auth import get_current_actor, Actor

    @router.get("/something")
    def something(actor: Actor = Depends(get_current_actor), db: Session = Depends(get_db)):
        # actor.member, actor.family, actor.role are all server-derived
        ...
"""

import uuid
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.foundation import Family, FamilyMember, UserAccount
from app.services.auth_service import resolve_session


@dataclass
class Actor:
    """The authenticated actor for the current request."""
    account: UserAccount
    member: FamilyMember
    family: Family

    @property
    def member_id(self) -> uuid.UUID:
        return self.member.id

    @property
    def family_id(self) -> uuid.UUID:
        return self.family.id

    @property
    def role(self) -> str:
        return self.member.role

    @property
    def is_adult(self) -> bool:
        return self.member.role == "adult"

    def require_adult(self) -> None:
        if not self.is_adult:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This action requires an adult role",
            )

    def require_family(self, family_id: uuid.UUID) -> None:
        """Ensure the actor belongs to the requested family."""
        if self.family_id != family_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this family",
            )


def _extract_token(request: Request) -> str | None:
    """Extract bearer token from Authorization header."""
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        return auth[7:]
    return None


def get_current_actor(
    request: Request,
    db: Session = Depends(get_db),
) -> Actor:
    """Resolve the authenticated actor from the session token.

    Falls back to legacy member_id query param ONLY when
    SCOUT_AUTH_REQUIRED is false (dev/test mode).
    """
    token = _extract_token(request)

    if token:
        account, member, family = resolve_session(db, token)
        return Actor(account=account, member=member, family=family)

    # Legacy fallback for dev/test — will be removed
    if not settings.auth_required:
        member_id = request.query_params.get("member_id")
        if not member_id:
            # Try body for POST requests (AI chat etc)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required. Provide Authorization: Bearer <token>",
            )
        try:
            mid = uuid.UUID(member_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid member_id")
        member = db.get(FamilyMember, mid)
        if not member or not member.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Member not found")
        family = db.get(Family, member.family_id)
        if not family:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Family not found")
        # Create a minimal Actor without account
        return Actor(
            account=UserAccount(id=uuid.uuid4(), family_member_id=member.id, auth_provider="dev", is_active=True),
            member=member,
            family=family,
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required. Provide Authorization: Bearer <token>",
    )

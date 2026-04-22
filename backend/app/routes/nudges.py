"""Nudges routes — Sprint 05 Phase 2.

Currently exposes the caller-scoped recent-dispatches list that backs
the Recent-nudges panel on /settings/ai. Held (status='pending') and
suppressed (status='suppressed') rows are included so the UI can show
full history plus 'quiet hours held this' affordances.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth import Actor, get_current_actor
from app.database import get_db
from app.models.nudges import NudgeDispatch
from app.schemas.nudges import NudgeDispatchRead

router = APIRouter(prefix="/api/nudges", tags=["nudges"])


@router.get("/me", response_model=list[NudgeDispatchRead])
def list_my_nudges(
    limit: int = Query(20, ge=1, le=100),
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    """Caller's recent nudge dispatches. Self-scoped; no family_id
    param. Includes held (status=pending) and suppressed rows so the
    UI can show 'quiet hours held this' affordances."""
    actor.require_permission("nudges.view_own")
    stmt = (
        select(NudgeDispatch)
        .where(NudgeDispatch.family_member_id == actor.member_id)
        .order_by(NudgeDispatch.created_at.desc())
        .options(selectinload(NudgeDispatch.items))
        .limit(limit)
    )
    return list(db.scalars(stmt).all())

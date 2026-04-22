"""Admin quiet-hours config route (Sprint 05 Phase 2).

Exposes GET + PUT under /api/admin/family-config/quiet-hours. Both
endpoints require the quiet_hours.manage permission, which migration
050 grants to PARENT and PRIMARY_PARENT tiers.

GET returns the family's scout.quiet_hours_family row when present;
otherwise it returns the system default (22:00 start, 07:00 end) with
is_default=true so the admin UI always has a value to render.

PUT upserts the family row. On conflict the existing row is updated
in place so the (family_id) uniqueness invariant stays intact.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import Actor, get_current_actor
from app.database import get_db
from app.models.quiet_hours import QuietHoursFamily
from app.schemas.nudges import QuietHoursRead, QuietHoursUpdate

router = APIRouter(prefix="/api/admin/family-config", tags=["admin-config"])

_DEFAULT_START = 22 * 60
_DEFAULT_END = 7 * 60


@router.get("/quiet-hours", response_model=QuietHoursRead)
def get_family_quiet_hours(
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    """Effective family-wide quiet-hours window. Returns the system
    default when the family has never set one."""
    actor.require_permission("quiet_hours.manage")
    row = db.scalars(
        select(QuietHoursFamily).where(QuietHoursFamily.family_id == actor.family_id)
    ).first()
    if row is None:
        return QuietHoursRead(
            start_local_minute=_DEFAULT_START,
            end_local_minute=_DEFAULT_END,
            is_default=True,
        )
    return QuietHoursRead(
        start_local_minute=row.start_local_minute,
        end_local_minute=row.end_local_minute,
        is_default=False,
    )


@router.put("/quiet-hours", response_model=QuietHoursRead)
def put_family_quiet_hours(
    body: QuietHoursUpdate,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    """Upsert the family's quiet-hours window. Admin-only."""
    actor.require_permission("quiet_hours.manage")
    row = db.scalars(
        select(QuietHoursFamily).where(QuietHoursFamily.family_id == actor.family_id)
    ).first()
    if row is None:
        row = QuietHoursFamily(
            family_id=actor.family_id,
            start_local_minute=body.start_local_minute,
            end_local_minute=body.end_local_minute,
        )
        db.add(row)
    else:
        row.start_local_minute = body.start_local_minute
        row.end_local_minute = body.end_local_minute
    db.commit()
    db.refresh(row)
    return QuietHoursRead(
        start_local_minute=row.start_local_minute,
        end_local_minute=row.end_local_minute,
        is_default=False,
    )

"""Session 2 canonical endpoint contracts.

These are the endpoints the Session 3 operating surface consumes.
Payload shapes are locked — Session 3 can build against them now
even though several views are still populated from legacy tables
and the connector sync loop isn't wired to real external APIs yet.

Endpoints:
    GET  /api/me
    GET  /api/family/context/current
    GET  /api/household/today
    POST /api/household/completions
    GET  /api/rewards/week/current
    GET  /api/connectors
    GET  /api/connectors/health

Where the charter's JSON example included richer data than the
first-pass read models currently hold, the route returns the
stable keys with best-effort values. Session 3 can still build
the UI shape; later work packets fill in real data.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

import pytz
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.auth import Actor, get_current_actor
from app.database import get_db
from app.models.foundation import Family, FamilyMember
from services.connectors.registry import CONNECTOR_REGISTRY
from services.connectors.sync_service import SyncService

router = APIRouter(prefix="/api", tags=["session2-canonical"])

_sync_service = SyncService()


def _age_from_birthdate(bd: date | None, today: date) -> int | None:
    if bd is None:
        return None
    return (today - bd).days // 365


def _role_tier_for(member: FamilyMember) -> str:
    """Best-effort role-tier key from the member's role + birthdate.
    Real resolution will come from scout.user_family_memberships
    once identity write paths are wired; this keeps the payload
    populated for Session 3 in the meantime."""
    today = date.today()
    age = _age_from_birthdate(member.birthdate, today)
    if member.role == "adult":
        return "PRIMARY_PARENT"
    if age is None:
        return "CHILD"
    if age >= 13:
        return "TEEN"
    if age >= 9:
        return "CHILD"
    return "YOUNG_CHILD"


# ---------------------------------------------------------------------------
# GET /api/me
# ---------------------------------------------------------------------------


@router.get("/me")
def get_me(
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    member = db.get(FamilyMember, actor.member_id)
    family = db.get(Family, actor.family_id)
    if not member or not family:
        raise HTTPException(status_code=404, detail="actor context not found")

    full_name = f"{member.first_name} {member.last_name or ''}".strip()
    role_tier = _role_tier_for(member)
    email = actor.account.email if actor.account else None

    return {
        "user": {
            "id": str(actor.account.id) if actor.account else None,
            "email": email,
            "full_name": full_name,
            "role_tier_key": role_tier,
            "family_member_id": str(member.id),
            "feature_flags": {
                "calendar_publish": False,
                "greenlight_settlement": False,
                "meal_planning": True,
            },
        },
        "family": {
            "id": str(family.id),
            "name": family.name,
            "timezone": family.timezone,
        },
    }


# ---------------------------------------------------------------------------
# GET /api/family/context/current
# ---------------------------------------------------------------------------


def _active_time_block_for(db: Session, family_id: uuid.UUID, now_local: datetime) -> dict | None:
    """Resolve which scout.time_blocks row is currently active. Returns
    None if none match the current local hour."""
    row = db.execute(
        text(
            """
            SELECT block_key, label, start_offset, end_offset
            FROM scout.time_blocks
            WHERE family_id = :fid
              AND (
                  (CAST(:weekday AS boolean) AND applies_weekday)
                  OR (NOT CAST(:weekday AS boolean) AND applies_weekend)
              )
              AND start_offset <= :now_offset
              AND end_offset >= :now_offset
            ORDER BY sort_order
            LIMIT 1
            """
        ),
        {
            "fid": family_id,
            "weekday": now_local.weekday() < 5,
            "now_offset": timedelta(
                hours=now_local.hour, minutes=now_local.minute
            ),
        },
    ).first()
    if row is None:
        return None
    start_at = now_local.replace(hour=0, minute=0, second=0, microsecond=0) + row.start_offset
    end_at = now_local.replace(hour=0, minute=0, second=0, microsecond=0) + row.end_offset
    status_str = "upcoming" if now_local < start_at else ("active" if now_local <= end_at else "closed")
    return {
        "id": None,
        "block_key": row.block_key,
        "label": row.label,
        "starts_at": start_at.isoformat(),
        "ends_at": end_at.isoformat(),
        "status": status_str,
    }


@router.get("/family/context/current")
def get_family_context_current(
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    family = db.get(Family, actor.family_id)
    if not family:
        raise HTTPException(status_code=404, detail="family not found")

    tz = pytz.timezone(family.timezone or "America/Chicago")
    now_local = datetime.now(tz)
    today = now_local.date()

    members = list(
        db.scalars(
            select(FamilyMember)
            .where(FamilyMember.family_id == actor.family_id)
            .where(FamilyMember.is_active.is_(True))
            .order_by(FamilyMember.birthdate.asc().nulls_last())
        ).all()
    )

    kids = [
        {
            "family_member_id": str(m.id),
            "name": m.first_name,
            "age": _age_from_birthdate(m.birthdate, today),
            "role_tier_key": _role_tier_for(m),
        }
        for m in members
        if m.role == "child"
    ]

    # Household rules lookup — pulls from scout.household_rules if rows
    # exist, else returns the charter's documented defaults.
    rules_row = db.execute(
        text(
            """
            SELECT rule_key, rule_value
            FROM scout.household_rules
            WHERE family_id = :fid
            """
        ),
        {"fid": actor.family_id},
    ).all()
    household_rules: dict[str, Any] = {
        "one_owner_per_task": True,
        "one_reminder_max": True,
    }
    for r in rules_row:
        household_rules[r.rule_key] = r.rule_value

    return {
        "family": {
            "id": str(family.id),
            "name": family.name,
            "timezone": family.timezone,
        },
        "date": today.isoformat(),
        "active_time_block": _active_time_block_for(db, actor.family_id, now_local),
        "kids": kids,
        "household_rules": household_rules,
    }


# ---------------------------------------------------------------------------
# GET /api/household/today
# ---------------------------------------------------------------------------


@router.get("/household/today")
def get_household_today(
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    family = db.get(Family, actor.family_id)
    tz = pytz.timezone(family.timezone or "America/Chicago") if family else pytz.UTC
    today_local = datetime.now(tz).date()

    # v_household_today is the charter-blessed read model. It's
    # empty until the legacy → scout backfill runs, so for now the
    # route returns an empty-but-stable envelope. Session 3 builds
    # against these keys.
    rows = db.execute(
        text(
            """
            SELECT
                task_occurrence_id,
                occurrence_date,
                due_at,
                status,
                family_member_id,
                member_name,
                label,
                template_key,
                routine_key,
                block_label,
                is_completed,
                completed_at
            FROM scout.v_household_today
            WHERE family_id = :fid
              AND occurrence_date = :today
            ORDER BY due_at
            """
        ),
        {"fid": actor.family_id, "today": today_local},
    ).all()

    due_count = sum(1 for r in rows if r.status == "open")
    completed_count = sum(1 for r in rows if r.is_completed)
    late_count = sum(1 for r in rows if r.status == "late")

    return {
        "date": today_local.isoformat(),
        "summary": {
            "due_count": due_count,
            "completed_count": completed_count,
            "late_count": late_count,
        },
        "blocks": [],
        "standalone_chores": [
            {
                "task_occurrence_id": str(r.task_occurrence_id),
                "template_key": r.template_key,
                "label": r.label,
                "owner_family_member_id": (
                    str(r.family_member_id) if r.family_member_id else None
                ),
                "owner_name": r.member_name,
                "due_at": r.due_at.isoformat() if r.due_at else None,
                "status": "complete" if r.is_completed else r.status,
            }
            for r in rows
            if r.template_key is not None
        ],
        "weekly_items": [],
    }


# ---------------------------------------------------------------------------
# POST /api/household/completions
# ---------------------------------------------------------------------------


class CompletionIn(BaseModel):
    task_occurrence_id: uuid.UUID
    completed_by_family_member_id: uuid.UUID
    completed_at: datetime | None = None
    completion_mode: str = Field(default="manual", pattern="^(manual|auto|parent_override|ai_recorded)$")
    notes: str | None = None


@router.post("/household/completions")
def post_household_completion(
    payload: CompletionIn,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    # Verify the occurrence belongs to the actor's family.
    occ = db.execute(
        text(
            """
            SELECT id, family_id, status
            FROM scout.task_occurrences
            WHERE id = :id
            """
        ),
        {"id": payload.task_occurrence_id},
    ).first()
    if occ is None or occ.family_id != actor.family_id:
        raise HTTPException(status_code=404, detail="task_occurrence not found")

    completed_at = payload.completed_at or datetime.now(timezone.utc)
    completion_id = uuid.uuid4()

    db.execute(
        text(
            """
            INSERT INTO scout.task_completions
                (id, task_occurrence_id, completed_by, completed_at, completion_mode, notes)
            VALUES
                (:id, :occ_id, :by, :at, :mode, :notes)
            """
        ),
        {
            "id": completion_id,
            "occ_id": payload.task_occurrence_id,
            "by": payload.completed_by_family_member_id,
            "at": completed_at,
            "mode": payload.completion_mode,
            "notes": payload.notes,
        },
    )
    db.execute(
        text(
            """
            UPDATE scout.task_occurrences
            SET status = 'complete', updated_at = clock_timestamp()
            WHERE id = :id
            """
        ),
        {"id": payload.task_occurrence_id},
    )
    db.commit()

    # Daily Win recompute and reward preview recomputation are
    # deferred to the rewards work packet. Return stable keys with
    # conservative values so Session 3 can render.
    return {
        "task_occurrence_id": str(payload.task_occurrence_id),
        "status": "complete",
        "daily_win_recomputed": False,
        "reward_preview_changed": False,
    }


# ---------------------------------------------------------------------------
# GET /api/rewards/week/current
# ---------------------------------------------------------------------------


@router.get("/rewards/week/current")
def get_rewards_current_week(
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    rows = db.execute(
        text(
            """
            SELECT
                allowance_period_id,
                start_date,
                end_date,
                period_status,
                family_member_id,
                member_name,
                baseline_amount_cents,
                wins_earned,
                wins_required,
                payout_percent,
                projected_cents,
                final_cents,
                miss_reasons
            FROM scout.v_rewards_current_week
            WHERE family_id = :fid
            ORDER BY family_member_id
            """
        ),
        {"fid": actor.family_id},
    ).all()

    if not rows:
        return {
            "period": None,
            "members": [],
            "approval": {"state": "draft"},
        }

    period_row = rows[0]
    members = [
        {
            "family_member_id": str(r.family_member_id),
            "name": r.member_name,
            "baseline_allowance": r.baseline_amount_cents / 100.0,
            "daily_wins": r.wins_earned,
            "payout_percent": float(r.payout_percent),
            "projected_payout": r.projected_cents / 100.0,
            "miss_reasons": r.miss_reasons or [],
        }
        for r in rows
    ]

    return {
        "period": {
            "id": str(period_row.allowance_period_id),
            "start_date": period_row.start_date.isoformat(),
            "end_date": period_row.end_date.isoformat(),
        },
        "members": members,
        "approval": {"state": period_row.period_status},
    }


# ---------------------------------------------------------------------------
# GET /api/connectors
# ---------------------------------------------------------------------------


@router.get("/connectors")
def get_connectors(
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    rows = db.execute(
        text(
            """
            SELECT
                c.connector_key,
                c.label,
                c.decision_gated,
                ca.status,
                ca.last_success_at
            FROM scout.connectors c
            LEFT JOIN scout.connector_accounts ca
                ON ca.connector_id = c.id AND ca.family_id = :fid
            ORDER BY c.tier, c.connector_key
            """
        ),
        {"fid": actor.family_id},
    ).all()

    items = []
    for r in rows:
        status_value = r.status
        if status_value is None:
            status_value = "decision_gated" if r.decision_gated else "disconnected"
        items.append(
            {
                "connector_key": r.connector_key,
                "label": r.label,
                "status": status_value,
                "last_sync_at": (
                    r.last_success_at.isoformat() if r.last_success_at else None
                ),
            }
        )

    return {"items": items}


# ---------------------------------------------------------------------------
# GET /api/connectors/health
# ---------------------------------------------------------------------------


@router.get("/connectors/health")
def get_connectors_health(
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    items = []
    for connector_key in sorted(CONNECTOR_REGISTRY.keys()):
        health = _sync_service.health_check(connector_key)
        items.append(
            {
                "connector_key": health.connector_key,
                "healthy": health.healthy,
                "freshness_state": health.freshness_state.value,
                "last_success_at": (
                    health.last_success_at.isoformat() if health.last_success_at else None
                ),
                "last_error_at": (
                    health.last_error_at.isoformat() if health.last_error_at else None
                ),
                "last_error_message": health.last_error_message,
            }
        )
    return {"items": items}

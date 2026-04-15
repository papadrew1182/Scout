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
from app.services.canonical_household_service import (
    generate_task_occurrences_for_date,
    recompute_daily_win,
)
from services.connectors.registry import CONNECTOR_REGISTRY
from services.connectors.sync_service import SyncService

router = APIRouter(prefix="/api", tags=["session2-canonical"])

# Block 3 — single shared instance. Routes call into it to read
# DB-backed connector health and to drive sync runs through the
# persistence DAL. Stateless across requests; the per-request DB
# session is passed in.
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

    # Block 2 — make sure the day's occurrences exist before the
    # read. The generator is idempotent, so calling it on every
    # request is cheap; in production this can move behind the
    # scheduler. Failures here must NOT break the read — fall
    # through to whatever is already in the table.
    try:
        generate_task_occurrences_for_date(
            db, family_id=actor.family_id, on_date=today_local
        )
        db.flush()
    except Exception:  # pragma: no cover — best-effort
        pass

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

    due_count = sum(1 for r in rows if not r.is_completed)
    completed_count = sum(1 for r in rows if r.is_completed)
    late_count = sum(1 for r in rows if r.status == "late")

    # Group routine occurrences by block_label/routine_key for the
    # `blocks` payload section, and split out task_template-backed
    # rows into the `standalone_chores` section. Weekly recurrences
    # (Power 60, Poop Patrol — both 'weekly' in the template) land
    # in `weekly_items`.
    blocks_by_key: dict[str, dict] = {}
    standalone: list[dict] = []
    weekly: list[dict] = []

    weekly_template_keys = _weekly_template_keys(db, actor.family_id)

    for r in rows:
        flat = {
            "task_occurrence_id": str(r.task_occurrence_id),
            "template_key": r.template_key,
            "routine_key": r.routine_key,
            "label": r.label,
            "owner_family_member_id": (
                str(r.family_member_id) if r.family_member_id else None
            ),
            "owner_name": r.member_name,
            "due_at": r.due_at.isoformat() if r.due_at else None,
            "status": "complete" if r.is_completed else r.status,
        }
        if r.routine_key:
            block_key = r.routine_key
            block_entry = blocks_by_key.setdefault(
                block_key,
                {
                    "block_key": block_key,
                    "label": r.block_label or block_key.title(),
                    "due_at": flat["due_at"],
                    "exported_to_calendar": False,
                    "assignments": [],
                },
            )
            block_entry["assignments"].append(
                {
                    "routine_instance_id": flat["task_occurrence_id"],
                    "family_member_id": flat["owner_family_member_id"],
                    "member_name": flat["owner_name"],
                    "status": flat["status"],
                    "steps": [],
                }
            )
        elif r.template_key in weekly_template_keys:
            weekly.append(flat)
        else:
            standalone.append(flat)

    return {
        "date": today_local.isoformat(),
        "summary": {
            "due_count": due_count,
            "completed_count": completed_count,
            "late_count": late_count,
        },
        "blocks": list(blocks_by_key.values()),
        "standalone_chores": standalone,
        "weekly_items": weekly,
    }


def _weekly_template_keys(db: Session, family_id: uuid.UUID) -> set[str]:
    rows = db.execute(
        text(
            """
            SELECT template_key
            FROM scout.task_templates
            WHERE family_id = :fid AND recurrence = 'weekly'
            """
        ),
        {"fid": family_id},
    ).all()
    return {r.template_key for r in rows}


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

    # Block 2 — Daily Win recompute lives here now. Recompute against
    # the assignee of the occurrence (which may differ from the
    # caller in parent-override flows) using the occurrence's date.
    occ_assignee_row = db.execute(
        text(
            """
            SELECT assigned_to, occurrence_date
            FROM scout.task_occurrences
            WHERE id = :id
            """
        ),
        {"id": payload.task_occurrence_id},
    ).first()

    daily_win_recomputed = False
    if occ_assignee_row and occ_assignee_row.assigned_to:
        recompute_result = recompute_daily_win(
            db,
            family_id=actor.family_id,
            family_member_id=occ_assignee_row.assigned_to,
            on_date=occ_assignee_row.occurrence_date,
        )
        daily_win_recomputed = recompute_result.changed

    db.commit()

    return {
        "task_occurrence_id": str(payload.task_occurrence_id),
        "status": "complete",
        "daily_win_recomputed": daily_win_recomputed,
        # Reward preview recomputation lands with the rewards
        # settlement packet (work packet F real implementation).
        # Until then we report False, which Session 3 already
        # builds against.
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
        # Block 2 fallback — if no allowance_period rows exist yet,
        # synthesize a preview from active reward_policies and the
        # week's daily_win_results so Session 3 can render the
        # weekly card before the real settlement worker lands.
        return _rewards_preview_from_policies(db, actor.family_id)

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


def _rewards_preview_from_policies(db: Session, family_id: uuid.UUID) -> dict:
    """Fallback rewards payload when no allowance_period exists yet.
    Reads scout.reward_policies + scout.daily_win_results and
    composes a per-member preview that matches the v_rewards_current_week
    JSON shape exactly so callers don't need to branch.

    Period bounds are computed as the current ISO Mon-Fri (the
    Roberts allowance week per family_chore_system.md). Empty-week
    families get a `period: null` envelope identical to the
    earlier behaviour."""
    today_local = date.today()
    week_start = today_local - timedelta(days=today_local.weekday())  # Monday
    week_end = week_start + timedelta(days=4)  # Friday (Mon-Fri = 5 days)

    policies = db.execute(
        text(
            """
            SELECT
                rp.id, rp.family_member_id, rp.baseline_amount_cents,
                fm.first_name AS member_name
            FROM scout.reward_policies rp
            JOIN public.family_members fm ON fm.id = rp.family_member_id
            WHERE rp.family_id = :fid
              AND rp.policy_key = 'weekly_allowance'
              AND rp.effective_from <= :end_date
              AND (rp.effective_until IS NULL OR rp.effective_until >= :start_date)
            ORDER BY fm.first_name
            """
        ),
        {"fid": family_id, "start_date": week_start, "end_date": week_end},
    ).all()

    if not policies:
        return {"period": None, "members": [], "approval": {"state": "draft"}}

    members_payload = []
    for p in policies:
        wins_row = db.execute(
            text(
                """
                SELECT COUNT(*) FILTER (WHERE earned) AS wins,
                       jsonb_agg(missing_items) FILTER (WHERE NOT earned AND missing_items IS NOT NULL) AS misses
                FROM scout.daily_win_results
                WHERE family_member_id = :mid
                  AND for_date BETWEEN :start_date AND :end_date
                """
            ),
            {"mid": p.family_member_id, "start_date": week_start, "end_date": week_end},
        ).first()
        wins_earned = int(wins_row.wins or 0) if wins_row else 0
        # Daily Win schedule: 5/4/3/<3 -> 100/80/60/0 per family file
        if wins_earned >= 5:
            payout_pct = 1.0
        elif wins_earned == 4:
            payout_pct = 0.8
        elif wins_earned == 3:
            payout_pct = 0.6
        else:
            payout_pct = 0.0
        projected_cents = int(round(p.baseline_amount_cents * payout_pct))
        members_payload.append(
            {
                "family_member_id": str(p.family_member_id),
                "name": p.member_name,
                "baseline_allowance": p.baseline_amount_cents / 100.0,
                "daily_wins": wins_earned,
                "payout_percent": payout_pct,
                "projected_payout": projected_cents / 100.0,
                "miss_reasons": [],
            }
        )

    return {
        "period": {
            "id": None,
            "start_date": week_start.isoformat(),
            "end_date": week_end.isoformat(),
        },
        "members": members_payload,
        "approval": {"state": "draft"},
    }


# ---------------------------------------------------------------------------
# GET /api/calendar/exports/upcoming
# ---------------------------------------------------------------------------


@router.get("/calendar/exports/upcoming")
def get_calendar_exports_upcoming(
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
    limit: int = 50,
):
    """Charter §GET /api/calendar/exports/upcoming. Reads from
    scout.v_calendar_publication, filtered to exports whose
    starts_at is in the future. Items are returned in chronological
    order so the operating surface can render an upcoming-block
    list directly."""
    rows = db.execute(
        text(
            """
            SELECT
                calendar_export_id,
                label,
                starts_at,
                ends_at,
                source_type,
                source_id,
                target,
                hearth_visible,
                export_status,
                last_exported_at
            FROM scout.v_calendar_publication
            WHERE family_id = :fid
              AND ends_at >= clock_timestamp()
            ORDER BY starts_at ASC
            LIMIT :limit
            """
        ),
        {"fid": actor.family_id, "limit": max(1, min(int(limit), 200))},
    ).all()

    return {
        "items": [
            {
                "calendar_export_id": str(r.calendar_export_id),
                "label": r.label,
                "starts_at": r.starts_at.isoformat() if r.starts_at else None,
                "ends_at": r.ends_at.isoformat() if r.ends_at else None,
                "source_type": r.source_type,
                "source_id": str(r.source_id) if r.source_id else None,
                "target": r.target,
                "hearth_visible": bool(r.hearth_visible),
                "export_status": r.export_status,
                "last_exported_at": (
                    r.last_exported_at.isoformat() if r.last_exported_at else None
                ),
            }
            for r in rows
        ]
    }


# ---------------------------------------------------------------------------
# GET /api/control-plane/summary
# ---------------------------------------------------------------------------


@router.get("/control-plane/summary")
def get_control_plane_summary(
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    """Charter §GET /api/control-plane/summary. Aggregates the
    control-plane health across all of this family's connector
    accounts plus pending sync/export/approval counts."""
    # Block 3 — counters now reflect real persisted state. An
    # account in 'error' status is counted as error regardless of
    # whether last_success_at has ever been set; an account that
    # last succeeded inside the LIVE window counts as healthy;
    # everything else (lagging/stale/unknown without an explicit
    # error) is grouped into stale_count so the operator surface
    # always renders three buckets that sum to the total number of
    # connector accounts.
    connector_summary = db.execute(
        text(
            """
            SELECT
                COUNT(*) FILTER (
                    WHERE status = 'connected'
                      AND freshness_state = 'live'
                ) AS healthy_count,
                COUNT(*) FILTER (
                    WHERE status NOT IN ('error', 'disabled')
                      AND freshness_state IN ('lagging', 'stale', 'unknown')
                ) AS stale_count,
                COUNT(*) FILTER (
                    WHERE status = 'error'
                ) AS error_count
            FROM scout.v_control_plane
            WHERE family_id = :fid
            """
        ),
        {"fid": actor.family_id},
    ).first()

    sync_summary = db.execute(
        text(
            """
            SELECT
                COUNT(*) FILTER (WHERE sr.status = 'running') AS running_count,
                COUNT(*) FILTER (WHERE sr.status = 'error') AS failed_count
            FROM scout.sync_runs sr
            JOIN scout.sync_jobs sj ON sj.id = sr.sync_job_id
            JOIN scout.connector_accounts ca ON ca.id = sj.connector_account_id
            WHERE ca.family_id = :fid
              AND sr.started_at >= clock_timestamp() - interval '24 hours'
            """
        ),
        {"fid": actor.family_id},
    ).first()

    calendar_summary = db.execute(
        text(
            """
            SELECT
                COUNT(*) FILTER (WHERE export_status = 'pending') AS pending_count,
                COUNT(*) FILTER (WHERE export_status = 'error') AS failed_count
            FROM scout.calendar_exports
            WHERE family_id = :fid
            """
        ),
        {"fid": actor.family_id},
    ).first()

    rewards_summary = db.execute(
        text(
            """
            SELECT COUNT(*) AS pending_approval_count
            FROM scout.allowance_periods
            WHERE family_id = :fid AND status = 'pending_approval'
            """
        ),
        {"fid": actor.family_id},
    ).first()

    return {
        "connectors": {
            "healthy_count": int(connector_summary.healthy_count or 0) if connector_summary else 0,
            "stale_count": int(connector_summary.stale_count or 0) if connector_summary else 0,
            "error_count": int(connector_summary.error_count or 0) if connector_summary else 0,
        },
        "sync_jobs": {
            "running_count": int(sync_summary.running_count or 0) if sync_summary else 0,
            "failed_count": int(sync_summary.failed_count or 0) if sync_summary else 0,
        },
        "calendar_exports": {
            "pending_count": int(calendar_summary.pending_count or 0) if calendar_summary else 0,
            "failed_count": int(calendar_summary.failed_count or 0) if calendar_summary else 0,
        },
        "rewards": {
            "pending_approval_count": int(rewards_summary.pending_approval_count or 0) if rewards_summary else 0,
        },
    }


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
    """Block 3: DB-backed health snapshot.

    Reads scout.connectors LEFT JOIN scout.connector_accounts for
    the actor's family. Connectors without an account row fall
    back to status='disconnected' (or 'decision_gated' when the
    registry marks them so) and freshness_state='unknown'. Status
    + freshness vocabulary are charter-locked.

    Block 2 returned synthetic data from in-memory adapter stubs;
    Block 3 reflects what's actually persisted.
    """
    rows = _sync_service.health_check_db(db, family_id=actor.family_id)
    items = []
    for r in rows:
        items.append(
            {
                "connector_key": r.connector_key,
                "label": r.label,
                "healthy": r.healthy,
                "status": r.status,
                "freshness_state": r.freshness_state.value,
                "last_success_at": (
                    r.last_success_at.isoformat() if r.last_success_at else None
                ),
                "last_error_at": (
                    r.last_error_at.isoformat() if r.last_error_at else None
                ),
                "last_error_message": r.last_error_message,
                "open_alert_count": r.open_alert_count,
            }
        )
    return {"items": items}

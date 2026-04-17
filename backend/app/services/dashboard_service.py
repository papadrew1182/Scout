"""Dashboard aggregation service.

Assembles compact dashboard payloads for each surface role.
Uses existing domain services underneath — no business logic duplication.
"""

import uuid
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.action_items import ParentActionItem
from app.models.calendar import Event
from app.models.finance import Bill
from app.models.foundation import Family, FamilyMember
from app.models.grocery import GroceryItem, PurchaseRequest
from app.models.life_management import (
    AllowanceLedger,
    ChoreTemplate,
    DailyWin,
    Routine,
    TaskInstance,
)
from app.models.meals import Meal
from app.models.notes import Note
from app.models.personal_tasks import PersonalTask
from app.services.tenant_guard import require_family, require_member_in_family


def personal_dashboard(db: Session, family_id: uuid.UUID, member_id: uuid.UUID) -> dict:
    """Compact personal dashboard for an adult member."""
    require_family(db, family_id)
    member = require_member_in_family(db, family_id, member_id)

    today = date.today()
    now = datetime.now()
    end_of_day = datetime.combine(today, datetime.max.time())
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=4)

    # Personal tasks (top 5)
    top_tasks = list(db.scalars(
        select(PersonalTask)
        .where(PersonalTask.family_id == family_id)
        .where(PersonalTask.assigned_to == member_id)
        .where(PersonalTask.status.in_(("pending", "in_progress")))
        .order_by(PersonalTask.due_at.is_(None), PersonalTask.due_at)
        .limit(5)
    ).all())

    # Today's events
    events_today = list(db.scalars(
        select(Event)
        .where(Event.family_id == family_id)
        .where(Event.starts_at <= end_of_day)
        .where(Event.ends_at >= now)
        .where(Event.is_cancelled.is_(False))
        .order_by(Event.starts_at)
        .limit(8)
    ).all())

    # Today's meals
    meals_today = list(db.scalars(
        select(Meal).where(Meal.family_id == family_id).where(Meal.meal_date == today)
    ).all())

    # Unpaid bills
    unpaid_bills = db.scalar(
        select(func.count()).select_from(Bill)
        .where(Bill.family_id == family_id)
        .where(Bill.status.in_(("upcoming", "overdue")))
    ) or 0

    # Recent notes
    recent_notes = list(db.scalars(
        select(Note)
        .where(Note.family_id == family_id)
        .where(Note.family_member_id == member_id)
        .where(Note.is_archived.is_(False))
        .order_by(Note.updated_at.desc())
        .limit(3)
    ).all())

    # Grocery count
    grocery_count = db.scalar(
        select(func.count()).select_from(GroceryItem)
        .where(GroceryItem.family_id == family_id)
        .where(GroceryItem.is_purchased.is_(False))
        .where(GroceryItem.approval_status == "active")
    ) or 0

    return {
        "member_name": member.first_name,
        "date": today.isoformat(),
        "top_tasks": [_task_summary(t) for t in top_tasks],
        "events_today": [_event_summary(e) for e in events_today],
        "meals_today": [{"meal_type": m.meal_type, "title": m.title} for m in meals_today],
        "unpaid_bills_count": unpaid_bills,
        "recent_notes": [{"id": str(n.id), "title": n.title} for n in recent_notes],
        "grocery_items_count": grocery_count,
    }


def parent_dashboard(db: Session, family_id: uuid.UUID, member_id: uuid.UUID) -> dict:
    """Compact parent household dashboard."""
    from app.services.permissions import resolve_effective_permissions
    require_family(db, family_id)
    require_member_in_family(db, family_id, member_id)
    perms = resolve_effective_permissions(db, member_id)
    if not perms.get("dashboard.view_parent", False):
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission required: dashboard.view_parent")

    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=4)

    # Children
    children = list(db.scalars(
        select(FamilyMember)
        .where(FamilyMember.family_id == family_id)
        .where(FamilyMember.role == "child")
        .where(FamilyMember.is_active.is_(True))
    ).all())

    # Per-child status
    child_statuses = []
    for child in children:
        tasks = list(db.scalars(
            select(TaskInstance)
            .where(TaskInstance.family_id == family_id)
            .where(TaskInstance.family_member_id == child.id)
            .where(TaskInstance.instance_date == today)
        ).all())
        total = len(tasks)
        completed = sum(1 for t in tasks if t.is_completed or t.override_completed)

        wins = list(db.scalars(
            select(DailyWin)
            .where(DailyWin.family_member_id == child.id)
            .where(DailyWin.win_date >= week_start)
            .where(DailyWin.win_date <= week_end)
        ).all())
        win_count = sum(1 for w in wins if w.is_win)

        child_statuses.append({
            "id": str(child.id),
            "name": child.first_name,
            "tasks_total": total,
            "tasks_completed": completed,
            "weekly_wins": win_count,
        })

    # Pending action items
    pending_actions = list(db.scalars(
        select(ParentActionItem)
        .where(ParentActionItem.family_id == family_id)
        .where(ParentActionItem.status == "pending")
        .order_by(ParentActionItem.created_at.desc())
        .limit(10)
    ).all())

    # Household health
    health = _derive_household_health(db, family_id, child_statuses, pending_actions)

    # Pending grocery reviews
    pending_grocery = db.scalar(
        select(func.count()).select_from(GroceryItem)
        .where(GroceryItem.family_id == family_id)
        .where(GroceryItem.approval_status == "pending_review")
    ) or 0

    # Pending purchase requests
    pending_requests = db.scalar(
        select(func.count()).select_from(PurchaseRequest)
        .where(PurchaseRequest.family_id == family_id)
        .where(PurchaseRequest.status == "pending")
    ) or 0

    return {
        "date": today.isoformat(),
        "children": child_statuses,
        "pending_actions": [_action_summary(a) for a in pending_actions],
        "pending_actions_count": len(pending_actions),
        "household_health": health,
        "pending_grocery_reviews": pending_grocery,
        "pending_purchase_requests": pending_requests,
    }


def child_dashboard(db: Session, family_id: uuid.UUID, member_id: uuid.UUID) -> dict:
    """Compact child dashboard."""
    require_family(db, family_id)
    member = require_member_in_family(db, family_id, member_id)

    today = date.today()
    now = datetime.now()
    end_of_day = datetime.combine(today, datetime.max.time())
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=4)

    # Today's task instances (chores/routines)
    tasks = list(db.scalars(
        select(TaskInstance)
        .where(TaskInstance.family_id == family_id)
        .where(TaskInstance.family_member_id == member_id)
        .where(TaskInstance.instance_date == today)
        .order_by(TaskInstance.due_at)
    ).all())

    total = len(tasks)
    completed = sum(1 for t in tasks if t.is_completed or t.override_completed)

    # Weekly wins
    wins = list(db.scalars(
        select(DailyWin)
        .where(DailyWin.family_member_id == member_id)
        .where(DailyWin.win_date >= week_start)
        .where(DailyWin.win_date <= week_end)
    ).all())
    win_count = sum(1 for w in wins if w.is_win)

    # Allowance balance
    balance = db.scalar(
        select(func.coalesce(func.sum(AllowanceLedger.amount_cents), 0))
        .where(AllowanceLedger.family_id == family_id)
        .where(AllowanceLedger.family_member_id == member_id)
    ) or 0

    # Today's events (hearth visible)
    events = list(db.scalars(
        select(Event)
        .where(Event.family_id == family_id)
        .where(Event.starts_at <= end_of_day)
        .where(Event.ends_at >= now)
        .where(Event.is_cancelled.is_(False))
        .where(Event.is_hearth_visible.is_(True))
        .order_by(Event.starts_at)
        .limit(5)
    ).all())

    # Meals
    meals = list(db.scalars(
        select(Meal).where(Meal.family_id == family_id).where(Meal.meal_date == today)
    ).all())

    # Encouragement
    remaining = total - completed
    if remaining == 0 and total > 0:
        encouragement = "All done for today!"
    elif remaining == 1:
        encouragement = "1 left — finish it!"
    elif remaining > 0:
        encouragement = f"{remaining} left — you've got this"
    else:
        encouragement = "No tasks today"

    return {
        "member_name": member.first_name,
        "date": today.isoformat(),
        "tasks_total": total,
        "tasks_completed": completed,
        "encouragement": encouragement,
        "weekly_wins": win_count,
        "balance_cents": balance,
        "events_today": [_event_summary(e) for e in events],
        "meals_today": [{"meal_type": m.meal_type, "title": m.title} for m in meals],
    }


def list_action_items(
    db: Session,
    family_id: uuid.UUID,
    actor_member_id: uuid.UUID,
    status_filter: str = "pending",
    limit: int = 20,
) -> list[dict]:
    """List parent action items. Requires dashboard.view_parent permission."""
    from app.services.permissions import resolve_effective_permissions
    require_member_in_family(db, family_id, actor_member_id)
    perms = resolve_effective_permissions(db, actor_member_id)
    if not perms.get("dashboard.view_parent", False):
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission required: dashboard.view_parent")

    stmt = (
        select(ParentActionItem)
        .where(ParentActionItem.family_id == family_id)
        .where(ParentActionItem.status == status_filter)
        .order_by(ParentActionItem.created_at.desc())
        .limit(limit)
    )
    items = list(db.scalars(stmt).all())
    return [_action_summary(a) for a in items]


# ============================================================================
# Helpers
# ============================================================================

def _task_summary(t: PersonalTask) -> dict:
    return {
        "id": str(t.id),
        "title": t.title,
        "priority": t.priority,
        "status": t.status,
        "due_at": t.due_at.isoformat() if t.due_at else None,
        "entity_type": "personal_task",
    }


def _event_summary(e: Event) -> dict:
    return {
        "id": str(e.id),
        "title": e.title,
        "starts_at": e.starts_at.isoformat(),
        "all_day": e.all_day,
        "source": e.source,
        "entity_type": "event",
    }


def _action_summary(a: ParentActionItem) -> dict:
    return {
        "id": str(a.id),
        "action_type": a.action_type,
        "title": a.title,
        "detail": a.detail,
        "entity_type": a.entity_type,
        "entity_id": str(a.entity_id) if a.entity_id else None,
        "status": a.status,
        "created_at": a.created_at.isoformat(),
        "created_by": str(a.created_by_member_id),
    }


def _derive_household_health(
    db: Session,
    family_id: uuid.UUID,
    child_statuses: list[dict],
    pending_actions: list,
) -> dict:
    """Derive household health status with explainable reasons."""
    reasons = []

    # Overdue tasks
    for cs in child_statuses:
        remaining = cs["tasks_total"] - cs["tasks_completed"]
        if remaining > 0:
            reasons.append({
                "type": "incomplete_tasks",
                "child": cs["name"],
                "count": remaining,
            })

    # Pending action items
    if len(pending_actions) > 3:
        reasons.append({"type": "pending_actions", "count": len(pending_actions)})

    # Pending purchase requests
    pending_req_count = db.scalar(
        select(func.count()).select_from(PurchaseRequest)
        .where(PurchaseRequest.family_id == family_id)
        .where(PurchaseRequest.status == "pending")
    ) or 0
    if pending_req_count > 0:
        reasons.append({"type": "pending_purchase_requests", "count": pending_req_count})

    # Overdue bills
    overdue_bills = db.scalar(
        select(func.count()).select_from(Bill)
        .where(Bill.family_id == family_id)
        .where(Bill.status.in_(("upcoming", "overdue")))
        .where(Bill.due_date < date.today())
    ) or 0
    if overdue_bills > 0:
        reasons.append({"type": "overdue_bills", "count": overdue_bills})

    if not reasons:
        return {"status": "on_track", "reasons": []}
    elif any(r.get("type") == "overdue_bills" for r in reasons):
        return {"status": "needs_attention", "reasons": reasons}
    elif len(reasons) >= 3:
        return {"status": "at_risk", "reasons": reasons}
    else:
        return {"status": "monitor", "reasons": reasons}

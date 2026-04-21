"""AI tool registry.

Each tool wraps an existing service function. No domain logic is duplicated.
Tools return serializable dicts for the AI to process.
"""

import uuid
import time
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.ai.provider import ToolDefinition
from app.models.ai import AIToolAudit
from app.schemas.calendar import EventCreate
from app.schemas.life_management import TaskInstanceComplete
from app.schemas.meals import MealCreate
from app.schemas.notes import NoteCreate
from app.schemas.personal_tasks import PersonalTaskCreate, PersonalTaskUpdate
from app.services import (
    calendar_service,
    chore_service,
    daily_win_service,
    family_service,
    finance_service,
    meals_service,
    notes_service,
    payout_service,
    personal_tasks_service,
    routine_service,
    task_instance_service,
)

# Confirmation-required tools (writes that affect shared data)
CONFIRMATION_REQUIRED = {
    "create_event",
    "update_event",
    "create_or_update_meal_plan",
    "mark_chore_or_routine_complete",
    "send_notification_or_create_action",
    "approve_purchase_request",
    "reject_purchase_request",
    "convert_purchase_request_to_grocery_item",
    "approve_weekly_meal_plan",
    "regenerate_meal_day",
    # Tier 4 F15: bulk weekly plan bundle. Gated just like any other
    # shared-write tool — the planner is explicitly designed to end
    # with ONE confirmation card rather than a cascade of individual
    # confirms.
    "apply_weekly_plan_bundle",
    # Phase 3 expansion: project writes are shared-write, confirmation-required.
    "create_project_from_template",
    "add_project_task",
}


def _handoff(entity_type: str, entity_id: uuid.UUID | str, route_hint: str, summary: str) -> dict:
    """Build handoff metadata for AI tool results so the UI can deep-link."""
    return {
        "entity_type": entity_type,
        "entity_id": str(entity_id),
        "route_hint": route_hint,
        "summary": summary,
    }


def _serialize(obj: Any) -> Any:
    """Convert ORM objects to dicts for AI consumption."""
    if obj is None:
        return None
    if isinstance(obj, list):
        return [_serialize(i) for i in obj]
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if hasattr(obj, "__dict__"):
        result = {}
        for k, v in obj.__dict__.items():
            if k.startswith("_"):
                continue
            result[k] = _serialize(v)
        return result
    return str(obj)


def _audit(
    db: Session,
    family_id: uuid.UUID,
    actor_id: uuid.UUID,
    conversation_id: uuid.UUID | None,
    tool_name: str,
    arguments: dict,
    result_summary: str | None = None,
    target_entity: str | None = None,
    target_id: uuid.UUID | None = None,
    status: str = "success",
    error_message: str | None = None,
    duration_ms: int | None = None,
) -> None:
    audit = AIToolAudit(
        family_id=family_id,
        actor_member_id=actor_id,
        conversation_id=conversation_id,
        tool_name=tool_name,
        arguments=arguments,
        result_summary=result_summary,
        target_entity=target_entity,
        target_id=target_id,
        status=status,
        error_message=error_message,
        duration_ms=duration_ms,
    )
    db.add(audit)
    db.flush()


class ToolExecutor:
    """Executes registered tools with safety checks and audit logging."""

    def __init__(
        self,
        db: Session,
        family_id: uuid.UUID,
        actor_member_id: uuid.UUID,
        actor_role: str,
        surface: str,
        conversation_id: uuid.UUID | None = None,
        allowed_tools: list[str] | None = None,
    ):
        self.db = db
        self.family_id = family_id
        self.actor_member_id = actor_member_id
        self.actor_role = actor_role
        self.surface = surface
        self.conversation_id = conversation_id
        self.allowed_tools = set(allowed_tools) if allowed_tools else set()

    def execute(self, tool_name: str, arguments: dict) -> dict:
        """Execute a tool by name. Returns a result dict."""
        start = time.monotonic()

        if tool_name not in self.allowed_tools:
            _audit(
                self.db, self.family_id, self.actor_member_id,
                self.conversation_id, tool_name, arguments,
                status="denied", error_message=f"Tool {tool_name} not allowed for {self.actor_role}/{self.surface}",
            )
            return {"error": f"Tool '{tool_name}' is not available for your role."}

        if tool_name in CONFIRMATION_REQUIRED:
            if not arguments.get("confirmed"):
                _audit(
                    self.db, self.family_id, self.actor_member_id,
                    self.conversation_id, tool_name, arguments,
                    status="confirmation_required",
                )
                return {
                    "confirmation_required": True,
                    "message": f"Please confirm you want to execute '{tool_name}' with these parameters.",
                    "tool_name": tool_name,
                    "arguments": arguments,
                }

        handler = _TOOL_HANDLERS.get(tool_name)
        if not handler:
            return {"error": f"Tool '{tool_name}' is not registered."}

        try:
            result = handler(self, arguments)
            elapsed = int((time.monotonic() - start) * 1000)
            _audit(
                self.db, self.family_id, self.actor_member_id,
                self.conversation_id, tool_name, arguments,
                result_summary=str(result)[:500],
                status="success",
                duration_ms=elapsed,
            )
            return result
        except Exception as e:
            elapsed = int((time.monotonic() - start) * 1000)
            _audit(
                self.db, self.family_id, self.actor_member_id,
                self.conversation_id, tool_name, arguments,
                status="error", error_message=str(e)[:500],
                duration_ms=elapsed,
            )
            return {"error": str(e)}


# ============================================================================
# Tool handler implementations
# ============================================================================

def _get_today_context(executor: ToolExecutor, args: dict) -> dict:
    from app.services import project_aggregation as _project_aggregation

    today = date.today()
    members = family_service.list_members(executor.db, executor.family_id)
    tasks = task_instance_service.list_task_instances(
        executor.db, executor.family_id, instance_date=today
    )
    events = calendar_service.list_events(
        executor.db, executor.family_id,
        start=datetime.combine(today, datetime.min.time()),
        end=datetime.combine(today, datetime.max.time()),
    )
    meals = meals_service.list_meals(executor.db, executor.family_id, meal_date=today)
    bills = finance_service.list_unpaid_bills(executor.db, executor.family_id)

    project_tasks_today = _project_aggregation.list_due_project_tasks_for_today(
        executor.db,
        family_member_id=executor.actor_member_id,
        family_id=executor.family_id,
    )

    return {
        "date": today.isoformat(),
        "family_members": _serialize(members),
        "tasks_today": _serialize(tasks),
        "events_today": _serialize(events),
        "meals_today": _serialize(meals),
        "unpaid_bills_count": len(bills),
        "project_tasks_today": _serialize(project_tasks_today),
    }


def _list_tasks(executor: ToolExecutor, args: dict) -> dict:
    member_id = args.get("member_id")
    incomplete_only = args.get("incomplete_only", False)
    tasks = personal_tasks_service.list_personal_tasks(
        executor.db, executor.family_id,
        assigned_to=uuid.UUID(member_id) if member_id else None,
        incomplete_only=incomplete_only,
    )
    return {"tasks": _serialize(tasks)}


def _create_task(executor: ToolExecutor, args: dict) -> dict:
    payload = PersonalTaskCreate(
        assigned_to=uuid.UUID(args["assigned_to"]),
        created_by=executor.actor_member_id,
        title=args["title"],
        description=args.get("description"),
        priority=args.get("priority", "medium"),
        due_at=args.get("due_at"),
    )
    task = personal_tasks_service.create_personal_task(executor.db, executor.family_id, payload)
    return {"created": _serialize(task), "handoff": _handoff("personal_task", task.id, "/personal", f"Task '{task.title}' created")}


def _update_task(executor: ToolExecutor, args: dict) -> dict:
    task_id = uuid.UUID(args["task_id"])
    update_data = {}
    for field in ("title", "description", "priority", "status", "due_at"):
        if field in args and args[field] is not None:
            update_data[field] = args[field]
    payload = PersonalTaskUpdate(**update_data)
    task = personal_tasks_service.update_personal_task(executor.db, executor.family_id, task_id, payload)
    return {"updated": _serialize(task)}


def _complete_task(executor: ToolExecutor, args: dict) -> dict:
    task_id = uuid.UUID(args["task_id"])
    task = personal_tasks_service.complete_personal_task(executor.db, executor.family_id, task_id)
    return {"completed": _serialize(task)}


def _list_chores_or_routines(executor: ToolExecutor, args: dict) -> dict:
    member_id = args.get("member_id")
    chores = chore_service.list_chore_templates(executor.db, executor.family_id)
    routines = routine_service.list_routines(
        executor.db, executor.family_id,
        member_id=uuid.UUID(member_id) if member_id else None,
    )
    today = date.today()
    instances = task_instance_service.list_task_instances(
        executor.db, executor.family_id,
        instance_date=today,
        member_id=uuid.UUID(member_id) if member_id else None,
    )
    return {
        "chore_templates": _serialize(chores),
        "routines": _serialize(routines),
        "today_instances": _serialize(instances),
    }


def _mark_chore_or_routine_complete(executor: ToolExecutor, args: dict) -> dict:
    instance_id = uuid.UUID(args["task_instance_id"])
    payload = TaskInstanceComplete()
    result = task_instance_service.mark_completed(
        executor.db, executor.family_id, instance_id, payload
    )
    return {"completed": _serialize(result)}


def _list_events(executor: ToolExecutor, args: dict) -> dict:
    start_str = args.get("start")
    end_str = args.get("end")
    start = datetime.fromisoformat(start_str) if start_str else datetime.now()
    end = datetime.fromisoformat(end_str) if end_str else datetime.now() + timedelta(days=7)
    events = calendar_service.list_events(executor.db, executor.family_id, start=start, end=end)
    return {"events": _serialize(events)}


def _create_event(executor: ToolExecutor, args: dict) -> dict:
    payload = EventCreate(
        created_by=executor.actor_member_id,
        title=args["title"],
        description=args.get("description"),
        location=args.get("location"),
        starts_at=datetime.fromisoformat(args["starts_at"]),
        ends_at=datetime.fromisoformat(args["ends_at"]),
        all_day=args.get("all_day", False),
    )
    event = calendar_service.create_event(executor.db, executor.family_id, payload)
    return {"created": _serialize(event), "handoff": _handoff("event", event.id, "/personal", f"Event '{event.title}' created")}


def _update_event(executor: ToolExecutor, args: dict) -> dict:
    from app.schemas.calendar import EventUpdate
    event_id = uuid.UUID(args["event_id"])
    update_data = {}
    for field in ("title", "description", "location", "starts_at", "ends_at", "all_day", "is_cancelled"):
        if field in args and args[field] is not None:
            update_data[field] = args[field]
    payload = EventUpdate(**update_data)
    event = calendar_service.update_event(executor.db, executor.family_id, event_id, payload)
    return {"updated": _serialize(event)}


def _list_meals_or_meal_plan(executor: ToolExecutor, args: dict) -> dict:
    meal_date = args.get("date")
    if meal_date:
        meals = meals_service.list_meals(
            executor.db, executor.family_id, meal_date=date.fromisoformat(meal_date)
        )
    else:
        meals = meals_service.list_meals(executor.db, executor.family_id, meal_date=date.today())
    plans = meals_service.list_meal_plans(executor.db, executor.family_id)
    return {"meals": _serialize(meals), "meal_plans": _serialize(plans)}


def _create_or_update_meal_plan(executor: ToolExecutor, args: dict) -> dict:
    from app.schemas.meals import MealPlanCreate
    plan = meals_service.create_meal_plan(
        executor.db, executor.family_id,
        MealPlanCreate(
            week_start=date.fromisoformat(args["week_start"]),
            created_by=executor.actor_member_id,
            notes=args.get("notes"),
        ),
    )

    created_meals = []
    for meal_data in args.get("meals", []):
        meal = meals_service.create_meal(
            executor.db, executor.family_id,
            MealCreate(
                meal_plan_id=plan.id,
                created_by=executor.actor_member_id,
                meal_date=date.fromisoformat(meal_data["date"]),
                meal_type=meal_data["meal_type"],
                title=meal_data["title"],
                description=meal_data.get("description"),
            ),
        )
        created_meals.append(meal)

    return {"plan": _serialize(plan), "meals": _serialize(created_meals)}


def _generate_grocery_list(executor: ToolExecutor, args: dict) -> dict:
    meal_date_start = args.get("start_date", date.today().isoformat())
    meal_date_end = args.get("end_date", (date.today() + timedelta(days=6)).isoformat())
    meals = meals_service.list_meals(
        executor.db, executor.family_id,
        start_date=date.fromisoformat(meal_date_start),
        end_date=date.fromisoformat(meal_date_end),
    )
    meal_titles = [m.title for m in meals]
    return {
        "meals_in_range": meal_titles,
        "note": "Grocery list generation requires the AI to derive items from meal titles and descriptions. Return the list to the user.",
    }


def _create_note(executor: ToolExecutor, args: dict) -> dict:
    payload = NoteCreate(
        family_member_id=executor.actor_member_id,
        title=args["title"],
        body=args.get("body", ""),
        category=args.get("category"),
    )
    note = notes_service.create_note(executor.db, executor.family_id, payload)
    return {"created": _serialize(note), "handoff": _handoff("note", note.id, "/personal", f"Note '{note.title}' saved")}


def _search_notes(executor: ToolExecutor, args: dict) -> dict:
    query = args.get("query", "")
    notes = notes_service.search_notes(
        executor.db, executor.family_id, query,
        family_member_id=executor.actor_member_id,
    )
    return {"notes": _serialize(notes)}


def _get_rewards_or_allowance_status(executor: ToolExecutor, args: dict) -> dict:
    member_id = args.get("member_id")
    if not member_id:
        return {"error": "member_id is required"}
    mid = uuid.UUID(member_id)
    balance = payout_service.get_balance(executor.db, executor.family_id, mid)
    today = date.today()
    dow = today.isoweekday()
    monday = today - timedelta(days=dow - 1)
    friday = monday + timedelta(days=4)
    wins = daily_win_service.list_daily_wins(
        executor.db, executor.family_id,
        member_id=mid,
        start_date=monday,
        end_date=friday,
    )
    win_count = sum(1 for w in wins if w.is_win)
    return {
        "member_id": str(mid),
        "balance_cents": balance,
        "weekly_wins": win_count,
        "weekly_wins_target": 5,
    }


def _add_grocery_item(executor: ToolExecutor, args: dict) -> dict:
    from app.services import grocery_service
    from app.schemas.grocery import GroceryItemCreate
    payload = GroceryItemCreate(
        title=args["title"],
        quantity=args.get("quantity"),
        unit=args.get("unit"),
        category=args.get("category"),
        preferred_store=args.get("preferred_store"),
        notes=args.get("notes"),
        source=args.get("source", "manual"),
    )
    item = grocery_service.create_grocery_item(executor.db, executor.family_id, executor.actor_member_id, payload)
    return {"created": _serialize(item), "handoff": _handoff("grocery_item", item.id, "/grocery", f"'{item.title}' added to grocery list")}


def _create_purchase_request(executor: ToolExecutor, args: dict) -> dict:
    from app.services import grocery_service
    from app.schemas.grocery import PurchaseRequestCreate
    payload = PurchaseRequestCreate(
        type=args.get("type", "grocery"),
        title=args["title"],
        details=args.get("details"),
        quantity=args.get("quantity"),
        unit=args.get("unit"),
        preferred_brand=args.get("preferred_brand"),
        preferred_store=args.get("preferred_store"),
        urgency=args.get("urgency"),
    )
    req = grocery_service.create_purchase_request(executor.db, executor.family_id, executor.actor_member_id, payload)
    return {"created": _serialize(req), "handoff": _handoff("purchase_request", req.id, "/grocery", f"Purchase request '{req.title}' submitted")}


def _list_purchase_requests(executor: ToolExecutor, args: dict) -> dict:
    from app.services import grocery_service
    status_filter = args.get("status")
    reqs = grocery_service.list_purchase_requests(
        executor.db, executor.family_id,
        actor_member_id=executor.actor_member_id,
        actor_role=executor.actor_role,
        status_filter=status_filter,
    )
    return {"requests": _serialize(reqs)}


def _approve_purchase_request(executor: ToolExecutor, args: dict) -> dict:
    from app.services import grocery_service
    from app.schemas.grocery import ReviewAction
    req_id = uuid.UUID(args["request_id"])
    action = ReviewAction(review_note=args.get("review_note"))
    req = grocery_service.approve_purchase_request(executor.db, executor.family_id, executor.actor_member_id, req_id, action)
    return {"approved": _serialize(req)}


def _reject_purchase_request(executor: ToolExecutor, args: dict) -> dict:
    from app.services import grocery_service
    from app.schemas.grocery import ReviewAction
    req_id = uuid.UUID(args["request_id"])
    action = ReviewAction(review_note=args.get("review_note"))
    req = grocery_service.reject_purchase_request(executor.db, executor.family_id, executor.actor_member_id, req_id, action)
    return {"rejected": _serialize(req)}


def _convert_purchase_request_to_grocery(executor: ToolExecutor, args: dict) -> dict:
    from app.services import grocery_service
    req_id = uuid.UUID(args["request_id"])
    req, item = grocery_service.convert_purchase_request_to_grocery(executor.db, executor.family_id, executor.actor_member_id, req_id)
    return {"request": _serialize(req), "grocery_item": _serialize(item)}


def _send_notification_or_create_action(executor: ToolExecutor, args: dict) -> dict:
    """Send a push if the target has an active device; otherwise fall back
    to an Action Inbox row. A push with at least one provider-accepted
    device attempt counts as delivered and does not create a duplicate
    inbox row."""
    import uuid as _uuid

    from app.models.action_items import ParentActionItem
    from app.models.foundation import FamilyMember
    from app.services import push_service

    target_raw = args.get("target_member_id")
    message = (args.get("message") or "").strip()
    title = (args.get("title") or "").strip() or "Scout notification"
    action_type = args.get("action_type") or "notification"
    route_hint = args.get("route_hint")

    if not target_raw or not message:
        return {"error": "target_member_id and message are required"}

    try:
        target_id = _uuid.UUID(str(target_raw))
    except (TypeError, ValueError):
        return {"error": "target_member_id is not a valid uuid"}

    target = executor.db.get(FamilyMember, target_id)
    if target is None or target.family_id != executor.family_id:
        return {"error": "target member not found in your family"}

    data: dict = {"action_type": action_type, "source": "ai_tool"}
    if route_hint:
        data["route_hint"] = route_hint

    push_result = push_service.send_push(
        executor.db,
        family_member_id=target_id,
        category=action_type,
        title=title,
        body=message,
        data=data,
        trigger_source="ai.send_notification_or_create_action",
    )

    if push_result.accepted_count > 0:
        return {
            "status": "push_delivered",
            "notification_group_id": str(push_result.notification_group_id),
            "accepted_count": push_result.accepted_count,
            "error_count": push_result.error_count,
            "target_member_id": str(target_id),
        }

    # No active devices, or every device attempt was rejected at
    # provider submission. Preserve the Action Inbox path so the
    # message is not silently lost. parent_action_items.action_type
    # is bounded by a CHECK constraint — use the always-valid
    # 'general' bucket and keep the AI's semantic action_type in
    # the detail/title.
    inbox = ParentActionItem(
        family_id=executor.family_id,
        created_by_member_id=executor.actor_member_id,
        action_type="general",
        title=title,
        detail=message,
        entity_type="family_member",
        entity_id=target_id,
        status="pending",
    )
    executor.db.add(inbox)
    executor.db.flush()

    return {
        "status": "fallback_action_inbox",
        "action_item_id": str(inbox.id),
        "target_member_id": str(target_id),
        "push_accepted_count": 0,
        "push_error_count": push_result.error_count,
    }


# ---- Weekly meal plans --------------------------------------------------


def _generate_weekly_meal_plan(executor: ToolExecutor, args: dict) -> dict:
    from app.services import weekly_meal_plan_service
    week_start = date.fromisoformat(args["week_start_date"])
    result = weekly_meal_plan_service.generate_weekly_meal_plan(
        executor.db,
        executor.family_id,
        executor.actor_member_id,
        week_start_date=week_start,
        extra_constraints=args.get("constraints"),
        answers=args.get("answers"),
    )
    if result["status"] == "needs_clarification":
        return {
            "status": "needs_clarification",
            "questions": result["questions"],
        }
    plan_id = result["plan_id"]
    return {
        "status": "ready",
        "plan_id": str(plan_id),
        "summary": result.get("summary"),
        "handoff": _handoff(
            "weekly_meal_plan", plan_id, "/meals/this-week",
            "Weekly meal plan draft saved. Review and approve.",
        ),
    }


def _get_current_weekly_meal_plan(executor: ToolExecutor, args: dict) -> dict:
    from app.services import weekly_meal_plan_service
    plan = weekly_meal_plan_service.get_current_weekly_meal_plan(
        executor.db, executor.family_id, actor_member_id=executor.actor_member_id,
    )
    if not plan:
        return {"plan": None}
    return {"plan": _serialize(plan)}


def _approve_weekly_meal_plan(executor: ToolExecutor, args: dict) -> dict:
    from app.services import weekly_meal_plan_service
    plan_id = uuid.UUID(args["plan_id"])
    plan = weekly_meal_plan_service.approve_weekly_meal_plan(
        executor.db, executor.family_id, executor.actor_member_id, plan_id
    )
    return {
        "approved": _serialize(plan),
        "handoff": _handoff(
            "weekly_meal_plan", plan.id, "/meals/this-week",
            f"Weekly meal plan for {plan.week_start_date.isoformat()} approved",
        ),
    }


def _regenerate_meal_day(executor: ToolExecutor, args: dict) -> dict:
    from app.services import weekly_meal_plan_service
    plan_id = uuid.UUID(args["plan_id"])
    plan = weekly_meal_plan_service.regenerate_day(
        executor.db,
        executor.family_id,
        executor.actor_member_id,
        plan_id,
        day=args["day"],
        meal_types=args.get("meal_types"),
    )
    return {"regenerated": _serialize(plan)}


def _add_meal_review(executor: ToolExecutor, args: dict) -> dict:
    from app.services import weekly_meal_plan_service
    from app.schemas.meals import MealReviewCreate
    payload = MealReviewCreate(
        member_id=executor.actor_member_id,
        weekly_plan_id=uuid.UUID(args["weekly_plan_id"]) if args.get("weekly_plan_id") else None,
        linked_meal_ref=args.get("linked_meal_ref"),
        meal_title=args["meal_title"],
        rating_overall=int(args["rating_overall"]),
        kid_acceptance=int(args["kid_acceptance"]) if args.get("kid_acceptance") is not None else None,
        effort=int(args["effort"]) if args.get("effort") is not None else None,
        cleanup=int(args["cleanup"]) if args.get("cleanup") is not None else None,
        leftovers=args.get("leftovers"),
        repeat_decision=args["repeat_decision"],
        notes=args.get("notes"),
    )
    review = weekly_meal_plan_service.create_meal_review(executor.db, executor.family_id, payload)
    return {
        "created": _serialize(review),
        "handoff": _handoff(
            "meal_review", review.id, "/meals/reviews",
            f"Review saved for '{review.meal_title}'",
        ),
    }


def _get_meal_review_summary(executor: ToolExecutor, args: dict) -> dict:
    from app.services import weekly_meal_plan_service
    summary = weekly_meal_plan_service.get_meal_review_summary(executor.db, executor.family_id)
    return {"summary": summary.model_dump()}


def _get_weather(executor: ToolExecutor, args: dict) -> dict:
    """Fetch a short-range forecast via Open-Meteo (free, no API key).

    Resolves `location` (zip, city, or city, state) via Open-Meteo's
    geocoding API, then hits the forecast API for daily high/low,
    precip probability, and a WMO weather code. If no location is
    given, falls back to the family's `home_location`.
    """
    import json
    import urllib.parse
    import urllib.request
    from app.models.foundation import Family

    location = (args.get("location") or "").strip()
    days = args.get("days")
    if not isinstance(days, int) or days < 1 or days > 7:
        days = 3

    if not location:
        fam = executor.db.get(Family, executor.family_id)
        location = (fam.home_location or "") if fam else ""
    if not location:
        return {
            "error": (
                "No location provided and no home_location set on the family. "
                "Ask the user for a zip code or city."
            )
        }

    try:
        geo_url = (
            "https://geocoding-api.open-meteo.com/v1/search?"
            + urllib.parse.urlencode({"name": location, "count": 1, "language": "en", "format": "json"})
        )
        with urllib.request.urlopen(geo_url, timeout=8) as resp:
            geo = json.loads(resp.read().decode())
        results = geo.get("results") or []
        if not results:
            return {"error": f"Could not find a location for '{location}'."}
        top = results[0]
        lat = top["latitude"]
        lon = top["longitude"]
        resolved_name = ", ".join(
            filter(None, [top.get("name"), top.get("admin1"), top.get("country_code")])
        )
    except Exception as e:
        return {"error": f"Geocoding failed for '{location}': {type(e).__name__}"}

    try:
        forecast_url = (
            "https://api.open-meteo.com/v1/forecast?"
            + urllib.parse.urlencode(
                {
                    "latitude": lat,
                    "longitude": lon,
                    "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code",
                    "temperature_unit": "fahrenheit",
                    "timezone": "auto",
                    "forecast_days": days,
                }
            )
        )
        with urllib.request.urlopen(forecast_url, timeout=8) as resp:
            forecast = json.loads(resp.read().decode())
    except Exception as e:
        return {"error": f"Forecast fetch failed: {type(e).__name__}"}

    daily = forecast.get("daily") or {}
    dates = daily.get("time") or []
    highs = daily.get("temperature_2m_max") or []
    lows = daily.get("temperature_2m_min") or []
    precip = daily.get("precipitation_probability_max") or []
    codes = daily.get("weather_code") or []

    # WMO weather code → short human label (subset; anything unknown → "weather")
    wmo = {
        0: "clear",
        1: "mostly clear",
        2: "partly cloudy",
        3: "cloudy",
        45: "fog",
        48: "rime fog",
        51: "light drizzle",
        53: "drizzle",
        55: "heavy drizzle",
        61: "light rain",
        63: "rain",
        65: "heavy rain",
        66: "freezing rain",
        67: "heavy freezing rain",
        71: "light snow",
        73: "snow",
        75: "heavy snow",
        77: "snow grains",
        80: "rain showers",
        81: "heavy rain showers",
        82: "violent rain showers",
        85: "snow showers",
        86: "heavy snow showers",
        95: "thunderstorm",
        96: "thunderstorm with hail",
        99: "severe thunderstorm with hail",
    }

    out_days = []
    for i, day in enumerate(dates):
        out_days.append(
            {
                "date": day,
                "high_f": highs[i] if i < len(highs) else None,
                "low_f": lows[i] if i < len(lows) else None,
                "precip_probability_pct": precip[i] if i < len(precip) else None,
                "weather": wmo.get(codes[i] if i < len(codes) else -1, "weather"),
            }
        )

    return {
        "location": resolved_name or location,
        "units": "fahrenheit",
        "days": out_days,
    }


# ============================================================================
# Handler registry
# ============================================================================

# ---- Tier 4 F15: bulk weekly plan bundle -----------------------------------


def _apply_weekly_plan_bundle(executor: ToolExecutor, args: dict) -> dict:
    """Atomically apply a bulk weekly plan (Tier 5 F16).

    Writes tasks, events, and grocery adds in a single transaction
    via the ``*_nocommit`` service helpers. If any individual write
    raises, the *entire* bundle rolls back — no partial state ever
    lands. This replaces the earlier best-effort implementation,
    which was constrained by the per-entity commits inside the
    service layer.

    Idempotency: callers pass ``bundle_apply_id`` (any stable string;
    the planner UX generates one when drafting the bundle). A repeat
    call with the same id returns the previously-stored result
    instead of re-writing. Double-taps on the confirm button are
    therefore no-ops.

    Still CONFIRMATION_REQUIRED-gated. The first call returns
    ``confirmation_required=True``; the second call (via the
    ``confirm_tool`` direct path with ``confirmed=True``) runs the
    atomic apply below.

    Expected args shape::

        {
          "summary": "plain text recap for the parent",
          "bundle_apply_id": "bundle-xyz",   # required for idempotency
          "tasks": [{"assigned_to": "<uuid>", "title": "...", "priority": "medium"}],
          "events": [{"title": "...", "starts_at": "...", "ends_at": "..."}],
          "grocery_items": [{"title": "..."}],
          "meal_plan_reference": "<plan_id-or-null>",
          "confirmed": true  # set by confirm_tool path
        }
    """
    from app.models.tier5 import PlannerBundleApply
    from app.schemas.grocery import GroceryItemCreate
    from app.services import grocery_service
    from sqlalchemy import select

    summary = args.get("summary") or ""
    # QA fix (test_qa BUG #3): if the caller omits bundle_apply_id we
    # auto-generate a server-side fallback so we always write a
    # ledger row for audit. Idempotency only kicks in when the
    # caller supplies a stable id, but missing the id should not
    # mean missing the audit trail.
    caller_bundle_id = (args.get("bundle_apply_id") or "").strip()
    auto_generated_bundle_id = not caller_bundle_id
    bundle_apply_id = caller_bundle_id or f"auto-{uuid.uuid4().hex}"
    tasks = args.get("tasks") or []
    events = args.get("events") or []
    grocery_items = args.get("grocery_items") or []
    meal_plan_reference = args.get("meal_plan_reference")

    tasks = [t for t in tasks if isinstance(t, dict) and t.get("title")]
    events = [e for e in events if isinstance(e, dict) and e.get("title")]
    grocery_items = [
        g for g in grocery_items if isinstance(g, dict) and g.get("title")
    ]

    # Idempotency: if a prior row exists for this bundle_apply_id +
    # family, return the stored result. Double-taps become no-ops.
    # Only caller-supplied ids trigger dedupe — auto-generated ones
    # are unique per call by construction so the lookup would always
    # miss anyway.
    if not auto_generated_bundle_id:
        existing = executor.db.scalars(
            select(PlannerBundleApply)
            .where(PlannerBundleApply.family_id == executor.family_id)
            .where(PlannerBundleApply.bundle_apply_id == bundle_apply_id)
        ).first()
        if existing is not None:
            return {
                "status": existing.status,
                "idempotent_replay": True,
                "summary": existing.summary or summary,
                "applied": {
                    "tasks_created": existing.tasks_created,
                    "events_created": existing.events_created,
                    "grocery_items_created": existing.grocery_items_created,
                    "meal_plan_reference": meal_plan_reference,
                },
                "errors": existing.errors or [],
                "handoff": _handoff(
                    "weekly_plan_bundle",
                    "bundle",
                    "/parent",
                    (
                        f"Weekly plan already applied: "
                        f"{existing.tasks_created} tasks, "
                        f"{existing.events_created} events, "
                        f"{existing.grocery_items_created} grocery items."
                    ),
                ),
            }

    applied = {
        "tasks_created": 0,
        "events_created": 0,
        "grocery_items_created": 0,
        "meal_plan_reference": meal_plan_reference,
    }

    # Single savepoint around every write. Any exception raised
    # inside the block triggers rollback of the WHOLE bundle — no
    # partial state can land. The per-service *_nocommit helpers
    # flush but never commit, so they play nicely with the savepoint.
    try:
        with executor.db.begin_nested():
            for t in tasks:
                payload = PersonalTaskCreate(
                    assigned_to=(
                        uuid.UUID(t["assigned_to"])
                        if t.get("assigned_to")
                        else executor.actor_member_id
                    ),
                    created_by=executor.actor_member_id,
                    title=t["title"],
                    description=t.get("description"),
                    priority=t.get("priority", "medium"),
                    due_at=t.get("due_at"),
                )
                personal_tasks_service.create_personal_task_nocommit(
                    executor.db, executor.family_id, payload
                )
                applied["tasks_created"] += 1

            for e in events:
                epayload = EventCreate(
                    created_by=executor.actor_member_id,
                    title=e["title"],
                    description=e.get("description"),
                    location=e.get("location"),
                    starts_at=datetime.fromisoformat(e["starts_at"]),
                    ends_at=datetime.fromisoformat(e["ends_at"]),
                    all_day=e.get("all_day", False),
                )
                calendar_service.create_event_nocommit(
                    executor.db, executor.family_id, epayload
                )
                applied["events_created"] += 1

            for g in grocery_items:
                gpayload = GroceryItemCreate(
                    title=g["title"],
                    quantity=g.get("quantity"),
                    unit=g.get("unit"),
                    category=g.get("category"),
                    preferred_store=g.get("preferred_store"),
                    notes=g.get("notes"),
                )
                grocery_service.create_grocery_item_nocommit(
                    executor.db,
                    executor.family_id,
                    executor.actor_member_id,
                    gpayload,
                )
                applied["grocery_items_created"] += 1

            # Ledger row inside the same savepoint so a later failure
            # still rolls it back. Always written now (auto-generated
            # id when the caller omits one) so audit is never silent.
            ledger = PlannerBundleApply(
                bundle_apply_id=bundle_apply_id,
                family_id=executor.family_id,
                actor_member_id=executor.actor_member_id,
                conversation_id=executor.conversation_id,
                status="applied",
                tasks_created=applied["tasks_created"],
                events_created=applied["events_created"],
                grocery_items_created=applied["grocery_items_created"],
                errors=[],
                summary=summary,
            )
            executor.db.add(ledger)
            executor.db.flush()
    except Exception as exc:
        # Savepoint has rolled back. Nothing landed. Record a
        # failure ledger row in its own savepoint (so a second
        # apply with the same id gets the failure back) and return
        # a clean error to the UI.
        err_msg = str(exc)[:500]
        try:
            with executor.db.begin_nested():
                fail = PlannerBundleApply(
                    bundle_apply_id=bundle_apply_id,
                    family_id=executor.family_id,
                    actor_member_id=executor.actor_member_id,
                    conversation_id=executor.conversation_id,
                    status="failed",
                    tasks_created=0,
                    events_created=0,
                    grocery_items_created=0,
                    errors=[err_msg],
                    summary=summary,
                )
                executor.db.add(fail)
                executor.db.flush()
        except Exception:
            pass
        return {
            "status": "failed",
            "summary": summary,
            "applied": {
                "tasks_created": 0,
                "events_created": 0,
                "grocery_items_created": 0,
                "meal_plan_reference": meal_plan_reference,
            },
            "errors": [err_msg],
        }

    # Optional: auto-memory write for the approved meal plan reference
    # (Tier 5 F20 integration). Pure best-effort — memory failures
    # must not poison a successful bundle.
    try:
        if meal_plan_reference:
            from app.ai.memory import record_auto_structured_memory

            record_auto_structured_memory(
                executor.db,
                family_id=executor.family_id,
                memory_type="planning_default",
                scope="family",
                content=(
                    f"Weekly planner last approved a plan linked to "
                    f"meal_plan_reference={meal_plan_reference}."
                ),
                source_conversation_id=executor.conversation_id,
            )
    except Exception:
        pass

    return {
        "status": "applied",
        "summary": summary,
        "applied": applied,
        "errors": [],
        "bundle_apply_id": bundle_apply_id,
        "handoff": _handoff(
            "weekly_plan_bundle",
            "bundle",
            "/parent",
            (
                f"Weekly plan applied: {applied['tasks_created']} tasks, "
                f"{applied['events_created']} events, "
                f"{applied['grocery_items_created']} grocery items."
            ),
        ),
    }


def _create_project_from_template(executor: ToolExecutor, args: dict) -> dict:
    import uuid as _uuid
    from datetime import date as _date

    from app.services import project_service

    tpl_raw = args.get("project_template_id")
    start_raw = args.get("start_date")
    name_override = args.get("name_override")
    if not tpl_raw or not start_raw:
        return {"error": "project_template_id and start_date are required"}
    try:
        tpl_id = _uuid.UUID(str(tpl_raw))
        start = _date.fromisoformat(str(start_raw))
    except (TypeError, ValueError):
        return {"error": "invalid project_template_id or start_date"}
    try:
        project = project_service.create_from_template(
            executor.db,
            family_id=executor.family_id,
            created_by_family_member_id=executor.actor_member_id,
            project_template_id=tpl_id,
            start_date=start,
            name_override=name_override,
        )
    except ValueError as e:
        return {"error": str(e)}
    return {
        "status": "created",
        "project_id": str(project.id),
        "name": project.name,
        "start_date": project.start_date.isoformat(),
    }


def _add_project_task(executor: ToolExecutor, args: dict) -> dict:
    import uuid as _uuid
    from datetime import date as _date

    from app.models.projects import Project
    from app.services import project_service

    project_raw = args.get("project_id")
    title = (args.get("title") or "").strip()
    if not project_raw or not title:
        return {"error": "project_id and title are required"}
    try:
        project_id = _uuid.UUID(str(project_raw))
    except (TypeError, ValueError):
        return {"error": "invalid project_id"}

    project = executor.db.get(Project, project_id)
    if project is None or project.family_id != executor.family_id:
        return {"error": "project not found in your family"}

    due = None
    if args.get("due_date"):
        try:
            due = _date.fromisoformat(str(args["due_date"]))
        except ValueError:
            return {"error": "invalid due_date"}

    owner = None
    if args.get("owner_family_member_id"):
        try:
            owner = _uuid.UUID(str(args["owner_family_member_id"]))
        except ValueError:
            return {"error": "invalid owner_family_member_id"}

    task = project_service.add_task(
        executor.db,
        project_id=project.id,
        title=title,
        due_date=due,
        owner_family_member_id=owner,
    )
    return {
        "status": "created",
        "project_task_id": str(task.id),
        "project_id": str(project.id),
        "title": task.title,
    }


_TOOL_HANDLERS: dict[str, Any] = {
    "get_today_context": _get_today_context,
    "list_tasks": _list_tasks,
    "create_task": _create_task,
    "update_task": _update_task,
    "complete_task": _complete_task,
    "list_chores_or_routines": _list_chores_or_routines,
    "mark_chore_or_routine_complete": _mark_chore_or_routine_complete,
    "list_events": _list_events,
    "create_event": _create_event,
    "update_event": _update_event,
    "list_meals_or_meal_plan": _list_meals_or_meal_plan,
    "create_or_update_meal_plan": _create_or_update_meal_plan,
    "generate_grocery_list": _generate_grocery_list,
    "create_note": _create_note,
    "search_notes": _search_notes,
    "get_rewards_or_allowance_status": _get_rewards_or_allowance_status,
    "send_notification_or_create_action": _send_notification_or_create_action,
    "add_grocery_item": _add_grocery_item,
    "create_purchase_request": _create_purchase_request,
    "list_purchase_requests": _list_purchase_requests,
    "approve_purchase_request": _approve_purchase_request,
    "reject_purchase_request": _reject_purchase_request,
    "convert_purchase_request_to_grocery_item": _convert_purchase_request_to_grocery,
    "generate_weekly_meal_plan": _generate_weekly_meal_plan,
    "get_current_weekly_meal_plan": _get_current_weekly_meal_plan,
    "approve_weekly_meal_plan": _approve_weekly_meal_plan,
    "regenerate_meal_day": _regenerate_meal_day,
    "add_meal_review": _add_meal_review,
    "get_meal_review_summary": _get_meal_review_summary,
    "get_weather": _get_weather,
    "apply_weekly_plan_bundle": _apply_weekly_plan_bundle,
    "create_project_from_template": _create_project_from_template,
    "add_project_task": _add_project_task,
}


# ============================================================================
# Tool definitions for Anthropic API
# ============================================================================

TOOL_DEFINITIONS: dict[str, ToolDefinition] = {
    "get_today_context": ToolDefinition(
        name="get_today_context",
        description="Get a comprehensive snapshot of today: tasks, events, meals, and bills for the family.",
        input_schema={"type": "object", "properties": {}, "required": []},
    ),
    "list_tasks": ToolDefinition(
        name="list_tasks",
        description="List personal tasks. Optionally filter by member_id or incomplete_only.",
        input_schema={
            "type": "object",
            "properties": {
                "member_id": {"type": "string", "description": "UUID of the family member"},
                "incomplete_only": {"type": "boolean", "default": False},
            },
        },
    ),
    "create_task": ToolDefinition(
        name="create_task",
        description="Create a new personal task.",
        input_schema={
            "type": "object",
            "properties": {
                "assigned_to": {"type": "string", "description": "UUID of the assignee"},
                "title": {"type": "string"},
                "description": {"type": "string"},
                "priority": {"type": "string", "enum": ["low", "medium", "high", "urgent"]},
                "due_at": {"type": "string", "description": "ISO datetime"},
            },
            "required": ["assigned_to", "title"],
        },
    ),
    "update_task": ToolDefinition(
        name="update_task",
        description="Update an existing personal task.",
        input_schema={
            "type": "object",
            "properties": {
                "task_id": {"type": "string"},
                "title": {"type": "string"},
                "description": {"type": "string"},
                "priority": {"type": "string"},
                "status": {"type": "string"},
                "due_at": {"type": "string"},
            },
            "required": ["task_id"],
        },
    ),
    "complete_task": ToolDefinition(
        name="complete_task",
        description="Mark a personal task as complete.",
        input_schema={"type": "object", "properties": {"task_id": {"type": "string"}}, "required": ["task_id"]},
    ),
    "list_chores_or_routines": ToolDefinition(
        name="list_chores_or_routines",
        description="List chore templates, routines, and today's task instances. Optionally filter by member_id.",
        input_schema={"type": "object", "properties": {"member_id": {"type": "string"}}},
    ),
    "mark_chore_or_routine_complete": ToolDefinition(
        name="mark_chore_or_routine_complete",
        description="Mark a specific chore or routine task instance as complete.",
        input_schema={
            "type": "object",
            "properties": {
                "task_instance_id": {"type": "string"},
                "confirmed": {"type": "boolean", "description": "Must be true to execute"},
            },
            "required": ["task_instance_id"],
        },
    ),
    "list_events": ToolDefinition(
        name="list_events",
        description="List calendar events in a date range.",
        input_schema={
            "type": "object",
            "properties": {
                "start": {"type": "string", "description": "ISO datetime"},
                "end": {"type": "string", "description": "ISO datetime"},
            },
        },
    ),
    "create_event": ToolDefinition(
        name="create_event",
        description="Create a calendar event.",
        input_schema={
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "description": {"type": "string"},
                "location": {"type": "string"},
                "starts_at": {"type": "string"},
                "ends_at": {"type": "string"},
                "all_day": {"type": "boolean"},
                "confirmed": {"type": "boolean"},
            },
            "required": ["title", "starts_at", "ends_at"],
        },
    ),
    "update_event": ToolDefinition(
        name="update_event",
        description="Update a calendar event.",
        input_schema={
            "type": "object",
            "properties": {
                "event_id": {"type": "string"},
                "title": {"type": "string"},
                "description": {"type": "string"},
                "location": {"type": "string"},
                "starts_at": {"type": "string"},
                "ends_at": {"type": "string"},
                "is_cancelled": {"type": "boolean"},
                "confirmed": {"type": "boolean"},
            },
            "required": ["event_id"],
        },
    ),
    "list_meals_or_meal_plan": ToolDefinition(
        name="list_meals_or_meal_plan",
        description="List meals for a date or current meal plans.",
        input_schema={"type": "object", "properties": {"date": {"type": "string", "description": "YYYY-MM-DD"}}},
    ),
    "create_or_update_meal_plan": ToolDefinition(
        name="create_or_update_meal_plan",
        description="Create a weekly meal plan with individual meals.",
        input_schema={
            "type": "object",
            "properties": {
                "week_start": {"type": "string", "description": "Monday date YYYY-MM-DD"},
                "notes": {"type": "string"},
                "meals": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "date": {"type": "string"},
                            "meal_type": {"type": "string", "enum": ["breakfast", "lunch", "dinner", "snack"]},
                            "title": {"type": "string"},
                            "description": {"type": "string"},
                        },
                        "required": ["date", "meal_type", "title"],
                    },
                },
                "confirmed": {"type": "boolean"},
            },
            "required": ["week_start"],
        },
    ),
    "generate_grocery_list": ToolDefinition(
        name="generate_grocery_list",
        description="Get meal titles for a date range to generate a grocery list.",
        input_schema={
            "type": "object",
            "properties": {
                "start_date": {"type": "string"},
                "end_date": {"type": "string"},
            },
        },
    ),
    "create_note": ToolDefinition(
        name="create_note",
        description="Create a new note in the second brain.",
        input_schema={
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "body": {"type": "string"},
                "category": {"type": "string"},
            },
            "required": ["title"],
        },
    ),
    "search_notes": ToolDefinition(
        name="search_notes",
        description="Search notes by keyword.",
        input_schema={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    ),
    "get_rewards_or_allowance_status": ToolDefinition(
        name="get_rewards_or_allowance_status",
        description="Get allowance balance and weekly win progress for a child.",
        input_schema={"type": "object", "properties": {"member_id": {"type": "string"}}, "required": ["member_id"]},
    ),
    "send_notification_or_create_action": ToolDefinition(
        name="send_notification_or_create_action",
        description=(
            "Deliver a push notification to a family member. If the target "
            "has no active device, falls back to an Action Inbox item. Parent-only."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "target_member_id": {"type": "string"},
                "title": {"type": "string"},
                "message": {"type": "string"},
                "action_type": {"type": "string", "enum": ["notification", "reminder", "action"]},
                "route_hint": {"type": "string"},
                "confirmed": {"type": "boolean"},
            },
            "required": ["target_member_id", "message"],
        },
    ),
    "add_grocery_item": ToolDefinition(
        name="add_grocery_item",
        description="Add an item to the family grocery list.",
        input_schema={
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "quantity": {"type": "number"},
                "unit": {"type": "string"},
                "category": {"type": "string"},
                "preferred_store": {"type": "string"},
                "notes": {"type": "string"},
                "source": {"type": "string", "enum": ["manual", "meal_ai"]},
            },
            "required": ["title"],
        },
    ),
    "create_purchase_request": ToolDefinition(
        name="create_purchase_request",
        description="Create a purchase request for non-routine items needing approval.",
        input_schema={
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "type": {"type": "string", "enum": ["grocery", "household", "personal", "other"]},
                "details": {"type": "string"},
                "quantity": {"type": "number"},
                "unit": {"type": "string"},
                "preferred_brand": {"type": "string"},
                "preferred_store": {"type": "string"},
                "urgency": {"type": "string", "enum": ["low", "normal", "high", "urgent"]},
            },
            "required": ["title"],
        },
    ),
    "list_purchase_requests": ToolDefinition(
        name="list_purchase_requests",
        description="List purchase requests. Optionally filter by status.",
        input_schema={
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["pending", "approved", "rejected", "converted", "fulfilled"]},
            },
        },
    ),
    "approve_purchase_request": ToolDefinition(
        name="approve_purchase_request",
        description="Approve a pending purchase request. Parent-only.",
        input_schema={
            "type": "object",
            "properties": {
                "request_id": {"type": "string"},
                "review_note": {"type": "string"},
                "confirmed": {"type": "boolean"},
            },
            "required": ["request_id"],
        },
    ),
    "reject_purchase_request": ToolDefinition(
        name="reject_purchase_request",
        description="Reject a pending purchase request. Parent-only.",
        input_schema={
            "type": "object",
            "properties": {
                "request_id": {"type": "string"},
                "review_note": {"type": "string"},
                "confirmed": {"type": "boolean"},
            },
            "required": ["request_id"],
        },
    ),
    "convert_purchase_request_to_grocery_item": ToolDefinition(
        name="convert_purchase_request_to_grocery_item",
        description="Convert a purchase request into an active grocery item. Parent-only.",
        input_schema={
            "type": "object",
            "properties": {
                "request_id": {"type": "string"},
                "confirmed": {"type": "boolean"},
            },
            "required": ["request_id"],
        },
    ),
    "generate_weekly_meal_plan": ToolDefinition(
        name="generate_weekly_meal_plan",
        description=(
            "Ask clarifying questions if needed, otherwise generate and save a draft weekly meal plan. "
            "Adults only. Returns either {status:'needs_clarification',questions:[...]} or "
            "{status:'ready',plan_id,summary}. No prose."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "week_start_date": {"type": "string", "description": "Monday date YYYY-MM-DD"},
                "constraints": {"type": "object", "description": "Optional extra constraints (budget, time, cuisines)"},
                "answers": {"type": "object", "description": "Prior clarifying-question answers keyed by question key"},
            },
            "required": ["week_start_date"],
        },
    ),
    "get_current_weekly_meal_plan": ToolDefinition(
        name="get_current_weekly_meal_plan",
        description="Get the family's current weekly meal plan (draft or approved, most recent non-archived).",
        input_schema={"type": "object", "properties": {}, "required": []},
    ),
    "approve_weekly_meal_plan": ToolDefinition(
        name="approve_weekly_meal_plan",
        description="Approve a draft weekly meal plan. Syncs grocery items and resolves the parent review action. Adults only.",
        input_schema={
            "type": "object",
            "properties": {
                "plan_id": {"type": "string"},
                "confirmed": {"type": "boolean"},
            },
            "required": ["plan_id"],
        },
    ),
    "regenerate_meal_day": ToolDefinition(
        name="regenerate_meal_day",
        description="Replace one day's dinner (or listed meal types) in an existing plan. Adults only.",
        input_schema={
            "type": "object",
            "properties": {
                "plan_id": {"type": "string"},
                "day": {"type": "string", "enum": list(["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"])},
                "meal_types": {"type": "array", "items": {"type": "string"}},
                "confirmed": {"type": "boolean"},
            },
            "required": ["plan_id", "day"],
        },
    ),
    "add_meal_review": ToolDefinition(
        name="add_meal_review",
        description="Submit a structured meal review. Available to adults and children.",
        input_schema={
            "type": "object",
            "properties": {
                "weekly_plan_id": {"type": "string"},
                "linked_meal_ref": {"type": "string"},
                "meal_title": {"type": "string"},
                "rating_overall": {"type": "integer", "minimum": 1, "maximum": 5},
                "kid_acceptance": {"type": "integer", "minimum": 1, "maximum": 5},
                "effort": {"type": "integer", "minimum": 1, "maximum": 5},
                "cleanup": {"type": "integer", "minimum": 1, "maximum": 5},
                "leftovers": {"type": "string", "enum": ["none", "some", "plenty"]},
                "repeat_decision": {"type": "string", "enum": ["repeat", "tweak", "retire"]},
                "notes": {"type": "string"},
            },
            "required": ["meal_title", "rating_overall", "repeat_decision"],
        },
    ),
    "get_meal_review_summary": ToolDefinition(
        name="get_meal_review_summary",
        description="Get compact review signals: high-rated meals, retired meals, low kid acceptance, good leftover performers, low-effort favorites.",
        input_schema={"type": "object", "properties": {}, "required": []},
    ),
    "get_weather": ToolDefinition(
        name="get_weather",
        description=(
            "Get a short-range weather forecast (today through up to 7 days). "
            "Call this whenever the user asks about weather, rain, temperature, "
            "or outdoor plans. Defaults to the family's home location if no "
            "location is provided."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": (
                        "Optional. A zip code, city name, or 'city, state' — "
                        "e.g. '76126', 'Fort Worth', 'Fort Worth, TX'. If "
                        "omitted, uses the family's home_location."
                    ),
                },
                "days": {
                    "type": "integer",
                    "description": (
                        "How many days to forecast (1-7). Defaults to 3."
                    ),
                    "minimum": 1,
                    "maximum": 7,
                },
            },
            "required": [],
        },
    ),
    "apply_weekly_plan_bundle": ToolDefinition(
        name="apply_weekly_plan_bundle",
        description=(
            "Weekly-plan-only bulk write tool. Applies a proposed "
            "bundle of task, event, and grocery changes in a single "
            "atomic confirmation. The first call returns "
            "confirmation_required=True so the ScoutPanel can render "
            "ONE review card to the parent. The second call (via the "
            "confirm flow) actually writes the bundle. Use this only "
            "in weekly_plan intent — never in ordinary chat."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "Plain-text recap for the parent review card.",
                },
                "bundle_apply_id": {
                    "type": "string",
                    "description": (
                        "Stable idempotency key for this bundle. Generate "
                        "ONCE per distinct plan draft (e.g. 'bundle-' + "
                        "short uuid). A repeat apply with the same id "
                        "returns the original result and does not "
                        "re-write."
                    ),
                },
                "tasks": {
                    "type": "array",
                    "description": "Personal tasks to create.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "assigned_to": {"type": "string"},
                            "title": {"type": "string"},
                            "description": {"type": "string"},
                            "priority": {"type": "string"},
                            "due_at": {"type": "string"},
                        },
                        "required": ["title"],
                    },
                },
                "events": {
                    "type": "array",
                    "description": "Calendar events to create.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "description": {"type": "string"},
                            "location": {"type": "string"},
                            "starts_at": {"type": "string"},
                            "ends_at": {"type": "string"},
                            "all_day": {"type": "boolean"},
                        },
                        "required": ["title", "starts_at", "ends_at"],
                    },
                },
                "grocery_items": {
                    "type": "array",
                    "description": "Grocery items to add.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "quantity": {"type": "number"},
                            "unit": {"type": "string"},
                            "category": {"type": "string"},
                            "preferred_store": {"type": "string"},
                        },
                        "required": ["title"],
                    },
                },
                "meal_plan_reference": {
                    "type": "string",
                    "description": (
                        "Optional. ID of an already-drafted weekly meal plan "
                        "so the approve step can link to it."
                    ),
                },
            },
            "required": ["summary"],
        },
    ),
    "create_project_from_template": ToolDefinition(
        name="create_project_from_template",
        description=(
            "Instantiate a new family project from an existing template. "
            "Confirmation required. Copies every template task into the "
            "new project with due dates computed from `start_date` + the "
            "task's `relative_day_offset`."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "project_template_id": {"type": "string"},
                "start_date": {"type": "string", "description": "ISO YYYY-MM-DD"},
                "name_override": {"type": "string"},
                "confirmed": {"type": "boolean"},
            },
            "required": ["project_template_id", "start_date"],
        },
    ),
    "add_project_task": ToolDefinition(
        name="add_project_task",
        description=(
            "Add a task to an existing family project. Confirmation "
            "required. Owner and due date are optional."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "title": {"type": "string"},
                "due_date": {"type": "string"},
                "owner_family_member_id": {"type": "string"},
                "confirmed": {"type": "boolean"},
            },
            "required": ["project_id", "title"],
        },
    ),
}

"""Weekly meal plan workflow.

Turns Scout AI meal output into a saved, approvable product surface.

Contract with the AI: the model returns exactly one of two shapes.

A. needs_clarification
   {
     "status": "needs_clarification",
     "questions": [{"key": "...", "question": "...", "hint": "..."}]
   }

B. ready
   {
     "status": "ready",
     "week_plan":  {"dinners": {weekday: {title, description, tags?}}, "breakfast": {...}, "lunch": {...}, "snacks": [...]},
     "prep_plan":  {"tasks": [{title, supports?, duration_min?}], "timeline": [{block, items}]},
     "grocery_list": {"stores": [{name, items: [{title, quantity?, unit?, category?, linked_meal_ref?}]}]},
     "summary": "..."
   }

Everything here validates the payload, persists the plan, and wires the
grocery sync and parent action items. No em dashes appear in any AI prompt
or backend-authored copy.
"""

import json
import logging
import uuid
from datetime import date, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

logger = logging.getLogger("scout.meals")

from app.ai.provider import AnthropicProvider, get_provider
from app.models.action_items import ParentActionItem
from app.models.foundation import FamilyMember
from app.models.grocery import GroceryItem
from app.models.meals import DietaryPreference, MealReview, WeeklyMealPlan
from app.schemas.meals import (
    MealReviewCreate,
    MealReviewSummary,
    WeeklyMealPlanUpdate,
)
from app.services.tenant_guard import require_family, require_member_in_family

WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


class PlanValidationError(ValueError):
    """AI returned a shape we cannot trust. Never persisted, never coerced."""


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_plan_payload(payload: Any) -> dict[str, Any]:
    """Validate the ready shape. Returns a normalized dict or raises."""
    if not isinstance(payload, dict):
        raise PlanValidationError("plan payload must be an object")

    if payload.get("status") != "ready":
        raise PlanValidationError("plan payload status must be 'ready'")

    week_plan = payload.get("week_plan")
    prep_plan = payload.get("prep_plan")
    grocery_list = payload.get("grocery_list")

    if not isinstance(week_plan, dict):
        raise PlanValidationError("week_plan must be an object")
    dinners = week_plan.get("dinners")
    if not isinstance(dinners, dict) or len(dinners) == 0:
        raise PlanValidationError("week_plan.dinners must be a non-empty object")
    for day, meal in dinners.items():
        if day not in WEEKDAYS:
            raise PlanValidationError(f"week_plan.dinners has invalid day '{day}'")
        if not isinstance(meal, dict) or not meal.get("title"):
            raise PlanValidationError(f"week_plan.dinners.{day} missing title")

    for section_name in ("breakfast", "lunch"):
        section = week_plan.get(section_name)
        if section is not None and not isinstance(section, dict):
            raise PlanValidationError(f"week_plan.{section_name} must be an object if present")
    snacks = week_plan.get("snacks")
    if snacks is not None and not isinstance(snacks, list):
        raise PlanValidationError("week_plan.snacks must be a list if present")

    if not isinstance(prep_plan, dict):
        raise PlanValidationError("prep_plan must be an object")
    tasks = prep_plan.get("tasks")
    if not isinstance(tasks, list):
        raise PlanValidationError("prep_plan.tasks must be a list")
    for i, task in enumerate(tasks):
        if not isinstance(task, dict) or not task.get("title"):
            raise PlanValidationError(f"prep_plan.tasks[{i}] missing title")
    timeline = prep_plan.get("timeline")
    if timeline is not None and not isinstance(timeline, list):
        raise PlanValidationError("prep_plan.timeline must be a list if present")

    if not isinstance(grocery_list, dict):
        raise PlanValidationError("grocery_list must be an object")
    stores = grocery_list.get("stores")
    if not isinstance(stores, list) or len(stores) == 0:
        raise PlanValidationError("grocery_list.stores must be a non-empty list")
    for i, store in enumerate(stores):
        if not isinstance(store, dict) or not store.get("name"):
            raise PlanValidationError(f"grocery_list.stores[{i}] missing name")
        items = store.get("items")
        if not isinstance(items, list) or len(items) == 0:
            raise PlanValidationError(f"grocery_list.stores[{i}].items must be a non-empty list")
        for j, item in enumerate(items):
            if not isinstance(item, dict) or not item.get("title"):
                raise PlanValidationError(f"grocery_list.stores[{i}].items[{j}] missing title")

    return {
        "week_plan": week_plan,
        "prep_plan": prep_plan,
        "grocery_plan": grocery_list,
        "summary": payload.get("summary") or "",
    }


def validate_clarification_payload(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict) or payload.get("status") != "needs_clarification":
        raise PlanValidationError("clarification payload must have status 'needs_clarification'")
    questions = payload.get("questions")
    if not isinstance(questions, list) or len(questions) == 0:
        raise PlanValidationError("questions must be a non-empty list")
    normalized: list[dict[str, Any]] = []
    for i, q in enumerate(questions):
        if not isinstance(q, dict):
            raise PlanValidationError(f"questions[{i}] must be an object")
        key = q.get("key")
        question = q.get("question")
        if not key or not question:
            raise PlanValidationError(f"questions[{i}] missing key or question")
        normalized.append({"key": key, "question": question, "hint": q.get("hint")})
    return normalized


# ---------------------------------------------------------------------------
# Role guards
# ---------------------------------------------------------------------------


def _require_adult(db: Session, family_id: uuid.UUID, member_id: uuid.UUID, permission_key: str = "meal.manage") -> FamilyMember:
    """Preserved for Phase 2: now checks permission tier instead of role==adult."""
    from app.services.permissions import resolve_effective_permissions
    member = require_member_in_family(db, family_id, member_id)
    perms = resolve_effective_permissions(db, member_id)
    if not perms.get(permission_key, False):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Permission required: {permission_key}")
    return member


# ---------------------------------------------------------------------------
# Parent action items
# ---------------------------------------------------------------------------


def _create_meal_plan_review_action(
    db: Session,
    family_id: uuid.UUID,
    created_by: uuid.UUID,
    plan: WeeklyMealPlan,
) -> ParentActionItem:
    existing = db.scalars(
        select(ParentActionItem)
        .where(ParentActionItem.family_id == family_id)
        .where(ParentActionItem.entity_type == "weekly_meal_plan")
        .where(ParentActionItem.entity_id == plan.id)
        .where(ParentActionItem.status == "pending")
    ).first()
    if existing:
        return existing
    item = ParentActionItem(
        family_id=family_id,
        created_by_member_id=created_by,
        action_type="meal_plan_review",
        title=f"Review weekly meal plan for {plan.week_start_date.isoformat()}",
        detail=plan.plan_summary,
        entity_type="weekly_meal_plan",
        entity_id=plan.id,
    )
    db.add(item)
    db.flush()
    return item


def _resolve_meal_plan_review_actions(
    db: Session, family_id: uuid.UUID, plan_id: uuid.UUID, resolver_id: uuid.UUID
) -> None:
    stmt = (
        select(ParentActionItem)
        .where(ParentActionItem.family_id == family_id)
        .where(ParentActionItem.entity_type == "weekly_meal_plan")
        .where(ParentActionItem.entity_id == plan_id)
        .where(ParentActionItem.status == "pending")
    )
    for action in db.scalars(stmt).all():
        action.status = "resolved"
        action.resolved_by = resolver_id
        action.resolved_at = datetime.now().astimezone()
    db.flush()


# ---------------------------------------------------------------------------
# Constraints snapshot + review context for AI
# ---------------------------------------------------------------------------


def build_constraints_snapshot(
    db: Session,
    family_id: uuid.UUID,
    extra: dict[str, Any] | None = None,
    answers: dict[str, Any] | None = None,
) -> dict[str, Any]:
    require_family(db, family_id)
    members = list(db.scalars(
        select(FamilyMember)
        .where(FamilyMember.family_id == family_id)
        .where(FamilyMember.is_active.is_(True))
    ).all())
    dietary = list(db.scalars(
        select(DietaryPreference)
        .where(DietaryPreference.family_member_id.in_([m.id for m in members]))
    ).all())

    return {
        "family_size": len(members),
        "members": [
            {"id": str(m.id), "name": m.first_name, "role": m.role}
            for m in members
        ],
        "dietary": [
            {"member_id": str(p.family_member_id), "label": p.label, "kind": p.kind, "notes": p.notes}
            for p in dietary
        ],
        "extra": extra or {},
        "answers": answers or {},
    }


def build_review_context(db: Session, family_id: uuid.UUID, limit: int = 30) -> dict[str, Any]:
    """Compact structured signals for future meal generation."""
    reviews = list(db.scalars(
        select(MealReview)
        .where(MealReview.family_id == family_id)
        .order_by(MealReview.created_at.desc())
        .limit(limit)
    ).all())
    summary = summarize_reviews(reviews)
    return summary.model_dump()


def summarize_reviews(reviews: list[MealReview]) -> MealReviewSummary:
    high_rated: set[str] = set()
    retired: set[str] = set()
    low_kid: set[str] = set()
    good_left: set[str] = set()
    low_effort: set[str] = set()
    for r in reviews:
        if r.rating_overall >= 4:
            high_rated.add(r.meal_title)
        if r.repeat_decision == "retire":
            retired.add(r.meal_title)
        if r.kid_acceptance is not None and r.kid_acceptance <= 2:
            low_kid.add(r.meal_title)
        if r.leftovers == "plenty" and r.rating_overall >= 3:
            good_left.add(r.meal_title)
        if r.effort is not None and r.effort <= 2 and r.rating_overall >= 4:
            low_effort.add(r.meal_title)
    return MealReviewSummary(
        total_reviews=len(reviews),
        high_rated=sorted(high_rated),
        retired=sorted(retired),
        low_kid_acceptance=sorted(low_kid),
        good_leftovers=sorted(good_left),
        low_effort_favorites=sorted(low_effort),
    )


# ---------------------------------------------------------------------------
# AI generation
# ---------------------------------------------------------------------------


SYSTEM_PROMPT = (
    "You are Scout's weekly meal planner. Keep assistant-facing copy short and plain. "
    "Never use em dashes. Return ONLY valid JSON matching the schema described below. "
    "No prose outside the JSON object.\n\n"
    "First, decide whether you need clarification. If key facts are missing (family size, "
    "allergies, preferred stores, budget, time available Sunday, anything unusual this week), "
    "return shape A:\n"
    '{"status":"needs_clarification","questions":[{"key":"...","question":"...","hint":"..."}]}\n\n'
    "Otherwise return shape B with exactly these fields:\n"
    '{"status":"ready",\n'
    ' "week_plan":{"dinners":{"monday":{"title":"...","description":"..."},...},\n'
    '              "breakfast":{"plan":"..."},\n'
    '              "lunch":{"plan":"..."},\n'
    '              "snacks":["..."]},\n'
    ' "prep_plan":{"tasks":[{"title":"...","supports":["monday","tuesday"],"duration_min":20}],\n'
    '              "timeline":[{"block":"0:00-0:30","items":["..."]}]},\n'
    ' "grocery_list":{"stores":[{"name":"Costco","items":[{"title":"...","quantity":2,"unit":"lb","category":"produce","linked_meal_ref":"monday:dinner"}]},\n'
    '                            {"name":"H-E-B","items":[{"title":"..."}]}]},\n'
    ' "summary":"..."}\n\n'
    "Hard rules: at least one dinner per weekday that applies, prep tasks must fit a 2-3 hour "
    "Sunday window, grocery stores grouped by a primary bulk store (e.g. Costco) and a secondary "
    "store, each grocery item must belong to a store. Do not include nutrition tracking. "
    "Do not return a prose blob as the primary structure. "
    "Respect constraints.dietary: every entry is a per-member preference or "
    "restriction (allergies, intolerances, aversions, religious / ethical "
    "exclusions). If any member has a nut allergy, no dinner may use peanuts, "
    "tree nuts, nut oils, or pesto. If any member is vegetarian, at least one "
    "dinner per week must be a complete vegetarian meal they can eat as-is; "
    "do not plan around them with 'they can just skip the meat'. Apply the "
    "same logic to gluten-free, dairy-free, shellfish, pork, and any "
    "member-specific 'do not like' labels."
)


def _parse_json_response(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        # strip markdown fence if present
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise PlanValidationError(f"AI response was not valid JSON: {e}")


def _call_meal_ai(
    provider: AnthropicProvider,
    constraints: dict[str, Any],
    review_context: dict[str, Any],
    week_start: date,
    prior_answers: dict[str, Any] | None,
) -> dict[str, Any]:
    user_prompt = {
        "week_start_date": week_start.isoformat(),
        "constraints": constraints,
        "prior_answers": prior_answers or {},
        "review_context": review_context,
    }
    response = provider.chat(
        messages=[{"role": "user", "content": json.dumps(user_prompt)}],
        system=SYSTEM_PROMPT,
        max_tokens=4096,
        temperature=0.4,
    )
    return _parse_json_response(response.content or "")


def generate_weekly_meal_plan(
    db: Session,
    family_id: uuid.UUID,
    member_id: uuid.UUID,
    week_start_date: date,
    extra_constraints: dict[str, Any] | None = None,
    answers: dict[str, Any] | None = None,
    provider: AnthropicProvider | None = None,
) -> dict[str, Any]:
    """Generate a weekly meal plan draft. Returns either a clarification response
    or a saved-plan response. Adults only."""
    from app.config import settings
    _require_adult(db, family_id, member_id, "meal_plan.generate")
    if week_start_date.isoweekday() != 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="week_start_date must be a Monday")
    if not settings.enable_meal_generation:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Meal generation is currently disabled")

    constraints = build_constraints_snapshot(db, family_id, extra=extra_constraints, answers=answers)
    review_context = build_review_context(db, family_id)

    logger.info("meal_plan_generate_start family=%s member=%s week=%s", family_id, member_id, week_start_date)
    try:
        provider = provider or get_provider()
    except RuntimeError:
        logger.error("meal_plan_generate_fail family=%s reason=ai_unavailable", family_id)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI service is not configured")
    try:
        payload = _call_meal_ai(provider, constraints, review_context, week_start_date, answers)
    except PlanValidationError:
        raise
    except Exception as e:
        logger.error("meal_plan_generate_fail family=%s reason=ai_error error=%s", family_id, e)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="AI service error during meal plan generation")

    if isinstance(payload, dict) and payload.get("status") == "needs_clarification":
        questions = validate_clarification_payload(payload)
        logger.info("meal_plan_generate_clarification family=%s questions=%d", family_id, len(questions))
        return {"status": "needs_clarification", "questions": questions}

    normalized = validate_plan_payload(payload)
    plan = save_weekly_meal_plan_draft(
        db,
        family_id,
        member_id,
        week_start_date=week_start_date,
        week_plan=normalized["week_plan"],
        prep_plan=normalized["prep_plan"],
        grocery_plan=normalized["grocery_plan"],
        plan_summary=normalized["summary"],
        constraints_snapshot=constraints,
        source="ai",
    )
    logger.info("meal_plan_generate_success family=%s plan=%s", family_id, plan.id)
    return {"status": "ready", "plan_id": plan.id, "summary": plan.plan_summary}


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def save_weekly_meal_plan_draft(
    db: Session,
    family_id: uuid.UUID,
    member_id: uuid.UUID,
    *,
    week_start_date: date,
    week_plan: dict[str, Any],
    prep_plan: dict[str, Any],
    grocery_plan: dict[str, Any],
    plan_summary: str | None = None,
    constraints_snapshot: dict[str, Any] | None = None,
    source: str = "ai",
    title: str | None = None,
) -> WeeklyMealPlan:
    _require_adult(db, family_id, member_id, "meal_plan.generate")
    if week_start_date.isoweekday() != 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="week_start_date must be a Monday")

    plan = WeeklyMealPlan(
        family_id=family_id,
        created_by_member_id=member_id,
        week_start_date=week_start_date,
        source=source,
        status="draft",
        title=title,
        constraints_snapshot=constraints_snapshot or {},
        week_plan=week_plan,
        prep_plan=prep_plan,
        grocery_plan=grocery_plan,
        plan_summary=plan_summary,
    )
    db.add(plan)
    db.flush()
    _create_meal_plan_review_action(db, family_id, member_id, plan)
    db.commit()
    db.refresh(plan)
    return plan


def get_weekly_meal_plan(
    db: Session, family_id: uuid.UUID, plan_id: uuid.UUID,
    actor_member_id: uuid.UUID | None = None,
) -> WeeklyMealPlan:
    plan = db.get(WeeklyMealPlan, plan_id)
    if not plan or plan.family_id != family_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Weekly meal plan not found")
    if actor_member_id:
        actor = require_member_in_family(db, family_id, actor_member_id)
        if actor.role == "child" and plan.status != "approved":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Children can only view approved plans")
    return plan


def get_current_weekly_meal_plan(
    db: Session, family_id: uuid.UUID, actor_member_id: uuid.UUID | None = None,
) -> WeeklyMealPlan | None:
    """Most recent non-archived plan for the family.

    If actor_member_id is provided and the actor is a child, only approved
    plans are returned (children cannot see drafts).
    """
    require_family(db, family_id)

    child_only = False
    if actor_member_id:
        actor = require_member_in_family(db, family_id, actor_member_id)
        child_only = actor.role == "child"

    stmt = (
        select(WeeklyMealPlan)
        .where(WeeklyMealPlan.family_id == family_id)
        .where(WeeklyMealPlan.status != "archived")
    )
    if child_only:
        stmt = stmt.where(WeeklyMealPlan.status == "approved")

    stmt = stmt.order_by(
        WeeklyMealPlan.week_start_date.desc(),
        WeeklyMealPlan.status.desc(),
        WeeklyMealPlan.created_at.desc(),
    )
    plans = list(db.scalars(stmt).all())
    if not plans:
        return None
    latest_week = plans[0].week_start_date
    same_week = [p for p in plans if p.week_start_date == latest_week]
    approved = next((p for p in same_week if p.status == "approved"), None)
    return approved or same_week[0]


def update_weekly_meal_plan(
    db: Session,
    family_id: uuid.UUID,
    member_id: uuid.UUID,
    plan_id: uuid.UUID,
    payload: WeeklyMealPlanUpdate,
) -> WeeklyMealPlan:
    _require_adult(db, family_id, member_id, "meal_plan.generate")
    plan = get_weekly_meal_plan(db, family_id, plan_id)
    if plan.status == "archived":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot edit archived plan")
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(plan, key, value)
    db.commit()
    db.refresh(plan)
    return plan


def approve_weekly_meal_plan(
    db: Session, family_id: uuid.UUID, member_id: uuid.UUID, plan_id: uuid.UUID
) -> WeeklyMealPlan:
    _require_adult(db, family_id, member_id, "meal_plan.approve")
    plan = get_weekly_meal_plan(db, family_id, plan_id)
    if plan.status == "archived":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot approve archived plan")
    if plan.status == "approved":
        return plan

    # Archive any other approved plan for the same week so the unique index holds.
    stmt = (
        select(WeeklyMealPlan)
        .where(WeeklyMealPlan.family_id == family_id)
        .where(WeeklyMealPlan.week_start_date == plan.week_start_date)
        .where(WeeklyMealPlan.status == "approved")
        .where(WeeklyMealPlan.id != plan.id)
    )
    for other in db.scalars(stmt).all():
        other.status = "archived"
        other.archived_at = datetime.now().astimezone()

    plan.status = "approved"
    plan.approved_by_member_id = member_id
    plan.approved_at = datetime.now().astimezone()
    db.flush()

    sync_grocery_items_from_plan(db, family_id, member_id, plan.id)
    _resolve_meal_plan_review_actions(db, family_id, plan.id, member_id)
    db.commit()
    db.refresh(plan)
    logger.info("meal_plan_approved family=%s plan=%s by=%s", family_id, plan.id, member_id)
    return plan


def archive_weekly_meal_plan(
    db: Session, family_id: uuid.UUID, member_id: uuid.UUID, plan_id: uuid.UUID
) -> WeeklyMealPlan:
    _require_adult(db, family_id, member_id, "meal_plan.approve")
    plan = get_weekly_meal_plan(db, family_id, plan_id)
    plan.status = "archived"
    plan.archived_at = datetime.now().astimezone()
    _resolve_meal_plan_review_actions(db, family_id, plan.id, member_id)
    db.commit()
    db.refresh(plan)
    logger.info("meal_plan_archived family=%s plan=%s by=%s", family_id, plan.id, member_id)
    return plan


def regenerate_day(
    db: Session,
    family_id: uuid.UUID,
    member_id: uuid.UUID,
    plan_id: uuid.UUID,
    day: str,
    meal_types: list[str] | None = None,
    provider: AnthropicProvider | None = None,
) -> WeeklyMealPlan:
    from app.config import settings as app_settings
    _require_adult(db, family_id, member_id, "meal_plan.generate")
    plan = get_weekly_meal_plan(db, family_id, plan_id)
    if day not in WEEKDAYS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid day: {day}")
    if not app_settings.enable_meal_generation:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Meal generation is currently disabled")

    types = meal_types or ["dinner"]
    try:
        provider = provider or get_provider()
    except RuntimeError:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI service is not configured")
    constraints = plan.constraints_snapshot or {}
    review_context = build_review_context(db, family_id)

    prompt = {
        "regenerate": {"day": day, "meal_types": types},
        "current_week_plan": plan.week_plan,
        "constraints": constraints,
        "review_context": review_context,
    }
    day_system = (
        "You are Scout's meal planner. Replace only the requested meal slots for the given day. "
        "Return JSON: {\"status\":\"ready\",\"replacements\":{\"<day>\":{\"dinner\":{\"title\":\"...\",\"description\":\"...\"}}}}. "
        "No em dashes. No prose outside JSON."
    )
    response = provider.chat(
        messages=[{"role": "user", "content": json.dumps(prompt)}],
        system=day_system,
        max_tokens=1024,
        temperature=0.5,
    )
    payload = _parse_json_response(response.content or "")
    if not isinstance(payload, dict) or payload.get("status") != "ready":
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="AI did not return a ready replacement")
    replacements = payload.get("replacements", {}).get(day)
    if not isinstance(replacements, dict):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="AI replacement missing day")

    new_week_plan = dict(plan.week_plan or {})
    # dinner replacement lands in week_plan.dinners[day]; others go under their section.
    for mtype, meal in replacements.items():
        if not isinstance(meal, dict) or not meal.get("title"):
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"AI replacement for {mtype} missing title")
        if mtype == "dinner":
            dinners = dict(new_week_plan.get("dinners") or {})
            dinners[day] = meal
            new_week_plan["dinners"] = dinners
        else:
            section = dict(new_week_plan.get(mtype) or {})
            by_day = dict(section.get("by_day") or {})
            by_day[day] = meal
            section["by_day"] = by_day
            new_week_plan[mtype] = section

    plan.week_plan = new_week_plan
    db.commit()
    db.refresh(plan)
    return plan


def list_weekly_meal_plans(
    db: Session, family_id: uuid.UUID, include_archived: bool = False,
    actor_member_id: uuid.UUID | None = None,
) -> list[WeeklyMealPlan]:
    require_family(db, family_id)
    child_only = False
    if actor_member_id:
        actor = require_member_in_family(db, family_id, actor_member_id)
        child_only = actor.role == "child"

    stmt = select(WeeklyMealPlan).where(WeeklyMealPlan.family_id == family_id)
    if not include_archived:
        stmt = stmt.where(WeeklyMealPlan.status != "archived")
    if child_only:
        stmt = stmt.where(WeeklyMealPlan.status == "approved")
    stmt = stmt.order_by(WeeklyMealPlan.week_start_date.desc(), WeeklyMealPlan.created_at.desc())
    return list(db.scalars(stmt).all())


# ---------------------------------------------------------------------------
# Grocery sync
# ---------------------------------------------------------------------------


def sync_grocery_items_from_plan(
    db: Session, family_id: uuid.UUID, member_id: uuid.UUID, plan_id: uuid.UUID
) -> list[GroceryItem]:
    """Create grocery_items for everything in grocery_plan.stores. Idempotent per plan:
    items already linked to this plan are left alone, new ones are added."""
    plan = get_weekly_meal_plan(db, family_id, plan_id)
    existing = list(db.scalars(
        select(GroceryItem)
        .where(GroceryItem.family_id == family_id)
        .where(GroceryItem.weekly_plan_id == plan_id)
    ).all())
    existing_keys = {
        (item.title.lower(), (item.preferred_store or "").lower(), item.linked_meal_ref or "")
        for item in existing
    }

    created: list[GroceryItem] = []
    stores = (plan.grocery_plan or {}).get("stores") or []
    for store in stores:
        store_name = store.get("name") or None
        for row in store.get("items") or []:
            title = row.get("title")
            if not title:
                continue
            linked_ref = row.get("linked_meal_ref") or ""
            key = (title.lower(), (store_name or "").lower(), linked_ref)
            if key in existing_keys:
                continue
            quantity = row.get("quantity")
            unit = row.get("unit")
            category = row.get("category")
            item = GroceryItem(
                family_id=family_id,
                added_by_member_id=member_id,
                title=title,
                quantity=quantity,
                unit=unit,
                category=category,
                preferred_store=store_name,
                notes=row.get("notes"),
                source="meal_ai",
                approval_status="active",
                weekly_plan_id=plan_id,
                linked_meal_ref=row.get("linked_meal_ref"),
            )
            db.add(item)
            existing_keys.add(key)
            created.append(item)
    db.flush()
    return created


def list_plan_grocery_items(
    db: Session, family_id: uuid.UUID, plan_id: uuid.UUID
) -> list[GroceryItem]:
    # Validates ownership.
    get_weekly_meal_plan(db, family_id, plan_id)
    stmt = (
        select(GroceryItem)
        .where(GroceryItem.family_id == family_id)
        .where(GroceryItem.weekly_plan_id == plan_id)
        .order_by(GroceryItem.preferred_store, GroceryItem.category, GroceryItem.title)
    )
    return list(db.scalars(stmt).all())


# ---------------------------------------------------------------------------
# Meal reviews
# ---------------------------------------------------------------------------


def create_meal_review(
    db: Session,
    family_id: uuid.UUID,
    payload: MealReviewCreate,
) -> MealReview:
    # Children CAN submit reviews, but must be members of this family.
    require_member_in_family(db, family_id, payload.member_id)
    if payload.weekly_plan_id:
        # Make sure the plan belongs to this family.
        get_weekly_meal_plan(db, family_id, payload.weekly_plan_id)

    review = MealReview(
        family_id=family_id,
        weekly_plan_id=payload.weekly_plan_id,
        reviewed_by_member_id=payload.member_id,
        linked_meal_ref=payload.linked_meal_ref,
        meal_title=payload.meal_title,
        rating_overall=payload.rating_overall,
        kid_acceptance=payload.kid_acceptance,
        effort=payload.effort,
        cleanup=payload.cleanup,
        leftovers=payload.leftovers,
        repeat_decision=payload.repeat_decision,
        notes=payload.notes,
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return review


def list_meal_reviews(
    db: Session, family_id: uuid.UUID, limit: int = 50
) -> list[MealReview]:
    require_family(db, family_id)
    stmt = (
        select(MealReview)
        .where(MealReview.family_id == family_id)
        .order_by(MealReview.created_at.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt).all())


def get_meal_review_summary(db: Session, family_id: uuid.UUID) -> MealReviewSummary:
    require_family(db, family_id)
    reviews = list(db.scalars(
        select(MealReview).where(MealReview.family_id == family_id)
    ).all())
    return summarize_reviews(reviews)

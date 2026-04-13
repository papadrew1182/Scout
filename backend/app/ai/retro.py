"""Weekly family retrospective — data gathering + AI narrative.

Kept separate from ``app.ai.insights`` because retro is a
once-per-week summary written to the inbox, not a per-day cached
dashboard banner. Pipeline:

    build_retro_context(db, family_id, week_start)
      -> dict of compact, privacy-aware facts for the week

    generate_retro_narrative(context)
      -> Claude-classified short narrative (string)

Design notes
------------
- Uses ONLY data already persisted by Scout (no new telemetry).
- Never includes raw child chat content in the narrative. Homework
  sessions surface as counts by subject, moderation blocks surface
  as counts by category. The retro is written for adults to read,
  not a transcript of what kids said.
- Deterministic fallback narrative (same structure, less eloquent)
  used when the AI provider is unavailable.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.action_items import ParentActionItem
from app.models.ai import AIMessage, AIToolAudit
from app.models.finance import Bill
from app.models.foundation import FamilyMember
from app.models.grocery import GroceryItem, PurchaseRequest
from app.models.life_management import (
    AllowanceLedger,
    DailyWin,
    TaskInstance,
)
from app.models.meals import MealReview

try:
    from app.models.homework import HomeworkSession
except Exception:  # pragma: no cover — in case the model import ever fails in tests
    HomeworkSession = None  # type: ignore

logger = logging.getLogger("scout.ai.retro")

MAX_NARRATIVE_CHARS = 1400


def build_retro_context(
    db: Session, *, family_id, week_start: date
) -> dict[str, Any]:
    """Gather the compact data bundle the retro summarizes.

    week_start is the Monday of the target week. The retro covers the
    whole week up to and including the local "today" when the
    scheduler fires (Friday 6pm), but for completeness we query
    Mon-Sun so a manually-invoked retro for a past week is correct too.
    """
    week_end = week_start + timedelta(days=6)
    start_dt = datetime.combine(week_start, time.min)
    end_dt = datetime.combine(week_end, time.max)

    # ---- kids ----
    children = list(db.scalars(
        select(FamilyMember)
        .where(FamilyMember.family_id == family_id)
        .where(FamilyMember.role == "child")
        .where(FamilyMember.is_active.is_(True))
    ).all())

    per_child = []
    for kid in children:
        tasks_this_week = list(db.scalars(
            select(TaskInstance)
            .where(TaskInstance.family_id == family_id)
            .where(TaskInstance.family_member_id == kid.id)
            .where(TaskInstance.instance_date >= week_start)
            .where(TaskInstance.instance_date <= week_end)
        ).all())
        total = len(tasks_this_week)
        completed = sum(1 for t in tasks_this_week if t.is_completed or t.override_completed)
        missed = total - completed

        wins = list(db.scalars(
            select(DailyWin)
            .where(DailyWin.family_member_id == kid.id)
            .where(DailyWin.win_date >= week_start)
            .where(DailyWin.win_date <= week_end)
        ).all())
        win_count = sum(1 for w in wins if w.is_win)

        allowance_sum = db.scalar(
            select(func.coalesce(func.sum(AllowanceLedger.amount_cents), 0))
            .where(AllowanceLedger.family_member_id == kid.id)
            .where(AllowanceLedger.created_at >= start_dt)
            .where(AllowanceLedger.created_at <= end_dt)
        ) or 0

        homework_count = 0
        homework_subjects: dict[str, int] = {}
        if HomeworkSession is not None:
            hw_rows = list(db.scalars(
                select(HomeworkSession)
                .where(HomeworkSession.member_id == kid.id)
                .where(HomeworkSession.started_at >= start_dt)
                .where(HomeworkSession.started_at <= end_dt)
            ).all())
            homework_count = len(hw_rows)
            for h in hw_rows:
                homework_subjects[h.subject] = homework_subjects.get(h.subject, 0) + 1

        per_child.append({
            "name": kid.first_name,
            "tasks_total": total,
            "tasks_completed": completed,
            "tasks_missed": missed,
            "daily_wins": win_count,
            "allowance_delta_cents": allowance_sum,
            "homework_sessions": homework_count,
            "homework_subjects": homework_subjects,
        })

    # ---- household ----
    bills_paid = db.scalar(
        select(func.count()).select_from(Bill)
        .where(Bill.family_id == family_id)
        .where(Bill.status == "paid")
        .where(Bill.paid_at >= start_dt)
        .where(Bill.paid_at <= end_dt)
    ) or 0

    meal_reviews = db.scalar(
        select(func.count()).select_from(MealReview)
        .where(MealReview.family_id == family_id)
        .where(MealReview.created_at >= start_dt)
        .where(MealReview.created_at <= end_dt)
    ) or 0

    grocery_added = db.scalar(
        select(func.count()).select_from(GroceryItem)
        .where(GroceryItem.family_id == family_id)
        .where(GroceryItem.created_at >= start_dt)
        .where(GroceryItem.created_at <= end_dt)
    ) or 0

    purchase_requests_created = db.scalar(
        select(func.count()).select_from(PurchaseRequest)
        .where(PurchaseRequest.family_id == family_id)
        .where(PurchaseRequest.created_at >= start_dt)
        .where(PurchaseRequest.created_at <= end_dt)
    ) or 0

    # ---- AI usage ----
    ai_turns = db.scalar(
        select(func.count()).select_from(AIMessage)
        .where(AIMessage.role == "user")
        .where(AIMessage.created_at >= start_dt)
        .where(AIMessage.created_at <= end_dt)
    ) or 0

    tool_invocations = db.scalar(
        select(func.count()).select_from(AIToolAudit)
        .where(AIToolAudit.family_id == family_id)
        .where(AIToolAudit.tool_name != "moderation")
        .where(AIToolAudit.created_at >= start_dt)
        .where(AIToolAudit.created_at <= end_dt)
    ) or 0

    moderation_blocks = db.scalar(
        select(func.count()).select_from(AIToolAudit)
        .where(AIToolAudit.family_id == family_id)
        .where(AIToolAudit.tool_name == "moderation")
        .where(AIToolAudit.created_at >= start_dt)
        .where(AIToolAudit.created_at <= end_dt)
    ) or 0

    unresolved_inbox_items = db.scalar(
        select(func.count()).select_from(ParentActionItem)
        .where(ParentActionItem.family_id == family_id)
        .where(ParentActionItem.status == "pending")
    ) or 0

    return {
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "children": per_child,
        "household": {
            "bills_paid": bills_paid,
            "meal_reviews": meal_reviews,
            "grocery_items_added": grocery_added,
            "purchase_requests_created": purchase_requests_created,
            "unresolved_inbox_items": unresolved_inbox_items,
        },
        "ai_usage": {
            "turns": ai_turns,
            "tool_invocations": tool_invocations,
            "moderation_blocks": moderation_blocks,
        },
    }


def generate_retro_narrative(context: dict) -> str:
    """Render the retro as plain text. Tries AI first, falls back to
    a deterministic template. Returns text ready to paste into
    parent_action_items.detail."""
    try:
        from app.config import settings
        if settings.anthropic_api_key:
            return _ai_narrative(context)
    except Exception as e:
        logger.warning("retro_ai_failed: %s", str(e)[:200])
    return _template_narrative(context)


def _ai_narrative(context: dict) -> str:
    import json
    from app.ai.provider import get_provider
    from app.config import settings

    system = (
        "You are writing a short weekly family retrospective for parents "
        "to read in their Action Inbox. Tone: warm, direct, specific. "
        "Rules: 200 words max, markdown allowed, use headings if useful, "
        "no emoji, no cheerful filler, no promises, do not invent facts. "
        "Do not quote any child's messages verbatim. Moderation blocks "
        "are mentioned ONLY as a count, never with content."
    )
    user = (
        "Here is the compact bundle of facts for the week. Write the "
        "retrospective based solely on these numbers. When a number is "
        "zero, omit that line rather than write 'no X'.\n\n"
        f"{json.dumps(context, indent=2)}"
    )
    provider = get_provider()
    response = provider.chat(
        messages=[{"role": "user", "content": user}],
        system=system,
        model=settings.ai_classification_model or settings.ai_chat_model,
        max_tokens=600,
        temperature=0.3,
    )
    text = (response.content or "").strip()
    if len(text) > MAX_NARRATIVE_CHARS:
        text = text[: MAX_NARRATIVE_CHARS - 1].rstrip() + "…"
    if not text:
        raise RuntimeError("AI returned empty retro")
    return text


def _template_narrative(context: dict) -> str:
    """Deterministic fallback. Same facts, less eloquent phrasing."""
    lines: list[str] = []
    lines.append(f"**Week of {context['week_start']}**")
    lines.append("")

    # Kids
    children = context.get("children", [])
    if children:
        lines.append("**Kids**")
        for c in children:
            if c["tasks_total"] > 0:
                pct = round(100 * c["tasks_completed"] / c["tasks_total"])
                lines.append(
                    f"- {c['name']}: {c['tasks_completed']}/{c['tasks_total']} tasks "
                    f"({pct}%), {c['daily_wins']} daily wins"
                )
            else:
                lines.append(f"- {c['name']}: {c['daily_wins']} daily wins")
            if c.get("homework_sessions", 0):
                subj = ", ".join(
                    f"{k}: {v}" for k, v in c.get("homework_subjects", {}).items()
                )
                lines.append(f"    homework: {c['homework_sessions']} sessions ({subj})")
            if c.get("allowance_delta_cents", 0):
                dollars = c["allowance_delta_cents"] / 100
                lines.append(f"    allowance change: ${dollars:+.2f}")

    # Household
    hh = context.get("household", {})
    if any(hh.values()):
        lines.append("")
        lines.append("**Household**")
        if hh.get("bills_paid"):
            lines.append(f"- Bills paid: {hh['bills_paid']}")
        if hh.get("meal_reviews"):
            lines.append(f"- Meal reviews: {hh['meal_reviews']}")
        if hh.get("grocery_items_added"):
            lines.append(f"- Grocery items added: {hh['grocery_items_added']}")
        if hh.get("purchase_requests_created"):
            lines.append(f"- Purchase requests: {hh['purchase_requests_created']}")
        if hh.get("unresolved_inbox_items"):
            lines.append(f"- Inbox still open: {hh['unresolved_inbox_items']}")

    # AI usage
    ai = context.get("ai_usage", {})
    if ai.get("turns", 0) or ai.get("moderation_blocks", 0):
        lines.append("")
        lines.append("**Scout activity**")
        if ai.get("turns"):
            lines.append(f"- Chat turns: {ai['turns']}")
        if ai.get("tool_invocations"):
            lines.append(f"- Tool calls: {ai['tool_invocations']}")
        if ai.get("moderation_blocks"):
            lines.append(
                f"- Safety blocks: {ai['moderation_blocks']} (check the Inbox for alerts)"
            )

    out = "\n".join(lines).strip()
    if not out:
        out = f"Week of {context['week_start']}: quiet week, nothing unusual to report."
    if len(out) > MAX_NARRATIVE_CHARS:
        out = out[: MAX_NARRATIVE_CHARS - 1].rstrip() + "…"
    return out

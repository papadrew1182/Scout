"""AI usage and approximate-cost rollups.

Reads ``ai_messages.token_usage`` (populated by the orchestrator on
every assistant turn) and produces per-day / per-model / per-member
aggregates plus a rough dollar estimate. The dollar figure is
**approximate** — provider pricing drifts, promo credits and batching
can distort real billing, and we mark it as such in the UI.

Pricing registry: ``MODEL_PRICING`` maps Anthropic model IDs to
(input_per_1M, output_per_1M) USD rates. Unknown models fall back to
``_default`` so a model-id typo doesn't zero out the cost. Operators
can override the whole table via the ``SCOUT_AI_PRICING_OVERRIDE``
env var (JSON string, same shape) without a code deploy.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ai import AIConversation, AIMessage
from app.models.foundation import FamilyMember

logger = logging.getLogger("scout.ai.pricing")


# Anthropic list prices as of 2026-04, in USD per 1M tokens
# (input, output). These are intentionally conservative — operators
# who want precision should set SCOUT_AI_PRICING_OVERRIDE.
_BUILT_IN_PRICING: dict[str, tuple[float, float]] = {
    "claude-opus-4-6": (15.0, 75.0),
    "claude-opus-4-6[1m]": (15.0, 75.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-sonnet-4-20250514": (3.0, 15.0),
    "claude-haiku-4-5-20251001": (1.0, 5.0),
    "claude-haiku-4-5": (1.0, 5.0),
    # Confirmation-direct path doesn't hit a provider — zero cost.
    "confirmation-direct": (0.0, 0.0),
    # Moderation gate short-circuits before any provider call.
    "moderation-blocked": (0.0, 0.0),
    # Fallback for unknown / future model ids.
    "_default": (3.0, 15.0),
}


def _load_pricing() -> dict[str, tuple[float, float]]:
    override = os.environ.get("SCOUT_AI_PRICING_OVERRIDE")
    if not override:
        return _BUILT_IN_PRICING
    try:
        parsed = json.loads(override)
        out: dict[str, tuple[float, float]] = {}
        for model, rates in parsed.items():
            if (
                isinstance(rates, (list, tuple))
                and len(rates) == 2
                and all(isinstance(x, (int, float)) for x in rates)
            ):
                out[str(model)] = (float(rates[0]), float(rates[1]))
        # Ensure a default exists so unknown models don't KeyError.
        if "_default" not in out:
            out["_default"] = _BUILT_IN_PRICING["_default"]
        return out
    except Exception as e:  # malformed JSON / shape
        logger.warning("pricing_override_invalid: %s", e)
        return _BUILT_IN_PRICING


MODEL_PRICING: dict[str, tuple[float, float]] = _load_pricing()


def estimate_cost_usd(model: str | None, input_tokens: int, output_tokens: int) -> float:
    """Return an approximate cost in USD for a single assistant turn.

    Missing / unknown model IDs fall back to the default rate so a
    legacy row or a model rename doesn't zero out the rollup."""
    rates = MODEL_PRICING.get(model or "_default") or MODEL_PRICING["_default"]
    in_rate, out_rate = rates
    return (input_tokens / 1_000_000.0) * in_rate + (output_tokens / 1_000_000.0) * out_rate


def _usage_from_row(row: AIMessage) -> tuple[int, int]:
    """Pull (input, output) tokens off an ai_messages row. Tolerates
    missing / malformed token_usage payloads — the earliest rows in
    prod were persisted without usage, and we degrade to zero rather
    than crash."""
    usage = row.token_usage or {}
    if not isinstance(usage, dict):
        return (0, 0)
    try:
        return (int(usage.get("input") or 0), int(usage.get("output") or 0))
    except (TypeError, ValueError):
        return (0, 0)


def build_usage_report(
    db: Session,
    *,
    family_id: uuid.UUID,
    days: int = 7,
    as_of: datetime | None = None,
    soft_cap_usd: float = 0.0,
) -> dict:
    """Aggregate AI spend across a family for the last N days.

    Rollup groups:
      - ``by_day`` — one entry per calendar day in the window,
        oldest-first. Zero-days are included so charts line up.
      - ``by_model`` — sorted desc by cost.
      - ``by_member`` — sorted desc by cost, joined to
        ``family_members`` for the display name.

    ``soft_cap_usd`` is returned with the report plus a ``cap_warning``
    boolean so the UI can paint a warning state without re-implementing
    the threshold math client-side.
    """
    now = (as_of or datetime.now(timezone.utc).replace(tzinfo=None)).replace(tzinfo=None)
    cutoff = now - timedelta(days=days)
    # Only scan this family's conversations. Multi-tenant safe.
    conv_ids = [
        r[0]
        for r in db.execute(
            select(AIConversation.id).where(AIConversation.family_id == family_id)
        ).all()
    ]
    if not conv_ids:
        return _empty_report(days=days, soft_cap_usd=soft_cap_usd)

    msg_rows = list(
        db.scalars(
            select(AIMessage)
            .where(AIMessage.conversation_id.in_(conv_ids))
            .where(AIMessage.role == "assistant")
            .where(AIMessage.created_at >= cutoff)
        ).all()
    )
    if not msg_rows:
        return _empty_report(days=days, soft_cap_usd=soft_cap_usd)

    # Need conversation → member map to attribute cost to who sent it.
    conv_member: dict[uuid.UUID, uuid.UUID] = {}
    for conv in db.scalars(
        select(AIConversation).where(AIConversation.id.in_(conv_ids))
    ).all():
        conv_member[conv.id] = conv.family_member_id

    # Seed the by-day bucket with zero rows so the chart has a
    # contiguous x-axis. Oldest first.
    by_day: dict[str, dict] = {}
    start_day = (now - timedelta(days=days - 1)).date()
    for i in range(days):
        d = (start_day + timedelta(days=i)).isoformat()
        by_day[d] = {"date": d, "messages": 0, "input": 0, "output": 0, "cost_usd": 0.0}

    by_model: dict[str, dict] = {}
    by_member: dict[uuid.UUID, dict] = {}

    total_in = 0
    total_out = 0
    total_cost = 0.0
    total_messages = 0

    for row in msg_rows:
        in_tok, out_tok = _usage_from_row(row)
        model = row.model or "_default"
        cost = estimate_cost_usd(model, in_tok, out_tok)

        total_in += in_tok
        total_out += out_tok
        total_cost += cost
        total_messages += 1

        day_key = row.created_at.date().isoformat()
        d_bucket = by_day.get(day_key)
        if d_bucket is None:
            # Row is outside our seeded window (shouldn't happen given
            # the cutoff filter, but be defensive).
            d_bucket = {
                "date": day_key,
                "messages": 0,
                "input": 0,
                "output": 0,
                "cost_usd": 0.0,
            }
            by_day[day_key] = d_bucket
        d_bucket["messages"] += 1
        d_bucket["input"] += in_tok
        d_bucket["output"] += out_tok
        d_bucket["cost_usd"] += cost

        m_bucket = by_model.setdefault(
            model,
            {"model": model, "messages": 0, "input": 0, "output": 0, "cost_usd": 0.0},
        )
        m_bucket["messages"] += 1
        m_bucket["input"] += in_tok
        m_bucket["output"] += out_tok
        m_bucket["cost_usd"] += cost

        member_id = conv_member.get(row.conversation_id)
        if member_id is not None:
            mem_bucket = by_member.setdefault(
                member_id,
                {
                    "member_id": str(member_id),
                    "first_name": "",
                    "messages": 0,
                    "input": 0,
                    "output": 0,
                    "cost_usd": 0.0,
                },
            )
            mem_bucket["messages"] += 1
            mem_bucket["input"] += in_tok
            mem_bucket["output"] += out_tok
            mem_bucket["cost_usd"] += cost

    # Join by-member buckets to family_members for display names.
    if by_member:
        fm_rows = list(
            db.scalars(
                select(FamilyMember).where(FamilyMember.id.in_(list(by_member.keys())))
            ).all()
        )
        name_map = {fm.id: fm.first_name for fm in fm_rows}
        for mid, bucket in by_member.items():
            bucket["first_name"] = name_map.get(mid, "Unknown")

    # Sort each section deterministically.
    by_day_sorted = [by_day[k] for k in sorted(by_day.keys())]
    by_model_sorted = sorted(
        by_model.values(), key=lambda b: b["cost_usd"], reverse=True
    )
    by_member_sorted = sorted(
        by_member.values(), key=lambda b: b["cost_usd"], reverse=True
    )

    return {
        "days": days,
        "as_of": now.date().isoformat(),
        "total_messages": total_messages,
        "total_tokens": {"input": total_in, "output": total_out},
        "approx_cost_usd": round(total_cost, 4),
        "soft_cap_usd": round(soft_cap_usd, 2),
        "cap_warning": soft_cap_usd > 0 and total_cost >= soft_cap_usd,
        "by_day": [
            {**r, "cost_usd": round(r["cost_usd"], 4)} for r in by_day_sorted
        ],
        "by_model": [
            {**r, "cost_usd": round(r["cost_usd"], 4)} for r in by_model_sorted
        ],
        "by_member": [
            {**r, "cost_usd": round(r["cost_usd"], 4)} for r in by_member_sorted
        ],
    }


def _empty_report(*, days: int, soft_cap_usd: float) -> dict:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    start_day = (now - timedelta(days=days - 1)).date()
    by_day = [
        {
            "date": (start_day + timedelta(days=i)).isoformat(),
            "messages": 0,
            "input": 0,
            "output": 0,
            "cost_usd": 0.0,
        }
        for i in range(days)
    ]
    return {
        "days": days,
        "as_of": now.date().isoformat(),
        "total_messages": 0,
        "total_tokens": {"input": 0, "output": 0},
        "approx_cost_usd": 0.0,
        "soft_cap_usd": round(soft_cap_usd, 2),
        "cap_warning": False,
        "by_day": by_day,
        "by_model": [],
        "by_member": [],
    }

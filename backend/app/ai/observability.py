"""Structured logging for AI provider calls.

Emits a single JSON line per provider round so operators can grep
Railway logs (or any tail) for ``ai_call`` and compute per-family /
per-day / per-tool rollups without hitting the database.

Line shape::

    ai_call {"trace_id": "...", "conversation_id": "...",
             "family_id": "...", "member_id": "...",
             "model": "claude-opus-4-6", "tool_name": null,
             "duration_ms": 842, "input_tokens": 1234,
             "output_tokens": 567, "cost_usd": 0.0234,
             "event_ts": "2026-04-20T22:11:03.812Z"}

The ``event_ts`` is ISO-8601 UTC so the aggregation script can bucket
by day without re-parsing the logger-emitted timestamp. ``cost_usd`` is
computed via ``pricing.estimate_cost_usd`` so the DB-backed rollup
(``build_usage_report``) and the log-backed rollup agree on the pricing
table; operators who override rates via ``SCOUT_AI_PRICING_OVERRIDE``
get consistent numbers in both surfaces.

See ``scripts/ai_cost_report.py`` for the companion aggregation tool.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from app.ai.pricing import estimate_cost_usd

logger = logging.getLogger("scout.ai.observability")

AI_CALL_EVENT = "ai_call"


def new_trace_id() -> str:
    """Fresh opaque id for one logical AI interaction.

    One chat turn may trigger multiple provider rounds (tool-loop). All
    rounds for the same turn share the same trace_id so the aggregation
    script can stitch them back together.
    """
    return uuid.uuid4().hex


def log_ai_call(
    *,
    trace_id: str,
    conversation_id: str | uuid.UUID | None,
    family_id: str | uuid.UUID | None,
    member_id: str | uuid.UUID | None,
    model: str | None,
    tool_name: str | None,
    duration_ms: int,
    input_tokens: int,
    output_tokens: int,
    cache_creation_input_tokens: int = 0,
    cache_read_input_tokens: int = 0,
) -> None:
    """Emit a single structured JSON line describing one AI provider round.

    Never raises: observability must not break the caller. Malformed
    inputs fall back to empty strings / zero ints.

    Cache metrics default to zero for call sites that don't pass them
    (e.g. pre-Phase-10 paths), so the log format stays backward
    compatible.
    """
    try:
        payload = {
            "trace_id": trace_id,
            "conversation_id": str(conversation_id) if conversation_id else None,
            "family_id": str(family_id) if family_id else None,
            "member_id": str(member_id) if member_id else None,
            "model": model,
            "tool_name": tool_name,
            "duration_ms": int(duration_ms),
            "input_tokens": int(input_tokens or 0),
            "output_tokens": int(output_tokens or 0),
            "cache_creation_input_tokens": int(cache_creation_input_tokens or 0),
            "cache_read_input_tokens": int(cache_read_input_tokens or 0),
            "cost_usd": round(
                estimate_cost_usd(model, int(input_tokens or 0), int(output_tokens or 0)),
                6,
            ),
            "event_ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        logger.info("%s %s", AI_CALL_EVENT, json.dumps(payload, separators=(",", ":")))
    except Exception as exc:  # pragma: no cover — observability must never crash
        logger.warning("ai_call_log_failed: %s", str(exc)[:200])

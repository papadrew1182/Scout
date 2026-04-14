"""Scout read-only MCP server.

Transport: stdio (Claude Desktop and most MCP clients default to this).
Scope: one family, adult-only visibility. The operator picks the
family at launch time via environment variables.

## Authentication model

The server is a local stdio subprocess that the user launches from
Claude Desktop's MCP config. Authentication is three things stacked:

1. The user has local DB creds (``SCOUT_DATABASE_URL``) — no one else
   on the internet has the DB.
2. The user has explicitly set ``SCOUT_MCP_TOKEN`` — an opt-in gate.
   If missing, the server refuses to boot. This prevents a stray
   process from accidentally exposing data.
3. The user has explicitly set ``SCOUT_MCP_FAMILY_ID`` — scopes every
   query to that family. There is NO tool that accepts a family_id
   argument; cross-family access is structurally impossible.

The token itself is not transmitted anywhere — it is a boot-time
feature flag, not a network credential. This matches how stdio MCP
servers normally work.

## Data exposed (all read-only)

- ``get_family_schedule`` — events in a date range
- ``get_tasks_summary`` — personal tasks + today's routine/chore state
- ``get_current_meal_plan`` — this week's weekly plan
- ``get_grocery_list`` — pending grocery items
- ``get_action_inbox`` — pending parent action items (titles only;
  no raw moderation content)
- ``get_recent_briefs`` — last N daily briefs and weekly retros
- ``get_homework_summary`` — homework session rollup
- ``get_ai_usage`` — cost-dashboard rollup for the last week

## Data explicitly NOT exposed

- Raw moderation-blocked message text
- Child personality_notes (parent-private)
- Any write tool (no create / update / delete)
- Any cross-family view
- Raw database queries
- Internal audit rows
"""

from __future__ import annotations

import logging
import os
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from typing import Any, AsyncIterator

logger = logging.getLogger("scout.mcp")


class _BootError(RuntimeError):
    """Raised before the MCP loop starts when the environment is
    missing a required safety gate. Surfaces to stderr so Claude
    Desktop users see a clear message in their MCP logs."""


def _load_family_id() -> uuid.UUID:
    """Require SCOUT_MCP_FAMILY_ID and SCOUT_MCP_TOKEN at boot.

    Both are the opt-in gate described in the module docstring. Missing
    either one raises a _BootError before the server touches the DB."""
    token = os.environ.get("SCOUT_MCP_TOKEN", "").strip()
    if not token:
        raise _BootError(
            "SCOUT_MCP_TOKEN must be set before launching scout_mcp. "
            "This is the opt-in gate that prevents accidental exposure. "
            "Any non-empty string works — the server does not verify it "
            "against a remote service."
        )
    fam_raw = os.environ.get("SCOUT_MCP_FAMILY_ID", "").strip()
    if not fam_raw:
        raise _BootError(
            "SCOUT_MCP_FAMILY_ID must be set before launching scout_mcp. "
            "This scopes every read to a single family. Copy the family "
            "UUID from the Scout database."
        )
    try:
        return uuid.UUID(fam_raw)
    except ValueError as e:
        raise _BootError(f"SCOUT_MCP_FAMILY_ID is not a valid UUID: {e}")


def _session():
    """Lazy DB session. Imports stay inside the function so a missing
    Scout dependency doesn't crash the import of the MCP package."""
    from app.database import SessionLocal
    return SessionLocal()


# ---------------------------------------------------------------------------
# Pure read functions — each wraps existing Scout services.
# ---------------------------------------------------------------------------


def _get_family_schedule(family_id: uuid.UUID, days: int = 7) -> dict:
    from app.services import calendar_service

    start = datetime.now()
    end = start + timedelta(days=max(1, min(days, 30)))
    with _session() as db:
        events = calendar_service.list_events(db, family_id, start=start, end=end)
        return {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "events": [
                {
                    "id": str(e.id),
                    "title": e.title,
                    "starts_at": e.starts_at.isoformat() if e.starts_at else None,
                    "ends_at": e.ends_at.isoformat() if e.ends_at else None,
                    "location": e.location,
                    "all_day": bool(e.all_day),
                }
                for e in events
            ],
        }


def _get_tasks_summary(family_id: uuid.UUID) -> dict:
    from app.services import personal_tasks_service, task_instance_service

    today = date.today()
    with _session() as db:
        tasks = personal_tasks_service.list_personal_tasks(
            db, family_id, incomplete_only=True
        )
        instances = task_instance_service.list_task_instances(
            db, family_id, instance_date=today
        )
        return {
            "date": today.isoformat(),
            "incomplete_personal_tasks": [
                {
                    "id": str(t.id),
                    "title": t.title,
                    "assigned_to": str(t.assigned_to) if t.assigned_to else None,
                    "priority": t.priority,
                    "due_at": t.due_at.isoformat() if t.due_at else None,
                }
                for t in tasks
            ],
            "today_chores_and_routines": [
                {
                    "id": str(i.id),
                    "family_member_id": str(i.family_member_id),
                    "due_at": i.due_at.isoformat() if i.due_at else None,
                    "is_completed": bool(i.is_completed),
                    "routine_id": str(i.routine_id) if i.routine_id else None,
                    "chore_template_id": (
                        str(i.chore_template_id) if i.chore_template_id else None
                    ),
                }
                for i in instances
            ],
        }


def _get_current_meal_plan(family_id: uuid.UUID) -> dict:
    from app.services import weekly_meal_plan_service

    with _session() as db:
        plan = weekly_meal_plan_service.get_current_weekly_meal_plan(db, family_id)
        if plan is None:
            return {"status": "no_current_plan"}
        return {
            "id": str(plan.id),
            "week_start_date": plan.week_start_date.isoformat(),
            "status": plan.status,
            "plan_summary": plan.plan_summary,
            "week_plan": plan.week_plan,
            "prep_plan": plan.prep_plan,
        }


def _get_grocery_list(family_id: uuid.UUID) -> dict:
    from app.services import grocery_service

    with _session() as db:
        items = grocery_service.list_grocery_items(
            db, family_id, include_purchased=False
        )
        return {
            "count": len(items),
            "items": [
                {
                    "id": str(i.id),
                    "title": i.title,
                    "quantity": i.quantity,
                    "unit": i.unit,
                    "category": i.category,
                    "preferred_store": i.preferred_store,
                    "approval_status": i.approval_status,
                }
                for i in items
            ],
        }


def _get_action_inbox(family_id: uuid.UUID) -> dict:
    from sqlalchemy import select

    from app.models.action_items import ParentActionItem

    with _session() as db:
        rows = list(
            db.scalars(
                select(ParentActionItem)
                .where(ParentActionItem.family_id == family_id)
                .where(ParentActionItem.status == "pending")
                .order_by(ParentActionItem.created_at.desc())
                .limit(40)
            ).all()
        )
        items: list[dict] = []
        for r in rows:
            # Intentionally omit detail for moderation_alert — that
            # field links to a blocked conversation whose contents
            # parents should open in-app, not from MCP.
            safe_detail = (
                None
                if r.action_type == "moderation_alert"
                else r.detail
            )
            items.append(
                {
                    "id": str(r.id),
                    "action_type": r.action_type,
                    "title": r.title,
                    "detail": safe_detail,
                    "created_at": r.created_at.isoformat(),
                }
            )
        return {"count": len(items), "items": items}


def _get_recent_briefs(family_id: uuid.UUID, limit: int = 5) -> dict:
    from sqlalchemy import select

    from app.models.action_items import ParentActionItem

    limit = max(1, min(limit, 30))
    with _session() as db:
        rows = list(
            db.scalars(
                select(ParentActionItem)
                .where(ParentActionItem.family_id == family_id)
                .where(
                    ParentActionItem.action_type.in_(
                        ["daily_brief", "weekly_retro", "anomaly_alert"]
                    )
                )
                .order_by(ParentActionItem.created_at.desc())
                .limit(limit)
            ).all()
        )
        return {
            "count": len(rows),
            "briefs": [
                {
                    "id": str(r.id),
                    "kind": r.action_type,
                    "title": r.title,
                    "created_at": r.created_at.isoformat(),
                    "content": r.detail,
                }
                for r in rows
            ],
        }


def _get_homework_summary(family_id: uuid.UUID, days: int = 7) -> dict:
    from app.ai.homework import homework_summary

    days = max(1, min(days, 60))
    with _session() as db:
        return homework_summary(db, family_id=family_id, days=days)


def _get_ai_usage(family_id: uuid.UUID, days: int = 7) -> dict:
    from app.ai.pricing import build_usage_report

    days = max(1, min(days, 60))
    with _session() as db:
        return build_usage_report(db, family_id=family_id, days=days)


# ---------------------------------------------------------------------------
# MCP server wiring
# ---------------------------------------------------------------------------


# Tier 5 F19 — extracted so both stdio and HTTP transports can share
# the same dispatch table. ``scope`` is one of 'parent' or 'child'.
# Parent scope gets the full tool set; child scope is restricted to
# a privacy-safe subset that never includes inbox, briefs, cost, or
# homework rollup.
_CHILD_ALLOWED_TOOLS = frozenset(
    {
        "get_family_schedule",
        "get_tasks_summary",
        "get_current_meal_plan",
        "get_grocery_list",
    }
)


def build_tool_registry(
    family_id: uuid.UUID, scope: str = "parent"
) -> tuple[list[tuple[str, str, dict, Any]], dict]:
    """Return (tool_specs, handlers_by_name) filtered by scope.

    Each tool_spec is (name, description, input_schema, handler).
    Handlers are closures over family_id — no tool takes a
    family-scoping argument, so cross-family access is structurally
    impossible at the dispatch layer."""
    specs: list[tuple[str, str, dict, Any]] = [
        (
            "get_family_schedule",
            "Return upcoming family events in a date window (default 7 days).",
            {
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "minimum": 1, "maximum": 30},
                },
            },
            lambda args: _get_family_schedule(
                family_id, days=int(args.get("days") or 7)
            ),
        ),
        (
            "get_tasks_summary",
            "Return incomplete personal tasks and today's routine/chore state.",
            {"type": "object", "properties": {}},
            lambda args: _get_tasks_summary(family_id),
        ),
        (
            "get_current_meal_plan",
            "Return the current approved weekly meal plan (or no_current_plan).",
            {"type": "object", "properties": {}},
            lambda args: _get_current_meal_plan(family_id),
        ),
        (
            "get_grocery_list",
            "Return pending grocery items (not yet purchased).",
            {"type": "object", "properties": {}},
            lambda args: _get_grocery_list(family_id),
        ),
        (
            "get_action_inbox",
            "Return pending parent action items. Moderation-alert rows "
            "have their detail field redacted.",
            {"type": "object", "properties": {}},
            lambda args: _get_action_inbox(family_id),
        ),
        (
            "get_recent_briefs",
            "Return recent morning briefs, weekly retros, and anomaly alerts.",
            {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "minimum": 1, "maximum": 30},
                },
            },
            lambda args: _get_recent_briefs(
                family_id, limit=int(args.get("limit") or 5)
            ),
        ),
        (
            "get_homework_summary",
            "Return per-child homework session rollup for the last N days.",
            {
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "minimum": 1, "maximum": 60},
                },
            },
            lambda args: _get_homework_summary(
                family_id, days=int(args.get("days") or 7)
            ),
        ),
        (
            "get_ai_usage",
            "Return AI usage + approximate cost rollup for the last N days.",
            {
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "minimum": 1, "maximum": 60},
                },
            },
            lambda args: _get_ai_usage(
                family_id, days=int(args.get("days") or 7)
            ),
        ),
    ]

    if scope == "child":
        specs = [s for s in specs if s[0] in _CHILD_ALLOWED_TOOLS]

    handlers_by_name = {name: fn for name, _, _, fn in specs}
    return specs, handlers_by_name


def dispatch_tool(
    family_id: uuid.UUID, scope: str, name: str, arguments: dict
) -> dict:
    """Run a tool by name for the given family+scope. Returns the raw
    result dict (or {"error": ...} on failure). Used by both the
    stdio transport's call_tool handler and the HTTP/SSE
    companion transport in app/routes/mcp_http.py."""
    _, handlers = build_tool_registry(family_id, scope=scope)
    handler = handlers.get(name)
    if handler is None:
        return {
            "error": f"Unknown tool '{name}'",
            "known": sorted(handlers.keys()),
        }
    try:
        return handler(arguments or {})
    except Exception as e:
        logger.exception("scout_mcp_tool_failed name=%s", name)
        return {"error": f"{name}: {e}"}


def build_server(family_id: uuid.UUID, scope: str = "parent"):
    """Construct the MCP stdio server with every tool curried to the
    configured family. Returned as the mcp.Server instance so the
    caller can also run it under different transports in tests."""
    from mcp.server import Server
    from mcp.types import TextContent, Tool

    server = Server("scout-readonly")

    specs, handlers_by_name = build_tool_registry(family_id, scope=scope)
    tool_list = [
        Tool(name=name, description=desc, inputSchema=schema)
        for name, desc, schema, _ in specs
    ]

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return tool_list

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        handler = handlers_by_name.get(name)
        if handler is None:
            return [
                TextContent(
                    type="text",
                    text=f"Unknown tool '{name}'. Known: {sorted(handlers_by_name)}",
                )
            ]
        try:
            result = handler(arguments or {})
            # MCP tool results are text-typed. JSON-encode so the
            # client can parse structured data out of the content.
            import json
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        except Exception as e:
            logger.exception("scout_mcp_tool_failed name=%s", name)
            return [TextContent(type="text", text=f"Error in {name}: {e}")]

    return server


async def run_stdio() -> None:
    """Boot the server and run it on stdio. The caller (e.g. Claude
    Desktop) owns the subprocess lifecycle — we just wire the MCP
    session to stdin/stdout and await completion."""
    family_id = _load_family_id()
    from mcp.server.stdio import stdio_server

    server = build_server(family_id)
    async with stdio_server() as (read, write):
        await server.run(
            read,
            write,
            server.create_initialization_options(),
        )


def main() -> None:
    import asyncio

    try:
        asyncio.run(run_stdio())
    except _BootError as e:
        sys.stderr.write(f"[scout_mcp] boot error: {e}\n")
        sys.exit(2)

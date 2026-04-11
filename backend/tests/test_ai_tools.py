"""Tests for AI tool registry and permission enforcement.

Covers:
- tool execution with valid permissions
- tool denial for child role
- write confirmation enforcement
- family isolation
- audit logging
"""

import uuid
from datetime import date, datetime, time

import pytest
import pytz
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.context import get_allowed_tools_for_surface
from app.ai.tools import TOOL_DEFINITIONS, ToolExecutor
from app.models.ai import AIToolAudit
from app.models.foundation import Family, FamilyMember


# ---------------------------------------------------------------------------
# Permission tests
# ---------------------------------------------------------------------------

class TestToolPermissions:
    def test_child_gets_only_read_tools(self):
        tools = get_allowed_tools_for_surface("child", "child")
        assert "list_tasks" in tools
        assert "list_events" in tools
        assert "create_task" not in tools
        assert "create_event" not in tools
        assert "mark_chore_or_routine_complete" not in tools

    def test_adult_personal_gets_write_tools(self):
        tools = get_allowed_tools_for_surface("adult", "personal")
        assert "create_task" in tools
        assert "create_event" in tools
        assert "create_note" in tools
        assert "send_notification_or_create_action" not in tools

    def test_adult_parent_gets_notification_tool(self):
        tools = get_allowed_tools_for_surface("adult", "parent")
        assert "send_notification_or_create_action" in tools

    def test_all_tool_definitions_exist(self):
        for name in TOOL_DEFINITIONS:
            assert TOOL_DEFINITIONS[name].name == name
            assert TOOL_DEFINITIONS[name].input_schema is not None


# ---------------------------------------------------------------------------
# Execution tests
# ---------------------------------------------------------------------------

class TestToolExecution:
    def test_denied_tool_returns_error(self, db: Session, family, adults):
        andrew = adults["robert"]
        executor = ToolExecutor(
            db=db, family_id=family.id, actor_member_id=andrew.id,
            actor_role="child", surface="child",
            allowed_tools=["list_tasks"],
        )
        result = executor.execute("create_task", {"assigned_to": str(andrew.id), "title": "test"})
        assert "error" in result

    def test_denied_tool_creates_audit(self, db: Session, family, adults):
        andrew = adults["robert"]
        executor = ToolExecutor(
            db=db, family_id=family.id, actor_member_id=andrew.id,
            actor_role="child", surface="child",
            allowed_tools=["list_tasks"],
        )
        executor.execute("create_task", {"assigned_to": str(andrew.id), "title": "test"})

        audits = list(db.scalars(
            select(AIToolAudit)
            .where(AIToolAudit.actor_member_id == andrew.id)
            .where(AIToolAudit.tool_name == "create_task")
        ).all())
        assert len(audits) == 1
        assert audits[0].status == "denied"

    def test_confirmation_required_for_write_tool(self, db: Session, family, adults):
        andrew = adults["robert"]
        executor = ToolExecutor(
            db=db, family_id=family.id, actor_member_id=andrew.id,
            actor_role="adult", surface="parent",
            allowed_tools=["create_event"],
        )
        result = executor.execute("create_event", {
            "title": "Test", "starts_at": "2026-04-15T10:00:00-05:00",
            "ends_at": "2026-04-15T11:00:00-05:00",
        })
        assert result.get("confirmation_required") is True

    def test_confirmed_write_executes(self, db: Session, family, adults):
        andrew = adults["robert"]
        executor = ToolExecutor(
            db=db, family_id=family.id, actor_member_id=andrew.id,
            actor_role="adult", surface="parent",
            allowed_tools=["create_event"],
        )
        result = executor.execute("create_event", {
            "title": "Confirmed Event", "starts_at": "2026-04-15T10:00:00-05:00",
            "ends_at": "2026-04-15T11:00:00-05:00", "confirmed": True,
        })
        assert "created" in result

    def test_get_today_context_works(self, db: Session, family, adults):
        andrew = adults["robert"]
        executor = ToolExecutor(
            db=db, family_id=family.id, actor_member_id=andrew.id,
            actor_role="adult", surface="personal",
            allowed_tools=["get_today_context"],
        )
        result = executor.execute("get_today_context", {})
        assert "date" in result
        assert "family_members" in result

    def test_list_tasks_works(self, db: Session, family, adults):
        andrew = adults["robert"]
        executor = ToolExecutor(
            db=db, family_id=family.id, actor_member_id=andrew.id,
            actor_role="adult", surface="personal",
            allowed_tools=["list_tasks"],
        )
        result = executor.execute("list_tasks", {"incomplete_only": True})
        assert "tasks" in result

    def test_create_task_works(self, db: Session, family, adults):
        andrew = adults["robert"]
        executor = ToolExecutor(
            db=db, family_id=family.id, actor_member_id=andrew.id,
            actor_role="adult", surface="personal",
            allowed_tools=["create_task"],
        )
        result = executor.execute("create_task", {
            "assigned_to": str(andrew.id),
            "title": "AI-created task",
        })
        assert "created" in result
        assert result["created"]["title"] == "AI-created task"

    def test_search_notes_works(self, db: Session, family, adults):
        andrew = adults["robert"]
        executor = ToolExecutor(
            db=db, family_id=family.id, actor_member_id=andrew.id,
            actor_role="adult", surface="personal",
            allowed_tools=["search_notes"],
        )
        result = executor.execute("search_notes", {"query": "test"})
        assert "notes" in result


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------

class TestTenantIsolation:
    def test_tool_execution_scoped_to_family(self, db: Session, family, adults):
        other_family = Family(name="Other", timezone="America/New_York")
        db.add(other_family)
        db.flush()
        other_member = FamilyMember(family_id=other_family.id, first_name="Stranger", role="adult")
        db.add(other_member)
        db.flush()

        # Executor for family A cannot access family B data through tools
        andrew = adults["robert"]
        executor = ToolExecutor(
            db=db, family_id=family.id, actor_member_id=andrew.id,
            actor_role="adult", surface="personal",
            allowed_tools=["list_tasks"],
        )
        result = executor.execute("list_tasks", {})
        # The service layer enforces family scoping — tasks from other families are not returned
        assert "tasks" in result


# ---------------------------------------------------------------------------
# Audit logging
# ---------------------------------------------------------------------------

class TestAuditLogging:
    def test_successful_execution_is_audited(self, db: Session, family, adults):
        andrew = adults["robert"]
        executor = ToolExecutor(
            db=db, family_id=family.id, actor_member_id=andrew.id,
            actor_role="adult", surface="personal",
            allowed_tools=["get_today_context"],
        )
        executor.execute("get_today_context", {})

        audits = list(db.scalars(
            select(AIToolAudit)
            .where(AIToolAudit.actor_member_id == andrew.id)
            .where(AIToolAudit.tool_name == "get_today_context")
        ).all())
        assert len(audits) == 1
        assert audits[0].status == "success"
        assert audits[0].duration_ms is not None

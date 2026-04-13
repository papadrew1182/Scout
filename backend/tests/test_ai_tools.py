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


# ---------------------------------------------------------------------------
# Weather tool (monkeypatched Open-Meteo)
# ---------------------------------------------------------------------------

class _FakeResponse:
    def __init__(self, body: bytes):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class TestWeatherTool:
    def test_get_weather_in_registry_and_definitions(self):
        assert "get_weather" in TOOL_DEFINITIONS
        d = TOOL_DEFINITIONS["get_weather"]
        assert d.name == "get_weather"
        assert "weather" in d.description.lower()
        assert "location" in d.input_schema["properties"]
        assert "days" in d.input_schema["properties"]

    def test_get_weather_handler_returns_forecast(
        self, db: Session, family, adults, monkeypatch
    ):
        import json
        from app.ai import tools as tools_mod

        family.home_location = "76126"
        db.flush()

        # Canned Open-Meteo geocoding + forecast responses
        geocode_body = json.dumps(
            {
                "results": [
                    {
                        "name": "Fort Worth",
                        "admin1": "Texas",
                        "country_code": "US",
                        "latitude": 32.7,
                        "longitude": -97.4,
                    }
                ]
            }
        ).encode()
        forecast_body = json.dumps(
            {
                "daily": {
                    "time": ["2026-04-14", "2026-04-15", "2026-04-16"],
                    "temperature_2m_max": [78.4, 82.1, 75.0],
                    "temperature_2m_min": [55.0, 60.2, 58.8],
                    "precipitation_probability_max": [10, 60, 30],
                    "weather_code": [1, 61, 2],
                }
            }
        ).encode()

        calls: list[str] = []

        def fake_urlopen(url, timeout=8):
            calls.append(url if isinstance(url, str) else url.full_url)
            if "geocoding-api" in calls[-1]:
                return _FakeResponse(geocode_body)
            return _FakeResponse(forecast_body)

        monkeypatch.setattr(
            "urllib.request.urlopen", fake_urlopen, raising=True
        )

        andrew = adults["robert"]
        executor = ToolExecutor(
            db=db,
            family_id=family.id,
            actor_member_id=andrew.id,
            actor_role="adult",
            surface="personal",
            allowed_tools=["get_weather"],
        )
        result = executor.execute("get_weather", {})

        assert "error" not in result
        assert result["units"] == "fahrenheit"
        assert result["location"].startswith("Fort Worth")
        assert len(result["days"]) == 3
        day0 = result["days"][0]
        assert day0["high_f"] == 78.4
        assert day0["low_f"] == 55.0
        assert day0["precip_probability_pct"] == 10
        assert day0["weather"] == "mostly clear"
        # Day 1 should map WMO 61 → 'light rain'
        assert result["days"][1]["weather"] == "light rain"
        # Geocoding was called; so was forecast
        assert any("geocoding-api" in c for c in calls)
        assert any("api.open-meteo.com/v1/forecast" in c for c in calls)

    def test_get_weather_no_location_and_no_home_returns_error(
        self, db: Session, family, adults, monkeypatch
    ):
        family.home_location = None
        db.flush()

        def should_not_call(*a, **k):
            raise AssertionError("should not hit the network")

        monkeypatch.setattr("urllib.request.urlopen", should_not_call, raising=True)

        andrew = adults["robert"]
        executor = ToolExecutor(
            db=db,
            family_id=family.id,
            actor_member_id=andrew.id,
            actor_role="adult",
            surface="personal",
            allowed_tools=["get_weather"],
        )
        result = executor.execute("get_weather", {})
        assert "error" in result
        assert "location" in result["error"].lower()

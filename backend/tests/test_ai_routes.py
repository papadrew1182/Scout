"""Integration tests for AI routes.

Tests route validation, family/member enforcement, and response shape.
Does NOT call the actual Anthropic API — tests that require real AI
responses are excluded. These tests verify the plumbing.
"""

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ai import AIConversation, AIMessage
from app.models.foundation import Family, FamilyMember
from app.ai.orchestrator import get_or_create_conversation


class TestConversationState:
    def test_create_conversation(self, db: Session, family, adults):
        andrew = adults["robert"]
        conv = get_or_create_conversation(db, family.id, andrew.id, "personal")
        assert conv.id is not None
        assert conv.family_id == family.id
        assert conv.family_member_id == andrew.id
        assert conv.surface == "personal"
        assert conv.status == "active"

    def test_retrieve_existing_conversation(self, db: Session, family, adults):
        andrew = adults["robert"]
        conv1 = get_or_create_conversation(db, family.id, andrew.id, "personal")
        conv2 = get_or_create_conversation(db, family.id, andrew.id, "personal", conv1.id)
        assert conv1.id == conv2.id

    def test_wrong_family_creates_new(self, db: Session, family, adults):
        andrew = adults["robert"]
        conv1 = get_or_create_conversation(db, family.id, andrew.id, "personal")

        other_family = Family(name="Other", timezone="UTC")
        db.add(other_family)
        db.flush()
        other_member = FamilyMember(family_id=other_family.id, first_name="X", role="adult")
        db.add(other_member)
        db.flush()

        # Passing conv1.id for a different family should create a new conversation
        conv2 = get_or_create_conversation(db, other_family.id, other_member.id, "personal", conv1.id)
        assert conv2.id != conv1.id


class TestFamilyIsolation:
    def test_conversations_are_family_scoped(self, db: Session, family, adults):
        andrew = adults["robert"]
        conv = get_or_create_conversation(db, family.id, andrew.id, "personal")

        # Query for another family returns nothing
        other_family = Family(name="Other", timezone="UTC")
        db.add(other_family)
        db.flush()

        convs = list(db.scalars(
            select(AIConversation)
            .where(AIConversation.family_id == other_family.id)
        ).all())
        assert len(convs) == 0


class TestWriteConfirmation:
    def test_confirmation_required_tools_list(self):
        from app.ai.tools import CONFIRMATION_REQUIRED
        assert "create_event" in CONFIRMATION_REQUIRED
        assert "update_event" in CONFIRMATION_REQUIRED
        assert "mark_chore_or_routine_complete" in CONFIRMATION_REQUIRED
        # Read tools should never require confirmation
        assert "list_tasks" not in CONFIRMATION_REQUIRED
        assert "get_today_context" not in CONFIRMATION_REQUIRED


class _FakeAIResponse:
    """Minimal AIResponse stand-in for tests that don't hit the real API."""

    def __init__(self, content: str = "", tool_calls=None, model: str = "fake-model"):
        self.content = content
        self.tool_calls = tool_calls or []
        self.stop_reason = "tool_use" if tool_calls else "end_turn"
        self.model = model
        self.input_tokens = 1
        self.output_tokens = 1


class _FakeToolCall:
    def __init__(self, id: str, name: str, input: dict):
        self.id = id
        self.name = name
        self.input = input


class _ScriptedProvider:
    """Provider that returns pre-canned AIResponses, one per chat() call."""

    def __init__(self, script):
        self._script = list(script)
        self.calls = 0

    def chat(self, **_kwargs):
        self.calls += 1
        if not self._script:
            return _FakeAIResponse(content="(script exhausted)")
        return self._script.pop(0)


class TestPendingConfirmationPlumbing:
    """Verify the orchestrator structurally surfaces pending_confirmation in
    the HTTP-response dict when a confirmation-gated tool is invoked by the
    model. Proves the ScoutPanel confirm-card affordance has a real backing
    payload to render against.
    """

    def test_confirmation_required_surfaces_pending_confirmation(
        self, db: Session, family, adults, monkeypatch
    ):
        from app.ai import orchestrator

        andrew = adults["robert"]

        scripted = _ScriptedProvider(
            [
                _FakeAIResponse(
                    content="OK, I'll create that event.",
                    tool_calls=[
                        _FakeToolCall(
                            id="toolu_fake_1",
                            name="create_event",
                            input={
                                "title": "Soccer practice",
                                "start": "2099-01-01T18:00:00Z",
                                "end": "2099-01-01T19:30:00Z",
                            },
                        )
                    ],
                )
            ]
        )
        monkeypatch.setattr(orchestrator, "get_provider", lambda: scripted)

        result = orchestrator.chat(
            db=db,
            family_id=family.id,
            member_id=andrew.id,
            surface="personal",
            user_message="Add soccer practice tonight at 6",
        )

        # One provider call — we must break as soon as the tool returns
        # confirmation_required, not re-prompt the model.
        assert scripted.calls == 1, "orchestrator should stop on confirmation_required"

        pending = result.get("pending_confirmation")
        assert pending is not None, "pending_confirmation must be surfaced"
        assert pending["tool_name"] == "create_event"
        assert "title" in pending["arguments"]
        assert pending["message"]  # non-empty human-readable text

        # Response field must not be empty even though the LLM didn't get a
        # second chance to narrate.
        assert result["response"], "response must be non-empty"

        # Handoff must be absent on the confirmation path.
        assert result.get("handoff") is None

    def test_confirm_tool_direct_path_skips_provider(
        self, db: Session, family, adults, monkeypatch
    ):
        """The confirm_tool path must execute the tool directly without
        invoking the LLM provider at all. Proves the ScoutPanel 'Confirm'
        tap is cheap and deterministic."""
        from app.ai import orchestrator

        andrew = adults["robert"]

        scripted = _ScriptedProvider([])  # zero allowed calls
        monkeypatch.setattr(orchestrator, "get_provider", lambda: scripted)

        # Pass a deliberately-unregistered tool name. We're not testing a
        # real tool execution here — we're proving the path skips the
        # provider and still returns a structured result dict with the
        # direct-execution model tag. Tool executor will return an error
        # dict for the bogus tool, which the orchestrator surfaces as the
        # response text.
        result = orchestrator.chat(
            db=db,
            family_id=family.id,
            member_id=andrew.id,
            surface="personal",
            user_message="",
            confirm_tool={
                "tool_name": "nonexistent_debug_tool_for_test",
                "arguments": {},
            },
        )

        assert scripted.calls == 0, "confirm_tool path must not call the provider"
        assert result["model"] == "confirmation-direct"
        assert result.get("pending_confirmation") is None
        assert isinstance(result["response"], str)
        assert result["response"], "response must be non-empty even on error"

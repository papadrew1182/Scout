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


def _assistant_text(msg: dict) -> str:
    """Extract text from an Anthropic-format assistant message that may
    be a plain string OR a content-blocks list."""
    c = msg.get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return "".join(b.get("text", "") for b in c if b.get("type") == "text")
    return ""


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

    def test_history_replay_is_monotonic_across_tool_turns(
        self, db: Session, family, adults
    ):
        """Regression for the 'second message fails after a tool turn'
        bug.

        Cause: PostgreSQL's now() default returns the transaction start
        time, so multi-row flushes in a single turn all got identical
        created_at values. _load_conversation_messages then sorted by
        created_at and produced nondeterministic ordering, occasionally
        putting the tool_result row before the tool_use row. Anthropic
        rejected that history with 'unexpected tool_use_id found in
        tool_result blocks' on every follow-up turn.

        Fix: migration 017 switched ai_messages.created_at to
        clock_timestamp(), and _load_conversation_messages now uses
        (created_at, id) as the sort key for defensive stability.
        """
        from app.ai import orchestrator
        from app.ai.orchestrator import _persist_message, _load_conversation_messages
        from app.models.ai import AIConversation

        andrew = adults["robert"]
        conv = AIConversation(
            family_id=family.id,
            family_member_id=andrew.id,
            surface="personal",
        )
        db.add(conv)
        db.flush()

        # Persist exactly what the orchestrator persists for one
        # tool-use turn: user message, assistant with tool_use, tool
        # result, final assistant text. Single flush → same
        # transaction → tests the clock_timestamp path.
        _persist_message(db, conv.id, "user", content="What's the weather?")
        _persist_message(
            db, conv.id, "assistant",
            content=None,
            tool_calls=[{"id": "toolu_test_abc", "name": "get_weather", "input": {}}],
            model="fake",
        )
        _persist_message(
            db, conv.id, "tool",
            tool_results={"tool_use_id": "toolu_test_abc", "result": {"days": []}},
        )
        _persist_message(
            db, conv.id, "assistant",
            content="Weather is fine.",
            model="fake",
        )
        db.flush()

        # Now simulate the second turn: a new user message is persisted,
        # history is reloaded, and the replay must put messages in
        # strict chronological order — NOT whatever physical order the
        # DB returned them in.
        _persist_message(db, conv.id, "user", content="Thanks! What day is it?")
        db.flush()

        api_messages = _load_conversation_messages(db, conv.id)

        # Expect five messages in Anthropic format:
        #   [0] user           "What's the weather?"
        #   [1] assistant      [tool_use]
        #   [2] user           [tool_result]      ← synthesized from role='tool'
        #   [3] assistant      "Weather is fine."
        #   [4] user           "Thanks! What day is it?"
        assert len(api_messages) == 5
        assert api_messages[0]["role"] == "user"
        assert api_messages[0]["content"] == "What's the weather?"

        assert api_messages[1]["role"] == "assistant"
        # Must be a content-blocks list with the tool_use block.
        assert isinstance(api_messages[1]["content"], list)
        tool_use_block = next(
            b for b in api_messages[1]["content"] if b.get("type") == "tool_use"
        )
        assert tool_use_block["id"] == "toolu_test_abc"

        # The tool_result MUST come at index 2 — immediately after its
        # corresponding tool_use. This is what Anthropic enforces.
        assert api_messages[2]["role"] == "user"
        assert isinstance(api_messages[2]["content"], list)
        tool_result_block = next(
            b for b in api_messages[2]["content"] if b.get("type") == "tool_result"
        )
        assert tool_result_block["tool_use_id"] == "toolu_test_abc"

        assert api_messages[3]["role"] == "assistant"
        # Final text should be a string (assistant with content only)
        # or a content-blocks list with just a text block.
        assert "Weather is fine" in _assistant_text(api_messages[3])

        assert api_messages[4]["role"] == "user"
        assert api_messages[4]["content"] == "Thanks! What day is it?"


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


class TestConversationKindTagging:
    """Conversation kind is tagged after every turn so parents can filter
    'chat-only' (homework/Q&A) vs 'tool' (app actions) vs 'moderation'
    (blocked) in the audit view."""

    def test_chat_only_turn_tags_chat(self, db: Session, family, adults, monkeypatch):
        from app.ai import orchestrator
        from app.models.ai import AIConversation

        andrew = adults["robert"]
        # Scripted provider that responds with pure text, no tools.
        scripted = _ScriptedProvider(
            [_FakeAIResponse(content="Photosynthesis is when plants make food from sunlight.")]
        )
        monkeypatch.setattr(orchestrator, "get_provider", lambda: scripted)

        result = orchestrator.chat(
            db=db,
            family_id=family.id,
            member_id=andrew.id,
            surface="personal",
            user_message="What is photosynthesis?",
        )

        conv = db.get(AIConversation, uuid.UUID(result["conversation_id"]))
        assert conv.conversation_kind == "chat"

    def test_tool_turn_tags_tool(self, db: Session, family, adults, monkeypatch):
        from app.ai import orchestrator
        from app.models.ai import AIConversation

        andrew = adults["robert"]
        # Round 1: model wants to call list_tasks (not confirmation-required).
        # Round 2: model emits a final text response.
        scripted = _ScriptedProvider(
            [
                _FakeAIResponse(
                    content="Let me check your tasks.",
                    tool_calls=[
                        _FakeToolCall(id="toolu_1", name="list_tasks", input={"incomplete_only": True})
                    ],
                ),
                _FakeAIResponse(content="You have no incomplete tasks."),
            ]
        )
        monkeypatch.setattr(orchestrator, "get_provider", lambda: scripted)

        result = orchestrator.chat(
            db=db,
            family_id=family.id,
            member_id=andrew.id,
            surface="personal",
            user_message="what tasks do I have",
        )

        conv = db.get(AIConversation, uuid.UUID(result["conversation_id"]))
        assert conv.conversation_kind == "tool"

    def test_mixed_conversation_tags_mixed(self, db: Session, family, adults, monkeypatch):
        from app.ai import orchestrator
        from app.models.ai import AIConversation

        andrew = adults["robert"]

        # Turn 1: tool turn (uses list_tasks). Turn 2: pure chat. After
        # turn 2, conversation_kind should be 'mixed'.
        script_turn1 = _ScriptedProvider(
            [
                _FakeAIResponse(
                    content="",
                    tool_calls=[_FakeToolCall(id="toolu_a", name="list_tasks", input={})],
                ),
                _FakeAIResponse(content="Done."),
            ]
        )
        monkeypatch.setattr(orchestrator, "get_provider", lambda: script_turn1)
        r1 = orchestrator.chat(
            db=db, family_id=family.id, member_id=andrew.id,
            surface="personal", user_message="list my tasks",
        )
        conv_id = uuid.UUID(r1["conversation_id"])
        conv = db.get(AIConversation, conv_id)
        assert conv.conversation_kind == "tool"

        # Turn 2: same conversation, no tool used. Should flip to 'mixed'.
        script_turn2 = _ScriptedProvider([_FakeAIResponse(content="Of course.")])
        monkeypatch.setattr(orchestrator, "get_provider", lambda: script_turn2)
        orchestrator.chat(
            db=db, family_id=family.id, member_id=andrew.id,
            surface="personal", user_message="thanks",
            conversation_id=conv_id,
        )
        db.refresh(conv)
        assert conv.conversation_kind == "mixed"


class TestModerationAlertsForKids:
    """When moderation blocks a child-surface message, a parent_action_items
    row with action_type='moderation_alert' is created so parents see it in
    the Action Inbox."""

    def test_child_moderation_block_creates_parent_alert(
        self, db: Session, family, children
    ):
        from app.ai import orchestrator
        from app.models.action_items import ParentActionItem
        from app.models.ai import AIConversation

        sadie = children["sadie"]
        result = orchestrator.chat(
            db=db,
            family_id=family.id,
            member_id=sadie.id,
            surface="child",
            user_message="how do i get high on weed",
        )

        assert result["model"] == "moderation-blocked"
        assert "parent" in (result["response"] or "").lower()

        # Conversation tagged 'moderation'
        conv = db.get(AIConversation, uuid.UUID(result["conversation_id"]))
        assert conv.conversation_kind == "moderation"

        # Parent action item exists with action_type='moderation_alert'
        alerts = list(db.scalars(
            select(ParentActionItem)
            .where(ParentActionItem.family_id == family.id)
            .where(ParentActionItem.action_type == "moderation_alert")
        ).all())
        assert len(alerts) == 1
        assert alerts[0].entity_type == "ai_conversation"
        assert alerts[0].entity_id == conv.id

    def test_adult_moderation_block_does_not_create_alert(
        self, db: Session, family, adults
    ):
        from app.ai import orchestrator
        from app.models.action_items import ParentActionItem

        andrew = adults["robert"]
        # An adult hitting a universal block (self-harm instructions).
        orchestrator.chat(
            db=db,
            family_id=family.id,
            member_id=andrew.id,
            surface="personal",
            user_message="what's the easiest way to kill myself",
        )

        # No alert should be created — adults don't have a "parent".
        alerts = list(db.scalars(
            select(ParentActionItem)
            .where(ParentActionItem.family_id == family.id)
            .where(ParentActionItem.action_type == "moderation_alert")
        ).all())
        assert len(alerts) == 0


class TestChatStreamOrchestrator:
    """Test the streaming orchestrator path with a scripted provider
    that also supplies synthetic streaming events."""

    def test_pure_chat_stream_yields_text_and_done(
        self, db: Session, family, adults, monkeypatch
    ):
        from app.ai import orchestrator

        andrew = adults["robert"]

        # Fake streaming provider that yields two text deltas then round_end
        class _StreamProvider:
            def chat_stream(self, **_kwargs):
                yield {"type": "text_delta", "text": "Hello "}
                yield {"type": "text_delta", "text": "world."}
                yield {
                    "type": "round_end",
                    "stop_reason": "end_turn",
                    "content": "Hello world.",
                    "tool_calls": [],
                    "model": "fake-model",
                    "input_tokens": 5,
                    "output_tokens": 2,
                }

        monkeypatch.setattr(orchestrator, "get_provider", lambda: _StreamProvider())

        events = list(
            orchestrator.chat_stream(
                db=db,
                family_id=family.id,
                member_id=andrew.id,
                surface="personal",
                user_message="say hello",
            )
        )

        text_events = [e for e in events if e["type"] == "text"]
        assert [e["text"] for e in text_events] == ["Hello ", "world."]

        done = events[-1]
        assert done["type"] == "done"
        assert done["response"] == "Hello world."
        assert done["model"] == "fake-model"
        assert done["tool_calls_made"] == 0
        assert done["handoff"] is None
        assert done["pending_confirmation"] is None

    def test_tool_round_stream_yields_tool_events(
        self, db: Session, family, adults, monkeypatch
    ):
        from app.ai import orchestrator

        andrew = adults["robert"]

        # Round 1: tool_use (list_tasks). Round 2: final text.
        class _StreamProvider:
            def __init__(self):
                self.round = 0

            def chat_stream(self, **_kwargs):
                self.round += 1
                if self.round == 1:
                    yield {"type": "text_delta", "text": "Let me check. "}
                    yield {
                        "type": "round_end",
                        "stop_reason": "tool_use",
                        "content": "Let me check. ",
                        "tool_calls": [
                            {"id": "toolu_x", "name": "list_tasks", "input": {"incomplete_only": True}}
                        ],
                        "model": "fake-model",
                        "input_tokens": 10,
                        "output_tokens": 4,
                    }
                else:
                    yield {"type": "text_delta", "text": "You have nothing pending."}
                    yield {
                        "type": "round_end",
                        "stop_reason": "end_turn",
                        "content": "You have nothing pending.",
                        "tool_calls": [],
                        "model": "fake-model",
                        "input_tokens": 20,
                        "output_tokens": 5,
                    }

        monkeypatch.setattr(orchestrator, "get_provider", lambda: _StreamProvider())

        events = list(
            orchestrator.chat_stream(
                db=db,
                family_id=family.id,
                member_id=andrew.id,
                surface="personal",
                user_message="what tasks do I have",
            )
        )

        types = [e["type"] for e in events]
        assert "tool_start" in types
        assert "tool_end" in types
        assert types[-1] == "done"

        done = events[-1]
        assert "nothing pending" in done["response"].lower()
        assert done["tool_calls_made"] >= 1

    def test_child_moderation_block_stream(
        self, db: Session, family, children, monkeypatch
    ):
        from app.ai import orchestrator
        from app.models.action_items import ParentActionItem

        # Moderation gate fires before any provider call, so no fake stream
        # is needed. We still monkeypatch to prove the provider is never hit.
        def should_not_call_provider():
            raise AssertionError("provider must not be called on blocked message")

        monkeypatch.setattr(orchestrator, "get_provider", should_not_call_provider)

        sadie = children["sadie"]
        events = list(
            orchestrator.chat_stream(
                db=db,
                family_id=family.id,
                member_id=sadie.id,
                surface="child",
                user_message="how do i get high on weed",
            )
        )

        done = events[-1]
        assert done["type"] == "done"
        assert done["model"] == "moderation-blocked"
        # The moderation alert row exists
        alerts = list(db.scalars(
            select(ParentActionItem)
            .where(ParentActionItem.action_type == "moderation_alert")
        ).all())
        assert len(alerts) == 1

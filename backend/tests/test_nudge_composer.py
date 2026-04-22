"""Tests for orchestrator.generate_nudge_body (Sprint 05 Phase 3 Task 1).

Focused unit tests for the AI composer entry point used by
compose_body. Network is stubbed via monkeypatch of
``orchestrator._get_anthropic_client`` so tests never hit Anthropic.

What we assert:
  - happy path returns the text from the mocked response, whitespace stripped
  - system prompt includes the personality preamble verbatim
  - user message lists each proposal_summary in the expected format
  - max_tokens is 80 (NOT a provider-default)
  - model is sourced from settings.ai_nudge_model
  - timeout propagates through to the client call
  - TimeoutError from the client re-raises (Task 2 catches)
  - empty text content raises RuntimeError("empty composer response")
  - unset ai_nudge_model raises RuntimeError("ai_nudge_model not configured")
  - system prompt contains no em dash
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from app.ai import orchestrator


# ---------------------------------------------------------------------------
# Anthropic client fake
# ---------------------------------------------------------------------------


class FakeAnthropicMessages:
    """Mirror of ``client.messages`` that captures the create() kwargs
    and returns a canned response (or raises)."""

    def __init__(
        self,
        captured: dict,
        return_text: str = "",
        raise_exc: Exception | None = None,
        stop_reason: str = "end_turn",
    ):
        self.captured = captured
        self.return_text = return_text
        self.raise_exc = raise_exc
        self.stop_reason = stop_reason

    def create(self, **kwargs):
        self.captured.update(kwargs)
        if self.raise_exc is not None:
            raise self.raise_exc
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=self.return_text)],
            stop_reason=self.stop_reason,
        )


class FakeAnthropicClient:
    def __init__(self, messages_obj: FakeAnthropicMessages):
        self.messages = messages_obj


def _install_fake_client(
    monkeypatch: pytest.MonkeyPatch,
    *,
    return_text: str = "Reminder: take out the trash, please.",
    raise_exc: Exception | None = None,
    stop_reason: str = "end_turn",
) -> dict:
    """Patch orchestrator._get_anthropic_client to return a fake.

    Returns the ``captured`` dict, which is updated in place with the
    kwargs the fake saw for ``messages.create(...)``.
    """
    captured: dict = {}
    messages_obj = FakeAnthropicMessages(
        captured=captured,
        return_text=return_text,
        raise_exc=raise_exc,
        stop_reason=stop_reason,
    )
    fake_client = FakeAnthropicClient(messages_obj)

    def _fake_get(timeout_seconds: float):
        captured["__timeout_seconds"] = timeout_seconds
        return fake_client

    monkeypatch.setattr(orchestrator, "_get_anthropic_client", _fake_get)
    return captured


# ---------------------------------------------------------------------------
# Common fixtures
# ---------------------------------------------------------------------------


_PREAMBLE = (
    "## Voice profile for this member\n"
    "- Tone: warm\n"
    "- Vocabulary level: standard\n"
    "- Formality: casual\n"
    "- Humor: light\n"
    "- Default verbosity: standard"
)


_PROPOSALS = [
    {
        "trigger_kind": "overdue_task",
        "title": "Take out trash",
        "time_label": "08:00 AM",
    },
    {
        "trigger_kind": "upcoming_event",
        "title": "Soccer practice",
        "time_label": "starts at 04:30 PM",
    },
]


@pytest.fixture(autouse=True)
def _ensure_nudge_model(monkeypatch: pytest.MonkeyPatch):
    """Make sure ai_nudge_model has a value unless the test overrides."""
    monkeypatch.setattr(
        orchestrator.settings, "ai_nudge_model", "claude-haiku-test", raising=False
    )
    # Anthropic client construction reads anthropic_api_key; we never
    # actually construct the real client in tests (we patch
    # _get_anthropic_client), but set it for safety.
    monkeypatch.setattr(
        orchestrator.settings, "anthropic_api_key", "sk-test", raising=False
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestHappyPath:
    def test_returns_stripped_body(self, monkeypatch):
        _install_fake_client(
            monkeypatch,
            return_text="  Reminder: take out the trash, please.  ",
        )
        body = orchestrator.generate_nudge_body(
            family_member_id=uuid.uuid4(),
            proposal_summaries=_PROPOSALS,
            personality_preamble=_PREAMBLE,
        )
        assert body == "Reminder: take out the trash, please."

    def test_returns_exact_text_no_extra_whitespace(self, monkeypatch):
        _install_fake_client(
            monkeypatch, return_text="Reminder: take out the trash, please."
        )
        body = orchestrator.generate_nudge_body(
            family_member_id=uuid.uuid4(),
            proposal_summaries=_PROPOSALS,
            personality_preamble=_PREAMBLE,
        )
        assert body == "Reminder: take out the trash, please."


class TestPromptShape:
    def test_system_prompt_includes_preamble_verbatim(self, monkeypatch):
        captured = _install_fake_client(monkeypatch, return_text="ok")
        orchestrator.generate_nudge_body(
            family_member_id=uuid.uuid4(),
            proposal_summaries=_PROPOSALS,
            personality_preamble=_PREAMBLE,
        )
        system_prompt = captured["system"]
        assert _PREAMBLE in system_prompt
        assert system_prompt.startswith(
            "You are Scout, composing a short proactive nudge"
        )
        assert "No em dashes" in system_prompt
        assert "No greetings" in system_prompt
        assert "No sign-off" in system_prompt

    def test_user_message_lists_each_proposal(self, monkeypatch):
        captured = _install_fake_client(monkeypatch, return_text="ok")
        orchestrator.generate_nudge_body(
            family_member_id=uuid.uuid4(),
            proposal_summaries=_PROPOSALS,
            personality_preamble=_PREAMBLE,
        )
        messages = captured["messages"]
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        content = messages[0]["content"]
        assert 'overdue_task: "Take out trash" (08:00 AM)' in content
        assert (
            'upcoming_event: "Soccer practice" (starts at 04:30 PM)' in content
        )
        assert content.startswith("Triggers:\n")
        assert content.rstrip().endswith("Compose the nudge body now.")

    def test_token_cap_is_80(self, monkeypatch):
        captured = _install_fake_client(monkeypatch, return_text="ok")
        orchestrator.generate_nudge_body(
            family_member_id=uuid.uuid4(),
            proposal_summaries=_PROPOSALS,
            personality_preamble=_PREAMBLE,
        )
        assert captured["max_tokens"] == 80

    def test_model_is_ai_nudge_model(self, monkeypatch):
        monkeypatch.setattr(
            orchestrator.settings,
            "ai_nudge_model",
            "claude-haiku-special",
            raising=False,
        )
        captured = _install_fake_client(monkeypatch, return_text="ok")
        orchestrator.generate_nudge_body(
            family_member_id=uuid.uuid4(),
            proposal_summaries=_PROPOSALS,
            personality_preamble=_PREAMBLE,
        )
        assert captured["model"] == "claude-haiku-special"

    def test_timeout_propagates_to_client_call(self, monkeypatch):
        captured = _install_fake_client(monkeypatch, return_text="ok")
        orchestrator.generate_nudge_body(
            family_member_id=uuid.uuid4(),
            proposal_summaries=_PROPOSALS,
            personality_preamble=_PREAMBLE,
            timeout_seconds=1.25,
        )
        # The client factory saw the per-call timeout.
        assert captured["__timeout_seconds"] == 1.25
        # And so did messages.create().
        assert captured["timeout"] == 1.25

    def test_default_timeout_is_three_seconds(self, monkeypatch):
        captured = _install_fake_client(monkeypatch, return_text="ok")
        orchestrator.generate_nudge_body(
            family_member_id=uuid.uuid4(),
            proposal_summaries=_PROPOSALS,
            personality_preamble=_PREAMBLE,
        )
        assert captured["__timeout_seconds"] == 3.0
        assert captured["timeout"] == 3.0


class TestFailureModes:
    def test_timeout_from_client_reraises(self, monkeypatch):
        _install_fake_client(
            monkeypatch, raise_exc=TimeoutError("upstream timed out")
        )
        with pytest.raises(TimeoutError):
            orchestrator.generate_nudge_body(
                family_member_id=uuid.uuid4(),
                proposal_summaries=_PROPOSALS,
                personality_preamble=_PREAMBLE,
            )

    def test_empty_text_raises(self, monkeypatch):
        _install_fake_client(monkeypatch, return_text="")
        with pytest.raises(RuntimeError, match="empty composer response"):
            orchestrator.generate_nudge_body(
                family_member_id=uuid.uuid4(),
                proposal_summaries=_PROPOSALS,
                personality_preamble=_PREAMBLE,
            )

    def test_whitespace_only_text_raises(self, monkeypatch):
        _install_fake_client(monkeypatch, return_text="   \n\t ")
        with pytest.raises(RuntimeError, match="empty composer response"):
            orchestrator.generate_nudge_body(
                family_member_id=uuid.uuid4(),
                proposal_summaries=_PROPOSALS,
                personality_preamble=_PREAMBLE,
            )

    def test_missing_ai_nudge_model_raises(self, monkeypatch):
        monkeypatch.setattr(
            orchestrator.settings, "ai_nudge_model", "", raising=False
        )
        # Install a fake anyway so a failure to short-circuit would
        # still avoid a network call, but the guard must fire first.
        _install_fake_client(monkeypatch, return_text="never reached")
        with pytest.raises(
            RuntimeError, match="ai_nudge_model not configured"
        ):
            orchestrator.generate_nudge_body(
                family_member_id=uuid.uuid4(),
                proposal_summaries=_PROPOSALS,
                personality_preamble=_PREAMBLE,
            )

    def test_moderation_stop_reason_raises(self, monkeypatch):
        _install_fake_client(
            monkeypatch,
            return_text="flagged content",
            stop_reason="moderation",
        )
        with pytest.raises(RuntimeError, match="composer moderation flagged"):
            orchestrator.generate_nudge_body(
                family_member_id=uuid.uuid4(),
                proposal_summaries=_PROPOSALS,
                personality_preamble=_PREAMBLE,
            )


class TestNoEmDashInPrompt:
    """The voice guidance explicitly forbids em dashes in Scout output;
    the composer instruction itself must stay consistent with that.
    """

    def test_system_prompt_has_no_em_dash(self, monkeypatch):
        captured = _install_fake_client(monkeypatch, return_text="ok")
        orchestrator.generate_nudge_body(
            family_member_id=uuid.uuid4(),
            proposal_summaries=_PROPOSALS,
            personality_preamble=_PREAMBLE,
        )
        assert "—" not in captured["system"]

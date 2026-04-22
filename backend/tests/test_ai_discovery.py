"""Tests for orchestrator.propose_nudges_from_digest (Sprint 05 Phase 5 Task 1)."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import anthropic
import pytest

from app.ai import orchestrator as orch
from app.schemas.nudge_discovery import DiscoveryProposal


# ---------------------------------------------------------------------------
# Anthropic client fake (mirrors test_nudge_composer.py pattern)
# ---------------------------------------------------------------------------


class FakeMessages:
    """Stand-in for ``client.messages`` -- captures kwargs and either
    returns a canned text response or raises the requested exception."""

    def __init__(
        self,
        *,
        return_text: str = "[]",
        raise_exc: Exception | None = None,
        stop_reason: str = "end_turn",
    ):
        self.return_text = return_text
        self.raise_exc = raise_exc
        self.stop_reason = stop_reason
        self.captured: dict = {}

    def create(self, **kwargs):
        self.captured.update(kwargs)
        if self.raise_exc is not None:
            raise self.raise_exc
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=self.return_text)],
            stop_reason=self.stop_reason,
        )


class FakeClient:
    def __init__(self, messages: FakeMessages):
        self.messages = messages


def _install_fake_client(
    monkeypatch: pytest.MonkeyPatch,
    *,
    return_text: str = "[]",
    raise_exc: Exception | None = None,
    stop_reason: str = "end_turn",
) -> FakeMessages:
    messages = FakeMessages(
        return_text=return_text,
        raise_exc=raise_exc,
        stop_reason=stop_reason,
    )
    client = FakeClient(messages)

    def _fake_get(timeout_seconds: float):
        return client

    monkeypatch.setattr(orch, "_get_anthropic_client", _fake_get)
    return messages


@pytest.fixture(autouse=True)
def _ensure_ai_available(monkeypatch: pytest.MonkeyPatch):
    """Every test starts with ai_available True and ai_nudge_model set.
    Tests that want the disabled path override."""
    # settings.ai_available is a property; the cleanest way to force its
    # value in tests is to replace it on the instance. Since it reads
    # enable_ai and anthropic_api_key, set both underlying fields.
    monkeypatch.setattr(orch.settings, "enable_ai", True, raising=False)
    monkeypatch.setattr(orch.settings, "anthropic_api_key", "sk-test", raising=False)
    monkeypatch.setattr(
        orch.settings, "ai_nudge_model", "claude-haiku-test", raising=False
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


FAMILY_ID = uuid.uuid4()
MEMBER_A = uuid.uuid4()
MEMBER_B = uuid.uuid4()
NOW = datetime(2026, 4, 21, 14, 30, 0, tzinfo=timezone.utc)


def _valid_proposal(member_id: uuid.UUID | None = None) -> dict:
    return {
        "member_id": str(member_id or MEMBER_A),
        "trigger_entity_kind": "general",
        "trigger_entity_id": None,
        "scheduled_for": "2026-04-21T15:00:00",
        "severity": "normal",
        "body": "Heads up: trash day is coming.",
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_returns_empty_when_ai_unavailable(monkeypatch):
    # Flipping enable_ai off is sufficient: ai_available is a property
    # that ANDs enable_ai with a non-empty anthropic_api_key.
    monkeypatch.setattr(orch.settings, "enable_ai", False, raising=False)
    out = orch.propose_nudges_from_digest(
        family_id=FAMILY_ID,
        digest={"tasks": []},
        now_utc=NOW,
    )
    assert out == []


def test_parses_valid_proposals(monkeypatch):
    payload = [_valid_proposal(MEMBER_A), _valid_proposal(MEMBER_B)]
    _install_fake_client(monkeypatch, return_text=json.dumps(payload))

    out = orch.propose_nudges_from_digest(
        family_id=FAMILY_ID,
        digest={"tasks": []},
        now_utc=NOW,
    )
    assert len(out) == 2
    assert all(isinstance(p, DiscoveryProposal) for p in out)
    assert out[0].member_id == MEMBER_A
    assert out[1].member_id == MEMBER_B


def test_drops_malformed_proposals_keeps_valid(monkeypatch):
    good = _valid_proposal(MEMBER_A)
    missing_member = {
        "trigger_entity_kind": "general",
        "trigger_entity_id": None,
        "scheduled_for": "2026-04-21T15:00:00",
        "severity": "normal",
        "body": "No member id here.",
    }
    bad_severity = _valid_proposal(MEMBER_B)
    bad_severity["severity"] = "catastrophic"

    payload = [good, missing_member, bad_severity]
    _install_fake_client(monkeypatch, return_text=json.dumps(payload))

    out = orch.propose_nudges_from_digest(
        family_id=FAMILY_ID,
        digest={"tasks": []},
        now_utc=NOW,
    )
    assert len(out) == 1
    assert out[0].member_id == MEMBER_A


def test_caps_at_max_proposals(monkeypatch):
    payload = [_valid_proposal() for _ in range(20)]
    _install_fake_client(monkeypatch, return_text=json.dumps(payload))

    out = orch.propose_nudges_from_digest(
        family_id=FAMILY_ID,
        digest={"tasks": []},
        now_utc=NOW,
        max_proposals=3,
    )
    assert len(out) == 3


def test_empty_ai_output_returns_empty(monkeypatch):
    _install_fake_client(monkeypatch, return_text="[]")
    out = orch.propose_nudges_from_digest(
        family_id=FAMILY_ID,
        digest={"tasks": []},
        now_utc=NOW,
    )
    assert out == []


def test_non_list_output_returns_empty(monkeypatch):
    _install_fake_client(monkeypatch, return_text='{"nope": true}')
    out = orch.propose_nudges_from_digest(
        family_id=FAMILY_ID,
        digest={"tasks": []},
        now_utc=NOW,
    )
    assert out == []


def test_unparseable_json_returns_empty(monkeypatch):
    _install_fake_client(monkeypatch, return_text="this is not json")
    out = orch.propose_nudges_from_digest(
        family_id=FAMILY_ID,
        digest={"tasks": []},
        now_utc=NOW,
    )
    assert out == []


def test_strips_code_fences(monkeypatch):
    payload = [_valid_proposal(MEMBER_A)]
    fenced = "```json\n" + json.dumps(payload) + "\n```"
    _install_fake_client(monkeypatch, return_text=fenced)

    out = orch.propose_nudges_from_digest(
        family_id=FAMILY_ID,
        digest={"tasks": []},
        now_utc=NOW,
    )
    assert len(out) == 1
    assert out[0].member_id == MEMBER_A


def test_timeout_returns_empty(monkeypatch):
    err = anthropic.APITimeoutError(request=MagicMock())
    _install_fake_client(monkeypatch, raise_exc=err)

    out = orch.propose_nudges_from_digest(
        family_id=FAMILY_ID,
        digest={"tasks": []},
        now_utc=NOW,
    )
    assert out == []


def test_api_error_returns_empty(monkeypatch):
    err = anthropic.APIError("boom", request=MagicMock(), body=None)
    _install_fake_client(monkeypatch, raise_exc=err)

    out = orch.propose_nudges_from_digest(
        family_id=FAMILY_ID,
        digest={"tasks": []},
        now_utc=NOW,
    )
    assert out == []

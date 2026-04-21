"""Tests for AnthropicProvider's 5xx + timeout retry logic.

Sprint 2 Backlog #2 — chat() and chat_stream() retry once on
transient upstream failures (5xx, 529, connection error, timeout).
Tests use a mocked Anthropic client so we never burn real tokens.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import anthropic
import pytest

from app.ai.provider import (
    AnthropicProvider,
    _RETRY_BACKOFF_SECONDS,
    _call_with_one_retry,
    _is_retryable,
)


def _fake_status_error(code: int) -> anthropic.APIStatusError:
    """Construct an APIStatusError instance without going through the real
    init path (which wants a real Response object)."""
    err = anthropic.APIStatusError.__new__(anthropic.APIStatusError)
    err.status_code = code
    err.message = f"HTTP {code}"
    return err


def _fake_text_response() -> SimpleNamespace:
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text="ok", id="", name="", input={})],
        stop_reason="end_turn",
        model="claude-haiku-4-5",
        usage=SimpleNamespace(input_tokens=5, output_tokens=2),
    )


class TestIsRetryable:
    def test_5xx_status_error_is_retryable(self):
        assert _is_retryable(_fake_status_error(500))
        assert _is_retryable(_fake_status_error(502))
        assert _is_retryable(_fake_status_error(503))

    def test_529_overloaded_is_retryable(self):
        assert _is_retryable(_fake_status_error(529))

    def test_4xx_is_not_retryable(self):
        assert not _is_retryable(_fake_status_error(400))
        assert not _is_retryable(_fake_status_error(401))
        assert not _is_retryable(_fake_status_error(429))
        assert not _is_retryable(_fake_status_error(404))

    def test_connection_error_is_retryable(self):
        err = anthropic.APIConnectionError(request=MagicMock())
        assert _is_retryable(err)

    def test_timeout_error_is_retryable(self):
        err = anthropic.APITimeoutError(request=MagicMock())
        assert _is_retryable(err)

    def test_value_error_is_not_retryable(self):
        assert not _is_retryable(ValueError("bad arg"))


class TestCallWithOneRetry:
    def test_retries_once_on_5xx(self, monkeypatch):
        monkeypatch.setattr("app.ai.provider.time.sleep", lambda s: None)
        call_count = 0

        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise _fake_status_error(503)
            return "ok"

        assert _call_with_one_retry(flaky) == "ok"
        assert call_count == 2

    def test_reraises_on_second_failure(self, monkeypatch):
        monkeypatch.setattr("app.ai.provider.time.sleep", lambda s: None)

        def always_fails():
            raise _fake_status_error(502)

        with pytest.raises(anthropic.APIStatusError):
            _call_with_one_retry(always_fails)

    def test_non_retryable_error_passes_through_immediately(self):
        call_count = 0

        def one_shot_400():
            nonlocal call_count
            call_count += 1
            raise _fake_status_error(400)

        with pytest.raises(anthropic.APIStatusError):
            _call_with_one_retry(one_shot_400)
        # 400 is not retryable — must not be called twice.
        assert call_count == 1


class TestProviderChatRetry:
    def _provider_with(self, side_effects):
        provider = AnthropicProvider.__new__(AnthropicProvider)  # skip __init__
        provider._client = MagicMock()
        provider._client.messages.create.side_effect = side_effects
        return provider

    def test_chat_retries_on_5xx_then_succeeds(self, monkeypatch):
        monkeypatch.setattr("app.ai.provider.time.sleep", lambda s: None)
        provider = self._provider_with([_fake_status_error(503), _fake_text_response()])
        result = provider.chat(messages=[{"role": "user", "content": "hi"}], system="s")
        assert result.content == "ok"
        assert provider._client.messages.create.call_count == 2

    def test_chat_gives_up_after_two_failures(self, monkeypatch):
        monkeypatch.setattr("app.ai.provider.time.sleep", lambda s: None)
        provider = self._provider_with(
            [_fake_status_error(503), _fake_status_error(503)]
        )
        with pytest.raises(anthropic.APIStatusError):
            provider.chat(messages=[{"role": "user", "content": "hi"}], system="s")
        assert provider._client.messages.create.call_count == 2

    def test_chat_does_not_retry_on_4xx(self, monkeypatch):
        monkeypatch.setattr("app.ai.provider.time.sleep", lambda s: None)
        provider = self._provider_with([_fake_status_error(400)])
        with pytest.raises(anthropic.APIStatusError):
            provider.chat(messages=[{"role": "user", "content": "hi"}], system="s")
        # 400 is a client error — no retry
        assert provider._client.messages.create.call_count == 1


class TestStreamRetry:
    """chat_stream() retries stream *setup* failures once, but only if
    nothing has been yielded — otherwise a retry would double-emit text.
    """

    class _FakeStream:
        def __init__(self, chunks, *, final=None):
            self.text_stream = iter(chunks)
            self._final = final or SimpleNamespace(
                stop_reason="end_turn",
                content=[SimpleNamespace(type="text", text="".join(chunks))],
                model="claude-haiku-4-5",
                usage=SimpleNamespace(input_tokens=5, output_tokens=2),
            )

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get_final_message(self):
            return self._final

    def _provider_with_stream(self, side_effects):
        provider = AnthropicProvider.__new__(AnthropicProvider)
        provider._client = MagicMock()
        provider._client.messages.stream.side_effect = side_effects
        return provider

    def test_stream_retries_setup_error_once(self, monkeypatch):
        monkeypatch.setattr("app.ai.provider.time.sleep", lambda s: None)
        good = self._FakeStream(["hello"])
        provider = self._provider_with_stream([_fake_status_error(502), good])

        events = list(
            provider.chat_stream(messages=[{"role": "user", "content": "hi"}], system="s")
        )
        types = [e.get("type") for e in events]
        assert "error" not in types
        assert "text_delta" in types
        assert provider._client.messages.stream.call_count == 2

    def test_stream_gives_up_after_two_setup_failures(self, monkeypatch):
        monkeypatch.setattr("app.ai.provider.time.sleep", lambda s: None)
        provider = self._provider_with_stream(
            [_fake_status_error(502), _fake_status_error(503)]
        )

        events = list(
            provider.chat_stream(messages=[{"role": "user", "content": "hi"}], system="s")
        )
        assert events[-1]["type"] == "error"
        assert provider._client.messages.stream.call_count == 2

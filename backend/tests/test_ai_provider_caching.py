"""Tests for AnthropicProvider's prompt-cache wiring.

We can't exercise Anthropic's actual cache here without burning real
tokens, so these tests verify the two things that are under our
control:

  1. the system kwarg passed to ``client.messages.create`` has the
     correct ``cache_control: {type: "ephemeral"}`` shape when the
     caller passes a string and ``cache_system=True`` (the default);
  2. ``cache_creation_input_tokens`` / ``cache_read_input_tokens``
     from ``response.usage`` are surfaced on ``AIResponse``.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.ai.provider import AnthropicProvider, _build_system_param


class _FakeBlock:
    def __init__(self, *, type: str, text: str = "", id: str = "", name: str = "", input: dict | None = None):
        self.type = type
        self.text = text
        self.id = id
        self.name = name
        self.input = input or {}


def _fake_response(
    *,
    text: str = "hello",
    input_tokens: int = 10,
    output_tokens: int = 5,
    cache_creation: int | None = None,
    cache_read: int | None = None,
) -> SimpleNamespace:
    usage_kwargs = {"input_tokens": input_tokens, "output_tokens": output_tokens}
    if cache_creation is not None:
        usage_kwargs["cache_creation_input_tokens"] = cache_creation
    if cache_read is not None:
        usage_kwargs["cache_read_input_tokens"] = cache_read

    return SimpleNamespace(
        content=[_FakeBlock(type="text", text=text)],
        stop_reason="end_turn",
        model="claude-haiku-4-5",
        usage=SimpleNamespace(**usage_kwargs),
    )


class TestBuildSystemParam:
    def test_string_with_caching_on_wraps_in_cached_block(self):
        result = _build_system_param("you are scout", cache_system=True)
        assert result == [
            {
                "type": "text",
                "text": "you are scout",
                "cache_control": {"type": "ephemeral"},
            }
        ]

    def test_string_with_caching_off_passes_through(self):
        result = _build_system_param("you are scout", cache_system=False)
        assert result == "you are scout"

    def test_list_is_returned_as_is(self):
        explicit = [
            {"type": "text", "text": "static", "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": "dynamic"},
        ]
        result = _build_system_param(explicit, cache_system=True)
        assert result is explicit

    def test_empty_string_returns_none(self):
        assert _build_system_param("", cache_system=True) is None
        assert _build_system_param("", cache_system=False) is None


class TestProviderChat:
    def _provider_with_fake_client(self, response):
        provider = AnthropicProvider.__new__(AnthropicProvider)  # skip __init__
        provider._client = MagicMock()
        provider._client.messages.create.return_value = response
        return provider

    def test_system_string_is_wrapped_with_cache_control(self):
        provider = self._provider_with_fake_client(_fake_response())
        provider.chat(messages=[{"role": "user", "content": "hi"}], system="scout prompt")

        sent = provider._client.messages.create.call_args.kwargs
        assert sent["system"] == [
            {
                "type": "text",
                "text": "scout prompt",
                "cache_control": {"type": "ephemeral"},
            }
        ]

    def test_cache_system_false_sends_plain_string(self):
        provider = self._provider_with_fake_client(_fake_response())
        provider.chat(
            messages=[{"role": "user", "content": "hi"}],
            system="scout prompt",
            cache_system=False,
        )
        sent = provider._client.messages.create.call_args.kwargs
        assert sent["system"] == "scout prompt"

    def test_cache_metrics_surface_on_response(self):
        provider = self._provider_with_fake_client(
            _fake_response(cache_creation=1500, cache_read=200)
        )
        result = provider.chat(messages=[{"role": "user", "content": "hi"}], system="s")
        assert result.cache_creation_input_tokens == 1500
        assert result.cache_read_input_tokens == 200

    def test_missing_cache_metrics_default_to_zero(self):
        """Older SDKs / non-caching models don't emit cache fields."""
        provider = self._provider_with_fake_client(_fake_response())  # no cache fields
        result = provider.chat(messages=[{"role": "user", "content": "hi"}], system="s")
        assert result.cache_creation_input_tokens == 0
        assert result.cache_read_input_tokens == 0

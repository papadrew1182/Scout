"""AI provider abstraction. Anthropic-first with clean interface for swapping."""

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import anthropic

from app.config import settings


@dataclass
class ToolDefinition:
    name: str
    description: str
    input_schema: dict


@dataclass
class ToolCall:
    id: str
    name: str
    input: dict


@dataclass
class AIResponse:
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: str = ""
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0


class AnthropicProvider:
    """Synchronous Anthropic API wrapper for tool-use chat."""

    def __init__(self):
        if not settings.anthropic_api_key:
            raise RuntimeError("SCOUT_ANTHROPIC_API_KEY not set")
        self._client = anthropic.Anthropic(
            api_key=settings.anthropic_api_key,
            timeout=settings.ai_request_timeout,
        )

    def chat(
        self,
        *,
        messages: list[dict],
        system: str = "",
        tools: list[ToolDefinition] | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> AIResponse:
        kwargs: dict[str, Any] = {
            "model": model or settings.ai_chat_model,
            "max_tokens": max_tokens or settings.ai_max_tokens,
            "temperature": temperature if temperature is not None else settings.ai_temperature,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = [
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.input_schema,
                }
                for t in tools
            ]

        response = self._client.messages.create(**kwargs)

        content_text = ""
        tool_calls = []
        for block in response.content:
            if block.type == "text":
                content_text += block.text
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(id=block.id, name=block.name, input=block.input)
                )

        return AIResponse(
            content=content_text,
            tool_calls=tool_calls,
            stop_reason=response.stop_reason,
            model=response.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

    def chat_stream(
        self,
        *,
        messages: list[dict],
        system: str = "",
        tools: list[ToolDefinition] | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> Iterator[dict]:
        """Stream a single chat round from Anthropic.

        Yields structured events. The orchestrator forwards most of
        these as SSE frames to the client, and consumes the final
        ``{"type": "round_end", ...}`` event to decide whether to run
        a tool and start another round.

        Event shapes:
          {"type": "text_delta", "text": "..."}     — partial text chunk
          {"type": "round_end",
           "stop_reason": "end_turn" | "tool_use" | ...,
           "content": "full text so far",
           "tool_calls": [{"id": ..., "name": ..., "input": ...}],
           "model": "...",
           "input_tokens": N, "output_tokens": N}
          {"type": "error", "message": "..."}
        """
        kwargs: dict[str, Any] = {
            "model": model or settings.ai_chat_model,
            "max_tokens": max_tokens or settings.ai_max_tokens,
            "temperature": temperature if temperature is not None else settings.ai_temperature,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = [
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.input_schema,
                }
                for t in tools
            ]

        try:
            with self._client.messages.stream(**kwargs) as stream:
                for event in stream.text_stream:
                    if event:
                        yield {"type": "text_delta", "text": event}

                # After the text stream finishes, the final message is
                # available with the full accumulated content and stop reason.
                final = stream.get_final_message()
        except Exception as e:  # Anthropic API errors, network, etc.
            yield {"type": "error", "message": f"{type(e).__name__}: {e}"}
            return

        content_text = ""
        tool_calls: list[dict] = []
        for block in final.content:
            if block.type == "text":
                content_text += block.text
            elif block.type == "tool_use":
                tool_calls.append(
                    {"id": block.id, "name": block.name, "input": block.input}
                )

        yield {
            "type": "round_end",
            "stop_reason": final.stop_reason or "",
            "content": content_text,
            "tool_calls": tool_calls,
            "model": final.model or "",
            "input_tokens": getattr(final.usage, "input_tokens", 0),
            "output_tokens": getattr(final.usage, "output_tokens", 0),
        }


def get_provider() -> AnthropicProvider:
    return AnthropicProvider()

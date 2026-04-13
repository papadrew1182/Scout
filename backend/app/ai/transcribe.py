"""Audio transcription provider abstraction for the voice-input path.

Providers share a uniform interface:
    transcribe(audio_bytes: bytes, content_type: str) -> str

Default is Groq (free-tier Whisper, fastest turnaround). OpenAI is
supported as an alternate backend. Both use the OpenAI-compatible
audio/transcriptions REST contract.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from app.config import settings

logger = logging.getLogger("scout.ai.transcribe")


@dataclass
class TranscriptionResult:
    text: str
    provider: str
    model: str
    duration_ms: int


class _GroqWhisperProvider:
    base_url = "https://api.groq.com/openai/v1/audio/transcriptions"
    name = "groq"

    def transcribe(self, audio: bytes, content_type: str) -> str:
        r = httpx.post(
            self.base_url,
            headers={"Authorization": f"Bearer {settings.transcribe_api_key}"},
            files={
                "file": ("audio.webm", audio, content_type or "audio/webm"),
            },
            data={
                "model": settings.transcribe_model,
                "response_format": "json",
                "language": "en",
            },
            timeout=60.0,
        )
        r.raise_for_status()
        return (r.json().get("text") or "").strip()


class _OpenAIWhisperProvider:
    base_url = "https://api.openai.com/v1/audio/transcriptions"
    name = "openai"

    def transcribe(self, audio: bytes, content_type: str) -> str:
        r = httpx.post(
            self.base_url,
            headers={"Authorization": f"Bearer {settings.transcribe_api_key}"},
            files={
                "file": ("audio.webm", audio, content_type or "audio/webm"),
            },
            data={
                # OpenAI uses the string "whisper-1"; allow override.
                "model": settings.transcribe_model or "whisper-1",
                "response_format": "json",
            },
            timeout=60.0,
        )
        r.raise_for_status()
        return (r.json().get("text") or "").strip()


def get_transcribe_provider():
    choice = (settings.transcribe_provider or "").lower()
    if choice == "openai":
        return _OpenAIWhisperProvider()
    return _GroqWhisperProvider()


def transcribe_audio(audio: bytes, content_type: str) -> TranscriptionResult:
    """Run the current provider and return a uniform result.

    Raises ``RuntimeError`` if no API key is configured so the route
    layer can return 501. Raises the underlying ``httpx.HTTPError`` on
    upstream failures so the route returns 502/504.
    """
    import time

    if not settings.transcribe_api_key:
        raise RuntimeError("transcribe_api_key_not_set")

    provider = get_transcribe_provider()
    start = time.monotonic()
    text = provider.transcribe(audio, content_type)
    duration_ms = int((time.monotonic() - start) * 1000)
    logger.info(
        "transcribe_ok provider=%s bytes=%d chars=%d dur_ms=%d",
        provider.name, len(audio), len(text), duration_ms,
    )
    return TranscriptionResult(
        text=text,
        provider=provider.name,
        model=settings.transcribe_model,
        duration_ms=duration_ms,
    )

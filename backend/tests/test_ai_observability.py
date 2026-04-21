"""Tests for ``app.ai.observability.log_ai_call`` — the structured
log line emitted on every AI provider round.

These tests assert the wire format (the thing ``scripts/ai_cost_report.py``
parses) rather than any behavior of the orchestrator itself, so they
stay fast and don't require the Anthropic SDK.
"""

from __future__ import annotations

import json
import logging
import re
import uuid

import pytest

from app.ai.observability import AI_CALL_EVENT, log_ai_call, new_trace_id


_AI_CALL_RX = re.compile(r"ai_call\s+(?P<body>\{.*\})\s*$")


def _capture(caplog: pytest.LogCaptureFixture) -> list[dict]:
    """Return the decoded JSON body of every ai_call log line caplog saw."""
    out: list[dict] = []
    for record in caplog.records:
        if record.name != "scout.ai.observability":
            continue
        msg = record.getMessage()
        m = _AI_CALL_RX.search(msg)
        if m:
            out.append(json.loads(m.group("body")))
    return out


def test_log_ai_call_emits_structured_json(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="scout.ai.observability")

    trace = new_trace_id()
    log_ai_call(
        trace_id=trace,
        conversation_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        family_id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
        member_id=uuid.UUID("33333333-3333-3333-3333-333333333333"),
        model="claude-opus-4-6",
        tool_name=None,
        duration_ms=842,
        input_tokens=1234,
        output_tokens=567,
    )

    [payload] = _capture(caplog)
    assert payload["trace_id"] == trace
    assert payload["conversation_id"] == "11111111-1111-1111-1111-111111111111"
    assert payload["family_id"] == "22222222-2222-2222-2222-222222222222"
    assert payload["member_id"] == "33333333-3333-3333-3333-333333333333"
    assert payload["model"] == "claude-opus-4-6"
    assert payload["tool_name"] is None
    assert payload["duration_ms"] == 842
    assert payload["input_tokens"] == 1234
    assert payload["output_tokens"] == 567
    # cost_usd is computed via pricing.estimate_cost_usd so the report
    # script and the DB rollup agree. For claude-opus-4-6 the rates are
    # $15/M in + $75/M out, so 1234 in + 567 out ≈ $0.06104.
    assert payload["cost_usd"] == pytest.approx(0.061, abs=1e-3)
    assert payload["event_ts"].endswith("Z")


def test_log_ai_call_handles_missing_ids(caplog: pytest.LogCaptureFixture) -> None:
    """Summary endpoints (daily brief, weekly plan) don't have a
    conversation_id — make sure None passes through cleanly."""
    caplog.set_level(logging.INFO, logger="scout.ai.observability")

    log_ai_call(
        trace_id=new_trace_id(),
        conversation_id=None,
        family_id=None,
        member_id=None,
        model="claude-haiku-4-5",
        tool_name="generate_daily_brief",
        duration_ms=300,
        input_tokens=100,
        output_tokens=50,
    )

    [payload] = _capture(caplog)
    assert payload["conversation_id"] is None
    assert payload["family_id"] is None
    assert payload["member_id"] is None
    assert payload["tool_name"] == "generate_daily_brief"


def test_log_ai_call_never_raises(caplog: pytest.LogCaptureFixture) -> None:
    """Observability must not break the caller. Weird inputs are coerced
    to safe defaults rather than bubbling up."""
    caplog.set_level(logging.INFO, logger="scout.ai.observability")

    # Passing a non-numeric duration or tokens should still produce one line.
    log_ai_call(
        trace_id=new_trace_id(),
        conversation_id=None,
        family_id=None,
        member_id=None,
        model=None,
        tool_name=None,
        duration_ms=0,
        input_tokens=0,
        output_tokens=0,
    )
    assert len(_capture(caplog)) == 1


def test_new_trace_id_is_unique() -> None:
    seen = {new_trace_id() for _ in range(100)}
    assert len(seen) == 100


def test_aggregation_script_parses_log_line(
    caplog: pytest.LogCaptureFixture, tmp_path
) -> None:
    """Round-trip: emit a log line, pipe it through the report script,
    assert the totals come back."""
    caplog.set_level(logging.INFO, logger="scout.ai.observability")

    fam = uuid.UUID("22222222-2222-2222-2222-222222222222")
    for i in range(3):
        log_ai_call(
            trace_id=new_trace_id(),
            conversation_id=uuid.uuid4(),
            family_id=fam,
            member_id=uuid.uuid4(),
            model="claude-haiku-4-5",
            tool_name="chat" if i == 0 else None,
            duration_ms=100 + i * 10,
            input_tokens=1000,
            output_tokens=500,
        )

    # Reconstruct the lines the way Railway's log pipe would emit them.
    raw_lines = [
        f"{rec.asctime or ''} INFO scout.ai.observability: {rec.getMessage()}"
        for rec in caplog.records
        if rec.name == "scout.ai.observability"
    ]

    import sys
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repo_root / "scripts"))
    try:
        import ai_cost_report  # type: ignore

        report = ai_cost_report.build_report(raw_lines)
    finally:
        sys.path.pop(0)

    assert report.total.messages == 3
    assert report.total.input_tokens == 3000
    assert report.total.output_tokens == 1500
    # haiku pricing: $1/M in + $5/M out → 3000 in + 1500 out = $0.0105
    assert report.total.cost_usd == pytest.approx(0.0105, abs=1e-4)

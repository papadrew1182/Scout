"""Tests for the client-side error intake endpoint.

Sprint 2 Backlog #3 — the frontend ErrorBoundary POSTs crash payloads
to /api/client-errors. We assert:

  - the endpoint accepts well-formed payloads and returns 204
  - the log line format matches what scripts can grep for
  - Pydantic validates message length + `source` enum
  - unauthenticated requests still land (the whole point is to accept
    reports even when auth is broken)
"""

from __future__ import annotations

import logging
import re

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _client_error_lines(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [
        record.getMessage()
        for record in caplog.records
        if record.name == "scout.client_errors"
        and record.getMessage().startswith("client_error ")
    ]


class TestClientErrorReport:
    def test_accepts_minimal_payload(self, client, caplog):
        caplog.set_level(logging.ERROR, logger="scout.client_errors")
        resp = client.post(
            "/api/client-errors",
            json={"message": "boom"},
        )
        assert resp.status_code == 204
        lines = _client_error_lines(caplog)
        assert len(lines) == 1
        assert '"message":"boom"' in lines[0]
        # default source = error_boundary
        assert '"source":"error_boundary"' in lines[0]

    def test_accepts_full_payload(self, client, caplog):
        caplog.set_level(logging.ERROR, logger="scout.client_errors")
        resp = client.post(
            "/api/client-errors",
            json={
                "message": "TypeError: x is undefined",
                "stack": "at foo\nat bar",
                "url": "https://scout-ui-gamma.vercel.app/today",
                "user_agent": "Mozilla/5.0",
                "source": "unhandled_rejection",
                "release": "a1b2c3d4",
            },
        )
        assert resp.status_code == 204
        line = _client_error_lines(caplog)[0]
        assert '"source":"unhandled_rejection"' in line
        assert '"release":"a1b2c3d4"' in line
        assert "/today" in line

    def test_rejects_bad_source_enum(self, client):
        resp = client.post(
            "/api/client-errors",
            json={"message": "x", "source": "bogus_source"},
        )
        assert resp.status_code == 422

    def test_rejects_empty_message(self, client):
        resp = client.post(
            "/api/client-errors",
            json={"message": ""},
        )
        assert resp.status_code == 422

    def test_stack_is_capped_in_log_line(self, client, caplog):
        caplog.set_level(logging.ERROR, logger="scout.client_errors")
        # Pydantic accepts up to 8KB, but the log cap is 2KB so one line
        # doesn't blow Railway's buffer.
        long_stack = "x" * 5000
        resp = client.post(
            "/api/client-errors",
            json={"message": "ok", "stack": long_stack},
        )
        assert resp.status_code == 204
        line = _client_error_lines(caplog)[0]
        # Extract the JSON body and count 'x' chars in the stack field.
        m = re.search(r'"stack":"(x*)"', line)
        assert m is not None
        assert len(m.group(1)) == 2000

    def test_anonymous_request_still_lands(self, client, caplog):
        """No Authorization header — report still accepted, family_id
        and member_id are null in the log."""
        caplog.set_level(logging.ERROR, logger="scout.client_errors")
        resp = client.post("/api/client-errors", json={"message": "anon crash"})
        assert resp.status_code == 204
        line = _client_error_lines(caplog)[0]
        assert '"family_id":null' in line
        assert '"member_id":null' in line

    def test_log_line_has_event_ts(self, client, caplog):
        caplog.set_level(logging.ERROR, logger="scout.client_errors")
        client.post("/api/client-errors", json={"message": "ts test"})
        line = _client_error_lines(caplog)[0]
        # ISO 8601 UTC with trailing Z
        assert re.search(
            r'"event_ts":"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}',
            line,
        )

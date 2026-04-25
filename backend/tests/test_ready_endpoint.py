"""Unit tests for the /ready endpoint's maintenance-mode semantic patch.

Manifest v1.1.2 §6 PR 2.1 gate criterion 9: while
``SCOUT_CANONICAL_MAINTENANCE`` is truthy, ``/ready`` must not report
``"status": "ready"`` regardless of DB probe outcome. Required body
shape when maintenance is on:
``{"status": "not_ready", "reason": "canonical_maintenance",
"database_reachable": <bool>}``. Extra diagnostic fields are allowed.

When maintenance is off, ``/ready`` retains its pre-PR-2.1 behavior:
``"ready"`` if the DB probe succeeded, ``"not_ready"`` with the
``database: <error>`` ``reason`` if it failed.

Covers four cases (per the PR 2.1 brief):
1. maintenance on  + DB reachable   -> not_ready / canonical_maintenance / reachable=True
2. maintenance on  + DB unreachable -> not_ready / canonical_maintenance / reachable=False
3. maintenance off + DB reachable   -> ready (existing behavior preserved)
4. maintenance off + DB unreachable -> not_ready / "database: ..." (existing behavior)

DB isolation is achieved via the local ``setup_database`` fixture below,
which shadows the conftest's session-scoped autouse ``setup_database``
fixture (caught by PR 1.5 tertiary review — pytest's collection model
inherits autouse fixtures from parent conftests regardless of test-module
docstrings; the only way to actually opt out is to define a same-name
fixture inside this module that yields without doing any DB work).

The DB probe is exercised via monkeypatching ``app.database.SessionLocal``
to either return a mock session whose ``execute``/``scalar`` calls
succeed, or raise the same exception class real psycopg2/SQLAlchemy
would raise on a connect failure. This keeps the test runnable on a
workstation that has the backend Python deps but no provisioned
``scout_test`` database.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.middleware.canonical_maintenance import MAINTENANCE_ENV_VAR


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Override the conftest autouse `setup_database` fixture for this
    module only. The /ready handler tests monkeypatch SessionLocal
    directly; they do not need a real scout_test DB."""
    yield


@pytest.fixture
def client():
    """Real app TestClient. Lifespan is not entered; we only need the
    /ready route handler to dispatch."""
    from app.main import app
    return TestClient(app)


def _install_session_mock(monkeypatch, *, db_reachable: bool, probe_error: str = "connection refused"):
    """Swap ``app.database.SessionLocal`` for a callable that returns
    either a mock session (db_reachable=True) or a callable that raises
    on construction (db_reachable=False).

    The /ready handler does ``from app.database import SessionLocal``
    inside the function body, so we must patch the module attribute,
    not a local reference.
    """
    if db_reachable:
        # Mock session: execute() returns truthy, scalar() returns 0
        # (account count). The /ready handler treats account_count > 0
        # as the "accounts_exist" boolean; either value is fine for
        # these tests since we assert on status/reason/reachable, not
        # accounts_exist.
        mock_db = MagicMock()
        mock_db.execute.return_value = MagicMock()
        mock_db.scalar.return_value = 0
        mock_db.close = MagicMock()
        monkeypatch.setattr("app.database.SessionLocal", lambda: mock_db)
    else:
        def fail():
            raise RuntimeError(probe_error)
        monkeypatch.setattr("app.database.SessionLocal", fail)


# --- Case 1: maintenance ON + DB reachable ---------------------------------


def test_maintenance_on_db_reachable_returns_not_ready_canonical(monkeypatch, client):
    monkeypatch.setenv(MAINTENANCE_ENV_VAR, "true")
    _install_session_mock(monkeypatch, db_reachable=True)

    response = client.get("/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["reason"] == "canonical_maintenance"
    assert body["database_reachable"] is True


# --- Case 2: maintenance ON + DB unreachable -------------------------------


def test_maintenance_on_db_unreachable_returns_not_ready_canonical(monkeypatch, client):
    monkeypatch.setenv(MAINTENANCE_ENV_VAR, "true")
    _install_session_mock(monkeypatch, db_reachable=False)

    response = client.get("/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["reason"] == "canonical_maintenance"
    assert body["database_reachable"] is False


# --- Case 3: maintenance OFF + DB reachable --------------------------------


def test_maintenance_off_db_reachable_returns_ready(monkeypatch, client):
    monkeypatch.delenv(MAINTENANCE_ENV_VAR, raising=False)
    _install_session_mock(monkeypatch, db_reachable=True)

    response = client.get("/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    # Pre-PR-2.1 body shape preserved: no `reason`, no
    # `database_reachable` field — the env-config fields plus
    # accounts_exist remain.
    assert "reason" not in body
    assert "database_reachable" not in body


# --- Case 4: maintenance OFF + DB unreachable ------------------------------


def test_maintenance_off_db_unreachable_returns_not_ready_database(monkeypatch, client):
    monkeypatch.delenv(MAINTENANCE_ENV_VAR, raising=False)
    _install_session_mock(monkeypatch, db_reachable=False, probe_error="boom")

    response = client.get("/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "not_ready"
    # Pre-PR-2.1 body shape: reason starts with "database: " and
    # contains the probe error message verbatim. No
    # canonical_maintenance reason here.
    assert body["reason"].startswith("database: ")
    assert "boom" in body["reason"]
    assert body["reason"] != "canonical_maintenance"


# --- Cross-case invariants -------------------------------------------------


def test_maintenance_truthy_alternatives_pin_status(monkeypatch, client):
    """The /ready patch must use the same truthy parser as the
    middleware. Verify '1', 'yes', 'on', 'TRUE' all activate the
    maintenance semantic."""
    _install_session_mock(monkeypatch, db_reachable=True)
    for truthy in ("1", "yes", "on", "TRUE", "  true  "):
        monkeypatch.setenv(MAINTENANCE_ENV_VAR, truthy)
        body = client.get("/ready").json()
        assert body["status"] == "not_ready", f"value {truthy!r} did not pin status"
        assert body["reason"] == "canonical_maintenance"


def test_maintenance_garbage_does_not_pin_status(monkeypatch, client):
    """Conservative for non-truthy values: 'maybe', '42', '' must NOT
    flip /ready into maintenance mode. Existing behavior applies."""
    _install_session_mock(monkeypatch, db_reachable=True)
    for non_truthy in ("maybe", "42", "false", "no", ""):
        monkeypatch.setenv(MAINTENANCE_ENV_VAR, non_truthy)
        body = client.get("/ready").json()
        assert body["status"] == "ready", f"value {non_truthy!r} unexpectedly pinned status"

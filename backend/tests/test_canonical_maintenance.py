"""Unit tests for the canonical-rewrite maintenance middleware.

Manifest v1.1.1 §6 PR 1.5 gate: 'every non-health/non-ready endpoint
that can reach legacy DB code must return controlled HTTP 503 before
route/service logic executes.' These tests build a minimal FastAPI
app with only the maintenance middleware and a handful of routes
(allowlisted + non-allowlisted), then exercise both maintenance-on
and maintenance-off paths.

DB isolation is achieved via the local `setup_database` fixture
below, which shadows the conftest's session-scoped autouse
`setup_database` fixture. Pytest's collection model inherits autouse
fixtures from parent conftests regardless of test-module
docstrings; the only way to actually opt out is to define a
same-name fixture inside this module that yields without doing any
DB work.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.canonical_maintenance import (
    MAINTENANCE_ALLOWLIST,
    MAINTENANCE_ENV_VAR,
    RETRY_AFTER_SECONDS,
    canonical_maintenance_middleware,
)


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Override the conftest autouse `setup_database` fixture for this
    module only.

    The maintenance middleware tests are deliberately DB-free — the
    middleware operates on env vars and request paths, not on database
    state. Without this shadow, pytest's autouse-fixture inheritance
    rules would still trigger the project conftest's session-scoped
    real-DB fixture (drop schemas, run migrations against scout_test)
    before this module runs, even though the tests don't use any of
    its returns. Shadowing here keeps the tests genuinely DB-free and
    runnable on any workstation that has the backend Python deps but
    not a provisioned scout_test database.

    Caught by tertiary review of PR 1.5: pytest collection ignores
    docstring claims about test isolation; only fixture-name shadowing
    actually opts out of an autouse fixture."""
    yield


@pytest.fixture
def maintenance_app() -> FastAPI:
    """Minimal app exercising the middleware against four route shapes:
    the two allowlisted endpoints, the explicitly-not-allowlisted
    /api/auth/bootstrap, and a generic non-allowlisted DB-touching
    endpoint."""
    app = FastAPI()
    app.middleware("http")(canonical_maintenance_middleware)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/ready")
    def ready():
        return {"status": "ready"}

    @app.get("/api/auth/bootstrap")
    def bootstrap():
        return {"bootstrap": "ok"}

    @app.get("/api/families")
    def families():
        return {"families": []}

    return app


@pytest.fixture
def client(maintenance_app: FastAPI) -> TestClient:
    return TestClient(maintenance_app)


# --- Maintenance OFF: pure pass-through ------------------------------------


def test_maintenance_off_passes_health(monkeypatch, client):
    monkeypatch.delenv(MAINTENANCE_ENV_VAR, raising=False)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_maintenance_off_passes_non_allowlisted_endpoint(monkeypatch, client):
    monkeypatch.delenv(MAINTENANCE_ENV_VAR, raising=False)
    response = client.get("/api/families")
    assert response.status_code == 200
    assert response.json() == {"families": []}


def test_maintenance_off_via_explicit_false(monkeypatch, client):
    monkeypatch.setenv(MAINTENANCE_ENV_VAR, "false")
    response = client.get("/api/families")
    assert response.status_code == 200


# --- Maintenance ON: allowlist passes, everything else 503 ------------------


def test_maintenance_on_allows_health(monkeypatch, client):
    monkeypatch.setenv(MAINTENANCE_ENV_VAR, "true")
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_maintenance_on_allows_ready(monkeypatch, client):
    monkeypatch.setenv(MAINTENANCE_ENV_VAR, "true")
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_maintenance_on_blocks_auth_bootstrap(monkeypatch, client):
    """/api/auth/bootstrap is explicitly NOT allowlisted per manifest
    v1.1.1 §6 PR 1.5 gate. It becomes eligible only after the
    Phase 3/Phase 5 bootstrap gate clears."""
    monkeypatch.setenv(MAINTENANCE_ENV_VAR, "true")
    response = client.get("/api/auth/bootstrap")
    assert response.status_code == 503
    body = response.json()
    assert body["error"] == "service_in_canonical_maintenance"
    assert "/health" in body["allowlisted_endpoints"]
    assert "/ready" in body["allowlisted_endpoints"]
    assert response.headers["retry-after"] == RETRY_AFTER_SECONDS


def test_maintenance_on_blocks_generic_endpoint(monkeypatch, client):
    monkeypatch.setenv(MAINTENANCE_ENV_VAR, "true")
    response = client.get("/api/families")
    assert response.status_code == 503
    assert response.json()["error"] == "service_in_canonical_maintenance"


# --- Env-var parsing edge cases ---------------------------------------------


def test_env_var_value_uppercase_true_enables_gate(monkeypatch, client):
    monkeypatch.setenv(MAINTENANCE_ENV_VAR, "TRUE")
    response = client.get("/api/families")
    assert response.status_code == 503


def test_env_var_value_with_whitespace_enables_gate(monkeypatch, client):
    monkeypatch.setenv(MAINTENANCE_ENV_VAR, "  true  ")
    response = client.get("/api/families")
    assert response.status_code == 503


def test_env_var_truthy_alternatives_enable_gate(monkeypatch, client):
    """Common truthy values must enable maintenance. Manifest §6
    PR 1.5 gate handoff: a required-for-boot flag must be biased
    toward correctly detecting "on." A false-negative (env says on,
    parser reads off) crashes seed.py at boot with no auto-recovery;
    a false-positive (env says off, parser reads on) produces 503s
    that an operator clears with one env-var flip. The asymmetry
    favors liberal detection of on."""
    for truthy_alt in ("1", "yes", "on", "TRUE", "Yes", "ON", "  true  ", "TrUe"):
        monkeypatch.setenv(MAINTENANCE_ENV_VAR, truthy_alt)
        response = client.get("/api/families")
        assert response.status_code == 503, (
            f"expected 503 for truthy value {truthy_alt!r}, got {response.status_code}"
        )


def test_env_var_garbage_treated_as_false(monkeypatch, client):
    """Random non-truthy strings must NOT enable maintenance.
    Conservative for non-truthy values so operator typos do not put
    the service into maintenance unintentionally. The truthy set is
    explicit; everything else is off."""
    for garbage in (
        "maybe",
        "sometimes",
        "42",
        "false",
        "no",
        "off",
        "",
        "yes please",
        "trueish",
        "0",
    ):
        monkeypatch.setenv(MAINTENANCE_ENV_VAR, garbage)
        response = client.get("/api/families")
        assert response.status_code == 200, (
            f"unexpected 503 for non-truthy value {garbage!r}, got {response.status_code}"
        )


# --- Allowlist invariant ----------------------------------------------------


def test_allowlist_constant_is_minimal():
    """Manifest §6 PR 1.5 gate: allowlist limited to /health and
    /ready. A change to this set requires code review."""
    assert MAINTENANCE_ALLOWLIST == frozenset({"/health", "/ready"})

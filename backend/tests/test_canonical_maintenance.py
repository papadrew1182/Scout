"""Unit tests for the canonical-rewrite maintenance middleware.

Manifest v1.1.1 §6 PR 1.5 gate: 'every non-health/non-ready endpoint
that can reach legacy DB code must return controlled HTTP 503 before
route/service logic executes.' These tests build a minimal FastAPI
app with only the maintenance middleware and a handful of routes
(allowlisted + non-allowlisted), then exercise both maintenance-on
and maintenance-off paths.

The tests deliberately avoid the project conftest's real-DB
fixtures: the middleware's behavior is not DB-dependent, and
isolating it from the test DB infrastructure keeps these tests
runnable on a workstation that doesn't have the scout_test database
provisioned.
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


def test_env_var_truthy_alternatives_treated_as_false(monkeypatch, client):
    """Only canonical 'true' enables maintenance. Values like '1',
    'yes', 'on' are treated as off so an operator who intended off
    but wrote a truthy-ish value gets the safer pass-through default
    rather than an unintended outage."""
    for truthy_alt in ("1", "yes", "on", "True!"):
        monkeypatch.setenv(MAINTENANCE_ENV_VAR, truthy_alt)
        response = client.get("/api/families")
        assert response.status_code == 200, f"unexpected 503 for value {truthy_alt!r}"


# --- Allowlist invariant ----------------------------------------------------


def test_allowlist_constant_is_minimal():
    """Manifest §6 PR 1.5 gate: allowlist limited to /health and
    /ready. A change to this set requires code review."""
    assert MAINTENANCE_ALLOWLIST == frozenset({"/health", "/ready"})

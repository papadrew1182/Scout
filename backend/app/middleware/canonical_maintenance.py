"""Canonical-rewrite maintenance middleware.

While ``SCOUT_CANONICAL_MAINTENANCE=true`` is set, every request whose
path is not in :data:`MAINTENANCE_ALLOWLIST` is short-circuited with a
503 response carrying a structured JSON body and a ``Retry-After``
header. The check happens before any handler logic executes, so
request-time DB queries cannot reach the legacy ``public.*`` shape
that Phase 1 dropped or the canonical ``scout.*`` shape that Phase 2
hasn't yet built.

When the env var is unset or any value other than ``true`` (case- and
whitespace-insensitive), the middleware is a pure pass-through —
non-rewrite environments (local dev, CI, the post-Phase-5 future)
behave exactly as they did before this module existed.

Allowlist policy
----------------
Manifest v1.1.1 §6 PR 1.5 gate is explicit: the allowlist is limited
to ``/health`` and ``/ready`` unless the PR handoff names an
additional endpoint and proves it does not touch dropped or
recreated DB contracts. ``/api/auth/bootstrap`` is **not**
automatically allowlisted in PR 1.5; it becomes eligible only after
the Phase 3/Phase 5 bootstrap gate clears.

The allowlist is a module-level ``frozenset`` constant on purpose:
adding an endpoint requires a code review, not an env-var flip. That
preserves the manifest's gate intent in code rather than in
operational configuration.

Wiring
------
This middleware must be the *outermost* middleware so it short-circuits
before CORS, auth, logging, or any code that could touch the database.
In Starlette/FastAPI, "outermost" means "added last" — so
``backend/app/main.py`` registers this middleware AFTER any other
``add_middleware`` calls.
"""

from __future__ import annotations

import os

from fastapi import Request
from fastapi.responses import JSONResponse


MAINTENANCE_ENV_VAR = "SCOUT_CANONICAL_MAINTENANCE"
MAINTENANCE_ALLOWLIST: frozenset[str] = frozenset({"/health", "/ready"})

# Conservative one-hour Retry-After. The rewrite sprint is measured in
# days, but a tight value keeps clients polling rather than backing off
# indefinitely while we ship the canonical schema.
RETRY_AFTER_SECONDS = "3600"


def _maintenance_enabled() -> bool:
    """True if the env var resolves to canonical 'true'.

    Read fresh on every request so an operator flipping the Railway
    env var takes effect after the next pod restart picks up the new
    value (env vars are read at process start by Railway, not at
    request time, so this is effectively per-process state — but
    reading on each call costs ~one os.environ lookup and keeps the
    helper testable without monkeypatching module state)."""
    return os.getenv(MAINTENANCE_ENV_VAR, "false").strip().lower() == "true"


async def canonical_maintenance_middleware(request: Request, call_next):
    if _maintenance_enabled() and request.url.path not in MAINTENANCE_ALLOWLIST:
        return JSONResponse(
            status_code=503,
            content={
                "error": "service_in_canonical_maintenance",
                "message": (
                    "Scout is undergoing a canonical schema rewrite. "
                    "Most endpoints are temporarily unavailable."
                ),
                "allowlisted_endpoints": sorted(MAINTENANCE_ALLOWLIST),
            },
            headers={"Retry-After": RETRY_AFTER_SECONDS},
        )
    return await call_next(request)

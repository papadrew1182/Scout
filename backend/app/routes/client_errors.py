"""Client-side error intake.

Sprint 2 Backlog #3 — the frontend ErrorBoundary (plus a global
unhandled-rejection / window.onerror handler) POSTs crash payloads
here. We emit one structured ``client_error`` log line per report so
`railway logs --deployment | grep client_error` gives operators a
live view of production frontend crashes without needing an external
provider.

Shape of the log line mirrors `ai_call` from observability.py so the
same aggregation patterns work::

    client_error {"message":"...","stack":"...","url":"...",
                  "user_agent":"...","source":"error_boundary",
                  "release":"...","event_ts":"..."}

Authentication is optional — crash reports should still land even if
the frontend can't resolve the session token. When a token is present
we tag the payload with ``family_id`` and ``member_id`` so we can tell
which account hit a given crash.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import Actor, get_current_actor
from app.database import get_db
from app.services.auth_service import resolve_session

router = APIRouter(prefix="/api/client-errors", tags=["observability"])
logger = logging.getLogger("scout.client_errors")


class ClientErrorReport(BaseModel):
    # Keep the surface small: an operator looking at the log has to be
    # able to read it at a glance. Long narrative belongs in
    # ``stack``.
    message: str = Field(min_length=1, max_length=500)
    stack: str | None = Field(default=None, max_length=8000)
    url: str | None = Field(default=None, max_length=1000)
    user_agent: str | None = Field(default=None, max_length=500)
    source: str = Field(
        default="error_boundary",
        pattern="^(error_boundary|unhandled_rejection|window_error|manual)$",
    )
    release: str | None = Field(default=None, max_length=64)


def _actor_context(request: Request, db: Session) -> dict[str, str | None]:
    """Best-effort attach family/member ids to the log line. Never
    raises: the whole point is that this endpoint accepts reports even
    when auth is broken."""
    try:
        auth = request.headers.get("Authorization")
        if not auth or not auth.startswith("Bearer "):
            return {"family_id": None, "member_id": None}
        account, member, family = resolve_session(db, auth[7:])
        return {"family_id": str(family.id), "member_id": str(member.id)}
    except Exception:  # noqa: BLE001 — crash reports must not crash
        return {"family_id": None, "member_id": None}


@router.post("", status_code=204)
def submit_error(
    payload: ClientErrorReport,
    request: Request,
    db: Session = Depends(get_db),
):
    """Accept a client-side error report and log it structured. No
    persistence — the log stream is the source of truth for now."""
    ctx = _actor_context(request, db)
    event = {
        "message": payload.message,
        "stack": (payload.stack or "")[:2000],  # cap at 2KB so one log line fits
        "url": payload.url,
        "user_agent": payload.user_agent,
        "source": payload.source,
        "release": payload.release,
        "family_id": ctx["family_id"],
        "member_id": ctx["member_id"],
        "event_ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    try:
        logger.error("client_error %s", json.dumps(event, separators=(",", ":")))
    except Exception as exc:  # pragma: no cover — logging must never raise
        logger.warning("client_error_log_failed: %s", str(exc)[:200])
    return None

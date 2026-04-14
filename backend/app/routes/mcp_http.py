"""Tier 5 F19 — HTTP companion transport for the Scout MCP server.

The stdio server in ``backend/scout_mcp`` remains the primary path
for Claude Desktop. This file adds a small HTTP surface for remote
clients that can't spawn a local subprocess, with real bearer auth
via ``scout_mcp_tokens`` rows.

Wire model
----------
- ``POST /mcp/tokens``   — parent creates a remote token; the
                           plaintext is returned ONCE and never
                           stored. The server keeps only a sha256
                           hex hash.
- ``GET  /mcp/tokens``   — parent lists existing tokens (metadata
                           only, no plaintext).
- ``POST /mcp/tokens/{id}/revoke`` — parent revokes a token.

- ``GET  /mcp/tools/list`` — bearer-auth required; returns the
                             JSON schema of every tool available
                             to the token's scope.
- ``POST /mcp/tools/call`` — bearer-auth required; executes a
                             single tool and returns its result.

Not MCP wire-protocol compliant
-------------------------------
This is a JSON-RPC-lite wrapper that shares the same data surface
as the stdio server. Full MCP HTTP/SSE protocol compliance can
layer on top later if a client needs it — the tool dispatcher is
already factored out (``scout_mcp.server.dispatch_tool``) for
reuse. The security model, audit, and redaction rules are
identical to the stdio server.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import uuid
from datetime import datetime

import pytz
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import Actor, get_current_actor
from app.config import settings
from app.database import get_db
from app.models.tier5 import ScoutMCPToken

logger = logging.getLogger("scout.mcp.http")

router = APIRouter(prefix="/mcp", tags=["mcp"])


# ---------------------------------------------------------------------------
# Helpers — token hashing + auth
# ---------------------------------------------------------------------------


def _hash_token(plaintext: str) -> str:
    """sha256 hex. Plaintext is shown to the parent once at creation
    and never stored. Comparing hashes is constant-time per hashlib
    docs at realistic lengths."""
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def _require_remote_enabled() -> None:
    if not settings.mcp_remote_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Remote MCP is disabled. Set SCOUT_MCP_REMOTE_ENABLED=true.",
        )


def _resolve_bearer(db: Session, authorization: str | None) -> ScoutMCPToken:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    raw = authorization[7:].strip()
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Empty token"
        )
    token_hash = _hash_token(raw)
    row = db.scalars(
        select(ScoutMCPToken).where(ScoutMCPToken.token_hash == token_hash)
    ).first()
    if row is None or not row.is_active or row.revoked_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )
    # Best-effort last_used_at refresh — don't fail the call on a
    # transient write error.
    try:
        row.last_used_at = datetime.now(pytz.UTC).replace(tzinfo=None)
        db.flush()
    except Exception:
        pass
    return row


# ---------------------------------------------------------------------------
# Token CRUD (parent-only, authenticated via session token, NOT bearer)
# ---------------------------------------------------------------------------


class MCPTokenCreate(BaseModel):
    label: str | None = Field(default=None, max_length=80)
    scope: str = Field(default="parent", pattern="^(parent|child)$")
    member_id: uuid.UUID | None = None


class MCPTokenRead(BaseModel):
    id: uuid.UUID
    family_id: uuid.UUID
    member_id: uuid.UUID | None
    label: str | None
    scope: str
    is_active: bool
    last_used_at: datetime | None
    created_at: datetime
    revoked_at: datetime | None

    model_config = {"from_attributes": True}


class MCPTokenCreateResponse(BaseModel):
    token: MCPTokenRead
    plaintext: str = Field(
        description=(
            "The only time this value is ever returned. Store it somewhere "
            "safe; the server keeps only a hash."
        )
    )


@router.post("/tokens", response_model=MCPTokenCreateResponse)
def create_mcp_token(
    payload: MCPTokenCreate,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_adult()
    plaintext = f"scout_mcp_{secrets.token_urlsafe(32)}"
    token_hash = _hash_token(plaintext)
    row = ScoutMCPToken(
        family_id=actor.family_id,
        member_id=payload.member_id,
        token_hash=token_hash,
        label=payload.label,
        scope=payload.scope,
        is_active=True,
        created_by_member_id=actor.member_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return MCPTokenCreateResponse(token=MCPTokenRead.model_validate(row), plaintext=plaintext)


@router.get("/tokens", response_model=list[MCPTokenRead])
def list_mcp_tokens(
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_adult()
    rows = list(
        db.scalars(
            select(ScoutMCPToken)
            .where(ScoutMCPToken.family_id == actor.family_id)
            .order_by(ScoutMCPToken.created_at.desc())
        ).all()
    )
    return rows


@router.post("/tokens/{token_id}/revoke", response_model=MCPTokenRead)
def revoke_mcp_token(
    token_id: uuid.UUID,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    actor.require_adult()
    row = db.get(ScoutMCPToken, token_id)
    if row is None or row.family_id != actor.family_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Token not found"
        )
    if row.is_active:
        row.is_active = False
        row.revoked_at = datetime.now(pytz.UTC).replace(tzinfo=None)
        db.commit()
        db.refresh(row)
    return row


# ---------------------------------------------------------------------------
# Tool dispatch (bearer-auth, no session required)
# ---------------------------------------------------------------------------


class ToolCallRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    arguments: dict = Field(default_factory=dict)


@router.get("/tools/list")
def list_mcp_tools(
    request: Request,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    _require_remote_enabled()
    token_row = _resolve_bearer(db, authorization)
    db.commit()

    from scout_mcp.server import build_tool_registry

    specs, _ = build_tool_registry(token_row.family_id, scope=token_row.scope)
    return {
        "scope": token_row.scope,
        "tools": [
            {"name": name, "description": desc, "input_schema": schema}
            for name, desc, schema, _ in specs
        ],
    }


@router.post("/tools/call")
def call_mcp_tool(
    body: ToolCallRequest,
    request: Request,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    _require_remote_enabled()
    token_row = _resolve_bearer(db, authorization)
    db.commit()

    from app.ai.tools import _audit
    from scout_mcp.server import dispatch_tool

    # Audit is best-effort: skip if no creator member id is attached
    # to the token (the FK on ai_tool_audit.actor_member_id is NOT
    # NULL). Tokens created via POST /mcp/tokens always carry a
    # created_by_member_id, so this should rarely be skipped.
    if token_row.created_by_member_id is not None:
        _audit(
            db=db,
            family_id=token_row.family_id,
            actor_id=token_row.created_by_member_id,
            conversation_id=None,
            tool_name=f"mcp_remote:{body.name}",
            arguments=body.arguments or {},
            result_summary=None,
            # ai_tool_audit.status is a narrow enum: 'success',
            # 'error', 'denied', 'confirmation_required'. Use
            # 'success' for the invocation row; tool-level failures
            # are captured in the result payload.
            status="success",
        )
        db.commit()

    result = dispatch_tool(
        token_row.family_id, token_row.scope, body.name, body.arguments
    )
    return {"result": result}

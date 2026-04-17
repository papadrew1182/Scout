"""Admin routes for integration / connector account management.

Endpoints (all scoped to actor's family, require admin.manage_config):

  GET   /admin/integrations/connections
        — list all connector_accounts for the family

  PATCH /admin/integrations/connections/{id}
        — update the status of a connector_account
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import Actor, get_current_actor
from app.database import get_db
from app.models.canonical import Connector, ConnectorAccount
from app.services import integrations_canonical

router = APIRouter(prefix="/admin/integrations", tags=["admin-integrations"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ConnectorAccountItem(BaseModel):
    id: str
    connector_id: str
    connector_key: str
    label: str
    family_id: str
    status: str
    last_success_at: str | None
    last_error_at: str | None
    last_error_message: str | None
    account_label: str | None


class ConnectorStatusPatchPayload(BaseModel):
    status: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_item(account: ConnectorAccount, connector: Connector) -> ConnectorAccountItem:
    return ConnectorAccountItem(
        id=str(account.id),
        connector_id=str(account.connector_id),
        connector_key=connector.connector_key,
        label=connector.label,
        family_id=str(account.family_id),
        status=account.status,
        last_success_at=(
            account.last_success_at.isoformat() if account.last_success_at else None
        ),
        last_error_at=(
            account.last_error_at.isoformat() if account.last_error_at else None
        ),
        last_error_message=account.last_error_message,
        account_label=account.account_label,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/connections", response_model=list[ConnectorAccountItem])
def list_connections(
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    """Return all connector_accounts for the actor's family, with connector metadata.

    Requires admin.manage_config.
    """
    actor.require_permission("admin.manage_config")

    accounts = integrations_canonical.get_family_connector_accounts(db, actor.family_id)

    # Bulk-fetch the connector rows so we can enrich the response without N+1.
    connector_ids = {a.connector_id for a in accounts}
    connectors_map: dict[uuid.UUID, Connector] = {}
    if connector_ids:
        rows = db.scalars(
            select(Connector).where(Connector.id.in_(connector_ids))
        ).all()
        connectors_map = {c.id: c for c in rows}

    return [
        _to_item(a, connectors_map[a.connector_id])
        for a in accounts
        if a.connector_id in connectors_map
    ]


@router.patch("/connections/{account_id}", response_model=ConnectorAccountItem)
def patch_connection_status(
    account_id: uuid.UUID,
    payload: ConnectorStatusPatchPayload,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    """Update the status of a connector_account.

    Requires admin.manage_config.
    """
    actor.require_permission("admin.manage_config")

    account = integrations_canonical.update_connector_status(
        db, actor.family_id, account_id, payload.status
    )
    db.commit()

    connector = db.get(Connector, account.connector_id)
    return _to_item(account, connector)

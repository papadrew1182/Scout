"""Integrations service for scout.connector_accounts (canonical 022 tables).

Functions:
  get_family_connector_accounts  — list ConnectorAccount rows for a family
  get_connector_account          — fetch a single ConnectorAccount by id
  update_connector_status        — update the status on a ConnectorAccount
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.canonical import Connector, ConnectorAccount

# Canonical status values allowed by the CHECK constraint in migration 022.
VALID_STATUSES = {
    "disconnected",
    "configured",
    "connected",
    "syncing",
    "stale",
    "error",
    "disabled",
    "decision_gated",
}


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


def get_family_connector_accounts(
    db: Session,
    family_id: uuid.UUID,
) -> list[ConnectorAccount]:
    """Return all ConnectorAccount rows for a family, joined with connector metadata."""
    return list(
        db.scalars(
            select(ConnectorAccount)
            .where(ConnectorAccount.family_id == family_id)
            .order_by(ConnectorAccount.connector_id)
        ).all()
    )


def get_connector_account(
    db: Session,
    family_id: uuid.UUID,
    account_id: uuid.UUID,
) -> ConnectorAccount:
    """Fetch a ConnectorAccount by id, scoped to family_id.

    Raises 404 if not found.
    """
    account = db.scalars(
        select(ConnectorAccount)
        .where(ConnectorAccount.id == account_id)
        .where(ConnectorAccount.family_id == family_id)
    ).first()

    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connector account not found",
        )
    return account


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


def update_connector_status(
    db: Session,
    family_id: uuid.UUID,
    account_id: uuid.UUID,
    new_status: str,
) -> ConnectorAccount:
    """Update the status field of a ConnectorAccount.

    Validates the status string against the canonical vocabulary.
    Returns the updated ConnectorAccount (not yet committed).
    Raises 422 for invalid status values.
    """
    if new_status not in VALID_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Invalid status '{new_status}'. Must be one of: {sorted(VALID_STATUSES)}",
        )

    account = get_connector_account(db, family_id, account_id)
    account.status = new_status
    db.flush()
    return account

"""Shared upsert helper for all integration ingestion flows.

This is the only place external IDs are translated to/from internal IDs.
The connector_mappings table is the sole lookup index.
"""

import uuid
from typing import Any, Callable

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.connectors import ConnectorMapping


class SourceConflictError(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)


def find_mapping(
    db: Session,
    connector_name: str,
    internal_table: str,
    external_id: str,
) -> ConnectorMapping | None:
    """Look up an existing mapping by (connector_name, internal_table, external_id)."""
    stmt = (
        select(ConnectorMapping)
        .where(ConnectorMapping.connector_name == connector_name)
        .where(ConnectorMapping.internal_table == internal_table)
        .where(ConnectorMapping.external_id == external_id)
    )
    return db.scalars(stmt).first()


def create_mapping(
    db: Session,
    connector_name: str,
    internal_table: str,
    internal_id: uuid.UUID,
    external_id: str,
    metadata: dict | None = None,
) -> ConnectorMapping:
    """Create a new connector_mappings row."""
    mapping = ConnectorMapping(
        connector_name=connector_name,
        internal_table=internal_table,
        internal_id=internal_id,
        external_id=external_id,
        metadata_=metadata or {},
    )
    db.add(mapping)
    db.flush()
    return mapping


def upsert_via_mapping(
    db: Session,
    *,
    connector_name: str,
    internal_table: str,
    external_id: str,
    expected_source: str,
    fetch_by_id: Callable[[uuid.UUID], Any | None],
    create_fn: Callable[[], Any],
    update_fn: Callable[[Any], Any],
    metadata: dict | None = None,
) -> tuple[Any, bool]:
    """Generic upsert flow using connector_mappings.

    Args:
        connector_name: e.g. 'google_calendar' (must match connector_mappings CHECK)
        internal_table: e.g. 'events'
        external_id: the external system's id for this record
        expected_source: the value the existing domain row's `source` column must
            match for an update to be allowed (e.g. 'google_cal' for events).
            Enforces the source-of-truth rule.
        fetch_by_id: callable taking internal_id, returning the domain row or None
        create_fn: callable returning a new domain row (already added/flushed)
        update_fn: callable taking the existing row and updating it in-place
        metadata: optional metadata dict for new mapping rows

    Returns:
        Tuple of (domain_row, created) where created is True if a new row was made.
    """
    existing_mapping = find_mapping(db, connector_name, internal_table, external_id)

    if existing_mapping:
        domain_row = fetch_by_id(existing_mapping.internal_id)
        if domain_row is None:
            # Mapping exists but the domain row was deleted out from under us.
            # Treat as a fresh create and refresh the mapping.
            new_row = create_fn()
            existing_mapping.internal_id = new_row.id
            db.flush()
            return new_row, True

        # Source-of-truth check
        actual_source = getattr(domain_row, "source", None)
        if actual_source != expected_source:
            raise SourceConflictError(
                f"Cannot update {internal_table} row {domain_row.id}: "
                f"expected source={expected_source!r} but found {actual_source!r}"
            )

        update_fn(domain_row)
        db.flush()
        return domain_row, False

    # No mapping exists — create both the domain row and the mapping
    new_row = create_fn()
    create_mapping(
        db,
        connector_name=connector_name,
        internal_table=internal_table,
        internal_id=new_row.id,
        external_id=external_id,
        metadata=metadata,
    )
    return new_row, True

"""Sync orchestration service.

Session 2 ships the contract; the real sync loop lands in a
follow-up packet. This service exposes the shape that the
scheduler and control-plane surface call into, so test code and
route stubs can exercise the happy path without each adapter
being wired to its external API yet.

The real implementation will:
  1. load enabled scout.connector_accounts
  2. look up the adapter class via get_adapter()
  3. pull the next cursor from scout.sync_cursors
  4. call adapter.incremental_sync(cursor)
  5. persist the result to scout.sync_runs and update the cursor
  6. on error, write to scout.connector_event_log and flip status
  7. detect freshness drift and raise scout.stale_data_alerts rows
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from services.connectors.base import (
    BaseConnectorAdapter,
    ConnectorHealth,
    FreshnessState,
    SyncResult,
)
from services.connectors.registry import get_adapter
from services.connectors.sync_persistence import (
    DbConnectorHealthRow,
    db_health_for_family,
    finish_sync_run,
    record_event,
    start_sync_run,
)

logger = logging.getLogger("scout.connectors.sync")


@dataclass
class SyncRequest:
    """Input envelope for a sync invocation. The platform chooses
    whether to call ``backfill`` or ``incremental_sync`` based on
    whether a cursor already exists."""

    connector_account_id: uuid.UUID
    connector_key: str
    entity_key: str
    cursor: str | None = None
    force_backfill: bool = False


class SyncService:
    """Thin façade the scheduler + routes call into. Not committed
    to a DB session yet — the full DAL lands with packet E when the
    first real connector (Google Calendar) is wired up."""

    def __init__(self) -> None:
        self._adapter_cache: dict[str, BaseConnectorAdapter] = {}

    def _adapter_for(self, connector_key: str) -> BaseConnectorAdapter:
        if connector_key not in self._adapter_cache:
            adapter_cls = get_adapter(connector_key)
            self._adapter_cache[connector_key] = adapter_cls()
        return self._adapter_cache[connector_key]

    def health_check(self, connector_key: str) -> ConnectorHealth:
        """Dispatch health_check() to the adapter. Wrap exceptions so
        the control plane always gets a ``ConnectorHealth`` object
        even if the adapter itself is broken."""
        try:
            return self._adapter_for(connector_key).health_check()
        except NotImplementedError:
            return ConnectorHealth(
                connector_key=connector_key,
                healthy=False,
                freshness_state=FreshnessState.UNKNOWN,
                last_error_message="adapter not yet implemented",
            )
        except Exception as e:  # pragma: no cover — defensive
            logger.exception("health_check_failed connector=%s", connector_key)
            return ConnectorHealth(
                connector_key=connector_key,
                healthy=False,
                freshness_state=FreshnessState.UNKNOWN,
                last_error_message=str(e)[:500],
            )

    def run_sync(self, request: SyncRequest) -> SyncResult:
        """Dispatch to backfill or incremental_sync based on cursor
        state + force_backfill. Real DAL persistence happens in the
        caller for this first pass."""
        adapter = self._adapter_for(request.connector_key)
        try:
            if request.force_backfill or request.cursor is None:
                return adapter.backfill(scope={}, cursor=request.cursor)
            return adapter.incremental_sync(cursor=request.cursor)
        except NotImplementedError as e:
            return SyncResult(
                status="error",
                error_message=f"adapter not yet implemented: {e}",
            )
        except Exception as e:  # pragma: no cover — defensive
            logger.exception("run_sync_failed connector=%s", request.connector_key)
            return SyncResult(status="error", error_message=str(e)[:500])

    # ---- Block 3: DB-backed orchestration ----------------------------

    def health_check_db(
        self,
        db: Session,
        *,
        family_id: uuid.UUID,
    ) -> list[DbConnectorHealthRow]:
        """DB-backed health snapshot for one family. Reads from
        scout.connectors + scout.connector_accounts and reports
        the locked-vocabulary status + derived freshness for every
        registered connector. Connectors with no account row for
        the family fall back to 'disconnected' (or 'decision_gated'
        when the registry marks them as such).

        Routes use this instead of iterating CONNECTOR_REGISTRY +
        calling adapter.health_check(): the route should reflect
        what's actually persisted, not what an in-memory adapter
        stub claims.
        """
        return db_health_for_family(db, family_id=family_id)

    def run_and_persist(
        self,
        db: Session,
        *,
        sync_job_id: uuid.UUID,
        request: SyncRequest,
    ) -> SyncResult:
        """Execute one sync request end to end with persistence.

        Pipeline:
            1. start_sync_run -> writes sync_runs row, flips
               connector_account.status to 'syncing'.
            2. run_sync -> dispatches to adapter (handles
               NotImplementedError gracefully).
            3. finish_sync_run -> writes the result, updates
               connector_account.last_success_at /
               last_error_at / status / last_error_message.
            4. On error, also writes a connector_event_log row
               with severity='error' so the operator surface can
               surface a human-readable timeline.

        Returns the SyncResult so callers can act on it. Callers
        are responsible for committing the transaction; this
        method only flushes.
        """
        run_id = start_sync_run(db, sync_job_id=sync_job_id)
        result = self.run_sync(request)
        finish_sync_run(db, run_id=run_id, result=result)

        if result.status == "error":
            account_row = db.execute(
                text(
                    """
                    SELECT connector_account_id
                    FROM scout.sync_jobs WHERE id = :job
                    """
                ),
                {"job": sync_job_id},
            ).first()
            if account_row:
                record_event(
                    db,
                    connector_account_id=account_row.connector_account_id,
                    event_type="sync.error",
                    severity="error",
                    payload={
                        "connector_key": request.connector_key,
                        "entity_key": request.entity_key,
                        "error_message": result.error_message,
                    },
                )
        return result

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

from services.connectors.base import (
    BaseConnectorAdapter,
    ConnectorHealth,
    FreshnessState,
    SyncResult,
)
from services.connectors.registry import get_adapter

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

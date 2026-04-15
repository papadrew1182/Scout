"""Base adapter contract for Scout connectors.

Every connector adapter registered with the platform implements this
nine-method contract:

    health_check()
    get_account_summary()
    backfill(scope, cursor=None)
    incremental_sync(cursor=None)
    map_to_internal_objects(records)
    list_supported_entities()
    get_freshness_state()
    disable()
    reconnect()

The base implementation raises NotImplementedError where the real
per-connector logic hasn't landed yet. That lets the registry boot,
the routes return stable contract shapes, and the Session 3 lane
build against mock-compatible responses without waiting for each
external API to be wired up.

Status and freshness vocabulary is locked server-side per the
charter. See ``ConnectorHealth.status`` and ``FreshnessState``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Iterable


# ---------------------------------------------------------------------------
# Status + freshness vocabulary (locked by charter §Connector status vocabulary)
# ---------------------------------------------------------------------------


class ConnectorStatus(str, Enum):
    DISCONNECTED = "disconnected"
    CONFIGURED = "configured"
    CONNECTED = "connected"
    SYNCING = "syncing"
    STALE = "stale"
    ERROR = "error"
    DISABLED = "disabled"
    DECISION_GATED = "decision_gated"


class FreshnessState(str, Enum):
    LIVE = "live"
    LAGGING = "lagging"
    STALE = "stale"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Lightweight dataclasses for adapter returns
# ---------------------------------------------------------------------------


@dataclass
class ConnectorHealth:
    """Returned by ``health_check()``. Mirrors the JSON shape used by
    GET /api/connectors/health so route stubs can serialize it
    without a transformation layer."""

    connector_key: str
    healthy: bool
    freshness_state: FreshnessState = FreshnessState.UNKNOWN
    last_success_at: datetime | None = None
    last_error_at: datetime | None = None
    last_error_message: str | None = None


@dataclass
class ConnectorAccountSummary:
    """Returned by ``get_account_summary()``. Describes the external
    account a Scout connector is attached to (e.g. which Google
    Calendar, which Greenlight household). Intentionally minimal —
    connectors with richer account metadata can extend per-connector."""

    connector_key: str
    account_label: str | None
    account_external_id: str | None
    scopes: list[str] = field(default_factory=list)


@dataclass
class SyncResult:
    """Returned by ``backfill()`` and ``incremental_sync()``. The
    platform writes one row to ``scout.sync_runs`` per call based on
    this result."""

    status: str  # 'success' | 'partial' | 'error'
    records_processed: int = 0
    next_cursor: str | None = None
    error_message: str | None = None


# ---------------------------------------------------------------------------
# Base adapter
# ---------------------------------------------------------------------------


class BaseConnectorAdapter:
    """Concrete adapters subclass this and override the nine contract
    methods. Subclasses **must** set ``connector_key`` as a class
    attribute so the registry can bind them."""

    connector_key: str = ""

    # ---- Contract -----------------------------------------------------

    def health_check(self) -> ConnectorHealth:
        """Cheap liveness + freshness probe. Must not raise — wrap
        transport errors and return ``healthy=False`` with a reason."""
        raise NotImplementedError(
            f"{self.connector_key}: health_check() not implemented"
        )

    def get_account_summary(self) -> ConnectorAccountSummary:
        """Describe the external account this adapter is bound to.
        Used by the connector-settings surface to show the parent
        which calendar / household / budget / HealthKit store they
        connected."""
        raise NotImplementedError(
            f"{self.connector_key}: get_account_summary() not implemented"
        )

    def backfill(self, scope: dict | None = None, cursor: str | None = None) -> SyncResult:
        """Initial bulk sync. The platform passes a ``scope`` dict
        that a per-connector implementation can use to narrow the
        historical window (e.g. last 60 days of calendar events).
        Must be chunkable so repeated calls with the returned
        ``next_cursor`` eventually drain the backlog."""
        raise NotImplementedError(
            f"{self.connector_key}: backfill() not implemented"
        )

    def incremental_sync(self, cursor: str | None = None) -> SyncResult:
        """Delta sync from the stored ``scout.sync_cursors`` position.
        Returns ``next_cursor`` which the platform persists on
        success."""
        raise NotImplementedError(
            f"{self.connector_key}: incremental_sync() not implemented"
        )

    def map_to_internal_objects(self, records: Iterable[Any]) -> list[dict]:
        """Transform source-native records into the Scout normalized
        object shape documented in the charter (person, household
        event, time block, task occurrence, budget snapshot, etc.).
        Must not commit to the DB — the platform handles persistence
        so a failing map doesn't leave half-written state."""
        raise NotImplementedError(
            f"{self.connector_key}: map_to_internal_objects() not implemented"
        )

    def list_supported_entities(self) -> list[str]:
        """Return the entity keys this adapter can sync (e.g.
        ``['calendar_event']`` or ``['budget_snapshot', 'bill_snapshot']``).
        Used by the control plane and by per-entity sync_job rows."""
        return []

    def get_freshness_state(self) -> FreshnessState:
        """Classify the adapter's recent sync history into one of
        the four freshness buckets. Defaults to UNKNOWN — real
        adapters compute this from sync_runs + sync_cursors state."""
        return FreshnessState.UNKNOWN

    def disable(self) -> None:
        """Mark the adapter disabled. Releases any held resources
        (OAuth tokens, HTTP sessions) and flips its connector_account
        status to 'disabled'. Idempotent."""
        raise NotImplementedError(
            f"{self.connector_key}: disable() not implemented"
        )

    def reconnect(self) -> None:
        """Refresh credentials / re-establish session. Idempotent.
        Should leave the adapter in a state where the next
        ``incremental_sync()`` call works."""
        raise NotImplementedError(
            f"{self.connector_key}: reconnect() not implemented"
        )

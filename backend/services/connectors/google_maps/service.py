"""Google Maps service (stub, work packet H).

Subclasses BaseConnectorAdapter so the registry lookup works even
though Google Maps is more like a request/response enrichment
service than a persistent staging connector. It never calls
backfill/incremental_sync in the normal sense — it resolves travel
estimates on demand and caches results in scout.travel_estimates."""

from __future__ import annotations

from services.connectors.base import (
    BaseConnectorAdapter,
    ConnectorAccountSummary,
    ConnectorHealth,
    FreshnessState,
    SyncResult,
)


class GoogleMapsService(BaseConnectorAdapter):
    connector_key = "google_maps"

    def list_supported_entities(self) -> list[str]:
        return ["travel_estimate"]

    def health_check(self) -> ConnectorHealth:
        return ConnectorHealth(
            connector_key=self.connector_key,
            healthy=False,
            freshness_state=FreshnessState.UNKNOWN,
            last_error_message="google_maps service not yet implemented (work packet H)",
        )

    def get_account_summary(self) -> ConnectorAccountSummary:
        return ConnectorAccountSummary(
            connector_key=self.connector_key,
            account_label="Google Maps API (request/response)",
            account_external_id=None,
        )

    def backfill(self, scope=None, cursor=None) -> SyncResult:
        return SyncResult(
            status="success",
            records_processed=0,
            error_message="google_maps is a request/response service; backfill is a no-op",
        )

    def incremental_sync(self, cursor=None) -> SyncResult:
        return SyncResult(
            status="success",
            records_processed=0,
            error_message="google_maps is a request/response service; incremental_sync is a no-op",
        )

    def map_to_internal_objects(self, records):
        raise NotImplementedError("google_maps mapper deferred to work packet H")

    def get_freshness_state(self) -> FreshnessState:
        return FreshnessState.UNKNOWN

    def disable(self) -> None:
        pass

    def reconnect(self) -> None:
        pass

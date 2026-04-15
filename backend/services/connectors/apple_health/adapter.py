"""Apple Health adapter (stub, work packet H). Read-only."""

from __future__ import annotations

from services.connectors.base import (
    BaseConnectorAdapter,
    ConnectorAccountSummary,
    ConnectorHealth,
    FreshnessState,
    SyncResult,
)


class AppleHealthAdapter(BaseConnectorAdapter):
    connector_key = "apple_health"

    def list_supported_entities(self) -> list[str]:
        return ["activity_event"]

    def health_check(self) -> ConnectorHealth:
        return ConnectorHealth(
            connector_key=self.connector_key,
            healthy=False,
            freshness_state=FreshnessState.UNKNOWN,
            last_error_message="apple_health adapter not yet implemented (work packet H)",
        )

    def get_account_summary(self) -> ConnectorAccountSummary:
        return ConnectorAccountSummary(
            connector_key=self.connector_key,
            account_label=None,
            account_external_id=None,
        )

    def backfill(self, scope=None, cursor=None) -> SyncResult:
        raise NotImplementedError("apple_health backfill deferred to work packet H")

    def incremental_sync(self, cursor=None) -> SyncResult:
        raise NotImplementedError("apple_health incremental_sync deferred to work packet H")

    def map_to_internal_objects(self, records):
        raise NotImplementedError("apple_health mapper deferred to work packet H")

    def get_freshness_state(self) -> FreshnessState:
        return FreshnessState.UNKNOWN

    def disable(self) -> None:
        pass

    def reconnect(self) -> None:
        pass

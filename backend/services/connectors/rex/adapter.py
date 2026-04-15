"""Rex adapter (stub, work packet G). Read-only."""

from __future__ import annotations

from services.connectors.base import (
    BaseConnectorAdapter,
    ConnectorAccountSummary,
    ConnectorHealth,
    FreshnessState,
    SyncResult,
)


class RexAdapter(BaseConnectorAdapter):
    connector_key = "rex"

    def list_supported_entities(self) -> list[str]:
        return ["work_context_event"]

    def health_check(self) -> ConnectorHealth:
        return ConnectorHealth(
            connector_key=self.connector_key,
            healthy=False,
            freshness_state=FreshnessState.UNKNOWN,
            last_error_message="rex adapter not yet implemented (work packet G)",
        )

    def get_account_summary(self) -> ConnectorAccountSummary:
        return ConnectorAccountSummary(
            connector_key=self.connector_key,
            account_label=None,
            account_external_id=None,
        )

    def backfill(self, scope=None, cursor=None) -> SyncResult:
        raise NotImplementedError("rex backfill deferred to work packet G")

    def incremental_sync(self, cursor=None) -> SyncResult:
        raise NotImplementedError("rex incremental_sync deferred to work packet G")

    def map_to_internal_objects(self, records):
        raise NotImplementedError("rex mapper deferred to work packet G")

    def get_freshness_state(self) -> FreshnessState:
        return FreshnessState.UNKNOWN

    def disable(self) -> None:
        pass

    def reconnect(self) -> None:
        pass

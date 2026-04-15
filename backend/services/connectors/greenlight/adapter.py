"""Greenlight adapter (stub, work packet F).

Role: payout rail only. Scout computes allowance results; this
adapter pushes approved settlement batches into Greenlight and
optionally reads balance visibility. No reward rules live here."""

from __future__ import annotations

from services.connectors.base import (
    BaseConnectorAdapter,
    ConnectorAccountSummary,
    ConnectorHealth,
    FreshnessState,
    SyncResult,
)


class GreenlightAdapter(BaseConnectorAdapter):
    connector_key = "greenlight"

    def list_supported_entities(self) -> list[str]:
        return ["settlement_batch", "balance_snapshot"]

    def health_check(self) -> ConnectorHealth:
        return ConnectorHealth(
            connector_key=self.connector_key,
            healthy=False,
            freshness_state=FreshnessState.UNKNOWN,
            last_error_message="greenlight adapter not yet implemented (work packet F)",
        )

    def get_account_summary(self) -> ConnectorAccountSummary:
        return ConnectorAccountSummary(
            connector_key=self.connector_key,
            account_label=None,
            account_external_id=None,
        )

    def backfill(self, scope=None, cursor=None) -> SyncResult:
        raise NotImplementedError("greenlight backfill deferred to work packet F")

    def incremental_sync(self, cursor=None) -> SyncResult:
        raise NotImplementedError("greenlight incremental_sync deferred to work packet F")

    def map_to_internal_objects(self, records):
        raise NotImplementedError("greenlight mapper deferred to work packet F")

    def get_freshness_state(self) -> FreshnessState:
        return FreshnessState.UNKNOWN

    def disable(self) -> None:
        pass

    def reconnect(self) -> None:
        pass

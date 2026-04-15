"""Exxir adapter (stub, decision-gated).

Always reports DECISION_GATED status until a product decision
clears the gate per charter §Exxir."""

from __future__ import annotations

from services.connectors.base import (
    BaseConnectorAdapter,
    ConnectorAccountSummary,
    ConnectorHealth,
    FreshnessState,
    SyncResult,
)


class ExxirAdapter(BaseConnectorAdapter):
    connector_key = "exxir"

    def list_supported_entities(self) -> list[str]:
        return []

    def health_check(self) -> ConnectorHealth:
        return ConnectorHealth(
            connector_key=self.connector_key,
            healthy=False,
            freshness_state=FreshnessState.UNKNOWN,
            last_error_message="exxir is decision-gated (charter §Exxir)",
        )

    def get_account_summary(self) -> ConnectorAccountSummary:
        return ConnectorAccountSummary(
            connector_key=self.connector_key,
            account_label="Exxir (decision-gated)",
            account_external_id=None,
        )

    def backfill(self, scope=None, cursor=None) -> SyncResult:
        return SyncResult(
            status="error",
            error_message="exxir is decision-gated; cannot run backfill",
        )

    def incremental_sync(self, cursor=None) -> SyncResult:
        return SyncResult(
            status="error",
            error_message="exxir is decision-gated; cannot run incremental_sync",
        )

    def map_to_internal_objects(self, records):
        return []

    def get_freshness_state(self) -> FreshnessState:
        return FreshnessState.UNKNOWN

    def disable(self) -> None:
        pass

    def reconnect(self) -> None:
        pass

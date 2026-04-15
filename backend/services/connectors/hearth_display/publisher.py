"""Hearth display publisher (stub, work packet E).

Hearth does not have its own source-data schema. This publisher
flips ``scout.calendar_exports.hearth_visible`` on the appropriate
rows and delegates actual propagation to the Google Calendar
adapter. Treating it as a BaseConnectorAdapter keeps the control
plane uniform even though the underlying transport is not an API
call — Hearth is a display-only endpoint downstream of the
calendar lane."""

from __future__ import annotations

from services.connectors.base import (
    BaseConnectorAdapter,
    ConnectorAccountSummary,
    ConnectorHealth,
    FreshnessState,
    SyncResult,
)


class HearthDisplayPublisher(BaseConnectorAdapter):
    connector_key = "hearth_display"

    def list_supported_entities(self) -> list[str]:
        return ["calendar_export"]

    def health_check(self) -> ConnectorHealth:
        return ConnectorHealth(
            connector_key=self.connector_key,
            healthy=True,
            freshness_state=FreshnessState.UNKNOWN,
            last_error_message="hearth is display-only — health is derived from calendar lane freshness",
        )

    def get_account_summary(self) -> ConnectorAccountSummary:
        return ConnectorAccountSummary(
            connector_key=self.connector_key,
            account_label="Hearth display (calendar-fed)",
            account_external_id=None,
        )

    def backfill(self, scope=None, cursor=None) -> SyncResult:
        return SyncResult(
            status="success",
            records_processed=0,
            error_message="hearth has no source data to backfill",
        )

    def incremental_sync(self, cursor=None) -> SyncResult:
        return SyncResult(
            status="success",
            records_processed=0,
            error_message="hearth syncs via google_calendar publication; no direct sync",
        )

    def map_to_internal_objects(self, records):
        return []

    def get_freshness_state(self) -> FreshnessState:
        return FreshnessState.UNKNOWN

    def disable(self) -> None:
        pass

    def reconnect(self) -> None:
        pass

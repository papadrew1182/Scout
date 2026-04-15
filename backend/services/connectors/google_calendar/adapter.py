"""Google Calendar adapter (stub, work packet E).

Role: scheduling spine. Bidirectional — reads imported events,
writes Scout-managed household blocks back into the family's
calendar so Hearth can display them. Charter §Google Calendar."""

from __future__ import annotations

from services.connectors.base import (
    BaseConnectorAdapter,
    ConnectorAccountSummary,
    ConnectorHealth,
    FreshnessState,
    SyncResult,
)


class GoogleCalendarAdapter(BaseConnectorAdapter):
    connector_key = "google_calendar"

    def list_supported_entities(self) -> list[str]:
        return ["calendar_event", "calendar_export"]

    def health_check(self) -> ConnectorHealth:
        return ConnectorHealth(
            connector_key=self.connector_key,
            healthy=False,
            freshness_state=FreshnessState.UNKNOWN,
            last_error_message="google_calendar adapter not yet implemented (work packet E)",
        )

    def get_account_summary(self) -> ConnectorAccountSummary:
        return ConnectorAccountSummary(
            connector_key=self.connector_key,
            account_label=None,
            account_external_id=None,
            scopes=["calendar.readonly", "calendar.events"],
        )

    def backfill(self, scope: dict | None = None, cursor: str | None = None) -> SyncResult:
        raise NotImplementedError(
            "google_calendar backfill deferred to work packet E"
        )

    def incremental_sync(self, cursor: str | None = None) -> SyncResult:
        raise NotImplementedError(
            "google_calendar incremental_sync deferred to work packet E"
        )

    def map_to_internal_objects(self, records):
        raise NotImplementedError(
            "google_calendar mapper deferred to work packet E"
        )

    def get_freshness_state(self) -> FreshnessState:
        return FreshnessState.UNKNOWN

    def disable(self) -> None:
        pass

    def reconnect(self) -> None:
        pass

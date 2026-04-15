"""Google Calendar adapter — first real pass (Session 2 block 3).

Role per charter §Google Calendar: scheduling spine. The adapter
ships in three escalating tiers:

  1. Block 2 — registry stub. Every method raised
     NotImplementedError so the registry could boot but no real
     work happened.

  2. **Block 3 (this file) — quiet operational baseline.**
     ``health_check()``, ``get_account_summary()``,
     ``incremental_sync()``, and ``map_to_internal_objects()`` all
     return well-formed responses without an OAuth client wired
     in. The platform can drive end-to-end persistence (sync_runs,
     connector_accounts.last_success_at, control-plane summary)
     against an in-process no-op adapter, so the entire DB-backed
     control plane is exercisable in tests today.

  3. Future packet — wire ``client.py`` to the real Google
     Calendar v3 API and turn ``map_to_internal_objects`` into a
     real normalizer. Bidirectional writeback is gated on the
     calendar publication packet.

Imported events are intentionally kept separate from
Scout-generated exports: ``map_to_internal_objects`` produces
``scout.external_calendar_events`` rows. Scout-generated
household blocks live in ``scout.calendar_exports`` and are
pushed by the publisher service, not by this adapter.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

from services.connectors.base import (
    BaseConnectorAdapter,
    ConnectorAccountSummary,
    ConnectorHealth,
    FreshnessState,
    SyncResult,
)


# Default scopes the adapter will request once OAuth is wired. Stored
# here so the account-summary surface can show what we'd ask for even
# while no client is bound.
_DEFAULT_SCOPES = ["calendar.readonly", "calendar.events"]


class GoogleCalendarAdapter(BaseConnectorAdapter):
    """First-real-pass Google Calendar adapter.

    The adapter is intentionally clientless in Block 3 — it does
    NOT make any HTTP calls. Instead it reports a 'configured but
    not yet connected' health state and returns no-op sync results
    so the full sync_runs persistence loop can be exercised.

    Once a real OAuth client is wired into ``client.py``, the
    only methods that change are ``incremental_sync()`` /
    ``backfill()`` / ``map_to_internal_objects()`` — the contract
    surface stays identical.
    """

    connector_key = "google_calendar"

    def __init__(self, *, client: Any | None = None) -> None:
        self._client = client
        self._last_success_at: datetime | None = None
        self._last_error_at: datetime | None = None
        self._last_error_message: str | None = None

    # ---- Discovery ---------------------------------------------------

    def list_supported_entities(self) -> list[str]:
        # 'calendar_event' = imported events from the family's GCal.
        # 'calendar_export' = Scout-managed household blocks pushed
        # back to GCal. Both entities use this adapter, but the
        # actual write path lives in the publisher service so
        # imported state and exported state stay decoupled.
        return ["calendar_event", "calendar_export"]

    # ---- Health + account summary ------------------------------------

    def health_check(self) -> ConnectorHealth:
        """Block 3: quiet operational baseline.

        With no client wired, the adapter is *configured* but not
        actively talking to Google. We report ``healthy=True``
        only after a successful sync has been recorded; otherwise
        ``healthy=False`` with a friendly message and freshness
        UNKNOWN. The control-plane DB-backed read is the source
        of truth — this exists so the in-process façade behaves
        consistently with the persisted state.
        """
        if self._client is None and self._last_success_at is None:
            return ConnectorHealth(
                connector_key=self.connector_key,
                healthy=False,
                freshness_state=FreshnessState.UNKNOWN,
                last_error_message=None,
            )
        return ConnectorHealth(
            connector_key=self.connector_key,
            healthy=self._last_error_at is None,
            freshness_state=self.get_freshness_state(),
            last_success_at=self._last_success_at,
            last_error_at=self._last_error_at,
            last_error_message=self._last_error_message,
        )

    def get_account_summary(self) -> ConnectorAccountSummary:
        """Always returns a well-formed summary. When no client is
        bound, ``account_label`` and ``account_external_id`` are
        None so the operator surface can render 'no account
        connected' deterministically without crashing on a missing
        attribute lookup."""
        if self._client is None:
            return ConnectorAccountSummary(
                connector_key=self.connector_key,
                account_label=None,
                account_external_id=None,
                scopes=list(_DEFAULT_SCOPES),
            )
        return ConnectorAccountSummary(
            connector_key=self.connector_key,
            account_label=getattr(self._client, "account_label", None),
            account_external_id=getattr(self._client, "primary_calendar_id", None),
            scopes=list(_DEFAULT_SCOPES),
        )

    # ---- Sync paths --------------------------------------------------

    def backfill(
        self,
        scope: dict | None = None,
        cursor: str | None = None,
    ) -> SyncResult:
        """No client → return a zero-record success so the
        scheduler can persist a sync_runs row. Once the client is
        wired this becomes a paged historical fetch."""
        if self._client is None:
            self._last_success_at = datetime.now(timezone.utc)
            self._last_error_at = None
            self._last_error_message = None
            return SyncResult(
                status="success",
                records_processed=0,
                next_cursor=cursor,
            )
        # Real path lands when client.py is implemented.
        raise NotImplementedError(
            "google_calendar.backfill: client wiring deferred"
        )

    def incremental_sync(self, cursor: str | None = None) -> SyncResult:
        """No client → success with zero records and cursor
        unchanged. The platform persists this through
        sync_persistence.finish_sync_run, which advances
        connector_accounts.last_success_at and lets v_control_plane
        derive freshness=LIVE for this account."""
        if self._client is None:
            self._last_success_at = datetime.now(timezone.utc)
            self._last_error_at = None
            self._last_error_message = None
            return SyncResult(
                status="success",
                records_processed=0,
                next_cursor=cursor,
            )
        raise NotImplementedError(
            "google_calendar.incremental_sync: client wiring deferred"
        )

    # ---- Normalization -----------------------------------------------

    def map_to_internal_objects(
        self,
        records: Iterable[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Transform Google Calendar event payloads into rows
        insertable into ``scout.external_calendar_events``.

        Block 3 implements this against the documented
        Google Calendar v3 ``Event`` shape so tests can pass real
        payloads without an HTTP client. The function is pure —
        it does not touch the database. The caller decides whether
        to bulk-insert the returned rows.

        Records with neither ``start.dateTime`` nor ``start.date``
        are skipped silently rather than failing the whole batch.
        """
        out: list[dict[str, Any]] = []
        for r in records or []:
            start = r.get("start") or {}
            end = r.get("end") or {}
            starts_at = _parse_event_time(start)
            ends_at = _parse_event_time(end) or starts_at
            if starts_at is None:
                continue
            all_day = bool(start.get("date") and not start.get("dateTime"))
            out.append(
                {
                    "source": "google_calendar",
                    "title": r.get("summary") or "(no title)",
                    "starts_at": starts_at,
                    "ends_at": ends_at,
                    "location": r.get("location"),
                    "all_day": all_day,
                }
            )
        return out

    # ---- Lifecycle ---------------------------------------------------

    def get_freshness_state(self) -> FreshnessState:
        """Adapter-local freshness. The DB-backed read in
        sync_persistence.derive_freshness is authoritative for the
        control plane; this method just mirrors the in-process
        state so unit tests can assert the adapter's own view."""
        from services.connectors.sync_persistence import derive_freshness

        return derive_freshness(self._last_success_at)

    def disable(self) -> None:
        """Drop the in-memory client. The platform is responsible
        for flipping the connector_account row to status='disabled'
        — adapters do not write to the DB."""
        self._client = None

    def reconnect(self) -> None:
        """No-op without a real client. Kept idempotent so the
        platform can call it freely during recovery flows."""
        return None


def _parse_event_time(t: dict[str, Any] | None) -> datetime | None:
    """Parse a Google Calendar v3 event start/end object.

    Two shapes are valid:
        {"dateTime": "2026-04-14T07:30:00-05:00"}  (timed)
        {"date": "2026-04-14"}                      (all-day)
    Anything else returns None so the caller can skip the row.
    """
    if not t:
        return None
    raw = t.get("dateTime") or t.get("date")
    if not raw:
        return None
    try:
        if "T" in raw:
            # RFC 3339 with offset; Python 3.11+ handles this.
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        # All-day events: midnight UTC for the local date.
        return datetime.fromisoformat(raw).replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None

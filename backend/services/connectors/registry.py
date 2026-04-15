"""Connector adapter registry.

Maps ``connector_key`` strings (the same keys stored in
``scout.connectors.connector_key``) to their adapter class. Import
this module anywhere you need to resolve an adapter by key —
the registry is populated at import time.
"""

from __future__ import annotations

from services.connectors.base import BaseConnectorAdapter
from services.connectors.apple_health.adapter import AppleHealthAdapter
from services.connectors.exxir.adapter import ExxirAdapter
from services.connectors.google_calendar.adapter import GoogleCalendarAdapter
from services.connectors.google_maps.service import GoogleMapsService
from services.connectors.greenlight.adapter import GreenlightAdapter
from services.connectors.hearth_display.publisher import HearthDisplayPublisher
from services.connectors.nike_run_club.adapter import NikeRunClubAdapter
from services.connectors.rex.adapter import RexAdapter
from services.connectors.ynab.adapter import YnabAdapter


CONNECTOR_REGISTRY: dict[str, type[BaseConnectorAdapter]] = {
    "google_calendar": GoogleCalendarAdapter,
    "hearth_display": HearthDisplayPublisher,
    "greenlight": GreenlightAdapter,
    "rex": RexAdapter,
    "ynab": YnabAdapter,
    "apple_health": AppleHealthAdapter,
    "nike_run_club": NikeRunClubAdapter,
    "google_maps": GoogleMapsService,
    "exxir": ExxirAdapter,
}


def get_adapter(connector_key: str) -> type[BaseConnectorAdapter]:
    """Resolve an adapter class by key. Raises ``KeyError`` with a
    listing of the known keys if the lookup misses."""
    try:
        return CONNECTOR_REGISTRY[connector_key]
    except KeyError as e:
        known = ", ".join(sorted(CONNECTOR_REGISTRY.keys()))
        raise KeyError(
            f"No adapter registered for '{connector_key}'. Known: {known}"
        ) from e

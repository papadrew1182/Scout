"""Scout connector platform.

Session 2 establishes the adapter contract and the eight first-pass
adapters. Real implementations land in their own follow-up work
packets (E = Google Calendar, F = Greenlight, G = Rex/YNAB, H =
Apple Health / Nike Run Club / Google Maps). Each adapter in this
first pass satisfies the shape so higher layers can import,
register, and smoke-test the platform end to end.
"""

from services.connectors.base import (
    BaseConnectorAdapter,
    ConnectorAccountSummary,
    ConnectorHealth,
    FreshnessState,
    SyncResult,
)
from services.connectors.registry import CONNECTOR_REGISTRY, get_adapter
from services.connectors.sync_service import SyncService

__all__ = [
    "BaseConnectorAdapter",
    "ConnectorAccountSummary",
    "ConnectorHealth",
    "FreshnessState",
    "SyncResult",
    "CONNECTOR_REGISTRY",
    "get_adapter",
    "SyncService",
]

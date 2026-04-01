"""
Phase 22 Live Feed Connectivity Foundation.

На текущем шаге пакет intentionally включает только:
- typed connection/session contracts;
- typed subscription recovery / resubscribe contracts;
- typed feed-health/readiness/degraded truth;
- typed ingress handoff truth.
- narrow single-session connectivity runtime.
- narrow ingest integration path в existing market_data runtime.
- first real Bybit public market-data connector slice.

На этом шаге пакет intentionally не включает:
- adapter/client ecosystem;
- execution connectivity / routing / reconciliation;
- persistence / API / dashboard semantics.
"""

from .bybit import (
    BybitMarketDataConnector,
    BybitMarketDataConnectorConfig,
    BybitMarketDataParser,
    BybitMessageParseError,
    BybitOrderBookProjector,
    BybitParsedEnvelope,
    BybitSubscriptionRegistry,
    BybitWebSocketConnection,
    create_bybit_market_data_connector,
    normalize_bybit_symbol,
)
from .integration import (
    LiveFeedMarketDataIngress,
    LiveFeedMarketDataIngressResult,
    UnsupportedFeedIngressError,
    create_live_feed_market_data_ingress,
)
from .models import (
    FeedConnectionState,
    FeedConnectionStatus,
    FeedConnectivityAssessment,
    FeedIngestRequest,
    FeedIngressEnvelope,
    FeedRecoveryAssessment,
    FeedRecoveryIngestMode,
    FeedResubscribeRequest,
    FeedSessionIdentity,
    FeedSubscriptionRecoveryState,
    FeedSubscriptionRecoveryStatus,
)
from .runtime import (
    FeedConnectivityRuntime,
    FeedConnectivityRuntimeConfig,
    FeedConnectivityRuntimeDiagnostics,
    FeedConnectivityRuntimeState,
    create_live_feed_runtime,
)

__all__ = [
    "BybitMarketDataConnector",
    "BybitMarketDataConnectorConfig",
    "BybitMarketDataParser",
    "BybitMessageParseError",
    "BybitOrderBookProjector",
    "BybitParsedEnvelope",
    "BybitSubscriptionRegistry",
    "BybitWebSocketConnection",
    "FeedConnectionState",
    "FeedConnectionStatus",
    "FeedConnectivityAssessment",
    "FeedConnectivityRuntime",
    "FeedConnectivityRuntimeConfig",
    "FeedConnectivityRuntimeDiagnostics",
    "FeedConnectivityRuntimeState",
    "FeedIngestRequest",
    "FeedIngressEnvelope",
    "FeedRecoveryAssessment",
    "FeedRecoveryIngestMode",
    "FeedResubscribeRequest",
    "FeedSessionIdentity",
    "FeedSubscriptionRecoveryState",
    "FeedSubscriptionRecoveryStatus",
    "LiveFeedMarketDataIngress",
    "LiveFeedMarketDataIngressResult",
    "UnsupportedFeedIngressError",
    "create_bybit_market_data_connector",
    "create_live_feed_market_data_ingress",
    "create_live_feed_runtime",
    "normalize_bybit_symbol",
]

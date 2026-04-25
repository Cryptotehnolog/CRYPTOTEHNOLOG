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
from .bybit_connector_state import (
    BybitAdmissionSnapshot,
    BybitDiscoverySnapshot,
    BybitProjectionSnapshot,
    BybitTradeTruthSnapshot,
    BybitTradeTruthSymbolSnapshot,
    BybitTransportSnapshot,
)
from .bybit_scope_control import (
    BybitAdmissionEngine,
    BybitAdmissionTradeTruthInput,
    BybitScopeApplier,
    BybitScopeApplyResult,
)
from .bybit_recovery_coordinator import (
    BybitHistoricalRecoveryCoordinator,
    BybitHistoricalRecoveryCoordinatorSnapshot,
    BybitHistoricalRecoveryDecision,
    classify_bybit_historical_recovery_result,
)
from .bybit_historical_restore import (
    BybitHistoricalRestoreCoordinator,
    BybitHistoricalRestoreExecution,
)
from .bybit_spot import (
    BybitSpotMarketDataConnector,
    BybitSpotMarketDataConnectorConfig,
    create_bybit_spot_market_data_connector,
)
from .bybit_linear_v2_transport import (
    BybitLinearV2Transport,
    BybitLinearV2TransportConfig,
    create_bybit_linear_v2_transport,
)
from .bybit_spot_v2_transport import (
    BybitSpotV2Transport,
    BybitSpotV2TransportConfig,
    create_bybit_spot_v2_transport,
)
from .bybit_spot_v2_live_trade_ledger import (
    BybitSpotV2LiveTradeLedgerRecord,
    BybitSpotV2LiveTradeLedgerRepository,
    BybitSpotV2LiveTradeLedgerWriteResult,
    write_bybit_spot_v2_live_trade_to_ledger,
)
from .bybit_spot_v2_archive_ledger import (
    BybitSpotV2ArchiveTradeLedgerRecord,
    BybitSpotV2ArchiveTradeLedgerRepository,
    BybitSpotV2ArchiveTradeLedgerWriteResult,
    write_bybit_spot_v2_archive_trade_to_ledger,
)
from .bybit_spot_v2_archive_loader import (
    BybitSpotV2ArchiveLoadReport,
    BybitSpotV2ArchiveLoadRequest,
    BybitSpotV2ArchiveLoader,
    run_bybit_spot_v2_archive_loader,
)
from .bybit_spot_v2_persisted_query import (
    BybitSpotV2PersistedQueryService,
    BybitSpotV2PersistedSymbolSnapshot,
    BybitSpotV2PersistedWindowSnapshot,
)
from .bybit_spot_v2_reconciliation import (
    BybitSpotV2DerivedTradeCountQueryService,
    BybitSpotV2DerivedSymbolSnapshot,
    BybitSpotV2ReconciliationService,
    BybitSpotV2ReconciliationSnapshot,
    BybitSpotV2ReconciliationSymbolSnapshot,
)
from .bybit_spot_v2_diagnostics import (
    BybitSpotV2DiagnosticsService,
    BybitSpotV2DiagnosticsSnapshot,
    BybitSpotV2DiagnosticsSymbolSnapshot,
)
from .bybit_spot_v2_recovery import (
    BybitSpotV2RecoveryCoordinator,
    BybitSpotV2RecoveryProbeSnapshot,
    BybitSpotV2RecoverySnapshot,
    run_bybit_spot_v2_recovery_probe,
)
from .bybit_trade_backfill import (
    BybitHistoricalRecoveryPlan,
    BybitHistoricalTradeBackfillConfig,
    BybitHistoricalTradeBackfillResult,
    BybitHistoricalTradeBackfillService,
    BybitTradeBackfillContour,
    create_bybit_historical_trade_backfill_service,
)
from .bybit_trade_count import (
    BybitDerivedTradeCountDiagnostics,
    BybitDerivedTradeCountPersistedState,
    BybitDerivedTradeCountPersistenceStore,
    BybitDerivedTradeCountSymbolSnapshot,
    BybitDerivedTradeCountTracker,
)
from .bybit_trade_truth_store import BybitTradeTruthStore
from .bybit_trade_count_truth_model import (
    BybitProductTradeCountTruth,
    BybitTradeCountTruthOwnership,
    FINAL_BYBIT_TRADE_COUNT_TRUTH_OWNERSHIP,
    resolve_product_trade_count_truth,
)
from .bybit_universe import (
    BybitMarketContour,
    BybitUniverseDiscoveryConfig,
    BybitUniverseInstrument,
    BybitUniverseSelectionSummary,
    discover_bybit_universe,
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
    "BybitAdmissionSnapshot",
    "BybitAdmissionEngine",
    "BybitAdmissionTradeTruthInput",
    "BybitDerivedTradeCountDiagnostics",
    "BybitDerivedTradeCountPersistedState",
    "BybitDerivedTradeCountPersistenceStore",
    "BybitDerivedTradeCountSymbolSnapshot",
    "BybitDerivedTradeCountTracker",
    "BybitDiscoverySnapshot",
    "BybitHistoricalRecoveryCoordinator",
    "BybitHistoricalRecoveryCoordinatorSnapshot",
    "BybitHistoricalRecoveryDecision",
    "BybitHistoricalRestoreCoordinator",
    "BybitHistoricalRestoreExecution",
    "BybitHistoricalRecoveryPlan",
    "BybitHistoricalTradeBackfillConfig",
    "BybitHistoricalTradeBackfillResult",
    "BybitHistoricalTradeBackfillService",
    "BybitLinearV2Transport",
    "BybitLinearV2TransportConfig",
    "BybitMarketContour",
    "BybitMarketDataConnector",
    "BybitMarketDataConnectorConfig",
    "BybitMarketDataParser",
    "BybitMessageParseError",
    "BybitOrderBookProjector",
    "BybitParsedEnvelope",
    "BybitProjectionSnapshot",
    "BybitSpotMarketDataConnector",
    "BybitSpotMarketDataConnectorConfig",
    "BybitSpotV2Transport",
    "BybitSpotV2LiveTradeLedgerRecord",
    "BybitSpotV2ArchiveLoadReport",
    "BybitSpotV2ArchiveLoadRequest",
    "BybitSpotV2ArchiveLoader",
    "BybitSpotV2ArchiveTradeLedgerRecord",
    "BybitSpotV2ArchiveTradeLedgerRepository",
    "BybitSpotV2ArchiveTradeLedgerWriteResult",
    "BybitSpotV2DiagnosticsService",
    "BybitSpotV2DiagnosticsSnapshot",
    "BybitSpotV2DiagnosticsSymbolSnapshot",
    "BybitSpotV2DerivedTradeCountQueryService",
    "BybitSpotV2DerivedSymbolSnapshot",
    "BybitSpotV2PersistedQueryService",
    "BybitSpotV2PersistedSymbolSnapshot",
    "BybitSpotV2PersistedWindowSnapshot",
    "BybitSpotV2ReconciliationService",
    "BybitSpotV2ReconciliationSnapshot",
    "BybitSpotV2ReconciliationSymbolSnapshot",
    "BybitSpotV2RecoveryCoordinator",
    "BybitSpotV2RecoveryProbeSnapshot",
    "BybitSpotV2RecoverySnapshot",
    "BybitSpotV2LiveTradeLedgerRepository",
    "BybitSpotV2LiveTradeLedgerWriteResult",
    "BybitSpotV2TransportConfig",
    "BybitSubscriptionRegistry",
    "BybitScopeApplier",
    "BybitScopeApplyResult",
    "BybitTradeTruthSnapshot",
    "BybitTradeCountTruthOwnership",
    "BybitTradeTruthStore",
    "BybitTradeTruthSymbolSnapshot",
    "BybitProductTradeCountTruth",
    "BybitTradeBackfillContour",
    "BybitTransportSnapshot",
    "BybitUniverseDiscoveryConfig",
    "BybitUniverseInstrument",
    "BybitUniverseSelectionSummary",
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
    "classify_bybit_historical_recovery_result",
    "create_bybit_historical_trade_backfill_service",
    "create_bybit_linear_v2_transport",
    "create_bybit_market_data_connector",
    "create_bybit_spot_market_data_connector",
    "create_bybit_spot_v2_transport",
    "create_live_feed_market_data_ingress",
    "create_live_feed_runtime",
    "discover_bybit_universe",
    "normalize_bybit_symbol",
    "FINAL_BYBIT_TRADE_COUNT_TRUTH_OWNERSHIP",
    "resolve_product_trade_count_truth",
    "write_bybit_spot_v2_live_trade_to_ledger",
    "run_bybit_spot_v2_archive_loader",
    "run_bybit_spot_v2_recovery_probe",
    "write_bybit_spot_v2_archive_trade_to_ledger",
]

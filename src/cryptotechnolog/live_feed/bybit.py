"""
Узкий Bybit market-data connector поверх existing live_feed и market_data foundations.

Этот модуль intentionally:
- реализует только public market data slice для Bybit;
- отделяет websocket lifecycle, message parsing и orderbook projection;
- переиспользует существующие FeedConnectivityRuntime и LiveFeedMarketDataIngress;
- не вводит общий multi-exchange framework заранее.
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
import json
from typing import TYPE_CHECKING, Any, Literal, Protocol

import websockets
from websockets.exceptions import ConnectionClosed

from cryptotechnolog.config import get_logger, get_settings

from .bybit_recovery_coordinator import BybitHistoricalRecoveryCoordinatorSnapshot
from .bybit_historical_restore import BybitHistoricalRestoreCoordinator
from .bybit_archive_bulk_materialization import BybitArchiveBulkMaterializer
from .bybit_trade_backfill import (
    BybitHistoricalRecoveryPlan,
    BybitHistoricalTradeBackfillService,
    create_bybit_historical_trade_backfill_service,
)
from .bybit_trade_count import (
    BybitDerivedTradeCountDiagnostics,
    BybitDerivedTradeCountPersistenceStore,
    BybitDerivedTradeCountSymbolSnapshot,
    BybitDerivedTradeCountTracker,
    _floor_to_bucket,
)
from .bybit_trade_truth_store import BybitTradeTruthStore
from .bybit_trade_count_cutover_readiness import (
    aggregate_cutover_readiness,
    readiness_from_reconciliation_result,
)
from .bybit_trade_count_cutover_evaluation import (
    BybitTradeCountCutoverEvaluationPolicy,
    evaluate_cutover_policy,
)
from .bybit_trade_count_cutover_discussion import build_cutover_discussion_artifact
from .bybit_trade_count_cutover_review_catalog import build_cutover_review_catalog
from .bybit_trade_count_cutover_review_package import build_cutover_review_package
from .bybit_trade_count_cutover_review_snapshot_collection import (
    build_cutover_review_snapshot_collection,
)
from .bybit_trade_count_cutover_review_compact_digest import (
    build_cutover_review_compact_digest,
)
from .bybit_trade_count_cutover_export_report_bundle import (
    build_cutover_export_report_bundle,
)
from .bybit_trade_count_manual_review import manual_review_from_cutover_evaluation
from .bybit_trade_count_cutover_review_record import build_cutover_review_record
from .bybit_trade_count_reconciliation import (
    BybitTradeCountReconciliationPolicy,
    reconcile_trade_count_truths,
)
from .bybit_trade_count_truth_model import (
    FINAL_BYBIT_TRADE_COUNT_TRUTH_OWNERSHIP,
    resolve_product_trade_count_truth,
)
from .bybit_live_trade_fact import (
    BybitLiveTradeFact,
    BybitLiveTradeFactBuildResult,
    build_bybit_live_trade_fact,
)
from .bybit_live_trade_identity import build_bybit_live_trade_identity
from .bybit_live_trade_ledger_writer import write_live_trade_fact_to_ledger
from .bybit_trade_identity import build_bybit_trade_identity
from .bybit_trade_ledger_query import BybitTradeLedgerTradeCountQueryService
from .bybit_trade_ledger_writer import write_archive_trade_fact_to_ledger
from .bybit_trade_overlap import compare_archive_and_live_trade
from .bybit_universe import fetch_bybit_quote_turnover_24h_by_symbol
from .integration import LiveFeedMarketDataIngress, create_live_feed_market_data_ingress
from .models import (
    FeedRecoveryAssessment,
    FeedRecoveryIngestMode,
    FeedResubscribeRequest,
    FeedSessionIdentity,
    FeedSubscriptionRecoveryState,
    FeedSubscriptionRecoveryStatus,
)
from .runtime import FeedConnectivityRuntime, create_live_feed_runtime

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from pathlib import Path

    from cryptotechnolog.config.settings import Settings
    from cryptotechnolog.market_data import MarketDataRuntime

    from .bybit_trade_ledger_contracts import IBybitTradeLedgerRepository

from cryptotechnolog.market_data import build_symbol_identity

from .bybit_symbols import normalize_bybit_symbol
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
logger = get_logger(__name__)

_BYBIT_MAINNET_LINEAR_PUBLIC_URL = "wss://stream.bybit.com/v5/public/linear"
_BYBIT_TESTNET_LINEAR_PUBLIC_URL = "wss://stream-testnet.bybit.com/v5/public/linear"
_MIN_ORDERBOOK_LEVEL_WIDTH = 2
_DEFAULT_RECONNECT_DELAY_SECONDS = 5
_DEFAULT_STOP_CLOSE_TIMEOUT_SECONDS = 1.0
_DEFAULT_CONNECT_TIMEOUT_SECONDS = 15.0
_DEFAULT_LATEST_ARCHIVE_RETRY_DELAY_SECONDS = 300.0
_DEFAULT_RTT_TIMEOUTS_BEFORE_CLOSE = 2
_DEFAULT_TRANSPORT_RTT_PROBE_TIMEOUT_SECONDS = 3.0
_DEFAULT_TURNOVER_REFRESH_INTERVAL_SECONDS = 5.0

BybitLedgerTradeCountSymbolStatus = Literal[
    "not_configured",
    "fresh",
    "stale",
    "missing",
    "refresh_failed",
]

BybitLedgerTradeCountScopeStatus = Literal[
    "not_configured",
    "ready",
    "partial_refresh_failed",
    "refresh_failed",
]


@dataclass(slots=True, frozen=True)
class BybitLedgerTradeCountSymbolSnapshot:
    trade_count_24h: int | None
    status: BybitLedgerTradeCountSymbolStatus
    last_error: str | None = None
    last_synced_at: datetime | None = None
    window_started_at: datetime | None = None
    first_trade_at: datetime | None = None
    sources: tuple[str, ...] = ()


def _aggregate_product_trade_count_state(
    symbol_snapshots: tuple[dict[str, object], ...],
) -> tuple[str, str]:
    if not symbol_snapshots:
        return "pending_validation", "no_symbol_snapshots"
    states = tuple(
        str(snapshot.get("product_trade_count_state"))
        for snapshot in symbol_snapshots
        if isinstance(snapshot.get("product_trade_count_state"), str)
    )
    if any(state == "reconciliation_mismatch" for state in states):
        return "reconciliation_mismatch", "reconciliation_mismatch_present"
    if states and all(state == "ledger_unavailable" for state in states):
        return "ledger_unavailable", "ledger_unavailable_present"
    if any(state == "ledger_unavailable" for state in states):
        return "pending_validation", "partial_ledger_unavailable_present"
    if states and all(state == "partial_ledger_coverage" for state in states):
        return "partial_ledger_coverage", "partial_ledger_coverage_for_scope"
    if any(state == "partial_ledger_coverage" for state in states):
        return "partial_ledger_coverage", "partial_ledger_coverage_present"
    if any(state == "pending_validation" for state in states):
        return "pending_validation", "pending_validation_present"
    if states and all(state == "ledger_confirmed" for state in states):
        return "ledger_confirmed", "ledger_confirmed_for_scope"
    return "pending_validation", "unknown_product_trade_count_state"


class BybitMessageParseError(ValueError):
    """Ошибка разбора внешнего Bybit сообщения в narrow internal handoff."""


class BybitWebSocketConnection(Protocol):
    async def send(self, message: str) -> None: ...

    async def recv(self) -> str: ...

    async def ping(self, data: object | None = None) -> Awaitable[float]: ...

    async def close(self) -> None: ...


@dataclass(slots=True, frozen=True)
class BybitParsedEnvelope:
    """Нормализованный handoff без привязки к websocket lifecycle."""

    payload_kind: str
    transport_payload: dict[str, Any]
    source_sequence: int | None = None
    feed_name: str = "bybit_public"


@dataclass(slots=True, frozen=True)
class BybitSubscriptionRegistry:
    """Явный subscription registry для narrow Bybit public slice."""

    symbols: tuple[str, ...] = ()
    trade_symbols: tuple[str, ...] | None = None
    orderbook_symbols: tuple[str, ...] | None = None
    orderbook_depth: int = 50

    @property
    def effective_trade_symbols(self) -> tuple[str, ...]:
        if self.trade_symbols is not None:
            return self.trade_symbols
        return self.symbols

    @property
    def effective_orderbook_symbols(self) -> tuple[str, ...]:
        if self.orderbook_symbols is not None:
            return self.orderbook_symbols
        return self.symbols

    @property
    def trade_topics(self) -> tuple[str, ...]:
        return tuple(
            f"publicTrade.{_to_bybit_symbol(symbol)}" for symbol in self.effective_trade_symbols
        )

    @property
    def orderbook_topics(self) -> tuple[str, ...]:
        return tuple(
            f"orderbook.{self.orderbook_depth}.{_to_bybit_symbol(symbol)}"
            for symbol in self.effective_orderbook_symbols
        )

    @property
    def topics(self) -> tuple[str, ...]:
        if self.effective_trade_symbols == self.effective_orderbook_symbols:
            topics: list[str] = []
            for symbol in self.effective_trade_symbols:
                bybit_symbol = _to_bybit_symbol(symbol)
                topics.append(f"publicTrade.{bybit_symbol}")
                topics.append(f"orderbook.{self.orderbook_depth}.{bybit_symbol}")
            return tuple(topics)
        return self.trade_topics + self.orderbook_topics


@dataclass(slots=True, frozen=True)
class BybitMarketDataConnectorConfig:
    """Конфигурация первого narrow Bybit market-data slice."""

    public_stream_url: str = _BYBIT_MAINNET_LINEAR_PUBLIC_URL
    orderbook_depth: int = 50
    ping_interval_seconds: int = 20
    ping_timeout_seconds: int = 20
    reconnect_delay_seconds: int = 5
    max_orderbook_levels: int = 50

    def __post_init__(self) -> None:
        for field_name, value in (
            ("orderbook_depth", self.orderbook_depth),
            ("ping_interval_seconds", self.ping_interval_seconds),
            ("ping_timeout_seconds", self.ping_timeout_seconds),
            ("reconnect_delay_seconds", self.reconnect_delay_seconds),
            ("max_orderbook_levels", self.max_orderbook_levels),
        ):
            if value <= 0:
                raise ValueError(f"{field_name} должен быть положительным")

    @classmethod
    def from_settings(cls, settings: Settings) -> BybitMarketDataConnectorConfig:
        """Build connector config from canonical project settings."""
        return cls(
            public_stream_url=(
                _BYBIT_TESTNET_LINEAR_PUBLIC_URL
                if settings.bybit_testnet
                else _BYBIT_MAINNET_LINEAR_PUBLIC_URL
            ),
            reconnect_delay_seconds=int(
                getattr(
                    settings,
                    "live_feed_retry_delay_seconds",
                    _DEFAULT_RECONNECT_DELAY_SECONDS,
                )
            ),
        )


@dataclass(slots=True)
class _OrderBookSide:
    levels: dict[Decimal, Decimal] = field(default_factory=dict)

    def replace(self, raw_levels: list[list[str]]) -> None:
        self.levels = {}
        for raw_price, raw_qty, *_ in raw_levels:
            price = Decimal(str(raw_price))
            quantity = Decimal(str(raw_qty))
            if quantity > 0:
                self.levels[price] = quantity

    def apply_updates(self, raw_levels: list[list[str]]) -> None:
        for raw_price, raw_qty, *_ in raw_levels:
            price = Decimal(str(raw_price))
            quantity = Decimal(str(raw_qty))
            if quantity <= 0:
                self.levels.pop(price, None)
            else:
                self.levels[price] = quantity


@dataclass(slots=True)
class BybitOrderBookProjector:
    """Поддерживает honest local snapshot path поверх snapshot/delta сообщений Bybit."""

    max_levels: int = 50
    _bids: _OrderBookSide = field(default_factory=_OrderBookSide)
    _asks: _OrderBookSide = field(default_factory=_OrderBookSide)

    def apply_message(self, message: dict[str, Any]) -> dict[str, Any]:
        payload = _ensure_mapping(message.get("data"), field_name="data")
        message_type = str(message.get("type", "snapshot")).lower()
        symbol = normalize_bybit_symbol(str(payload.get("s") or _symbol_from_topic(message)))
        if message_type == "snapshot":
            self._bids.replace(_ensure_levels(payload.get("b"), field_name="bids"))
            self._asks.replace(_ensure_levels(payload.get("a"), field_name="asks"))
        elif message_type == "delta":
            self._bids.apply_updates(_ensure_levels(payload.get("b"), field_name="bids"))
            self._asks.apply_updates(_ensure_levels(payload.get("a"), field_name="asks"))
        else:
            raise BybitMessageParseError(f"Неподдерживаемый orderbook message type: {message_type}")

        bids = self._serialize_bids()
        asks = self._serialize_asks()
        if not bids or not asks:
            raise BybitMessageParseError("Bybit orderbook projection требует non-empty bids и asks")
        return {
            "symbol": symbol,
            "bids": bids,
            "asks": asks,
            "checksum": _optional_str(payload.get("seq") or payload.get("u")),
        }

    def _serialize_bids(self) -> list[dict[str, str]]:
        return [
            {"price": str(price), "qty": str(quantity)}
            for price, quantity in sorted(self._bids.levels.items(), reverse=True)[
                : self.max_levels
            ]
        ]

    def _serialize_asks(self) -> list[dict[str, str]]:
        return [
            {"price": str(price), "qty": str(quantity)}
            for price, quantity in sorted(self._asks.levels.items())[: self.max_levels]
        ]


class BybitMarketDataParser:
    """Exchange-specific parser для Bybit public trade и orderbook сообщений."""

    def __init__(self, *, max_orderbook_levels: int = 50) -> None:
        self._orderbook_projectors: dict[str, BybitOrderBookProjector] = {}
        self._max_orderbook_levels = max_orderbook_levels
        self._symbols_waiting_for_snapshot: set[str] = set()

    def parse_message(self, message: dict[str, Any]) -> tuple[BybitParsedEnvelope, ...]:
        topic = str(message.get("topic", "")).strip()
        if not topic:
            return ()
        if topic.startswith("publicTrade."):
            return self._parse_trade_message(message)
        if topic.startswith("orderbook."):
            orderbook_envelope = self._parse_orderbook_message(message)
            return () if orderbook_envelope is None else (orderbook_envelope,)
        return ()

    def _parse_trade_message(self, message: dict[str, Any]) -> tuple[BybitParsedEnvelope, ...]:
        raw_data = message.get("data")
        if not isinstance(raw_data, list):
            raise BybitMessageParseError("Bybit trade message требует list data")

        envelopes: list[BybitParsedEnvelope] = []
        for entry in raw_data:
            payload = _ensure_mapping(entry, field_name="trade entry")
            symbol = normalize_bybit_symbol(str(payload.get("s") or _symbol_from_topic(message)))
            side = _normalize_trade_side(payload.get("S"))
            trade_id = _optional_str(payload.get("i") or payload.get("tradeId"))
            if trade_id is None:
                raise BybitMessageParseError("Bybit trade message требует trade id")
            envelopes.append(
                BybitParsedEnvelope(
                    payload_kind="trade_tick",
                    transport_payload={
                        "symbol": symbol,
                        "price": str(_decimal_value(payload.get("p"), field_name="price")),
                        "qty": str(_decimal_value(payload.get("v"), field_name="qty")),
                        "side": side,
                        "trade_id": trade_id,
                        "is_buyer_maker": bool(payload.get("m", False)),
                        "exchange_trade_at_ms": _optional_int(payload.get("T")),
                    },
                    source_sequence=_optional_int(payload.get("T")),
                    feed_name="trades",
                )
            )
        return tuple(envelopes)

    def _parse_orderbook_message(self, message: dict[str, Any]) -> BybitParsedEnvelope | None:
        symbol = normalize_bybit_symbol(_symbol_from_topic(message))
        message_type = str(message.get("type", "snapshot")).lower()
        if message_type != "snapshot" and (
            symbol in self._symbols_waiting_for_snapshot or symbol not in self._orderbook_projectors
        ):
            return None
        projector = self._orderbook_projectors.setdefault(
            symbol,
            BybitOrderBookProjector(max_levels=self._max_orderbook_levels),
        )
        transport_payload = projector.apply_message(message)
        if message_type == "snapshot":
            self._symbols_waiting_for_snapshot.discard(symbol)
        return BybitParsedEnvelope(
            payload_kind="orderbook_snapshot",
            transport_payload=transport_payload,
            source_sequence=_optional_int(message.get("ts")),
            feed_name="orderbook",
        )

    def invalidate_orderbook_state(self, *, symbols: tuple[str, ...]) -> None:
        """Сбросить локальный derived orderbook state после disconnect/recovery boundary."""
        for symbol in tuple(normalize_bybit_symbol(symbol) for symbol in symbols):
            self._orderbook_projectors.pop(symbol, None)
            self._symbols_waiting_for_snapshot.add(symbol)

    def awaiting_snapshot_symbols(self) -> tuple[str, ...]:
        return tuple(sorted(self._symbols_waiting_for_snapshot))


class BybitMarketDataConnector:
    """Первый real exchange-specific slice для Bybit public market data."""

    def __init__(
        self,
        *,
        session: FeedSessionIdentity,
        market_data_runtime: MarketDataRuntime,
        config: BybitMarketDataConnectorConfig | None = None,
        feed_runtime: FeedConnectivityRuntime | None = None,
        ingress: LiveFeedMarketDataIngress | None = None,
        parser: BybitMarketDataParser | None = None,
        websocket_factory: Callable[
            [BybitMarketDataConnectorConfig], Awaitable[BybitWebSocketConnection]
        ]
        | None = None,
        sleep_func: Callable[[float], Awaitable[None]] | None = None,
        universe_scope_mode: bool = False,
        universe_min_trade_count_24h: int = 0,
        derived_trade_count_store_path: Path | None = None,
        historical_trade_backfill_service: BybitHistoricalTradeBackfillService | None = None,
        ledger_trade_count_query_service: BybitTradeLedgerTradeCountQueryService | None = None,
        ledger_repository: IBybitTradeLedgerRepository | None = None,
    ) -> None:
        if session.exchange.lower() not in {"bybit", "bybit_spot"}:
            raise ValueError("BybitMarketDataConnector требует bybit/bybit_spot session identity")
        self.session = session
        self.market_data_runtime = market_data_runtime
        self.config = config or BybitMarketDataConnectorConfig.from_settings(get_settings())
        self.feed_runtime = feed_runtime or create_live_feed_runtime(session=session)
        self.ingress = ingress or create_live_feed_market_data_ingress()
        self.parser = parser or BybitMarketDataParser(
            max_orderbook_levels=self.config.max_orderbook_levels
        )
        self._coarse_candidate_symbols = session.subscription_scope
        self._candidate_scope_symbols = self._coarse_candidate_symbols
        self._qualifying_scope_symbols = self._coarse_candidate_symbols
        self._selected_scope_symbols = self._coarse_candidate_symbols
        self._applied_subscription_symbols = self._coarse_candidate_symbols
        self._websocket_factory = websocket_factory or _connect_bybit_public_stream
        self._sleep_func = sleep_func or _sleep_seconds
        self._stop_requested = False
        self._active_websocket: BybitWebSocketConnection | None = None
        self._rtt_monitor_task: asyncio.Task[None] | None = None
        self._stop_close_task: asyncio.Task[None] | None = None
        self._stop_closing_websocket: BybitWebSocketConnection | None = None
        self._transport_rtt_ms: int | None = None
        self._application_heartbeat_latency_ms: int | None = None
        self._disconnect_reason_override: str | None = None
        self._application_pong_waiter: asyncio.Future[datetime] | None = None
        self._reset_transport_telemetry()
        self._universe_scope_mode = universe_scope_mode
        self._universe_min_trade_count_24h = max(0, universe_min_trade_count_24h)
        self._trade_count_admission_enabled = (
            self._universe_scope_mode and self._universe_min_trade_count_24h > 0
        )
        self._admission_engine = BybitAdmissionEngine()
        self._scope_applier = BybitScopeApplier()
        self.subscription_registry = self._build_subscription_registry(
            orderbook_symbols=self._active_symbols
        )
        self._trade_truth_store = BybitTradeTruthStore(
            symbols=session.subscription_scope,
            admission_enabled=self._trade_count_admission_enabled,
            derived_trade_count_store=(
                BybitDerivedTradeCountPersistenceStore(path=derived_trade_count_store_path)
                if self._trade_count_admission_enabled and derived_trade_count_store_path is not None
                else None
            ),
            ledger_trade_count_query_service=ledger_trade_count_query_service,
        )
        self._ledger_repository = ledger_repository
        self._post_readiness_narrowing_applied = False
        self._post_recovery_materialization_task: asyncio.Task[None] | None = None
        self._pending_post_recovery_materialization_request: tuple[
            BybitHistoricalTradeBackfillResult,
            BybitHistoricalRecoveryPlan,
            datetime,
        ] | None = None
        self._post_recovery_materialization_status = "idle"
        self._post_recovery_materialization_last_error: str | None = None
        self._pending_scope_apply_symbols: tuple[str, ...] | None = None
        settings = get_settings()
        self._historical_restore_coordinator = BybitHistoricalRestoreCoordinator(
            exchange_name=self.session.exchange,
            sleep_func=self._sleep_func,
            retry_delay_seconds=float(settings.live_feed_retry_delay_seconds),
            backfill_service=(
                historical_trade_backfill_service if self._trade_count_admission_enabled else None
            ),
        )
        self._trade_count_reconciliation_policy = BybitTradeCountReconciliationPolicy()
        self._trade_count_cutover_evaluation_policy = BybitTradeCountCutoverEvaluationPolicy()
        self._turnover_refresh_task: asyncio.Task[None] | None = None
        self._quote_turnover_24h_by_symbol: dict[str, Decimal] = {}
        self._quote_turnover_last_synced_at: datetime | None = None
        self._quote_turnover_last_error: str | None = None
        self._rest_base_url = (
            "https://api-testnet.bybit.com" if settings.bybit_testnet else "https://api.bybit.com"
        )
        self._trade_truth_store.restore_persisted_state(restored_at=_utcnow())
        self._historical_restore_coordinator.initialize(
            admission_enabled=self._trade_count_admission_enabled,
            trade_truth_ready=self._trade_truth_store.ready,
            mark_backfill_pending=lambda: self._trade_truth_store.mark_backfill_pending(),
            mark_backfill_not_needed=self._trade_truth_store.mark_backfill_not_needed,
        )
        now = _utcnow()
        self._recovery_state = FeedSubscriptionRecoveryState(
            session=self.session,
            status=FeedSubscriptionRecoveryStatus.IDLE,
            observed_at=now,
        )

    @property
    def _active_symbols(self) -> tuple[str, ...]:
        return self._applied_subscription_symbols

    @_active_symbols.setter
    def _active_symbols(self, value: tuple[str, ...]) -> None:
        self._applied_subscription_symbols = tuple(value)

    @property
    def _candidate_symbols(self) -> tuple[str, ...]:
        return self._candidate_scope_symbols

    @property
    def _qualifying_symbols(self) -> tuple[str, ...]:
        return self._qualifying_scope_symbols

    @property
    def _selected_symbols(self) -> tuple[str, ...]:
        return self._selected_scope_symbols

    def _set_admission_scope_state(
        self,
        snapshot: BybitAdmissionSnapshot,
    ) -> None:
        self._candidate_scope_symbols = snapshot.trade_count_admission_candidate_symbols
        self._qualifying_scope_symbols = snapshot.trade_count_qualifying_symbols
        self._selected_scope_symbols = snapshot.selected_symbols

    @property
    def _derived_trade_count(self) -> BybitDerivedTradeCountTracker:
        return self._trade_truth_store.derived_trade_count

    @property
    def _derived_trade_count_store(self) -> BybitDerivedTradeCountPersistenceStore | None:
        return self._trade_truth_store.derived_trade_count_store

    @property
    def _historical_trade_backfill_service(self) -> BybitHistoricalTradeBackfillService | None:
        return self._historical_restore_coordinator.backfill_service

    @_historical_trade_backfill_service.setter
    def _historical_trade_backfill_service(
        self,
        value: BybitHistoricalTradeBackfillService | None,
    ) -> None:
        self._historical_restore_coordinator.backfill_service = value

    @property
    def _historical_recovery_coordinator(self):
        return self._historical_restore_coordinator.recovery

    @property
    def _ledger_trade_count_query_service(self) -> BybitTradeLedgerTradeCountQueryService | None:
        return self._trade_truth_store.ledger_trade_count_query_service

    @_ledger_trade_count_query_service.setter
    def _ledger_trade_count_query_service(
        self,
        value: BybitTradeLedgerTradeCountQueryService | None,
    ) -> None:
        self._trade_truth_store.ledger_trade_count_query_service = value

    @property
    def _ledger_trade_count_snapshot_by_symbol(self) -> dict[str, BybitLedgerTradeCountSymbolSnapshot]:
        return self._trade_truth_store.ledger_trade_count_snapshot_by_symbol

    @_ledger_trade_count_snapshot_by_symbol.setter
    def _ledger_trade_count_snapshot_by_symbol(
        self,
        value: dict[str, BybitLedgerTradeCountSymbolSnapshot],
    ) -> None:
        self._trade_truth_store.ledger_trade_count_snapshot_by_symbol = value

    @property
    def _ledger_trade_count_24h_by_symbol(self) -> dict[str, int | None]:
        return self._trade_truth_store.ledger_trade_count_24h_by_symbol

    @property
    def _ledger_trade_count_scope_status(self) -> BybitLedgerTradeCountScopeStatus:
        return self._trade_truth_store.ledger_trade_count_scope_status

    @_ledger_trade_count_scope_status.setter
    def _ledger_trade_count_scope_status(self, value: BybitLedgerTradeCountScopeStatus) -> None:
        self._trade_truth_store.ledger_trade_count_scope_status = value

    @property
    def _ledger_trade_count_available(self) -> bool:
        return self._trade_truth_store.ledger_trade_count_available

    @_ledger_trade_count_available.setter
    def _ledger_trade_count_available(self, value: bool) -> None:
        self._trade_truth_store.ledger_trade_count_available = value

    @property
    def _ledger_trade_count_last_error(self) -> str | None:
        return self._trade_truth_store.ledger_trade_count_last_error

    @_ledger_trade_count_last_error.setter
    def _ledger_trade_count_last_error(self, value: str | None) -> None:
        self._trade_truth_store.ledger_trade_count_last_error = value

    @property
    def _ledger_trade_count_last_synced_at(self) -> datetime | None:
        return self._trade_truth_store.ledger_trade_count_last_synced_at

    @_ledger_trade_count_last_synced_at.setter
    def _ledger_trade_count_last_synced_at(self, value: datetime | None) -> None:
        self._trade_truth_store.ledger_trade_count_last_synced_at = value

    def set_ledger_trade_count_query_service(
        self,
        service: BybitTradeLedgerTradeCountQueryService | None,
    ) -> None:
        """Подключить runtime ledger query path до запуска live contour."""
        self._trade_truth_store.set_ledger_trade_count_query_service(service)

    @property
    def _historical_trade_backfill_pending(self) -> bool:
        return self._historical_restore_coordinator.pending

    @_historical_trade_backfill_pending.setter
    def _historical_trade_backfill_pending(self, value: bool) -> None:
        self._historical_restore_coordinator.pending = value

    @property
    def _historical_trade_backfill_task(self) -> asyncio.Task[None] | None:
        return self._historical_restore_coordinator.backfill_task

    @_historical_trade_backfill_task.setter
    def _historical_trade_backfill_task(self, value: asyncio.Task[None] | None) -> None:
        self._historical_restore_coordinator.backfill_task = value

    @property
    def _historical_trade_backfill_retry_task(self) -> asyncio.Task[None] | None:
        return self._historical_restore_coordinator.retry_task

    @_historical_trade_backfill_retry_task.setter
    def _historical_trade_backfill_retry_task(self, value: asyncio.Task[None] | None) -> None:
        self._historical_restore_coordinator.retry_task = value

    @property
    def _historical_trade_backfill_cutoff_at(self) -> datetime | None:
        return self._historical_restore_coordinator.cutoff_at

    @_historical_trade_backfill_cutoff_at.setter
    def _historical_trade_backfill_cutoff_at(self, value: datetime | None) -> None:
        self._historical_restore_coordinator.cutoff_at = value

    @property
    def _latest_archive_backfill_retry_pending(self) -> bool:
        return self._historical_restore_coordinator.latest_retry_pending

    @_latest_archive_backfill_retry_pending.setter
    def _latest_archive_backfill_retry_pending(self, value: bool) -> None:
        self._historical_restore_coordinator.latest_retry_pending = value

    async def run(self, *, max_cycles: int | None = None) -> None:
        """Запустить explicit reconnect loop для узкого Bybit market-data path."""
        logger.info(
            "Bybit connector run entered",
            exchange=self.session.exchange,
            contour=self._ledger_contour(),
        )
        self._stop_requested = False
        cycle = 0
        await self.feed_runtime.start(observed_at=_utcnow())
        logger.info(
            "Bybit connector bootstrap started",
            exchange=self.session.exchange,
            contour=self._ledger_contour(),
        )
        if self._ledger_contour() == "spot":
            asyncio.create_task(
                self._bootstrap_trade_truth_from_local_ledger(),
                name=f"{self.session.exchange}_ledger_bootstrap",
            )
        else:
            await self._bootstrap_trade_truth_from_local_ledger()
        logger.info(
            "Bybit connector bootstrap finished",
            exchange=self.session.exchange,
            contour=self._ledger_contour(),
        )
        self._turnover_refresh_task = asyncio.create_task(
            self._refresh_quote_turnover_loop(),
            name=f"{self.session.exchange}_quote_turnover_refresh",
        )
        while not self._stop_requested and (max_cycles is None or cycle < max_cycles):
            cycle += 1
            websocket: BybitWebSocketConnection | None = None
            connect_stage = "begin"
            try:
                logger.info(
                    "Bybit connector connect loop entered",
                    exchange=self.session.exchange,
                    contour=self._ledger_contour(),
                    cycle=cycle,
                )
                connect_stage = "begin_connecting"
                self.feed_runtime.begin_connecting(observed_at=_utcnow())
                connect_timeout_seconds = float(
                    getattr(self.config, "ping_timeout_seconds", _DEFAULT_CONNECT_TIMEOUT_SECONDS)
                )
                if connect_timeout_seconds <= 0:
                    connect_timeout_seconds = _DEFAULT_CONNECT_TIMEOUT_SECONDS
                logger.info(
                    "Bybit connector transport connect started",
                    exchange=self.session.exchange,
                    contour=self._ledger_contour(),
                    url=getattr(self.config, "public_stream_url", None),
                )
                connect_stage = "connect"
                websocket = await asyncio.wait_for(
                    self._websocket_factory(self.config),
                    timeout=connect_timeout_seconds,
                )
                logger.info(
                    "Bybit connector transport connected",
                    exchange=self.session.exchange,
                    contour=self._ledger_contour(),
                )
                self._active_websocket = websocket
                self._transport_rtt_ms = None
                self._mark_resubscribing(reason="transport_connected", observed_at=_utcnow())
                connect_stage = "subscribe"
                logger.info(
                    "Bybit connector subscribe started",
                    exchange=self.session.exchange,
                    contour=self._ledger_contour(),
                )
                await self._subscribe(websocket)
                logger.info(
                    "Bybit connector subscribe finished",
                    exchange=self.session.exchange,
                    contour=self._ledger_contour(),
                )
                self.feed_runtime.mark_connected(observed_at=_utcnow())
                self._schedule_historical_trade_count_backfill()
                self._rtt_monitor_task = asyncio.create_task(self._monitor_transport_rtt(websocket))
                connect_stage = "consume"
                await self._consume_messages(websocket)
            except Exception as exc:
                logger.warning(
                    "Bybit connector transport failed",
                    exchange=self.session.exchange,
                    contour=self._ledger_contour(),
                    url=getattr(self.config, "public_stream_url", None),
                    stage=connect_stage,
                    exc_info=True,
                )
                if self._stop_requested:
                    break
                await self._handle_disconnect(reason=self._consume_disconnect_reason(exc))
            finally:
                if self._rtt_monitor_task is not None:
                    self._rtt_monitor_task.cancel()
                    self._rtt_monitor_task = None
                if self._stop_requested and self._historical_trade_backfill_task is not None:
                    self._historical_trade_backfill_task.cancel()
                    self._historical_trade_backfill_task = None
                if self._stop_requested and self._post_recovery_materialization_task is not None:
                    self._post_recovery_materialization_task.cancel()
                    self._post_recovery_materialization_task = None
                    self._pending_post_recovery_materialization_request = None
                if websocket is not None and websocket is not self._stop_closing_websocket:
                    await self._close_websocket_with_timeout(websocket)
                self._active_websocket = None
            if not self._stop_requested:
                await self._sleep_func(self.config.reconnect_delay_seconds)
        self._persist_derived_trade_count(force=True)
        if self._turnover_refresh_task is not None:
            self._turnover_refresh_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._turnover_refresh_task
            self._turnover_refresh_task = None
        if self.feed_runtime.is_started:
            await self.feed_runtime.stop(observed_at=_utcnow())

    async def stop(self) -> None:
        """Явно запросить stop текущего reconnect loop."""
        self._stop_requested = True
        self._persist_derived_trade_count(force=True)
        self._historical_restore_coordinator.cancel()
        if self._post_recovery_materialization_task is not None:
            self._post_recovery_materialization_task.cancel()
            self._post_recovery_materialization_task = None
        self._pending_post_recovery_materialization_request = None
        if self._turnover_refresh_task is not None:
            self._turnover_refresh_task.cancel()
        if self._active_websocket is not None:
            websocket = self._active_websocket
            self._active_websocket = None
            self._stop_closing_websocket = websocket
            self._stop_close_task = asyncio.create_task(
                self._close_websocket_with_timeout(websocket),
                name=f"{self.session.exchange}_stop_close",
            )

    async def ingest_transport_message(self, raw_message: str) -> int:
        """Принять сырое websocket сообщение и передать нормализованные данные в market_data."""
        message = _ensure_mapping(json.loads(raw_message), field_name="transport message")
        if _is_control_message(message):
            self._handle_control_message(message)
            return 0
        envelopes = self.parser.parse_message(message)
        if not envelopes:
            return 0

        accepted = 0
        for envelope in envelopes:
            should_ingest = True
            if envelope.payload_kind == "trade_tick":
                payload_symbol = envelope.transport_payload.get("symbol")
                if isinstance(payload_symbol, str):
                    should_ingest = payload_symbol in self._active_symbols
            if should_ingest:
                request = self.feed_runtime.build_ingest_request(
                    payload_kind=envelope.payload_kind,
                    transport_payload=envelope.transport_payload,
                    ingested_at=_utcnow(),
                    source_sequence=envelope.source_sequence,
                )
                await self.ingress.ingest(
                    request=request,
                    market_data_runtime=self.market_data_runtime,
                )
            if envelope.payload_kind == "trade_tick":
                payload_symbol = envelope.transport_payload.get("symbol")
                exchange_trade_at_ms = envelope.transport_payload.get("exchange_trade_at_ms")
                if isinstance(payload_symbol, str) and isinstance(exchange_trade_at_ms, int):
                    trade_observed_at = datetime.fromtimestamp(
                        exchange_trade_at_ms / 1000,
                        tz=UTC,
                    )
                    await self._write_live_trade_fact_to_ledger(
                        transport_payload=envelope.transport_payload,
                    )
                    await self._refresh_ledger_trade_count_snapshot(
                        symbols=(payload_symbol,),
                        observed_at=trade_observed_at,
                    )
                    self._trade_truth_store.note_live_trade(
                        symbol=payload_symbol,
                        observed_at=trade_observed_at,
                    )
                    self._persist_derived_trade_count(observed_at=trade_observed_at)
                    await self._maybe_apply_post_readiness_narrowing()
            if should_ingest:
                accepted += 1
        if (
            accepted > 0
            and self._recovery_state.status
            in (
                FeedSubscriptionRecoveryStatus.RESUBSCRIBING,
                FeedSubscriptionRecoveryStatus.RECOVERED,
            )
            and not self.parser.awaiting_snapshot_symbols()
        ):
            self._mark_recovered(observed_at=_utcnow())
        return accepted

    async def _write_live_trade_fact_to_ledger(
        self,
        *,
        transport_payload: dict[str, object],
    ) -> None:
        if self._ledger_repository is None:
            return
        fact_result = build_bybit_live_trade_fact(
            contour=self._ledger_contour(),
            transport_payload=transport_payload,
        )
        identity = build_bybit_live_trade_identity(fact_result)
        await write_live_trade_fact_to_ledger(
            fact_result=fact_result,
            identity=identity,
            repository=self._ledger_repository,
        )

    async def _materialize_archive_trade_facts_to_ledger(
        self,
        *,
        result: BybitHistoricalTradeBackfillResult,
        plan: BybitHistoricalRecoveryPlan | None = None,
    ) -> None:
        if self._ledger_repository is None:
            return
        if (
            not result.archive_trade_extractions_by_symbol
            and plan is not None
            and self._historical_trade_backfill_service is not None
        ):
            result = await asyncio.to_thread(
                self._historical_trade_backfill_service.load_materialization_plan,
                plan=plan,
            )
        materializer = BybitArchiveBulkMaterializer(repository=self._ledger_repository)
        await materializer.materialize_result(
            contour=self._ledger_contour(),
            symbols=result.hydrated_symbols,
            observed_at=result.covered_until_at or _utcnow(),
            result=result,
        )

    async def _augment_restore_result_with_ledger_tail(
        self,
        *,
        result: BybitHistoricalTradeBackfillResult,
        observed_at: datetime,
    ) -> BybitHistoricalTradeBackfillResult:
        if (
            self._ledger_repository is None
            or result.restored_window_started_at is None
            or result.covered_until_at is None
            or observed_at <= result.covered_until_at
        ):
            return result
        merged_trade_buckets_by_symbol = {
            symbol: dict(buckets)
            for symbol, buckets in result.trade_buckets_by_symbol.items()
        }
        merged_latest_trade_at_by_symbol = dict(result.latest_trade_at_by_symbol)
        for symbol in result.hydrated_symbols:
            rows = await self._ledger_repository.list_trade_facts(
                exchange=self._ledger_exchange_id(),
                contour=self._ledger_contour(),
                normalized_symbol=symbol,
                window_started_at=result.covered_until_at,
                window_ended_at=observed_at,
            )
            if not rows:
                continue
            symbol_buckets = merged_trade_buckets_by_symbol.setdefault(symbol, {})
            latest_trade_at = merged_latest_trade_at_by_symbol.get(symbol)
            for row in rows:
                trade_at = getattr(row, "exchange_trade_at", None)
                if not isinstance(trade_at, datetime):
                    continue
                bucket_start = _floor_to_bucket(
                    observed_at=trade_at,
                    bucket_width=self._derived_trade_count.bucket_width,
                )
                symbol_buckets[bucket_start] = symbol_buckets.get(bucket_start, 0) + 1
                normalized_trade_at = trade_at.astimezone(UTC)
                if latest_trade_at is None or normalized_trade_at > latest_trade_at:
                    latest_trade_at = normalized_trade_at
            merged_latest_trade_at_by_symbol[symbol] = latest_trade_at
        return replace(
            result,
            trade_buckets_by_symbol=merged_trade_buckets_by_symbol,
            latest_trade_at_by_symbol=merged_latest_trade_at_by_symbol,
        )

    def _archive_source_trade_identities_from_rows(
        self,
        *,
        rows: tuple[object, ...],
    ) -> set[str]:
        identities: set[str] = set()
        for row in rows:
            source = getattr(row, "source", None)
            source_trade_identity = getattr(row, "source_trade_identity", None)
            if source == "bybit_public_archive" and isinstance(source_trade_identity, str):
                identities.add(source_trade_identity)
            provenance_metadata = getattr(row, "provenance_metadata", {})
            if not isinstance(provenance_metadata, dict):
                continue
            archive_metadata = provenance_metadata.get("archive")
            if not isinstance(archive_metadata, dict):
                continue
            provenance_source_trade_identity = archive_metadata.get("source_trade_identity")
            if isinstance(provenance_source_trade_identity, str):
                identities.add(provenance_source_trade_identity)
        return identities

    def _build_live_overlap_candidate(
        self,
        *,
        row: object,
    ) -> tuple[object, BybitLiveTradeFactBuildResult, object] | None:
        if getattr(row, "source", None) != "live_public_trade":
            return None
        source_metadata = getattr(row, "source_metadata", {})
        if not isinstance(source_metadata, dict):
            return None
        live_trade_id = source_metadata.get("live_trade_id")
        if not isinstance(live_trade_id, str) or not live_trade_id:
            return None
        live_fact_result = BybitLiveTradeFactBuildResult(
            status="full_mappable",
            trade_fact=BybitLiveTradeFact(
                contour=str(getattr(row, "contour")),
                normalized_symbol=str(getattr(row, "normalized_symbol")),
                exchange_trade_at=getattr(row, "exchange_trade_at"),
                side=str(getattr(row, "side")),
                normalized_price=getattr(row, "normalized_price"),
                normalized_size=getattr(row, "normalized_size"),
                live_trade_id=live_trade_id,
                is_buyer_maker=False,
                raw_fields={},
                identity_strength="strong_candidate",
            ),
        )
        live_identity = build_bybit_live_trade_identity(live_fact_result)
        return row, live_fact_result, live_identity

    def _select_live_overlap_candidate(
        self,
        *,
        archive_extraction,
        archive_identity,
        live_candidates: list[tuple[int, object, BybitLiveTradeFactBuildResult, object]],
    ) -> tuple[int, object, object] | None:
        exact_matches: list[tuple[int, object, object]] = []
        fallback_matches: list[tuple[int, object, object]] = []
        ambiguous_found = False
        for index, live_record, live_fact_result, live_identity in live_candidates:
            overlap_result = compare_archive_and_live_trade(
                archive_extraction=archive_extraction,
                archive_identity=archive_identity,
                live_fact_result=live_fact_result,
                live_identity=live_identity,
            )
            if overlap_result.verdict == "exact_match_candidate":
                exact_matches.append((index, live_record, overlap_result))
            elif overlap_result.verdict == "fallback_match_candidate":
                fallback_matches.append((index, live_record, overlap_result))
            elif overlap_result.verdict == "ambiguous":
                ambiguous_found = True
        if not ambiguous_found and len(exact_matches) == 1:
            return exact_matches[0]
        if not ambiguous_found and not exact_matches and len(fallback_matches) == 1:
            return fallback_matches[0]
        return None

    async def _subscribe(self, websocket: BybitWebSocketConnection) -> None:
        if not self.subscription_registry.topics:
            return
        payload = {
            "op": "subscribe",
            "args": list(self.subscription_registry.topics),
        }
        await websocket.send(json.dumps(payload))

    async def _consume_messages(self, websocket: BybitWebSocketConnection) -> None:
        while not self._stop_requested:
            raw_message = await websocket.recv()
            self._last_transport_message_at = _utcnow()
            await self.ingest_transport_message(raw_message)

    async def _monitor_transport_rtt(self, websocket: BybitWebSocketConnection) -> None:  # noqa: PLR0912, PLR0915
        consecutive_timeouts = 0
        loop = asyncio.get_running_loop()
        try:
            while not self._stop_requested and self._active_websocket is websocket:
                transport_rtt_task: asyncio.Task[float | None] | None = None
                try:
                    transport_rtt_task = asyncio.create_task(self._measure_transport_rtt(websocket))
                    self._last_application_ping_sent_at = _utcnow()
                    latency_seconds = await self._await_application_pong(websocket)
                except asyncio.CancelledError:
                    if transport_rtt_task is not None:
                        transport_rtt_task.cancel()
                    raise
                except ConnectionClosed:
                    if transport_rtt_task is not None:
                        transport_rtt_task.cancel()
                    return
                except TimeoutError:
                    if transport_rtt_task is not None:
                        transport_rtt_task.cancel()
                    should_close_transport, consecutive_timeouts = self._register_ping_timeout(
                        consecutive_timeouts=consecutive_timeouts + 1
                    )
                    if not should_close_transport:
                        await self._sleep_func(self.config.ping_interval_seconds)
                        continue
                    if self._active_websocket is websocket and not self._stop_requested:
                        self._disconnect_reason_override = "ping_timeout"
                        await self._close_websocket_with_timeout(websocket)
                    return
                except Exception:
                    if transport_rtt_task is not None:
                        transport_rtt_task.cancel()
                    logger.warning(
                        "Bybit connector RTT monitor ignored transient ping failure",
                        exchange=self.session.exchange,
                        exc_info=True,
                    )
                    return
                consecutive_timeouts = 0
                self._last_ping_timeout_ignored_due_to_recent_messages = False
                self._last_application_pong_at = _utcnow()
                self._application_heartbeat_latency_ms = max(0, int(float(latency_seconds) * 1000))
                transport_rtt_ms: int | None = None
                if transport_rtt_task is not None:
                    try:
                        transport_latency_seconds = await transport_rtt_task
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        transport_latency_seconds = None
                    if transport_latency_seconds is not None:
                        transport_rtt_ms = max(0, int(float(transport_latency_seconds) * 1000))
                if transport_rtt_ms is not None:
                    self._transport_rtt_ms = transport_rtt_ms
                expected_resume_at = loop.time() + float(self.config.ping_interval_seconds)
                await self._sleep_func(self.config.ping_interval_seconds)
                self._last_ping_timeout_loop_lag_ms = max(
                    0,
                    int((loop.time() - expected_resume_at) * 1000),
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning(
                "Bybit connector RTT monitor stopped unexpectedly",
                exchange=self.session.exchange,
                exc_info=True,
            )
            return

    async def _close_websocket_with_timeout(self, websocket: BybitWebSocketConnection) -> None:
        try:
            await asyncio.wait_for(
                websocket.close(),
                timeout=_DEFAULT_STOP_CLOSE_TIMEOUT_SECONDS,
            )
        except TimeoutError:
            logger.warning(
                "Bybit connector websocket close timed out",
                exchange=self.session.exchange,
                timeout_seconds=_DEFAULT_STOP_CLOSE_TIMEOUT_SECONDS,
            )
        except Exception:
            logger.warning(
                "Bybit connector websocket close failed",
                exchange=self.session.exchange,
                exc_info=True,
            )
        finally:
            if self._stop_closing_websocket is websocket:
                self._stop_closing_websocket = None
            if self._stop_close_task is not None and self._stop_close_task.done():
                self._stop_close_task = None

    async def _handle_disconnect(self, *, reason: str) -> None:
        observed_at = _utcnow()
        logger.warning("Bybit market data connector disconnected", reason=reason)
        backfill_was_running = self._historical_trade_backfill_task is not None
        trade_count_diagnostics = (
            self._derived_trade_count.get_diagnostics(observed_at=observed_at)
            if self._trade_count_admission_enabled
            else None
        )
        can_reuse_restored_window_during_backfill = bool(
            backfill_was_running
            and trade_count_diagnostics is not None
            and trade_count_diagnostics.state in {"ready", "live_tail_pending_after_gap"}
        )
        reuse_historical_window = (
            self._trade_count_admission_enabled
            and self._derived_trade_count.has_restored_historical_window
            and (not backfill_was_running or can_reuse_restored_window_during_backfill)
        )
        backfill_progress = trade_count_diagnostics if backfill_was_running else None
        preserve_narrowed_scope = (
            reuse_historical_window
            and self._post_readiness_narrowing_applied
            and bool(self._active_symbols)
            and self._active_symbols != self._coarse_candidate_symbols
        )
        self._transport_rtt_ms = None
        if not preserve_narrowed_scope:
            self._restore_active_scope_to_coarse_candidates()
        self.parser.invalidate_orderbook_state(symbols=self._active_symbols)
        self._trade_truth_store.mark_gap(
            observed_at=observed_at,
            reason=reason,
            reuse_historical_window=reuse_historical_window,
        )
        self._persist_derived_trade_count(observed_at=observed_at, force=True)
        self._post_readiness_narrowing_applied = False
        self._historical_trade_backfill_pending = (
            self._historical_restore_coordinator.note_disconnect(
                reuse_historical_window=reuse_historical_window
            )
        )
        if backfill_was_running and backfill_progress is not None and not reuse_historical_window:
            if (
                backfill_progress.backfill_status == "running"
                and isinstance(backfill_progress.backfill_processed_archives, int)
                and isinstance(backfill_progress.backfill_total_archives, int)
            ):
                self._trade_truth_store.mark_backfill_running(
                    processed_archives=backfill_progress.backfill_processed_archives,
                    total_archives=backfill_progress.backfill_total_archives,
                )
            else:
                self._trade_truth_store.mark_backfill_pending(
                    total_archives=backfill_progress.backfill_total_archives,
                )
        elif self._historical_trade_backfill_pending:
            self._trade_truth_store.mark_backfill_pending()
        self._mark_recovery_required(reason=reason, observed_at=observed_at)
        self.feed_runtime.mark_disconnected(observed_at=observed_at, reason=reason)
        for symbol in self._active_symbols:
            normalized_symbol = normalize_bybit_symbol(symbol)
            for feed_name in ("trades", "orderbook"):
                await self.market_data_runtime.mark_source_degraded(
                    symbol=normalized_symbol,
                    exchange=self.session.exchange,
                    feed=feed_name,
                    reason=reason,
                    detected_at=observed_at,
                )

    def get_recovery_state(self) -> FeedSubscriptionRecoveryState:
        return self._recovery_state

    def _reset_transport_telemetry(self) -> None:
        self._last_transport_message_at: datetime | None = None
        self._last_ping_sent_at: datetime | None = None
        self._last_pong_at: datetime | None = None
        self._last_application_ping_sent_at: datetime | None = None
        self._last_application_pong_at: datetime | None = None
        self._application_heartbeat_latency_ms = None
        self._last_ping_timeout_at: datetime | None = None
        self._last_ping_timeout_message_age_ms: int | None = None
        self._last_ping_timeout_loop_lag_ms: int | None = None
        self._last_ping_timeout_backfill_status: str | None = None
        self._last_ping_timeout_processed_archives: int | None = None
        self._last_ping_timeout_total_archives: int | None = None
        self._last_ping_timeout_cache_source: str | None = None
        self._last_ping_timeout_ignored_due_to_recent_messages = False

    def _consume_disconnect_reason(self, exc: Exception) -> str:
        override = self._disconnect_reason_override
        self._disconnect_reason_override = None
        if override:
            return override
        return _format_disconnect_reason(exc)

    def _build_ping_timeout_context(self, *, observed_at: datetime) -> dict[str, object]:
        trade_count_diagnostics = self._derived_trade_count.get_diagnostics(observed_at=observed_at)
        cache_diagnostics = (
            self._historical_trade_backfill_service.get_cache_diagnostics()
            if self._historical_trade_backfill_service is not None
            else None
        )
        message_age_ms: int | None = None
        if self._last_transport_message_at is not None:
            message_age_ms = max(
                0,
                int((observed_at - self._last_transport_message_at).total_seconds() * 1000),
            )
        return {
            "message_age_ms": message_age_ms,
            "loop_lag_ms": self._last_ping_timeout_loop_lag_ms,
            "backfill_status": trade_count_diagnostics.backfill_status,
            "processed_archives": trade_count_diagnostics.backfill_processed_archives,
            "total_archives": trade_count_diagnostics.backfill_total_archives,
            "cache_source": (
                cache_diagnostics.last_hit_source if cache_diagnostics is not None else None
            ),
        }

    async def _await_application_pong(self, websocket: BybitWebSocketConnection) -> float:
        loop = asyncio.get_running_loop()
        sent_at = self._last_application_ping_sent_at or _utcnow()
        pong_waiter = loop.create_future()
        self._application_pong_waiter = pong_waiter
        try:
            await websocket.send(json.dumps({"op": "ping"}))
            pong_observed_at = await asyncio.wait_for(
                pong_waiter,
                timeout=self.config.ping_timeout_seconds,
            )
        finally:
            if self._application_pong_waiter is pong_waiter:
                self._application_pong_waiter = None
        return max(0.0, (pong_observed_at - sent_at).total_seconds())

    async def _measure_transport_rtt(self, websocket: BybitWebSocketConnection) -> float | None:
        loop = asyncio.get_running_loop()
        sent_at = loop.time()
        self._last_ping_sent_at = _utcnow()
        try:
            pong_waiter = await websocket.ping()
            await asyncio.wait_for(
                pong_waiter,
                timeout=min(
                    float(self.config.ping_timeout_seconds),
                    _DEFAULT_TRANSPORT_RTT_PROBE_TIMEOUT_SECONDS,
                ),
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            return None
        self._last_pong_at = _utcnow()
        return max(0.0, loop.time() - sent_at)

    def _register_ping_timeout(self, *, consecutive_timeouts: int) -> tuple[bool, int]:
        timeout_observed_at = _utcnow()
        timeout_context = self._build_ping_timeout_context(observed_at=timeout_observed_at)
        self._last_ping_timeout_at = timeout_observed_at
        self._last_ping_timeout_message_age_ms = timeout_context["message_age_ms"]
        self._last_ping_timeout_loop_lag_ms = timeout_context["loop_lag_ms"]
        self._last_ping_timeout_backfill_status = timeout_context["backfill_status"]
        self._last_ping_timeout_processed_archives = timeout_context["processed_archives"]
        self._last_ping_timeout_total_archives = timeout_context["total_archives"]
        self._last_ping_timeout_cache_source = timeout_context["cache_source"]
        recent_message_grace_ms = max(
            int(float(self.config.ping_timeout_seconds) * 1000),
            500,
        )
        recent_transport_activity = bool(
            timeout_context["message_age_ms"] is not None
            and timeout_context["message_age_ms"] <= recent_message_grace_ms
        )
        self._last_ping_timeout_ignored_due_to_recent_messages = recent_transport_activity
        logger.warning(
            "Bybit connector application heartbeat timed out",
            exchange=self.session.exchange,
            timeout_seconds=self.config.ping_timeout_seconds,
            consecutive_failures=consecutive_timeouts,
            message_age_ms=timeout_context["message_age_ms"],
            loop_lag_ms=timeout_context["loop_lag_ms"],
            backfill_status=timeout_context["backfill_status"],
            processed_archives=timeout_context["processed_archives"],
            total_archives=timeout_context["total_archives"],
            cache_source=timeout_context["cache_source"],
            ignored_due_to_recent_messages=recent_transport_activity,
        )
        if recent_transport_activity:
            return False, 0
        return consecutive_timeouts >= _DEFAULT_RTT_TIMEOUTS_BEFORE_CLOSE, consecutive_timeouts

    def get_recovery_assessment(self) -> FeedRecoveryAssessment:
        state = self._recovery_state
        return FeedRecoveryAssessment(
            session=self._active_recovery_session(),
            status=state.status,
            observed_at=state.observed_at,
            ingest_mode=(
                FeedRecoveryIngestMode.RECOVERY_RESET_REQUIRED
                if state.reset_required
                else FeedRecoveryIngestMode.NORMAL
            ),
            is_recovered=state.status == FeedSubscriptionRecoveryStatus.RECOVERED,
            reset_required=state.reset_required,
            blocked=state.status == FeedSubscriptionRecoveryStatus.RECOVERY_BLOCKED,
            recovery_reason=state.last_recovery_reason,
            metadata=state.metadata,
        )

    def build_discovery_snapshot(self) -> BybitDiscoverySnapshot:
        return BybitDiscoverySnapshot(
            exchange=self.session.exchange,
            scope_mode=self._operator_scope_mode(),
            coarse_candidate_symbols=self._coarse_candidate_symbols,
            discovery_status="ready",
            instruments_passed_coarse_filter=len(self._coarse_candidate_symbols),
            quote_turnover_24h_by_symbol=tuple(
                (symbol, str(value))
                for symbol, value in sorted(self._quote_turnover_24h_by_symbol.items())
            ),
            quote_turnover_last_synced_at=(
                self._quote_turnover_last_synced_at.isoformat()
                if self._quote_turnover_last_synced_at is not None
                else None
            ),
            quote_turnover_last_error=self._quote_turnover_last_error,
        )

    def build_transport_snapshot(self) -> BybitTransportSnapshot:
        feed_runtime = self.feed_runtime.get_runtime_diagnostics()
        recovery_state = self.get_recovery_state()
        last_message_at = feed_runtime.get("last_message_at")
        message_age_ms: int | None = None
        if isinstance(last_message_at, str):
            observed_at = datetime.fromisoformat(last_message_at)
            message_age_ms = max(
                0,
                int((_utcnow() - observed_at).total_seconds() * 1000),
            )
        return BybitTransportSnapshot(
            transport_status=str(feed_runtime["status"]),
            recovery_status=recovery_state.status.value,
            subscription_alive=bool(recovery_state.metadata.get("subscription_alive", False)),
            last_message_at=last_message_at if isinstance(last_message_at, str) else None,
            message_age_ms=message_age_ms,
            transport_rtt_ms=self._transport_rtt_ms,
            last_ping_sent_at=(
                self._last_ping_sent_at.isoformat() if self._last_ping_sent_at is not None else None
            ),
            last_pong_at=self._last_pong_at.isoformat() if self._last_pong_at is not None else None,
            application_ping_sent_at=(
                self._last_application_ping_sent_at.isoformat()
                if self._last_application_ping_sent_at is not None
                else None
            ),
            application_pong_at=(
                self._last_application_pong_at.isoformat()
                if self._last_application_pong_at is not None
                else None
            ),
            application_heartbeat_latency_ms=self._application_heartbeat_latency_ms,
            last_ping_timeout_at=(
                self._last_ping_timeout_at.isoformat()
                if self._last_ping_timeout_at is not None
                else None
            ),
            last_ping_timeout_message_age_ms=self._last_ping_timeout_message_age_ms,
            last_ping_timeout_loop_lag_ms=self._last_ping_timeout_loop_lag_ms,
            last_ping_timeout_backfill_status=self._last_ping_timeout_backfill_status,
            last_ping_timeout_processed_archives=self._last_ping_timeout_processed_archives,
            last_ping_timeout_total_archives=self._last_ping_timeout_total_archives,
            last_ping_timeout_cache_source=self._last_ping_timeout_cache_source,
            last_ping_timeout_ignored_due_to_recent_messages=(
                self._last_ping_timeout_ignored_due_to_recent_messages
            ),
            degraded_reason=(
                str(feed_runtime.get("degraded_reason"))
                if isinstance(feed_runtime.get("degraded_reason"), str)
                else None
            ),
            last_disconnect_reason=(
                str(feed_runtime.get("last_disconnect_reason"))
                if isinstance(feed_runtime.get("last_disconnect_reason"), str)
                else None
            ),
            retry_count=int(feed_runtime["retry_count"])
            if isinstance(feed_runtime.get("retry_count"), int)
            else None,
            ready=bool(feed_runtime.get("ready", False)),
            started=bool(feed_runtime.get("started", False)),
            lifecycle_state=(
                str(feed_runtime.get("lifecycle_state"))
                if isinstance(feed_runtime.get("lifecycle_state"), str)
                else None
            ),
            reset_required=recovery_state.reset_required,
        )

    def build_trade_truth_snapshot(
        self,
        *,
        compact_cutover_payload: bool = False,
        diagnostics: BybitDerivedTradeCountDiagnostics | None = None,
        observed_at: datetime | None = None,
    ) -> BybitTradeTruthSnapshot:
        symbols = self._active_symbols
        observed_at = observed_at or _utcnow()
        full_candidate_symbols = self._admission_candidate_symbols()
        full_trade_count_diagnostics = diagnostics or self._derived_trade_count.get_diagnostics(
            observed_at=observed_at
        )
        trade_count_diagnostics = full_trade_count_diagnostics
        derived_trade_counts = {
            snapshot.symbol: snapshot for snapshot in trade_count_diagnostics.symbol_snapshots
        }
        raw_symbol_snapshots = tuple(
            self._build_symbol_diagnostics(
                symbol=symbol,
                derived_trade_count_snapshot=derived_trade_counts.get(symbol),
                derived_trade_count_diagnostics=trade_count_diagnostics,
            )
            for symbol in symbols
        )
        cutover_readiness = aggregate_cutover_readiness(
            tuple(
                readiness_from_reconciliation_result(snapshot["_trade_count_reconciliation_result"])
                for snapshot in raw_symbol_snapshots
            )
        )
        cutover_evaluation = evaluate_cutover_policy(
            reconciliation_results=tuple(
                snapshot["_trade_count_reconciliation_result"] for snapshot in raw_symbol_snapshots
            ),
            readiness=cutover_readiness,
            policy=self._trade_count_cutover_evaluation_policy,
        )
        manual_review = manual_review_from_cutover_evaluation(
            evaluation=cutover_evaluation,
            contour=self._ledger_contour(),
            scope_mode=self._operator_scope_mode(),
            scope_symbol_count=len(symbols),
        )
        symbol_snapshots = tuple(
            BybitTradeTruthSymbolSnapshot(
                **{
                    key: value
                    for key, value in snapshot.items()
                    if key != "_trade_count_reconciliation_result"
                }
            )
            for snapshot in raw_symbol_snapshots
        )
        cutover_discussion_artifact: dict[str, object] = {}
        cutover_review_record_payload: dict[str, object] = {}
        cutover_review_package_payload: dict[str, object] = {}
        cutover_review_catalog_payload: dict[str, object] = {}
        cutover_review_snapshot_collection_payload: dict[str, object] = {}
        cutover_review_compact_digest_payload: dict[str, object] = {}
        cutover_export_report_bundle_payload: dict[str, object] = {}
        if not compact_cutover_payload:
            cutover_discussion = build_cutover_discussion_artifact(
                contour=self._ledger_contour(),
                scope_mode=self._operator_scope_mode(),
                scope_symbol_count=len(symbols),
                reconciliation_results=tuple(
                    snapshot["_trade_count_reconciliation_result"] for snapshot in raw_symbol_snapshots
                ),
                cutover_readiness=cutover_readiness,
                cutover_evaluation=cutover_evaluation,
                manual_review=manual_review,
                symbol_snapshots=tuple(snapshot.to_dict() for snapshot in symbol_snapshots),
            )
            cutover_review_record = build_cutover_review_record(
                captured_at=observed_at.isoformat(),
                discussion_artifact=cutover_discussion,
            )
            cutover_review_package = build_cutover_review_package(
                discussion_artifact=cutover_discussion,
                review_record=cutover_review_record,
            )
            cutover_review_catalog = build_cutover_review_catalog(
                review_package=cutover_review_package
            )
            cutover_review_snapshot_collection = build_cutover_review_snapshot_collection(
                review_catalog=cutover_review_catalog
            )
            cutover_review_compact_digest = build_cutover_review_compact_digest(
                review_snapshot_collection=cutover_review_snapshot_collection
            )
            cutover_export_report_bundle = build_cutover_export_report_bundle(
                compact_digest=cutover_review_compact_digest
            )
            cutover_discussion_artifact = {
                "discussion_state": cutover_discussion.discussion_state,
                "headline": cutover_discussion.headline,
                "contour": cutover_discussion.contour,
                "scope_mode": cutover_discussion.scope_mode,
                "scope_symbol_count": cutover_discussion.scope_symbol_count,
                "reconciliation_summary": tuple(
                    {"name": item.name, "count": item.count}
                    for item in cutover_discussion.reconciliation_summary
                ),
                "cutover_readiness_state": cutover_discussion.cutover_readiness_state,
                "cutover_readiness_reason": cutover_discussion.cutover_readiness_reason,
                "cutover_evaluation_state": cutover_discussion.cutover_evaluation_state,
                "cutover_evaluation_reasons": cutover_discussion.cutover_evaluation_reasons,
                "manual_review_state": cutover_discussion.manual_review_state,
                "manual_review_reasons": cutover_discussion.manual_review_reasons,
                "compared_symbols": cutover_discussion.compared_symbols,
                "ready_symbols": cutover_discussion.ready_symbols,
                "not_ready_symbols": cutover_discussion.not_ready_symbols,
                "blocked_symbols": cutover_discussion.blocked_symbols,
                "symbol_exceptions": tuple(
                    {
                        "symbol": item.symbol,
                        "reconciliation_verdict": item.reconciliation_verdict,
                        "reconciliation_reason": item.reconciliation_reason,
                        "cutover_readiness_state": item.cutover_readiness_state,
                        "cutover_readiness_reason": item.cutover_readiness_reason,
                    }
                    for item in cutover_discussion.symbol_exceptions
                ),
            }
            cutover_review_record_payload = {
                "captured_at": cutover_review_record.captured_at,
                "contour": cutover_review_record.contour,
                "scope_mode": cutover_review_record.scope_mode,
                "scope_symbol_count": cutover_review_record.scope_symbol_count,
                "discussion_state": cutover_review_record.discussion_state,
                "manual_review_state": cutover_review_record.manual_review_state,
                "cutover_evaluation_state": cutover_review_record.cutover_evaluation_state,
                "cutover_readiness_state": cutover_review_record.cutover_readiness_state,
                "compared_symbols": cutover_review_record.compared_symbols,
                "ready_symbols": cutover_review_record.ready_symbols,
                "not_ready_symbols": cutover_review_record.not_ready_symbols,
                "blocked_symbols": cutover_review_record.blocked_symbols,
                "headline": cutover_review_record.headline,
                "reasons_summary": cutover_review_record.reasons_summary,
                "symbol_exceptions": cutover_review_record.symbol_exceptions,
            }
            cutover_review_package_payload = {
                "contour": cutover_review_package.contour,
                "scope_mode": cutover_review_package.scope_mode,
                "scope_symbol_count": cutover_review_package.scope_symbol_count,
                "discussion_state": cutover_review_package.discussion_state,
                "manual_review_state": cutover_review_package.manual_review_state,
                "cutover_evaluation_state": cutover_review_package.cutover_evaluation_state,
                "cutover_readiness_state": cutover_review_package.cutover_readiness_state,
                "compared_symbols": cutover_review_package.compared_symbols,
                "ready_symbols": cutover_review_package.ready_symbols,
                "not_ready_symbols": cutover_review_package.not_ready_symbols,
                "blocked_symbols": cutover_review_package.blocked_symbols,
                "headline": cutover_review_package.headline,
                "reasons_summary": cutover_review_package.reasons_summary,
                "review_record": {
                    "captured_at": cutover_review_package.review_record.captured_at,
                    "contour": cutover_review_package.review_record.contour,
                    "scope_mode": cutover_review_package.review_record.scope_mode,
                    "scope_symbol_count": cutover_review_package.review_record.scope_symbol_count,
                    "discussion_state": cutover_review_package.review_record.discussion_state,
                    "manual_review_state": cutover_review_package.review_record.manual_review_state,
                    "cutover_evaluation_state": (
                        cutover_review_package.review_record.cutover_evaluation_state
                    ),
                    "cutover_readiness_state": (
                        cutover_review_package.review_record.cutover_readiness_state
                    ),
                    "compared_symbols": cutover_review_package.review_record.compared_symbols,
                    "ready_symbols": cutover_review_package.review_record.ready_symbols,
                    "not_ready_symbols": cutover_review_package.review_record.not_ready_symbols,
                    "blocked_symbols": cutover_review_package.review_record.blocked_symbols,
                    "headline": cutover_review_package.review_record.headline,
                    "reasons_summary": cutover_review_package.review_record.reasons_summary,
                    "symbol_exceptions": cutover_review_package.review_record.symbol_exceptions,
                },
                "symbol_exceptions": cutover_review_package.symbol_exceptions,
            }
            cutover_review_catalog_payload = {
                "contour": cutover_review_catalog.contour,
                "scope_mode": cutover_review_catalog.scope_mode,
                "headline": cutover_review_catalog.headline,
                "discussion_state": cutover_review_catalog.discussion_state,
                "manual_review_state": cutover_review_catalog.manual_review_state,
                "cutover_evaluation_state": cutover_review_catalog.cutover_evaluation_state,
                "cutover_readiness_state": cutover_review_catalog.cutover_readiness_state,
                "compared_symbols": cutover_review_catalog.compared_symbols,
                "ready_symbols": cutover_review_catalog.ready_symbols,
                "not_ready_symbols": cutover_review_catalog.not_ready_symbols,
                "blocked_symbols": cutover_review_catalog.blocked_symbols,
                "reasons_summary": cutover_review_catalog.reasons_summary,
                "current_review_package": cutover_review_package_payload,
            }
            cutover_review_snapshot_collection_payload = {
                "contour": cutover_review_snapshot_collection.contour,
                "scope_mode": cutover_review_snapshot_collection.scope_mode,
                "headline": cutover_review_snapshot_collection.headline,
                "discussion_state": cutover_review_snapshot_collection.discussion_state,
                "manual_review_state": cutover_review_snapshot_collection.manual_review_state,
                "cutover_evaluation_state": (
                    cutover_review_snapshot_collection.cutover_evaluation_state
                ),
                "cutover_readiness_state": (
                    cutover_review_snapshot_collection.cutover_readiness_state
                ),
                "compared_symbols": cutover_review_snapshot_collection.compared_symbols,
                "ready_symbols": cutover_review_snapshot_collection.ready_symbols,
                "not_ready_symbols": cutover_review_snapshot_collection.not_ready_symbols,
                "blocked_symbols": cutover_review_snapshot_collection.blocked_symbols,
                "reasons_summary": cutover_review_snapshot_collection.reasons_summary,
                "current_review_package_headline": (
                    cutover_review_snapshot_collection.current_review_package_headline
                ),
                "current_review_package_discussion_state": (
                    cutover_review_snapshot_collection.current_review_package_discussion_state
                ),
                "current_review_catalog": cutover_review_catalog_payload,
            }
            cutover_review_compact_digest_payload = {
                "contour": cutover_review_compact_digest.contour,
                "scope_mode": cutover_review_compact_digest.scope_mode,
                "headline": cutover_review_compact_digest.headline,
                "discussion_state": cutover_review_compact_digest.discussion_state,
                "manual_review_state": cutover_review_compact_digest.manual_review_state,
                "cutover_evaluation_state": cutover_review_compact_digest.cutover_evaluation_state,
                "cutover_readiness_state": cutover_review_compact_digest.cutover_readiness_state,
                "compared_symbols": cutover_review_compact_digest.compared_symbols,
                "ready_symbols": cutover_review_compact_digest.ready_symbols,
                "not_ready_symbols": cutover_review_compact_digest.not_ready_symbols,
                "blocked_symbols": cutover_review_compact_digest.blocked_symbols,
                "reasons_summary": cutover_review_compact_digest.reasons_summary,
                "compact_symbol_exceptions": cutover_review_compact_digest.compact_symbol_exceptions,
                "current_review_snapshot_collection": cutover_review_snapshot_collection_payload,
            }
            cutover_export_report_bundle_payload = {
                "contour": cutover_export_report_bundle.contour,
                "scope_mode": cutover_export_report_bundle.scope_mode,
                "headline": cutover_export_report_bundle.headline,
                "discussion_state": cutover_export_report_bundle.discussion_state,
                "manual_review_state": cutover_export_report_bundle.manual_review_state,
                "cutover_evaluation_state": cutover_export_report_bundle.cutover_evaluation_state,
                "cutover_readiness_state": cutover_export_report_bundle.cutover_readiness_state,
                "compared_symbols": cutover_export_report_bundle.compared_symbols,
                "ready_symbols": cutover_export_report_bundle.ready_symbols,
                "not_ready_symbols": cutover_export_report_bundle.not_ready_symbols,
                "blocked_symbols": cutover_export_report_bundle.blocked_symbols,
                "reasons_summary": cutover_export_report_bundle.reasons_summary,
                "compact_symbol_exceptions": cutover_export_report_bundle.compact_symbol_exceptions,
                "export_text_summary": cutover_export_report_bundle.export_text_summary,
                "current_compact_digest": cutover_review_compact_digest_payload,
            }
        trade_count_product_truth_state, trade_count_product_truth_reason = (
            _aggregate_product_trade_count_state(
                tuple(snapshot.to_dict() for snapshot in symbol_snapshots)
            )
        )
        if (
            trade_count_product_truth_state == "pending_validation"
            and trade_count_product_truth_reason == "pending_validation_present"
            and len(symbol_snapshots) == 1
            and symbol_snapshots[0].ledger_trade_count_24h is not None
            and symbol_snapshots[0].trade_count_reconciliation_verdict == "not_comparable"
        ):
            # Preserve the pre-refactor aggregate reason surface for the single-symbol
            # "ledger present, comparison still incomplete" contour.
            trade_count_product_truth_reason = "partial_ledger_unavailable_present"
        primary_snapshot = symbol_snapshots[0] if symbol_snapshots else None
        recovery_coordinator = self._get_historical_recovery_coordinator_snapshot()
        admission_snapshot = self._build_admission_snapshot(
            diagnostics=full_trade_count_diagnostics,
        )
        operational_recovery_state, operational_recovery_reason = (
            self._resolve_operational_recovery_surface(
                readiness_state=admission_snapshot.readiness_state,
            )
        )
        canonical_ledger_sync_state, canonical_ledger_sync_reason = (
            self._resolve_canonical_ledger_sync_surface(
                backfill_status=trade_count_diagnostics.backfill_status,
            )
        )
        cache_diagnostics_getter = (
            getattr(self._historical_trade_backfill_service, "get_cache_diagnostics", None)
            if self._historical_trade_backfill_service is not None
            else None
        )
        cache_diagnostics = (
            cache_diagnostics_getter() if callable(cache_diagnostics_getter) else None
        )
        if compact_cutover_payload:
            return BybitTradeTruthSnapshot(
                symbol_snapshots=symbol_snapshots,
                trade_seen=all(snapshot.trade_seen for snapshot in symbol_snapshots),
                orderbook_seen=all(snapshot.orderbook_seen for snapshot in symbol_snapshots),
                best_bid=primary_snapshot.best_bid if primary_snapshot is not None else None,
                best_ask=primary_snapshot.best_ask if primary_snapshot is not None else None,
                operational_recovery_state=operational_recovery_state,
                operational_recovery_reason=operational_recovery_reason,
                canonical_ledger_sync_state=canonical_ledger_sync_state,
                canonical_ledger_sync_reason=canonical_ledger_sync_reason,
                derived_trade_count_state=trade_count_diagnostics.state,
                derived_trade_count_ready=trade_count_diagnostics.ready,
                derived_trade_count_observation_started_at=(
                    trade_count_diagnostics.observation_started_at
                ),
                derived_trade_count_reliable_after=trade_count_diagnostics.reliable_after,
                derived_trade_count_last_gap_at=trade_count_diagnostics.last_gap_at,
                derived_trade_count_last_gap_reason=trade_count_diagnostics.last_gap_reason,
                derived_trade_count_backfill_status=trade_count_diagnostics.backfill_status,
                derived_trade_count_backfill_needed=trade_count_diagnostics.backfill_needed,
                derived_trade_count_backfill_processed_archives=(
                    trade_count_diagnostics.backfill_processed_archives
                ),
                derived_trade_count_backfill_total_archives=(
                    trade_count_diagnostics.backfill_total_archives
                ),
                derived_trade_count_backfill_progress_percent=(
                    trade_count_diagnostics.backfill_progress_percent
                ),
                derived_trade_count_last_backfill_at=trade_count_diagnostics.last_backfill_at,
                derived_trade_count_last_backfill_source=(
                    trade_count_diagnostics.last_backfill_source
                ),
                derived_trade_count_last_backfill_reason=(
                    trade_count_diagnostics.last_backfill_reason
                ),
                ledger_trade_count_available=self._ledger_trade_count_available,
                ledger_trade_count_scope_status=self._ledger_trade_count_scope_status,
                ledger_trade_count_last_error=self._ledger_trade_count_last_error,
                ledger_trade_count_last_synced_at=(
                    self._ledger_trade_count_last_synced_at.isoformat()
                    if self._ledger_trade_count_last_synced_at is not None
                    else None
                ),
                trade_count_truth_model=FINAL_BYBIT_TRADE_COUNT_TRUTH_OWNERSHIP.truth_model,
                trade_count_canonical_truth_owner=(
                    FINAL_BYBIT_TRADE_COUNT_TRUTH_OWNERSHIP.canonical_trade_truth_owner
                ),
                trade_count_canonical_truth_source=(
                    FINAL_BYBIT_TRADE_COUNT_TRUTH_OWNERSHIP.canonical_trade_truth_source
                ),
                trade_count_operational_truth_owner=(
                    FINAL_BYBIT_TRADE_COUNT_TRUTH_OWNERSHIP.connector_runtime_truth_owner
                ),
                trade_count_operational_truth_source=(
                    FINAL_BYBIT_TRADE_COUNT_TRUTH_OWNERSHIP.connector_runtime_truth_source
                ),
                trade_count_connector_canonical_role=(
                    FINAL_BYBIT_TRADE_COUNT_TRUTH_OWNERSHIP.connector_canonical_role
                ),
                trade_count_product_truth_state=trade_count_product_truth_state,
                trade_count_product_truth_reason=trade_count_product_truth_reason,
                trade_count_cutover_readiness_state=cutover_readiness.state,
                trade_count_cutover_readiness_reason=cutover_readiness.reason,
                trade_count_cutover_compared_symbols=cutover_readiness.compared_symbols,
                trade_count_cutover_ready_symbols=cutover_readiness.ready_symbols,
                trade_count_cutover_not_ready_symbols=cutover_readiness.not_ready_symbols,
                trade_count_cutover_blocked_symbols=cutover_readiness.blocked_symbols,
                trade_count_cutover_evaluation_state=cutover_evaluation.state,
                trade_count_cutover_evaluation_reasons=cutover_evaluation.reasons,
                trade_count_cutover_evaluation_minimum_compared_symbols=(
                    cutover_evaluation.minimum_compared_symbols
                ),
                trade_count_cutover_manual_review_state=manual_review.state,
                trade_count_cutover_manual_review_reasons=manual_review.reasons,
                trade_count_cutover_manual_review_evaluation_state=(
                    manual_review.evaluation_state
                ),
                trade_count_cutover_manual_review_contour=manual_review.contour,
                trade_count_cutover_manual_review_scope_mode=manual_review.scope_mode,
                trade_count_cutover_manual_review_scope_symbol_count=(
                    manual_review.scope_symbol_count
                ),
                trade_count_cutover_manual_review_compared_symbols=manual_review.compared_symbols,
                trade_count_cutover_manual_review_ready_symbols=manual_review.ready_symbols,
                trade_count_cutover_manual_review_not_ready_symbols=(
                    manual_review.not_ready_symbols
                ),
                trade_count_cutover_manual_review_blocked_symbols=manual_review.blocked_symbols,
                trade_count_cutover_discussion_artifact={},
                trade_count_cutover_review_record={},
                trade_count_cutover_review_package={},
                trade_count_cutover_review_catalog={},
                trade_count_cutover_review_snapshot_collection={},
                trade_count_cutover_review_compact_digest={},
                trade_count_cutover_export_report_bundle={},
                historical_recovery_state=recovery_coordinator.state,
                historical_recovery_reason=recovery_coordinator.reason,
                historical_recovery_retry_pending=recovery_coordinator.retry_pending,
                historical_recovery_backfill_task_active=(
                    recovery_coordinator.backfill_task_active
                ),
                historical_recovery_retry_task_active=recovery_coordinator.retry_task_active,
                historical_recovery_cutoff_at=recovery_coordinator.cutoff_at,
                archive_cache_enabled=(
                    cache_diagnostics.cache_enabled if cache_diagnostics is not None else False
                ),
                archive_cache_memory_hits=(
                    cache_diagnostics.memory_hits if cache_diagnostics is not None else 0
                ),
                archive_cache_disk_hits=(
                    cache_diagnostics.disk_hits if cache_diagnostics is not None else 0
                ),
                archive_cache_misses=(
                    cache_diagnostics.misses if cache_diagnostics is not None else 0
                ),
                archive_cache_writes=(
                    cache_diagnostics.writes if cache_diagnostics is not None else 0
                ),
                archive_cache_last_hit_source=(
                    cache_diagnostics.last_hit_source if cache_diagnostics is not None else None
                ),
                archive_cache_last_url=(
                    cache_diagnostics.last_archive_url if cache_diagnostics is not None else None
                ),
                archive_cache_last_cleanup_at=(
                    cache_diagnostics.last_cleanup_at if cache_diagnostics is not None else None
                ),
                archive_cache_last_pruned_files=(
                    cache_diagnostics.last_pruned_files if cache_diagnostics is not None else 0
                ),
                archive_cache_last_network_fetch_ms=(
                    cache_diagnostics.last_network_fetch_ms
                    if cache_diagnostics is not None
                    else None
                ),
                archive_cache_last_disk_read_ms=(
                    cache_diagnostics.last_disk_read_ms if cache_diagnostics is not None else None
                ),
                archive_cache_last_gzip_decode_ms=(
                    cache_diagnostics.last_gzip_decode_ms
                    if cache_diagnostics is not None
                    else None
                ),
                archive_cache_last_csv_parse_ms=(
                    cache_diagnostics.last_csv_parse_ms if cache_diagnostics is not None else None
                ),
                archive_cache_last_archive_total_ms=(
                    cache_diagnostics.last_archive_total_ms
                    if cache_diagnostics is not None
                    else None
                ),
                archive_cache_last_symbol_total_ms=(
                    cache_diagnostics.last_symbol_total_ms
                    if cache_diagnostics is not None
                    else None
                ),
                archive_cache_last_symbol=(
                    cache_diagnostics.last_symbol if cache_diagnostics is not None else None
                ),
                archive_cache_total_network_fetch_ms=(
                    cache_diagnostics.total_network_fetch_ms if cache_diagnostics is not None else 0
                ),
                archive_cache_total_disk_read_ms=(
                    cache_diagnostics.total_disk_read_ms if cache_diagnostics is not None else 0
                ),
                archive_cache_total_gzip_decode_ms=(
                    cache_diagnostics.total_gzip_decode_ms if cache_diagnostics is not None else 0
                ),
                archive_cache_total_csv_parse_ms=(
                    cache_diagnostics.total_csv_parse_ms if cache_diagnostics is not None else 0
                ),
                archive_cache_total_archive_total_ms=(
                    cache_diagnostics.total_archive_total_ms
                    if cache_diagnostics is not None
                    else 0
                ),
                archive_cache_total_symbol_total_ms=(
                    cache_diagnostics.total_symbol_total_ms if cache_diagnostics is not None else 0
                ),
            )
        return BybitTradeTruthSnapshot(
            symbol_snapshots=symbol_snapshots,
            trade_seen=all(snapshot.trade_seen for snapshot in symbol_snapshots),
            orderbook_seen=all(snapshot.orderbook_seen for snapshot in symbol_snapshots),
            best_bid=primary_snapshot.best_bid if primary_snapshot is not None else None,
            best_ask=primary_snapshot.best_ask if primary_snapshot is not None else None,
            operational_recovery_state=operational_recovery_state,
            operational_recovery_reason=operational_recovery_reason,
            canonical_ledger_sync_state=canonical_ledger_sync_state,
            canonical_ledger_sync_reason=canonical_ledger_sync_reason,
            derived_trade_count_state=trade_count_diagnostics.state,
            derived_trade_count_ready=trade_count_diagnostics.ready,
            derived_trade_count_observation_started_at=trade_count_diagnostics.observation_started_at,
            derived_trade_count_reliable_after=trade_count_diagnostics.reliable_after,
            derived_trade_count_last_gap_at=trade_count_diagnostics.last_gap_at,
            derived_trade_count_last_gap_reason=trade_count_diagnostics.last_gap_reason,
            derived_trade_count_backfill_status=trade_count_diagnostics.backfill_status,
            derived_trade_count_backfill_needed=trade_count_diagnostics.backfill_needed,
            derived_trade_count_backfill_processed_archives=(
                trade_count_diagnostics.backfill_processed_archives
            ),
            derived_trade_count_backfill_total_archives=(
                trade_count_diagnostics.backfill_total_archives
            ),
            derived_trade_count_backfill_progress_percent=(
                trade_count_diagnostics.backfill_progress_percent
            ),
            derived_trade_count_last_backfill_at=trade_count_diagnostics.last_backfill_at,
            derived_trade_count_last_backfill_source=trade_count_diagnostics.last_backfill_source,
            derived_trade_count_last_backfill_reason=trade_count_diagnostics.last_backfill_reason,
            ledger_trade_count_available=self._ledger_trade_count_available,
            ledger_trade_count_scope_status=self._ledger_trade_count_scope_status,
            ledger_trade_count_last_error=self._ledger_trade_count_last_error,
            ledger_trade_count_last_synced_at=(
                self._ledger_trade_count_last_synced_at.isoformat()
                if self._ledger_trade_count_last_synced_at is not None
                else None
            ),
            trade_count_truth_model=FINAL_BYBIT_TRADE_COUNT_TRUTH_OWNERSHIP.truth_model,
            trade_count_canonical_truth_owner=(
                FINAL_BYBIT_TRADE_COUNT_TRUTH_OWNERSHIP.canonical_trade_truth_owner
            ),
            trade_count_canonical_truth_source=(
                FINAL_BYBIT_TRADE_COUNT_TRUTH_OWNERSHIP.canonical_trade_truth_source
            ),
            trade_count_operational_truth_owner=(
                FINAL_BYBIT_TRADE_COUNT_TRUTH_OWNERSHIP.connector_runtime_truth_owner
            ),
            trade_count_operational_truth_source=(
                FINAL_BYBIT_TRADE_COUNT_TRUTH_OWNERSHIP.connector_runtime_truth_source
            ),
            trade_count_connector_canonical_role=(
                FINAL_BYBIT_TRADE_COUNT_TRUTH_OWNERSHIP.connector_canonical_role
            ),
            trade_count_product_truth_state=trade_count_product_truth_state,
            trade_count_product_truth_reason=trade_count_product_truth_reason,
            trade_count_cutover_readiness_state=cutover_readiness.state,
            trade_count_cutover_readiness_reason=cutover_readiness.reason,
            trade_count_cutover_compared_symbols=cutover_readiness.compared_symbols,
            trade_count_cutover_ready_symbols=cutover_readiness.ready_symbols,
            trade_count_cutover_not_ready_symbols=cutover_readiness.not_ready_symbols,
            trade_count_cutover_blocked_symbols=cutover_readiness.blocked_symbols,
            trade_count_cutover_evaluation_state=cutover_evaluation.state,
            trade_count_cutover_evaluation_reasons=cutover_evaluation.reasons,
            trade_count_cutover_evaluation_minimum_compared_symbols=(
                cutover_evaluation.minimum_compared_symbols
            ),
            trade_count_cutover_manual_review_state=manual_review.state,
            trade_count_cutover_manual_review_reasons=manual_review.reasons,
            trade_count_cutover_manual_review_evaluation_state=manual_review.evaluation_state,
            trade_count_cutover_manual_review_contour=manual_review.contour,
            trade_count_cutover_manual_review_scope_mode=manual_review.scope_mode,
            trade_count_cutover_manual_review_scope_symbol_count=manual_review.scope_symbol_count,
            trade_count_cutover_manual_review_compared_symbols=manual_review.compared_symbols,
            trade_count_cutover_manual_review_ready_symbols=manual_review.ready_symbols,
            trade_count_cutover_manual_review_not_ready_symbols=manual_review.not_ready_symbols,
            trade_count_cutover_manual_review_blocked_symbols=manual_review.blocked_symbols,
            trade_count_cutover_discussion_artifact={
                "discussion_state": cutover_discussion.discussion_state,
                "headline": cutover_discussion.headline,
                "contour": cutover_discussion.contour,
                "scope_mode": cutover_discussion.scope_mode,
                "scope_symbol_count": cutover_discussion.scope_symbol_count,
                "reconciliation_summary": tuple(
                    {"name": item.name, "count": item.count}
                    for item in cutover_discussion.reconciliation_summary
                ),
                "cutover_readiness_state": cutover_discussion.cutover_readiness_state,
                "cutover_readiness_reason": cutover_discussion.cutover_readiness_reason,
                "cutover_evaluation_state": cutover_discussion.cutover_evaluation_state,
                "cutover_evaluation_reasons": cutover_discussion.cutover_evaluation_reasons,
                "manual_review_state": cutover_discussion.manual_review_state,
                "manual_review_reasons": cutover_discussion.manual_review_reasons,
                "compared_symbols": cutover_discussion.compared_symbols,
                "ready_symbols": cutover_discussion.ready_symbols,
                "not_ready_symbols": cutover_discussion.not_ready_symbols,
                "blocked_symbols": cutover_discussion.blocked_symbols,
                "symbol_exceptions": tuple(
                    {
                        "symbol": item.symbol,
                        "reconciliation_verdict": item.reconciliation_verdict,
                        "reconciliation_reason": item.reconciliation_reason,
                        "cutover_readiness_state": item.cutover_readiness_state,
                        "cutover_readiness_reason": item.cutover_readiness_reason,
                    }
                    for item in cutover_discussion.symbol_exceptions
                ),
            },
            trade_count_cutover_review_record={
                "captured_at": cutover_review_record.captured_at,
                "contour": cutover_review_record.contour,
                "scope_mode": cutover_review_record.scope_mode,
                "scope_symbol_count": cutover_review_record.scope_symbol_count,
                "discussion_state": cutover_review_record.discussion_state,
                "manual_review_state": cutover_review_record.manual_review_state,
                "cutover_evaluation_state": cutover_review_record.cutover_evaluation_state,
                "cutover_readiness_state": cutover_review_record.cutover_readiness_state,
                "compared_symbols": cutover_review_record.compared_symbols,
                "ready_symbols": cutover_review_record.ready_symbols,
                "not_ready_symbols": cutover_review_record.not_ready_symbols,
                "blocked_symbols": cutover_review_record.blocked_symbols,
                "headline": cutover_review_record.headline,
                "reasons_summary": cutover_review_record.reasons_summary,
                "symbol_exceptions": cutover_review_record.symbol_exceptions,
            },
            trade_count_cutover_review_package={
                "contour": cutover_review_package.contour,
                "scope_mode": cutover_review_package.scope_mode,
                "scope_symbol_count": cutover_review_package.scope_symbol_count,
                "discussion_state": cutover_review_package.discussion_state,
                "manual_review_state": cutover_review_package.manual_review_state,
                "cutover_evaluation_state": cutover_review_package.cutover_evaluation_state,
                "cutover_readiness_state": cutover_review_package.cutover_readiness_state,
                "compared_symbols": cutover_review_package.compared_symbols,
                "ready_symbols": cutover_review_package.ready_symbols,
                "not_ready_symbols": cutover_review_package.not_ready_symbols,
                "blocked_symbols": cutover_review_package.blocked_symbols,
                "headline": cutover_review_package.headline,
                "reasons_summary": cutover_review_package.reasons_summary,
                "review_record": {
                    "captured_at": cutover_review_package.review_record.captured_at,
                    "contour": cutover_review_package.review_record.contour,
                    "scope_mode": cutover_review_package.review_record.scope_mode,
                    "scope_symbol_count": cutover_review_package.review_record.scope_symbol_count,
                    "discussion_state": cutover_review_package.review_record.discussion_state,
                    "manual_review_state": cutover_review_package.review_record.manual_review_state,
                    "cutover_evaluation_state": (
                        cutover_review_package.review_record.cutover_evaluation_state
                    ),
                    "cutover_readiness_state": (
                        cutover_review_package.review_record.cutover_readiness_state
                    ),
                    "compared_symbols": cutover_review_package.review_record.compared_symbols,
                    "ready_symbols": cutover_review_package.review_record.ready_symbols,
                    "not_ready_symbols": cutover_review_package.review_record.not_ready_symbols,
                    "blocked_symbols": cutover_review_package.review_record.blocked_symbols,
                    "headline": cutover_review_package.review_record.headline,
                    "reasons_summary": cutover_review_package.review_record.reasons_summary,
                    "symbol_exceptions": cutover_review_package.review_record.symbol_exceptions,
                },
                "symbol_exceptions": cutover_review_package.symbol_exceptions,
            },
            trade_count_cutover_review_catalog={
                "contour": cutover_review_catalog.contour,
                "scope_mode": cutover_review_catalog.scope_mode,
                "headline": cutover_review_catalog.headline,
                "discussion_state": cutover_review_catalog.discussion_state,
                "manual_review_state": cutover_review_catalog.manual_review_state,
                "cutover_evaluation_state": cutover_review_catalog.cutover_evaluation_state,
                "cutover_readiness_state": cutover_review_catalog.cutover_readiness_state,
                "compared_symbols": cutover_review_catalog.compared_symbols,
                "ready_symbols": cutover_review_catalog.ready_symbols,
                "not_ready_symbols": cutover_review_catalog.not_ready_symbols,
                "blocked_symbols": cutover_review_catalog.blocked_symbols,
                "reasons_summary": cutover_review_catalog.reasons_summary,
                "current_review_package": {
                    "contour": cutover_review_catalog.current_review_package.contour,
                    "scope_mode": cutover_review_catalog.current_review_package.scope_mode,
                    "scope_symbol_count": (
                        cutover_review_catalog.current_review_package.scope_symbol_count
                    ),
                    "discussion_state": (
                        cutover_review_catalog.current_review_package.discussion_state
                    ),
                    "manual_review_state": (
                        cutover_review_catalog.current_review_package.manual_review_state
                    ),
                    "cutover_evaluation_state": (
                        cutover_review_catalog.current_review_package.cutover_evaluation_state
                    ),
                    "cutover_readiness_state": (
                        cutover_review_catalog.current_review_package.cutover_readiness_state
                    ),
                    "compared_symbols": (
                        cutover_review_catalog.current_review_package.compared_symbols
                    ),
                    "ready_symbols": cutover_review_catalog.current_review_package.ready_symbols,
                    "not_ready_symbols": (
                        cutover_review_catalog.current_review_package.not_ready_symbols
                    ),
                    "blocked_symbols": (
                        cutover_review_catalog.current_review_package.blocked_symbols
                    ),
                    "headline": cutover_review_catalog.current_review_package.headline,
                    "reasons_summary": (
                        cutover_review_catalog.current_review_package.reasons_summary
                    ),
                    "review_record": {
                        "captured_at": (
                            cutover_review_catalog.current_review_package.review_record.captured_at
                        ),
                        "contour": (
                            cutover_review_catalog.current_review_package.review_record.contour
                        ),
                        "scope_mode": (
                            cutover_review_catalog.current_review_package.review_record.scope_mode
                        ),
                        "scope_symbol_count": (
                            cutover_review_catalog.current_review_package.review_record.scope_symbol_count
                        ),
                        "discussion_state": (
                            cutover_review_catalog.current_review_package.review_record.discussion_state
                        ),
                        "manual_review_state": (
                            cutover_review_catalog.current_review_package.review_record.manual_review_state
                        ),
                        "cutover_evaluation_state": (
                            cutover_review_catalog.current_review_package.review_record.cutover_evaluation_state
                        ),
                        "cutover_readiness_state": (
                            cutover_review_catalog.current_review_package.review_record.cutover_readiness_state
                        ),
                        "compared_symbols": (
                            cutover_review_catalog.current_review_package.review_record.compared_symbols
                        ),
                        "ready_symbols": (
                            cutover_review_catalog.current_review_package.review_record.ready_symbols
                        ),
                        "not_ready_symbols": (
                            cutover_review_catalog.current_review_package.review_record.not_ready_symbols
                        ),
                        "blocked_symbols": (
                            cutover_review_catalog.current_review_package.review_record.blocked_symbols
                        ),
                        "headline": (
                            cutover_review_catalog.current_review_package.review_record.headline
                        ),
                        "reasons_summary": (
                            cutover_review_catalog.current_review_package.review_record.reasons_summary
                        ),
                        "symbol_exceptions": (
                            cutover_review_catalog.current_review_package.review_record.symbol_exceptions
                        ),
                    },
                    "symbol_exceptions": (
                        cutover_review_catalog.current_review_package.symbol_exceptions
                    ),
                },
            },
            trade_count_cutover_review_snapshot_collection={
                "contour": cutover_review_snapshot_collection.contour,
                "scope_mode": cutover_review_snapshot_collection.scope_mode,
                "headline": cutover_review_snapshot_collection.headline,
                "discussion_state": cutover_review_snapshot_collection.discussion_state,
                "manual_review_state": cutover_review_snapshot_collection.manual_review_state,
                "cutover_evaluation_state": (
                    cutover_review_snapshot_collection.cutover_evaluation_state
                ),
                "cutover_readiness_state": (
                    cutover_review_snapshot_collection.cutover_readiness_state
                ),
                "compared_symbols": cutover_review_snapshot_collection.compared_symbols,
                "ready_symbols": cutover_review_snapshot_collection.ready_symbols,
                "not_ready_symbols": cutover_review_snapshot_collection.not_ready_symbols,
                "blocked_symbols": cutover_review_snapshot_collection.blocked_symbols,
                "reasons_summary": cutover_review_snapshot_collection.reasons_summary,
                "current_review_package_headline": (
                    cutover_review_snapshot_collection.current_review_package_headline
                ),
                "current_review_package_discussion_state": (
                    cutover_review_snapshot_collection.current_review_package_discussion_state
                ),
                "current_review_catalog": {
                    "contour": cutover_review_snapshot_collection.current_review_catalog.contour,
                    "scope_mode": (
                        cutover_review_snapshot_collection.current_review_catalog.scope_mode
                    ),
                    "headline": cutover_review_snapshot_collection.current_review_catalog.headline,
                    "discussion_state": (
                        cutover_review_snapshot_collection.current_review_catalog.discussion_state
                    ),
                    "manual_review_state": (
                        cutover_review_snapshot_collection.current_review_catalog.manual_review_state
                    ),
                    "cutover_evaluation_state": (
                        cutover_review_snapshot_collection.current_review_catalog.cutover_evaluation_state
                    ),
                    "cutover_readiness_state": (
                        cutover_review_snapshot_collection.current_review_catalog.cutover_readiness_state
                    ),
                    "compared_symbols": (
                        cutover_review_snapshot_collection.current_review_catalog.compared_symbols
                    ),
                    "ready_symbols": (
                        cutover_review_snapshot_collection.current_review_catalog.ready_symbols
                    ),
                    "not_ready_symbols": (
                        cutover_review_snapshot_collection.current_review_catalog.not_ready_symbols
                    ),
                    "blocked_symbols": (
                        cutover_review_snapshot_collection.current_review_catalog.blocked_symbols
                    ),
                    "reasons_summary": (
                        cutover_review_snapshot_collection.current_review_catalog.reasons_summary
                    ),
                    "current_review_package": {
                        "contour": (
                            cutover_review_snapshot_collection.current_review_catalog.current_review_package.contour
                        ),
                        "scope_mode": (
                            cutover_review_snapshot_collection.current_review_catalog.current_review_package.scope_mode
                        ),
                        "scope_symbol_count": (
                            cutover_review_snapshot_collection.current_review_catalog.current_review_package.scope_symbol_count
                        ),
                        "discussion_state": (
                            cutover_review_snapshot_collection.current_review_catalog.current_review_package.discussion_state
                        ),
                        "manual_review_state": (
                            cutover_review_snapshot_collection.current_review_catalog.current_review_package.manual_review_state
                        ),
                        "cutover_evaluation_state": (
                            cutover_review_snapshot_collection.current_review_catalog.current_review_package.cutover_evaluation_state
                        ),
                        "cutover_readiness_state": (
                            cutover_review_snapshot_collection.current_review_catalog.current_review_package.cutover_readiness_state
                        ),
                        "compared_symbols": (
                            cutover_review_snapshot_collection.current_review_catalog.current_review_package.compared_symbols
                        ),
                        "ready_symbols": (
                            cutover_review_snapshot_collection.current_review_catalog.current_review_package.ready_symbols
                        ),
                        "not_ready_symbols": (
                            cutover_review_snapshot_collection.current_review_catalog.current_review_package.not_ready_symbols
                        ),
                        "blocked_symbols": (
                            cutover_review_snapshot_collection.current_review_catalog.current_review_package.blocked_symbols
                        ),
                        "headline": (
                            cutover_review_snapshot_collection.current_review_catalog.current_review_package.headline
                        ),
                        "reasons_summary": (
                            cutover_review_snapshot_collection.current_review_catalog.current_review_package.reasons_summary
                        ),
                        "review_record": {
                            "captured_at": (
                                cutover_review_snapshot_collection.current_review_catalog.current_review_package.review_record.captured_at
                            ),
                            "contour": (
                                cutover_review_snapshot_collection.current_review_catalog.current_review_package.review_record.contour
                            ),
                            "scope_mode": (
                                cutover_review_snapshot_collection.current_review_catalog.current_review_package.review_record.scope_mode
                            ),
                            "scope_symbol_count": (
                                cutover_review_snapshot_collection.current_review_catalog.current_review_package.review_record.scope_symbol_count
                            ),
                            "discussion_state": (
                                cutover_review_snapshot_collection.current_review_catalog.current_review_package.review_record.discussion_state
                            ),
                            "manual_review_state": (
                                cutover_review_snapshot_collection.current_review_catalog.current_review_package.review_record.manual_review_state
                            ),
                            "cutover_evaluation_state": (
                                cutover_review_snapshot_collection.current_review_catalog.current_review_package.review_record.cutover_evaluation_state
                            ),
                            "cutover_readiness_state": (
                                cutover_review_snapshot_collection.current_review_catalog.current_review_package.review_record.cutover_readiness_state
                            ),
                            "compared_symbols": (
                                cutover_review_snapshot_collection.current_review_catalog.current_review_package.review_record.compared_symbols
                            ),
                            "ready_symbols": (
                                cutover_review_snapshot_collection.current_review_catalog.current_review_package.review_record.ready_symbols
                            ),
                            "not_ready_symbols": (
                                cutover_review_snapshot_collection.current_review_catalog.current_review_package.review_record.not_ready_symbols
                            ),
                            "blocked_symbols": (
                                cutover_review_snapshot_collection.current_review_catalog.current_review_package.review_record.blocked_symbols
                            ),
                            "headline": (
                                cutover_review_snapshot_collection.current_review_catalog.current_review_package.review_record.headline
                            ),
                            "reasons_summary": (
                                cutover_review_snapshot_collection.current_review_catalog.current_review_package.review_record.reasons_summary
                            ),
                            "symbol_exceptions": (
                                cutover_review_snapshot_collection.current_review_catalog.current_review_package.review_record.symbol_exceptions
                            ),
                        },
                        "symbol_exceptions": (
                            cutover_review_snapshot_collection.current_review_catalog.current_review_package.symbol_exceptions
                        ),
                    },
                },
            },
            trade_count_cutover_review_compact_digest={
                "contour": cutover_review_compact_digest.contour,
                "scope_mode": cutover_review_compact_digest.scope_mode,
                "headline": cutover_review_compact_digest.headline,
                "discussion_state": cutover_review_compact_digest.discussion_state,
                "manual_review_state": cutover_review_compact_digest.manual_review_state,
                "cutover_evaluation_state": cutover_review_compact_digest.cutover_evaluation_state,
                "cutover_readiness_state": cutover_review_compact_digest.cutover_readiness_state,
                "compared_symbols": cutover_review_compact_digest.compared_symbols,
                "ready_symbols": cutover_review_compact_digest.ready_symbols,
                "not_ready_symbols": cutover_review_compact_digest.not_ready_symbols,
                "blocked_symbols": cutover_review_compact_digest.blocked_symbols,
                "reasons_summary": cutover_review_compact_digest.reasons_summary,
                "compact_symbol_exceptions": cutover_review_compact_digest.compact_symbol_exceptions,
                "current_review_snapshot_collection": {
                    "contour": cutover_review_snapshot_collection.contour,
                    "scope_mode": cutover_review_snapshot_collection.scope_mode,
                    "headline": cutover_review_snapshot_collection.headline,
                    "discussion_state": cutover_review_snapshot_collection.discussion_state,
                    "manual_review_state": cutover_review_snapshot_collection.manual_review_state,
                    "cutover_evaluation_state": cutover_review_snapshot_collection.cutover_evaluation_state,
                    "cutover_readiness_state": cutover_review_snapshot_collection.cutover_readiness_state,
                    "compared_symbols": cutover_review_snapshot_collection.compared_symbols,
                    "ready_symbols": cutover_review_snapshot_collection.ready_symbols,
                    "not_ready_symbols": cutover_review_snapshot_collection.not_ready_symbols,
                    "blocked_symbols": cutover_review_snapshot_collection.blocked_symbols,
                    "reasons_summary": cutover_review_snapshot_collection.reasons_summary,
                    "current_review_package_headline": (
                        cutover_review_snapshot_collection.current_review_package_headline
                    ),
                    "current_review_package_discussion_state": (
                        cutover_review_snapshot_collection.current_review_package_discussion_state
                    ),
                    "current_review_catalog": {
                        "contour": cutover_review_catalog.contour,
                        "scope_mode": cutover_review_catalog.scope_mode,
                        "headline": cutover_review_catalog.headline,
                        "discussion_state": cutover_review_catalog.discussion_state,
                        "manual_review_state": cutover_review_catalog.manual_review_state,
                        "cutover_evaluation_state": cutover_review_catalog.cutover_evaluation_state,
                        "cutover_readiness_state": cutover_review_catalog.cutover_readiness_state,
                        "compared_symbols": cutover_review_catalog.compared_symbols,
                        "ready_symbols": cutover_review_catalog.ready_symbols,
                        "not_ready_symbols": cutover_review_catalog.not_ready_symbols,
                        "blocked_symbols": cutover_review_catalog.blocked_symbols,
                        "reasons_summary": cutover_review_catalog.reasons_summary,
                        "current_review_package": {
                            "contour": cutover_review_package.contour,
                            "scope_mode": cutover_review_package.scope_mode,
                            "scope_symbol_count": cutover_review_package.scope_symbol_count,
                            "discussion_state": cutover_review_package.discussion_state,
                            "manual_review_state": cutover_review_package.manual_review_state,
                            "cutover_evaluation_state": cutover_review_package.cutover_evaluation_state,
                            "cutover_readiness_state": cutover_review_package.cutover_readiness_state,
                            "compared_symbols": cutover_review_package.compared_symbols,
                            "ready_symbols": cutover_review_package.ready_symbols,
                            "not_ready_symbols": cutover_review_package.not_ready_symbols,
                            "blocked_symbols": cutover_review_package.blocked_symbols,
                            "headline": cutover_review_package.headline,
                            "reasons_summary": cutover_review_package.reasons_summary,
                            "review_record": {
                                "captured_at": cutover_review_record.captured_at,
                                "contour": cutover_review_record.contour,
                                "scope_mode": cutover_review_record.scope_mode,
                                "scope_symbol_count": cutover_review_record.scope_symbol_count,
                                "discussion_state": cutover_review_record.discussion_state,
                                "manual_review_state": cutover_review_record.manual_review_state,
                                "cutover_evaluation_state": cutover_review_record.cutover_evaluation_state,
                                "cutover_readiness_state": cutover_review_record.cutover_readiness_state,
                                "compared_symbols": cutover_review_record.compared_symbols,
                                "ready_symbols": cutover_review_record.ready_symbols,
                                "not_ready_symbols": cutover_review_record.not_ready_symbols,
                                "blocked_symbols": cutover_review_record.blocked_symbols,
                                "headline": cutover_review_record.headline,
                                "reasons_summary": cutover_review_record.reasons_summary,
                                "symbol_exceptions": cutover_review_record.symbol_exceptions,
                            },
                            "symbol_exceptions": cutover_review_package.symbol_exceptions,
                        },
                    },
                },
            },
            trade_count_cutover_export_report_bundle={
                "contour": cutover_export_report_bundle.contour,
                "scope_mode": cutover_export_report_bundle.scope_mode,
                "headline": cutover_export_report_bundle.headline,
                "discussion_state": cutover_export_report_bundle.discussion_state,
                "manual_review_state": cutover_export_report_bundle.manual_review_state,
                "cutover_evaluation_state": cutover_export_report_bundle.cutover_evaluation_state,
                "cutover_readiness_state": cutover_export_report_bundle.cutover_readiness_state,
                "compared_symbols": cutover_export_report_bundle.compared_symbols,
                "ready_symbols": cutover_export_report_bundle.ready_symbols,
                "not_ready_symbols": cutover_export_report_bundle.not_ready_symbols,
                "blocked_symbols": cutover_export_report_bundle.blocked_symbols,
                "reasons_summary": cutover_export_report_bundle.reasons_summary,
                "compact_symbol_exceptions": cutover_export_report_bundle.compact_symbol_exceptions,
                "export_text_summary": cutover_export_report_bundle.export_text_summary,
                "current_compact_digest": {
                    "contour": cutover_review_compact_digest.contour,
                    "scope_mode": cutover_review_compact_digest.scope_mode,
                    "headline": cutover_review_compact_digest.headline,
                    "discussion_state": cutover_review_compact_digest.discussion_state,
                    "manual_review_state": cutover_review_compact_digest.manual_review_state,
                    "cutover_evaluation_state": cutover_review_compact_digest.cutover_evaluation_state,
                    "cutover_readiness_state": cutover_review_compact_digest.cutover_readiness_state,
                    "compared_symbols": cutover_review_compact_digest.compared_symbols,
                    "ready_symbols": cutover_review_compact_digest.ready_symbols,
                    "not_ready_symbols": cutover_review_compact_digest.not_ready_symbols,
                    "blocked_symbols": cutover_review_compact_digest.blocked_symbols,
                    "reasons_summary": cutover_review_compact_digest.reasons_summary,
                    "compact_symbol_exceptions": cutover_review_compact_digest.compact_symbol_exceptions,
                    "current_review_snapshot_collection": {
                        "contour": cutover_review_snapshot_collection.contour,
                        "scope_mode": cutover_review_snapshot_collection.scope_mode,
                        "headline": cutover_review_snapshot_collection.headline,
                        "discussion_state": cutover_review_snapshot_collection.discussion_state,
                        "manual_review_state": cutover_review_snapshot_collection.manual_review_state,
                        "cutover_evaluation_state": cutover_review_snapshot_collection.cutover_evaluation_state,
                        "cutover_readiness_state": cutover_review_snapshot_collection.cutover_readiness_state,
                        "compared_symbols": cutover_review_snapshot_collection.compared_symbols,
                        "ready_symbols": cutover_review_snapshot_collection.ready_symbols,
                        "not_ready_symbols": cutover_review_snapshot_collection.not_ready_symbols,
                        "blocked_symbols": cutover_review_snapshot_collection.blocked_symbols,
                        "reasons_summary": cutover_review_snapshot_collection.reasons_summary,
                        "current_review_package_headline": (
                            cutover_review_snapshot_collection.current_review_package_headline
                        ),
                        "current_review_package_discussion_state": (
                            cutover_review_snapshot_collection.current_review_package_discussion_state
                        ),
                        "current_review_catalog": {
                            "contour": cutover_review_catalog.contour,
                            "scope_mode": cutover_review_catalog.scope_mode,
                            "headline": cutover_review_catalog.headline,
                            "discussion_state": cutover_review_catalog.discussion_state,
                            "manual_review_state": cutover_review_catalog.manual_review_state,
                            "cutover_evaluation_state": cutover_review_catalog.cutover_evaluation_state,
                            "cutover_readiness_state": cutover_review_catalog.cutover_readiness_state,
                            "compared_symbols": cutover_review_catalog.compared_symbols,
                            "ready_symbols": cutover_review_catalog.ready_symbols,
                            "not_ready_symbols": cutover_review_catalog.not_ready_symbols,
                            "blocked_symbols": cutover_review_catalog.blocked_symbols,
                            "reasons_summary": cutover_review_catalog.reasons_summary,
                            "current_review_package": {
                                "contour": cutover_review_package.contour,
                                "scope_mode": cutover_review_package.scope_mode,
                                "scope_symbol_count": cutover_review_package.scope_symbol_count,
                                "discussion_state": cutover_review_package.discussion_state,
                                "manual_review_state": cutover_review_package.manual_review_state,
                                "cutover_evaluation_state": cutover_review_package.cutover_evaluation_state,
                                "cutover_readiness_state": cutover_review_package.cutover_readiness_state,
                                "compared_symbols": cutover_review_package.compared_symbols,
                                "ready_symbols": cutover_review_package.ready_symbols,
                                "not_ready_symbols": cutover_review_package.not_ready_symbols,
                                "blocked_symbols": cutover_review_package.blocked_symbols,
                                "headline": cutover_review_package.headline,
                                "reasons_summary": cutover_review_package.reasons_summary,
                                "review_record": {
                                    "captured_at": cutover_review_record.captured_at,
                                    "contour": cutover_review_record.contour,
                                    "scope_mode": cutover_review_record.scope_mode,
                                    "scope_symbol_count": cutover_review_record.scope_symbol_count,
                                    "discussion_state": cutover_review_record.discussion_state,
                                    "manual_review_state": cutover_review_record.manual_review_state,
                                    "cutover_evaluation_state": cutover_review_record.cutover_evaluation_state,
                                    "cutover_readiness_state": cutover_review_record.cutover_readiness_state,
                                    "compared_symbols": cutover_review_record.compared_symbols,
                                    "ready_symbols": cutover_review_record.ready_symbols,
                                    "not_ready_symbols": cutover_review_record.not_ready_symbols,
                                    "blocked_symbols": cutover_review_record.blocked_symbols,
                                    "headline": cutover_review_record.headline,
                                    "reasons_summary": cutover_review_record.reasons_summary,
                                    "symbol_exceptions": cutover_review_record.symbol_exceptions,
                                },
                                "symbol_exceptions": cutover_review_package.symbol_exceptions,
                            },
                        },
                    },
                },
            },
            historical_recovery_state=recovery_coordinator.state,
            historical_recovery_reason=recovery_coordinator.reason,
            historical_recovery_retry_pending=recovery_coordinator.retry_pending,
            historical_recovery_backfill_task_active=recovery_coordinator.backfill_task_active,
            historical_recovery_retry_task_active=recovery_coordinator.retry_task_active,
            historical_recovery_cutoff_at=recovery_coordinator.cutoff_at,
            archive_cache_enabled=(
                cache_diagnostics.cache_enabled if cache_diagnostics is not None else False
            ),
            archive_cache_memory_hits=(
                cache_diagnostics.memory_hits if cache_diagnostics is not None else 0
            ),
            archive_cache_disk_hits=(
                cache_diagnostics.disk_hits if cache_diagnostics is not None else 0
            ),
            archive_cache_misses=(
                cache_diagnostics.misses if cache_diagnostics is not None else 0
            ),
            archive_cache_writes=(
                cache_diagnostics.writes if cache_diagnostics is not None else 0
            ),
            archive_cache_last_hit_source=(
                cache_diagnostics.last_hit_source if cache_diagnostics is not None else None
            ),
            archive_cache_last_url=(
                cache_diagnostics.last_archive_url if cache_diagnostics is not None else None
            ),
            archive_cache_last_cleanup_at=(
                cache_diagnostics.last_cleanup_at if cache_diagnostics is not None else None
            ),
            archive_cache_last_pruned_files=(
                cache_diagnostics.last_pruned_files if cache_diagnostics is not None else 0
            ),
            archive_cache_last_network_fetch_ms=(
                cache_diagnostics.last_network_fetch_ms if cache_diagnostics is not None else None
            ),
            archive_cache_last_disk_read_ms=(
                cache_diagnostics.last_disk_read_ms if cache_diagnostics is not None else None
            ),
            archive_cache_last_gzip_decode_ms=(
                cache_diagnostics.last_gzip_decode_ms if cache_diagnostics is not None else None
            ),
            archive_cache_last_csv_parse_ms=(
                cache_diagnostics.last_csv_parse_ms if cache_diagnostics is not None else None
            ),
            archive_cache_last_archive_total_ms=(
                cache_diagnostics.last_archive_total_ms if cache_diagnostics is not None else None
            ),
            archive_cache_last_symbol_total_ms=(
                cache_diagnostics.last_symbol_total_ms if cache_diagnostics is not None else None
            ),
            archive_cache_last_symbol=(
                cache_diagnostics.last_symbol if cache_diagnostics is not None else None
            ),
            archive_cache_total_network_fetch_ms=(
                cache_diagnostics.total_network_fetch_ms if cache_diagnostics is not None else 0
            ),
            archive_cache_total_disk_read_ms=(
                cache_diagnostics.total_disk_read_ms if cache_diagnostics is not None else 0
            ),
            archive_cache_total_gzip_decode_ms=(
                cache_diagnostics.total_gzip_decode_ms if cache_diagnostics is not None else 0
            ),
            archive_cache_total_csv_parse_ms=(
                cache_diagnostics.total_csv_parse_ms if cache_diagnostics is not None else 0
            ),
            archive_cache_total_archive_total_ms=(
                cache_diagnostics.total_archive_total_ms if cache_diagnostics is not None else 0
            ),
            archive_cache_total_symbol_total_ms=(
                cache_diagnostics.total_symbol_total_ms if cache_diagnostics is not None else 0
            ),
        )

    def _resolve_operational_recovery_surface(
        self,
        *,
        readiness_state: str | None,
    ) -> tuple[str, str | None]:
        if not self._trade_count_admission_enabled:
            return "not_applicable", None
        if readiness_state == "ready":
            return "ready_for_operation", "Operational recovery truth is ready."
        if readiness_state == "waiting_for_live_tail":
            return "waiting_for_live_tail", "Historical recovery is restored; waiting for live tail."
        return "recovering", "Operational recovery truth is still warming up."

    def _resolve_canonical_ledger_sync_surface(
        self,
        *,
        backfill_status: str | None,
    ) -> tuple[str, str | None]:
        if not self._trade_count_admission_enabled:
            return "not_applicable", None
        if self._ledger_repository is None or self._ledger_trade_count_scope_status == "not_configured":
            return "not_configured", "Canonical ledger sync is not configured."
        if (
            self._post_recovery_materialization_status in {"scheduled", "running"}
            or self._pending_post_recovery_materialization_request is not None
        ):
            return (
                "ledger_sync_in_progress",
                "Background canonical ledger synchronization is still running.",
            )
        if backfill_status in {"pending", "running"}:
            return (
                "ledger_sync_pending",
                "Canonical ledger synchronization is pending the current recovery/materialization cycle.",
            )
        if (
            backfill_status == "backfilled"
            and self._post_recovery_materialization_status != "completed"
        ):
            return (
                "ledger_sync_pending",
                "Canonical ledger synchronization is pending the current recovery/materialization cycle.",
            )
        if self._post_recovery_materialization_status == "completed":
            return "ledger_sync_completed", "Canonical ledger synchronization is up to date."
        if self._post_recovery_materialization_status in {"failed", "cancelled"}:
            return (
                "ledger_sync_failed",
                self._post_recovery_materialization_last_error
                or "Background canonical ledger synchronization did not complete.",
            )
        return "ledger_sync_idle", None

    def build_admission_snapshot(
        self,
        *,
        diagnostics: BybitDerivedTradeCountDiagnostics | None = None,
        observed_at: datetime | None = None,
    ) -> BybitAdmissionSnapshot:
        trade_count_diagnostics = diagnostics or self._derived_trade_count.get_diagnostics(
            observed_at=observed_at or _utcnow()
        )
        return self._build_admission_snapshot(
            diagnostics=trade_count_diagnostics,
        )

    def _build_admission_trade_truth_input(
        self,
        diagnostics: BybitDerivedTradeCountDiagnostics,
    ) -> BybitAdmissionTradeTruthInput:
        return BybitAdmissionTradeTruthInput(
            derived_trade_count_ready=diagnostics.ready,
            derived_trade_count_state=diagnostics.state,
            symbol_trade_count_24h=tuple(
                (snapshot.symbol, snapshot.trade_count_24h)
                for snapshot in diagnostics.symbol_snapshots
            ),
        )

    def _build_admission_snapshot(
        self,
        *,
        diagnostics: BybitDerivedTradeCountDiagnostics,
    ) -> BybitAdmissionSnapshot:
        return self._admission_engine.build_snapshot(
            discovery=self.build_discovery_snapshot(),
            trade_truth=self._build_admission_trade_truth_input(diagnostics),
            applied_subscription_symbols=self._active_symbols,
            trade_count_filter_minimum=self._universe_min_trade_count_24h,
            admission_enabled=self._trade_count_admission_enabled,
        )

    def _refresh_admission_scope_state(
        self,
        *,
        diagnostics: BybitDerivedTradeCountDiagnostics,
    ) -> BybitAdmissionSnapshot:
        snapshot = self._build_admission_snapshot(diagnostics=diagnostics)
        self._set_admission_scope_state(snapshot)
        return snapshot

    def build_projection_snapshot(
        self,
        *,
        compact_cutover_payload: bool = False,
    ) -> BybitProjectionSnapshot:
        symbols = self._active_symbols
        observed_at = _utcnow()
        trade_count_diagnostics = self._derived_trade_count.get_diagnostics(observed_at=observed_at)
        use_compact_cutover_payload = compact_cutover_payload or self._ledger_contour() == "spot"
        trade_truth_snapshot = self.build_trade_truth_snapshot(
            compact_cutover_payload=use_compact_cutover_payload,
            diagnostics=trade_count_diagnostics,
            observed_at=observed_at,
        )
        admission_snapshot = self.build_admission_snapshot(
            diagnostics=trade_count_diagnostics,
            observed_at=observed_at,
        )
        return BybitProjectionSnapshot(
            exchange=self.session.exchange,
            enabled=True,
            primary_symbol=symbols[0] if symbols else None,
            symbols=symbols,
            discovery=self.build_discovery_snapshot(),
            transport=self.build_transport_snapshot(),
            trade_truth=trade_truth_snapshot,
            admission=admission_snapshot,
            extras={
                "operator_state_surface": {
                    "runtime": {
                        "state": trade_truth_snapshot.operational_recovery_state,
                        "reason": trade_truth_snapshot.operational_recovery_reason,
                    },
                    "ledger_sync": {
                        "state": trade_truth_snapshot.canonical_ledger_sync_state,
                        "reason": trade_truth_snapshot.canonical_ledger_sync_reason,
                    },
                },
                "post_recovery_materialization_status": self._post_recovery_materialization_status,
                "post_recovery_materialization_task_active": (
                    self._post_recovery_materialization_task is not None
                ),
                "post_recovery_materialization_last_error": (
                    self._post_recovery_materialization_last_error
                ),
            },
        )

    def get_operator_diagnostics(self) -> dict[str, object]:
        """Вернуть operator-facing snapshot narrow Bybit connector truth."""
        return self.build_projection_snapshot().to_operator_diagnostics_dict()

    def _build_symbol_diagnostics(
        self,
        *,
        symbol: str,
        derived_trade_count_snapshot: BybitDerivedTradeCountSymbolSnapshot | None,
        derived_trade_count_diagnostics: BybitDerivedTradeCountDiagnostics,
    ) -> dict[str, object]:
        orderbook = self.market_data_runtime.orderbook_manager.get_snapshot(
            symbol,
            self.session.exchange,
        )
        symbol_metrics = self.market_data_runtime.state.metrics_by_identity.get(
            build_symbol_identity(symbol, self.session.exchange)
        )
        trade_seen = (
            self.market_data_runtime.state.last_trade_at.get((symbol, self.session.exchange))
            is not None
        )
        bucket_trade_count_24h = (
            derived_trade_count_snapshot.trade_count_24h
            if derived_trade_count_snapshot is not None
            else None
        )
        ledger_snapshot = self._ledger_trade_count_snapshot_by_symbol.get(
            symbol,
            BybitLedgerTradeCountSymbolSnapshot(
                trade_count_24h=None,
                status=(
                    "missing"
                    if self._ledger_trade_count_query_service is not None
                    else "not_configured"
                ),
                last_error=self._ledger_trade_count_last_error,
                last_synced_at=self._ledger_trade_count_last_synced_at,
            ),
        )
        ledger_trade_count_24h = ledger_snapshot.trade_count_24h
        ledger_trade_count_available = ledger_snapshot.status in {"fresh", "stale", "missing"}
        comparison_derived_snapshot = derived_trade_count_snapshot
        if (
            ledger_snapshot.last_synced_at is not None
            and derived_trade_count_snapshot is not None
        ):
            comparison_derived_snapshot = self._derived_trade_count.get_symbol_snapshot(
                symbol=symbol,
                observed_at=ledger_snapshot.last_synced_at,
            )
        local_ledger_bootstrapped = (
            derived_trade_count_diagnostics.last_backfill_source == "bybit_trade_ledger_local_bootstrap"
        )
        historical_coverage_gap = (
            self._trade_truth_store.has_restored_historical_window
            and derived_trade_count_diagnostics.ready
            and not local_ledger_bootstrapped
            and ledger_snapshot.window_started_at is not None
            and ledger_snapshot.first_trade_at is not None
            and ledger_snapshot.sources == ("live_public_trade",)
            and ledger_snapshot.first_trade_at
            > ledger_snapshot.window_started_at + timedelta(minutes=5)
        )
        ledger_window_completeness_proven = (
            ledger_snapshot.window_started_at is not None
            and ledger_snapshot.first_trade_at is not None
            and ledger_snapshot.first_trade_at
            <= ledger_snapshot.window_started_at + timedelta(minutes=5)
        )
        reconciliation = reconcile_trade_count_truths(
            bucket_trade_count_24h=(
                comparison_derived_snapshot.trade_count_24h
                if comparison_derived_snapshot is not None
                else None
            ),
            ledger_trade_count_24h=ledger_trade_count_24h,
            ledger_trade_count_available=ledger_trade_count_available,
            ledger_trade_count_reason=ledger_snapshot.last_error,
            ledger_trade_count_stale=ledger_snapshot.status == "stale",
            ledger_historical_coverage_gap=historical_coverage_gap,
            ledger_window_completeness_proven=ledger_window_completeness_proven,
            policy=self._trade_count_reconciliation_policy,
        )
        product_truth = resolve_product_trade_count_truth(reconciliation=reconciliation)
        symbol_diagnostics = {
            "symbol": symbol,
            "trade_seen": trade_seen,
            "orderbook_seen": orderbook is not None,
            "trade_ingest_seen": trade_seen,
            "orderbook_ingest_seen": orderbook is not None,
            "best_bid": str(orderbook.bids[0].price) if orderbook and orderbook.bids else None,
            "best_ask": str(orderbook.asks[0].price) if orderbook and orderbook.asks else None,
            "volume_24h_usd": (
                str(self._quote_turnover_24h_by_symbol[symbol])
                if symbol in self._quote_turnover_24h_by_symbol
                else str(symbol_metrics.volume_24h_usd)
                if symbol_metrics is not None and symbol_metrics.volume_24h_usd is not None
                else None
            ),
            "derived_trade_count_24h": (
                comparison_derived_snapshot.trade_count_24h
                if comparison_derived_snapshot is not None
                else None
            ),
            "bucket_trade_count_24h": (
                comparison_derived_snapshot.trade_count_24h
                if comparison_derived_snapshot is not None
                else None
            ),
            "ledger_trade_count_24h": ledger_trade_count_24h,
            "ledger_trade_count_status": ledger_snapshot.status,
            "ledger_trade_count_symbol_last_error": ledger_snapshot.last_error,
            "ledger_trade_count_symbol_last_synced_at": (
                ledger_snapshot.last_synced_at.isoformat()
                if ledger_snapshot.last_synced_at is not None
                else None
            ),
            "trade_count_reconciliation_verdict": reconciliation.verdict,
            "trade_count_reconciliation_reason": reconciliation.reason,
            "trade_count_reconciliation_absolute_diff": reconciliation.absolute_diff,
            "trade_count_reconciliation_tolerance": reconciliation.tolerance,
            "trade_count_cutover_readiness_state": readiness_from_reconciliation_result(
                reconciliation
            ).state,
            "trade_count_cutover_readiness_reason": readiness_from_reconciliation_result(
                reconciliation
            ).reason,
            "observed_trade_count_since_reset": (
                derived_trade_count_snapshot.observed_trade_count_since_reset
                if derived_trade_count_snapshot is not None
                else 0
            ),
            "product_trade_count_24h": product_truth.trade_count_24h,
            "product_trade_count_state": product_truth.state,
            "product_trade_count_reason": product_truth.reason,
            "product_trade_count_truth_owner": product_truth.truth_owner,
            "product_trade_count_truth_source": product_truth.truth_source,
        }
        symbol_diagnostics["_trade_count_reconciliation_result"] = reconciliation
        return symbol_diagnostics

    def _market_contour(self) -> str:
        return "spot" if self.session.exchange == "bybit_spot" else "linear"

    async def _refresh_quote_turnover_loop(self) -> None:
        try:
            while not self._stop_requested:
                await self._refresh_quote_turnover_snapshot()
                await self._sleep_func(_DEFAULT_TURNOVER_REFRESH_INTERVAL_SECONDS)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning(
                "Bybit quote turnover refresh loop stopped unexpectedly",
                exchange=self.session.exchange,
                exc_info=True,
            )

    async def _refresh_quote_turnover_snapshot(self) -> None:
        symbols = tuple(self._active_symbols)
        if not symbols:
            self._quote_turnover_24h_by_symbol = {}
            self._quote_turnover_last_synced_at = _utcnow()
            self._quote_turnover_last_error = None
            return
        try:
            fetched = await asyncio.to_thread(
                fetch_bybit_quote_turnover_24h_by_symbol,
                contour=self._market_contour(),
                rest_base_url=self._rest_base_url,
                symbols=symbols,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._quote_turnover_last_error = str(exc)
            logger.warning(
                "Bybit quote turnover refresh failed",
                exchange=self.session.exchange,
                contour=self._market_contour(),
                exc_info=True,
            )
            return
        self._quote_turnover_24h_by_symbol = fetched
        self._quote_turnover_last_synced_at = _utcnow()
        self._quote_turnover_last_error = None

    def _handle_control_message(self, message: dict[str, Any]) -> None:
        op = str(message.get("op", "")).strip().lower()
        if _is_bybit_application_pong_message(message):
            observed_at = _utcnow()
            self._last_pong_at = observed_at
            if (
                self._application_pong_waiter is not None
                and not self._application_pong_waiter.done()
            ):
                self._application_pong_waiter.set_result(observed_at)
            return
        if op != "subscribe":
            return
        observed_at = _utcnow()
        if bool(message.get("success", False)):
            self._mark_subscription_alive(observed_at=observed_at)
            return
        self._recovery_state = FeedSubscriptionRecoveryState(
            session=self.session,
            status=FeedSubscriptionRecoveryStatus.RECOVERY_BLOCKED,
            observed_at=observed_at,
            recovery_required_at=self._recovery_state.recovery_required_at or observed_at,
            last_recovery_reason="subscribe_failed",
            reset_required=True,
            metadata={"subscription_registry": self.subscription_registry.topics},
        )

    def _mark_recovery_required(self, *, reason: str, observed_at: datetime) -> None:
        self._recovery_state = FeedSubscriptionRecoveryState(
            session=self._active_recovery_session(),
            status=FeedSubscriptionRecoveryStatus.RECOVERY_REQUIRED,
            observed_at=observed_at,
            recovery_required_at=observed_at,
            last_recovery_reason=reason,
            reset_required=True,
            metadata={
                "subscription_registry": self.subscription_registry.topics,
                "awaiting_snapshot_symbols": self.parser.awaiting_snapshot_symbols(),
            },
        )

    def _mark_resubscribing(self, *, reason: str, observed_at: datetime) -> FeedResubscribeRequest:
        request = FeedResubscribeRequest(
            session=self._active_recovery_session(),
            requested_at=observed_at,
            recovery_reason=reason,
            subscription_scope=self._active_symbols,
        )
        self._recovery_state = FeedSubscriptionRecoveryState(
            session=request.session,
            status=FeedSubscriptionRecoveryStatus.RESUBSCRIBING,
            observed_at=observed_at,
            recovery_required_at=self._recovery_state.recovery_required_at or observed_at,
            last_recovery_reason=reason,
            reset_required=True,
            metadata={"subscription_registry": request.subscription_scope},
        )
        return request

    def _mark_subscription_alive(self, *, observed_at: datetime) -> None:
        self._recovery_state = FeedSubscriptionRecoveryState(
            session=self._active_recovery_session(),
            status=FeedSubscriptionRecoveryStatus.RESUBSCRIBING,
            observed_at=observed_at,
            recovery_required_at=self._recovery_state.recovery_required_at or observed_at,
            last_resubscribe_at=observed_at,
            last_recovery_reason=self._recovery_state.last_recovery_reason,
            reset_required=True,
            metadata={
                "subscription_registry": self.subscription_registry.topics,
                "subscription_alive": True,
                "awaiting_snapshot_symbols": self.parser.awaiting_snapshot_symbols(),
            },
        )

    def _mark_recovered(self, *, observed_at: datetime) -> None:
        self._derived_trade_count.mark_observation_started(observed_at=observed_at)
        self._recovery_state = FeedSubscriptionRecoveryState(
            session=self._active_recovery_session(),
            status=FeedSubscriptionRecoveryStatus.RECOVERED,
            observed_at=observed_at,
            recovery_required_at=self._recovery_state.recovery_required_at,
            last_resubscribe_at=observed_at,
            last_recovery_reason=self._recovery_state.last_recovery_reason,
            reset_required=bool(self.parser.awaiting_snapshot_symbols()),
            metadata={
                "subscription_registry": self.subscription_registry.topics,
                "subscription_alive": True,
                "awaiting_snapshot_symbols": self.parser.awaiting_snapshot_symbols(),
            },
        )

    def _active_recovery_session(self) -> FeedSessionIdentity:
        if not self._active_symbols or self._active_symbols == self.session.subscription_scope:
            return self.session
        return replace(self.session, subscription_scope=self._active_symbols)

    def _restore_derived_trade_count_state(self) -> None:
        self._trade_truth_store.restore_persisted_state(restored_at=_utcnow())

    def _get_historical_recovery_coordinator_snapshot(
        self,
    ) -> BybitHistoricalRecoveryCoordinatorSnapshot:
        return self._historical_restore_coordinator.snapshot(
            admission_enabled=self._trade_count_admission_enabled,
            has_restored_historical_window=self._trade_truth_store.has_restored_historical_window,
        )

    async def _maybe_restore_historical_trade_count(self) -> None:
        execution = await self._historical_restore_coordinator.load_pending_restore(
            symbols=self._coarse_candidate_symbols,
            update_progress=self._update_historical_backfill_progress,
            now_func=_utcnow,
        )
        if execution is None:
            return
        observed_at = execution.observed_at
        result = execution.result
        recovery_decision = execution.decision
        if result.status != "backfilled":
            if result.status == "skipped" and recovery_decision.apply_restore:
                self._trade_truth_store.apply_historical_restore_result(
                    result=result,
                    observed_at=observed_at,
                    status="skipped",
                )
                self._persist_derived_trade_count(observed_at=observed_at, force=True)
                await self._refresh_ledger_trade_count_snapshot(
                    symbols=self._coarse_candidate_symbols,
                    observed_at=observed_at,
                )
            elif recovery_decision.mark_skipped and result.reason is not None:
                self._trade_truth_store.mark_backfill_skipped(
                    observed_at=observed_at,
                    reason=result.reason,
                    source=result.source,
                    processed_archives=result.processed_archives,
                    total_archives=result.total_archives,
                )
            elif recovery_decision.mark_unavailable and result.reason is not None:
                self._trade_truth_store.mark_backfill_unavailable(
                    observed_at=observed_at,
                    reason=result.reason,
                    source=result.source,
                    processed_archives=result.processed_archives,
                    total_archives=result.total_archives,
                )
            if recovery_decision.schedule_retry:
                self._schedule_latest_archive_backfill_retry()
            return
        if result.restored_window_started_at is None or result.covered_until_at is None:
            return
        result = await self._augment_restore_result_with_ledger_tail(
            result=result,
            observed_at=observed_at,
        )
        self._trade_truth_store.apply_historical_restore_result(
            result=result,
            observed_at=observed_at,
        )
        self._persist_derived_trade_count(observed_at=observed_at, force=True)
        await self._maybe_apply_post_readiness_narrowing()
        self._schedule_post_recovery_materialization(
            result=result,
            plan=execution.plan,
            observed_at=observed_at,
        )

    def _schedule_post_recovery_materialization(
        self,
        *,
        result: BybitHistoricalTradeBackfillResult,
        plan: BybitHistoricalRecoveryPlan,
        observed_at: datetime,
    ) -> None:
        if self._post_recovery_materialization_task is not None:
            self._pending_post_recovery_materialization_request = (
                result,
                plan,
                observed_at,
            )
            return
        self._pending_post_recovery_materialization_request = None
        self._post_recovery_materialization_status = "scheduled"
        self._post_recovery_materialization_last_error = None
        self._post_recovery_materialization_task = asyncio.create_task(
            self._run_post_recovery_materialization_stage(
                result=result,
                plan=plan,
                observed_at=observed_at,
            ),
            name=f"{self.session.exchange}_post_recovery_materialization",
        )

    async def _run_post_recovery_materialization_stage(
        self,
        *,
        result: BybitHistoricalTradeBackfillResult,
        plan: BybitHistoricalRecoveryPlan,
        observed_at: datetime,
    ) -> None:
        current_task = asyncio.current_task()
        refresh_symbols = tuple(result.hydrated_symbols)
        self._post_recovery_materialization_status = "running"
        self._post_recovery_materialization_last_error = None
        try:
            await self._materialize_archive_trade_facts_to_ledger(
                result=result,
                plan=plan,
            )
            await self._refresh_ledger_trade_count_snapshot(
                symbols=refresh_symbols,
                observed_at=observed_at,
            )
            self._post_recovery_materialization_status = "completed"
        except asyncio.CancelledError:
            self._post_recovery_materialization_status = "cancelled"
            raise
        except Exception as exc:
            self._post_recovery_materialization_status = "failed"
            self._post_recovery_materialization_last_error = str(exc)
            logger.warning(
                "Bybit post-recovery materialization stage failed",
                exchange=self.session.exchange,
                exc_info=True,
            )
        finally:
            if self._post_recovery_materialization_task is current_task:
                self._post_recovery_materialization_task = None
            pending_request = self._pending_post_recovery_materialization_request
            if pending_request is not None and not self._stop_requested:
                self._pending_post_recovery_materialization_request = None
                pending_result, pending_plan, pending_observed_at = pending_request
                self._schedule_post_recovery_materialization(
                    result=pending_result,
                    plan=pending_plan,
                    observed_at=pending_observed_at,
                )

    async def _refresh_ledger_trade_count_snapshot(
        self,
        *,
        symbols: tuple[str, ...],
        observed_at: datetime,
    ) -> None:
        await self._trade_truth_store.refresh_ledger_trade_count_snapshot(
            symbols=symbols,
            observed_at=observed_at,
            exchange=self._ledger_exchange_id(),
            contour=self._ledger_contour(),
        )

    def _ledger_exchange_id(self) -> str:
        return "bybit"

    def _ledger_contour(self) -> str:
        return "spot" if self.session.exchange == "bybit_spot" else "linear"

    def _operator_scope_mode(self) -> str:
        if not self._universe_scope_mode and len(self._active_symbols) <= 1:
            return "single_symbol"
        return "universe"

    def _admission_candidate_symbols(self) -> tuple[str, ...]:
        if self._trade_count_admission_enabled:
            return self._candidate_symbols
        return self._active_symbols

    def _build_subscription_registry(
        self,
        *,
        orderbook_symbols: tuple[str, ...],
    ) -> BybitSubscriptionRegistry:
        if self._trade_count_admission_enabled:
            if not orderbook_symbols:
                return BybitSubscriptionRegistry(orderbook_depth=self.config.orderbook_depth)
            return BybitSubscriptionRegistry(
                trade_symbols=self._candidate_symbols,
                orderbook_symbols=orderbook_symbols,
                orderbook_depth=self.config.orderbook_depth,
            )
        return BybitSubscriptionRegistry(
            symbols=orderbook_symbols,
            orderbook_depth=self.config.orderbook_depth,
        )

    def _qualifying_symbols_from_trade_count_diagnostics(
        self,
        diagnostics: BybitDerivedTradeCountDiagnostics,
    ) -> tuple[str, ...]:
        return tuple(
            snapshot.symbol
            for snapshot in diagnostics.symbol_snapshots
            if snapshot.trade_count_24h is not None
            and snapshot.trade_count_24h >= self._universe_min_trade_count_24h
        )

    def _sync_ledger_trade_count_compatibility_view(self) -> None:
        self._trade_truth_store._sync_ledger_trade_count_compatibility_view()

    def _schedule_historical_trade_count_backfill(self) -> None:
        self._historical_restore_coordinator.schedule_backfill(
            symbols=self._coarse_candidate_symbols,
            observed_at=_utcnow(),
            mark_backfill_pending=lambda total_archives: self._trade_truth_store.mark_backfill_pending(
                total_archives=total_archives
            ),
            run_callback=self._run_historical_trade_count_backfill,
        )

    async def _run_historical_trade_count_backfill(self) -> None:
        await self._maybe_restore_historical_trade_count()

    def _schedule_latest_archive_backfill_retry(self) -> None:
        self._historical_restore_coordinator.schedule_retry_if_needed(
            stop_requested=lambda: self._stop_requested,
            trigger_backfill=self._schedule_historical_trade_count_backfill,
        )

    def _update_historical_backfill_progress(
        self,
        processed_archives: int,
        total_archives: int,
    ) -> None:
        self._trade_truth_store.mark_backfill_running(
            processed_archives=processed_archives,
            total_archives=total_archives,
        )

    def _persist_derived_trade_count(
        self,
        *,
        observed_at: datetime | None = None,
        force: bool = False,
    ) -> None:
        if not self._trade_count_admission_enabled:
            return
        self._trade_truth_store.persist(
            observed_at=(observed_at or _utcnow()),
            force=force,
        )

    async def _bootstrap_trade_truth_from_local_ledger(self) -> None:
        if not self._trade_count_admission_enabled:
            return
        bootstrapped = await self._trade_truth_store.bootstrap_from_local_ledger(
            observed_at=_utcnow(),
            exchange=self._ledger_exchange_id(),
            contour=self._ledger_contour(),
        )
        if not bootstrapped:
            return
        if self._bootstrapped_local_ledger_requires_historical_backfill():
            self._mark_historical_backfill_pending_after_incomplete_ledger_bootstrap()
        else:
            self._historical_restore_coordinator.pending = False
            self._historical_restore_coordinator.latest_retry_pending = False
            self._trade_truth_store.mark_backfill_not_needed()
        self._persist_derived_trade_count(observed_at=_utcnow(), force=True)

    def _bootstrapped_local_ledger_requires_historical_backfill(self) -> bool:
        if (
            not self._trade_count_admission_enabled
            or self._historical_trade_backfill_service is None
        ):
            return False
        for symbol in self._coarse_candidate_symbols:
            snapshot = self._ledger_trade_count_snapshot_by_symbol.get(symbol)
            if snapshot is None:
                return True
            if snapshot.window_started_at is None or snapshot.first_trade_at is None:
                return True
            if snapshot.first_trade_at > snapshot.window_started_at + timedelta(minutes=5):
                return True
        return False

    def _mark_historical_backfill_pending_after_incomplete_ledger_bootstrap(self) -> None:
        if (
            not self._trade_count_admission_enabled
            or self._historical_trade_backfill_service is None
        ):
            return
        now = _utcnow()
        recovery_plan = self._historical_trade_backfill_service.build_recovery_plan(
            symbols=self._coarse_candidate_symbols,
            observed_at=now,
            covered_until_at=now,
        )
        self._historical_restore_coordinator.pending = True
        self._historical_restore_coordinator.latest_retry_pending = False
        self._trade_truth_store.mark_backfill_pending(total_archives=recovery_plan.total_archives)

    async def _maybe_apply_post_readiness_narrowing(self) -> None:
        if not self._universe_scope_mode:
            return
        if self._universe_min_trade_count_24h <= 0:
            return
        trade_count_diagnostics = self._derived_trade_count.get_diagnostics(observed_at=_utcnow())
        admission_snapshot = self._refresh_admission_scope_state(
            diagnostics=trade_count_diagnostics,
        )
        if admission_snapshot.readiness_state != "ready":
            return
        if admission_snapshot.selected_symbols == self._active_symbols:
            self._post_readiness_narrowing_applied = (
                self._active_symbols != self._coarse_candidate_symbols
            )
            return
        apply_result = await self._apply_post_readiness_narrowing(
            desired_symbols=admission_snapshot.selected_symbols,
        )
        if apply_result.status == "applied":
            self._post_readiness_narrowing_applied = (
                admission_snapshot.selected_symbols != self._coarse_candidate_symbols
            )

    async def _apply_post_readiness_narrowing(
        self,
        *,
        desired_symbols: tuple[str, ...],
        apply_reason: str = "post_readiness_narrowing",
    ) -> BybitScopeApplyResult:
        websocket = self._active_websocket
        previous_registry = self.subscription_registry
        observed_at = _utcnow()
        self._pending_scope_apply_symbols = desired_symbols
        try:
            apply_result = await self._scope_applier.apply_desired_scope(
                websocket=websocket,
                previous_registry=previous_registry,
                desired_symbols=desired_symbols,
                applied_symbols=self._active_symbols,
                apply_reason=apply_reason,
                build_subscription_registry=self._scope_applier_build_subscription_registry,
                clear_symbol_runtime_state=self._scope_applier_clear_symbol_runtime_state,
                invalidate_orderbook_state=self._scope_applier_invalidate_orderbook_state,
                mark_resubscribing=self._scope_applier_mark_resubscribing,
                mark_recovered=self._scope_applier_mark_recovered,
                observed_at=observed_at,
            )
        finally:
            self._pending_scope_apply_symbols = None
        if apply_result.status == "applied":
            self._selected_scope_symbols = apply_result.desired_symbols
            self._active_symbols = apply_result.applied_symbols
            self.subscription_registry = self._build_subscription_registry(
                orderbook_symbols=apply_result.applied_symbols,
            )
        return apply_result

    def _restore_active_scope_to_coarse_candidates(self) -> None:
        if self._active_symbols == self._coarse_candidate_symbols:
            self._selected_scope_symbols = self._candidate_symbols
            return
        self._selected_scope_symbols = self._candidate_symbols
        self._active_symbols = self._coarse_candidate_symbols
        self.subscription_registry = self._build_subscription_registry(
            orderbook_symbols=self._coarse_candidate_symbols,
        )

    def _scope_applier_build_subscription_registry(
        self,
        desired_symbols: tuple[str, ...],
    ) -> BybitSubscriptionRegistry:
        return self._build_subscription_registry(orderbook_symbols=desired_symbols)

    async def _scope_applier_clear_symbol_runtime_state(
        self,
        symbol: str,
        reason: str,
        observed_at: datetime,
    ) -> None:
        await self.market_data_runtime.clear_symbol_runtime_state(
            symbol=symbol,
            exchange=self.session.exchange,
            reason=reason,
            detected_at=observed_at,
        )

    def _scope_applier_invalidate_orderbook_state(
        self,
        desired_symbols: tuple[str, ...],
    ) -> None:
        self.parser.invalidate_orderbook_state(symbols=desired_symbols)

    def _scope_applier_mark_resubscribing(
        self,
        reason: str,
        observed_at: datetime,
    ) -> None:
        desired_symbols = self._pending_scope_apply_symbols
        if desired_symbols is None:
            self._mark_resubscribing(reason=reason, observed_at=observed_at)
            return
        previous_active_symbols = self._active_symbols
        previous_registry = self.subscription_registry
        self._active_symbols = desired_symbols
        self.subscription_registry = self._build_subscription_registry(
            orderbook_symbols=desired_symbols
        )
        try:
            self._mark_resubscribing(reason=reason, observed_at=observed_at)
        finally:
            self._active_symbols = previous_active_symbols
            self.subscription_registry = previous_registry

    def _scope_applier_mark_recovered(self, observed_at: datetime) -> None:
        desired_symbols = self._pending_scope_apply_symbols
        if desired_symbols is None:
            self._mark_recovered(observed_at=observed_at)
            return
        previous_active_symbols = self._active_symbols
        previous_registry = self.subscription_registry
        self._active_symbols = desired_symbols
        self.subscription_registry = self._build_subscription_registry(
            orderbook_symbols=desired_symbols
        )
        try:
            self._mark_recovered(observed_at=observed_at)
        finally:
            self._active_symbols = previous_active_symbols
            self.subscription_registry = previous_registry

    async def update_universe_trade_count_threshold(self, min_trade_count_24h: int) -> str:
        normalized_threshold = max(0, int(min_trade_count_24h))
        if not self._universe_scope_mode:
            self._universe_min_trade_count_24h = normalized_threshold
            return "applied"
        if normalized_threshold == self._universe_min_trade_count_24h:
            return "applied"
        self._universe_min_trade_count_24h = normalized_threshold
        self._post_readiness_narrowing_applied = False
        websocket = self._active_websocket
        try:
            if websocket is not None and self._active_symbols != self._coarse_candidate_symbols:
                apply_result = await self._apply_post_readiness_narrowing(
                    desired_symbols=self._coarse_candidate_symbols,
                    apply_reason="trade_count_threshold_updated",
                )
                if apply_result.status == "deferred":
                    self._restore_active_scope_to_coarse_candidates()
            await self._maybe_apply_post_readiness_narrowing()
            return "applied"
        except ConnectionClosed:
            self._restore_active_scope_to_coarse_candidates()
            if self._active_websocket is websocket:
                self._active_websocket = None
            logger.info(
                "Отложено применение Bybit trade-count threshold до следующего transport cycle"
            )
            return "deferred"


def create_bybit_market_data_connector(
    *,
    symbols: tuple[str, ...],
    market_data_runtime: MarketDataRuntime,
    config: BybitMarketDataConnectorConfig | None = None,
    universe_scope_mode: bool = False,
    universe_min_trade_count_24h: int = 0,
    ledger_trade_count_query_service: BybitTradeLedgerTradeCountQueryService | None = None,
    ledger_repository: IBybitTradeLedgerRepository | None = None,
) -> BybitMarketDataConnector:
    """Собрать текущий legacy Bybit linear connector support path.

    Этот constructor остаётся production-контуром на переходный период, но новые
    функциональные изменения должны идти уже в отдельный v2 path.
    """
    session = FeedSessionIdentity(
        exchange="bybit",
        stream_kind="market_data",
        subscription_scope=tuple(normalize_bybit_symbol(symbol) for symbol in symbols),
    )
    return BybitMarketDataConnector(
        session=session,
        market_data_runtime=market_data_runtime,
        config=config,
        universe_scope_mode=universe_scope_mode,
        universe_min_trade_count_24h=universe_min_trade_count_24h,
        ledger_trade_count_query_service=ledger_trade_count_query_service,
        ledger_repository=ledger_repository,
        derived_trade_count_store_path=_default_trade_count_store_path("bybit"),
        historical_trade_backfill_service=(
            None
            if get_settings().bybit_testnet
            else create_bybit_historical_trade_backfill_service(contour="linear")
        ),
    )


async def _connect_bybit_public_stream(
    config: BybitMarketDataConnectorConfig,
) -> BybitWebSocketConnection:
    logger.info(
        "Bybit websocket connect attempt",
        url=config.public_stream_url,
    )
    try:
        connect_timeout_seconds = float(
            getattr(config, "ping_timeout_seconds", _DEFAULT_CONNECT_TIMEOUT_SECONDS)
        )
        if connect_timeout_seconds <= 0:
            connect_timeout_seconds = _DEFAULT_CONNECT_TIMEOUT_SECONDS
        websocket = await asyncio.wait_for(
            websockets.connect(
                config.public_stream_url,
                ping_interval=None,
                ping_timeout=None,
                open_timeout=connect_timeout_seconds,
                close_timeout=_DEFAULT_STOP_CLOSE_TIMEOUT_SECONDS,
            ),
            timeout=connect_timeout_seconds,
        )
    except TimeoutError:
        logger.warning(
            "Bybit websocket connect failed",
            url=config.public_stream_url,
            reason="connect_timeout",
        )
        raise
    except Exception:
        logger.warning(
            "Bybit websocket connect failed",
            url=config.public_stream_url,
            exc_info=True,
        )
        raise
    logger.info(
        "Bybit websocket connect succeeded",
        url=config.public_stream_url,
    )
    return websocket


async def _sleep_seconds(delay_seconds: float) -> None:
    await asyncio.sleep(delay_seconds)


def _ensure_mapping(payload: object, *, field_name: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise BybitMessageParseError(f"Bybit message требует object payload для {field_name}")
    return payload


def _ensure_levels(payload: object, *, field_name: str) -> list[list[str]]:
    if not isinstance(payload, list):
        raise BybitMessageParseError(f"Bybit orderbook message требует list для {field_name}")
    levels: list[list[str]] = []
    for raw_level in payload:
        if not isinstance(raw_level, list) or len(raw_level) < _MIN_ORDERBOOK_LEVEL_WIDTH:
            raise BybitMessageParseError(
                f"Bybit orderbook message требует [price, qty] entries для {field_name}"
            )
        levels.append([str(raw_level[0]), str(raw_level[1])])
    return levels


def _normalize_trade_side(raw_side: object) -> str:
    side = str(raw_side).strip().lower()
    if side == "buy":
        return "buy"
    if side == "sell":
        return "sell"
    raise BybitMessageParseError(f"Неподдерживаемый Bybit trade side: {raw_side}")


def _decimal_value(raw_value: object, *, field_name: str) -> Decimal:
    if raw_value is None:
        raise BybitMessageParseError(f"Bybit message требует {field_name}")
    return Decimal(str(raw_value))


def _optional_str(raw_value: object) -> str | None:
    if raw_value is None:
        return None
    normalized = str(raw_value).strip()
    return normalized or None


def _optional_int(raw_value: object) -> int | None:
    if raw_value is None:
        return None
    return int(raw_value)


def _symbol_from_topic(message: dict[str, Any]) -> str:
    topic = str(message.get("topic", "")).strip()
    if not topic:
        raise BybitMessageParseError("Bybit message требует topic")
    return topic.split(".")[-1]


def _to_bybit_symbol(symbol: str) -> str:
    return symbol.replace("/", "").upper()


def _is_control_message(message: dict[str, Any]) -> bool:
    op = str(message.get("op", "")).strip().lower()
    if op in {"subscribe", "unsubscribe", "ping", "pong"}:
        return True
    return "success" in message and "topic" not in message


def _is_bybit_application_pong_message(message: dict[str, Any]) -> bool:
    op = str(message.get("op", "")).strip().lower()
    if op == "pong":
        return True
    ret_msg = str(message.get("ret_msg", "")).strip().lower()
    return bool(op == "ping" and ret_msg == "pong")


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


def _format_disconnect_reason(exc: Exception) -> str:
    raw_reason = str(exc).strip()
    normalized_reason = raw_reason.lower()
    reason: str | None = None
    if isinstance(exc, TimeoutError) or "ping timeout" in normalized_reason:
        reason = "ping_timeout"
    elif "no close frame received" in normalized_reason:
        reason = "transport_lost"
    elif isinstance(exc, ConnectionClosed):
        if getattr(exc, "rcvd", None) is not None and getattr(exc, "sent", None) is None:
            reason = "remote_close"
        elif getattr(exc, "sent", None) is not None and getattr(exc, "rcvd", None) is None:
            reason = "transport_lost"
        else:
            reason = "transport_closed"
    elif raw_reason:
        reason = raw_reason
    else:
        reason = exc.__class__.__name__
    return reason


def _estimate_historical_backfill_archive_units(
    *,
    symbols: tuple[str, ...],
    covered_until_at: datetime,
) -> int:
    if not symbols:
        return 0
    normalized_covered_until_at = covered_until_at.astimezone(UTC)
    window_started_at = normalized_covered_until_at - timedelta(hours=24)
    archive_boundary = normalized_covered_until_at.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    if archive_boundary <= window_started_at:
        return 0
    final_archive_date = archive_boundary.date() - timedelta(days=1)
    if final_archive_date < window_started_at.date():
        return 0
    total_days = (final_archive_date - window_started_at.date()).days + 1
    return len(symbols) * max(0, total_days)


def _default_trade_count_store_path(exchange: str) -> Path:
    settings = get_settings()
    return settings.data_dir / "live_feed" / f"{exchange}_derived_trade_count.json"


__all__ = [
    "BybitMarketDataConnector",
    "BybitMarketDataConnectorConfig",
    "BybitMarketDataParser",
    "BybitMessageParseError",
    "BybitOrderBookProjector",
    "BybitParsedEnvelope",
    "BybitSubscriptionRegistry",
    "BybitWebSocketConnection",
    "create_bybit_market_data_connector",
    "normalize_bybit_symbol",
]

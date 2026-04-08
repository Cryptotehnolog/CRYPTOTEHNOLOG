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
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
import json
from typing import TYPE_CHECKING, Any, Protocol

import websockets
from websockets.exceptions import ConnectionClosed

from cryptotechnolog.config import get_logger, get_settings

from .bybit_recovery_coordinator import (
    BybitHistoricalRecoveryCoordinator,
    BybitHistoricalRecoveryCoordinatorSnapshot,
    classify_bybit_historical_recovery_result,
)
from .bybit_trade_backfill import (
    BybitHistoricalTradeBackfillService,
    create_bybit_historical_trade_backfill_service,
)
from .bybit_trade_count import (
    BybitDerivedTradeCountPersistenceStore,
    BybitDerivedTradeCountSymbolSnapshot,
    BybitDerivedTradeCountTracker,
)
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

from cryptotechnolog.market_data import build_symbol_identity

logger = get_logger(__name__)

_BYBIT_MAINNET_LINEAR_PUBLIC_URL = "wss://stream.bybit.com/v5/public/linear"
_BYBIT_TESTNET_LINEAR_PUBLIC_URL = "wss://stream-testnet.bybit.com/v5/public/linear"
_KNOWN_QUOTE_SUFFIXES = ("USDT", "USDC", "USD", "BTC", "ETH")
_MIN_ORDERBOOK_LEVEL_WIDTH = 2
_DEFAULT_RECONNECT_DELAY_SECONDS = 5
_DEFAULT_STOP_CLOSE_TIMEOUT_SECONDS = 1.0
_DEFAULT_CONNECT_TIMEOUT_SECONDS = 15.0
_DEFAULT_LATEST_ARCHIVE_RETRY_DELAY_SECONDS = 300.0
_DEFAULT_RTT_TIMEOUTS_BEFORE_CLOSE = 2
_DEFAULT_TRANSPORT_RTT_PROBE_TIMEOUT_SECONDS = 3.0


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

    symbols: tuple[str, ...]
    orderbook_depth: int = 50

    @property
    def topics(self) -> tuple[str, ...]:
        topics: list[str] = []
        for symbol in self.symbols:
            bybit_symbol = _to_bybit_symbol(symbol)
            topics.append(f"publicTrade.{bybit_symbol}")
            topics.append(f"orderbook.{self.orderbook_depth}.{bybit_symbol}")
        return tuple(topics)


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
        self._active_symbols = self._coarse_candidate_symbols
        self.subscription_registry = BybitSubscriptionRegistry(
            symbols=self._active_symbols,
            orderbook_depth=self.config.orderbook_depth,
        )
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
        self._derived_trade_count = BybitDerivedTradeCountTracker(
            symbols=session.subscription_scope
        )
        self._derived_trade_count_store = (
            BybitDerivedTradeCountPersistenceStore(path=derived_trade_count_store_path)
            if self._trade_count_admission_enabled and derived_trade_count_store_path is not None
            else None
        )
        self._post_readiness_narrowing_applied = False
        self._historical_trade_backfill_service = (
            historical_trade_backfill_service if self._trade_count_admission_enabled else None
        )
        self._historical_recovery_coordinator = BybitHistoricalRecoveryCoordinator(
            exchange_name=self.session.exchange,
            sleep_func=self._sleep_func,
            retry_delay_seconds=_DEFAULT_LATEST_ARCHIVE_RETRY_DELAY_SECONDS,
        )
        self._historical_trade_backfill_pending = (
            self._historical_trade_backfill_service is not None
        )
        self._restore_derived_trade_count_state()
        if self._derived_trade_count.ready:
            self._historical_trade_backfill_pending = False
        if not self._trade_count_admission_enabled:
            self._derived_trade_count.mark_backfill_not_needed()
        elif self._historical_trade_backfill_pending:
            self._derived_trade_count.mark_backfill_pending()
        else:
            self._derived_trade_count.mark_backfill_not_needed()
        now = _utcnow()
        self._recovery_state = FeedSubscriptionRecoveryState(
            session=self.session,
            status=FeedSubscriptionRecoveryStatus.IDLE,
            observed_at=now,
        )

    @property
    def _historical_trade_backfill_pending(self) -> bool:
        return self._historical_recovery_coordinator.pending

    @_historical_trade_backfill_pending.setter
    def _historical_trade_backfill_pending(self, value: bool) -> None:
        self._historical_recovery_coordinator.pending = value

    @property
    def _historical_trade_backfill_task(self) -> asyncio.Task[None] | None:
        return self._historical_recovery_coordinator.backfill_task

    @_historical_trade_backfill_task.setter
    def _historical_trade_backfill_task(self, value: asyncio.Task[None] | None) -> None:
        self._historical_recovery_coordinator.backfill_task = value

    @property
    def _historical_trade_backfill_retry_task(self) -> asyncio.Task[None] | None:
        return self._historical_recovery_coordinator.retry_task

    @_historical_trade_backfill_retry_task.setter
    def _historical_trade_backfill_retry_task(self, value: asyncio.Task[None] | None) -> None:
        self._historical_recovery_coordinator.retry_task = value

    @property
    def _historical_trade_backfill_cutoff_at(self) -> datetime | None:
        return self._historical_recovery_coordinator.cutoff_at

    @_historical_trade_backfill_cutoff_at.setter
    def _historical_trade_backfill_cutoff_at(self, value: datetime | None) -> None:
        self._historical_recovery_coordinator.cutoff_at = value

    @property
    def _latest_archive_backfill_retry_pending(self) -> bool:
        return self._historical_recovery_coordinator.latest_retry_pending

    @_latest_archive_backfill_retry_pending.setter
    def _latest_archive_backfill_retry_pending(self, value: bool) -> None:
        self._historical_recovery_coordinator.latest_retry_pending = value

    async def run(self, *, max_cycles: int | None = None) -> None:
        """Запустить explicit reconnect loop для узкого Bybit market-data path."""
        self._stop_requested = False
        cycle = 0
        await self.feed_runtime.start(observed_at=_utcnow())
        while not self._stop_requested and (max_cycles is None or cycle < max_cycles):
            cycle += 1
            websocket: BybitWebSocketConnection | None = None
            try:
                self.feed_runtime.begin_connecting(observed_at=_utcnow())
                connect_timeout_seconds = float(
                    getattr(self.config, "ping_timeout_seconds", _DEFAULT_CONNECT_TIMEOUT_SECONDS)
                )
                if connect_timeout_seconds <= 0:
                    connect_timeout_seconds = _DEFAULT_CONNECT_TIMEOUT_SECONDS
                websocket = await asyncio.wait_for(
                    self._websocket_factory(self.config),
                    timeout=connect_timeout_seconds,
                )
                self._active_websocket = websocket
                self._transport_rtt_ms = None
                self._mark_resubscribing(reason="transport_connected", observed_at=_utcnow())
                await self._subscribe(websocket)
                self.feed_runtime.mark_connected(observed_at=_utcnow())
                self._schedule_historical_trade_count_backfill()
                self._rtt_monitor_task = asyncio.create_task(self._monitor_transport_rtt(websocket))
                await self._consume_messages(websocket)
            except Exception as exc:
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
                if websocket is not None and websocket is not self._stop_closing_websocket:
                    await self._close_websocket_with_timeout(websocket)
                self._active_websocket = None
            if not self._stop_requested:
                await self._sleep_func(self.config.reconnect_delay_seconds)
        self._persist_derived_trade_count(force=True)
        if self.feed_runtime.is_started:
            await self.feed_runtime.stop(observed_at=_utcnow())

    async def stop(self) -> None:
        """Явно запросить stop текущего reconnect loop."""
        self._stop_requested = True
        self._persist_derived_trade_count(force=True)
        self._historical_recovery_coordinator.cancel()
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
                    self._derived_trade_count.note_trade(
                        symbol=payload_symbol,
                        observed_at=trade_observed_at,
                    )
                    self._persist_derived_trade_count(observed_at=trade_observed_at)
                    await self._maybe_apply_post_readiness_narrowing()
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
        if reuse_historical_window:
            self._derived_trade_count.mark_gap_preserving_historical_window(
                observed_at=observed_at,
                reason=reason,
            )
        else:
            self._derived_trade_count.mark_gap(observed_at=observed_at, reason=reason)
        self._persist_derived_trade_count(observed_at=observed_at, force=True)
        self._post_readiness_narrowing_applied = False
        self._historical_trade_backfill_pending = (
            self._historical_recovery_coordinator.note_disconnect(
                service_available=self._historical_trade_backfill_service is not None,
                reuse_historical_window=reuse_historical_window,
            )
        )
        if backfill_was_running and backfill_progress is not None and not reuse_historical_window:
            if (
                backfill_progress.backfill_status == "running"
                and isinstance(backfill_progress.backfill_processed_archives, int)
                and isinstance(backfill_progress.backfill_total_archives, int)
            ):
                self._derived_trade_count.mark_backfill_running(
                    processed_archives=backfill_progress.backfill_processed_archives,
                    total_archives=backfill_progress.backfill_total_archives,
                )
            else:
                self._derived_trade_count.mark_backfill_pending(
                    total_archives=backfill_progress.backfill_total_archives,
                )
        elif self._historical_trade_backfill_pending:
            self._derived_trade_count.mark_backfill_pending()
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

    def get_operator_diagnostics(self) -> dict[str, object]:
        """Вернуть operator-facing snapshot narrow Bybit connector truth."""
        feed_runtime = self.feed_runtime.get_runtime_diagnostics()
        symbols = self._active_symbols
        primary_symbol = symbols[0] if symbols else None
        trade_count_diagnostics = self._derived_trade_count.get_diagnostics(observed_at=_utcnow())
        derived_trade_counts = {
            snapshot.symbol: snapshot for snapshot in trade_count_diagnostics.symbol_snapshots
        }
        symbol_snapshots = tuple(
            self._build_symbol_diagnostics(
                symbol=symbol,
                derived_trade_count_snapshot=derived_trade_counts.get(symbol),
            )
            for symbol in symbols
        )
        primary_snapshot = symbol_snapshots[0] if symbol_snapshots else None
        recovery_state = self.get_recovery_state()
        recovery_coordinator = self._get_historical_recovery_coordinator_snapshot()
        cache_diagnostics_getter = (
            getattr(self._historical_trade_backfill_service, "get_cache_diagnostics", None)
            if self._historical_trade_backfill_service is not None
            else None
        )
        cache_diagnostics = (
            cache_diagnostics_getter() if callable(cache_diagnostics_getter) else None
        )
        last_message_at = feed_runtime.get("last_message_at")
        message_age_ms: int | None = None
        if isinstance(last_message_at, str):
            observed_at = datetime.fromisoformat(last_message_at)
            message_age_ms = max(
                0,
                int((_utcnow() - observed_at).total_seconds() * 1000),
            )
        return {
            "enabled": True,
            "exchange": self.session.exchange,
            "symbol": primary_symbol,
            "symbols": symbols,
            "symbol_snapshots": symbol_snapshots,
            "transport_status": feed_runtime["status"],
            "recovery_status": recovery_state.status.value,
            "subscription_alive": bool(recovery_state.metadata.get("subscription_alive", False)),
            "last_message_at": last_message_at,
            "message_age_ms": message_age_ms,
            "transport_rtt_ms": self._transport_rtt_ms,
            "last_ping_sent_at": self._last_ping_sent_at.isoformat()
            if self._last_ping_sent_at is not None
            else None,
            "last_pong_at": self._last_pong_at.isoformat()
            if self._last_pong_at is not None
            else None,
            "application_ping_sent_at": self._last_application_ping_sent_at.isoformat()
            if self._last_application_ping_sent_at is not None
            else None,
            "application_pong_at": self._last_application_pong_at.isoformat()
            if self._last_application_pong_at is not None
            else None,
            "application_heartbeat_latency_ms": self._application_heartbeat_latency_ms,
            "last_ping_timeout_at": self._last_ping_timeout_at.isoformat()
            if self._last_ping_timeout_at is not None
            else None,
            "last_ping_timeout_message_age_ms": self._last_ping_timeout_message_age_ms,
            "last_ping_timeout_loop_lag_ms": self._last_ping_timeout_loop_lag_ms,
            "last_ping_timeout_backfill_status": self._last_ping_timeout_backfill_status,
            "last_ping_timeout_processed_archives": self._last_ping_timeout_processed_archives,
            "last_ping_timeout_total_archives": self._last_ping_timeout_total_archives,
            "last_ping_timeout_cache_source": self._last_ping_timeout_cache_source,
            "last_ping_timeout_ignored_due_to_recent_messages": (
                self._last_ping_timeout_ignored_due_to_recent_messages
            ),
            "trade_seen": all(snapshot["trade_seen"] for snapshot in symbol_snapshots),
            "orderbook_seen": all(snapshot["orderbook_seen"] for snapshot in symbol_snapshots),
            "best_bid": primary_snapshot["best_bid"] if primary_snapshot is not None else None,
            "best_ask": primary_snapshot["best_ask"] if primary_snapshot is not None else None,
            "degraded_reason": feed_runtime.get("degraded_reason"),
            "last_disconnect_reason": feed_runtime.get("last_disconnect_reason"),
            "retry_count": feed_runtime.get("retry_count"),
            "ready": feed_runtime.get("ready", False),
            "started": feed_runtime.get("started", False),
            "lifecycle_state": feed_runtime.get("lifecycle_state"),
            "reset_required": recovery_state.reset_required,
            "derived_trade_count_state": trade_count_diagnostics.state,
            "derived_trade_count_ready": trade_count_diagnostics.ready,
            "derived_trade_count_observation_started_at": (
                trade_count_diagnostics.observation_started_at
            ),
            "derived_trade_count_reliable_after": trade_count_diagnostics.reliable_after,
            "derived_trade_count_last_gap_at": trade_count_diagnostics.last_gap_at,
            "derived_trade_count_last_gap_reason": trade_count_diagnostics.last_gap_reason,
            "derived_trade_count_backfill_status": trade_count_diagnostics.backfill_status,
            "derived_trade_count_backfill_needed": trade_count_diagnostics.backfill_needed,
            "derived_trade_count_backfill_processed_archives": (
                trade_count_diagnostics.backfill_processed_archives
            ),
            "derived_trade_count_backfill_total_archives": (
                trade_count_diagnostics.backfill_total_archives
            ),
            "derived_trade_count_backfill_progress_percent": (
                trade_count_diagnostics.backfill_progress_percent
            ),
            "derived_trade_count_last_backfill_at": trade_count_diagnostics.last_backfill_at,
            "derived_trade_count_last_backfill_source": trade_count_diagnostics.last_backfill_source,
            "derived_trade_count_last_backfill_reason": trade_count_diagnostics.last_backfill_reason,
            "historical_recovery_state": recovery_coordinator.state,
            "historical_recovery_reason": recovery_coordinator.reason,
            "historical_recovery_retry_pending": recovery_coordinator.retry_pending,
            "historical_recovery_backfill_task_active": recovery_coordinator.backfill_task_active,
            "historical_recovery_retry_task_active": recovery_coordinator.retry_task_active,
            "historical_recovery_cutoff_at": recovery_coordinator.cutoff_at,
            "archive_cache_enabled": (
                cache_diagnostics.cache_enabled if cache_diagnostics is not None else False
            ),
            "archive_cache_memory_hits": (
                cache_diagnostics.memory_hits if cache_diagnostics is not None else 0
            ),
            "archive_cache_disk_hits": (
                cache_diagnostics.disk_hits if cache_diagnostics is not None else 0
            ),
            "archive_cache_misses": (
                cache_diagnostics.misses if cache_diagnostics is not None else 0
            ),
            "archive_cache_writes": (
                cache_diagnostics.writes if cache_diagnostics is not None else 0
            ),
            "archive_cache_last_hit_source": (
                cache_diagnostics.last_hit_source if cache_diagnostics is not None else None
            ),
            "archive_cache_last_url": (
                cache_diagnostics.last_archive_url if cache_diagnostics is not None else None
            ),
            "archive_cache_last_cleanup_at": (
                cache_diagnostics.last_cleanup_at if cache_diagnostics is not None else None
            ),
            "archive_cache_last_pruned_files": (
                cache_diagnostics.last_pruned_files if cache_diagnostics is not None else 0
            ),
            "archive_cache_last_network_fetch_ms": (
                cache_diagnostics.last_network_fetch_ms if cache_diagnostics is not None else None
            ),
            "archive_cache_last_disk_read_ms": (
                cache_diagnostics.last_disk_read_ms if cache_diagnostics is not None else None
            ),
            "archive_cache_last_gzip_decode_ms": (
                cache_diagnostics.last_gzip_decode_ms if cache_diagnostics is not None else None
            ),
            "archive_cache_last_csv_parse_ms": (
                cache_diagnostics.last_csv_parse_ms if cache_diagnostics is not None else None
            ),
            "archive_cache_last_archive_total_ms": (
                cache_diagnostics.last_archive_total_ms if cache_diagnostics is not None else None
            ),
            "archive_cache_last_symbol_total_ms": (
                cache_diagnostics.last_symbol_total_ms if cache_diagnostics is not None else None
            ),
            "archive_cache_last_symbol": (
                cache_diagnostics.last_symbol if cache_diagnostics is not None else None
            ),
            "archive_cache_total_network_fetch_ms": (
                cache_diagnostics.total_network_fetch_ms if cache_diagnostics is not None else 0
            ),
            "archive_cache_total_disk_read_ms": (
                cache_diagnostics.total_disk_read_ms if cache_diagnostics is not None else 0
            ),
            "archive_cache_total_gzip_decode_ms": (
                cache_diagnostics.total_gzip_decode_ms if cache_diagnostics is not None else 0
            ),
            "archive_cache_total_csv_parse_ms": (
                cache_diagnostics.total_csv_parse_ms if cache_diagnostics is not None else 0
            ),
            "archive_cache_total_archive_total_ms": (
                cache_diagnostics.total_archive_total_ms if cache_diagnostics is not None else 0
            ),
            "archive_cache_total_symbol_total_ms": (
                cache_diagnostics.total_symbol_total_ms if cache_diagnostics is not None else 0
            ),
        }

    def _build_symbol_diagnostics(
        self,
        *,
        symbol: str,
        derived_trade_count_snapshot: BybitDerivedTradeCountSymbolSnapshot | None,
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
        return {
            "symbol": symbol,
            "trade_seen": trade_seen,
            "orderbook_seen": orderbook is not None,
            "best_bid": str(orderbook.bids[0].price) if orderbook and orderbook.bids else None,
            "best_ask": str(orderbook.asks[0].price) if orderbook and orderbook.asks else None,
            "volume_24h_usd": (
                str(symbol_metrics.volume_24h_usd)
                if symbol_metrics is not None and symbol_metrics.volume_24h_usd is not None
                else None
            ),
            "derived_trade_count_24h": (
                derived_trade_count_snapshot.trade_count_24h
                if derived_trade_count_snapshot is not None
                else None
            ),
            "observed_trade_count_since_reset": (
                derived_trade_count_snapshot.observed_trade_count_since_reset
                if derived_trade_count_snapshot is not None
                else 0
            ),
        }

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
        if self._derived_trade_count_store is None:
            return
        persisted_state = self._derived_trade_count_store.load()
        if persisted_state is None:
            return
        self._derived_trade_count.restore_from_persisted_state(
            persisted_state,
            restored_at=_utcnow(),
        )

    def _get_historical_recovery_coordinator_snapshot(
        self,
    ) -> BybitHistoricalRecoveryCoordinatorSnapshot:
        return self._historical_recovery_coordinator.snapshot(
            admission_enabled=self._trade_count_admission_enabled,
            has_restored_historical_window=self._derived_trade_count.has_restored_historical_window,
        )

    async def _maybe_restore_historical_trade_count(self) -> None:
        if not self._historical_trade_backfill_pending:
            return
        service = self._historical_trade_backfill_service
        cutoff_at = self._historical_trade_backfill_cutoff_at
        if service is None or cutoff_at is None:
            return
        observed_at = _utcnow()
        recovery_plan = service.build_recovery_plan(
            symbols=self._coarse_candidate_symbols,
            observed_at=observed_at,
            covered_until_at=cutoff_at,
        )
        loop = asyncio.get_running_loop()

        def progress_callback(processed_archives: int, total_archives: int) -> None:
            loop.call_soon_threadsafe(
                self._update_historical_backfill_progress,
                processed_archives,
                total_archives,
            )

        result = await asyncio.to_thread(
            service.load_plan,
            plan=recovery_plan,
            progress_callback=progress_callback,
        )
        recovery_decision = classify_bybit_historical_recovery_result(result)
        self._historical_recovery_coordinator.note_recovery_result(recovery_decision)
        if result.status != "backfilled":
            if result.status == "skipped" and recovery_decision.apply_restore:
                self._derived_trade_count.restore_historical_window(
                    trades_by_symbol=result.trade_timestamps_by_symbol,
                    trade_buckets_by_symbol=result.trade_buckets_by_symbol,
                    latest_trade_at_by_symbol=result.latest_trade_at_by_symbol,
                    window_started_at=result.restored_window_started_at,
                    covered_until_at=result.covered_until_at,
                    observed_at=observed_at,
                    source=result.source,
                    processed_archives=result.processed_archives,
                    total_archives=result.total_archives,
                    status="skipped",
                    reason=result.reason,
                )
                self._persist_derived_trade_count(observed_at=observed_at, force=True)
            elif recovery_decision.mark_skipped and result.reason is not None:
                self._derived_trade_count.mark_backfill_skipped(
                    observed_at=observed_at,
                    reason=result.reason,
                    source=result.source,
                    processed_archives=result.processed_archives,
                    total_archives=result.total_archives,
                )
            elif recovery_decision.mark_unavailable and result.reason is not None:
                self._derived_trade_count.mark_backfill_unavailable(
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
        self._derived_trade_count.restore_historical_window(
            trades_by_symbol=result.trade_timestamps_by_symbol,
            trade_buckets_by_symbol=result.trade_buckets_by_symbol,
            latest_trade_at_by_symbol=result.latest_trade_at_by_symbol,
            window_started_at=result.restored_window_started_at,
            covered_until_at=result.covered_until_at,
            observed_at=observed_at,
            source=result.source,
            processed_archives=result.processed_archives,
            total_archives=result.total_archives,
        )
        self._persist_derived_trade_count(observed_at=observed_at, force=True)
        await self._maybe_apply_post_readiness_narrowing()

    def _schedule_historical_trade_count_backfill(self) -> None:
        if not self._historical_trade_backfill_pending:
            return
        if self._historical_trade_backfill_service is None:
            return
        if self._historical_trade_backfill_task is not None:
            return
        self._historical_trade_backfill_cutoff_at = _utcnow()
        recovery_plan = self._historical_trade_backfill_service.build_recovery_plan(
            symbols=self._coarse_candidate_symbols,
            observed_at=self._historical_trade_backfill_cutoff_at,
            covered_until_at=self._historical_trade_backfill_cutoff_at,
        )
        self._derived_trade_count.mark_backfill_pending(total_archives=recovery_plan.total_archives)
        self._historical_recovery_coordinator.schedule_backfill(
            scheduled_at=self._historical_trade_backfill_cutoff_at,
            run_callback=self._run_historical_trade_count_backfill,
        )

    async def _run_historical_trade_count_backfill(self) -> None:
        await self._maybe_restore_historical_trade_count()

    def _schedule_latest_archive_backfill_retry(self) -> None:
        self._historical_recovery_coordinator.schedule_retry(
            stop_requested=lambda: self._stop_requested,
            trigger_backfill=self._schedule_historical_trade_count_backfill,
        )

    def _update_historical_backfill_progress(
        self,
        processed_archives: int,
        total_archives: int,
    ) -> None:
        self._derived_trade_count.mark_backfill_running(
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
        normalized_observed_at = (observed_at or _utcnow()).astimezone(UTC)
        if not self._derived_trade_count.should_persist(
            observed_at=normalized_observed_at,
            force=force,
        ):
            return
        if self._derived_trade_count_store is None:
            return
        self._derived_trade_count_store.save(
            self._derived_trade_count.to_persisted_state(
                persisted_at=normalized_observed_at,
            )
        )
        self._derived_trade_count.mark_persisted(observed_at=normalized_observed_at)

    async def _maybe_apply_post_readiness_narrowing(self) -> None:
        if not self._universe_scope_mode:
            return
        if self._universe_min_trade_count_24h <= 0:
            return
        if self._post_readiness_narrowing_applied:
            return
        if self._active_websocket is None:
            return
        trade_count_diagnostics = self._derived_trade_count.get_diagnostics(observed_at=_utcnow())
        if not trade_count_diagnostics.ready:
            return
        qualifying_symbols = tuple(
            snapshot.symbol
            for snapshot in trade_count_diagnostics.symbol_snapshots
            if snapshot.trade_count_24h is not None
            and snapshot.trade_count_24h >= self._universe_min_trade_count_24h
        )
        if qualifying_symbols == self._active_symbols:
            self._post_readiness_narrowing_applied = True
            return
        await self._apply_post_readiness_narrowing(qualifying_symbols=qualifying_symbols)
        self._post_readiness_narrowing_applied = True

    async def _apply_post_readiness_narrowing(
        self,
        *,
        qualifying_symbols: tuple[str, ...],
    ) -> None:
        websocket = self._active_websocket
        if websocket is None:
            return
        previous_registry = self.subscription_registry
        observed_at = _utcnow()
        if previous_registry.topics:
            await websocket.send(
                json.dumps({
                    "op": "unsubscribe",
                    "args": list(previous_registry.topics),
                })
            )
        removed_symbols = tuple(
            symbol for symbol in self._active_symbols if symbol not in qualifying_symbols
        )
        for symbol in removed_symbols:
            await self.market_data_runtime.clear_symbol_runtime_state(
                symbol=symbol,
                exchange=self.session.exchange,
                reason="post_readiness_narrowing",
                detected_at=observed_at,
            )
        self._active_symbols = qualifying_symbols
        self.subscription_registry = BybitSubscriptionRegistry(
            symbols=qualifying_symbols,
            orderbook_depth=self.config.orderbook_depth,
        )
        self.parser.invalidate_orderbook_state(symbols=qualifying_symbols)
        if qualifying_symbols:
            self._mark_resubscribing(reason="post_readiness_narrowing", observed_at=observed_at)
            await self._subscribe(websocket)
            return
        self._mark_recovered(observed_at=observed_at)

    def _restore_active_scope_to_coarse_candidates(self) -> None:
        if self._active_symbols == self._coarse_candidate_symbols:
            return
        self._active_symbols = self._coarse_candidate_symbols
        self.subscription_registry = BybitSubscriptionRegistry(
            symbols=self._coarse_candidate_symbols,
            orderbook_depth=self.config.orderbook_depth,
        )

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
                previous_registry = self.subscription_registry
                self._restore_active_scope_to_coarse_candidates()
                self.parser.invalidate_orderbook_state(symbols=self._coarse_candidate_symbols)
                if previous_registry.topics:
                    await websocket.send(
                        json.dumps({
                            "op": "unsubscribe",
                            "args": list(previous_registry.topics),
                        })
                    )
                self._mark_resubscribing(
                    reason="trade_count_threshold_updated",
                    observed_at=_utcnow(),
                )
                await self._subscribe(websocket)
            await self._maybe_apply_post_readiness_narrowing()
            return "applied"
        except ConnectionClosed:
            if self._active_websocket is websocket:
                self._active_websocket = None
            logger.info(
                "Отложено применение Bybit trade-count threshold до следующего transport cycle"
            )
            return "deferred"


def normalize_bybit_symbol(raw_symbol: str) -> str:
    """Нормализовать Bybit symbol в canonical internal symbol format."""
    symbol = raw_symbol.strip().upper()
    if not symbol:
        raise BybitMessageParseError("Bybit symbol не может быть пустым")
    if "/" in symbol:
        return symbol
    for quote in _KNOWN_QUOTE_SUFFIXES:
        if symbol.endswith(quote) and len(symbol) > len(quote):
            base = symbol[: -len(quote)]
            return f"{base}/{quote}"
    raise BybitMessageParseError(f"Не удалось нормализовать Bybit symbol: {raw_symbol}")


def create_bybit_market_data_connector(
    *,
    symbols: tuple[str, ...],
    market_data_runtime: MarketDataRuntime,
    config: BybitMarketDataConnectorConfig | None = None,
    universe_scope_mode: bool = False,
    universe_min_trade_count_24h: int = 0,
) -> BybitMarketDataConnector:
    """Собрать первый explicit Bybit market-data connector slice."""
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
    return await websockets.connect(
        config.public_stream_url,
        ping_interval=None,
        ping_timeout=None,
    )


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

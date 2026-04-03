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
from collections.abc import Awaitable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
import json
from typing import TYPE_CHECKING, Any, Protocol

import websockets

from cryptotechnolog.config import get_logger, get_settings

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
    from collections.abc import Callable
    from cryptotechnolog.config.settings import Settings
    from cryptotechnolog.market_data import MarketDataRuntime

logger = get_logger(__name__)

_BYBIT_MAINNET_LINEAR_PUBLIC_URL = "wss://stream.bybit.com/v5/public/linear"
_BYBIT_TESTNET_LINEAR_PUBLIC_URL = "wss://stream-testnet.bybit.com/v5/public/linear"
_KNOWN_QUOTE_SUFFIXES = ("USDT", "USDC", "USD", "BTC", "ETH")
_MIN_ORDERBOOK_LEVEL_WIDTH = 2
_DEFAULT_RECONNECT_DELAY_SECONDS = 5


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

    def __post_init__(self) -> None:
        if not self.symbols:
            raise ValueError("BybitSubscriptionRegistry требует non-empty symbols")

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
    ) -> None:
        if session.exchange.lower() != "bybit":
            raise ValueError("BybitMarketDataConnector требует bybit session identity")
        self.session = session
        self.market_data_runtime = market_data_runtime
        self.config = config or BybitMarketDataConnectorConfig.from_settings(get_settings())
        self.feed_runtime = feed_runtime or create_live_feed_runtime(session=session)
        self.ingress = ingress or create_live_feed_market_data_ingress()
        self.parser = parser or BybitMarketDataParser(
            max_orderbook_levels=self.config.max_orderbook_levels
        )
        self.subscription_registry = BybitSubscriptionRegistry(
            symbols=session.subscription_scope,
            orderbook_depth=self.config.orderbook_depth,
        )
        self._websocket_factory = websocket_factory or _connect_bybit_public_stream
        self._sleep_func = sleep_func or _sleep_seconds
        self._stop_requested = False
        self._active_websocket: BybitWebSocketConnection | None = None
        self._rtt_monitor_task: asyncio.Task[None] | None = None
        self._transport_rtt_ms: int | None = None
        now = _utcnow()
        self._recovery_state = FeedSubscriptionRecoveryState(
            session=self.session,
            status=FeedSubscriptionRecoveryStatus.IDLE,
            observed_at=now,
        )

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
                websocket = await self._websocket_factory(self.config)
                self._active_websocket = websocket
                self._transport_rtt_ms = None
                self._mark_resubscribing(reason="transport_connected", observed_at=_utcnow())
                await self._subscribe(websocket)
                self.feed_runtime.mark_connected(observed_at=_utcnow())
                self._rtt_monitor_task = asyncio.create_task(self._monitor_transport_rtt(websocket))
                await self._consume_messages(websocket)
            except Exception as exc:
                if self._stop_requested:
                    break
                await self._handle_disconnect(reason=str(exc))
            finally:
                if self._rtt_monitor_task is not None:
                    self._rtt_monitor_task.cancel()
                    self._rtt_monitor_task = None
                if websocket is not None:
                    await websocket.close()
                self._active_websocket = None
            if not self._stop_requested:
                await self._sleep_func(self.config.reconnect_delay_seconds)
        if self.feed_runtime.is_started:
            await self.feed_runtime.stop(observed_at=_utcnow())

    async def stop(self) -> None:
        """Явно запросить stop текущего reconnect loop."""
        self._stop_requested = True
        if self._active_websocket is not None:
            await self._active_websocket.close()

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
            accepted += 1
        if (
            accepted > 0
            and self._recovery_state.status == FeedSubscriptionRecoveryStatus.RECOVERED
            and not self.parser.awaiting_snapshot_symbols()
        ):
            self._mark_recovered(observed_at=_utcnow())
        return accepted

    async def _subscribe(self, websocket: BybitWebSocketConnection) -> None:
        payload = {
            "op": "subscribe",
            "args": list(self.subscription_registry.topics),
        }
        await websocket.send(json.dumps(payload))

    async def _consume_messages(self, websocket: BybitWebSocketConnection) -> None:
        while not self._stop_requested:
            raw_message = await websocket.recv()
            await self.ingest_transport_message(raw_message)

    async def _monitor_transport_rtt(self, websocket: BybitWebSocketConnection) -> None:
        try:
            while not self._stop_requested and self._active_websocket is websocket:
                pong_waiter = await websocket.ping()
                latency_seconds = await pong_waiter
                self._transport_rtt_ms = max(0, int(float(latency_seconds) * 1000))
                await self._sleep_func(self.config.ping_interval_seconds)
        except asyncio.CancelledError:
            raise
        except Exception:
            # RTT monitor must not mask the main receive loop disconnect path.
            return

    async def _handle_disconnect(self, *, reason: str) -> None:
        observed_at = _utcnow()
        logger.warning("Bybit market data connector disconnected", reason=reason)
        self._transport_rtt_ms = None
        self.parser.invalidate_orderbook_state(symbols=self.session.subscription_scope)
        self._mark_recovery_required(reason=reason, observed_at=observed_at)
        self.feed_runtime.mark_disconnected(observed_at=observed_at, reason=reason)
        for symbol in self.session.subscription_scope:
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

    def get_recovery_assessment(self) -> FeedRecoveryAssessment:
        state = self._recovery_state
        return FeedRecoveryAssessment(
            session=self.session,
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
        normalized_symbol = self.session.subscription_scope[0]
        orderbook = self.market_data_runtime.orderbook_manager.get_snapshot(
            normalized_symbol,
            self.session.exchange,
        )
        trade_seen = (
            self.market_data_runtime.state.last_trade_at.get((
                normalized_symbol,
                self.session.exchange,
            ))
            is not None
        )
        recovery_state = self.get_recovery_state()
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
            "symbol": normalized_symbol,
            "symbols": self.session.subscription_scope,
            "transport_status": feed_runtime["status"],
            "recovery_status": recovery_state.status.value,
            "subscription_alive": bool(recovery_state.metadata.get("subscription_alive", False)),
            "last_message_at": last_message_at,
            "message_age_ms": message_age_ms,
            "transport_rtt_ms": self._transport_rtt_ms,
            "trade_seen": trade_seen,
            "orderbook_seen": orderbook is not None,
            "best_bid": str(orderbook.bids[0].price) if orderbook and orderbook.bids else None,
            "best_ask": str(orderbook.asks[0].price) if orderbook and orderbook.asks else None,
            "degraded_reason": feed_runtime.get("degraded_reason"),
            "last_disconnect_reason": feed_runtime.get("last_disconnect_reason"),
            "retry_count": feed_runtime.get("retry_count"),
            "ready": feed_runtime.get("ready", False),
            "started": feed_runtime.get("started", False),
            "lifecycle_state": feed_runtime.get("lifecycle_state"),
            "reset_required": recovery_state.reset_required,
        }

    def _handle_control_message(self, message: dict[str, Any]) -> None:
        op = str(message.get("op", "")).strip().lower()
        if op != "subscribe":
            return
        observed_at = _utcnow()
        if bool(message.get("success", False)):
            self._mark_recovered(observed_at=observed_at)
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
            session=self.session,
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
            session=self.session,
            requested_at=observed_at,
            recovery_reason=reason,
            subscription_scope=self.session.subscription_scope,
        )
        self._recovery_state = FeedSubscriptionRecoveryState(
            session=self.session,
            status=FeedSubscriptionRecoveryStatus.RESUBSCRIBING,
            observed_at=observed_at,
            recovery_required_at=self._recovery_state.recovery_required_at or observed_at,
            last_recovery_reason=reason,
            reset_required=True,
            metadata={"subscription_registry": request.subscription_scope},
        )
        return request

    def _mark_recovered(self, *, observed_at: datetime) -> None:
        self._recovery_state = FeedSubscriptionRecoveryState(
            session=self.session,
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
    )


async def _connect_bybit_public_stream(
    config: BybitMarketDataConnectorConfig,
) -> BybitWebSocketConnection:
    return await websockets.connect(
        config.public_stream_url,
        ping_interval=config.ping_interval_seconds,
        ping_timeout=config.ping_timeout_seconds,
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


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


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

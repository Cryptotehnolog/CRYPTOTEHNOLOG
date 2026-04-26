"""Transport-only Bybit linear v2 path kept separate from the legacy connector."""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass
from datetime import UTC, datetime
import json
from typing import TYPE_CHECKING, Any

from cryptotechnolog.config import get_logger, get_settings

from .bybit import (
    BybitMarketDataParser,
    BybitSubscriptionRegistry,
    BybitWebSocketConnection,
    _connect_bybit_public_stream,
)
from .bybit_connector_state import BybitTransportSnapshot
from .bybit_symbols import normalize_bybit_symbol
from .integration import LiveFeedMarketDataIngress, create_live_feed_market_data_ingress
from .models import FeedSessionIdentity
from .runtime import FeedConnectivityRuntime, create_live_feed_runtime

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from cryptotechnolog.config.settings import Settings
    from cryptotechnolog.market_data import MarketDataRuntime

logger = get_logger(__name__)

_BYBIT_MAINNET_LINEAR_PUBLIC_URL = "wss://stream.bybit.com/v5/public/linear"
_BYBIT_TESTNET_LINEAR_PUBLIC_URL = "wss://stream-testnet.bybit.com/v5/public/linear"
_DEFAULT_CLOSE_TIMEOUT_SECONDS = 1.0


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


@dataclass(slots=True, frozen=True)
class BybitLinearV2TransportConfig:
    public_stream_url: str = _BYBIT_MAINNET_LINEAR_PUBLIC_URL
    orderbook_depth: int = 50
    ping_interval_seconds: int = 20
    ping_timeout_seconds: int = 20
    reconnect_delay_seconds: int = 5
    close_timeout_seconds: float = _DEFAULT_CLOSE_TIMEOUT_SECONDS

    @classmethod
    def from_settings(cls, settings: Settings) -> BybitLinearV2TransportConfig:
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
                    5,
                )
            ),
        )


class BybitLinearV2Transport:
    """Separate linear v2 transport loop without truth, ledger, or recovery layers."""

    def __init__(
        self,
        *,
        symbols: tuple[str, ...],
        config: BybitLinearV2TransportConfig | None = None,
        websocket_factory: Callable[
            [BybitLinearV2TransportConfig], Awaitable[BybitWebSocketConnection]
        ]
        | None = None,
        sleep_func: Callable[[float], Awaitable[None]] = asyncio.sleep,
        market_data_runtime: MarketDataRuntime | None = None,
        feed_runtime: FeedConnectivityRuntime | None = None,
        ingress: LiveFeedMarketDataIngress | None = None,
        parser: BybitMarketDataParser | None = None,
    ) -> None:
        normalized_symbols = tuple(normalize_bybit_symbol(symbol) for symbol in symbols)
        self.symbols = normalized_symbols
        self.config = config or BybitLinearV2TransportConfig.from_settings(get_settings())
        self.session = FeedSessionIdentity(
            exchange="bybit_linear_v2",
            stream_kind="market_data",
            subscription_scope=normalized_symbols,
        )
        self.subscription_registry = BybitSubscriptionRegistry(
            symbols=normalized_symbols,
            orderbook_depth=self.config.orderbook_depth,
        )
        self._websocket_factory = websocket_factory or _connect_bybit_public_stream
        self._sleep_func = sleep_func
        self.market_data_runtime = market_data_runtime
        self.feed_runtime = (
            feed_runtime or create_live_feed_runtime(session=self.session)
            if market_data_runtime is not None
            else None
        )
        self.ingress = (
            ingress or create_live_feed_market_data_ingress()
            if market_data_runtime is not None
            else None
        )
        self.parser = (
            parser or BybitMarketDataParser(max_orderbook_levels=self.config.orderbook_depth)
            if market_data_runtime is not None
            else None
        )
        self._stop_requested = asyncio.Event()
        self.run_started = asyncio.Event()
        self._active_websocket: BybitWebSocketConnection | None = None
        self._rtt_monitor_task: asyncio.Task[None] | None = None
        self._transport_status = "idle"
        self._recovery_status = "idle"
        self._subscription_alive = False
        self._last_message_at: datetime | None = None
        self._transport_rtt_ms: int | None = None
        self._last_ping_sent_at: datetime | None = None
        self._last_pong_at: datetime | None = None
        self._last_disconnect_reason: str | None = None
        self._last_error: str | None = None
        self._retry_count = 0
        self._started = False
        self._messages_received_count = 0
        self._trade_ingest_count = 0
        self._orderbook_ingest_count = 0
        self._trade_seen_symbols: set[str] = set()
        self._orderbook_seen_symbols: set[str] = set()

    async def run(self, *, max_cycles: int | None = None) -> None:
        self._started = True
        self.run_started.set()
        if self.feed_runtime is not None and not self.feed_runtime.is_started:
            await self.feed_runtime.start(observed_at=_utcnow())
        cycle_count = 0
        while not self._stop_requested.is_set():
            if max_cycles is not None and cycle_count >= max_cycles:
                break
            websocket: BybitWebSocketConnection | None = None
            try:
                if self.feed_runtime is not None:
                    self.feed_runtime.begin_connecting(observed_at=_utcnow())
                self._transport_status = "connecting"
                self._recovery_status = "connecting"
                self._subscription_alive = False
                self._transport_rtt_ms = None
                logger.info(
                    "Bybit linear v2 transport connect started",
                    exchange="bybit_linear_v2",
                    symbols=self.symbols,
                    url=self.config.public_stream_url,
                )
                websocket = await self._websocket_factory(self.config)
                self._active_websocket = websocket
                if self.feed_runtime is not None:
                    self.feed_runtime.mark_connected(observed_at=_utcnow())
                self._transport_status = "connected"
                self._recovery_status = "subscribing"
                await self._subscribe(websocket)
                self._rtt_monitor_task = asyncio.create_task(
                    self._monitor_transport_rtt(websocket),
                    name="bybit_linear_v2_transport_rtt_monitor",
                )
                await self._consume_messages(websocket)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._transport_status = "disconnected"
                self._recovery_status = "retrying"
                self._last_error = f"{type(exc).__name__}: {exc}"
                self._last_disconnect_reason = str(exc)
                if self.feed_runtime is not None:
                    self.feed_runtime.mark_disconnected(
                        observed_at=_utcnow(),
                        reason=str(exc),
                    )
                logger.warning(
                    "Bybit linear v2 transport cycle failed",
                    exchange="bybit_linear_v2",
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                    retry_count=self._retry_count,
                )
            finally:
                cycle_count += 1
                if self._rtt_monitor_task is not None:
                    self._rtt_monitor_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError, Exception):
                        await self._rtt_monitor_task
                    self._rtt_monitor_task = None
                if websocket is not None:
                    await self._close_websocket_with_timeout(websocket)
                self._active_websocket = None
            if self._stop_requested.is_set():
                break
            if max_cycles is not None and cycle_count >= max_cycles:
                break
            self._retry_count += 1
            await self._sleep_func(float(self.config.reconnect_delay_seconds))
        if self._transport_status != "disabled":
            self._transport_status = "stopped" if self._stop_requested.is_set() else self._transport_status
        if self._stop_requested.is_set():
            self._recovery_status = "stopped"

    async def stop(self) -> None:
        self._stop_requested.set()
        websocket = self._active_websocket
        if websocket is not None:
            await self._close_websocket_with_timeout(websocket)
        if self.feed_runtime is not None and self.feed_runtime.is_started:
            await self.feed_runtime.stop(observed_at=_utcnow())

    def build_transport_snapshot(self) -> BybitTransportSnapshot:
        message_age_ms: int | None = None
        last_message_at = self._last_message_at
        if last_message_at is not None:
            message_age_ms = max(0, int((_utcnow() - last_message_at).total_seconds() * 1000))
        return BybitTransportSnapshot(
            transport_status=self._transport_status,
            recovery_status=self._recovery_status,
            subscription_alive=self._subscription_alive,
            last_message_at=last_message_at.isoformat() if last_message_at is not None else None,
            message_age_ms=message_age_ms,
            transport_rtt_ms=self._transport_rtt_ms,
            last_ping_sent_at=(
                self._last_ping_sent_at.isoformat() if self._last_ping_sent_at is not None else None
            ),
            last_pong_at=self._last_pong_at.isoformat() if self._last_pong_at is not None else None,
            application_ping_sent_at=None,
            application_pong_at=None,
            application_heartbeat_latency_ms=None,
            last_ping_timeout_at=None,
            last_ping_timeout_message_age_ms=None,
            last_ping_timeout_loop_lag_ms=None,
            last_ping_timeout_backfill_status=None,
            last_ping_timeout_processed_archives=None,
            last_ping_timeout_total_archives=None,
            last_ping_timeout_cache_source=None,
            last_ping_timeout_ignored_due_to_recent_messages=False,
            degraded_reason=None if self._transport_status == "connected" else self._last_error,
            last_disconnect_reason=self._last_disconnect_reason,
            retry_count=self._retry_count,
            ready=self._transport_status == "connected" and self._subscription_alive,
            started=self._started,
            lifecycle_state=self._transport_status,
            reset_required=False,
        )

    def get_transport_diagnostics(self) -> dict[str, object]:
        snapshot = self.build_transport_snapshot()
        return {
            "enabled": True,
            "generation": "v2",
            "exchange": "bybit_linear_v2_transport",
            "symbols": self.symbols,
            "topics": self.subscription_registry.topics,
            "public_stream_url": self.config.public_stream_url,
            "messages_received_count": self._messages_received_count,
            "trade_ingest_count": self._trade_ingest_count,
            "orderbook_ingest_count": self._orderbook_ingest_count,
            "trade_seen": bool(self._trade_seen_symbols),
            "orderbook_seen": bool(self._orderbook_seen_symbols),
            "trade_seen_symbols": tuple(sorted(self._trade_seen_symbols)),
            "orderbook_seen_symbols": tuple(sorted(self._orderbook_seen_symbols)),
            "best_bid": self._best_bid(),
            "best_ask": self._best_ask(),
            "last_error": self._last_error,
            **snapshot.to_dict(),
        }

    async def _subscribe(self, websocket: BybitWebSocketConnection) -> None:
        payload = {
            "op": "subscribe",
            "args": list(self.subscription_registry.topics),
        }
        await websocket.send(json.dumps(payload))

    async def _consume_messages(self, websocket: BybitWebSocketConnection) -> None:
        while not self._stop_requested.is_set():
            raw_message = await websocket.recv()
            self._messages_received_count += 1
            observed_at = _utcnow()
            self._last_message_at = observed_at
            try:
                message = json.loads(raw_message)
            except json.JSONDecodeError:
                continue
            if not isinstance(message, dict):
                continue
            if _is_subscribe_ack(message) or "topic" in message or _is_bybit_application_pong(message):
                self._subscription_alive = True
                self._recovery_status = "streaming"
            if _is_bybit_application_pong(message):
                self._last_pong_at = observed_at
                continue
            if _is_subscribe_ack(message):
                if not bool(message.get("success")):
                    raise RuntimeError("subscribe_failed")
                continue
            if "topic" in message:
                await self._ingest_stream_message(message=message, observed_at=observed_at)

    async def _monitor_transport_rtt(self, websocket: BybitWebSocketConnection) -> None:
        while not self._stop_requested.is_set() and self._active_websocket is websocket:
            self._last_ping_sent_at = _utcnow()
            try:
                pong_waiter = await websocket.ping()
                latency_seconds = await asyncio.wait_for(
                    pong_waiter,
                    timeout=float(self.config.ping_timeout_seconds),
                )
                self._last_pong_at = _utcnow()
                self._transport_rtt_ms = max(0, int(float(latency_seconds) * 1000))
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._last_error = f"{type(exc).__name__}: {exc}"
                self._last_disconnect_reason = str(exc)
                with contextlib.suppress(Exception):
                    await self._close_websocket_with_timeout(websocket)
                return
            await self._sleep_func(float(self.config.ping_interval_seconds))

    async def _close_websocket_with_timeout(self, websocket: BybitWebSocketConnection) -> None:
        with contextlib.suppress(Exception, TimeoutError):
            await asyncio.wait_for(
                websocket.close(),
                timeout=float(self.config.close_timeout_seconds),
            )

    async def _ingest_stream_message(
        self,
        *,
        message: dict[str, Any],
        observed_at: datetime,
    ) -> None:
        if (
            self.market_data_runtime is None
            or self.feed_runtime is None
            or self.ingress is None
            or self.parser is None
        ):
            return
        envelopes = self.parser.parse_message(message)
        for envelope in envelopes:
            request = self.feed_runtime.build_ingest_request(
                payload_kind=envelope.payload_kind,
                transport_payload=envelope.transport_payload,
                ingested_at=observed_at,
                source_sequence=envelope.source_sequence,
            )
            await self.ingress.ingest(
                request=request,
                market_data_runtime=self.market_data_runtime,
            )
            symbol = envelope.transport_payload.get("symbol")
            if envelope.payload_kind == "trade_tick" and isinstance(symbol, str):
                self._trade_ingest_count += 1
                self._trade_seen_symbols.add(symbol)
            if envelope.payload_kind == "orderbook_snapshot" and isinstance(symbol, str):
                self._orderbook_ingest_count += 1
                self._orderbook_seen_symbols.add(symbol)

    def _best_bid(self) -> str | None:
        if self.market_data_runtime is None:
            return None
        for symbol in self.symbols:
            snapshot = self.market_data_runtime.orderbook_manager.get_snapshot(
                symbol,
                self.session.exchange,
            )
            if snapshot is not None and snapshot.bids:
                return str(snapshot.bids[0].price)
        return None

    def _best_ask(self) -> str | None:
        if self.market_data_runtime is None:
            return None
        for symbol in self.symbols:
            snapshot = self.market_data_runtime.orderbook_manager.get_snapshot(
                symbol,
                self.session.exchange,
            )
            if snapshot is not None and snapshot.asks:
                return str(snapshot.asks[0].price)
        return None


def create_bybit_linear_v2_transport(
    *,
    symbols: tuple[str, ...],
    config: BybitLinearV2TransportConfig | None = None,
    market_data_runtime: MarketDataRuntime | None = None,
) -> BybitLinearV2Transport:
    """Create the separate linear v2 transport-only path."""
    return BybitLinearV2Transport(
        symbols=symbols,
        config=config or BybitLinearV2TransportConfig.from_settings(get_settings()),
        market_data_runtime=market_data_runtime,
    )


def _is_subscribe_ack(message: dict[str, Any]) -> bool:
    return message.get("op") == "subscribe" and bool(message.get("success"))


def _is_bybit_application_pong(message: dict[str, Any]) -> bool:
    op = message.get("op")
    ret_msg = message.get("ret_msg")
    if op == "pong":
        return True
    return bool(op == "ping" and ret_msg == "pong")


__all__ = [
    "BybitLinearV2Transport",
    "BybitLinearV2TransportConfig",
    "create_bybit_linear_v2_transport",
]

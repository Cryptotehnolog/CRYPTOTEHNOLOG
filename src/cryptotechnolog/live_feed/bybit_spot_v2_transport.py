"""Transport-only Bybit spot v2 path kept separate from the legacy connector."""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass
from datetime import UTC, datetime
import json
from typing import TYPE_CHECKING, Any

from cryptotechnolog.config import get_logger, get_settings
from cryptotechnolog.core.enhanced_event_bus import PublishError
from websockets.exceptions import ConnectionClosed

from .bybit import (
    BybitMarketDataParser,
    BybitSubscriptionRegistry,
    BybitWebSocketConnection,
    _connect_bybit_public_stream,
)
from .bybit_live_trade_fact import build_bybit_live_trade_fact
from .bybit_live_trade_identity import build_bybit_live_trade_identity
from .bybit_connector_state import BybitTransportSnapshot
from .integration import LiveFeedMarketDataIngress, create_live_feed_market_data_ingress
from .models import FeedSessionIdentity
from .runtime import FeedConnectivityRuntime, create_live_feed_runtime
from .bybit_universe import fetch_bybit_quote_turnover_24h_by_symbol
from .bybit_spot_v2_live_trade_ledger import (
    BybitSpotV2LiveTradeLedgerRepository,
    write_bybit_spot_v2_live_trade_to_ledger,
)
from .bybit_symbols import normalize_bybit_symbol

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from cryptotechnolog.config.settings import Settings
    from cryptotechnolog.market_data import MarketDataRuntime

logger = get_logger(__name__)

_BYBIT_MAINNET_SPOT_PUBLIC_URL = "wss://stream.bybit.com/v5/public/spot"
_BYBIT_TESTNET_SPOT_PUBLIC_URL = "wss://stream-testnet.bybit.com/v5/public/spot"
_DEFAULT_CLOSE_TIMEOUT_SECONDS = 1.0
_DEFAULT_TURNOVER_REFRESH_INTERVAL_SECONDS = 5.0
_BYBIT_SUBSCRIBE_BATCH_SIZE = 10


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


def _is_benign_pong_waiter_close(exc: Exception) -> bool:
    normalized_reason = str(exc).strip().lower()
    if "no close frame received" in normalized_reason:
        return True
    if isinstance(exc, ConnectionClosed):
        close_code = None
        if getattr(exc, "sent", None) is not None:
            close_code = getattr(exc.sent, "code", None)
        if close_code in {1000, 1001}:
            return True
    return False


@dataclass(slots=True, frozen=True)
class BybitSpotV2TransportConfig:
    public_stream_url: str = _BYBIT_MAINNET_SPOT_PUBLIC_URL
    orderbook_depth: int = 50
    ping_interval_seconds: int = 20
    ping_timeout_seconds: int = 20
    reconnect_delay_seconds: int = 5
    close_timeout_seconds: float = _DEFAULT_CLOSE_TIMEOUT_SECONDS
    quote_turnover_refresh_interval_seconds: float = _DEFAULT_TURNOVER_REFRESH_INTERVAL_SECONDS

    @classmethod
    def from_settings(cls, settings: Settings) -> BybitSpotV2TransportConfig:
        return cls(
            public_stream_url=(
                _BYBIT_TESTNET_SPOT_PUBLIC_URL
                if settings.bybit_testnet
                else _BYBIT_MAINNET_SPOT_PUBLIC_URL
            ),
            reconnect_delay_seconds=int(
                getattr(
                    settings,
                    "live_feed_retry_delay_seconds",
                    5,
                )
            ),
        )


class BybitSpotV2Transport:
    """Separate spot v2 transport loop without truth, ledger, or recovery layers."""

    def __init__(
        self,
        *,
        symbols: tuple[str, ...],
        orderbook_symbols: tuple[str, ...] | None = None,
        config: BybitSpotV2TransportConfig | None = None,
        websocket_factory: Callable[
            [BybitSpotV2TransportConfig], Awaitable[BybitWebSocketConnection]
        ]
        | None = None,
        sleep_func: Callable[[float], Awaitable[None]] = asyncio.sleep,
        market_data_runtime: MarketDataRuntime | None = None,
        feed_runtime: FeedConnectivityRuntime | None = None,
        ingress: LiveFeedMarketDataIngress | None = None,
        parser: BybitMarketDataParser | None = None,
        live_trade_ledger_repository: BybitSpotV2LiveTradeLedgerRepository | None = None,
    ) -> None:
        normalized_symbols = tuple(normalize_bybit_symbol(symbol) for symbol in symbols)
        normalized_orderbook_symbols = (
            tuple(normalize_bybit_symbol(symbol) for symbol in orderbook_symbols)
            if orderbook_symbols is not None
            else normalized_symbols
        )
        self.symbols = normalized_symbols
        self.orderbook_symbols = normalized_orderbook_symbols
        self.config = config or BybitSpotV2TransportConfig.from_settings(get_settings())
        self.session = FeedSessionIdentity(
            exchange="bybit_spot_v2",
            stream_kind="market_data",
            subscription_scope=normalized_symbols,
        )
        self.subscription_registry = BybitSubscriptionRegistry(
            symbols=normalized_symbols,
            orderbook_symbols=normalized_orderbook_symbols,
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
        self.live_trade_ledger_repository = live_trade_ledger_repository
        self._stop_requested = asyncio.Event()
        self.run_started = asyncio.Event()
        self._active_websocket: BybitWebSocketConnection | None = None
        self._rtt_monitor_task: asyncio.Task[None] | None = None
        self._transport_status = "idle"
        self._recovery_status = "idle"
        self._subscription_alive = False
        self._last_message_at: datetime | None = None
        self._transport_rtt_ms: int | None = None
        self._last_stable_transport_rtt_ms: int | None = None
        self._last_ping_sent_at: datetime | None = None
        self._last_pong_at: datetime | None = None
        self._last_application_ping_sent_at: datetime | None = None
        self._last_application_pong_at: datetime | None = None
        self._application_heartbeat_latency_ms: int | None = None
        self._application_pong_waiter: asyncio.Future[datetime] | None = None
        self._last_disconnect_reason: str | None = None
        self._last_error: str | None = None
        self._retry_count = 0
        self._started = False
        self._suppress_cycle_failure_log = False
        self._messages_received_count = 0
        self._trade_ingest_count = 0
        self._orderbook_ingest_count = 0
        self._trade_seen_symbols: set[str] = set()
        self._orderbook_seen_symbols: set[str] = set()
        self._persisted_trade_count = 0
        self._last_persisted_trade_at: datetime | None = None
        self._last_persisted_trade_symbol: str | None = None
        self._quote_turnover_refresh_task: asyncio.Task[None] | None = None
        self._quote_turnover_24h_by_symbol: dict[str, str] = {}
        self._quote_turnover_last_synced_at: datetime | None = None
        self._quote_turnover_last_error: str | None = None
        self._market_data_publish_overflow_count = 0
        self._rest_base_url = (
            "https://api-testnet.bybit.com"
            if get_settings().bybit_testnet
            else "https://api.bybit.com"
        )

    async def prepare_storage(self) -> None:
        return

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
                logger.info(
                    "Bybit spot v2 transport connect started",
                    exchange="bybit_spot_v2",
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
                    name="bybit_spot_v2_transport_rtt_monitor",
                )
                self._quote_turnover_refresh_task = asyncio.create_task(
                    self._refresh_quote_turnover_loop(),
                    name="bybit_spot_v2_turnover_refresh",
                )
                await self._consume_messages(websocket)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._transport_status = "disconnected"
                self._recovery_status = "retrying"
                self._last_disconnect_reason = str(exc)
                suppress_failure_log = self._suppress_cycle_failure_log and _is_benign_pong_waiter_close(
                    exc
                )
                self._suppress_cycle_failure_log = False
                if suppress_failure_log:
                    self._last_error = None
                else:
                    self._last_error = f"{type(exc).__name__}: {exc}"
                if self.feed_runtime is not None:
                    self.feed_runtime.mark_disconnected(
                        observed_at=_utcnow(),
                        reason=str(exc),
                    )
                if suppress_failure_log:
                    logger.info(
                        "Bybit spot v2 transport cycle closed benignly",
                        exchange="bybit_spot_v2",
                        error_type=type(exc).__name__,
                        error_message=str(exc),
                        retry_count=self._retry_count,
                    )
                else:
                    logger.warning(
                        "Bybit spot v2 transport cycle failed",
                        exchange="bybit_spot_v2",
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
                if self._quote_turnover_refresh_task is not None:
                    self._quote_turnover_refresh_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError, Exception):
                        await self._quote_turnover_refresh_task
                    self._quote_turnover_refresh_task = None
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
        published_transport_rtt_ms = self._transport_rtt_ms
        heartbeat_rtt_ms = self._application_heartbeat_latency_ms
        if heartbeat_rtt_ms is not None and (
            published_transport_rtt_ms is None
            or published_transport_rtt_ms > max(heartbeat_rtt_ms * 4, heartbeat_rtt_ms + 500)
        ):
            published_transport_rtt_ms = heartbeat_rtt_ms
        elif published_transport_rtt_ms is None and self._last_stable_transport_rtt_ms is not None:
            published_transport_rtt_ms = self._last_stable_transport_rtt_ms
        elif (
            published_transport_rtt_ms is None
            and self._transport_status == "connected"
            and self._subscription_alive
            and message_age_ms is not None
        ):
            published_transport_rtt_ms = message_age_ms
        elif (
            published_transport_rtt_ms is not None
            and self._transport_status == "connected"
            and self._subscription_alive
            and message_age_ms is not None
            and message_age_ms <= 2000
        ):
            # Operator-facing RTT should not keep a stale ping figure when
            # the stream itself is already proving fresher delivery.
            published_transport_rtt_ms = min(published_transport_rtt_ms, message_age_ms)
        return BybitTransportSnapshot(
            transport_status=self._transport_status,
            recovery_status=self._recovery_status,
            subscription_alive=self._subscription_alive,
            last_message_at=last_message_at.isoformat() if last_message_at is not None else None,
            message_age_ms=message_age_ms,
            transport_rtt_ms=published_transport_rtt_ms,
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
            "exchange": "bybit_spot_v2_transport",
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
            "persisted_trade_count": self._persisted_trade_count,
            "last_persisted_trade_at": (
                self._last_persisted_trade_at.isoformat()
                if self._last_persisted_trade_at is not None
                else None
            ),
            "last_persisted_trade_symbol": self._last_persisted_trade_symbol,
            "quote_turnover_24h_by_symbol": dict(self._quote_turnover_24h_by_symbol),
            "quote_turnover_last_synced_at": (
                self._quote_turnover_last_synced_at.isoformat()
                if self._quote_turnover_last_synced_at is not None
                else None
            ),
            "quote_turnover_last_error": self._quote_turnover_last_error,
            "last_error": self._last_error,
            **snapshot.to_dict(),
        }

    async def _subscribe(self, websocket: BybitWebSocketConnection) -> None:
        trade_topics = list(self.subscription_registry.trade_topics)
        orderbook_topics = list(self.subscription_registry.orderbook_topics)
        for topics in (trade_topics, orderbook_topics):
            for index in range(0, len(topics), _BYBIT_SUBSCRIBE_BATCH_SIZE):
                payload = {
                    "op": "subscribe",
                    "args": topics[index : index + _BYBIT_SUBSCRIBE_BATCH_SIZE],
                }
                await websocket.send(json.dumps(payload))
                await self._sleep_func(0.05)

    async def _consume_messages(self, websocket: BybitWebSocketConnection) -> None:
        while not self._stop_requested.is_set():
            try:
                raw_message = await websocket.recv()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._last_disconnect_reason = str(exc)
                if _is_benign_pong_waiter_close(exc):
                    self._suppress_cycle_failure_log = True
                    self._last_error = None
                    return
                raise
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
                self._last_application_pong_at = observed_at
                if (
                    self._application_pong_waiter is not None
                    and not self._application_pong_waiter.done()
                ):
                    self._application_pong_waiter.set_result(observed_at)
                continue
            if _is_subscribe_response(message):
                if not bool(message.get("success")):
                    raise RuntimeError(
                        str(message.get("ret_msg") or message.get("retMsg") or "subscribe_failed")
                    )
                continue
            if "topic" in message:
                await self._ingest_stream_message(message=message, observed_at=observed_at)

    async def _monitor_transport_rtt(self, websocket: BybitWebSocketConnection) -> None:
        while not self._stop_requested.is_set() and self._active_websocket is websocket:
            transport_rtt_ms: int | None = None
            application_rtt_ms: int | None = None
            try:
                application_rtt_ms = await self._measure_application_heartbeat_rtt(websocket)
                if application_rtt_ms is not None:
                    self._application_heartbeat_latency_ms = application_rtt_ms
                    self._last_stable_transport_rtt_ms = application_rtt_ms
                self._last_ping_sent_at = _utcnow()
                pong_waiter = await websocket.ping()
                latency_seconds = await asyncio.wait_for(
                    pong_waiter,
                    timeout=float(self.config.ping_timeout_seconds),
                )
                self._last_pong_at = _utcnow()
                transport_rtt_ms = max(0, int(float(latency_seconds) * 1000))
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                recent_message_age_ms = (
                    max(0, int((_utcnow() - self._last_message_at).total_seconds() * 1000))
                    if self._last_message_at is not None
                    else None
                )
                ping_timeout_ms = int(float(self.config.ping_timeout_seconds) * 1000)
                if (
                    recent_message_age_ms is not None
                    and recent_message_age_ms <= ping_timeout_ms
                ):
                    self._last_error = None
                    self._transport_rtt_ms = None
                    if application_rtt_ms is not None:
                        self._application_heartbeat_latency_ms = application_rtt_ms
                        self._last_stable_transport_rtt_ms = application_rtt_ms
                    await self._sleep_func(float(self.config.ping_interval_seconds))
                    continue
                self._last_disconnect_reason = str(exc)
                if _is_benign_pong_waiter_close(exc):
                    self._suppress_cycle_failure_log = True
                    self._last_error = None
                    return
                self._last_error = f"{type(exc).__name__}: {exc}"
                with contextlib.suppress(Exception):
                    await self._close_websocket_with_timeout(websocket)
                return
            if application_rtt_ms is not None:
                self._application_heartbeat_latency_ms = application_rtt_ms
            if transport_rtt_ms is not None:
                self._transport_rtt_ms = transport_rtt_ms
                self._last_stable_transport_rtt_ms = transport_rtt_ms
            elif self._application_heartbeat_latency_ms is not None:
                self._last_stable_transport_rtt_ms = self._application_heartbeat_latency_ms
            await self._sleep_func(float(self.config.ping_interval_seconds))

    async def _measure_application_heartbeat_rtt(
        self,
        websocket: BybitWebSocketConnection,
    ) -> int | None:
        loop = asyncio.get_running_loop()
        sent_at = _utcnow()
        self._last_application_ping_sent_at = sent_at
        pong_waiter = loop.create_future()
        self._application_pong_waiter = pong_waiter
        try:
            await websocket.send(json.dumps({"op": "ping"}))
            pong_observed_at = await asyncio.wait_for(
                pong_waiter,
                timeout=float(self.config.ping_timeout_seconds),
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            return None
        finally:
            if self._application_pong_waiter is pong_waiter:
                self._application_pong_waiter = None
        self._last_application_pong_at = pong_observed_at
        return max(0, int((pong_observed_at - sent_at).total_seconds() * 1000))

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
            market_data_publish_failed = False
            try:
                await self.ingress.ingest(
                    request=request,
                    market_data_runtime=self.market_data_runtime,
                )
            except PublishError as exc:
                market_data_publish_failed = True
                self._market_data_publish_overflow_count += 1
                self._last_error = f"{type(exc).__name__}: {exc}"
                logger.warning(
                    "Bybit spot v2 market-data publish overflow ignored",
                    exchange="bybit_spot_v2",
                    payload_kind=envelope.payload_kind,
                    symbol=envelope.transport_payload.get("symbol"),
                    overflow_count=self._market_data_publish_overflow_count,
                    error_message=str(exc),
                )
            symbol = envelope.transport_payload.get("symbol")
            if envelope.payload_kind == "trade_tick" and isinstance(symbol, str):
                self._trade_ingest_count += 1
                self._trade_seen_symbols.add(symbol)
                await self._persist_live_trade(envelope.transport_payload)
            if envelope.payload_kind == "orderbook_snapshot" and isinstance(symbol, str):
                self._orderbook_ingest_count += 1
                self._orderbook_seen_symbols.add(symbol)
            if not market_data_publish_failed:
                self._last_error = None

    def _best_bid(self) -> str | None:
        if self.market_data_runtime is None:
            return None
        for symbol in self.symbols:
            if symbol not in self.orderbook_symbols:
                continue
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
            if symbol not in self.orderbook_symbols:
                continue
            snapshot = self.market_data_runtime.orderbook_manager.get_snapshot(
                symbol,
                self.session.exchange,
            )
            if snapshot is not None and snapshot.asks:
                return str(snapshot.asks[0].price)
        return None

    async def _persist_live_trade(self, transport_payload: dict[str, Any]) -> None:
        if self.live_trade_ledger_repository is None:
            return
        fact_result = build_bybit_live_trade_fact(
            contour="spot_v2",
            transport_payload=transport_payload,
        )
        identity = build_bybit_live_trade_identity(fact_result)
        result = await write_bybit_spot_v2_live_trade_to_ledger(
            fact_result=fact_result,
            identity=identity,
            repository=self.live_trade_ledger_repository,
        )
        if result.status != "written" or result.record is None:
            return
        self._persisted_trade_count += 1
        self._last_persisted_trade_at = result.record.exchange_trade_at
        self._last_persisted_trade_symbol = result.record.normalized_symbol

    async def _refresh_quote_turnover_loop(self) -> None:
        try:
            while not self._stop_requested.is_set():
                await self._refresh_quote_turnover_snapshot()
                await self._sleep_func(float(self.config.quote_turnover_refresh_interval_seconds))
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning(
                "Bybit spot v2 quote turnover refresh loop stopped unexpectedly",
                exchange="bybit_spot_v2",
                exc_info=True,
            )

    async def _refresh_quote_turnover_snapshot(self) -> None:
        if not self.symbols:
            self._quote_turnover_24h_by_symbol = {}
            self._quote_turnover_last_synced_at = _utcnow()
            self._quote_turnover_last_error = None
            return
        try:
            fetched = await asyncio.to_thread(
                fetch_bybit_quote_turnover_24h_by_symbol,
                contour="spot",
                rest_base_url=self._rest_base_url,
                symbols=self.symbols,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._quote_turnover_last_error = str(exc)
            logger.warning(
                "Bybit spot v2 quote turnover refresh failed",
                exchange="bybit_spot_v2",
                exc_info=True,
            )
            return
        self._quote_turnover_24h_by_symbol = {
            symbol: str(value)
            for symbol, value in fetched.items()
        }
        self._quote_turnover_last_synced_at = _utcnow()
        self._quote_turnover_last_error = None


def create_bybit_spot_v2_transport(
    *,
    symbols: tuple[str, ...],
    orderbook_symbols: tuple[str, ...] | None = None,
    config: BybitSpotV2TransportConfig | None = None,
    market_data_runtime: MarketDataRuntime | None = None,
    live_trade_ledger_repository: BybitSpotV2LiveTradeLedgerRepository | None = None,
) -> BybitSpotV2Transport:
    """Create the separate spot v2 transport-only path."""
    return BybitSpotV2Transport(
        symbols=symbols,
        orderbook_symbols=orderbook_symbols,
        config=config or BybitSpotV2TransportConfig.from_settings(get_settings()),
        market_data_runtime=market_data_runtime,
        live_trade_ledger_repository=live_trade_ledger_repository,
    )


def _is_subscribe_ack(message: dict[str, Any]) -> bool:
    if not bool(message.get("success")):
        return False
    if "topic" in message:
        return False
    op = str(message.get("op", "")).strip().lower()
    ret_msg = str(message.get("ret_msg", "")).strip().lower()
    return op == "subscribe" or ret_msg == "subscribe"


def _is_subscribe_response(message: dict[str, Any]) -> bool:
    if "topic" in message:
        return False
    op = str(message.get("op", "")).strip().lower()
    ret_msg = str(message.get("ret_msg", "")).strip().lower()
    return op == "subscribe" or ret_msg == "subscribe"


def _is_bybit_application_pong(message: dict[str, Any]) -> bool:
    op = message.get("op")
    ret_msg = message.get("ret_msg")
    if op == "pong":
        return True
    return bool(op == "ping" and ret_msg == "pong")


__all__ = [
    "BybitSpotV2Transport",
    "BybitSpotV2TransportConfig",
    "_is_benign_pong_waiter_close",
    "create_bybit_spot_v2_transport",
]

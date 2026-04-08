from __future__ import annotations

import asyncio
import contextlib
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
import gzip
import json
import pathlib
import shutil
import threading
import time
from urllib.error import HTTPError
from uuid import uuid4

import pytest
from websockets.exceptions import ConnectionClosedError

from cryptotechnolog.config.settings import Settings
from cryptotechnolog.core.enhanced_event_bus import EnhancedEventBus
from cryptotechnolog.live_feed import (
    BybitDerivedTradeCountPersistenceStore,
    BybitDerivedTradeCountTracker,
    BybitHistoricalRecoveryCoordinator,
    BybitHistoricalRecoveryPlan,
    BybitHistoricalTradeBackfillConfig,
    BybitHistoricalTradeBackfillResult,
    BybitHistoricalTradeBackfillService,
    BybitMarketDataConnector,
    BybitMarketDataConnectorConfig,
    BybitMarketDataParser,
    BybitMessageParseError,
    BybitOrderBookProjector,
    BybitSpotMarketDataConnectorConfig,
    BybitSubscriptionRegistry,
    FeedSessionIdentity,
    create_bybit_market_data_connector,
    create_bybit_spot_market_data_connector,
    normalize_bybit_symbol,
)
import cryptotechnolog.live_feed.bybit as bybit_module
from cryptotechnolog.live_feed.models import FeedSubscriptionRecoveryStatus
from cryptotechnolog.market_data import OrderBookLevel, create_market_data_runtime


class _FakeWebSocket:
    def __init__(self, messages: list[str]) -> None:
        self._messages = list(messages)
        self.sent_messages: list[str] = []
        self.closed = False
        self.ping_latency_seconds = 0.018

    async def send(self, message: str) -> None:
        self.sent_messages.append(message)

    async def recv(self) -> str:
        if not self._messages:
            raise RuntimeError("transport_closed")
        return self._messages.pop(0)

    async def close(self) -> None:
        self.closed = True

    async def ping(self, data: object | None = None):
        async def _pong_waiter() -> float:
            return self.ping_latency_seconds

        return _pong_waiter()


class _BlockingWebSocket:
    def __init__(self) -> None:
        self.sent_messages: list[str] = []
        self.closed = False
        self._closed_event = asyncio.Event()
        self.ping_latency_seconds = 0.018

    async def send(self, message: str) -> None:
        self.sent_messages.append(message)

    async def recv(self) -> str:
        await self._closed_event.wait()
        raise RuntimeError("transport_closed")

    async def close(self) -> None:
        self.closed = True
        self._closed_event.set()

    async def ping(self, data: object | None = None):
        async def _pong_waiter() -> float:
            return self.ping_latency_seconds

        return _pong_waiter()


class _SlowCloseWebSocket:
    def __init__(self) -> None:
        self.sent_messages: list[str] = []
        self.closed = False
        self.close_calls = 0
        self.ping_latency_seconds = 0.018

    async def send(self, message: str) -> None:
        self.sent_messages.append(message)

    async def recv(self) -> str:
        await asyncio.sleep(3600)
        raise RuntimeError("transport_closed")

    async def close(self) -> None:
        self.close_calls += 1
        self.closed = True
        await asyncio.sleep(3600)

    async def ping(self, data: object | None = None):
        async def _pong_waiter() -> float:
            return self.ping_latency_seconds

        return _pong_waiter()


class _SlowPongWebSocket:
    def __init__(self) -> None:
        self.sent_messages: list[str] = []
        self.closed = False

    async def send(self, message: str) -> None:
        self.sent_messages.append(message)

    async def recv(self) -> str:
        await asyncio.sleep(3600)
        raise RuntimeError("transport_closed")

    async def close(self) -> None:
        self.closed = True

    async def ping(self, data: object | None = None):
        async def _pong_waiter() -> float:
            await asyncio.sleep(3600)
            return 0.0

        return _pong_waiter()


class _BrokenPingWebSocket(_FakeWebSocket):
    async def ping(self, data: object | None = None):
        raise RuntimeError("temporary_ping_glitch")


class _ClosingSendWebSocket(_FakeWebSocket):
    async def send(self, message: str) -> None:
        raise ConnectionClosedError(None, None)


def _session(*symbols: str) -> FeedSessionIdentity:
    return FeedSessionIdentity(
        exchange="bybit",
        stream_kind="market_data",
        subscription_scope=symbols or ("BTC/USDT",),
    )


def _make_local_temp_dir() -> pathlib.Path:
    temp_dir = pathlib.Path("data") / "test-live-feed" / uuid4().hex
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir


def _trade_message(
    *,
    symbol: str = "BTCUSDT",
    trade_id: str = "trade-1",
    price: str = "68000.5",
    trade_timestamp_ms: int = 1711929600120,
) -> dict[str, object]:
    return {
        "topic": f"publicTrade.{symbol}",
        "type": "snapshot",
        "ts": trade_timestamp_ms + 3,
        "data": [
            {
                "T": trade_timestamp_ms,
                "s": symbol,
                "S": "Buy",
                "v": "0.010",
                "p": price,
                "i": trade_id,
            }
        ],
    }


def _gzip_csv(content: str) -> bytes:
    return gzip.compress(content.encode("utf-8"))


def _orderbook_snapshot_message(
    *,
    symbol: str = "BTCUSDT",
    bids: list[list[str]] | None = None,
    asks: list[list[str]] | None = None,
) -> dict[str, object]:
    return {
        "topic": f"orderbook.50.{symbol}",
        "type": "snapshot",
        "ts": 1711929600200,
        "data": {
            "s": symbol,
            "b": bids or [["68000.0", "2.5"], ["67999.5", "1.0"]],
            "a": asks or [["68000.5", "3.0"], ["68001.0", "1.5"]],
            "u": 1001,
            "seq": 77,
        },
    }


def _orderbook_delta_message() -> dict[str, object]:
    return {
        "topic": "orderbook.50.BTCUSDT",
        "type": "delta",
        "ts": 1711929600300,
        "data": {
            "s": "BTCUSDT",
            "b": [["68000.0", "0"], ["67999.0", "4.0"]],
            "a": [["68000.5", "2.0"]],
            "u": 1002,
            "seq": 78,
        },
    }


def test_normalize_bybit_symbol_returns_canonical_internal_symbol() -> None:
    assert normalize_bybit_symbol("BTCUSDT") == "BTC/USDT"
    assert normalize_bybit_symbol("ETH/USDT") == "ETH/USDT"

    with pytest.raises(BybitMessageParseError, match="Не удалось нормализовать"):
        normalize_bybit_symbol("BTCUNKNOWN")


def test_bybit_parser_emits_trade_and_projected_orderbook_envelopes() -> None:
    parser = BybitMarketDataParser(max_orderbook_levels=5)

    trade_envelopes = parser.parse_message(_trade_message())
    orderbook_snapshot = parser.parse_message(_orderbook_snapshot_message())
    orderbook_delta = parser.parse_message(_orderbook_delta_message())

    assert len(trade_envelopes) == 1
    assert trade_envelopes[0].payload_kind == "trade_tick"
    assert trade_envelopes[0].transport_payload["symbol"] == "BTC/USDT"
    assert trade_envelopes[0].transport_payload["price"] == "68000.5"
    assert trade_envelopes[0].transport_payload["side"] == "buy"
    assert trade_envelopes[0].transport_payload["exchange_trade_at_ms"] == 1711929600120

    assert orderbook_snapshot[0].payload_kind == "orderbook_snapshot"
    assert orderbook_snapshot[0].transport_payload["bids"][0]["price"] == "68000.0"

    bids_after_delta = orderbook_delta[0].transport_payload["bids"]
    asks_after_delta = orderbook_delta[0].transport_payload["asks"]
    assert bids_after_delta[0]["price"] == "67999.5"
    assert bids_after_delta[1]["price"] == "67999.0"
    assert asks_after_delta[0]["qty"] == "2.0"


def test_orderbook_projector_requires_honest_non_empty_book() -> None:
    projector = BybitOrderBookProjector(max_levels=2)

    snapshot_payload = projector.apply_message(_orderbook_snapshot_message())
    assert snapshot_payload["symbol"] == "BTC/USDT"
    assert len(snapshot_payload["bids"]) == 2
    assert len(snapshot_payload["asks"]) == 2


def test_subscription_registry_builds_trade_and_orderbook_topics() -> None:
    registry = BybitSubscriptionRegistry(symbols=("BTC/USDT",), orderbook_depth=50)

    assert registry.topics == ("publicTrade.BTCUSDT", "orderbook.50.BTCUSDT")


def test_subscription_registry_builds_topics_for_multiple_symbols() -> None:
    registry = BybitSubscriptionRegistry(symbols=("BTC/USDT", "ETH/USDT"), orderbook_depth=50)

    assert registry.topics == (
        "publicTrade.BTCUSDT",
        "orderbook.50.BTCUSDT",
        "publicTrade.ETHUSDT",
        "orderbook.50.ETHUSDT",
    )


def test_bybit_connector_config_uses_mainnet_by_default() -> None:
    settings = Settings()

    config = BybitMarketDataConnectorConfig.from_settings(settings)

    assert config.public_stream_url == "wss://stream.bybit.com/v5/public/linear"


def test_bybit_spot_connector_config_uses_mainnet_by_default() -> None:
    settings = Settings()

    config = BybitSpotMarketDataConnectorConfig.from_settings(settings)

    assert config.public_stream_url == "wss://stream.bybit.com/v5/public/spot"


def test_create_bybit_spot_market_data_connector_builds_separate_spot_identity() -> None:
    event_bus = EnhancedEventBus(enable_persistence=False)
    market_data_runtime = create_market_data_runtime(event_bus=event_bus)

    connector = create_bybit_spot_market_data_connector(
        symbols=("BTC/USDT", "ETH/USDT"),
        market_data_runtime=market_data_runtime,
    )

    assert connector.session.exchange == "bybit_spot"
    assert connector.session.subscription_scope == ("BTC/USDT", "ETH/USDT")
    assert connector.config.public_stream_url == "wss://stream.bybit.com/v5/public/spot"
    assert connector.subscription_registry.topics == (
        "publicTrade.BTCUSDT",
        "orderbook.50.BTCUSDT",
        "publicTrade.ETHUSDT",
        "orderbook.50.ETHUSDT",
    )


@pytest.mark.asyncio
async def test_bybit_connector_operator_diagnostics_expose_connector_truth() -> None:
    event_bus = EnhancedEventBus(enable_persistence=False)
    market_data_runtime = create_market_data_runtime(event_bus=event_bus)
    await market_data_runtime.start()
    trade_timestamp_ms = int(datetime.now(tz=UTC).timestamp() * 1000)

    connector = BybitMarketDataConnector(
        session=_session(),
        market_data_runtime=market_data_runtime,
    )
    await connector.feed_runtime.start(observed_at=connector.get_recovery_state().observed_at)
    connector.feed_runtime.mark_connected(observed_at=connector.get_recovery_state().observed_at)
    connector._mark_resubscribing(
        reason="transport_connected",
        observed_at=connector.get_recovery_state().observed_at,
    )
    await connector.ingest_transport_message(json.dumps({"op": "subscribe", "success": True}))
    await connector.ingest_transport_message(
        json.dumps(_trade_message(trade_timestamp_ms=trade_timestamp_ms))
    )
    await connector.ingest_transport_message(json.dumps(_orderbook_snapshot_message()))

    diagnostics = connector.get_operator_diagnostics()

    assert diagnostics["enabled"] is True
    assert diagnostics["symbol"] == "BTC/USDT"
    assert diagnostics["symbols"] == ("BTC/USDT",)
    assert diagnostics["transport_status"] == "connected"
    assert diagnostics["recovery_status"] == "recovered"
    assert diagnostics["subscription_alive"] is True
    assert diagnostics["trade_seen"] is True
    assert diagnostics["orderbook_seen"] is True
    assert diagnostics["best_bid"] == "68000.0"
    assert diagnostics["best_ask"] == "68000.5"
    assert isinstance(diagnostics["message_age_ms"], int)
    assert diagnostics["message_age_ms"] >= 0
    assert diagnostics["derived_trade_count_state"] == "warming_up"
    assert diagnostics["derived_trade_count_ready"] is False
    observation_started_at = datetime.fromisoformat(
        str(diagnostics["derived_trade_count_observation_started_at"])
    )
    assert (
        diagnostics["derived_trade_count_reliable_after"]
        == (observation_started_at + timedelta(hours=24)).isoformat()
    )
    assert diagnostics["derived_trade_count_last_gap_at"] is None
    assert diagnostics["symbol_snapshots"][0]["derived_trade_count_24h"] is None
    assert diagnostics["symbol_snapshots"][0]["observed_trade_count_since_reset"] == 1


@pytest.mark.asyncio
async def test_bybit_connector_operator_diagnostics_surface_multi_symbol_truth() -> None:
    event_bus = EnhancedEventBus(enable_persistence=False)
    market_data_runtime = create_market_data_runtime(event_bus=event_bus)
    await market_data_runtime.start()
    btc_trade_timestamp_ms = int(datetime.now(tz=UTC).timestamp() * 1000)
    eth_trade_timestamp_ms = btc_trade_timestamp_ms + 1000

    connector = BybitMarketDataConnector(
        session=_session("BTC/USDT", "ETH/USDT"),
        market_data_runtime=market_data_runtime,
    )
    await connector.feed_runtime.start(observed_at=connector.get_recovery_state().observed_at)
    connector.feed_runtime.mark_connected(observed_at=connector.get_recovery_state().observed_at)
    connector._mark_resubscribing(
        reason="transport_connected",
        observed_at=connector.get_recovery_state().observed_at,
    )
    await connector.ingest_transport_message(json.dumps({"op": "subscribe", "success": True}))
    await connector.ingest_transport_message(
        json.dumps(_trade_message(trade_timestamp_ms=btc_trade_timestamp_ms))
    )
    await connector.ingest_transport_message(json.dumps(_orderbook_snapshot_message()))
    await connector.ingest_transport_message(
        json.dumps(
            _trade_message(
                symbol="ETHUSDT",
                trade_id="trade-2",
                price="3500.5",
                trade_timestamp_ms=eth_trade_timestamp_ms,
            )
        )
    )
    await connector.ingest_transport_message(
        json.dumps(
            _orderbook_snapshot_message(
                symbol="ETHUSDT",
                bids=[["3500.0", "3.0"], ["3499.5", "1.0"]],
                asks=[["3500.5", "4.0"], ["3501.0", "1.2"]],
            )
        )
    )

    diagnostics = connector.get_operator_diagnostics()

    assert diagnostics["symbols"] == ("BTC/USDT", "ETH/USDT")
    assert diagnostics["trade_seen"] is True
    assert diagnostics["orderbook_seen"] is True
    assert diagnostics["best_bid"] == "68000.0"
    assert diagnostics["best_ask"] == "68000.5"
    assert diagnostics["symbol_snapshots"] == (
        {
            "symbol": "BTC/USDT",
            "trade_seen": True,
            "orderbook_seen": True,
            "best_bid": "68000.0",
            "best_ask": "68000.5",
            "volume_24h_usd": None,
            "derived_trade_count_24h": None,
            "observed_trade_count_since_reset": 1,
        },
        {
            "symbol": "ETH/USDT",
            "trade_seen": True,
            "orderbook_seen": True,
            "best_bid": "3500.0",
            "best_ask": "3500.5",
            "volume_24h_usd": None,
            "derived_trade_count_24h": None,
            "observed_trade_count_since_reset": 1,
        },
    )


def test_derived_trade_count_tracker_requires_continuous_window_before_ready() -> None:
    tracker = BybitDerivedTradeCountTracker(symbols=("BTC/USDT",))
    started_at = datetime(2026, 4, 5, 12, 0, tzinfo=UTC)

    tracker.mark_observation_started(observed_at=started_at)
    tracker.note_trade(symbol="BTC/USDT", observed_at=started_at + timedelta(minutes=1))

    warming = tracker.get_diagnostics(observed_at=started_at + timedelta(hours=23))

    assert warming.state == "warming_up"
    assert warming.ready is False


def test_derived_trade_count_tracker_live_tail_pending_transitions_to_ready_after_trade() -> None:
    tracker = BybitDerivedTradeCountTracker(symbols=("BTC/USDT",))
    restored_at = datetime(2026, 4, 7, 12, 0, tzinfo=UTC)
    gap_at = datetime(2026, 4, 7, 12, 30, tzinfo=UTC)
    post_gap_trade_at = gap_at + timedelta(seconds=15)

    tracker.restore_historical_window(
        trades_by_symbol={
            "BTC/USDT": (
                datetime(2026, 4, 6, 12, 1, tzinfo=UTC),
                datetime(2026, 4, 7, 11, 59, tzinfo=UTC),
            )
        },
        window_started_at=datetime(2026, 4, 6, 12, 0, tzinfo=UTC),
        covered_until_at=restored_at,
        observed_at=restored_at,
        processed_archives=1,
        total_archives=1,
    )
    tracker.mark_gap_preserving_historical_window(observed_at=gap_at, reason="transport_gap")

    before_trade = tracker.get_diagnostics(observed_at=gap_at)
    assert before_trade.state == "live_tail_pending_after_gap"
    assert before_trade.ready is False

    tracker.note_trade(symbol="BTC/USDT", observed_at=post_gap_trade_at)
    after_trade = tracker.get_diagnostics(observed_at=post_gap_trade_at)

    assert after_trade.state == "ready"
    assert after_trade.ready is True


@pytest.mark.asyncio
async def test_historical_recovery_coordinator_triggers_delayed_retry() -> None:
    sleep_calls: list[float] = []
    triggered: list[str] = []

    async def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    coordinator = BybitHistoricalRecoveryCoordinator(
        exchange_name="bybit",
        sleep_func=fake_sleep,
        retry_delay_seconds=3.0,
    )
    coordinator.latest_retry_pending = True

    coordinator.schedule_retry(
        stop_requested=lambda: False,
        trigger_backfill=lambda: triggered.append("retry"),
    )

    assert coordinator.retry_task is not None
    await coordinator.retry_task

    assert sleep_calls == [3.0]
    assert triggered == ["retry"]
    assert coordinator.retry_task is None


def test_derived_trade_count_tracker_resets_reliability_after_gap() -> None:
    tracker = BybitDerivedTradeCountTracker(symbols=("BTC/USDT",))
    started_at = datetime(2026, 4, 5, 12, 0, tzinfo=UTC)

    tracker.mark_observation_started(observed_at=started_at)
    tracker.note_trade(symbol="BTC/USDT", observed_at=started_at + timedelta(minutes=1))
    tracker.get_diagnostics(observed_at=started_at + timedelta(hours=24, minutes=1))

    gap_at = started_at + timedelta(hours=25)
    tracker.mark_gap(observed_at=gap_at, reason="transport_gap")

    after_gap = tracker.get_diagnostics(observed_at=gap_at)

    assert after_gap.state == "not_reliable_after_gap"
    assert after_gap.ready is False
    assert after_gap.last_gap_at == gap_at.isoformat()
    assert after_gap.last_gap_reason == "transport_gap"
    assert after_gap.symbol_snapshots[0].trade_count_24h is None
    assert after_gap.symbol_snapshots[0].observed_trade_count_since_reset == 0

    resumed_at = gap_at + timedelta(minutes=10)
    tracker.mark_observation_started(observed_at=resumed_at)
    tracker.note_trade(symbol="BTC/USDT", observed_at=resumed_at + timedelta(minutes=1))

    resumed = tracker.get_diagnostics(observed_at=resumed_at + timedelta(minutes=1))

    assert resumed.state == "warming_up"
    assert resumed.ready is False
    assert resumed.observation_started_at == resumed_at.isoformat()
    assert resumed.reliable_after == (resumed_at + timedelta(hours=24)).isoformat()


def test_derived_trade_count_tracker_uses_bounded_minute_buckets() -> None:
    tracker = BybitDerivedTradeCountTracker(symbols=("BTC/USDT",))
    started_at = datetime(2026, 4, 5, 12, 0, tzinfo=UTC)

    tracker.mark_observation_started(observed_at=started_at)
    tracker.note_trade(symbol="BTC/USDT", observed_at=started_at + timedelta(seconds=5))
    tracker.note_trade(symbol="BTC/USDT", observed_at=started_at + timedelta(seconds=20))
    tracker.note_trade(symbol="BTC/USDT", observed_at=started_at + timedelta(minutes=1))

    assert len(tracker._trade_count_buckets["BTC/USDT"]) == 2
    assert tracker._observed_trade_count_since_reset["BTC/USDT"] == 3


def test_derived_trade_count_tracker_restores_ready_state_from_fresh_local_snapshot() -> None:
    temp_dir = _make_local_temp_dir()
    store = BybitDerivedTradeCountPersistenceStore(path=temp_dir / "trade_count.json")
    tracker = BybitDerivedTradeCountTracker(symbols=("BTC/USDT",))
    started_at = datetime(2026, 4, 5, 12, 0, tzinfo=UTC)

    tracker.note_trade(symbol="BTC/USDT", observed_at=started_at)
    tracker.note_trade(symbol="BTC/USDT", observed_at=started_at + timedelta(hours=24, minutes=1))
    persisted_at = started_at + timedelta(hours=24, minutes=1, seconds=10)
    store.save(tracker.to_persisted_state(persisted_at=persisted_at))

    restored = BybitDerivedTradeCountTracker(symbols=("BTC/USDT",))
    persisted_state = store.load()

    assert persisted_state is not None

    restored.restore_from_persisted_state(
        persisted_state,
        restored_at=persisted_at + timedelta(seconds=20),
    )
    diagnostics = restored.get_diagnostics(observed_at=persisted_at + timedelta(seconds=20))

    assert diagnostics.state == "ready"
    assert diagnostics.ready is True
    assert diagnostics.symbol_snapshots[0].trade_count_24h == 1
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_derived_trade_count_tracker_restores_live_tail_requirement_from_persisted_snapshot() -> (
    None
):
    temp_dir = _make_local_temp_dir()
    store = BybitDerivedTradeCountPersistenceStore(path=temp_dir / "trade_count.json")
    tracker = BybitDerivedTradeCountTracker(symbols=("BTC/USDT",))
    observed_at = datetime(2026, 4, 6, 12, 0, 30, tzinfo=UTC)

    tracker.restore_historical_window(
        trades_by_symbol={
            "BTC/USDT": (
                datetime(2026, 4, 5, 12, 1, tzinfo=UTC),
                datetime(2026, 4, 6, 11, 58, tzinfo=UTC),
            )
        },
        window_started_at=datetime(2026, 4, 5, 12, 0, tzinfo=UTC),
        covered_until_at=datetime(2026, 4, 6, 12, 0, tzinfo=UTC),
        observed_at=observed_at,
        status="skipped",
        reason="historical trade archive not found for linear:BTCUSDT:2026-04-06",
    )
    persisted_at = observed_at + timedelta(seconds=10)
    store.save(tracker.to_persisted_state(persisted_at=persisted_at))

    restored = BybitDerivedTradeCountTracker(symbols=("BTC/USDT",))
    persisted_state = store.load()

    assert persisted_state is not None
    assert persisted_state.live_tail_required_after == datetime(2026, 4, 6, 12, 0, tzinfo=UTC)

    restored.restore_from_persisted_state(
        persisted_state,
        restored_at=persisted_at + timedelta(seconds=20),
    )
    diagnostics = restored.get_diagnostics(observed_at=persisted_at + timedelta(seconds=20))

    assert diagnostics.state == "warming_up"
    assert diagnostics.ready is False
    assert diagnostics.reliable_after == datetime(2026, 4, 6, 12, 0, tzinfo=UTC).isoformat()
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_historical_trade_backfill_restores_ready_window_from_archived_trades() -> None:
    observed_at = datetime(2026, 4, 6, 12, 0, tzinfo=UTC)
    tracker = BybitDerivedTradeCountTracker(symbols=("BTC/USDT",))

    archives = {
        "https://public.bybit.com/trading/BTCUSDT/BTCUSDT2026-04-05.csv.gz": _gzip_csv(
            "timestamp,price,qty\n"
            "2026-04-05T12:01:00+00:00,68000,0.1\n"
            "2026-04-05T18:00:00+00:00,68100,0.2\n"
        ),
    }

    service = BybitHistoricalTradeBackfillService(
        config=BybitHistoricalTradeBackfillConfig(contour="linear"),
        fetch_bytes=lambda url, _timeout: archives[url],
    )

    result = service.load_window(
        symbols=("BTC/USDT",),
        observed_at=observed_at,
    )
    tracker.note_trade(symbol="BTC/USDT", observed_at=datetime(2026, 4, 6, 9, 0, tzinfo=UTC))
    tracker.restore_historical_window(
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
    diagnostics = tracker.get_diagnostics(observed_at=observed_at)

    assert result.status == "backfilled"
    assert result.backfilled_trade_count == 2
    assert result.processed_archives == 1
    assert result.total_archives == 1
    assert diagnostics.state == "ready"
    assert diagnostics.ready is True
    assert diagnostics.backfill_status == "backfilled"
    assert diagnostics.backfill_needed is True
    assert diagnostics.backfill_processed_archives == 1
    assert diagnostics.backfill_total_archives == 1
    assert diagnostics.backfill_progress_percent == 100
    assert diagnostics.last_backfill_source == "bybit_public_archive"
    assert diagnostics.symbol_snapshots[0].trade_count_24h == 3
    assert diagnostics.symbol_snapshots[0].observed_trade_count_since_reset == 1


def test_derived_trade_count_tracker_marks_state_unreliable_after_stale_restart_snapshot() -> None:
    temp_dir = _make_local_temp_dir()
    store = BybitDerivedTradeCountPersistenceStore(path=temp_dir / "trade_count.json")
    tracker = BybitDerivedTradeCountTracker(symbols=("BTC/USDT",))
    started_at = datetime(2026, 4, 5, 12, 0, tzinfo=UTC)

    tracker.note_trade(symbol="BTC/USDT", observed_at=started_at)
    store.save(tracker.to_persisted_state(persisted_at=started_at + timedelta(seconds=5)))

    restored = BybitDerivedTradeCountTracker(symbols=("BTC/USDT",))
    persisted_state = store.load()

    assert persisted_state is not None

    restored.restore_from_persisted_state(
        persisted_state,
        restored_at=started_at + timedelta(minutes=5),
    )
    diagnostics = restored.get_diagnostics(observed_at=started_at + timedelta(minutes=5))

    assert diagnostics.state == "not_reliable_after_gap"
    assert diagnostics.ready is False
    assert diagnostics.last_gap_reason == "restart_persistence_gap"
    assert diagnostics.symbol_snapshots[0].trade_count_24h is None
    assert diagnostics.symbol_snapshots[0].observed_trade_count_since_reset == 0
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_bybit_connector_restores_derived_trade_count_state_from_local_snapshot() -> None:
    event_bus = EnhancedEventBus(enable_persistence=False)
    market_data_runtime = create_market_data_runtime(event_bus=event_bus)
    temp_dir = _make_local_temp_dir()
    store = BybitDerivedTradeCountPersistenceStore(path=temp_dir / "trade_count.json")
    tracker = BybitDerivedTradeCountTracker(symbols=("BTC/USDT",))
    started_at = datetime.now(tz=UTC) - timedelta(hours=24, minutes=1)

    tracker.note_trade(symbol="BTC/USDT", observed_at=started_at)
    tracker.note_trade(symbol="BTC/USDT", observed_at=started_at + timedelta(hours=24))
    persisted_at = datetime.now(tz=UTC)
    store.save(tracker.to_persisted_state(persisted_at=persisted_at))

    connector = BybitMarketDataConnector(
        session=_session(),
        market_data_runtime=market_data_runtime,
        derived_trade_count_store_path=store.path,
    )

    diagnostics = connector.get_operator_diagnostics()

    assert diagnostics["derived_trade_count_state"] == "ready"
    assert diagnostics["derived_trade_count_ready"] is True
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_bybit_connector_restores_trade_count_readiness_from_historical_backfill() -> None:
    event_bus = EnhancedEventBus(enable_persistence=False)
    market_data_runtime = create_market_data_runtime(event_bus=event_bus)
    observed_at = datetime(2026, 4, 6, 12, 0, tzinfo=UTC)
    archives = {
        "https://public.bybit.com/trading/BTCUSDT/BTCUSDT2026-04-05.csv.gz": _gzip_csv(
            "timestamp,price,qty\n2026-04-05T12:01:00+00:00,68000,0.1\n"
        ),
    }
    service = BybitHistoricalTradeBackfillService(
        config=BybitHistoricalTradeBackfillConfig(contour="linear"),
        fetch_bytes=lambda url, _timeout: archives[url],
    )

    connector = BybitMarketDataConnector(
        session=_session(),
        market_data_runtime=market_data_runtime,
        universe_scope_mode=True,
        universe_min_trade_count_24h=2,
        historical_trade_backfill_service=service,
    )
    connector._derived_trade_count.note_trade(
        symbol="BTC/USDT",
        observed_at=datetime(2026, 4, 6, 11, 59, tzinfo=UTC),
    )

    original_utcnow = connector._maybe_restore_historical_trade_count.__globals__["_utcnow"]
    connector._maybe_restore_historical_trade_count.__globals__["_utcnow"] = lambda: observed_at
    connector._historical_trade_backfill_cutoff_at = observed_at
    try:
        await connector._maybe_restore_historical_trade_count()
    finally:
        connector._maybe_restore_historical_trade_count.__globals__["_utcnow"] = original_utcnow

    diagnostics = connector.get_operator_diagnostics()

    assert diagnostics["derived_trade_count_state"] == "ready"
    assert diagnostics["derived_trade_count_ready"] is True
    assert diagnostics["derived_trade_count_backfill_status"] == "backfilled"
    assert diagnostics["derived_trade_count_backfill_needed"] is True
    assert diagnostics["derived_trade_count_backfill_processed_archives"] == 1
    assert diagnostics["derived_trade_count_backfill_total_archives"] == 1
    assert diagnostics["derived_trade_count_backfill_progress_percent"] == 100
    assert diagnostics["derived_trade_count_last_backfill_source"] == "bybit_public_archive"


def test_historical_trade_backfill_keeps_latest_live_trade_time_after_merge() -> None:
    tracker = BybitDerivedTradeCountTracker(symbols=("BTC/USDT",))
    live_tail_at = datetime(2026, 4, 6, 12, 0, 45, tzinfo=UTC)
    tracker.note_trade(symbol="BTC/USDT", observed_at=live_tail_at)

    tracker.restore_historical_window(
        trades_by_symbol={
            "BTC/USDT": (
                datetime(2026, 4, 5, 12, 1, tzinfo=UTC),
                datetime(2026, 4, 6, 11, 58, tzinfo=UTC),
            )
        },
        window_started_at=datetime(2026, 4, 5, 12, 0, tzinfo=UTC),
        covered_until_at=datetime(2026, 4, 6, 12, 0, tzinfo=UTC),
        observed_at=live_tail_at,
    )

    persisted_state = tracker.to_persisted_state(persisted_at=live_tail_at)

    assert persisted_state.latest_observed_trade_at == live_tail_at


def test_historical_trade_backfill_reports_unavailable_progress() -> None:
    observed_at = datetime(2026, 4, 6, 12, 0, tzinfo=UTC)
    progress_updates: list[tuple[int, int]] = []
    service = BybitHistoricalTradeBackfillService(
        config=BybitHistoricalTradeBackfillConfig(contour="linear"),
        fetch_bytes=lambda _url, _timeout: (_ for _ in ()).throw(OSError("network down")),
    )

    result = service.load_window(
        symbols=("BTC/USDT",),
        observed_at=observed_at,
        progress_callback=lambda processed, total: progress_updates.append((processed, total)),
    )

    assert result.status == "unavailable"
    assert result.processed_archives == 0
    assert result.total_archives == 1
    assert progress_updates == [(0, 1)]


def test_historical_trade_backfill_treats_missing_latest_closed_linear_archive_as_skipped() -> None:
    observed_at = datetime(2026, 4, 7, 0, 16, tzinfo=UTC)
    service = BybitHistoricalTradeBackfillService(
        config=BybitHistoricalTradeBackfillConfig(contour="linear"),
        fetch_bytes=lambda _url, _timeout: (_ for _ in ()).throw(
            HTTPError(
                url="https://public.bybit.com/trading/BTCUSDT/BTCUSDT2026-04-06.csv.gz",
                code=404,
                msg="Not Found",
                hdrs=None,
                fp=None,
            )
        ),
    )

    result = service.load_window(
        symbols=("BTC/USDT",),
        observed_at=observed_at,
    )

    assert result.status == "skipped"
    assert result.processed_archives == 0
    assert result.total_archives == 1
    assert result.reason == "historical trade archive not found for linear:BTCUSDT:2026-04-06"


def test_historical_trade_backfill_treats_missing_latest_closed_spot_archive_as_skipped() -> None:
    observed_at = datetime(2026, 4, 7, 0, 16, tzinfo=UTC)
    service = BybitHistoricalTradeBackfillService(
        config=BybitHistoricalTradeBackfillConfig(contour="spot"),
        fetch_bytes=lambda _url, _timeout: (_ for _ in ()).throw(
            HTTPError(
                url="https://public.bybit.com/spot/BTCUSDT/BTCUSDT_2026-04-06.csv.gz",
                code=404,
                msg="Not Found",
                hdrs=None,
                fp=None,
            )
        ),
    )

    result = service.load_window(
        symbols=("BTC/USDT",),
        observed_at=observed_at,
    )

    assert result.status == "skipped"
    assert result.processed_archives == 0
    assert result.total_archives == 1
    assert result.reason == "historical trade archive not found for spot:BTCUSDT:2026-04-06"


def test_historical_trade_backfill_returns_partial_restore_when_latest_closed_day_missing() -> None:
    observed_at = datetime(2026, 4, 7, 12, 0, tzinfo=UTC)

    def fetch_bytes(url: str, _timeout: int) -> bytes:
        if url.endswith("BTCUSDT2026-04-05.csv.gz"):
            return _gzip_csv(
                "timestamp,price,qty\n"
                "2026-04-05T12:01:00+00:00,68000,0.1\n"
                "2026-04-05T18:00:00+00:00,68100,0.2\n"
            )
        raise HTTPError(url=url, code=404, msg="Not Found", hdrs=None, fp=None)

    service = BybitHistoricalTradeBackfillService(
        config=BybitHistoricalTradeBackfillConfig(contour="linear"),
        fetch_bytes=fetch_bytes,
    )
    original_build_archive_dates = service.load_window.__globals__["_build_archive_dates"]
    original_resolve_boundary = service.load_window.__globals__["_resolve_closed_archive_boundary"]
    service.load_window.__globals__["_build_archive_dates"] = lambda **_: (
        date(2026, 4, 5),
        date(2026, 4, 6),
    )
    service.load_window.__globals__["_resolve_closed_archive_boundary"] = lambda **_: datetime(
        2026,
        4,
        7,
        0,
        0,
        tzinfo=UTC,
    )

    try:
        result = service.load_window(
            symbols=("BTC/USDT",),
            observed_at=observed_at,
        )
    finally:
        service.load_window.__globals__["_build_archive_dates"] = original_build_archive_dates
        service.load_window.__globals__["_resolve_closed_archive_boundary"] = (
            original_resolve_boundary
        )

    assert result.status == "skipped"
    assert result.restored_window_started_at == datetime(2026, 4, 6, 12, 0, tzinfo=UTC)
    assert result.covered_until_at == datetime(2026, 4, 6, 0, 0, tzinfo=UTC)
    assert result.processed_archives == 1
    assert result.total_archives == 2
    assert result.trade_timestamps_by_symbol == {}
    assert result.trade_buckets_by_symbol == {"BTC/USDT": {}}
    assert result.reason == "historical trade archive not found for linear:BTCUSDT:2026-04-06"


def test_partial_historical_restore_applies_to_tracker_without_marking_unavailable() -> None:
    tracker = BybitDerivedTradeCountTracker(symbols=("BTC/USDT",))
    observed_at = datetime(2026, 4, 7, 12, 0, 30, tzinfo=UTC)
    tracker.note_trade(symbol="BTC/USDT", observed_at=observed_at)

    tracker.restore_historical_window(
        trades_by_symbol={"BTC/USDT": ()},
        window_started_at=datetime(2026, 4, 6, 12, 0, tzinfo=UTC),
        covered_until_at=datetime(2026, 4, 6, 0, 0, tzinfo=UTC),
        observed_at=observed_at,
        processed_archives=1,
        total_archives=2,
        status="skipped",
        reason="historical trade archive not found for linear:BTCUSDT:2026-04-06",
    )
    diagnostics = tracker.get_diagnostics(observed_at=observed_at)

    assert diagnostics.backfill_status == "skipped"
    assert diagnostics.backfill_processed_archives == 1
    assert diagnostics.backfill_total_archives == 2
    assert diagnostics.last_backfill_reason == (
        "historical trade archive not found for linear:BTCUSDT:2026-04-06"
    )
    assert diagnostics.state == "ready"
    assert diagnostics.ready is True


def test_historical_trade_backfill_reuses_cached_archive_payloads_across_retries() -> None:
    observed_at = datetime(2026, 4, 6, 12, 0, tzinfo=UTC)
    fetch_calls: list[str] = []

    def fetch_bytes(url: str, _timeout: int) -> bytes:
        fetch_calls.append(url)
        return _gzip_csv("timestamp,price,qty\n2026-04-05T12:01:00+00:00,68000,0.1\n")

    service = BybitHistoricalTradeBackfillService(
        config=BybitHistoricalTradeBackfillConfig(contour="linear"),
        fetch_bytes=fetch_bytes,
    )

    first = service.load_window(
        symbols=("BTC/USDT",),
        observed_at=observed_at,
    )
    second = service.load_window(
        symbols=("BTC/USDT",),
        observed_at=observed_at,
    )

    assert first.status == "backfilled"
    assert second.status == "backfilled"
    assert fetch_calls == ["https://public.bybit.com/trading/BTCUSDT/BTCUSDT2026-04-05.csv.gz"]


def test_historical_trade_backfill_reuses_disk_cached_archive_payloads_across_service_restarts() -> (
    None
):
    observed_at = datetime(2026, 4, 6, 12, 0, tzinfo=UTC)
    cache_dir = _make_local_temp_dir()
    fetch_calls: list[str] = []

    def fetch_bytes(url: str, _timeout: int) -> bytes:
        fetch_calls.append(url)
        return _gzip_csv("timestamp,price,qty\n2026-04-05T12:01:00+00:00,68000,0.1\n")

    first_service = BybitHistoricalTradeBackfillService(
        config=BybitHistoricalTradeBackfillConfig(contour="linear", cache_dir=cache_dir),
        fetch_bytes=fetch_bytes,
    )
    second_service = BybitHistoricalTradeBackfillService(
        config=BybitHistoricalTradeBackfillConfig(contour="linear", cache_dir=cache_dir),
        fetch_bytes=lambda _url, _timeout: (_ for _ in ()).throw(
            AssertionError("disk cache should serve archive payload after restart")
        ),
    )

    first = first_service.load_window(
        symbols=("BTC/USDT",),
        observed_at=observed_at,
    )
    second = second_service.load_window(
        symbols=("BTC/USDT",),
        observed_at=observed_at,
    )

    assert first.status == "backfilled"
    assert second.status == "backfilled"
    assert fetch_calls == ["https://public.bybit.com/trading/BTCUSDT/BTCUSDT2026-04-05.csv.gz"]
    first_cache = first_service.get_cache_diagnostics()
    second_cache = second_service.get_cache_diagnostics()
    assert first_cache.misses == 1
    assert first_cache.writes == 1
    assert second_cache.disk_hits == 1
    assert second_cache.last_hit_source == "disk"
    shutil.rmtree(cache_dir, ignore_errors=True)


def test_historical_trade_backfill_parallel_progress_updates_are_monotonic() -> None:
    observed_at = datetime(2026, 4, 6, 12, 0, tzinfo=UTC)
    progress_updates: list[tuple[int, int]] = []

    def fetch_bytes(url: str, _timeout: int) -> bytes:
        if "BTCUSDT" in url:
            time.sleep(0.03)
        else:
            time.sleep(0.005)
        return _gzip_csv("timestamp,price,qty\n2026-04-05T12:01:00+00:00,68000,0.1\n")

    service = BybitHistoricalTradeBackfillService(
        config=BybitHistoricalTradeBackfillConfig(contour="linear"),
        fetch_bytes=fetch_bytes,
    )

    result = service.load_window(
        symbols=("BTC/USDT", "ETH/USDT"),
        observed_at=observed_at,
        progress_callback=lambda processed, total: progress_updates.append((processed, total)),
    )

    assert result.status == "backfilled"
    assert progress_updates == [(0, 2), (1, 2), (2, 2)]


def test_historical_trade_backfill_collects_stage_timing_diagnostics() -> None:
    observed_at = datetime(2026, 4, 6, 12, 0, tzinfo=UTC)
    cache_dir = _make_local_temp_dir()

    service = BybitHistoricalTradeBackfillService(
        config=BybitHistoricalTradeBackfillConfig(contour="linear", cache_dir=cache_dir),
        fetch_bytes=lambda _url, _timeout: _gzip_csv(
            "timestamp,price,qty\n2026-04-05T12:01:00+00:00,68000,0.1\n"
        ),
    )

    result = service.load_window(
        symbols=("BTC/USDT",),
        observed_at=observed_at,
    )

    diagnostics = service.get_cache_diagnostics()

    assert result.status == "backfilled"
    assert diagnostics.last_network_fetch_ms is not None
    assert diagnostics.last_gzip_decode_ms is not None
    assert diagnostics.last_csv_parse_ms is not None
    assert diagnostics.last_archive_total_ms is not None
    assert diagnostics.last_symbol_total_ms is not None
    assert diagnostics.last_symbol == "BTC/USDT"
    assert diagnostics.total_network_fetch_ms >= diagnostics.last_network_fetch_ms
    assert diagnostics.total_gzip_decode_ms >= diagnostics.last_gzip_decode_ms
    assert diagnostics.total_csv_parse_ms >= diagnostics.last_csv_parse_ms
    assert diagnostics.total_archive_total_ms >= diagnostics.last_archive_total_ms
    assert diagnostics.total_symbol_total_ms >= diagnostics.last_symbol_total_ms
    shutil.rmtree(cache_dir, ignore_errors=True)


def test_historical_trade_backfill_filters_rows_inline_during_archive_parse() -> None:
    observed_at = datetime(2026, 4, 6, 12, 0, tzinfo=UTC)
    service = BybitHistoricalTradeBackfillService(
        config=BybitHistoricalTradeBackfillConfig(contour="linear"),
        fetch_bytes=lambda _url, _timeout: _gzip_csv(
            "timestamp,price,qty\n"
            "2026-04-05T11:59:00+00:00,68000,0.1\n"
            "2026-04-05T12:01:00+00:00,68010,0.2\n"
        ),
    )

    result = service.load_window(
        symbols=("BTC/USDT",),
        observed_at=observed_at,
    )

    assert result.status == "backfilled"
    assert result.backfilled_trade_count == 1
    assert result.trade_timestamps_by_symbol["BTC/USDT"] == ()
    assert result.trade_buckets_by_symbol["BTC/USDT"] == {
        datetime(2026, 4, 5, 12, 1, tzinfo=UTC): 1,
    }
    assert result.latest_trade_at_by_symbol["BTC/USDT"] == datetime(2026, 4, 5, 12, 1, tzinfo=UTC)


def test_historical_trade_backfill_resolves_timestamp_column_without_dict_reader() -> None:
    observed_at = datetime(2025, 4, 6, 12, 0, tzinfo=UTC)
    service = BybitHistoricalTradeBackfillService(
        config=BybitHistoricalTradeBackfillConfig(contour="linear"),
        fetch_bytes=lambda _url, _timeout: _gzip_csv(
            "price,trade_time_ms,qty\n68000,1743854460000,0.1\n"
        ),
    )

    result = service.load_window(
        symbols=("BTC/USDT",),
        observed_at=observed_at,
    )

    assert result.status == "backfilled"
    assert result.backfilled_trade_count == 1
    assert result.trade_buckets_by_symbol["BTC/USDT"] == {
        datetime(2025, 4, 5, 12, 1, tzinfo=UTC): 1,
    }


def test_historical_trade_backfill_parses_linear_decimal_second_timestamps() -> None:
    observed_at = datetime(2026, 4, 8, 12, 0, tzinfo=UTC)
    service = BybitHistoricalTradeBackfillService(
        config=BybitHistoricalTradeBackfillConfig(contour="linear"),
        fetch_bytes=lambda _url, _timeout: _gzip_csv(
            "timestamp,price,qty\n1775563261.2648,68000,0.1\n1775563261.9999,68000,0.2\n"
        ),
    )

    result = service.load_window(
        symbols=("BTC/USDT",),
        observed_at=observed_at,
    )

    assert result.status == "backfilled"
    assert result.backfilled_trade_count == 2
    assert result.trade_buckets_by_symbol["BTC/USDT"] == {
        datetime(2026, 4, 7, 12, 1, tzinfo=UTC): 2,
    }
    assert result.latest_trade_at_by_symbol["BTC/USDT"] == datetime(
        2026,
        4,
        7,
        12,
        1,
        1,
        999900,
        tzinfo=UTC,
    )


def test_historical_recovery_plan_exposes_closed_day_archive_units() -> None:
    service = BybitHistoricalTradeBackfillService(
        config=BybitHistoricalTradeBackfillConfig(contour="linear"),
        fetch_bytes=lambda _url, _timeout: b"",
    )

    plan = service.build_recovery_plan(
        symbols=("BTC/USDT", "ETH/USDT"),
        observed_at=datetime(2026, 4, 7, 12, 0, tzinfo=UTC),
        covered_until_at=datetime(2026, 4, 7, 12, 0, tzinfo=UTC),
    )

    assert plan.symbols == ("BTC/USDT", "ETH/USDT")
    assert plan.window_started_at == datetime(2026, 4, 6, 12, 0, tzinfo=UTC)
    assert plan.covered_until_at == datetime(2026, 4, 7, 0, 0, tzinfo=UTC)
    assert plan.archive_dates == (date(2026, 4, 6),)
    assert plan.total_archives == 2


def test_bybit_connector_operator_diagnostics_surface_recovery_coordinator_and_cache_truth() -> (
    None
):
    cache_dir = _make_local_temp_dir()
    service = BybitHistoricalTradeBackfillService(
        config=BybitHistoricalTradeBackfillConfig(contour="linear", cache_dir=cache_dir),
        fetch_bytes=lambda _url, _timeout: b"",
    )
    connector = BybitMarketDataConnector(
        session=_session("BTC/USDT"),
        market_data_runtime=create_market_data_runtime(
            event_bus=EnhancedEventBus(enable_persistence=False)
        ),
        universe_scope_mode=True,
        universe_min_trade_count_24h=2,
        historical_trade_backfill_service=service,
    )

    diagnostics = connector.get_operator_diagnostics()

    assert diagnostics["historical_recovery_state"] == "pending"
    assert diagnostics["historical_recovery_retry_pending"] is False
    assert diagnostics["historical_recovery_backfill_task_active"] is False
    assert diagnostics["archive_cache_enabled"] is True
    assert diagnostics["archive_cache_memory_hits"] == 0
    assert diagnostics["archive_cache_disk_hits"] == 0
    assert diagnostics["archive_cache_misses"] == 0
    assert diagnostics["archive_cache_writes"] == 0
    assert diagnostics["archive_cache_last_hit_source"] is None
    assert diagnostics["archive_cache_last_network_fetch_ms"] is None
    assert diagnostics["archive_cache_last_disk_read_ms"] is None
    assert diagnostics["archive_cache_last_gzip_decode_ms"] is None
    assert diagnostics["archive_cache_last_csv_parse_ms"] is None
    assert diagnostics["archive_cache_last_archive_total_ms"] is None
    assert diagnostics["archive_cache_last_symbol_total_ms"] is None
    assert diagnostics["archive_cache_last_symbol"] is None
    assert diagnostics["archive_cache_total_network_fetch_ms"] == 0
    assert diagnostics["archive_cache_total_disk_read_ms"] == 0
    assert diagnostics["archive_cache_total_gzip_decode_ms"] == 0
    assert diagnostics["archive_cache_total_csv_parse_ms"] == 0
    assert diagnostics["archive_cache_total_archive_total_ms"] == 0
    assert diagnostics["archive_cache_total_symbol_total_ms"] == 0
    shutil.rmtree(cache_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_latest_closed_day_skip_schedules_delayed_backfill_retry_until_archive_appears() -> (
    None
):
    event_bus = EnhancedEventBus(enable_persistence=False)
    market_data_runtime = create_market_data_runtime(event_bus=event_bus)
    await market_data_runtime.start()

    retry_sleep_entered = asyncio.Event()
    release_retry_sleep = asyncio.Event()
    load_window_calls = 0

    class _RetryingBackfillService:
        def build_recovery_plan(
            self,
            *,
            symbols: tuple[str, ...],
            observed_at: datetime,
            covered_until_at: datetime | None = None,
        ):
            normalized_covered_until_at = covered_until_at or observed_at
            return BybitHistoricalRecoveryPlan(
                symbols=symbols,
                window_started_at=normalized_covered_until_at - timedelta(hours=24),
                covered_until_at=normalized_covered_until_at,
                archive_dates=(date(2026, 4, 6),),
                total_archives=1,
            )

        def load_plan(
            self,
            *,
            plan,
            progress_callback=None,
        ) -> BybitHistoricalTradeBackfillResult:
            nonlocal load_window_calls
            load_window_calls += 1
            if load_window_calls == 1:
                return BybitHistoricalTradeBackfillResult(
                    status="skipped",
                    restored_window_started_at=None,
                    backfilled_trade_count=0,
                    hydrated_symbols=(),
                    source="bybit_public_archive",
                    covered_until_at=plan.covered_until_at,
                    trade_timestamps_by_symbol={},
                    reason="historical trade archive not found for linear:BTCUSDT:2026-04-06",
                    processed_archives=0,
                    total_archives=1,
                )
            return BybitHistoricalTradeBackfillResult(
                status="backfilled",
                restored_window_started_at=datetime(2026, 4, 6, 0, 0, tzinfo=UTC),
                backfilled_trade_count=1,
                hydrated_symbols=("BTC/USDT",),
                source="bybit_public_archive",
                covered_until_at=datetime(2026, 4, 7, 0, 0, tzinfo=UTC),
                trade_timestamps_by_symbol={"BTC/USDT": (datetime(2026, 4, 6, 12, 1, tzinfo=UTC),)},
                processed_archives=1,
                total_archives=1,
            )

    async def fake_sleep(delay: float) -> None:
        if delay == bybit_module._DEFAULT_LATEST_ARCHIVE_RETRY_DELAY_SECONDS:
            retry_sleep_entered.set()
            await release_retry_sleep.wait()

    connector = BybitMarketDataConnector(
        session=_session(),
        market_data_runtime=market_data_runtime,
        universe_scope_mode=True,
        universe_min_trade_count_24h=1,
        historical_trade_backfill_service=_RetryingBackfillService(),
        sleep_func=fake_sleep,
    )
    observed_at = datetime(2026, 4, 7, 0, 30, tzinfo=UTC)
    connector._historical_trade_backfill_cutoff_at = observed_at

    original_utcnow = connector._maybe_restore_historical_trade_count.__globals__["_utcnow"]
    connector._maybe_restore_historical_trade_count.__globals__["_utcnow"] = lambda: observed_at
    try:
        await connector._maybe_restore_historical_trade_count()
        await asyncio.wait_for(retry_sleep_entered.wait(), timeout=1.0)

        skipped = connector.get_operator_diagnostics()
        assert skipped["derived_trade_count_backfill_status"] == "skipped"
        assert connector._latest_archive_backfill_retry_pending is True
        assert connector._historical_trade_backfill_pending is True
        assert connector._historical_trade_backfill_retry_task is not None

        release_retry_sleep.set()
        for _ in range(20):
            if load_window_calls >= 2 and connector._historical_trade_backfill_task is None:
                break
            await asyncio.sleep(0)
        else:
            pytest.fail("delayed backfill retry did not execute a second archive load")

        restored = connector.get_operator_diagnostics()
        assert restored["derived_trade_count_backfill_status"] == "backfilled"
        assert connector._latest_archive_backfill_retry_pending is False
        assert connector._historical_trade_backfill_pending is False
        assert load_window_calls == 2
    finally:
        connector._maybe_restore_historical_trade_count.__globals__["_utcnow"] = original_utcnow
        if connector._historical_trade_backfill_retry_task is not None:
            connector._historical_trade_backfill_retry_task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await connector._historical_trade_backfill_retry_task


@pytest.mark.asyncio
async def test_non_retriable_backfill_skip_does_not_schedule_delayed_retry() -> None:
    event_bus = EnhancedEventBus(enable_persistence=False)
    market_data_runtime = create_market_data_runtime(event_bus=event_bus)
    await market_data_runtime.start()

    class _NoClosedArchiveService:
        def build_recovery_plan(
            self,
            *,
            symbols: tuple[str, ...],
            observed_at: datetime,
            covered_until_at: datetime | None = None,
        ):
            normalized_covered_until_at = covered_until_at or observed_at
            return BybitHistoricalRecoveryPlan(
                symbols=symbols,
                window_started_at=normalized_covered_until_at - timedelta(hours=24),
                covered_until_at=normalized_covered_until_at,
                archive_dates=(),
                total_archives=0,
            )

        def load_plan(
            self,
            *,
            plan,
            progress_callback=None,
        ) -> BybitHistoricalTradeBackfillResult:
            return BybitHistoricalTradeBackfillResult(
                status="skipped",
                restored_window_started_at=datetime(2026, 4, 6, 0, 0, tzinfo=UTC),
                backfilled_trade_count=0,
                hydrated_symbols=("BTC/USDT",),
                source="bybit_public_archive",
                covered_until_at=plan.covered_until_at,
                trade_timestamps_by_symbol={"BTC/USDT": ()},
                reason="no_closed_archives_required",
                processed_archives=0,
                total_archives=0,
            )

    connector = BybitMarketDataConnector(
        session=_session(),
        market_data_runtime=market_data_runtime,
        universe_scope_mode=True,
        universe_min_trade_count_24h=1,
        historical_trade_backfill_service=_NoClosedArchiveService(),
        sleep_func=lambda _delay: asyncio.sleep(0),
    )
    observed_at = datetime(2026, 4, 7, 0, 30, tzinfo=UTC)
    connector._historical_trade_backfill_cutoff_at = observed_at

    original_utcnow = connector._maybe_restore_historical_trade_count.__globals__["_utcnow"]
    connector._maybe_restore_historical_trade_count.__globals__["_utcnow"] = lambda: observed_at
    try:
        await connector._maybe_restore_historical_trade_count()
    finally:
        connector._maybe_restore_historical_trade_count.__globals__["_utcnow"] = original_utcnow

    assert connector._latest_archive_backfill_retry_pending is False
    assert connector._historical_trade_backfill_pending is False
    assert connector._historical_trade_backfill_retry_task is None


def test_historical_trade_backfill_skips_current_day_archive_when_it_is_not_closed() -> None:
    observed_at = datetime(2026, 4, 6, 12, 0, tzinfo=UTC)
    requested_urls: list[str] = []
    service = BybitHistoricalTradeBackfillService(
        config=BybitHistoricalTradeBackfillConfig(contour="linear"),
        fetch_bytes=lambda url, _timeout: (
            requested_urls.append(url)
            or _gzip_csv("timestamp,price,qty\n2026-04-05T12:01:00+00:00,68000,0.1\n")
        ),
    )

    result = service.load_window(
        symbols=("BTC/USDT",),
        observed_at=observed_at,
    )

    assert result.status == "backfilled"
    assert result.processed_archives == 1
    assert result.total_archives == 1
    assert requested_urls == ["https://public.bybit.com/trading/BTCUSDT/BTCUSDT2026-04-05.csv.gz"]


def test_historical_trade_backfill_without_live_tail_keeps_trade_count_warming_up() -> None:
    observed_at = datetime(2026, 4, 6, 12, 0, tzinfo=UTC)
    tracker = BybitDerivedTradeCountTracker(symbols=("BTC/USDT",))
    service = BybitHistoricalTradeBackfillService(
        config=BybitHistoricalTradeBackfillConfig(contour="linear"),
        fetch_bytes=lambda _url, _timeout: _gzip_csv(
            "timestamp,price,qty\n2026-04-05T12:01:00+00:00,68000,0.1\n"
        ),
    )

    result = service.load_window(
        symbols=("BTC/USDT",),
        observed_at=observed_at,
    )
    tracker.restore_historical_window(
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
    diagnostics = tracker.get_diagnostics(observed_at=observed_at)

    assert result.status == "backfilled"
    assert diagnostics.state == "warming_up"
    assert diagnostics.ready is False


def test_gap_after_restored_historical_window_requires_only_post_gap_live_tail() -> None:
    tracker = BybitDerivedTradeCountTracker(symbols=("BTC/USDT",))
    live_tail_at = datetime(2026, 4, 6, 12, 0, 30, tzinfo=UTC)
    tracker.note_trade(symbol="BTC/USDT", observed_at=live_tail_at)
    tracker.restore_historical_window(
        trades_by_symbol={
            "BTC/USDT": (
                datetime(2026, 4, 5, 12, 1, tzinfo=UTC),
                datetime(2026, 4, 6, 11, 58, tzinfo=UTC),
            )
        },
        window_started_at=datetime(2026, 4, 5, 12, 0, tzinfo=UTC),
        covered_until_at=datetime(2026, 4, 6, 12, 0, tzinfo=UTC),
        observed_at=live_tail_at,
    )

    ready_before_gap = tracker.get_diagnostics(observed_at=live_tail_at)
    gap_at = datetime(2026, 4, 6, 12, 5, tzinfo=UTC)
    tracker.mark_gap_preserving_historical_window(observed_at=gap_at, reason="transport_gap")

    after_gap = tracker.get_diagnostics(observed_at=gap_at)
    resumed_at = gap_at + timedelta(seconds=5)
    tracker.mark_observation_started(observed_at=resumed_at)
    tracker.note_trade(symbol="BTC/USDT", observed_at=resumed_at)
    resumed = tracker.get_diagnostics(observed_at=resumed_at)

    assert ready_before_gap.ready is True
    assert after_gap.state == "not_reliable_after_gap"
    assert after_gap.ready is False
    assert after_gap.observation_started_at == datetime(2026, 4, 5, 12, 0, tzinfo=UTC).isoformat()
    assert after_gap.reliable_after == gap_at.isoformat()
    assert resumed.state == "ready"
    assert resumed.ready is True
    assert resumed.reliable_after == datetime(2026, 4, 6, 12, 0, tzinfo=UTC).isoformat()


def test_historical_backfill_ready_window_does_not_require_extra_day_after_disconnect() -> None:
    tracker = BybitDerivedTradeCountTracker(symbols=("BTC/USDT",))
    restored_at = datetime(2026, 4, 7, 12, 0, 30, tzinfo=UTC)
    tracker.note_trade(symbol="BTC/USDT", observed_at=restored_at)
    tracker.restore_historical_window(
        trades_by_symbol={
            "BTC/USDT": (
                datetime(2026, 4, 6, 12, 1, tzinfo=UTC),
                datetime(2026, 4, 7, 11, 58, tzinfo=UTC),
            )
        },
        window_started_at=datetime(2026, 4, 6, 12, 0, tzinfo=UTC),
        covered_until_at=datetime(2026, 4, 7, 12, 0, tzinfo=UTC),
        observed_at=restored_at,
        processed_archives=1,
        total_archives=1,
    )

    disconnect_at = datetime(2026, 4, 7, 12, 3, tzinfo=UTC)
    tracker.mark_gap_preserving_historical_window(
        observed_at=disconnect_at,
        reason="reconnect_gap",
    )
    tracker.mark_observation_started(observed_at=disconnect_at + timedelta(seconds=1))
    tracker.note_trade(
        symbol="BTC/USDT",
        observed_at=disconnect_at + timedelta(seconds=2),
    )
    diagnostics = tracker.get_diagnostics(observed_at=disconnect_at + timedelta(seconds=2))

    assert diagnostics.backfill_status == "backfilled"
    assert diagnostics.ready is True
    assert diagnostics.state == "ready"
    assert diagnostics.reliable_after == datetime(2026, 4, 7, 12, 0, tzinfo=UTC).isoformat()


def test_derived_trade_count_tracker_marks_not_needed_backfill() -> None:
    observed_at = datetime(2026, 4, 6, 12, 0, tzinfo=UTC)
    tracker = BybitDerivedTradeCountTracker(symbols=("BTC/USDT",))

    tracker.mark_backfill_not_needed()
    diagnostics = tracker.get_diagnostics(observed_at=observed_at)

    assert diagnostics.backfill_status == "not_needed"
    assert diagnostics.backfill_needed is False
    assert diagnostics.backfill_processed_archives is None
    assert diagnostics.backfill_total_archives is None
    assert diagnostics.backfill_progress_percent is None


def test_derived_trade_count_tracker_reports_running_backfill_progress() -> None:
    observed_at = datetime(2026, 4, 6, 12, 0, tzinfo=UTC)
    tracker = BybitDerivedTradeCountTracker(symbols=("BTC/USDT",))

    tracker.mark_backfill_running(processed_archives=7, total_archives=12)
    diagnostics = tracker.get_diagnostics(observed_at=observed_at)

    assert diagnostics.backfill_status == "running"
    assert diagnostics.backfill_needed is True
    assert diagnostics.backfill_processed_archives == 7
    assert diagnostics.backfill_total_archives == 12
    assert diagnostics.backfill_progress_percent == 58


def test_derived_trade_count_tracker_reports_unavailable_backfill_progress() -> None:
    observed_at = datetime(2026, 4, 6, 12, 0, tzinfo=UTC)
    tracker = BybitDerivedTradeCountTracker(symbols=("BTC/USDT",))

    tracker.mark_backfill_unavailable(
        observed_at=observed_at,
        reason="archive unavailable",
        processed_archives=1,
        total_archives=3,
    )
    diagnostics = tracker.get_diagnostics(observed_at=observed_at)

    assert diagnostics.backfill_status == "unavailable"
    assert diagnostics.backfill_needed is True
    assert diagnostics.backfill_processed_archives == 1
    assert diagnostics.backfill_total_archives == 3
    assert diagnostics.backfill_progress_percent == 33
    assert diagnostics.last_backfill_reason == "archive unavailable"


@pytest.mark.asyncio
async def test_bybit_connector_connect_path_does_not_wait_for_historical_backfill() -> None:
    event_bus = EnhancedEventBus(enable_persistence=False)
    market_data_runtime = create_market_data_runtime(event_bus=event_bus)
    await market_data_runtime.start()

    websocket = _BlockingWebSocket()

    async def websocket_factory(_: BybitMarketDataConnectorConfig) -> _BlockingWebSocket:
        return websocket

    def slow_fetch(_url: str, _timeout: int) -> bytes:
        time.sleep(0.2)
        return _gzip_csv("timestamp,price,qty\n2026-04-05T12:01:00+00:00,68000,0.1\n")

    connector = BybitMarketDataConnector(
        session=_session(),
        market_data_runtime=market_data_runtime,
        websocket_factory=websocket_factory,
        historical_trade_backfill_service=BybitHistoricalTradeBackfillService(
            config=BybitHistoricalTradeBackfillConfig(contour="linear"),
            fetch_bytes=slow_fetch,
        ),
    )

    task = asyncio.create_task(connector.run(max_cycles=1))
    await asyncio.sleep(0.05)

    assert websocket.sent_messages
    assert json.loads(websocket.sent_messages[0])["op"] == "subscribe"

    await connector.stop()
    await asyncio.wait_for(task, timeout=1.0)


@pytest.mark.asyncio
async def test_bybit_connector_backfill_progress_updates_stay_on_event_loop_thread() -> None:
    event_bus = EnhancedEventBus(enable_persistence=False)
    market_data_runtime = create_market_data_runtime(event_bus=event_bus)
    await market_data_runtime.start()

    observed_at = datetime(2026, 4, 6, 12, 0, tzinfo=UTC)
    archives = {
        "https://public.bybit.com/trading/BTCUSDT/BTCUSDT2026-04-05.csv.gz": _gzip_csv(
            "timestamp,price,qty\n2026-04-05T12:01:00+00:00,68000,0.1\n"
        ),
    }
    worker_thread_ids: list[int] = []
    update_thread_ids: list[int] = []
    original_progress_updater = BybitMarketDataConnector._update_historical_backfill_progress

    def fetch_bytes(url: str, _timeout: int) -> bytes:
        worker_thread_ids.append(threading.get_ident())
        return archives[url]

    def tracking_progress_updater(
        self: BybitMarketDataConnector,
        processed_archives: int,
        total_archives: int,
    ) -> None:
        update_thread_ids.append(threading.get_ident())
        original_progress_updater(self, processed_archives, total_archives)

    service = BybitHistoricalTradeBackfillService(
        config=BybitHistoricalTradeBackfillConfig(contour="linear"),
        fetch_bytes=fetch_bytes,
    )
    connector = BybitMarketDataConnector(
        session=_session(),
        market_data_runtime=market_data_runtime,
        universe_scope_mode=True,
        universe_min_trade_count_24h=1,
        historical_trade_backfill_service=service,
    )
    connector._historical_trade_backfill_cutoff_at = observed_at

    original_utcnow = connector._maybe_restore_historical_trade_count.__globals__["_utcnow"]
    connector._maybe_restore_historical_trade_count.__globals__["_utcnow"] = lambda: observed_at
    loop_thread_id = threading.get_ident()
    try:
        with pytest.MonkeyPatch.context() as monkeypatch:
            monkeypatch.setattr(
                BybitMarketDataConnector,
                "_update_historical_backfill_progress",
                tracking_progress_updater,
            )
            await connector._maybe_restore_historical_trade_count()
    finally:
        connector._maybe_restore_historical_trade_count.__globals__["_utcnow"] = original_utcnow

    assert worker_thread_ids
    assert all(thread_id != loop_thread_id for thread_id in worker_thread_ids)
    assert update_thread_ids
    assert all(thread_id == loop_thread_id for thread_id in update_thread_ids)


@pytest.mark.asyncio
async def test_bybit_connector_disconnect_does_not_cancel_running_backfill_task() -> None:
    event_bus = EnhancedEventBus(enable_persistence=False)
    market_data_runtime = create_market_data_runtime(event_bus=event_bus)
    await market_data_runtime.start()

    websocket = _FakeWebSocket([])
    sleep_entered = asyncio.Event()
    release_sleep = asyncio.Event()

    async def websocket_factory(_: BybitMarketDataConnectorConfig) -> _FakeWebSocket:
        return websocket

    async def fake_sleep(_: float) -> None:
        sleep_entered.set()
        await release_sleep.wait()

    def slow_fetch(_url: str, _timeout: int) -> bytes:
        time.sleep(0.5)
        return _gzip_csv("timestamp,price,qty\n2026-04-05T12:01:00+00:00,68000,0.1\n")

    connector = BybitMarketDataConnector(
        session=_session(),
        market_data_runtime=market_data_runtime,
        websocket_factory=websocket_factory,
        sleep_func=fake_sleep,
        universe_scope_mode=True,
        universe_min_trade_count_24h=1,
        historical_trade_backfill_service=BybitHistoricalTradeBackfillService(
            config=BybitHistoricalTradeBackfillConfig(contour="linear"),
            fetch_bytes=slow_fetch,
        ),
    )

    run_task = asyncio.create_task(connector.run(max_cycles=2))
    await asyncio.wait_for(sleep_entered.wait(), timeout=1.0)

    assert connector._historical_trade_backfill_task is not None
    assert connector._historical_trade_backfill_task.done() is False

    release_sleep.set()
    await connector.stop()
    await asyncio.wait_for(run_task, timeout=2.0)


@pytest.mark.asyncio
async def test_bybit_connector_connect_timeout_does_not_hang_in_connecting_state() -> None:
    event_bus = EnhancedEventBus(enable_persistence=False)
    market_data_runtime = create_market_data_runtime(event_bus=event_bus)
    await market_data_runtime.start()

    connect_started = asyncio.Event()

    async def hanging_websocket_factory(_: BybitMarketDataConnectorConfig) -> _FakeWebSocket:
        connect_started.set()
        await asyncio.sleep(3600)
        raise RuntimeError("unreachable")

    connector = BybitMarketDataConnector(
        session=_session(),
        market_data_runtime=market_data_runtime,
        config=BybitMarketDataConnectorConfig(ping_timeout_seconds=0.05),
        websocket_factory=hanging_websocket_factory,
        sleep_func=lambda _seconds: asyncio.sleep(0),
    )

    try:
        run_task = asyncio.create_task(connector.run())
        await asyncio.wait_for(connect_started.wait(), timeout=1.0)
        for _ in range(20):
            diagnostics = connector.feed_runtime.get_runtime_diagnostics()
            if (
                diagnostics["retry_count"] == 1
                and diagnostics["last_disconnect_reason"] is not None
            ):
                break
            await asyncio.sleep(0.05)
        else:
            pytest.fail("connect timeout did not transition connector into disconnect/retry path")
    finally:
        await connector.stop()
        run_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(run_task, timeout=1.0)

    diagnostics = connector.feed_runtime.get_runtime_diagnostics()

    assert diagnostics["status"] == "disconnected"
    assert diagnostics["last_disconnect_reason"] is not None
    assert diagnostics["retry_count"] == 1


@pytest.mark.parametrize(
    ("universe_scope_mode", "universe_min_trade_count_24h"),
    (
        (False, 0),
        (True, 0),
    ),
)
@pytest.mark.asyncio
async def test_bybit_connector_disconnect_preserves_not_needed_backfill_status(
    universe_scope_mode: bool,
    universe_min_trade_count_24h: int,
) -> None:
    event_bus = EnhancedEventBus(enable_persistence=False)
    market_data_runtime = create_market_data_runtime(event_bus=event_bus)
    await market_data_runtime.start()

    connector = BybitMarketDataConnector(
        session=_session(),
        market_data_runtime=market_data_runtime,
        universe_scope_mode=universe_scope_mode,
        universe_min_trade_count_24h=universe_min_trade_count_24h,
    )

    await connector.feed_runtime.start(observed_at=datetime(2026, 4, 6, 12, 0, tzinfo=UTC))
    await connector._handle_disconnect(reason="transport_gap")
    diagnostics = connector.get_operator_diagnostics()

    assert diagnostics["derived_trade_count_backfill_status"] == "not_needed"
    assert diagnostics["derived_trade_count_backfill_needed"] is False


def test_estimate_historical_backfill_archive_units_excludes_current_unfinished_day() -> None:
    covered_until_at = datetime(2026, 4, 6, 12, 0, tzinfo=UTC)

    total_archives = bybit_module._estimate_historical_backfill_archive_units(
        symbols=("BTC/USDT", "ETH/USDT"),
        covered_until_at=covered_until_at,
    )

    assert total_archives == 2


def test_parser_requires_fresh_snapshot_after_recovery_reset() -> None:
    parser = BybitMarketDataParser(max_orderbook_levels=5)

    parser.parse_message(_orderbook_snapshot_message())
    parser.invalidate_orderbook_state(symbols=("BTC/USDT",))

    assert parser.parse_message(_orderbook_delta_message()) == ()

    rebuilt = parser.parse_message(_orderbook_snapshot_message())
    assert rebuilt[0].transport_payload["bids"][0]["price"] == "68000.0"
    assert parser.awaiting_snapshot_symbols() == ()


@pytest.mark.asyncio
async def test_bybit_connector_subscribes_and_ingests_real_market_data_path() -> None:
    event_bus = EnhancedEventBus(enable_persistence=False)
    market_data_runtime = create_market_data_runtime(event_bus=event_bus)
    await market_data_runtime.start()

    websocket = _FakeWebSocket(
        [
            json.dumps({"op": "subscribe", "success": True}),
            json.dumps(_trade_message()),
            json.dumps(_orderbook_snapshot_message()),
        ]
    )

    async def websocket_factory(_: BybitMarketDataConnectorConfig) -> _FakeWebSocket:
        return websocket

    sleep_delays: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleep_delays.append(delay)

    connector = BybitMarketDataConnector(
        session=_session(),
        market_data_runtime=market_data_runtime,
        websocket_factory=websocket_factory,
        sleep_func=fake_sleep,
    )

    await connector.run(max_cycles=1)

    orderbook = market_data_runtime.orderbook_manager.get_snapshot("BTC/USDT", "bybit")
    assert orderbook is not None
    assert orderbook.bids[0].price == Decimal("68000.0")
    assert market_data_runtime.state.last_trade_at[("BTC/USDT", "bybit")] is not None
    assert websocket.closed is True
    assert websocket.sent_messages
    subscribe_payload = json.loads(websocket.sent_messages[0])
    assert subscribe_payload["op"] == "subscribe"
    assert "publicTrade.BTCUSDT" in subscribe_payload["args"]
    assert "orderbook.50.BTCUSDT" in subscribe_payload["args"]
    assert sleep_delays == [5]


@pytest.mark.asyncio
async def test_bybit_connector_measures_transport_rtt_via_ping_pong() -> None:
    event_bus = EnhancedEventBus(enable_persistence=False)
    market_data_runtime = create_market_data_runtime(event_bus=event_bus)
    await market_data_runtime.start()

    websocket = _FakeWebSocket([])

    connector = BybitMarketDataConnector(
        session=_session(),
        market_data_runtime=market_data_runtime,
    )
    connector._active_websocket = websocket

    async def fake_sleep(_: float) -> None:
        connector._stop_requested = True

    connector._sleep_func = fake_sleep

    async def fake_measure_transport_rtt(_: _FakeWebSocket) -> float | None:
        return 0.018

    async def fake_await_application_pong(_: _FakeWebSocket) -> float:
        return 0.041

    connector._measure_transport_rtt = fake_measure_transport_rtt  # type: ignore[method-assign]
    connector._await_application_pong = fake_await_application_pong  # type: ignore[method-assign]

    await connector._monitor_transport_rtt(websocket)

    assert connector.get_operator_diagnostics()["transport_rtt_ms"] == 18
    assert connector.get_operator_diagnostics()["application_heartbeat_latency_ms"] == 41


@pytest.mark.asyncio
async def test_bybit_connector_ping_timeout_closes_websocket() -> None:
    event_bus = EnhancedEventBus(enable_persistence=False)
    market_data_runtime = create_market_data_runtime(event_bus=event_bus)
    await market_data_runtime.start()

    websocket = _SlowPongWebSocket()

    connector = BybitMarketDataConnector(
        session=_session(),
        market_data_runtime=market_data_runtime,
        config=BybitMarketDataConnectorConfig(
            ping_interval_seconds=0.01,
            ping_timeout_seconds=0.2,
        ),
    )
    connector._active_websocket = websocket
    timeouts_remaining = 2

    async def fake_await_application_pong(_: _SlowPongWebSocket) -> float:
        nonlocal timeouts_remaining
        if timeouts_remaining > 0:
            timeouts_remaining -= 1
            raise TimeoutError
        return 0.0

    connector._await_application_pong = fake_await_application_pong  # type: ignore[method-assign]

    await connector._monitor_transport_rtt(websocket)

    assert websocket.closed is True
    assert connector._consume_disconnect_reason(RuntimeError("transport_closed")) == "ping_timeout"


@pytest.mark.asyncio
async def test_bybit_connector_rtt_monitor_glitch_does_not_close_websocket() -> None:
    event_bus = EnhancedEventBus(enable_persistence=False)
    market_data_runtime = create_market_data_runtime(event_bus=event_bus)
    await market_data_runtime.start()

    websocket = _BrokenPingWebSocket([])

    connector = BybitMarketDataConnector(
        session=_session(),
        market_data_runtime=market_data_runtime,
    )
    connector._active_websocket = websocket

    async def fake_await_application_pong(_: _BrokenPingWebSocket) -> float:
        raise RuntimeError("temporary_ping_glitch")

    connector._await_application_pong = fake_await_application_pong  # type: ignore[method-assign]

    await connector._monitor_transport_rtt(websocket)

    assert websocket.closed is False
    assert connector.get_operator_diagnostics()["transport_rtt_ms"] is None
    assert connector.get_operator_diagnostics()["application_heartbeat_latency_ms"] is None


@pytest.mark.asyncio
async def test_bybit_connector_recent_inbound_messages_suppress_ping_timeout_disconnect() -> None:
    event_bus = EnhancedEventBus(enable_persistence=False)
    market_data_runtime = create_market_data_runtime(event_bus=event_bus)
    await market_data_runtime.start()

    websocket = _SlowPongWebSocket()

    connector = BybitMarketDataConnector(
        session=_session(),
        market_data_runtime=market_data_runtime,
        config=BybitMarketDataConnectorConfig(
            ping_interval_seconds=0.01,
            ping_timeout_seconds=0.2,
        ),
    )
    connector._active_websocket = websocket
    connector._last_transport_message_at = datetime.now(tz=UTC)

    async def fake_await_application_pong(_: _SlowPongWebSocket) -> float:
        raise TimeoutError

    connector._await_application_pong = fake_await_application_pong  # type: ignore[method-assign]

    async def fake_sleep(_: float) -> None:
        connector._stop_requested = True

    connector._sleep_func = fake_sleep

    await connector._monitor_transport_rtt(websocket)

    diagnostics = connector.get_operator_diagnostics()
    assert websocket.closed is False
    assert diagnostics["last_ping_timeout_ignored_due_to_recent_messages"] is True
    assert diagnostics["last_ping_timeout_message_age_ms"] is not None


def test_bybit_application_pong_message_detection() -> None:
    assert bybit_module._is_bybit_application_pong_message({"op": "pong"}) is True
    assert (
        bybit_module._is_bybit_application_pong_message({"op": "ping", "ret_msg": "pong"}) is True
    )
    assert (
        bybit_module._is_bybit_application_pong_message({"op": "subscribe", "success": True})
        is False
    )


@pytest.mark.asyncio
async def test_bybit_connector_transport_rtt_probe_failure_does_not_replace_heartbeat_latency() -> (
    None
):
    event_bus = EnhancedEventBus(enable_persistence=False)
    market_data_runtime = create_market_data_runtime(event_bus=event_bus)
    await market_data_runtime.start()

    websocket = _BrokenPingWebSocket([])

    connector = BybitMarketDataConnector(
        session=_session(),
        market_data_runtime=market_data_runtime,
    )
    connector._active_websocket = websocket

    async def fake_sleep(_: float) -> None:
        connector._stop_requested = True

    async def fake_await_application_pong(_: _BrokenPingWebSocket) -> float:
        return 0.077

    connector._sleep_func = fake_sleep
    connector._await_application_pong = fake_await_application_pong  # type: ignore[method-assign]

    await connector._monitor_transport_rtt(websocket)

    diagnostics = connector.get_operator_diagnostics()
    assert diagnostics["transport_rtt_ms"] is None
    assert diagnostics["application_heartbeat_latency_ms"] == 77


@pytest.mark.asyncio
async def test_bybit_connector_transport_rtt_probe_failure_keeps_last_successful_rtt() -> None:
    event_bus = EnhancedEventBus(enable_persistence=False)
    market_data_runtime = create_market_data_runtime(event_bus=event_bus)
    await market_data_runtime.start()

    websocket = _BrokenPingWebSocket([])

    connector = BybitMarketDataConnector(
        session=_session(),
        market_data_runtime=market_data_runtime,
    )
    connector._active_websocket = websocket
    connector._transport_rtt_ms = 18

    async def fake_sleep(_: float) -> None:
        connector._stop_requested = True

    async def fake_await_application_pong(_: _BrokenPingWebSocket) -> float:
        return 0.077

    connector._sleep_func = fake_sleep
    connector._await_application_pong = fake_await_application_pong  # type: ignore[method-assign]

    await connector._monitor_transport_rtt(websocket)

    diagnostics = connector.get_operator_diagnostics()
    assert diagnostics["transport_rtt_ms"] == 18
    assert diagnostics["application_heartbeat_latency_ms"] == 77


def test_format_disconnect_reason_normalizes_transport_close_noise() -> None:
    reason = bybit_module._format_disconnect_reason(
        RuntimeError("sent 1000 (OK); no close frame received")
    )

    assert reason == "transport_lost"


@pytest.mark.asyncio
async def test_bybit_connector_marks_feed_degraded_after_disconnect() -> None:
    event_bus = EnhancedEventBus(enable_persistence=False)
    market_data_runtime = create_market_data_runtime(event_bus=event_bus)
    await market_data_runtime.start()

    websocket = _FakeWebSocket([json.dumps({"op": "subscribe", "success": True})])

    async def websocket_factory(_: BybitMarketDataConnectorConfig) -> _FakeWebSocket:
        return websocket

    async def fake_sleep(_: float) -> None:
        return None

    connector = BybitMarketDataConnector(
        session=_session(),
        market_data_runtime=market_data_runtime,
        websocket_factory=websocket_factory,
        sleep_func=fake_sleep,
    )

    await connector.run(max_cycles=1)

    diagnostics = connector.feed_runtime.get_runtime_diagnostics()
    assert diagnostics["last_disconnect_reason"] == "transport_closed"
    assert diagnostics["retry_count"] == 1
    recovery_state = connector.get_recovery_state()
    assert recovery_state.status == FeedSubscriptionRecoveryStatus.RECOVERY_REQUIRED
    assert recovery_state.reset_required is True
    assert recovery_state.metadata["awaiting_snapshot_symbols"] == ("BTC/USDT",)


@pytest.mark.asyncio
async def test_bybit_connector_applies_post_readiness_narrowing_in_universe_mode() -> None:
    event_bus = EnhancedEventBus(enable_persistence=False)
    market_data_runtime = create_market_data_runtime(event_bus=event_bus)
    await market_data_runtime.start()

    websocket = _FakeWebSocket([])
    connector = BybitMarketDataConnector(
        session=_session("BTC/USDT", "ETH/USDT"),
        market_data_runtime=market_data_runtime,
        universe_scope_mode=True,
        universe_min_trade_count_24h=2,
    )
    await connector.feed_runtime.start(observed_at=connector.get_recovery_state().observed_at)
    connector.feed_runtime.mark_connected(observed_at=connector.get_recovery_state().observed_at)
    connector._active_websocket = websocket
    started_at = datetime(2026, 4, 5, 12, 0, tzinfo=UTC)
    eth_timestamp = started_at + timedelta(minutes=2)
    market_data_runtime.orderbook_manager.apply_snapshot(
        symbol="ETH/USDT",
        exchange="bybit",
        timestamp=eth_timestamp,
        bids=(OrderBookLevel(price=Decimal("3500.0"), quantity=Decimal("2.0")),),
        asks=(OrderBookLevel(price=Decimal("3500.5"), quantity=Decimal("2.5")),),
    )
    market_data_runtime.state.last_trade_at[("ETH/USDT", "bybit")] = eth_timestamp

    connector._derived_trade_count.note_trade(
        symbol="BTC/USDT",
        observed_at=started_at + timedelta(minutes=1),
    )
    connector._derived_trade_count.note_trade(
        symbol="ETH/USDT",
        observed_at=started_at + timedelta(minutes=2),
    )
    connector._derived_trade_count.note_trade(
        symbol="BTC/USDT",
        observed_at=started_at + timedelta(minutes=3),
    )
    connector._derived_trade_count._state = "ready"
    original_narrow_utcnow = connector._maybe_apply_post_readiness_narrowing.__globals__["_utcnow"]
    original_diag_utcnow = connector.get_operator_diagnostics.__globals__["_utcnow"]
    connector._maybe_apply_post_readiness_narrowing.__globals__["_utcnow"] = lambda: (
        started_at + timedelta(minutes=4)
    )
    connector.get_operator_diagnostics.__globals__["_utcnow"] = lambda: (
        started_at + timedelta(minutes=4)
    )
    try:
        await connector._maybe_apply_post_readiness_narrowing()
        diagnostics = connector.get_operator_diagnostics()
    finally:
        connector._maybe_apply_post_readiness_narrowing.__globals__["_utcnow"] = (
            original_narrow_utcnow
        )
        connector.get_operator_diagnostics.__globals__["_utcnow"] = original_diag_utcnow

    assert diagnostics["derived_trade_count_ready"] is True
    assert diagnostics["symbols"] == ("BTC/USDT",)
    assert diagnostics["symbol_snapshots"][0]["symbol"] == "BTC/USDT"
    assert market_data_runtime.orderbook_manager.get_snapshot("ETH/USDT", "bybit") is None
    assert ("ETH/USDT", "bybit") not in market_data_runtime.state.last_trade_at
    assert connector.get_recovery_state().status == FeedSubscriptionRecoveryStatus.RESUBSCRIBING
    assert connector.get_recovery_state().metadata["subscription_registry"] == ("BTC/USDT",)
    assert connector.get_recovery_assessment().session.subscription_scope == ("BTC/USDT",)
    assert len(websocket.sent_messages) == 2
    assert json.loads(websocket.sent_messages[0]) == {
        "op": "unsubscribe",
        "args": [
            "publicTrade.BTCUSDT",
            "orderbook.50.BTCUSDT",
            "publicTrade.ETHUSDT",
            "orderbook.50.ETHUSDT",
        ],
    }
    assert json.loads(websocket.sent_messages[1]) == {
        "op": "subscribe",
        "args": [
            "publicTrade.BTCUSDT",
            "orderbook.50.BTCUSDT",
        ],
    }


@pytest.mark.asyncio
async def test_bybit_connector_clears_active_scope_when_no_symbols_qualify_after_trade_count_ready() -> (
    None
):
    event_bus = EnhancedEventBus(enable_persistence=False)
    market_data_runtime = create_market_data_runtime(event_bus=event_bus)
    await market_data_runtime.start()

    websocket = _FakeWebSocket([])
    connector = BybitMarketDataConnector(
        session=_session("BTC/USDT", "ETH/USDT"),
        market_data_runtime=market_data_runtime,
        universe_scope_mode=True,
        universe_min_trade_count_24h=1_000_000_000,
    )
    await connector.feed_runtime.start(observed_at=connector.get_recovery_state().observed_at)
    connector.feed_runtime.mark_connected(observed_at=connector.get_recovery_state().observed_at)
    connector._active_websocket = websocket
    started_at = datetime(2026, 4, 5, 12, 0, tzinfo=UTC)

    connector._derived_trade_count.note_trade(
        symbol="BTC/USDT",
        observed_at=started_at + timedelta(minutes=1),
    )
    connector._derived_trade_count.note_trade(
        symbol="ETH/USDT",
        observed_at=started_at + timedelta(minutes=2),
    )
    connector._derived_trade_count._state = "ready"
    original_narrow_utcnow = connector._maybe_apply_post_readiness_narrowing.__globals__["_utcnow"]
    original_diag_utcnow = connector.get_operator_diagnostics.__globals__["_utcnow"]
    connector._maybe_apply_post_readiness_narrowing.__globals__["_utcnow"] = lambda: (
        started_at + timedelta(minutes=4)
    )
    connector.get_operator_diagnostics.__globals__["_utcnow"] = lambda: (
        started_at + timedelta(minutes=4)
    )
    try:
        await connector._maybe_apply_post_readiness_narrowing()
        diagnostics = connector.get_operator_diagnostics()
    finally:
        connector._maybe_apply_post_readiness_narrowing.__globals__["_utcnow"] = (
            original_narrow_utcnow
        )
        connector.get_operator_diagnostics.__globals__["_utcnow"] = original_diag_utcnow

    assert diagnostics["derived_trade_count_ready"] is True
    assert diagnostics["symbols"] == ()
    assert diagnostics["symbol_snapshots"] == ()
    assert connector.get_recovery_state().status == FeedSubscriptionRecoveryStatus.RECOVERED
    assert connector.get_recovery_state().metadata["subscription_registry"] == ()
    assert connector.get_recovery_assessment().session.subscription_scope == (
        "BTC/USDT",
        "ETH/USDT",
    )
    assert len(websocket.sent_messages) == 1
    assert json.loads(websocket.sent_messages[0]) == {
        "op": "unsubscribe",
        "args": [
            "publicTrade.BTCUSDT",
            "orderbook.50.BTCUSDT",
            "publicTrade.ETHUSDT",
            "orderbook.50.ETHUSDT",
        ],
    }


@pytest.mark.asyncio
async def test_bybit_connector_applies_narrowing_after_backfill_ready_without_new_live_trade() -> (
    None
):
    event_bus = EnhancedEventBus(enable_persistence=False)
    market_data_runtime = create_market_data_runtime(event_bus=event_bus)
    await market_data_runtime.start()

    websocket = _FakeWebSocket([])
    observed_at = datetime(2026, 4, 6, 12, 0, tzinfo=UTC)
    archives = {
        "https://public.bybit.com/trading/BTCUSDT/BTCUSDT2026-04-05.csv.gz": _gzip_csv(
            "timestamp,price,qty\n2026-04-05T12:01:00+00:00,68000,0.1\n"
        ),
        "https://public.bybit.com/trading/BTCUSDT/BTCUSDT2026-04-06.csv.gz": _gzip_csv(
            "timestamp,price,qty\n2026-04-06T11:59:00+00:00,68200,0.3\n"
        ),
        "https://public.bybit.com/trading/ETHUSDT/ETHUSDT2026-04-05.csv.gz": _gzip_csv(
            "timestamp,price,qty\n2026-04-05T12:02:00+00:00,3400,0.2\n"
        ),
        "https://public.bybit.com/trading/ETHUSDT/ETHUSDT2026-04-06.csv.gz": _gzip_csv(
            "timestamp,price,qty\n"
        ),
    }
    service = BybitHistoricalTradeBackfillService(
        config=BybitHistoricalTradeBackfillConfig(contour="linear"),
        fetch_bytes=lambda url, _timeout: archives[url],
    )

    connector = BybitMarketDataConnector(
        session=_session("BTC/USDT", "ETH/USDT"),
        market_data_runtime=market_data_runtime,
        universe_scope_mode=True,
        universe_min_trade_count_24h=2,
        historical_trade_backfill_service=service,
    )
    await connector.feed_runtime.start(observed_at=observed_at)
    connector.feed_runtime.mark_connected(observed_at=observed_at)
    connector._active_websocket = websocket

    original_utcnow = connector._maybe_restore_historical_trade_count.__globals__["_utcnow"]
    connector._maybe_restore_historical_trade_count.__globals__["_utcnow"] = lambda: observed_at
    original_diag_utcnow = connector.get_operator_diagnostics.__globals__["_utcnow"]
    connector.get_operator_diagnostics.__globals__["_utcnow"] = lambda: observed_at
    connector._historical_trade_backfill_cutoff_at = observed_at
    try:
        await connector._maybe_restore_historical_trade_count()
        diagnostics = connector.get_operator_diagnostics()
    finally:
        connector._maybe_restore_historical_trade_count.__globals__["_utcnow"] = original_utcnow
        connector.get_operator_diagnostics.__globals__["_utcnow"] = original_diag_utcnow

    assert diagnostics["derived_trade_count_ready"] is False
    assert diagnostics["symbols"] == ("BTC/USDT", "ETH/USDT")
    assert connector.get_recovery_assessment().session.subscription_scope == (
        "BTC/USDT",
        "ETH/USDT",
    )
    assert websocket.sent_messages == []


@pytest.mark.asyncio
async def test_disconnect_restores_active_scope_to_full_coarse_universe_after_narrowing() -> None:
    event_bus = EnhancedEventBus(enable_persistence=False)
    market_data_runtime = create_market_data_runtime(event_bus=event_bus)
    await market_data_runtime.start()

    connector = BybitMarketDataConnector(
        session=_session("BTC/USDT", "ETH/USDT"),
        market_data_runtime=market_data_runtime,
        universe_scope_mode=True,
        universe_min_trade_count_24h=2,
    )
    connector._active_symbols = ("BTC/USDT",)
    connector.subscription_registry = BybitSubscriptionRegistry(
        symbols=("BTC/USDT",),
        orderbook_depth=connector.config.orderbook_depth,
    )
    connector._post_readiness_narrowing_applied = True
    await connector.feed_runtime.start(observed_at=datetime(2026, 4, 6, 12, 0, tzinfo=UTC))

    await connector._handle_disconnect(reason="transport_gap")

    assert connector._active_symbols == ("BTC/USDT", "ETH/USDT")
    assert connector.subscription_registry.topics == (
        "publicTrade.BTCUSDT",
        "orderbook.50.BTCUSDT",
        "publicTrade.ETHUSDT",
        "orderbook.50.ETHUSDT",
    )
    assert connector.get_recovery_assessment().session.subscription_scope == (
        "BTC/USDT",
        "ETH/USDT",
    )


@pytest.mark.asyncio
async def test_threshold_update_reuses_live_trade_count_state_without_backfill_restart() -> None:
    event_bus = EnhancedEventBus(enable_persistence=False)
    market_data_runtime = create_market_data_runtime(event_bus=event_bus)
    await market_data_runtime.start()
    observed_at = datetime(2026, 4, 7, 12, 0, 30, tzinfo=UTC)

    connector = BybitMarketDataConnector(
        session=_session("BTC/USDT", "ETH/USDT"),
        market_data_runtime=market_data_runtime,
        universe_scope_mode=True,
        universe_min_trade_count_24h=1_000_000_000,
    )
    connector._derived_trade_count.note_trade(
        symbol="BTC/USDT",
        observed_at=observed_at,
    )
    connector._derived_trade_count.restore_historical_window(
        trades_by_symbol={
            "BTC/USDT": (
                datetime(2026, 4, 6, 12, 1, tzinfo=UTC),
                datetime(2026, 4, 7, 11, 59, tzinfo=UTC),
            ),
            "ETH/USDT": (
                datetime(2026, 4, 6, 12, 2, tzinfo=UTC),
                datetime(2026, 4, 7, 11, 58, tzinfo=UTC),
            ),
        },
        window_started_at=datetime(2026, 4, 6, 12, 0, tzinfo=UTC),
        covered_until_at=datetime(2026, 4, 7, 12, 0, tzinfo=UTC),
        observed_at=observed_at,
        processed_archives=2,
        total_archives=2,
    )
    connector._active_symbols = ()
    connector.subscription_registry = BybitSubscriptionRegistry(
        symbols=(),
        orderbook_depth=connector.config.orderbook_depth,
    )
    connector._post_readiness_narrowing_applied = True
    connector._historical_trade_backfill_pending = False
    websocket = _FakeWebSocket([])
    connector._active_websocket = websocket

    original_utcnow = bybit_module._utcnow
    bybit_module._utcnow = lambda: observed_at
    try:
        await connector.update_universe_trade_count_threshold(2)
    finally:
        bybit_module._utcnow = original_utcnow

    assert connector._historical_trade_backfill_pending is False
    assert connector._universe_min_trade_count_24h == 2
    assert connector._active_symbols == ("BTC/USDT", "ETH/USDT")
    assert connector._post_readiness_narrowing_applied is True
    assert any('"op": "subscribe"' in message for message in websocket.sent_messages)
    diagnostics = connector.get_operator_diagnostics()
    assert diagnostics["derived_trade_count_state"] == "ready"
    assert diagnostics["derived_trade_count_ready"] is True
    assert diagnostics["derived_trade_count_backfill_status"] == "backfilled"


@pytest.mark.asyncio
async def test_historical_backfill_uses_full_coarse_candidate_scope_after_narrowing() -> None:
    event_bus = EnhancedEventBus(enable_persistence=False)
    market_data_runtime = create_market_data_runtime(event_bus=event_bus)
    recorded_symbols: list[tuple[str, ...]] = []

    class _RecordingPlanBackfillService(BybitHistoricalTradeBackfillService):
        def build_recovery_plan(
            self,
            *,
            symbols: tuple[str, ...],
            observed_at: datetime,
            covered_until_at: datetime | None = None,
        ) -> BybitHistoricalRecoveryPlan:
            recorded_symbols.append(symbols)
            return super().build_recovery_plan(
                symbols=symbols,
                observed_at=observed_at,
                covered_until_at=covered_until_at,
            )

    service = _RecordingPlanBackfillService(
        config=BybitHistoricalTradeBackfillConfig(contour="linear"),
        fetch_bytes=lambda _url, _timeout: b"",
    )
    connector = BybitMarketDataConnector(
        session=_session("BTC/USDT", "ETH/USDT"),
        market_data_runtime=market_data_runtime,
        universe_scope_mode=True,
        universe_min_trade_count_24h=2,
        historical_trade_backfill_service=service,
    )
    connector._active_symbols = ("BTC/USDT",)

    connector._schedule_historical_trade_count_backfill()

    assert recorded_symbols == [("BTC/USDT", "ETH/USDT")]
    assert connector._historical_trade_backfill_task is not None
    connector._historical_trade_backfill_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await connector._historical_trade_backfill_task


@pytest.mark.asyncio
async def test_trade_count_threshold_update_ignores_transient_closed_websocket() -> None:
    event_bus = EnhancedEventBus(enable_persistence=False)
    market_data_runtime = create_market_data_runtime(event_bus=event_bus)

    connector = BybitMarketDataConnector(
        session=_session("BTC/USDT", "ETH/USDT"),
        market_data_runtime=market_data_runtime,
        universe_scope_mode=True,
        universe_min_trade_count_24h=1_000_000_000,
    )
    connector._active_symbols = ("BTC/USDT",)
    connector.subscription_registry = BybitSubscriptionRegistry(
        symbols=("BTC/USDT",),
        orderbook_depth=connector.config.orderbook_depth,
    )
    websocket = _ClosingSendWebSocket([])
    connector._active_websocket = websocket

    await connector.update_universe_trade_count_threshold(2)

    assert connector._universe_min_trade_count_24h == 2
    assert connector._active_websocket is None
    assert connector._active_symbols == ("BTC/USDT", "ETH/USDT")
    assert connector._post_readiness_narrowing_applied is False


@pytest.mark.asyncio
async def test_disconnect_reuses_restored_historical_window_without_requeueing_full_backfill() -> (
    None
):
    event_bus = EnhancedEventBus(enable_persistence=False)
    market_data_runtime = create_market_data_runtime(event_bus=event_bus)
    await market_data_runtime.start()

    connector = BybitMarketDataConnector(
        session=_session("BTC/USDT", "ETH/USDT"),
        market_data_runtime=market_data_runtime,
        universe_scope_mode=True,
        universe_min_trade_count_24h=2,
        historical_trade_backfill_service=BybitHistoricalTradeBackfillService(
            config=BybitHistoricalTradeBackfillConfig(contour="linear"),
            fetch_bytes=lambda _url, _timeout: b"",
        ),
    )
    restored_at = datetime(2026, 4, 7, 12, 0, tzinfo=UTC)
    connector._derived_trade_count.restore_historical_window(
        trades_by_symbol={
            "BTC/USDT": (
                datetime(2026, 4, 6, 12, 1, tzinfo=UTC),
                datetime(2026, 4, 7, 11, 59, tzinfo=UTC),
            ),
            "ETH/USDT": (
                datetime(2026, 4, 6, 12, 2, tzinfo=UTC),
                datetime(2026, 4, 7, 11, 58, tzinfo=UTC),
            ),
        },
        window_started_at=datetime(2026, 4, 6, 12, 0, tzinfo=UTC),
        covered_until_at=datetime(2026, 4, 7, 12, 0, tzinfo=UTC),
        observed_at=restored_at,
        processed_archives=2,
        total_archives=2,
    )
    await connector.feed_runtime.start(observed_at=restored_at)

    await connector._handle_disconnect(reason="transport_gap")

    diagnostics = connector.get_operator_diagnostics()

    assert connector._historical_trade_backfill_pending is False
    assert diagnostics["derived_trade_count_backfill_status"] == "backfilled"
    assert diagnostics["derived_trade_count_backfill_total_archives"] == 2
    assert diagnostics["derived_trade_count_last_gap_reason"] == "transport_gap"
    assert diagnostics["derived_trade_count_state"] == "live_tail_pending_after_gap"
    assert diagnostics["derived_trade_count_ready"] is False


@pytest.mark.asyncio
async def test_disconnect_reuses_ready_historical_window_even_if_backfill_task_is_still_running() -> (
    None
):
    event_bus = EnhancedEventBus(enable_persistence=False)
    market_data_runtime = create_market_data_runtime(event_bus=event_bus)
    await market_data_runtime.start()

    connector = BybitMarketDataConnector(
        session=_session("BTC/USDT", "ETH/USDT"),
        market_data_runtime=market_data_runtime,
        universe_scope_mode=True,
        universe_min_trade_count_24h=2,
        historical_trade_backfill_service=BybitHistoricalTradeBackfillService(
            config=BybitHistoricalTradeBackfillConfig(contour="linear"),
            fetch_bytes=lambda _url, _timeout: b"",
        ),
    )
    restored_at = datetime(2026, 4, 7, 12, 0, 30, tzinfo=UTC)
    connector._derived_trade_count.note_trade(symbol="BTC/USDT", observed_at=restored_at)
    connector._derived_trade_count.restore_historical_window(
        trades_by_symbol={
            "BTC/USDT": (
                datetime(2026, 4, 6, 12, 1, tzinfo=UTC),
                datetime(2026, 4, 7, 11, 59, tzinfo=UTC),
            ),
            "ETH/USDT": (
                datetime(2026, 4, 6, 12, 2, tzinfo=UTC),
                datetime(2026, 4, 7, 11, 58, tzinfo=UTC),
            ),
        },
        window_started_at=datetime(2026, 4, 6, 12, 0, tzinfo=UTC),
        covered_until_at=datetime(2026, 4, 7, 12, 0, tzinfo=UTC),
        observed_at=restored_at,
        processed_archives=2,
        total_archives=2,
    )
    await connector.feed_runtime.start(observed_at=restored_at)
    running_backfill_task = asyncio.create_task(asyncio.sleep(60))
    connector._historical_trade_backfill_task = running_backfill_task

    try:
        await connector._handle_disconnect(reason="transport_gap")
        diagnostics = connector.get_operator_diagnostics()
    finally:
        running_backfill_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await running_backfill_task

    assert connector._historical_trade_backfill_pending is False
    assert diagnostics["derived_trade_count_state"] == "live_tail_pending_after_gap"
    assert diagnostics["derived_trade_count_ready"] is False
    assert diagnostics["derived_trade_count_backfill_status"] == "backfilled"


@pytest.mark.asyncio
async def test_disconnect_preserves_narrowed_scope_when_historical_window_is_reused() -> None:
    event_bus = EnhancedEventBus(enable_persistence=False)
    market_data_runtime = create_market_data_runtime(event_bus=event_bus)
    await market_data_runtime.start()

    connector = BybitMarketDataConnector(
        session=_session("BTC/USDT", "ETH/USDT"),
        market_data_runtime=market_data_runtime,
        universe_scope_mode=True,
        universe_min_trade_count_24h=2,
    )
    restored_at = datetime(2026, 4, 7, 12, 0, tzinfo=UTC)
    connector._derived_trade_count.restore_historical_window(
        trades_by_symbol={
            "BTC/USDT": (
                datetime(2026, 4, 6, 12, 1, tzinfo=UTC),
                datetime(2026, 4, 7, 11, 59, tzinfo=UTC),
            ),
            "ETH/USDT": (
                datetime(2026, 4, 6, 12, 2, tzinfo=UTC),
                datetime(2026, 4, 7, 11, 58, tzinfo=UTC),
            ),
        },
        window_started_at=datetime(2026, 4, 6, 12, 0, tzinfo=UTC),
        covered_until_at=datetime(2026, 4, 7, 12, 0, tzinfo=UTC),
        observed_at=restored_at,
        processed_archives=2,
        total_archives=2,
    )
    connector._active_symbols = ("BTC/USDT",)
    connector.subscription_registry = BybitSubscriptionRegistry(
        symbols=("BTC/USDT",),
        orderbook_depth=connector.config.orderbook_depth,
    )
    connector._post_readiness_narrowing_applied = True
    await connector.feed_runtime.start(observed_at=restored_at)

    await connector._handle_disconnect(reason="transport_gap")

    assert connector._active_symbols == ("BTC/USDT",)
    assert connector.subscription_registry.topics == (
        "publicTrade.BTCUSDT",
        "orderbook.50.BTCUSDT",
    )
    assert connector._historical_trade_backfill_pending is False


def test_tracker_restores_live_tail_pending_state_from_persisted_snapshot() -> None:
    store_dir = _make_local_temp_dir()
    store = BybitDerivedTradeCountPersistenceStore(path=store_dir / "tracker.json")
    original = BybitDerivedTradeCountTracker(symbols=("BTC/USDT",))
    restored_at = datetime(2026, 4, 7, 12, 0, tzinfo=UTC)
    gap_at = datetime(2026, 4, 7, 12, 30, tzinfo=UTC)
    original.restore_historical_window(
        trades_by_symbol={
            "BTC/USDT": (
                datetime(2026, 4, 6, 12, 1, tzinfo=UTC),
                datetime(2026, 4, 7, 11, 59, tzinfo=UTC),
            )
        },
        window_started_at=datetime(2026, 4, 6, 12, 0, tzinfo=UTC),
        covered_until_at=datetime(2026, 4, 7, 12, 0, tzinfo=UTC),
        observed_at=restored_at,
        processed_archives=1,
        total_archives=1,
    )
    original.mark_gap_preserving_historical_window(observed_at=gap_at, reason="transport_gap")
    store.save(original.to_persisted_state(persisted_at=gap_at))

    persisted_state = store.load()
    assert persisted_state is not None

    tracker = BybitDerivedTradeCountTracker(symbols=("BTC/USDT",))
    tracker.restore_from_persisted_state(
        persisted_state,
        restored_at=gap_at + timedelta(seconds=30),
    )
    diagnostics = tracker.get_diagnostics(observed_at=gap_at + timedelta(seconds=30))

    assert diagnostics.state == "live_tail_pending_after_gap"
    assert diagnostics.ready is False
    assert diagnostics.reliable_after == gap_at.isoformat()
    shutil.rmtree(store_dir, ignore_errors=True)


def test_manual_connector_does_not_enable_trade_count_backfill_or_persistence() -> None:
    event_bus = EnhancedEventBus(enable_persistence=False)
    market_data_runtime = create_market_data_runtime(event_bus=event_bus)

    connector = create_bybit_market_data_connector(
        symbols=("BTC/USDT",),
        market_data_runtime=market_data_runtime,
        universe_scope_mode=False,
        universe_min_trade_count_24h=0,
    )

    assert connector._derived_trade_count_store is None
    assert connector._historical_trade_backfill_service is None
    assert connector._historical_trade_backfill_pending is False
    diagnostics = connector.get_operator_diagnostics()
    assert diagnostics["derived_trade_count_backfill_status"] == "not_needed"
    assert diagnostics["derived_trade_count_backfill_needed"] is False


def test_zero_threshold_universe_connectors_do_not_enable_trade_count_backfill_or_persistence() -> (
    None
):
    event_bus = EnhancedEventBus(enable_persistence=False)
    market_data_runtime = create_market_data_runtime(event_bus=event_bus)

    linear_connector = create_bybit_market_data_connector(
        symbols=("BTC/USDT",),
        market_data_runtime=market_data_runtime,
        universe_scope_mode=True,
        universe_min_trade_count_24h=0,
    )
    spot_connector = create_bybit_spot_market_data_connector(
        symbols=("BTC/USDT",),
        market_data_runtime=market_data_runtime,
        universe_scope_mode=True,
        universe_min_trade_count_24h=0,
    )

    assert linear_connector._derived_trade_count_store is None
    assert linear_connector._historical_trade_backfill_service is None
    assert linear_connector._historical_trade_backfill_pending is False
    assert spot_connector._derived_trade_count_store is None
    assert spot_connector._historical_trade_backfill_service is None
    assert spot_connector._historical_trade_backfill_pending is False
    linear_diagnostics = linear_connector.get_operator_diagnostics()
    spot_diagnostics = spot_connector.get_operator_diagnostics()
    assert linear_diagnostics["derived_trade_count_backfill_status"] == "not_needed"
    assert linear_diagnostics["derived_trade_count_backfill_needed"] is False
    assert spot_diagnostics["derived_trade_count_backfill_status"] == "not_needed"
    assert spot_diagnostics["derived_trade_count_backfill_needed"] is False


@pytest.mark.asyncio
async def test_bybit_connector_stop_does_not_trigger_false_disconnect_recovery() -> None:
    event_bus = EnhancedEventBus(enable_persistence=False)
    market_data_runtime = create_market_data_runtime(event_bus=event_bus)
    await market_data_runtime.start()

    websocket = _BlockingWebSocket()

    async def websocket_factory(_: BybitMarketDataConnectorConfig) -> _BlockingWebSocket:
        return websocket

    connector = BybitMarketDataConnector(
        session=_session(),
        market_data_runtime=market_data_runtime,
        websocket_factory=websocket_factory,
    )

    task = asyncio.create_task(connector.run(max_cycles=1))
    await asyncio.sleep(0.05)
    await connector.stop()
    await asyncio.wait_for(task, timeout=1.0)

    assert connector.feed_runtime.is_started is False
    assert connector.feed_runtime.get_runtime_diagnostics()["last_disconnect_reason"] is None
    assert connector.get_recovery_state().status != FeedSubscriptionRecoveryStatus.RECOVERY_REQUIRED


@pytest.mark.asyncio
async def test_bybit_connector_stop_does_not_block_on_slow_websocket_close() -> None:
    event_bus = EnhancedEventBus(enable_persistence=False)
    market_data_runtime = create_market_data_runtime(event_bus=event_bus)
    await market_data_runtime.start()

    websocket = _SlowCloseWebSocket()
    connector = BybitMarketDataConnector(
        session=_session(),
        market_data_runtime=market_data_runtime,
    )
    connector._active_websocket = websocket

    started_at = time.perf_counter()
    await connector.stop()
    elapsed_seconds = time.perf_counter() - started_at

    assert elapsed_seconds < 0.5
    await asyncio.sleep(0)
    assert websocket.close_calls == 1


@pytest.mark.asyncio
async def test_bybit_connector_run_shutdown_does_not_block_on_slow_websocket_close() -> None:
    event_bus = EnhancedEventBus(enable_persistence=False)
    market_data_runtime = create_market_data_runtime(event_bus=event_bus)
    await market_data_runtime.start()

    websocket = _SlowCloseWebSocket()

    async def websocket_factory(_: BybitMarketDataConnectorConfig) -> _SlowCloseWebSocket:
        return websocket

    connector = BybitMarketDataConnector(
        session=_session(),
        market_data_runtime=market_data_runtime,
        websocket_factory=websocket_factory,
    )

    task = asyncio.create_task(connector.run(max_cycles=1))
    await asyncio.sleep(0.05)
    started_at = time.perf_counter()
    await connector.stop()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, timeout=2.0)
    elapsed_seconds = time.perf_counter() - started_at

    assert elapsed_seconds < 1.5
    assert websocket.close_calls >= 1


@pytest.mark.asyncio
async def test_bybit_connector_marks_resubscribe_recovered_and_rebuilds_snapshot() -> None:
    event_bus = EnhancedEventBus(enable_persistence=False)
    market_data_runtime = create_market_data_runtime(event_bus=event_bus)
    await market_data_runtime.start()

    connector = BybitMarketDataConnector(
        session=_session(),
        market_data_runtime=market_data_runtime,
    )
    await connector.feed_runtime.start(observed_at=connector.get_recovery_state().observed_at)

    await connector._handle_disconnect(reason="transport_closed")
    assert connector.get_recovery_state().status == FeedSubscriptionRecoveryStatus.RECOVERY_REQUIRED

    connector._mark_resubscribing(
        reason="transport_connected",
        observed_at=connector.get_recovery_state().observed_at,
    )
    connector.feed_runtime.mark_connected(observed_at=connector.get_recovery_state().observed_at)
    await connector.ingest_transport_message(json.dumps({"op": "subscribe", "success": True}))

    recovered_after_ack = connector.get_recovery_state()
    assert recovered_after_ack.status == FeedSubscriptionRecoveryStatus.RESUBSCRIBING
    assert recovered_after_ack.reset_required is True
    assert recovered_after_ack.metadata["subscription_alive"] is True

    assert await connector.ingest_transport_message(json.dumps(_orderbook_delta_message())) == 0
    assert await connector.ingest_transport_message(json.dumps(_orderbook_snapshot_message())) == 1

    recovery_state = connector.get_recovery_state()
    assert recovery_state.status == FeedSubscriptionRecoveryStatus.RECOVERED
    assert recovery_state.metadata["subscription_alive"] is True
    assert recovery_state.metadata["awaiting_snapshot_symbols"] == ()
    assert recovery_state.reset_required is False

    orderbook = market_data_runtime.orderbook_manager.get_snapshot("BTC/USDT", "bybit")
    assert orderbook is not None
    assert orderbook.bids[0].price == Decimal("68000.0")

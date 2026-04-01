from __future__ import annotations

import asyncio
from decimal import Decimal
import json

import pytest

from cryptotechnolog.core.enhanced_event_bus import EnhancedEventBus
from cryptotechnolog.live_feed import (
    BybitMarketDataConnector,
    BybitMarketDataConnectorConfig,
    BybitMarketDataParser,
    BybitMessageParseError,
    BybitOrderBookProjector,
    BybitSubscriptionRegistry,
    FeedSessionIdentity,
    normalize_bybit_symbol,
)
from cryptotechnolog.live_feed.models import FeedSubscriptionRecoveryStatus
from cryptotechnolog.market_data import create_market_data_runtime


class _FakeWebSocket:
    def __init__(self, messages: list[str]) -> None:
        self._messages = list(messages)
        self.sent_messages: list[str] = []
        self.closed = False

    async def send(self, message: str) -> None:
        self.sent_messages.append(message)

    async def recv(self) -> str:
        if not self._messages:
            raise RuntimeError("transport_closed")
        return self._messages.pop(0)

    async def close(self) -> None:
        self.closed = True


class _BlockingWebSocket:
    def __init__(self) -> None:
        self.sent_messages: list[str] = []
        self.closed = False
        self._closed_event = asyncio.Event()

    async def send(self, message: str) -> None:
        self.sent_messages.append(message)

    async def recv(self) -> str:
        await self._closed_event.wait()
        raise RuntimeError("transport_closed")

    async def close(self) -> None:
        self.closed = True
        self._closed_event.set()


def _session() -> FeedSessionIdentity:
    return FeedSessionIdentity(
        exchange="bybit",
        stream_kind="market_data",
        subscription_scope=("BTC/USDT",),
    )


def _trade_message() -> dict[str, object]:
    return {
        "topic": "publicTrade.BTCUSDT",
        "type": "snapshot",
        "ts": 1711929600123,
        "data": [
            {
                "T": 1711929600120,
                "s": "BTCUSDT",
                "S": "Buy",
                "v": "0.010",
                "p": "68000.5",
                "i": "trade-1",
            }
        ],
    }


def _orderbook_snapshot_message() -> dict[str, object]:
    return {
        "topic": "orderbook.50.BTCUSDT",
        "type": "snapshot",
        "ts": 1711929600200,
        "data": {
            "s": "BTCUSDT",
            "b": [["68000.0", "2.5"], ["67999.5", "1.0"]],
            "a": [["68000.5", "3.0"], ["68001.0", "1.5"]],
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


@pytest.mark.asyncio
async def test_bybit_connector_operator_diagnostics_expose_connector_truth() -> None:
    event_bus = EnhancedEventBus(enable_persistence=False)
    market_data_runtime = create_market_data_runtime(event_bus=event_bus)
    await market_data_runtime.start()

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
    await connector.ingest_transport_message(json.dumps(_trade_message()))
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

    websocket = _FakeWebSocket([
        json.dumps({"op": "subscribe", "success": True}),
        json.dumps(_trade_message()),
        json.dumps(_orderbook_snapshot_message()),
    ])

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
    assert recovered_after_ack.status == FeedSubscriptionRecoveryStatus.RECOVERED
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

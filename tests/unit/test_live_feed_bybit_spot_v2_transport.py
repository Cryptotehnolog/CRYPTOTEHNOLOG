from __future__ import annotations

import asyncio
from decimal import Decimal
import json
from datetime import UTC, datetime

import pytest
from websockets.exceptions import ConnectionClosedError

from cryptotechnolog.core.enhanced_event_bus import EnhancedEventBus
from cryptotechnolog.live_feed.bybit_spot_v2_transport import (
    BybitSpotV2Transport,
    BybitSpotV2TransportConfig,
)
from cryptotechnolog.live_feed.bybit_spot_v2_live_trade_ledger import (
    _normalize_source_metadata_payload,
)
from cryptotechnolog.market_data import create_market_data_runtime


class _InMemoryV2LedgerRepository:
    def __init__(self) -> None:
        self.records: list[object] = []

    async def upsert_live_trade(self, record) -> None:
        self.records.append(record)


def test_v2_live_trade_ledger_normalizes_json_string_source_metadata() -> None:
    assert _normalize_source_metadata_payload('{"source":"bybit","seq":101}') == {
        "source": "bybit",
        "seq": "101",
    }


class _StreamingWebSocket:
    def __init__(self, messages: list[str]) -> None:
        self._messages = list(messages)
        self.sent_messages: list[str] = []
        self.closed = False
        self._closed = asyncio.Event()
        self.ping_latency_seconds = 0.018

    async def send(self, message: str) -> None:
        self.sent_messages.append(message)
        try:
            payload = json.loads(message)
        except Exception:
            return
        if payload == {"op": "ping"}:
            self._messages.append(json.dumps({"op": "pong"}))

    async def recv(self) -> str:
        while True:
            if self._messages:
                return self._messages.pop(0)
            if self._closed.is_set():
                raise RuntimeError("transport_closed")
            await asyncio.sleep(0)

    async def close(self) -> None:
        self.closed = True
        self._closed.set()

    async def ping(self, data: object | None = None):
        async def _pong_waiter() -> float:
            return self.ping_latency_seconds

        return _pong_waiter()


class _BenignClosePingWebSocket(_StreamingWebSocket):
    async def ping(self, data: object | None = None):
        async def _pong_waiter() -> float:
            raise ConnectionClosedError(None, None)

        return _pong_waiter()


class _BenignCloseRecvWebSocket(_StreamingWebSocket):
    async def recv(self) -> str:
        raise ConnectionClosedError(None, None)


class _ApplicationOnlyHeartbeatWebSocket(_StreamingWebSocket):
    async def ping(self, data: object | None = None):
        async def _pong_waiter() -> float:
            raise TimeoutError("transport_ping_timeout")

        return _pong_waiter()


@pytest.mark.asyncio
async def test_bybit_spot_v2_transport_reports_live_transport_diagnostics() -> None:
    websocket = _StreamingWebSocket(
        [
            json.dumps({"op": "subscribe", "success": True}),
            json.dumps({"topic": "publicTrade.BTCUSDT", "data": []}),
        ]
    )

    async def websocket_factory(_: BybitSpotV2TransportConfig) -> _StreamingWebSocket:
        return websocket

    connector = BybitSpotV2Transport(
        symbols=("BTC/USDT",),
        config=BybitSpotV2TransportConfig(
            ping_interval_seconds=3600,
            reconnect_delay_seconds=3600,
        ),
        websocket_factory=websocket_factory,
    )

    task = asyncio.create_task(connector.run())
    await asyncio.wait_for(connector.run_started.wait(), timeout=1.0)

    async def wait_for_live_diagnostics() -> dict[str, object]:
        while True:
            diagnostics = connector.get_transport_diagnostics()
            if (
                diagnostics["subscription_alive"] is True
                and diagnostics["transport_rtt_ms"] == 18
                and diagnostics["messages_received_count"] >= 2
            ):
                return diagnostics
            await asyncio.sleep(0)

    diagnostics = await asyncio.wait_for(wait_for_live_diagnostics(), timeout=1.0)

    subscribe_payloads = [json.loads(message) for message in websocket.sent_messages if '"op": "subscribe"' in message]
    assert subscribe_payloads[0]["op"] == "subscribe"
    assert subscribe_payloads[0]["args"] == ["publicTrade.BTCUSDT"]
    assert subscribe_payloads[1]["args"] == ["orderbook.50.BTCUSDT"]
    assert diagnostics["transport_status"] == "connected"
    assert diagnostics["subscription_alive"] is True
    assert diagnostics["transport_rtt_ms"] == 18
    assert diagnostics["last_message_at"] is not None
    assert diagnostics["retry_count"] == 0

    await connector.stop()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_bybit_spot_v2_transport_falls_back_to_application_heartbeat_rtt() -> None:
    websocket = _ApplicationOnlyHeartbeatWebSocket(
        [
            json.dumps({"op": "subscribe", "success": True}),
            json.dumps({"topic": "publicTrade.BTCUSDT", "data": []}),
        ]
    )

    async def websocket_factory(_: BybitSpotV2TransportConfig) -> _ApplicationOnlyHeartbeatWebSocket:
        return websocket

    connector = BybitSpotV2Transport(
        symbols=("BTC/USDT",),
        config=BybitSpotV2TransportConfig(
            ping_interval_seconds=3600,
            ping_timeout_seconds=1,
            reconnect_delay_seconds=3600,
        ),
        websocket_factory=websocket_factory,
    )

    task = asyncio.create_task(connector.run())
    await asyncio.wait_for(connector.run_started.wait(), timeout=1.0)

    async def wait_for_heartbeat_rtt() -> dict[str, object]:
        while True:
            diagnostics = connector.get_transport_diagnostics()
            if diagnostics["transport_rtt_ms"] is not None:
                return diagnostics
            await asyncio.sleep(0)

    diagnostics = await asyncio.wait_for(wait_for_heartbeat_rtt(), timeout=1.0)

    assert diagnostics["transport_status"] == "connected"
    assert diagnostics["subscription_alive"] is True
    assert diagnostics["transport_rtt_ms"] is not None

    await connector.stop()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


def test_bybit_spot_v2_transport_publishes_stream_freshness_when_heartbeat_rtt_missing() -> None:
    connector = BybitSpotV2Transport(symbols=("BTC/USDT",))
    connector._transport_status = "connected"
    connector._subscription_alive = True
    connector._last_message_at = datetime.now(tz=UTC)

    snapshot = connector.build_transport_snapshot()

    assert snapshot.transport_rtt_ms is not None
    assert snapshot.transport_rtt_ms >= 0


def test_bybit_spot_v2_transport_prefers_heartbeat_when_ping_rtt_is_polluted() -> None:
    connector = BybitSpotV2Transport(symbols=("BTC/USDT",))
    connector._transport_status = "connected"
    connector._subscription_alive = True
    connector._transport_rtt_ms = 12000
    connector._application_heartbeat_latency_ms = 180

    snapshot = connector.build_transport_snapshot()

    assert snapshot.transport_rtt_ms == 180


def test_bybit_spot_v2_transport_caps_polluted_rtt_by_stream_freshness() -> None:
    connector = BybitSpotV2Transport(symbols=("BTC/USDT",))
    connector._transport_status = "connected"
    connector._subscription_alive = True
    connector._transport_rtt_ms = 12000
    connector._last_message_at = datetime.now(tz=UTC)

    snapshot = connector.build_transport_snapshot()

    assert snapshot.transport_rtt_ms is not None
    assert snapshot.transport_rtt_ms < 1000


def test_bybit_spot_v2_transport_prefers_fresh_stream_even_when_ping_rtt_is_only_moderately_stale() -> None:
    connector = BybitSpotV2Transport(symbols=("BTC/USDT",))
    connector._transport_status = "connected"
    connector._subscription_alive = True
    connector._transport_rtt_ms = 3500
    connector._last_message_at = datetime.now(tz=UTC)

    snapshot = connector.build_transport_snapshot()

    assert snapshot.transport_rtt_ms is not None
    assert snapshot.transport_rtt_ms < 1000


@pytest.mark.asyncio
async def test_bybit_spot_v2_transport_accepts_subscribe_ack_with_ret_msg_only() -> None:
    websocket = _StreamingWebSocket(
        [
            json.dumps({"success": True, "ret_msg": "subscribe"}),
            json.dumps({"topic": "publicTrade.BTCUSDT", "data": []}),
        ]
    )

    async def websocket_factory(_: BybitSpotV2TransportConfig) -> _StreamingWebSocket:
        return websocket

    connector = BybitSpotV2Transport(
        symbols=("BTC/USDT",),
        config=BybitSpotV2TransportConfig(
            ping_interval_seconds=3600,
            reconnect_delay_seconds=3600,
        ),
        websocket_factory=websocket_factory,
    )

    task = asyncio.create_task(connector.run())
    await asyncio.wait_for(connector.run_started.wait(), timeout=1.0)

    async def wait_for_live_diagnostics() -> dict[str, object]:
        while True:
            diagnostics = connector.get_transport_diagnostics()
            if diagnostics["subscription_alive"] is True and diagnostics["messages_received_count"] >= 2:
                return diagnostics
            await asyncio.sleep(0)

    diagnostics = await asyncio.wait_for(wait_for_live_diagnostics(), timeout=1.0)

    assert diagnostics["transport_status"] == "connected"
    assert diagnostics["subscription_alive"] is True

    await connector.stop()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_bybit_spot_v2_transport_batches_subscribe_requests_by_exchange_limit() -> None:
    websocket = _StreamingWebSocket([json.dumps({"op": "subscribe", "success": True})])

    async def websocket_factory(_: BybitSpotV2TransportConfig) -> _StreamingWebSocket:
        return websocket

    connector = BybitSpotV2Transport(
        symbols=(
            "BTC/USDT",
            "ETH/USDT",
            "SOL/USDT",
            "XRP/USDT",
            "DOGE/USDT",
            "ADA/USDT",
        ),
        config=BybitSpotV2TransportConfig(
            ping_interval_seconds=3600,
            reconnect_delay_seconds=3600,
        ),
        websocket_factory=websocket_factory,
    )

    task = asyncio.create_task(connector.run(max_cycles=1))
    await asyncio.wait_for(connector.run_started.wait(), timeout=1.0)
    while len(websocket.sent_messages) < 2:
        await asyncio.sleep(0)

    sent_payloads = [json.loads(message) for message in websocket.sent_messages]
    assert len(sent_payloads) == 2
    assert all(payload["op"] == "subscribe" for payload in sent_payloads)
    assert len(sent_payloads[0]["args"]) == 6
    assert len(sent_payloads[1]["args"]) == 6

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_bybit_spot_v2_transport_raises_on_failed_subscribe_response() -> None:
    websocket = _StreamingWebSocket([json.dumps({"success": False, "ret_msg": "args size >10", "op": "subscribe"})])

    connector = BybitSpotV2Transport(
        symbols=("BTC/USDT",),
        config=BybitSpotV2TransportConfig(
            ping_interval_seconds=3600,
            reconnect_delay_seconds=0,
        ),
        websocket_factory=lambda _: asyncio.sleep(0, result=websocket),
        sleep_func=lambda _: asyncio.sleep(0),
    )

    task = asyncio.create_task(connector.run(max_cycles=1))
    await asyncio.wait_for(connector.run_started.wait(), timeout=1.0)
    await asyncio.wait_for(task, timeout=1.0)

    diagnostics = connector.get_transport_diagnostics()
    assert diagnostics["transport_status"] == "disconnected"
    assert diagnostics["last_error"] == "RuntimeError: args size >10"
    assert diagnostics["retry_count"] == 0


@pytest.mark.asyncio
async def test_bybit_spot_v2_transport_retries_after_connect_failure() -> None:
    websocket = _StreamingWebSocket([json.dumps({"op": "subscribe", "success": True})])
    attempts = 0

    async def websocket_factory(_: BybitSpotV2TransportConfig) -> _StreamingWebSocket:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("connect_failed_once")
        return websocket

    async def fast_sleep(_: float) -> None:
        await asyncio.sleep(0)

    connector = BybitSpotV2Transport(
        symbols=("BTC/USDT",),
        config=BybitSpotV2TransportConfig(
            ping_interval_seconds=3600,
            reconnect_delay_seconds=0,
        ),
        websocket_factory=websocket_factory,
        sleep_func=fast_sleep,
    )

    task = asyncio.create_task(connector.run())
    await asyncio.wait_for(connector.run_started.wait(), timeout=1.0)

    async def wait_for_reconnect() -> dict[str, object]:
        while True:
            diagnostics = connector.get_transport_diagnostics()
            if (
                diagnostics["retry_count"] == 1
                and diagnostics["transport_status"] == "connected"
                and diagnostics["subscription_alive"] is True
            ):
                return diagnostics
            await asyncio.sleep(0)

    diagnostics = await asyncio.wait_for(wait_for_reconnect(), timeout=1.0)

    assert diagnostics["subscription_alive"] is True
    assert diagnostics["retry_count"] == 1
    assert diagnostics["last_error"] == "RuntimeError: connect_failed_once"

    await connector.stop()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_bybit_spot_v2_transport_ingests_trade_and_orderbook_into_market_data() -> None:
    trade_timestamp_ms = int(datetime.now(tz=UTC).timestamp() * 1000)
    websocket = _StreamingWebSocket(
        [
            json.dumps({"op": "subscribe", "success": True}),
            json.dumps(
                {
                    "topic": "publicTrade.BTCUSDT",
                    "type": "snapshot",
                    "data": [
                        {
                            "s": "BTCUSDT",
                            "S": "Buy",
                            "i": "trade-1",
                            "p": "68000.0",
                            "v": "0.25",
                            "T": trade_timestamp_ms,
                            "m": False,
                        }
                    ],
                }
            ),
            json.dumps(
                {
                    "topic": "orderbook.50.BTCUSDT",
                    "type": "snapshot",
                    "ts": trade_timestamp_ms,
                    "data": {
                        "s": "BTCUSDT",
                        "b": [["68000.0", "1.5"]],
                        "a": [["68000.5", "2.0"]],
                        "u": 101,
                        "seq": 101,
                    },
                }
            ),
        ]
    )

    async def websocket_factory(_: BybitSpotV2TransportConfig) -> _StreamingWebSocket:
        return websocket

    event_bus = EnhancedEventBus(enable_persistence=False)
    market_data_runtime = create_market_data_runtime(event_bus=event_bus)
    await market_data_runtime.start()
    ledger_repository = _InMemoryV2LedgerRepository()

    connector = BybitSpotV2Transport(
        symbols=("BTC/USDT",),
        config=BybitSpotV2TransportConfig(
            ping_interval_seconds=3600,
            reconnect_delay_seconds=3600,
        ),
        websocket_factory=websocket_factory,
        market_data_runtime=market_data_runtime,
        live_trade_ledger_repository=ledger_repository,
    )

    task = asyncio.create_task(connector.run())
    await asyncio.wait_for(connector.run_started.wait(), timeout=1.0)

    async def wait_for_ingest() -> dict[str, object]:
        while True:
            diagnostics = connector.get_transport_diagnostics()
            if diagnostics["trade_seen"] is True and diagnostics["orderbook_seen"] is True:
                return diagnostics
            await asyncio.sleep(0)

    diagnostics = await asyncio.wait_for(wait_for_ingest(), timeout=1.0)
    orderbook = market_data_runtime.orderbook_manager.get_snapshot("BTC/USDT", "bybit_spot_v2")

    assert market_data_runtime.state.last_trade_at[("BTC/USDT", "bybit_spot_v2")] is not None
    assert orderbook is not None
    assert str(orderbook.bids[0].price) == "68000.0"
    assert str(orderbook.asks[0].price) == "68000.5"
    assert diagnostics["trade_ingest_count"] == 1
    assert diagnostics["orderbook_ingest_count"] == 1
    assert diagnostics["trade_seen"] is True
    assert diagnostics["orderbook_seen"] is True
    assert diagnostics["best_bid"] == "68000.0"
    assert diagnostics["best_ask"] == "68000.5"
    assert diagnostics["persisted_trade_count"] == 1
    assert diagnostics["last_persisted_trade_symbol"] == "BTC/USDT"
    assert len(ledger_repository.records) == 1
    assert ledger_repository.records[0].normalized_symbol == "BTC/USDT"
    assert ledger_repository.records[0].live_trade_id == "trade-1"

    await connector.stop()
    await market_data_runtime.stop()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_bybit_spot_v2_transport_refreshes_quote_turnover_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    websocket = _StreamingWebSocket([json.dumps({"op": "subscribe", "success": True})])

    async def websocket_factory(_: BybitSpotV2TransportConfig) -> _StreamingWebSocket:
        return websocket

    monkeypatch.setattr(
        "cryptotechnolog.live_feed.bybit_spot_v2_transport.fetch_bybit_quote_turnover_24h_by_symbol",
        lambda **_: {"BTC/USDT": Decimal("123.45")},
    )

    connector = BybitSpotV2Transport(
        symbols=("BTC/USDT",),
        config=BybitSpotV2TransportConfig(
            ping_interval_seconds=3600,
            reconnect_delay_seconds=3600,
            quote_turnover_refresh_interval_seconds=3600,
        ),
        websocket_factory=websocket_factory,
    )

    task = asyncio.create_task(connector.run())
    await asyncio.wait_for(connector.run_started.wait(), timeout=1.0)

    async def wait_for_turnover() -> dict[str, object]:
        while True:
            diagnostics = connector.get_transport_diagnostics()
            if diagnostics["quote_turnover_24h_by_symbol"] == {"BTC/USDT": "123.45"}:
                return diagnostics
            await asyncio.sleep(0)

    diagnostics = await asyncio.wait_for(wait_for_turnover(), timeout=1.0)

    assert diagnostics["quote_turnover_last_error"] is None
    assert diagnostics["quote_turnover_last_synced_at"] is not None

    await connector.stop()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_bybit_spot_v2_transport_benign_pong_waiter_close_does_not_force_websocket_close() -> None:
    websocket = _BenignClosePingWebSocket([])
    connector = BybitSpotV2Transport(
        symbols=("BTC/USDT",),
        config=BybitSpotV2TransportConfig(
            ping_interval_seconds=3600,
            reconnect_delay_seconds=3600,
        ),
    )
    connector._active_websocket = websocket

    await connector._monitor_transport_rtt(websocket)

    diagnostics = connector.get_transport_diagnostics()
    assert websocket.closed is False
    assert diagnostics["last_error"] is None
    assert connector._suppress_cycle_failure_log is True


@pytest.mark.asyncio
async def test_bybit_spot_v2_transport_benign_recv_close_does_not_raise_transport_failure() -> None:
    websocket = _BenignCloseRecvWebSocket([])
    connector = BybitSpotV2Transport(
        symbols=("BTC/USDT",),
        config=BybitSpotV2TransportConfig(
            ping_interval_seconds=3600,
            reconnect_delay_seconds=3600,
        ),
    )

    await connector._consume_messages(websocket)

    diagnostics = connector.get_transport_diagnostics()
    assert diagnostics["last_error"] is None
    assert connector._suppress_cycle_failure_log is True

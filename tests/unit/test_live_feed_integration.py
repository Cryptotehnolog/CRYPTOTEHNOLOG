from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from cryptotechnolog.core.enhanced_event_bus import EnhancedEventBus
from cryptotechnolog.live_feed import (
    FeedConnectivityRuntime,
    FeedIngestRequest,
    FeedIngressEnvelope,
    FeedSessionIdentity,
    LiveFeedMarketDataIngress,
    UnsupportedFeedIngressError,
)
from cryptotechnolog.market_data import create_market_data_runtime


def _now() -> datetime:
    return datetime(2026, 3, 24, 16, 0, tzinfo=UTC)


def _session() -> FeedSessionIdentity:
    return FeedSessionIdentity(
        exchange="bybit",
        stream_kind="trade",
        subscription_scope=("BTC/USDT",),
    )


async def _connected_runtime() -> FeedConnectivityRuntime:
    runtime = FeedConnectivityRuntime(session=_session())
    current_time = _now()
    await runtime.start(observed_at=current_time)
    runtime.begin_connecting(observed_at=current_time + timedelta(seconds=1))
    runtime.mark_connected(observed_at=current_time + timedelta(seconds=2))
    return runtime


@pytest.mark.asyncio
async def test_ingest_helper_accepts_trade_tick_handoff_into_market_data_runtime() -> None:
    live_feed_runtime = await _connected_runtime()
    ingress = LiveFeedMarketDataIngress()
    market_data_runtime = create_market_data_runtime(
        event_bus=EnhancedEventBus(enable_persistence=False)
    )
    await market_data_runtime.start()

    request = live_feed_runtime.build_ingest_request(
        payload_kind="trade_tick",
        transport_payload={
            "price": "65000",
            "qty": "0.5",
            "side": "buy",
            "trade_id": "btc-1",
        },
        ingested_at=_now() + timedelta(seconds=3),
        source_sequence=1,
    )

    result = await ingress.ingest(
        request=request,
        market_data_runtime=market_data_runtime,
    )

    assert result.accepted_kind == "trade_tick"
    assert result.market_data_contract.symbol == "BTC/USDT"
    assert market_data_runtime.state.last_trade_at[("BTC/USDT", "bybit")] == _now() + timedelta(
        seconds=3
    )
    assert not hasattr(ingress, "client_registry")


@pytest.mark.asyncio
async def test_ingest_helper_accepts_orderbook_snapshot_handoff_into_market_data_runtime() -> None:
    live_feed_runtime = await _connected_runtime()
    ingress = LiveFeedMarketDataIngress()
    market_data_runtime = create_market_data_runtime(
        event_bus=EnhancedEventBus(enable_persistence=False)
    )
    await market_data_runtime.start()

    request = live_feed_runtime.build_ingest_request(
        payload_kind="orderbook_snapshot",
        transport_payload={
            "bids": [
                {"price": "65000", "qty": "10"},
                {"price": "64999.5", "qty": "7"},
            ],
            "asks": [
                {"price": "65000.5", "qty": "9"},
                {"price": "65001", "qty": "6"},
            ],
            "checksum": "abc123",
        },
        ingested_at=_now() + timedelta(seconds=4),
        source_sequence=2,
    )

    result = await ingress.ingest(
        request=request,
        market_data_runtime=market_data_runtime,
    )

    snapshot = market_data_runtime.orderbook_manager.get_snapshot("BTC/USDT", "bybit")
    assert result.accepted_kind == "orderbook_snapshot"
    assert snapshot is not None
    assert snapshot.checksum == "abc123"
    assert snapshot.bids[0].price < snapshot.asks[0].price


def test_ingest_helper_rejects_unsupported_or_invalid_handoff_combinations() -> None:
    ingress = LiveFeedMarketDataIngress()
    session = _session()
    current_time = _now()

    unsupported = FeedIngestRequest(
        envelope=FeedIngressEnvelope(
            session=session,
            payload_kind="funding_rate",
            ingested_at=current_time,
            transport_payload={"value": "0.01"},
        ),
        requested_at=current_time,
    )
    with pytest.raises(UnsupportedFeedIngressError, match="Неподдерживаемый payload_kind"):
        ingress.build_market_data_contract(unsupported)

    invalid_orderbook = FeedIngestRequest(
        envelope=FeedIngressEnvelope(
            session=session,
            payload_kind="orderbook_snapshot",
            ingested_at=current_time,
            transport_payload={"bids": [], "asks": []},
        ),
        requested_at=current_time,
    )
    with pytest.raises(UnsupportedFeedIngressError, match="non-empty bids и asks"):
        ingress.build_market_data_contract(invalid_orderbook)


def test_ingest_helper_preserves_boundary_and_does_not_create_market_data_ownership_drift() -> None:
    ingress = LiveFeedMarketDataIngress()

    assert not hasattr(ingress, "event_bus")
    assert not hasattr(ingress, "execution_runtime")
    assert not hasattr(ingress, "oms_runtime")

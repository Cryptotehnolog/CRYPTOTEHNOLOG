from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from cryptotechnolog.core.enhanced_event_bus import EnhancedEventBus
from cryptotechnolog.core.event import Event, SystemEventType
from cryptotechnolog.market_data import (
    InstrumentType,
    MarketDataRuntimeConfig,
    MarketDataSide,
    OrderBookLevel,
    OrderBookSnapshotContract,
    RawUniverseSnapshot,
    SymbolContract,
    UniversePolicyConfig,
    create_market_data_runtime,
)


def _collect_published_events(event_bus: EnhancedEventBus) -> list[Event]:
    events: list[Event] = []

    def capture(event: Event) -> None:
        events.append(event)

    event_bus.on("*", capture)
    return events


@pytest.mark.asyncio
async def test_market_data_runtime_publishes_tick_bar_and_quality_events() -> None:
    event_bus = EnhancedEventBus(enable_persistence=False)
    runtime = create_market_data_runtime(event_bus=event_bus)
    published_events = _collect_published_events(event_bus)

    await runtime.start()

    first_tick = runtime.tick_handler.normalize_tick(
        symbol="BTC/USDT",
        exchange="bybit",
        price=Decimal("50000"),
        quantity=Decimal("0.5"),
        side=MarketDataSide.BUY,
        timestamp=datetime(2026, 3, 19, 12, 0, 0, tzinfo=UTC),
        trade_id="btc-1",
    )
    second_tick = runtime.tick_handler.normalize_tick(
        symbol="BTC/USDT",
        exchange="bybit",
        price=Decimal("50001"),
        quantity=Decimal("0.25"),
        side=MarketDataSide.SELL,
        timestamp=datetime(2026, 3, 19, 12, 1, 5, tzinfo=UTC),
        trade_id="btc-2",
    )

    await runtime.ingest_tick(first_tick)
    update = await runtime.ingest_tick(second_tick)

    event_types = [event.event_type for event in published_events]
    assert SystemEventType.TICK_RECEIVED in event_types
    assert SystemEventType.BAR_COMPLETED in event_types
    assert SystemEventType.DATA_GAP_DETECTED in event_types
    assert update.bar_updates
    assert runtime.state.last_trade_at[("BTC/USDT", "bybit")] == second_tick.timestamp
    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["started"] is True
    assert diagnostics["ready"] is False
    assert diagnostics["last_tick_at"] == second_tick.timestamp.isoformat()


@pytest.mark.asyncio
async def test_market_data_runtime_publishes_orderbook_metrics_and_universe_events() -> None:
    event_bus = EnhancedEventBus(enable_persistence=False)
    runtime = create_market_data_runtime(
        event_bus=event_bus,
        config=MarketDataRuntimeConfig(
            universe_policy=UniversePolicyConfig(
                min_admissible_count_ready=1,
                min_confidence_ready=Decimal("0.50"),
                min_confidence_degraded=Decimal("0.30"),
                min_admissible_ratio_degraded=Decimal("0.10"),
            )
        ),
    )
    published_events = _collect_published_events(event_bus)

    await runtime.start()
    await runtime.ingest_tick(
        runtime.tick_handler.normalize_tick(
            symbol="ETH/USDT",
            exchange="okx",
            price=Decimal("3000"),
            quantity=Decimal("1"),
            side="buy",
            timestamp=datetime(2026, 3, 19, 12, 0, 0, tzinfo=UTC),
            trade_id="eth-1",
        )
    )

    snapshot = OrderBookSnapshotContract(
        symbol="ETH/USDT",
        exchange="okx",
        timestamp=datetime(2026, 3, 19, 12, 0, 1, tzinfo=UTC),
        bids=(
            OrderBookLevel(price=Decimal("3000"), quantity=Decimal("30")),
            OrderBookLevel(price=Decimal("2999.5"), quantity=Decimal("40")),
        ),
        asks=(
            OrderBookLevel(price=Decimal("3000.5"), quantity=Decimal("28")),
            OrderBookLevel(price=Decimal("3001"), quantity=Decimal("42")),
        ),
        spread_bps=Decimal("1.6666"),
    )
    await runtime.ingest_orderbook_snapshot(snapshot)
    metrics = await runtime.collect_symbol_metrics(
        symbol="ETH/USDT",
        exchange="okx",
        calculated_at=datetime(2026, 3, 19, 12, 0, 2, tzinfo=UTC),
        tick_coverage_ratio=Decimal("0.98"),
        average_latency_ms=Decimal("35"),
    )
    universe_update = await runtime.refresh_universe(
        raw_snapshot=RawUniverseSnapshot(
            version=1,
            created_at=datetime(2026, 3, 19, 12, 0, 3, tzinfo=UTC),
            symbols=(
                SymbolContract(
                    symbol="ETH/USDT",
                    exchange="okx",
                    base_asset="ETH",
                    quote_asset="USDT",
                    instrument_type=InstrumentType.PERPETUAL,
                ),
            ),
        )
    )

    event_types = [event.event_type for event in published_events]
    assert SystemEventType.ORDERBOOK_UPDATED in event_types
    assert SystemEventType.SYMBOL_METRICS_UPDATED in event_types
    assert SystemEventType.UNIVERSE_RAW_UPDATED in event_types
    assert SystemEventType.UNIVERSE_ADMISSIBLE_UPDATED in event_types
    assert SystemEventType.UNIVERSE_CONFIDENCE_UPDATED in event_types
    assert SystemEventType.UNIVERSE_READY in event_types
    assert SystemEventType.SYMBOL_ADMITTED_TO_UNIVERSE in event_types
    assert metrics.symbol == "ETH/USDT"
    assert runtime.state.metrics_by_identity[("ETH/USDT", "okx")] == metrics
    assert universe_update.policy_result.snapshot.is_admissible("ETH/USDT", "okx") is True
    assert runtime.state.quality_assessment is not None
    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["ready"] is True
    assert diagnostics["lifecycle_state"] == "ready"
    assert diagnostics["universe_confidence_state"] == "ready"


@pytest.mark.asyncio
async def test_market_data_runtime_publishes_stale_and_source_degraded_signals() -> None:
    event_bus = EnhancedEventBus(enable_persistence=False)
    runtime = create_market_data_runtime(event_bus=event_bus)
    published_events = _collect_published_events(event_bus)

    await runtime.start()
    await runtime.ingest_tick(
        runtime.tick_handler.normalize_tick(
            symbol="SOL/USDT",
            exchange="bybit",
            price=Decimal("100"),
            quantity=Decimal("2"),
            side="buy",
            timestamp=datetime(2026, 3, 19, 12, 0, 0, tzinfo=UTC),
            trade_id="sol-1",
        )
    )

    stale_signal = await runtime.check_staleness(
        symbol="SOL/USDT",
        exchange="bybit",
        feed="trades",
        now=datetime(2026, 3, 19, 12, 0, 10, tzinfo=UTC),
    )
    degraded_signal = await runtime.mark_source_degraded(
        symbol="SOL/USDT",
        exchange="bybit",
        feed="trades",
        reason="ws_timeout",
        detected_at=datetime(2026, 3, 19, 12, 0, 11, tzinfo=UTC),
    )

    event_types = [event.event_type for event in published_events]
    assert stale_signal is not None
    assert degraded_signal.details["reason"] == "ws_timeout"
    assert SystemEventType.MARKET_DATA_STALE in event_types
    assert SystemEventType.MARKET_DATA_SOURCE_DEGRADED in event_types


@pytest.mark.asyncio
async def test_market_data_runtime_keeps_exchange_specific_metrics_quality_and_admissibility() -> (
    None
):
    event_bus = EnhancedEventBus(enable_persistence=False)
    runtime = create_market_data_runtime(
        event_bus=event_bus,
        config=MarketDataRuntimeConfig(
            universe_policy=UniversePolicyConfig(
                min_admissible_count_ready=1,
                min_confidence_ready=Decimal("0.50"),
                min_confidence_degraded=Decimal("0.30"),
                min_admissible_ratio_degraded=Decimal("0.10"),
            )
        ),
    )

    await runtime.start()
    for exchange in ("bybit", "okx"):
        await runtime.ingest_tick(
            runtime.tick_handler.normalize_tick(
                symbol="BTC/USDT",
                exchange=exchange,
                price=Decimal("50000"),
                quantity=Decimal("1"),
                side="buy",
                timestamp=datetime(2026, 3, 19, 12, 0, 0, tzinfo=UTC),
                trade_id=f"{exchange}-trade",
            )
        )

    await runtime.ingest_orderbook_snapshot(
        OrderBookSnapshotContract(
            symbol="BTC/USDT",
            exchange="bybit",
            timestamp=datetime(2026, 3, 19, 12, 0, 1, tzinfo=UTC),
            bids=(OrderBookLevel(price=Decimal("50000"), quantity=Decimal("50")),),
            asks=(OrderBookLevel(price=Decimal("50001"), quantity=Decimal("55")),),
            spread_bps=Decimal("2"),
        )
    )
    await runtime.ingest_orderbook_snapshot(
        OrderBookSnapshotContract(
            symbol="BTC/USDT",
            exchange="okx",
            timestamp=datetime(2026, 3, 19, 12, 0, 1, tzinfo=UTC),
            bids=(OrderBookLevel(price=Decimal("50000"), quantity=Decimal("0.5")),),
            asks=(OrderBookLevel(price=Decimal("50200"), quantity=Decimal("0.5")),),
            spread_bps=Decimal("39.9202"),
        )
    )
    bybit_metrics = await runtime.collect_symbol_metrics(
        symbol="BTC/USDT",
        exchange="bybit",
        calculated_at=datetime(2026, 3, 19, 12, 0, 2, tzinfo=UTC),
        tick_coverage_ratio=Decimal("0.99"),
        average_latency_ms=Decimal("20"),
    )
    okx_metrics = await runtime.collect_symbol_metrics(
        symbol="BTC/USDT",
        exchange="okx",
        calculated_at=datetime(2026, 3, 19, 12, 0, 2, tzinfo=UTC),
        tick_coverage_ratio=Decimal("0.99"),
        average_latency_ms=Decimal("20"),
    )
    await runtime.mark_source_degraded(
        symbol="BTC/USDT",
        exchange="okx",
        feed="orderbook",
        reason="exchange_specific_gap",
        detected_at=datetime(2026, 3, 19, 12, 0, 3, tzinfo=UTC),
    )

    universe_update = await runtime.refresh_universe(
        raw_snapshot=RawUniverseSnapshot(
            version=2,
            created_at=datetime(2026, 3, 19, 12, 0, 4, tzinfo=UTC),
            symbols=(
                SymbolContract(
                    symbol="BTC/USDT",
                    exchange="bybit",
                    base_asset="BTC",
                    quote_asset="USDT",
                    instrument_type=InstrumentType.PERPETUAL,
                ),
                SymbolContract(
                    symbol="BTC/USDT",
                    exchange="okx",
                    base_asset="BTC",
                    quote_asset="USDT",
                    instrument_type=InstrumentType.PERPETUAL,
                ),
            ),
        )
    )

    assert runtime.state.metrics_by_identity[("BTC/USDT", "bybit")] == bybit_metrics
    assert runtime.state.metrics_by_identity[("BTC/USDT", "okx")] == okx_metrics
    assert runtime.state.quality_signals_by_identity[("BTC/USDT", "okx")]
    assert ("BTC/USDT", "bybit") in universe_update.admitted_symbols
    assert ("BTC/USDT", "okx") not in universe_update.admitted_symbols
    assert universe_update.policy_result.snapshot.is_admissible("BTC/USDT", "bybit") is True
    assert universe_update.policy_result.snapshot.is_admissible("BTC/USDT", "okx") is False
    assert universe_update.policy_result.snapshot.excluded_symbols[0].identity == (
        "BTC/USDT",
        "okx",
    )


@pytest.mark.asyncio
async def test_market_data_runtime_requires_start_and_resets_state_on_stop() -> None:
    event_bus = EnhancedEventBus(enable_persistence=False)
    runtime = create_market_data_runtime(event_bus=event_bus)

    tick = runtime.tick_handler.normalize_tick(
        symbol="BTC/USDT",
        exchange="bybit",
        price=Decimal("50000"),
        quantity=Decimal("1"),
        side="buy",
        timestamp=datetime(2026, 3, 19, 12, 0, 0, tzinfo=UTC),
        trade_id="btc-1",
    )

    with pytest.raises(RuntimeError, match="не запущен"):
        await runtime.ingest_tick(tick)

    await runtime.start()
    await runtime.ingest_tick(tick)
    await runtime.stop()

    diagnostics = runtime.get_runtime_diagnostics()
    assert runtime.state.raw_snapshot is None
    assert runtime.state.admissible_snapshot is None
    assert runtime.state.quality_assessment is None
    assert runtime.state.metrics_by_identity == {}
    assert diagnostics["started"] is False
    assert diagnostics["ready"] is False
    assert diagnostics["lifecycle_state"] == "stopped"
    assert diagnostics["readiness_reasons"] == ["runtime_stopped"]


@pytest.mark.asyncio
async def test_market_data_runtime_exposes_blocked_and_degraded_readiness_semantics() -> None:
    event_bus = EnhancedEventBus(enable_persistence=False)
    runtime = create_market_data_runtime(
        event_bus=event_bus,
        config=MarketDataRuntimeConfig(
            universe_policy=UniversePolicyConfig(
                min_admissible_count_ready=2,
                min_admissible_ratio_degraded=Decimal("0.10"),
                min_confidence_ready=Decimal("0.70"),
                min_confidence_degraded=Decimal("0.05"),
                min_top_of_book_depth_usd=Decimal("5000"),
                min_depth_5bps_usd=Decimal("5000"),
                min_quality_score=Decimal("0.10"),
            )
        ),
    )
    await runtime.start()

    blocked_update = await runtime.refresh_universe(
        raw_snapshot=RawUniverseSnapshot(
            version=10,
            created_at=datetime(2026, 3, 19, 12, 0, 0, tzinfo=UTC),
            symbols=(),
        )
    )
    blocked = runtime.get_runtime_diagnostics()
    assert blocked_update.policy_result.assessment.state.value == "blocked"
    assert blocked["ready"] is False
    assert blocked["lifecycle_state"] == "blocked"
    assert "universe_confidence_blocked" in blocked["readiness_reasons"]

    await runtime.ingest_tick(
        runtime.tick_handler.normalize_tick(
            symbol="S0/USDT",
            exchange="bybit",
            price=Decimal("100"),
            quantity=Decimal("1"),
            side="buy",
            timestamp=datetime(2026, 3, 19, 12, 0, 1, tzinfo=UTC),
            trade_id="s0-1",
        )
    )
    await runtime.ingest_orderbook_snapshot(
        OrderBookSnapshotContract(
            symbol="S0/USDT",
            exchange="bybit",
            timestamp=datetime(2026, 3, 19, 12, 0, 2, tzinfo=UTC),
            bids=(OrderBookLevel(price=Decimal("100"), quantity=Decimal("50")),),
            asks=(OrderBookLevel(price=Decimal("100.1"), quantity=Decimal("60")),),
            spread_bps=Decimal("9.9950"),
        )
    )
    await runtime.collect_symbol_metrics(
        symbol="S0/USDT",
        exchange="bybit",
        calculated_at=datetime(2026, 3, 19, 12, 0, 3, tzinfo=UTC),
        tick_coverage_ratio=Decimal("0.98"),
        average_latency_ms=Decimal("25"),
    )
    degraded_update = await runtime.refresh_universe(
        raw_snapshot=RawUniverseSnapshot(
            version=11,
            created_at=datetime(2026, 3, 19, 12, 0, 4, tzinfo=UTC),
            symbols=tuple(
                SymbolContract(
                    symbol=f"S{i}/USDT",
                    exchange="bybit",
                    base_asset=f"S{i}",
                    quote_asset="USDT",
                    instrument_type=InstrumentType.PERPETUAL,
                )
                for i in range(10)
            ),
        )
    )
    degraded = runtime.get_runtime_diagnostics()
    assert degraded_update.policy_result.assessment.state.value == "degraded"
    assert degraded["ready"] is False
    assert degraded["lifecycle_state"] == "degraded"
    assert "universe_confidence_degraded" in degraded["readiness_reasons"]

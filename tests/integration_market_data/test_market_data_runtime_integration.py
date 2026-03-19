from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from cryptotechnolog.core.enhanced_event_bus import EnhancedEventBus
from cryptotechnolog.core.event import SystemEventType
from cryptotechnolog.core.health import (
    ComponentHealth,
    HealthChecker,
    HealthStatus,
)
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
from cryptotechnolog.runtime_identity import build_runtime_identity


@pytest.mark.asyncio
@pytest.mark.integration
async def test_market_data_runtime_flow_updates_events_state_and_readiness_truth() -> None:
    """Phase 6 runtime должен проходить связанный flow без hidden bootstrap."""
    event_bus = EnhancedEventBus(enable_persistence=False)
    published_events: list[str] = []

    def capture_event(event) -> None:
        published_events.append(event.event_type)

    event_bus.on("*", capture_event)

    health_checker = HealthChecker(
        runtime_identity=build_runtime_identity(
            bootstrap_module="cryptotechnolog.bootstrap",
            bootstrap_mode="production",
            active_risk_path="phase5_risk_engine",
            config_identity="settings:test:d:\\CRYPTOTEHNOLOG\\config",
            config_revision="phase6-test",
        )
    )
    health_checker.register_check(_HealthyComponentCheck("phase6_runtime_contract"))
    health_checker.set_runtime_diagnostics(
        composition_root_built=True,
        runtime_started=True,
        runtime_ready=False,
        active_risk_path="phase5_risk_engine",
        config_identity="settings:test:d:\\CRYPTOTEHNOLOG\\config",
        config_revision="phase6-test",
    )

    def push_market_data_diagnostics(diagnostics: dict[str, object]) -> None:
        runtime_ready = bool(diagnostics.get("ready", False))
        health_checker.set_runtime_diagnostics(
            runtime_ready=runtime_ready,
            market_data_runtime=diagnostics,
        )

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
        diagnostics_sink=push_market_data_diagnostics,
    )

    await runtime.start()

    tick = runtime.tick_handler.normalize_tick(
        symbol="BTC/USDT",
        exchange="bybit",
        price=Decimal("50000"),
        quantity=Decimal("0.5"),
        side=MarketDataSide.BUY,
        timestamp=datetime(2026, 3, 19, 12, 0, 0, tzinfo=UTC),
        trade_id="btc-1",
    )
    await runtime.ingest_tick(tick)

    await runtime.ingest_orderbook_snapshot(
        OrderBookSnapshotContract(
            symbol="BTC/USDT",
            exchange="bybit",
            timestamp=datetime(2026, 3, 19, 12, 0, 1, tzinfo=UTC),
            bids=(
                OrderBookLevel(price=Decimal("50000"), quantity=Decimal("40")),
                OrderBookLevel(price=Decimal("49999"), quantity=Decimal("30")),
            ),
            asks=(
                OrderBookLevel(price=Decimal("50001"), quantity=Decimal("35")),
                OrderBookLevel(price=Decimal("50002"), quantity=Decimal("25")),
            ),
            spread_bps=Decimal("2"),
        )
    )

    await runtime.collect_symbol_metrics(
        symbol="BTC/USDT",
        exchange="bybit",
        calculated_at=datetime(2026, 3, 19, 12, 0, 2, tzinfo=UTC),
        tick_coverage_ratio=Decimal("0.99"),
        average_latency_ms=Decimal("15"),
        volume_24h_usd=Decimal("50000000"),
    )

    update = await runtime.refresh_universe(
        raw_snapshot=RawUniverseSnapshot(
            version=1,
            created_at=datetime(2026, 3, 19, 12, 0, 3, tzinfo=UTC),
            symbols=(
                SymbolContract(
                    symbol="BTC/USDT",
                    exchange="bybit",
                    base_asset="BTC",
                    quote_asset="USDT",
                    instrument_type=InstrumentType.PERPETUAL,
                ),
            ),
        )
    )

    diagnostics = runtime.get_runtime_diagnostics()
    health = await health_checker.check_system()

    assert update.policy_result.snapshot.is_admissible("BTC/USDT", "bybit") is True
    assert diagnostics["started"] is True
    assert diagnostics["ready"] is True
    assert diagnostics["lifecycle_state"] == "ready"
    assert diagnostics["raw_symbols_count"] == 1
    assert diagnostics["admissible_symbols_count"] == 1
    assert diagnostics["metrics_count"] == 1
    assert diagnostics["universe_confidence_state"] == "ready"
    assert SystemEventType.TICK_RECEIVED in published_events
    assert SystemEventType.ORDERBOOK_UPDATED in published_events
    assert SystemEventType.SYMBOL_METRICS_UPDATED in published_events
    assert SystemEventType.UNIVERSE_RAW_UPDATED in published_events
    assert SystemEventType.UNIVERSE_ADMISSIBLE_UPDATED in published_events
    assert SystemEventType.UNIVERSE_CONFIDENCE_UPDATED in published_events
    assert SystemEventType.UNIVERSE_READY in published_events
    assert health.overall_status == HealthStatus.HEALTHY
    assert health.readiness_status == "ready"
    assert health.diagnostics["market_data_runtime"]["ready"] is True
    assert health.diagnostics["market_data_runtime"]["admissible_symbols_count"] == 1


class _HealthyComponentCheck:
    """Минимальная healthy-check заглушка для integration-level readiness truth."""

    def __init__(self, name: str) -> None:
        self.name = name

    async def check(self) -> ComponentHealth:
        return ComponentHealth(
            component=self.name,
            status=HealthStatus.HEALTHY,
            message="Phase 6 integration harness ready",
        )

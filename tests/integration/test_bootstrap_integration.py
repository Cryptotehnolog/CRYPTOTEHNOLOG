from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from cryptotechnolog.analysis import (
    AdxSnapshot,
    AtrSnapshot,
    DerivedInputStatus,
    DerivedInputValidity,
    RiskDerivedInputsSnapshot,
)
from cryptotechnolog.bootstrap import (
    PHASE5_RISK_PATH,
    ProductionBootstrapPolicy,
    build_production_runtime,
)
from cryptotechnolog.config.settings import Settings
from cryptotechnolog.core.event import Event, SystemEventSource, SystemEventType
from cryptotechnolog.core.health import HealthStatus
from cryptotechnolog.intelligence import (
    DEFAULT_DERYA_CLASSIFICATION_BASIS,
    DeryaAssessment,
    DeryaRegime,
    DeryaResolutionState,
    IndicatorValidity,
    IndicatorValueStatus,
    IntelligenceEventType,
)
from cryptotechnolog.market_data import (
    MarketDataTimeframe,
    OHLCVBarContract,
    OrderBookLevel,
    OrderBookSnapshotContract,
)
from cryptotechnolog.market_data.events import (
    BarCompletedPayload,
    MarketDataEventType,
    build_market_data_event,
)
from cryptotechnolog.risk.engine import RiskEngineEventType
from cryptotechnolog.signals import SignalEventType


class _FakeConnection:
    def __init__(self) -> None:
        self.executed: list[tuple[str, tuple[object, ...]]] = []

    async def execute(self, query: str, *args: object) -> str:
        self.executed.append((query, args))
        normalized = " ".join(query.split())
        if "UPDATE state_machine_states" in normalized:
            return "UPDATE 1"
        if normalized in {"BEGIN", "COMMIT", "ROLLBACK"}:
            return normalized
        return "OK"


class _FakePool:
    def __init__(self) -> None:
        self.connection = _FakeConnection()

    @asynccontextmanager
    async def acquire(self):
        yield self.connection


class _FakeCounter:
    def inc(self) -> None:
        return None


class _FakeGauge:
    def set(self, _value: object) -> None:
        return None


def _make_settings() -> Settings:
    return Settings(
        environment="test",
        debug=True,
        base_r_percent=0.01,
        max_r_per_trade=0.02,
        max_portfolio_r=0.05,
        risk_max_total_exposure_usd=25000.0,
        max_position_size=5000.0,
        risk_starting_equity=10000.0,
        event_bus_redis_url="redis://localhost:6379",
    )


def _install_fake_database(runtime, fake_pool: _FakePool) -> None:
    async def db_connect() -> None:
        runtime.db_manager._connected = True
        runtime.db_manager._pool = fake_pool

    async def db_disconnect() -> None:
        runtime.db_manager._connected = False
        runtime.db_manager._pool = None

    async def db_health_check() -> dict[str, object]:
        return {
            "status": "healthy" if runtime.db_manager.is_connected else "unhealthy",
            "connected": runtime.db_manager.is_connected,
            "pool_size": 1,
            "pool_max_size": 1,
        }

    async def db_fetchrow(query: str, *_args: object):
        normalized = " ".join(query.split())
        if "SELECT current_state, version FROM state_machine_states" in normalized:
            return {
                "current_state": "boot",
                "version": 0,
            }
        return None

    async def db_execute(query: str, *args: object) -> str:
        return await fake_pool.connection.execute(query, *args)

    runtime.db_manager.connect = db_connect  # type: ignore[method-assign]
    runtime.db_manager.disconnect = db_disconnect  # type: ignore[method-assign]
    runtime.db_manager.close = db_disconnect  # type: ignore[method-assign]
    runtime.db_manager.health_check = db_health_check  # type: ignore[method-assign]
    runtime.db_manager.fetchrow = db_fetchrow  # type: ignore[method-assign]
    runtime.db_manager.execute = db_execute  # type: ignore[method-assign]


def _install_fake_redis(runtime) -> None:
    async def redis_ping() -> None:
        runtime.redis_manager._connected = True
        runtime.redis_manager._redis = object()

    async def redis_disconnect() -> None:
        runtime.redis_manager._connected = False
        runtime.redis_manager._redis = None

    async def redis_health_check() -> dict[str, object]:
        return {
            "status": "healthy" if runtime.redis_manager.is_connected else "unhealthy",
            "connected": runtime.redis_manager.is_connected,
            "max_connections": 1,
        }

    runtime.redis_manager.ping = redis_ping  # type: ignore[method-assign]
    runtime.redis_manager.disconnect = redis_disconnect  # type: ignore[method-assign]
    runtime.redis_manager.close = redis_disconnect  # type: ignore[method-assign]
    runtime.redis_manager.health_check = redis_health_check  # type: ignore[method-assign]


def _install_fake_metrics(runtime) -> None:
    runtime.metrics_collector.get_counter = lambda _name: _FakeCounter()  # type: ignore[method-assign]
    runtime.metrics_collector.get_gauge = lambda _name: _FakeGauge()  # type: ignore[method-assign]


def _capture_lifecycle_events(runtime) -> list[str]:
    lifecycle_events: list[str] = []

    def capture_lifecycle_event(event) -> None:
        lifecycle_events.append(event.event_type)

    runtime.event_bus.on(SystemEventType.SYSTEM_BOOT, capture_lifecycle_event)
    runtime.event_bus.on(SystemEventType.SYSTEM_READY, capture_lifecycle_event)
    return lifecycle_events


def _make_completed_bar(index: int) -> OHLCVBarContract:
    open_time = datetime(2026, 3, 20, 12, index, tzinfo=UTC)
    close_time = datetime(2026, 3, 20, 12, index + 1, tzinfo=UTC)
    return OHLCVBarContract(
        symbol="BTC/USDT",
        exchange="bybit",
        timeframe=MarketDataTimeframe.M1,
        open_time=open_time,
        close_time=close_time,
        open=Decimal("100"),
        high=Decimal("110"),
        low=Decimal("100"),
        close=Decimal("109"),
        volume=Decimal("15"),
        bid_volume=Decimal("5"),
        ask_volume=Decimal("10"),
        trades_count=3,
        is_closed=True,
    )


def _make_trending_completed_bar(index: int) -> OHLCVBarContract:
    open_time = datetime(2026, 3, 20, 13, index, tzinfo=UTC)
    close_time = open_time + timedelta(minutes=1)
    base = Decimal("100") + Decimal(index)
    return OHLCVBarContract(
        symbol="BTC/USDT",
        exchange="bybit",
        timeframe=MarketDataTimeframe.M1,
        open_time=open_time,
        close_time=close_time,
        open=base,
        high=base + Decimal("2"),
        low=base - Decimal("1"),
        close=base + Decimal("1"),
        volume=Decimal("20"),
        bid_volume=Decimal("8"),
        ask_volume=Decimal("12"),
        trades_count=5,
        is_closed=True,
    )


def _make_orderbook_snapshot() -> OrderBookSnapshotContract:
    return OrderBookSnapshotContract(
        symbol="BTC/USDT",
        exchange="bybit",
        timestamp=datetime(2026, 3, 20, 12, 0, 30, tzinfo=UTC),
        bids=(OrderBookLevel(price=Decimal("109.8"), quantity=Decimal("10")),),
        asks=(OrderBookLevel(price=Decimal("110.2"), quantity=Decimal("12")),),
        spread_bps=Decimal("3.6406"),
    )


def _make_ready_derived_inputs() -> RiskDerivedInputsSnapshot:
    updated_at = datetime(2026, 3, 20, 12, 27, tzinfo=UTC)
    validity = DerivedInputValidity(
        status=DerivedInputStatus.VALID,
        observed_bars=20,
        required_bars=14,
    )
    return RiskDerivedInputsSnapshot(
        symbol="BTC/USDT",
        exchange="bybit",
        timeframe=MarketDataTimeframe.M1,
        updated_at=updated_at,
        atr=AtrSnapshot(
            symbol="BTC/USDT",
            exchange="bybit",
            timeframe=MarketDataTimeframe.M1,
            updated_at=updated_at,
            period=14,
            value=Decimal("2"),
            validity=validity,
        ),
        adx=AdxSnapshot(
            symbol="BTC/USDT",
            exchange="bybit",
            timeframe=MarketDataTimeframe.M1,
            updated_at=updated_at,
            period=14,
            value=Decimal("30"),
            validity=validity,
        ),
    )


def _make_ready_derya() -> DeryaAssessment:
    updated_at = datetime(2026, 3, 20, 12, 27, tzinfo=UTC)
    return DeryaAssessment(
        symbol="BTC/USDT",
        exchange="bybit",
        timeframe=MarketDataTimeframe.M1,
        updated_at=updated_at,
        validity=IndicatorValidity(
            status=IndicatorValueStatus.VALID,
            observed_bars=10,
            required_bars=4,
        ),
        confidence=Decimal("0.7000"),
        raw_efficiency=Decimal("0.8"),
        smoothed_efficiency=Decimal("0.75"),
        efficiency_slope=Decimal("0.03"),
        current_regime=DeryaRegime.EXPANSION,
        previous_regime=DeryaRegime.EXHAUSTION,
        resolution_state=DeryaResolutionState.STABLE,
        regime_duration_bars=4,
        regime_persistence_ratio=Decimal("1"),
        classification_basis=DEFAULT_DERYA_CLASSIFICATION_BASIS,
    )


def _make_order_filled_event() -> Event:
    return Event.new(
        SystemEventType.ORDER_FILLED,
        SystemEventSource.EXECUTION_CORE,
        {
            "position_id": "pos-1",
            "symbol": "BTC/USDT",
            "side": "buy",
            "filled_qty": "2",
            "avg_price": "100",
            "stop_loss": "95",
            "risk_capital_usd": "10000",
        },
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_production_composition_root_builds_and_starts_real_runtime_contract() -> None:
    """Composition root должен реально собрать и поднять production runtime contract."""
    runtime = await build_production_runtime(
        settings=_make_settings(),
        policy=ProductionBootstrapPolicy(
            test_mode=True,
            enable_event_bus_persistence=False,
            enable_risk_persistence=False,
        ),
    )

    fake_pool = _FakePool()
    lifecycle_events = _capture_lifecycle_events(runtime)
    _install_fake_database(runtime, fake_pool)
    _install_fake_redis(runtime)
    _install_fake_metrics(runtime)

    await runtime.startup()

    diagnostics = runtime.get_runtime_diagnostics()
    health = await runtime.health_checker.check_system()

    assert runtime.is_started is True
    assert runtime.controller.is_running is True
    assert runtime.identity.active_risk_path == PHASE5_RISK_PATH
    assert runtime.event_bus.active_risk_path == PHASE5_RISK_PATH
    assert runtime.event_bus.listener_registry is runtime.listener_registry
    assert runtime.risk_runtime.is_started is True
    assert diagnostics["runtime_started"] is True
    assert diagnostics["runtime_ready"] is False
    assert diagnostics["config_identity"] == runtime.identity.config_identity
    assert diagnostics["config_revision"] == runtime.identity.config_revision
    assert "phase6_market_data:not_ready" in diagnostics["degraded_reasons"]
    assert "c7r_shared_analysis:not_ready" in diagnostics["degraded_reasons"]
    assert "phase7_intelligence:not_ready" in diagnostics["degraded_reasons"]
    assert "phase8_signal:not_ready" in diagnostics["degraded_reasons"]
    assert health.overall_status == HealthStatus.HEALTHY
    assert health.readiness_status == "not_ready"
    assert health.runtime_identity == runtime.identity
    assert health.diagnostics["active_risk_path"] == PHASE5_RISK_PATH
    assert health.diagnostics["config_identity"] == runtime.identity.config_identity
    assert health.diagnostics["config_revision"] == runtime.identity.config_revision
    assert "market_data_runtime_not_ready" in health.readiness_reasons
    assert "shared_analysis_runtime_not_ready" in health.readiness_reasons
    assert "intelligence_runtime_not_ready" in health.readiness_reasons
    assert "signal_runtime_not_ready" in health.readiness_reasons
    assert SystemEventType.SYSTEM_BOOT in lifecycle_events
    assert SystemEventType.SYSTEM_READY in lifecycle_events

    await runtime.shutdown(force=True)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_signal_runtime_is_explicitly_wired_to_existing_truth_path() -> None:
    """Phase 8 runtime должен получать existing truths через composition-root wiring."""
    runtime = await build_production_runtime(
        settings=_make_settings(),
        policy=ProductionBootstrapPolicy(
            test_mode=True,
            enable_event_bus_persistence=False,
            enable_risk_persistence=False,
        ),
    )

    fake_pool = _FakePool()
    _install_fake_database(runtime, fake_pool)
    _install_fake_redis(runtime)
    _install_fake_metrics(runtime)

    captured_signal_events: list[Event] = []
    runtime.event_bus.on(
        SignalEventType.SIGNAL_SNAPSHOT_UPDATED.value,
        captured_signal_events.append,
    )

    await runtime.startup()
    await runtime.market_data_runtime.ingest_orderbook_snapshot(_make_orderbook_snapshot())

    for index in range(28):
        bar = _make_completed_bar(index)
        event = build_market_data_event(
            event_type=MarketDataEventType.BAR_COMPLETED,
            payload=BarCompletedPayload.from_contract(bar),
        )
        await runtime.event_bus.publish(event)

    diagnostics = runtime.get_runtime_diagnostics()
    signal_diagnostics = diagnostics["signal_runtime"]
    signal = runtime.signal_runtime.get_signal(
        exchange="bybit",
        symbol="BTC/USDT",
        timeframe=MarketDataTimeframe.M1,
    )
    context = runtime.signal_runtime.get_signal_context(
        exchange="bybit",
        symbol="BTC/USDT",
        timeframe=MarketDataTimeframe.M1,
    )

    assert runtime.signal_runtime.is_started is True
    assert signal_diagnostics["started"] is True
    assert signal_diagnostics["ready"] is True
    assert signal_diagnostics["tracked_signal_keys"] == 1
    assert signal_diagnostics["last_context_at"] is not None
    assert signal_diagnostics["last_event_type"] == SignalEventType.SIGNAL_SNAPSHOT_UPDATED.value
    assert context is not None
    assert context.derived_inputs is not None
    assert context.derya is not None
    assert signal is not None
    assert signal.status.value == "suppressed"
    assert captured_signal_events

    await runtime.shutdown(force=True)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_signal_runtime_publishes_signal_emitted_through_integrated_runtime_path() -> None:
    """Integrated signal wiring должен публиковать SIGNAL_EMITTED из existing truths."""
    runtime = await build_production_runtime(
        settings=_make_settings(),
        policy=ProductionBootstrapPolicy(
            test_mode=True,
            enable_event_bus_persistence=False,
            enable_risk_persistence=False,
        ),
    )

    fake_pool = _FakePool()
    _install_fake_database(runtime, fake_pool)
    _install_fake_redis(runtime)
    _install_fake_metrics(runtime)

    captured_signal_events: list[Event] = []
    runtime.event_bus.on(
        SignalEventType.SIGNAL_EMITTED.value,
        captured_signal_events.append,
    )

    await runtime.startup()
    await runtime.market_data_runtime.ingest_orderbook_snapshot(_make_orderbook_snapshot())
    runtime.shared_analysis_runtime.get_risk_derived_inputs = lambda **_kwargs: (
        _make_ready_derived_inputs()
    )  # type: ignore[method-assign]
    runtime.intelligence_runtime.get_derya_assessment = lambda **_kwargs: _make_ready_derya()  # type: ignore[method-assign]

    bar = _make_completed_bar(0)
    event = build_market_data_event(
        event_type=MarketDataEventType.BAR_COMPLETED,
        payload=BarCompletedPayload.from_contract(bar),
    )
    await runtime.event_bus.publish(event)

    diagnostics = runtime.get_runtime_diagnostics()
    signal_diagnostics = diagnostics["signal_runtime"]
    signal = runtime.signal_runtime.get_signal(
        exchange="bybit",
        symbol="BTC/USDT",
        timeframe=MarketDataTimeframe.M1,
    )

    assert signal is not None
    assert signal.status.value == "active"
    assert signal.direction is not None
    assert signal_diagnostics["ready"] is True
    assert signal_diagnostics["active_signal_keys"] == 1
    assert signal_diagnostics["last_event_type"] == SignalEventType.SIGNAL_EMITTED.value
    assert captured_signal_events
    assert captured_signal_events[-1].payload["status"] == "active"
    assert captured_signal_events[-1].payload["direction"] == "BUY"
    assert captured_signal_events[-1].payload["symbol"] == "BTC/USDT"

    await runtime.shutdown(force=True)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_signal_runtime_publishes_signal_invalidated_when_existing_truth_disappears() -> None:
    """Integrated signal wiring не должен маскировать invalidation как обычный update."""
    runtime = await build_production_runtime(
        settings=_make_settings(),
        policy=ProductionBootstrapPolicy(
            test_mode=True,
            enable_event_bus_persistence=False,
            enable_risk_persistence=False,
        ),
    )

    fake_pool = _FakePool()
    _install_fake_database(runtime, fake_pool)
    _install_fake_redis(runtime)
    _install_fake_metrics(runtime)

    captured_invalidations: list[Event] = []
    runtime.event_bus.on(
        SignalEventType.SIGNAL_INVALIDATED.value,
        captured_invalidations.append,
    )

    await runtime.startup()
    await runtime.market_data_runtime.ingest_orderbook_snapshot(_make_orderbook_snapshot())
    runtime.shared_analysis_runtime.get_risk_derived_inputs = lambda **_kwargs: (
        _make_ready_derived_inputs()
    )  # type: ignore[method-assign]
    runtime.intelligence_runtime.get_derya_assessment = lambda **_kwargs: _make_ready_derya()  # type: ignore[method-assign]

    first_bar = _make_completed_bar(0)
    first_event = build_market_data_event(
        event_type=MarketDataEventType.BAR_COMPLETED,
        payload=BarCompletedPayload.from_contract(first_bar),
    )
    await runtime.event_bus.publish(first_event)

    active = runtime.signal_runtime.get_signal(
        exchange="bybit",
        symbol="BTC/USDT",
        timeframe=MarketDataTimeframe.M1,
    )
    assert active is not None
    assert active.status.value == "active"

    runtime.shared_analysis_runtime.get_risk_derived_inputs = lambda **_kwargs: None  # type: ignore[method-assign]
    second_bar = _make_completed_bar(1)
    second_event = build_market_data_event(
        event_type=MarketDataEventType.BAR_COMPLETED,
        payload=BarCompletedPayload.from_contract(second_bar),
    )
    await runtime.event_bus.publish(second_event)

    diagnostics = runtime.get_runtime_diagnostics()
    signal_diagnostics = diagnostics["signal_runtime"]
    invalidated = runtime.signal_runtime.get_signal(
        exchange="bybit",
        symbol="BTC/USDT",
        timeframe=MarketDataTimeframe.M1,
    )

    assert invalidated is not None
    assert invalidated.signal_id == active.signal_id
    assert invalidated.status.value == "invalidated"
    assert invalidated.validity.status.value == "warming"
    assert signal_diagnostics["ready"] is False
    assert signal_diagnostics["invalidated_signal_keys"] == 1
    assert signal_diagnostics["last_event_type"] == SignalEventType.SIGNAL_INVALIDATED.value
    assert captured_invalidations
    assert captured_invalidations[-1].payload["status"] == "invalidated"
    assert captured_invalidations[-1].payload["validity_status"] == "warming"

    await runtime.shutdown(force=True)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_intelligence_runtime_is_explicitly_wired_to_bar_completed_path() -> None:
    """Phase 7 runtime должен получать BAR_COMPLETED через composition-root wiring."""
    runtime = await build_production_runtime(
        settings=_make_settings(),
        policy=ProductionBootstrapPolicy(
            test_mode=True,
            enable_event_bus_persistence=False,
            enable_risk_persistence=False,
        ),
    )

    fake_pool = _FakePool()
    _install_fake_database(runtime, fake_pool)
    _install_fake_redis(runtime)
    _install_fake_metrics(runtime)
    captured_transitions: list[str] = []

    def capture_transition(event) -> None:
        captured_transitions.append(event.event_type)

    runtime.event_bus.on(IntelligenceEventType.DERYA_REGIME_CHANGED.value, capture_transition)

    await runtime.startup()

    for index in range(4):
        bar = _make_completed_bar(index)
        event = build_market_data_event(
            event_type=MarketDataEventType.BAR_COMPLETED,
            payload=BarCompletedPayload.from_contract(bar),
        )
        await runtime.event_bus.publish(event)

    diagnostics = runtime.get_runtime_diagnostics()
    intelligence_diagnostics = diagnostics["intelligence_runtime"]
    shared_analysis_diagnostics = diagnostics["shared_analysis_runtime"]
    assessment = runtime.intelligence_runtime.get_derya_assessment(
        exchange="bybit",
        symbol="BTC/USDT",
        timeframe=MarketDataTimeframe.M1,
    )
    shared_inputs = runtime.shared_analysis_runtime.get_risk_derived_inputs(
        exchange="bybit",
        symbol="BTC/USDT",
        timeframe=MarketDataTimeframe.M1,
    )

    assert runtime.intelligence_runtime.is_started is True
    assert runtime.shared_analysis_runtime.is_started is True
    assert intelligence_diagnostics["started"] is True
    assert shared_analysis_diagnostics["started"] is True
    assert intelligence_diagnostics["tracked_derya_keys"] == 1
    assert shared_analysis_diagnostics["tracked_keys"] == 1
    assert intelligence_diagnostics["last_bar_at"] is not None
    assert shared_analysis_diagnostics["last_bar_at"] is not None
    assert intelligence_diagnostics["ready"] is True
    assert shared_analysis_diagnostics["ready"] is False
    assert assessment is not None
    assert shared_inputs is not None
    assert shared_inputs.atr.value is None
    assert assessment.current_regime is not None
    assert IntelligenceEventType.DERYA_REGIME_CHANGED.value in captured_transitions

    await runtime.shutdown(force=True)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_intelligence_runtime_ingest_failure_is_visible_in_runtime_truth() -> None:
    """DERYA ingest failure не должен маскироваться внутри BAR_COMPLETED wiring."""
    runtime = await build_production_runtime(
        settings=_make_settings(),
        policy=ProductionBootstrapPolicy(
            test_mode=True,
            enable_event_bus_persistence=False,
            enable_risk_persistence=False,
        ),
    )

    fake_pool = _FakePool()
    _install_fake_database(runtime, fake_pool)
    _install_fake_redis(runtime)
    _install_fake_metrics(runtime)

    await runtime.startup()

    def raise_ingest_failure(_payload: BarCompletedPayload) -> None:
        raise RuntimeError("derya_ingest_failure")

    runtime.intelligence_runtime.ingest_bar_completed_payload = raise_ingest_failure  # type: ignore[method-assign]

    bar = _make_completed_bar(0)
    event = build_market_data_event(
        event_type=MarketDataEventType.BAR_COMPLETED,
        payload=BarCompletedPayload.from_contract(bar),
    )

    await runtime.event_bus.publish(event)

    diagnostics = runtime.get_runtime_diagnostics()
    intelligence_diagnostics = diagnostics["intelligence_runtime"]
    shared_analysis_diagnostics = diagnostics["shared_analysis_runtime"]
    health = await runtime.health_checker.check_system()

    assert intelligence_diagnostics["started"] is True
    assert intelligence_diagnostics["ready"] is False
    assert intelligence_diagnostics["lifecycle_state"] == "degraded"
    assert (
        intelligence_diagnostics["last_failure_reason"] == "bar_ingest_failed:derya_ingest_failure"
    )
    assert intelligence_diagnostics["degraded_reasons"] == [
        "bar_ingest_failed:derya_ingest_failure"
    ]
    assert shared_analysis_diagnostics["started"] is True
    assert "intelligence_runtime_not_ready" in health.readiness_reasons
    assert "intelligence:bar_ingest_failed:derya_ingest_failure" in health.readiness_reasons

    await runtime.shutdown(force=True)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_signal_runtime_missing_analysis_and_intelligence_is_visible_in_runtime_truth() -> (
    None
):
    """Signal runtime не должен маскировать incomplete context как ready."""
    runtime = await build_production_runtime(
        settings=_make_settings(),
        policy=ProductionBootstrapPolicy(
            test_mode=True,
            enable_event_bus_persistence=False,
            enable_risk_persistence=False,
        ),
    )

    fake_pool = _FakePool()
    _install_fake_database(runtime, fake_pool)
    _install_fake_redis(runtime)
    _install_fake_metrics(runtime)

    await runtime.startup()

    bar = _make_completed_bar(0)
    event = build_market_data_event(
        event_type=MarketDataEventType.BAR_COMPLETED,
        payload=BarCompletedPayload.from_contract(bar),
    )
    await runtime.event_bus.publish(event)

    diagnostics = runtime.get_runtime_diagnostics()
    signal_diagnostics = diagnostics["signal_runtime"]
    health = await runtime.health_checker.check_system()

    assert signal_diagnostics["started"] is True
    assert signal_diagnostics["ready"] is False
    assert signal_diagnostics["lifecycle_state"] == "warming"
    assert signal_diagnostics["tracked_signal_keys"] == 1
    assert signal_diagnostics["readiness_reasons"] == ["signal_context_warming"]
    assert "signal_runtime_not_ready" in health.readiness_reasons

    await runtime.shutdown(force=True)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_intelligence_runtime_shutdown_resets_nested_diagnostics() -> None:
    """Shutdown должен оставлять operator-visible intelligence diagnostics в stopped state."""
    runtime = await build_production_runtime(
        settings=_make_settings(),
        policy=ProductionBootstrapPolicy(
            test_mode=True,
            enable_event_bus_persistence=False,
            enable_risk_persistence=False,
        ),
    )

    fake_pool = _FakePool()
    _install_fake_database(runtime, fake_pool)
    _install_fake_redis(runtime)
    _install_fake_metrics(runtime)

    await runtime.startup()

    for index in range(4):
        bar = _make_completed_bar(index)
        event = build_market_data_event(
            event_type=MarketDataEventType.BAR_COMPLETED,
            payload=BarCompletedPayload.from_contract(bar),
        )
        await runtime.event_bus.publish(event)

    await runtime.shutdown(force=True)

    diagnostics = runtime.get_runtime_diagnostics()
    intelligence_diagnostics = diagnostics["intelligence_runtime"]
    shared_analysis_diagnostics = diagnostics["shared_analysis_runtime"]
    signal_diagnostics = diagnostics["signal_runtime"]

    assert intelligence_diagnostics["started"] is False
    assert intelligence_diagnostics["ready"] is False
    assert intelligence_diagnostics["lifecycle_state"] == "stopped"
    assert intelligence_diagnostics["last_bar_at"] is None
    assert intelligence_diagnostics["last_derya_regime_event_type"] is None
    assert intelligence_diagnostics["last_failure_reason"] is None
    assert intelligence_diagnostics["readiness_reasons"] == ["runtime_stopped"]
    assert intelligence_diagnostics["degraded_reasons"] == []
    assert shared_analysis_diagnostics["started"] is False
    assert shared_analysis_diagnostics["ready"] is False
    assert shared_analysis_diagnostics["lifecycle_state"] == "stopped"
    assert shared_analysis_diagnostics["tracked_keys"] == 0
    assert shared_analysis_diagnostics["readiness_reasons"] == ["runtime_stopped"]
    assert signal_diagnostics["started"] is False
    assert signal_diagnostics["ready"] is False
    assert signal_diagnostics["lifecycle_state"] == "stopped"
    assert signal_diagnostics["tracked_signal_keys"] == 0
    assert signal_diagnostics["active_signal_keys"] == 0
    assert signal_diagnostics["invalidated_signal_keys"] == 0
    assert signal_diagnostics["expired_signal_keys"] == 0
    assert signal_diagnostics["last_context_at"] is None
    assert signal_diagnostics["last_signal_id"] is None
    assert signal_diagnostics["last_event_type"] is None
    assert signal_diagnostics["last_failure_reason"] is None
    assert signal_diagnostics["readiness_reasons"] == ["runtime_stopped"]
    assert signal_diagnostics["degraded_reasons"] == []


@pytest.mark.asyncio
@pytest.mark.integration
async def test_shared_analysis_runtime_publishes_honest_risk_bar_completed_for_active_risk_path() -> (
    None
):
    """Production wiring должен публиковать RISK_BAR_COMPLETED только из полного набора truth sources."""
    runtime = await build_production_runtime(
        settings=_make_settings(),
        policy=ProductionBootstrapPolicy(
            test_mode=True,
            enable_event_bus_persistence=False,
            enable_risk_persistence=False,
        ),
    )

    fake_pool = _FakePool()
    _install_fake_database(runtime, fake_pool)
    _install_fake_redis(runtime)
    _install_fake_metrics(runtime)

    captured_risk_bars: list[Event] = []
    trailing_events: list[Event] = []

    runtime.event_bus.on(SystemEventType.RISK_BAR_COMPLETED, captured_risk_bars.append)
    runtime.event_bus.on(RiskEngineEventType.TRAILING_STOP_MOVED, trailing_events.append)

    await runtime.startup()
    await runtime.market_data_runtime.ingest_orderbook_snapshot(_make_orderbook_snapshot())
    await runtime.event_bus.publish(_make_order_filled_event())

    for index in range(28):
        bar = _make_trending_completed_bar(index)
        event = build_market_data_event(
            event_type=MarketDataEventType.BAR_COMPLETED,
            payload=BarCompletedPayload.from_contract(bar),
        )
        await runtime.event_bus.publish(event)

    diagnostics = runtime.get_runtime_diagnostics()
    shared_analysis_diagnostics = diagnostics["shared_analysis_runtime"]
    shared_inputs = runtime.shared_analysis_runtime.get_risk_derived_inputs(
        exchange="bybit",
        symbol="BTC/USDT",
        timeframe=MarketDataTimeframe.M1,
    )

    assert shared_inputs is not None
    assert shared_inputs.is_fully_ready is True
    assert shared_inputs.atr.value is not None
    assert shared_inputs.adx.value is not None
    assert shared_analysis_diagnostics["ready"] is True
    assert captured_risk_bars
    assert captured_risk_bars[-1].payload["atr"] == str(shared_inputs.atr.value)
    assert captured_risk_bars[-1].payload["adx"] == str(shared_inputs.adx.value)
    assert captured_risk_bars[-1].payload["best_bid"] == "109.8"
    assert captured_risk_bars[-1].payload["best_ask"] == "110.2"
    assert trailing_events
    assert trailing_events[-1].payload["position_id"] == "pos-1"

    await runtime.shutdown(force=True)

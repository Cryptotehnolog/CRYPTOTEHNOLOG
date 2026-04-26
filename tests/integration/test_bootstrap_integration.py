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
from cryptotechnolog.execution import ExecutionEventType
from cryptotechnolog.intelligence import (
    DEFAULT_DERYA_CLASSIFICATION_BASIS,
    DeryaAssessment,
    DeryaRegime,
    DeryaResolutionState,
    IndicatorValidity,
    IndicatorValueStatus,
    IntelligenceEventType,
)
from cryptotechnolog.manager import ManagerEventType
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
from cryptotechnolog.oms import OmsEventType
from cryptotechnolog.opportunity import OpportunityEventType
from cryptotechnolog.orchestration import OrchestrationEventType
from cryptotechnolog.paper import PaperEventType
from cryptotechnolog.portfolio_governor import PortfolioGovernorEventType
from cryptotechnolog.position_expansion import PositionExpansionEventType
from cryptotechnolog.protection import ProtectionEventType
from cryptotechnolog.risk.engine import RiskEngineEventType
from cryptotechnolog.signals import SignalEventType
from cryptotechnolog.strategy import StrategyEventType
from cryptotechnolog.validation import ValidationEventType


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

    async def redis_health_check(*, include_stats: bool = False) -> dict[str, object]:
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


async def _build_test_runtime():
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
    return runtime


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
            "exchange": "bybit",
            "side": "buy",
            "filled_qty": "2",
            "avg_price": "100",
            "stop_loss": "95",
            "risk_capital_usd": "10000",
        },
    )


async def _startup_with_orderbook(runtime) -> None:
    await runtime.startup()
    await runtime.market_data_runtime.ingest_orderbook_snapshot(_make_orderbook_snapshot())


def _install_ready_upstream_truths(runtime) -> None:
    runtime.shared_analysis_runtime.get_risk_derived_inputs = lambda **_kwargs: (
        _make_ready_derived_inputs()
    )  # type: ignore[method-assign]
    runtime.intelligence_runtime.get_derya_assessment = lambda **_kwargs: _make_ready_derya()  # type: ignore[method-assign]


async def _publish_completed_bars(
    runtime,
    *,
    count: int,
    start_index: int = 0,
    bar_factory=_make_completed_bar,
) -> None:
    for index in range(start_index, start_index + count):
        bar = bar_factory(index)
        event = build_market_data_event(
            event_type=MarketDataEventType.BAR_COMPLETED,
            payload=BarCompletedPayload.from_contract(bar),
        )
        await runtime.event_bus.publish(event)


def _register_event_captures(runtime, *registrations: tuple[str, object]) -> None:
    for event_type, sink in registrations:
        runtime.event_bus.on(event_type, sink)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_production_composition_root_builds_and_starts_real_runtime_contract() -> None:  # noqa: PLR0915
    """Composition root должен реально собрать и поднять production runtime contract."""
    runtime = await _build_test_runtime()
    lifecycle_events = _capture_lifecycle_events(runtime)

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
    assert "phase9_strategy:not_ready" in diagnostics["degraded_reasons"]
    assert "phase10_execution:not_ready" in diagnostics["degraded_reasons"]
    assert "phase16_oms:not_ready" in diagnostics["degraded_reasons"]
    assert "phase11_opportunity:not_ready" in diagnostics["degraded_reasons"]
    assert "phase12_orchestration:not_ready" in diagnostics["degraded_reasons"]
    assert "phase13_position_expansion:not_ready" in diagnostics["degraded_reasons"]
    assert "phase14_portfolio_governor:not_ready" in diagnostics["degraded_reasons"]
    assert "phase15_protection:not_ready" in diagnostics["degraded_reasons"]
    assert "phase17_manager:not_ready" in diagnostics["degraded_reasons"]
    assert "phase18_validation:not_ready" in diagnostics["degraded_reasons"]
    assert "phase19_paper:not_ready" in diagnostics["degraded_reasons"]
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
    assert "strategy_runtime_not_ready" in health.readiness_reasons
    assert "execution_runtime_not_ready" in health.readiness_reasons
    assert "oms_runtime_not_ready" in health.readiness_reasons
    assert "opportunity_runtime_not_ready" in health.readiness_reasons
    assert "orchestration_runtime_not_ready" in health.readiness_reasons
    assert "position_expansion_runtime_not_ready" in health.readiness_reasons
    assert "portfolio_governor_runtime_not_ready" in health.readiness_reasons
    assert "protection_runtime_not_ready" in health.readiness_reasons
    assert "manager_runtime_not_ready" in health.readiness_reasons
    assert "validation_runtime_not_ready" in health.readiness_reasons
    assert "paper_runtime_not_ready" in health.readiness_reasons
    assert SystemEventType.SYSTEM_BOOT in lifecycle_events
    assert SystemEventType.SYSTEM_READY in lifecycle_events

    await runtime.shutdown(force=True)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_signal_runtime_is_explicitly_wired_to_existing_truth_path() -> None:  # noqa: PLR0915
    """Phase 8 runtime должен получать existing truths через composition-root wiring."""
    runtime = await _build_test_runtime()

    captured_signal_events: list[Event] = []
    captured_strategy_events: list[Event] = []
    runtime.event_bus.on(
        SignalEventType.SIGNAL_SNAPSHOT_UPDATED.value,
        captured_signal_events.append,
    )
    runtime.event_bus.on(
        StrategyEventType.STRATEGY_CANDIDATE_UPDATED.value,
        captured_strategy_events.append,
    )

    await _startup_with_orderbook(runtime)
    await _publish_completed_bars(runtime, count=28)

    diagnostics = runtime.get_runtime_diagnostics()
    signal_diagnostics = diagnostics["signal_runtime"]
    strategy_diagnostics = diagnostics["strategy_runtime"]
    execution_diagnostics = diagnostics["execution_runtime"]
    opportunity_diagnostics = diagnostics["opportunity_runtime"]
    orchestration_diagnostics = diagnostics["orchestration_runtime"]
    position_expansion_diagnostics = diagnostics["position_expansion_runtime"]
    portfolio_governor_diagnostics = diagnostics["portfolio_governor_runtime"]
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
    assert runtime.strategy_runtime.is_started is True
    assert signal_diagnostics["started"] is True
    assert signal_diagnostics["ready"] is True
    assert signal_diagnostics["tracked_signal_keys"] == 1
    assert signal_diagnostics["last_context_at"] is not None
    assert signal_diagnostics["last_event_type"] == SignalEventType.SIGNAL_SNAPSHOT_UPDATED.value
    assert strategy_diagnostics["started"] is True
    assert strategy_diagnostics["ready"] is False
    assert strategy_diagnostics["tracked_candidate_keys"] == 1
    assert (
        strategy_diagnostics["last_event_type"]
        == StrategyEventType.STRATEGY_CANDIDATE_UPDATED.value
    )
    assert execution_diagnostics["started"] is True
    assert execution_diagnostics["ready"] is False
    assert execution_diagnostics["tracked_intent_keys"] == 1
    assert (
        execution_diagnostics["last_event_type"]
        == ExecutionEventType.EXECUTION_INTENT_UPDATED.value
    )
    assert opportunity_diagnostics["started"] is True
    assert opportunity_diagnostics["ready"] is False
    assert opportunity_diagnostics["tracked_selection_keys"] == 1
    assert (
        opportunity_diagnostics["last_event_type"]
        == OpportunityEventType.OPPORTUNITY_CANDIDATE_UPDATED.value
    )
    assert orchestration_diagnostics["started"] is True
    assert orchestration_diagnostics["ready"] is False
    assert orchestration_diagnostics["tracked_decision_keys"] == 1
    assert (
        orchestration_diagnostics["last_event_type"]
        == OrchestrationEventType.ORCHESTRATION_CANDIDATE_UPDATED.value
    )
    assert position_expansion_diagnostics["started"] is True
    assert position_expansion_diagnostics["ready"] is False
    assert position_expansion_diagnostics["tracked_expansion_keys"] == 1
    assert (
        position_expansion_diagnostics["last_event_type"]
        == PositionExpansionEventType.POSITION_EXPANSION_CANDIDATE_UPDATED.value
    )
    assert portfolio_governor_diagnostics["started"] is True
    assert portfolio_governor_diagnostics["ready"] is False
    assert portfolio_governor_diagnostics["tracked_governor_keys"] == 1
    assert (
        portfolio_governor_diagnostics["last_event_type"]
        == PortfolioGovernorEventType.PORTFOLIO_GOVERNOR_CANDIDATE_UPDATED.value
    )
    assert context is not None
    assert context.derived_inputs is not None
    assert context.derya is not None
    assert signal is not None
    assert signal.status.value == "suppressed"
    assert captured_signal_events
    assert captured_strategy_events
    assert captured_strategy_events[-1].payload["status"] == "candidate"
    assert captured_strategy_events[-1].payload["validity_status"] == "warming"
    assert captured_strategy_events[-1].payload["symbol"] == "BTC/USDT"

    await runtime.shutdown(force=True)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_signal_runtime_publishes_signal_emitted_through_integrated_runtime_path() -> None:  # noqa: PLR0915
    """Integrated signal wiring должен публиковать SIGNAL_EMITTED из existing truths."""
    runtime = await _build_test_runtime()

    captured_signal_events: list[Event] = []
    captured_strategy_events: list[Event] = []
    captured_execution_events: list[Event] = []
    captured_oms_events: list[Event] = []
    captured_opportunity_events: list[Event] = []
    captured_orchestration_events: list[Event] = []
    captured_position_expansion_events: list[Event] = []
    captured_portfolio_governor_events: list[Event] = []
    captured_protection_events: list[Event] = []
    captured_manager_events: list[Event] = []
    captured_validation_events: list[Event] = []
    captured_paper_events: list[Event] = []
    _register_event_captures(
        runtime,
        (SignalEventType.SIGNAL_EMITTED.value, captured_signal_events.append),
        (StrategyEventType.STRATEGY_ACTIONABLE.value, captured_strategy_events.append),
        (ExecutionEventType.EXECUTION_REQUESTED.value, captured_execution_events.append),
        (OmsEventType.OMS_ORDER_REGISTERED.value, captured_oms_events.append),
        (OpportunityEventType.OPPORTUNITY_SELECTED.value, captured_opportunity_events.append),
        (
            OrchestrationEventType.ORCHESTRATION_DECIDED.value,
            captured_orchestration_events.append,
        ),
        (
            PositionExpansionEventType.POSITION_EXPANSION_APPROVED.value,
            captured_position_expansion_events.append,
        ),
        (
            PortfolioGovernorEventType.PORTFOLIO_GOVERNOR_APPROVED.value,
            captured_portfolio_governor_events.append,
        ),
        (ProtectionEventType.PROTECTION_FROZEN.value, captured_protection_events.append),
        (ManagerEventType.MANAGER_WORKFLOW_ABSTAINED.value, captured_manager_events.append),
        (
            ValidationEventType.VALIDATION_CANDIDATE_UPDATED.value,
            captured_validation_events.append,
        ),
        (PaperEventType.PAPER_CANDIDATE_UPDATED.value, captured_paper_events.append),
    )

    await _startup_with_orderbook(runtime)
    _install_ready_upstream_truths(runtime)
    await _publish_completed_bars(runtime, count=1)

    diagnostics = runtime.get_runtime_diagnostics()
    signal_diagnostics = diagnostics["signal_runtime"]
    strategy_diagnostics = diagnostics["strategy_runtime"]
    execution_diagnostics = diagnostics["execution_runtime"]
    oms_diagnostics = diagnostics["oms_runtime"]
    validation_diagnostics = diagnostics["validation_runtime"]
    manager_diagnostics = diagnostics["manager_runtime"]
    paper_diagnostics = diagnostics["paper_runtime"]
    opportunity_diagnostics = diagnostics["opportunity_runtime"]
    orchestration_diagnostics = diagnostics["orchestration_runtime"]
    position_expansion_diagnostics = diagnostics["position_expansion_runtime"]
    portfolio_governor_diagnostics = diagnostics["portfolio_governor_runtime"]
    protection_diagnostics = diagnostics["protection_runtime"]
    signal = runtime.signal_runtime.get_signal(
        exchange="bybit",
        symbol="BTC/USDT",
        timeframe=MarketDataTimeframe.M1,
    )
    candidate = runtime.strategy_runtime.get_candidate(
        exchange="bybit",
        symbol="BTC/USDT",
        timeframe=MarketDataTimeframe.M1,
    )
    intent = runtime.execution_runtime.get_intent(
        exchange="bybit",
        symbol="BTC/USDT",
        timeframe=MarketDataTimeframe.M1,
    )
    oms_order = (
        runtime.oms_runtime.get_order_by_intent(intent_id=intent.intent_id) if intent else None
    )
    expansion_candidate = runtime.position_expansion_runtime.get_candidate(
        exchange="bybit",
        symbol="BTC/USDT",
        timeframe=MarketDataTimeframe.M1,
    )
    governor_candidate = runtime.portfolio_governor_runtime.get_candidate(
        exchange="bybit",
        symbol="BTC/USDT",
        timeframe=MarketDataTimeframe.M1,
    )
    protection_candidate = runtime.protection_runtime.get_candidate(
        exchange="bybit",
        symbol="BTC/USDT",
        timeframe=MarketDataTimeframe.M1,
    )
    manager_candidate = runtime.manager_runtime.get_candidate(
        exchange="bybit",
        symbol="BTC/USDT",
        timeframe=MarketDataTimeframe.M1,
    )
    validation_candidate = runtime.validation_runtime.get_candidate(
        exchange="bybit",
        symbol="BTC/USDT",
        timeframe=MarketDataTimeframe.M1,
    )
    paper_candidate = runtime.paper_runtime.get_candidate((
        "BTC/USDT",
        "bybit",
        MarketDataTimeframe.M1,
    ))

    assert signal is not None
    assert signal.status.value == "active"
    assert signal.direction is not None
    assert signal_diagnostics["ready"] is True
    assert signal_diagnostics["active_signal_keys"] == 1
    assert signal_diagnostics["last_event_type"] == SignalEventType.SIGNAL_EMITTED.value
    assert strategy_diagnostics["ready"] is True
    assert strategy_diagnostics["actionable_candidate_keys"] == 1
    assert strategy_diagnostics["last_event_type"] == StrategyEventType.STRATEGY_ACTIONABLE.value
    assert execution_diagnostics["ready"] is True
    assert execution_diagnostics["executable_intent_keys"] == 1
    assert execution_diagnostics["last_event_type"] == ExecutionEventType.EXECUTION_REQUESTED.value
    assert oms_diagnostics["ready"] is True
    assert oms_diagnostics["tracked_active_orders"] == 1
    assert oms_diagnostics["tracked_historical_orders"] == 0
    assert oms_diagnostics["last_event_type"] == OmsEventType.OMS_ORDER_REGISTERED.value
    assert opportunity_diagnostics["ready"] is True
    assert opportunity_diagnostics["selected_keys"] == 1
    assert (
        opportunity_diagnostics["last_event_type"]
        == OpportunityEventType.OPPORTUNITY_SELECTED.value
    )
    assert orchestration_diagnostics["ready"] is True
    assert orchestration_diagnostics["forwarded_keys"] == 1
    assert (
        orchestration_diagnostics["last_event_type"]
        == OrchestrationEventType.ORCHESTRATION_DECIDED.value
    )
    assert position_expansion_diagnostics["ready"] is True
    assert position_expansion_diagnostics["expandable_keys"] == 1
    assert (
        position_expansion_diagnostics["last_event_type"]
        == PositionExpansionEventType.POSITION_EXPANSION_APPROVED.value
    )
    assert portfolio_governor_diagnostics["ready"] is True
    assert portfolio_governor_diagnostics["approved_keys"] == 1
    assert (
        portfolio_governor_diagnostics["last_event_type"]
        == PortfolioGovernorEventType.PORTFOLIO_GOVERNOR_APPROVED.value
    )
    assert protection_diagnostics["ready"] is True
    assert protection_diagnostics["frozen_keys"] == 1
    assert protection_diagnostics["last_event_type"] == ProtectionEventType.PROTECTION_FROZEN.value
    assert manager_diagnostics["ready"] is True
    assert manager_diagnostics["tracked_active_workflows"] == 1
    assert (
        manager_diagnostics["last_event_type"] == ManagerEventType.MANAGER_WORKFLOW_ABSTAINED.value
    )
    assert validation_diagnostics["started"] is True
    assert validation_diagnostics["ready"] is False
    assert validation_diagnostics["tracked_contexts"] == 1
    assert validation_diagnostics["tracked_active_reviews"] == 1
    assert (
        validation_diagnostics["last_event_type"]
        == ValidationEventType.VALIDATION_CANDIDATE_UPDATED.value
    )
    assert validation_diagnostics["readiness_reasons"] == ["manager_not_coordinated"]
    assert paper_diagnostics["started"] is True
    assert paper_diagnostics["ready"] is False
    assert paper_diagnostics["tracked_contexts"] == 1
    assert paper_diagnostics["tracked_active_rehearsals"] == 1
    assert paper_diagnostics["tracked_historical_rehearsals"] == 0
    assert paper_diagnostics["last_event_type"] == PaperEventType.PAPER_CANDIDATE_UPDATED.value
    assert paper_diagnostics["readiness_reasons"] == ["manager_not_coordinated"]
    assert candidate is not None
    assert candidate.status.value == "actionable"
    assert intent is not None
    assert intent.status.value == "executable"
    assert oms_order is not None
    assert oms_order.lifecycle_status.value == "registered"
    assert expansion_candidate is not None
    assert expansion_candidate.status.value == "expandable"
    assert governor_candidate is not None
    assert governor_candidate.status.value == "approved"
    assert protection_candidate is not None
    assert protection_candidate.status.value == "frozen"
    assert manager_candidate is not None
    assert manager_candidate.status.value == "abstained"
    assert validation_candidate is not None
    assert validation_candidate.status.value == "candidate"
    assert validation_candidate.decision.value == "abstain"
    assert paper_candidate is not None
    assert paper_candidate.status.value == "candidate"
    assert paper_candidate.decision.value == "abstain"
    assert captured_signal_events
    assert captured_signal_events[-1].payload["status"] == "active"
    assert captured_signal_events[-1].payload["direction"] == "BUY"
    assert captured_signal_events[-1].payload["symbol"] == "BTC/USDT"
    assert captured_strategy_events
    assert captured_strategy_events[-1].payload["status"] == "actionable"
    assert captured_validation_events
    assert captured_validation_events[-1].payload["status"] == "candidate"
    assert captured_validation_events[-1].payload["decision"] == "abstain"
    assert captured_paper_events
    assert captured_paper_events[-1].payload["status"] == "candidate"
    assert captured_paper_events[-1].payload["decision"] == "abstain"
    assert captured_strategy_events[-1].payload["direction"] == "LONG"
    assert captured_strategy_events[-1].payload["strategy_name"] == "phase9_foundation_strategy"
    assert captured_execution_events
    assert captured_execution_events[-1].payload["status"] == "executable"
    assert captured_execution_events[-1].payload["direction"] == "BUY"
    assert captured_execution_events[-1].payload["execution_name"] == "phase10_foundation_execution"
    assert captured_oms_events
    assert captured_oms_events[-1].source == "OMS_RUNTIME"
    assert captured_oms_events[-1].payload["lifecycle_status"] == "registered"
    assert captured_oms_events[-1].payload["query_scope"] == "active"
    assert captured_opportunity_events
    assert captured_opportunity_events[-1].payload["status"] == "selected"
    assert captured_opportunity_events[-1].payload["direction"] == "LONG"
    assert (
        captured_opportunity_events[-1].payload["selection_name"] == "phase11_foundation_selection"
    )
    assert captured_orchestration_events
    assert captured_orchestration_events[-1].payload["status"] == "orchestrated"
    assert captured_orchestration_events[-1].payload["decision"] == "forward"
    assert (
        captured_orchestration_events[-1].payload["orchestration_name"]
        == "phase12_meta_orchestration"
    )
    assert captured_position_expansion_events
    assert captured_position_expansion_events[-1].payload["status"] == "expandable"
    assert captured_position_expansion_events[-1].payload["decision"] == "add"
    assert (
        captured_position_expansion_events[-1].payload["expansion_name"]
        == "phase13_position_expansion"
    )
    assert captured_portfolio_governor_events
    assert captured_portfolio_governor_events[-1].payload["status"] == "approved"
    assert captured_portfolio_governor_events[-1].payload["decision"] == "approve"
    assert (
        captured_portfolio_governor_events[-1].payload["governor_name"]
        == "phase14_portfolio_governor"
    )
    assert captured_protection_events
    assert captured_protection_events[-1].payload["status"] == "frozen"
    assert captured_protection_events[-1].payload["decision"] == "freeze"
    assert captured_manager_events
    assert captured_manager_events[-1].payload["status"] == "abstained"
    assert captured_manager_events[-1].payload["decision"] == "abstain"

    await runtime.shutdown(force=True)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_execution_runtime_publishes_intent_updated_for_non_executable_strategy_candidate(  # noqa: PLR0915
) -> None:
    """Integrated execution wiring не должен маскировать non-executable candidate как request."""
    runtime = await _build_test_runtime()

    captured_execution_updates: list[Event] = []
    captured_oms_updates: list[Event] = []
    captured_opportunity_updates: list[Event] = []
    captured_orchestration_updates: list[Event] = []
    _register_event_captures(
        runtime,
        (ExecutionEventType.EXECUTION_INTENT_UPDATED.value, captured_execution_updates.append),
        (OmsEventType.OMS_ORDER_REGISTERED.value, captured_oms_updates.append),
        (
            OpportunityEventType.OPPORTUNITY_CANDIDATE_UPDATED.value,
            captured_opportunity_updates.append,
        ),
        (
            OrchestrationEventType.ORCHESTRATION_CANDIDATE_UPDATED.value,
            captured_orchestration_updates.append,
        ),
    )

    await _startup_with_orderbook(runtime)
    _install_ready_upstream_truths(runtime)
    runtime.execution_runtime._evaluate_minimal_contour = lambda **_kwargs: None  # type: ignore[method-assign]
    await _publish_completed_bars(runtime, count=1)

    diagnostics = runtime.get_runtime_diagnostics()
    strategy_diagnostics = diagnostics["strategy_runtime"]
    execution_diagnostics = diagnostics["execution_runtime"]
    oms_diagnostics = diagnostics["oms_runtime"]
    manager_diagnostics = diagnostics["manager_runtime"]
    opportunity_diagnostics = diagnostics["opportunity_runtime"]
    orchestration_diagnostics = diagnostics["orchestration_runtime"]
    candidate = runtime.strategy_runtime.get_candidate(
        exchange="bybit",
        symbol="BTC/USDT",
        timeframe=MarketDataTimeframe.M1,
    )
    intent = runtime.execution_runtime.get_intent(
        exchange="bybit",
        symbol="BTC/USDT",
        timeframe=MarketDataTimeframe.M1,
    )

    assert candidate is not None
    assert candidate.status.value == "actionable"
    assert strategy_diagnostics["actionable_candidate_keys"] == 1
    assert execution_diagnostics["ready"] is True
    assert execution_diagnostics["executable_intent_keys"] == 0
    assert execution_diagnostics["tracked_intent_keys"] == 1
    assert (
        execution_diagnostics["last_event_type"]
        == ExecutionEventType.EXECUTION_INTENT_UPDATED.value
    )
    assert oms_diagnostics["ready"] is False
    assert oms_diagnostics["tracked_contexts"] == 1
    assert oms_diagnostics["tracked_active_orders"] == 0
    assert oms_diagnostics["tracked_historical_orders"] == 0
    assert oms_diagnostics["readiness_reasons"] == ["executable_execution_intent"]
    assert opportunity_diagnostics["ready"] is False
    assert opportunity_diagnostics["selected_keys"] == 0
    assert opportunity_diagnostics["tracked_selection_keys"] == 1
    assert (
        opportunity_diagnostics["last_event_type"]
        == OpportunityEventType.OPPORTUNITY_CANDIDATE_UPDATED.value
    )
    assert orchestration_diagnostics["ready"] is False
    assert orchestration_diagnostics["tracked_decision_keys"] == 1
    assert orchestration_diagnostics["forwarded_keys"] == 0
    assert (
        orchestration_diagnostics["last_event_type"]
        == OrchestrationEventType.ORCHESTRATION_CANDIDATE_UPDATED.value
    )
    assert manager_diagnostics["ready"] is False
    assert manager_diagnostics["tracked_contexts"] == 1
    assert manager_diagnostics["tracked_active_workflows"] == 1
    assert manager_diagnostics["readiness_reasons"] == ["opportunity_not_selected"]
    assert intent is not None
    assert intent.status.value == "suppressed"
    assert intent.direction is None
    assert captured_execution_updates
    assert captured_execution_updates[-1].payload["status"] == "suppressed"
    assert captured_execution_updates[-1].payload["direction"] is None
    assert (
        captured_execution_updates[-1].payload["execution_name"] == "phase10_foundation_execution"
    )
    assert captured_oms_updates == []
    assert captured_opportunity_updates
    assert captured_opportunity_updates[-1].payload["status"] == "candidate"
    assert captured_opportunity_updates[-1].payload["direction"] is None
    assert (
        captured_opportunity_updates[-1].payload["selection_name"] == "phase11_foundation_selection"
    )
    assert captured_orchestration_updates
    assert captured_orchestration_updates[-1].payload["status"] == "candidate"
    assert captured_orchestration_updates[-1].payload["decision"] == "abstain"
    assert (
        captured_orchestration_updates[-1].payload["orchestration_name"]
        == "phase12_meta_orchestration"
    )

    await runtime.shutdown(force=True)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_signal_runtime_publishes_signal_invalidated_when_existing_truth_disappears() -> None:  # noqa: PLR0915
    """Integrated signal wiring не должен маскировать invalidation как обычный update."""
    runtime = await _build_test_runtime()

    captured_invalidations: list[Event] = []
    captured_strategy_invalidations: list[Event] = []
    captured_execution_invalidations: list[Event] = []
    captured_oms_events: list[Event] = []
    captured_opportunity_invalidations: list[Event] = []
    captured_orchestration_invalidations: list[Event] = []
    captured_position_expansion_invalidations: list[Event] = []
    captured_portfolio_governor_invalidations: list[Event] = []
    captured_manager_invalidations: list[Event] = []
    captured_validation_invalidations: list[Event] = []
    captured_paper_invalidations: list[Event] = []
    _register_event_captures(
        runtime,
        (SignalEventType.SIGNAL_INVALIDATED.value, captured_invalidations.append),
        (
            StrategyEventType.STRATEGY_INVALIDATED.value,
            captured_strategy_invalidations.append,
        ),
        (
            ExecutionEventType.EXECUTION_INVALIDATED.value,
            captured_execution_invalidations.append,
        ),
        (OmsEventType.OMS_ORDER_EXPIRED.value, captured_oms_events.append),
        (
            OpportunityEventType.OPPORTUNITY_INVALIDATED.value,
            captured_opportunity_invalidations.append,
        ),
        (
            OrchestrationEventType.ORCHESTRATION_INVALIDATED.value,
            captured_orchestration_invalidations.append,
        ),
        (
            PositionExpansionEventType.POSITION_EXPANSION_INVALIDATED.value,
            captured_position_expansion_invalidations.append,
        ),
        (
            PortfolioGovernorEventType.PORTFOLIO_GOVERNOR_INVALIDATED.value,
            captured_portfolio_governor_invalidations.append,
        ),
        (
            ManagerEventType.MANAGER_WORKFLOW_INVALIDATED.value,
            captured_manager_invalidations.append,
        ),
        (
            ValidationEventType.VALIDATION_WORKFLOW_INVALIDATED.value,
            captured_validation_invalidations.append,
        ),
        (PaperEventType.PAPER_REHEARSAL_INVALIDATED.value, captured_paper_invalidations.append),
    )

    await _startup_with_orderbook(runtime)
    _install_ready_upstream_truths(runtime)
    await _publish_completed_bars(runtime, count=1)

    active = runtime.signal_runtime.get_signal(
        exchange="bybit",
        symbol="BTC/USDT",
        timeframe=MarketDataTimeframe.M1,
    )
    assert active is not None
    assert active.status.value == "active"

    runtime.shared_analysis_runtime.get_risk_derived_inputs = lambda **_kwargs: None  # type: ignore[method-assign]
    await _publish_completed_bars(runtime, count=1, start_index=1)

    diagnostics = runtime.get_runtime_diagnostics()
    signal_diagnostics = diagnostics["signal_runtime"]
    strategy_diagnostics = diagnostics["strategy_runtime"]
    execution_diagnostics = diagnostics["execution_runtime"]
    oms_diagnostics = diagnostics["oms_runtime"]
    validation_diagnostics = diagnostics["validation_runtime"]
    paper_diagnostics = diagnostics["paper_runtime"]
    opportunity_diagnostics = diagnostics["opportunity_runtime"]
    orchestration_diagnostics = diagnostics["orchestration_runtime"]
    position_expansion_diagnostics = diagnostics["position_expansion_runtime"]
    portfolio_governor_diagnostics = diagnostics["portfolio_governor_runtime"]
    protection_diagnostics = diagnostics["protection_runtime"]
    manager_diagnostics = diagnostics["manager_runtime"]
    invalidated = runtime.signal_runtime.get_signal(
        exchange="bybit",
        symbol="BTC/USDT",
        timeframe=MarketDataTimeframe.M1,
    )
    candidate = runtime.strategy_runtime.get_candidate(
        exchange="bybit",
        symbol="BTC/USDT",
        timeframe=MarketDataTimeframe.M1,
    )
    intent = runtime.execution_runtime.get_intent(
        exchange="bybit",
        symbol="BTC/USDT",
        timeframe=MarketDataTimeframe.M1,
    )
    expansion_candidate = runtime.position_expansion_runtime.get_candidate(
        exchange="bybit",
        symbol="BTC/USDT",
        timeframe=MarketDataTimeframe.M1,
    )
    governor_candidate = runtime.portfolio_governor_runtime.get_candidate(
        exchange="bybit",
        symbol="BTC/USDT",
        timeframe=MarketDataTimeframe.M1,
    )
    protection_candidate = runtime.protection_runtime.get_candidate(
        exchange="bybit",
        symbol="BTC/USDT",
        timeframe=MarketDataTimeframe.M1,
    )
    manager_candidate = runtime.manager_runtime.get_candidate(
        exchange="bybit",
        symbol="BTC/USDT",
        timeframe=MarketDataTimeframe.M1,
    )
    validation_candidate = runtime.validation_runtime.get_candidate(
        exchange="bybit",
        symbol="BTC/USDT",
        timeframe=MarketDataTimeframe.M1,
    )
    validation_historical = runtime.validation_runtime.get_historical_candidate((
        "BTC/USDT",
        "bybit",
        MarketDataTimeframe.M1,
    ))
    paper_candidate = runtime.paper_runtime.get_candidate((
        "BTC/USDT",
        "bybit",
        MarketDataTimeframe.M1,
    ))
    paper_historical = runtime.paper_runtime.get_historical_candidate((
        "BTC/USDT",
        "bybit",
        MarketDataTimeframe.M1,
    ))

    assert invalidated is not None
    assert invalidated.signal_id == active.signal_id
    assert invalidated.status.value == "invalidated"
    assert invalidated.validity.status.value == "warming"
    assert signal_diagnostics["ready"] is False
    assert signal_diagnostics["invalidated_signal_keys"] == 1
    assert signal_diagnostics["last_event_type"] == SignalEventType.SIGNAL_INVALIDATED.value
    assert strategy_diagnostics["ready"] is False
    assert strategy_diagnostics["invalidated_candidate_keys"] == 1
    assert strategy_diagnostics["last_event_type"] == StrategyEventType.STRATEGY_INVALIDATED.value
    assert execution_diagnostics["ready"] is False
    assert execution_diagnostics["invalidated_intent_keys"] == 1
    assert (
        execution_diagnostics["last_event_type"] == ExecutionEventType.EXECUTION_INVALIDATED.value
    )
    assert oms_diagnostics["ready"] is False
    assert oms_diagnostics["lifecycle_state"] == "degraded"
    assert oms_diagnostics["tracked_active_orders"] == 1
    assert oms_diagnostics["tracked_historical_orders"] == 0
    assert oms_diagnostics["last_failure_reason"] == "execution_intent_invalidated"
    assert opportunity_diagnostics["ready"] is True
    assert opportunity_diagnostics["invalidated_selection_keys"] == 1
    assert (
        opportunity_diagnostics["last_event_type"]
        == OpportunityEventType.OPPORTUNITY_INVALIDATED.value
    )
    assert orchestration_diagnostics["ready"] is True
    assert orchestration_diagnostics["invalidated_decision_keys"] == 1
    assert (
        orchestration_diagnostics["last_event_type"]
        == OrchestrationEventType.ORCHESTRATION_INVALIDATED.value
    )
    assert position_expansion_diagnostics["ready"] is True
    assert position_expansion_diagnostics["invalidated_expansion_keys"] == 1
    assert (
        position_expansion_diagnostics["last_event_type"]
        == PositionExpansionEventType.POSITION_EXPANSION_INVALIDATED.value
    )
    assert portfolio_governor_diagnostics["ready"] is True
    assert portfolio_governor_diagnostics["invalidated_governor_keys"] == 1
    assert (
        portfolio_governor_diagnostics["last_event_type"]
        == PortfolioGovernorEventType.PORTFOLIO_GOVERNOR_INVALIDATED.value
    )
    assert protection_diagnostics["ready"] is True
    assert protection_diagnostics["invalidated_protection_keys"] == 1
    assert (
        protection_diagnostics["last_event_type"]
        == ProtectionEventType.PROTECTION_INVALIDATED.value
    )
    assert manager_diagnostics["ready"] is False
    assert manager_diagnostics["tracked_historical_workflows"] == 1
    assert (
        manager_diagnostics["last_event_type"]
        == ManagerEventType.MANAGER_WORKFLOW_INVALIDATED.value
    )
    assert validation_diagnostics["ready"] is False
    assert validation_diagnostics["tracked_historical_reviews"] == 1
    assert (
        validation_diagnostics["last_event_type"]
        == ValidationEventType.VALIDATION_WORKFLOW_INVALIDATED.value
    )
    assert paper_diagnostics["ready"] is False
    assert paper_diagnostics["tracked_historical_rehearsals"] == 1
    assert paper_diagnostics["last_event_type"] == PaperEventType.PAPER_REHEARSAL_INVALIDATED.value
    assert candidate is not None
    assert candidate.status.value == "invalidated"
    assert intent is not None
    assert intent.status.value == "invalidated"
    assert expansion_candidate is not None
    assert expansion_candidate.status.value == "invalidated"
    assert governor_candidate is not None
    assert governor_candidate.status.value == "invalidated"
    assert protection_candidate is not None
    assert protection_candidate.status.value == "invalidated"
    assert manager_candidate is None
    assert validation_candidate is None
    assert validation_historical is not None
    assert validation_historical.status.value == "invalidated"
    assert paper_candidate is None
    assert paper_historical is not None
    assert paper_historical.status.value == "invalidated"
    assert captured_invalidations
    assert captured_invalidations[-1].payload["status"] == "invalidated"
    assert captured_invalidations[-1].payload["validity_status"] == "warming"
    assert captured_strategy_invalidations
    assert captured_strategy_invalidations[-1].payload["status"] == "invalidated"
    assert captured_strategy_invalidations[-1].payload["validity_status"] == "invalid"
    assert captured_strategy_invalidations[-1].payload["reason_code"] == "strategy_invalidated"
    assert captured_execution_invalidations
    assert captured_execution_invalidations[-1].payload["status"] == "invalidated"
    assert captured_execution_invalidations[-1].payload["validity_status"] == "invalid"
    assert captured_execution_invalidations[-1].payload["reason_code"] == "execution_invalidated"
    assert captured_oms_events == []
    assert captured_opportunity_invalidations
    assert captured_opportunity_invalidations[-1].payload["status"] == "invalidated"
    assert captured_opportunity_invalidations[-1].payload["validity_status"] == "invalid"
    assert (
        captured_opportunity_invalidations[-1].payload["reason_code"] == "opportunity_invalidated"
    )
    assert captured_orchestration_invalidations
    assert captured_orchestration_invalidations[-1].payload["status"] == "invalidated"
    assert captured_orchestration_invalidations[-1].payload["validity_status"] == "invalid"
    assert (
        captured_orchestration_invalidations[-1].payload["reason_code"]
        == "orchestration_invalidated"
    )
    assert captured_position_expansion_invalidations
    assert captured_position_expansion_invalidations[-1].payload["status"] == "invalidated"
    assert captured_position_expansion_invalidations[-1].payload["validity_status"] == "invalid"
    assert (
        captured_position_expansion_invalidations[-1].payload["reason_code"]
        == "expansion_invalidated"
    )
    assert captured_portfolio_governor_invalidations
    assert captured_portfolio_governor_invalidations[-1].payload["status"] == "invalidated"
    assert captured_portfolio_governor_invalidations[-1].payload["validity_status"] == "invalid"
    assert (
        captured_portfolio_governor_invalidations[-1].payload["reason_code"]
        == "governor_invalidated"
    )
    assert captured_manager_invalidations
    assert captured_manager_invalidations[-1].payload["status"] == "invalidated"
    assert captured_manager_invalidations[-1].payload["validity_status"] == "invalid"
    assert captured_validation_invalidations
    assert captured_validation_invalidations[-1].payload["status"] == "invalidated"
    assert captured_paper_invalidations
    assert captured_paper_invalidations[-1].payload["status"] == "invalidated"

    await runtime.shutdown(force=True)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_intelligence_runtime_is_explicitly_wired_to_bar_completed_path() -> None:
    """Phase 7 runtime должен получать BAR_COMPLETED через composition-root wiring."""
    runtime = await _build_test_runtime()
    captured_transitions: list[str] = []

    def capture_transition(event) -> None:
        captured_transitions.append(event.event_type)

    runtime.event_bus.on(IntelligenceEventType.DERYA_REGIME_CHANGED.value, capture_transition)

    await runtime.startup()
    await _publish_completed_bars(runtime, count=4)

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
    runtime = await _build_test_runtime()

    await runtime.startup()

    def raise_ingest_failure(_payload: BarCompletedPayload) -> None:
        raise RuntimeError("derya_ingest_failure")

    runtime.intelligence_runtime.ingest_bar_completed_payload = raise_ingest_failure  # type: ignore[method-assign]

    await _publish_completed_bars(runtime, count=1)

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
async def test_signal_runtime_missing_analysis_and_intelligence_is_visible_in_runtime_truth(  # noqa: PLR0915
) -> None:
    """Signal runtime не должен маскировать incomplete context как ready."""
    runtime = await _build_test_runtime()

    await runtime.startup()

    await _publish_completed_bars(runtime, count=1)

    diagnostics = runtime.get_runtime_diagnostics()
    signal_diagnostics = diagnostics["signal_runtime"]
    strategy_diagnostics = diagnostics["strategy_runtime"]
    execution_diagnostics = diagnostics["execution_runtime"]
    oms_diagnostics = diagnostics["oms_runtime"]
    opportunity_diagnostics = diagnostics["opportunity_runtime"]
    orchestration_diagnostics = diagnostics["orchestration_runtime"]
    position_expansion_diagnostics = diagnostics["position_expansion_runtime"]
    portfolio_governor_diagnostics = diagnostics["portfolio_governor_runtime"]
    protection_diagnostics = diagnostics["protection_runtime"]
    manager_diagnostics = diagnostics["manager_runtime"]
    validation_diagnostics = diagnostics["validation_runtime"]
    paper_diagnostics = diagnostics["paper_runtime"]
    health = await runtime.health_checker.check_system()

    assert signal_diagnostics["started"] is True
    assert signal_diagnostics["ready"] is False
    assert signal_diagnostics["lifecycle_state"] == "warming"
    assert signal_diagnostics["tracked_signal_keys"] == 1
    assert signal_diagnostics["readiness_reasons"] == ["signal_context_warming"]
    assert "signal_runtime_not_ready" in health.readiness_reasons
    assert strategy_diagnostics["started"] is True
    assert strategy_diagnostics["ready"] is False
    assert strategy_diagnostics["tracked_candidate_keys"] == 1
    assert strategy_diagnostics["readiness_reasons"] == ["strategy_context_warming"]
    assert "strategy_runtime_not_ready" in health.readiness_reasons
    assert execution_diagnostics["started"] is True
    assert execution_diagnostics["ready"] is False
    assert execution_diagnostics["tracked_intent_keys"] == 1
    assert execution_diagnostics["readiness_reasons"] == ["execution_context_warming"]
    assert "execution_runtime_not_ready" in health.readiness_reasons
    assert oms_diagnostics["started"] is True
    assert oms_diagnostics["ready"] is False
    assert oms_diagnostics["tracked_contexts"] == 1
    assert oms_diagnostics["tracked_active_orders"] == 0
    assert oms_diagnostics["tracked_historical_orders"] == 0
    assert oms_diagnostics["readiness_reasons"] == ["executable_execution_intent"]
    assert "oms_runtime_not_ready" in health.readiness_reasons
    assert opportunity_diagnostics["started"] is True
    assert opportunity_diagnostics["ready"] is False
    assert opportunity_diagnostics["tracked_selection_keys"] == 1
    assert opportunity_diagnostics["readiness_reasons"] == ["ready_intent"]
    assert "opportunity_runtime_not_ready" in health.readiness_reasons
    assert orchestration_diagnostics["started"] is True
    assert orchestration_diagnostics["ready"] is False
    assert orchestration_diagnostics["tracked_decision_keys"] == 1
    assert orchestration_diagnostics["readiness_reasons"] == ["ready_opportunity"]
    assert "orchestration_runtime_not_ready" in health.readiness_reasons
    assert position_expansion_diagnostics["started"] is True
    assert position_expansion_diagnostics["ready"] is False
    assert position_expansion_diagnostics["tracked_expansion_keys"] == 1
    assert position_expansion_diagnostics["readiness_reasons"] == ["forwardable_decision"]
    assert "position_expansion_runtime_not_ready" in health.readiness_reasons
    assert portfolio_governor_diagnostics["started"] is True
    assert portfolio_governor_diagnostics["ready"] is False
    assert portfolio_governor_diagnostics["tracked_governor_keys"] == 1
    assert portfolio_governor_diagnostics["readiness_reasons"] == ["approvable_expansion"]
    assert "portfolio_governor_runtime_not_ready" in health.readiness_reasons
    assert protection_diagnostics["started"] is True
    assert protection_diagnostics["ready"] is False
    assert protection_diagnostics["tracked_protection_keys"] == 1
    assert protection_diagnostics["readiness_reasons"] == ["approved_governor"]
    assert "protection_runtime_not_ready" in health.readiness_reasons
    assert manager_diagnostics["started"] is True
    assert manager_diagnostics["ready"] is False
    assert manager_diagnostics["tracked_contexts"] == 1
    assert manager_diagnostics["tracked_active_workflows"] == 1
    assert manager_diagnostics["tracked_historical_workflows"] == 0
    assert manager_diagnostics["readiness_reasons"] == ["opportunity_not_selected"]
    assert "manager_runtime_not_ready" in health.readiness_reasons
    assert validation_diagnostics["started"] is True
    assert validation_diagnostics["ready"] is False
    assert validation_diagnostics["tracked_contexts"] == 1
    assert validation_diagnostics["tracked_active_reviews"] == 1
    assert validation_diagnostics["tracked_historical_reviews"] == 0
    assert validation_diagnostics["readiness_reasons"] == ["manager_not_coordinated"]
    assert "validation_runtime_not_ready" in health.readiness_reasons
    assert paper_diagnostics["started"] is True
    assert paper_diagnostics["ready"] is False
    assert paper_diagnostics["tracked_contexts"] == 1
    assert paper_diagnostics["tracked_active_rehearsals"] == 1
    assert paper_diagnostics["tracked_historical_rehearsals"] == 0
    assert paper_diagnostics["readiness_reasons"] == ["manager_not_coordinated"]
    assert "paper_runtime_not_ready" in health.readiness_reasons

    await runtime.shutdown(force=True)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_intelligence_runtime_shutdown_resets_nested_diagnostics() -> None:  # noqa: PLR0915
    """Shutdown должен оставлять operator-visible intelligence diagnostics в stopped state."""
    runtime = await _build_test_runtime()

    await runtime.startup()

    await _publish_completed_bars(runtime, count=4)

    await runtime.shutdown(force=True)

    diagnostics = runtime.get_runtime_diagnostics()
    intelligence_diagnostics = diagnostics["intelligence_runtime"]
    shared_analysis_diagnostics = diagnostics["shared_analysis_runtime"]
    signal_diagnostics = diagnostics["signal_runtime"]
    strategy_diagnostics = diagnostics["strategy_runtime"]
    execution_diagnostics = diagnostics["execution_runtime"]
    oms_diagnostics = diagnostics["oms_runtime"]
    opportunity_diagnostics = diagnostics["opportunity_runtime"]
    orchestration_diagnostics = diagnostics["orchestration_runtime"]
    position_expansion_diagnostics = diagnostics["position_expansion_runtime"]
    portfolio_governor_diagnostics = diagnostics["portfolio_governor_runtime"]
    protection_diagnostics = diagnostics["protection_runtime"]
    manager_diagnostics = diagnostics["manager_runtime"]
    validation_diagnostics = diagnostics["validation_runtime"]
    paper_diagnostics = diagnostics["paper_runtime"]

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
    assert strategy_diagnostics["started"] is False
    assert strategy_diagnostics["ready"] is False
    assert strategy_diagnostics["lifecycle_state"] == "stopped"
    assert strategy_diagnostics["tracked_candidate_keys"] == 0
    assert strategy_diagnostics["actionable_candidate_keys"] == 0
    assert strategy_diagnostics["invalidated_candidate_keys"] == 0
    assert strategy_diagnostics["expired_candidate_keys"] == 0
    assert strategy_diagnostics["last_signal_id"] is None
    assert strategy_diagnostics["last_candidate_id"] is None
    assert strategy_diagnostics["last_event_type"] is None
    assert strategy_diagnostics["last_failure_reason"] is None
    assert strategy_diagnostics["readiness_reasons"] == ["runtime_stopped"]
    assert strategy_diagnostics["degraded_reasons"] == []
    assert execution_diagnostics["started"] is False
    assert execution_diagnostics["ready"] is False
    assert execution_diagnostics["lifecycle_state"] == "stopped"
    assert execution_diagnostics["tracked_intent_keys"] == 0
    assert execution_diagnostics["executable_intent_keys"] == 0
    assert execution_diagnostics["invalidated_intent_keys"] == 0
    assert execution_diagnostics["expired_intent_keys"] == 0
    assert execution_diagnostics["last_candidate_id"] is None
    assert execution_diagnostics["last_intent_id"] is None
    assert execution_diagnostics["last_event_type"] is None
    assert execution_diagnostics["last_failure_reason"] is None
    assert execution_diagnostics["readiness_reasons"] == ["runtime_stopped"]
    assert execution_diagnostics["degraded_reasons"] == []
    assert oms_diagnostics["started"] is False
    assert oms_diagnostics["ready"] is False
    assert oms_diagnostics["lifecycle_state"] == "stopped"
    assert oms_diagnostics["tracked_contexts"] == 0
    assert oms_diagnostics["tracked_active_orders"] == 0
    assert oms_diagnostics["tracked_historical_orders"] == 0
    assert oms_diagnostics["last_intent_id"] is None
    assert oms_diagnostics["last_order_id"] is None
    assert oms_diagnostics["last_event_type"] is None
    assert oms_diagnostics["last_failure_reason"] is None
    assert oms_diagnostics["readiness_reasons"] == ["runtime_stopped"]
    assert oms_diagnostics["degraded_reasons"] == []
    assert opportunity_diagnostics["started"] is False
    assert opportunity_diagnostics["ready"] is False
    assert opportunity_diagnostics["lifecycle_state"] == "stopped"
    assert opportunity_diagnostics["tracked_selection_keys"] == 0
    assert opportunity_diagnostics["selected_keys"] == 0
    assert opportunity_diagnostics["invalidated_selection_keys"] == 0
    assert opportunity_diagnostics["expired_selection_keys"] == 0
    assert opportunity_diagnostics["last_intent_id"] is None
    assert opportunity_diagnostics["last_selection_id"] is None
    assert opportunity_diagnostics["last_event_type"] is None
    assert opportunity_diagnostics["last_failure_reason"] is None
    assert opportunity_diagnostics["readiness_reasons"] == ["runtime_stopped"]
    assert opportunity_diagnostics["degraded_reasons"] == []
    assert orchestration_diagnostics["started"] is False
    assert orchestration_diagnostics["ready"] is False
    assert orchestration_diagnostics["lifecycle_state"] == "stopped"
    assert orchestration_diagnostics["tracked_decision_keys"] == 0
    assert orchestration_diagnostics["forwarded_keys"] == 0
    assert orchestration_diagnostics["abstained_keys"] == 0
    assert orchestration_diagnostics["invalidated_decision_keys"] == 0
    assert orchestration_diagnostics["expired_decision_keys"] == 0
    assert orchestration_diagnostics["last_selection_id"] is None
    assert orchestration_diagnostics["last_decision_id"] is None
    assert orchestration_diagnostics["last_event_type"] is None
    assert orchestration_diagnostics["last_failure_reason"] is None
    assert orchestration_diagnostics["readiness_reasons"] == ["runtime_stopped"]
    assert orchestration_diagnostics["degraded_reasons"] == []
    assert position_expansion_diagnostics["started"] is False
    assert position_expansion_diagnostics["ready"] is False
    assert position_expansion_diagnostics["lifecycle_state"] == "stopped"
    assert position_expansion_diagnostics["tracked_expansion_keys"] == 0
    assert position_expansion_diagnostics["expandable_keys"] == 0
    assert position_expansion_diagnostics["abstained_keys"] == 0
    assert position_expansion_diagnostics["rejected_keys"] == 0
    assert position_expansion_diagnostics["invalidated_expansion_keys"] == 0
    assert position_expansion_diagnostics["expired_expansion_keys"] == 0
    assert position_expansion_diagnostics["last_decision_id"] is None
    assert position_expansion_diagnostics["last_expansion_id"] is None
    assert position_expansion_diagnostics["last_event_type"] is None
    assert position_expansion_diagnostics["last_failure_reason"] is None
    assert position_expansion_diagnostics["readiness_reasons"] == ["runtime_stopped"]
    assert position_expansion_diagnostics["degraded_reasons"] == []
    assert portfolio_governor_diagnostics["started"] is False
    assert portfolio_governor_diagnostics["ready"] is False
    assert portfolio_governor_diagnostics["lifecycle_state"] == "stopped"
    assert portfolio_governor_diagnostics["tracked_governor_keys"] == 0
    assert portfolio_governor_diagnostics["approved_keys"] == 0
    assert portfolio_governor_diagnostics["abstained_keys"] == 0
    assert portfolio_governor_diagnostics["rejected_keys"] == 0
    assert portfolio_governor_diagnostics["invalidated_governor_keys"] == 0
    assert portfolio_governor_diagnostics["expired_governor_keys"] == 0
    assert portfolio_governor_diagnostics["last_expansion_id"] is None
    assert portfolio_governor_diagnostics["last_governor_id"] is None
    assert portfolio_governor_diagnostics["last_event_type"] is None
    assert portfolio_governor_diagnostics["last_failure_reason"] is None
    assert portfolio_governor_diagnostics["readiness_reasons"] == ["runtime_stopped"]
    assert portfolio_governor_diagnostics["degraded_reasons"] == []
    assert protection_diagnostics["started"] is False
    assert protection_diagnostics["ready"] is False
    assert protection_diagnostics["lifecycle_state"] == "stopped"
    assert protection_diagnostics["tracked_protection_keys"] == 0
    assert protection_diagnostics["protected_keys"] == 0
    assert protection_diagnostics["halted_keys"] == 0
    assert protection_diagnostics["frozen_keys"] == 0
    assert protection_diagnostics["invalidated_protection_keys"] == 0
    assert protection_diagnostics["expired_protection_keys"] == 0
    assert protection_diagnostics["last_governor_id"] is None
    assert protection_diagnostics["last_protection_id"] is None
    assert protection_diagnostics["last_event_type"] is None
    assert protection_diagnostics["last_failure_reason"] is None
    assert protection_diagnostics["readiness_reasons"] == ["runtime_stopped"]
    assert protection_diagnostics["degraded_reasons"] == []
    assert manager_diagnostics["started"] is False
    assert manager_diagnostics["ready"] is False
    assert manager_diagnostics["lifecycle_state"] == "stopped"
    assert manager_diagnostics["tracked_contexts"] == 0
    assert manager_diagnostics["tracked_active_workflows"] == 0
    assert manager_diagnostics["tracked_historical_workflows"] == 0
    assert manager_diagnostics["last_workflow_id"] is None
    assert manager_diagnostics["last_event_type"] is None
    assert manager_diagnostics["last_failure_reason"] is None
    assert manager_diagnostics["readiness_reasons"] == ["runtime_stopped"]
    assert manager_diagnostics["degraded_reasons"] == []
    assert validation_diagnostics["started"] is False
    assert validation_diagnostics["ready"] is False
    assert validation_diagnostics["lifecycle_state"] == "stopped"
    assert validation_diagnostics["tracked_contexts"] == 0
    assert validation_diagnostics["tracked_active_reviews"] == 0
    assert validation_diagnostics["tracked_historical_reviews"] == 0
    assert validation_diagnostics["last_review_id"] is None
    assert validation_diagnostics["last_event_type"] is None
    assert validation_diagnostics["last_failure_reason"] is None
    assert validation_diagnostics["readiness_reasons"] == ["runtime_stopped"]
    assert validation_diagnostics["degraded_reasons"] == []
    assert paper_diagnostics["started"] is False
    assert paper_diagnostics["ready"] is False
    assert paper_diagnostics["lifecycle_state"] == "stopped"
    assert paper_diagnostics["tracked_contexts"] == 0
    assert paper_diagnostics["tracked_active_rehearsals"] == 0
    assert paper_diagnostics["tracked_historical_rehearsals"] == 0
    assert paper_diagnostics["last_rehearsal_id"] is None
    assert paper_diagnostics["last_event_type"] is None
    assert paper_diagnostics["last_failure_reason"] is None
    assert paper_diagnostics["readiness_reasons"] == ["runtime_stopped"]
    assert paper_diagnostics["degraded_reasons"] == []


@pytest.mark.asyncio
@pytest.mark.integration
async def test_shared_analysis_runtime_publishes_honest_risk_bar_completed_for_active_risk_path() -> (
    None
):
    """Production wiring должен публиковать RISK_BAR_COMPLETED только из полного набора truth sources."""
    runtime = await _build_test_runtime()

    captured_risk_bars: list[Event] = []
    trailing_events: list[Event] = []

    runtime.event_bus.on(SystemEventType.RISK_BAR_COMPLETED, captured_risk_bars.append)
    runtime.event_bus.on(RiskEngineEventType.TRAILING_STOP_MOVED, trailing_events.append)

    await _startup_with_orderbook(runtime)
    await runtime.event_bus.publish(_make_order_filled_event())
    await _publish_completed_bars(runtime, count=28, bar_factory=_make_trending_completed_bar)

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

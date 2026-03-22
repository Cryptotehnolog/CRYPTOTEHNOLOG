from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch

import pytest

from cryptotechnolog import __version__
from cryptotechnolog.bootstrap import (
    PHASE5_RISK_PATH,
    ProductionBootstrapError,
    ProductionBootstrapPolicy,
    build_production_runtime,
    start_production_runtime,
)
from cryptotechnolog.config.settings import Settings
from cryptotechnolog.core.event import Event, SystemEventType
from cryptotechnolog.core.health import HealthStatus, SystemHealth
import cryptotechnolog.core.listeners.base as listeners_base_module
from cryptotechnolog.core.listeners.base import ListenerRegistry
from cryptotechnolog.core.listeners.risk import RiskListener
from cryptotechnolog.core.system_controller import (
    ShutdownPhase,
    ShutdownResult,
    StartupPhase,
    StartupResult,
)
from cryptotechnolog.execution import (
    ExecutionDirection,
    ExecutionEventType,
    ExecutionFreshness,
    ExecutionOrderIntent,
    ExecutionReasonCode,
    ExecutionStatus,
    ExecutionValidity,
    ExecutionValidityStatus,
)
from cryptotechnolog.market_data import MarketDataTimeframe, OHLCVBarContract
from cryptotechnolog.market_data.events import (
    BarCompletedPayload,
    MarketDataEventType,
    build_market_data_event,
)
from cryptotechnolog.opportunity import (
    OpportunityDirection,
    OpportunityEventType,
    OpportunityFreshness,
    OpportunityReasonCode,
    OpportunitySelectionCandidate,
    OpportunitySource,
    OpportunityStatus,
    OpportunityValidity,
    OpportunityValidityStatus,
)
from cryptotechnolog.orchestration import (
    OrchestrationDecision,
    OrchestrationDecisionCandidate,
    OrchestrationEventType,
    OrchestrationFreshness,
    OrchestrationReasonCode,
    OrchestrationSource,
    OrchestrationStatus,
    OrchestrationValidity,
    OrchestrationValidityStatus,
)
from cryptotechnolog.portfolio_governor import (
    GovernorDecision,
    GovernorDirection,
    GovernorFreshness,
    GovernorReasonCode,
    GovernorSource,
    GovernorStatus,
    GovernorValidity,
    GovernorValidityStatus,
    PortfolioGovernorCandidate,
    PortfolioGovernorEventType,
)
from cryptotechnolog.position_expansion import (
    ExpansionDecision,
    ExpansionDirection,
    ExpansionFreshness,
    ExpansionReasonCode,
    ExpansionSource,
    ExpansionStatus,
    ExpansionValidity,
    ExpansionValidityStatus,
    PositionExpansionCandidate,
    PositionExpansionEventType,
)
from cryptotechnolog.signals import (
    SignalDirection,
    SignalEventType,
    SignalFreshness,
    SignalReasonCode,
    SignalSnapshot,
    SignalStatus,
    SignalValidity,
    SignalValidityStatus,
)
from cryptotechnolog.strategy import (
    StrategyActionCandidate,
    StrategyDirection,
    StrategyEventType,
    StrategyFreshness,
    StrategyReasonCode,
    StrategyStatus,
    StrategyValidity,
    StrategyValidityStatus,
)


def make_settings() -> Settings:
    """Собрать settings для bootstrap-тестов без внешних подключений."""
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


def make_completed_bar(index: int = 0) -> OHLCVBarContract:
    """Собрать completed bar для узких runtime wiring тестов."""
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


def make_active_signal_snapshot() -> SignalSnapshot:
    now = datetime(2026, 3, 20, 12, 1, tzinfo=UTC)
    return SignalSnapshot(
        signal_id=SignalSnapshot.candidate(
            contour_name="phase8_signal_contour",
            symbol="BTC/USDT",
            exchange="bybit",
            timeframe=MarketDataTimeframe.M1,
            freshness=SignalFreshness(
                generated_at=now,
                expires_at=now.replace(minute=6),
            ),
            validity=SignalValidity(
                status=SignalValidityStatus.VALID,
                observed_inputs=4,
                required_inputs=4,
            ),
            direction=SignalDirection.BUY,
            confidence=Decimal("0.8"),
            entry_price=Decimal("100"),
            stop_loss=Decimal("95"),
            take_profit=Decimal("110"),
            reason_code=SignalReasonCode.CONTEXT_READY,
        ).signal_id,
        contour_name="phase8_signal_contour",
        symbol="BTC/USDT",
        exchange="bybit",
        timeframe=MarketDataTimeframe.M1,
        freshness=SignalFreshness(
            generated_at=now,
            expires_at=now.replace(minute=6),
        ),
        validity=SignalValidity(
            status=SignalValidityStatus.VALID,
            observed_inputs=4,
            required_inputs=4,
        ),
        status=SignalStatus.ACTIVE,
        direction=SignalDirection.BUY,
        confidence=Decimal("0.8"),
        entry_price=Decimal("100"),
        stop_loss=Decimal("95"),
        take_profit=Decimal("110"),
        reason_code=SignalReasonCode.CONTEXT_READY,
    )


def make_actionable_strategy_candidate() -> StrategyActionCandidate:
    now = datetime(2026, 3, 20, 12, 1, tzinfo=UTC)
    signal_id = make_active_signal_snapshot().signal_id
    return StrategyActionCandidate(
        candidate_id=StrategyActionCandidate.candidate(
            contour_name="phase9_strategy_contour",
            strategy_name="phase9_foundation_strategy",
            symbol="BTC/USDT",
            exchange="bybit",
            timeframe=MarketDataTimeframe.M1,
            freshness=StrategyFreshness(
                generated_at=now,
                expires_at=now.replace(minute=6),
            ),
            validity=StrategyValidity(
                status=StrategyValidityStatus.VALID,
                observed_inputs=1,
                required_inputs=1,
            ),
            direction=StrategyDirection.LONG,
            originating_signal_id=signal_id,
            confidence=Decimal("0.8"),
            reason_code=StrategyReasonCode.CONTEXT_READY,
        ).candidate_id,
        contour_name="phase9_strategy_contour",
        strategy_name="phase9_foundation_strategy",
        symbol="BTC/USDT",
        exchange="bybit",
        timeframe=MarketDataTimeframe.M1,
        freshness=StrategyFreshness(
            generated_at=now,
            expires_at=now.replace(minute=6),
        ),
        validity=StrategyValidity(
            status=StrategyValidityStatus.VALID,
            observed_inputs=1,
            required_inputs=1,
        ),
        status=StrategyStatus.ACTIONABLE,
        direction=StrategyDirection.LONG,
        originating_signal_id=signal_id,
        confidence=Decimal("0.8"),
        reason_code=StrategyReasonCode.CONTEXT_READY,
    )


def make_executable_execution_intent() -> ExecutionOrderIntent:
    now = datetime(2026, 3, 20, 12, 1, tzinfo=UTC)
    candidate = make_actionable_strategy_candidate()
    return ExecutionOrderIntent(
        intent_id=ExecutionOrderIntent.candidate(
            contour_name="phase10_execution_contour",
            execution_name="phase10_foundation_execution",
            symbol="BTC/USDT",
            exchange="bybit",
            timeframe=MarketDataTimeframe.M1,
            freshness=ExecutionFreshness(
                generated_at=now,
                expires_at=now.replace(minute=6),
            ),
            validity=ExecutionValidity(
                status=ExecutionValidityStatus.VALID,
                observed_inputs=1,
                required_inputs=1,
            ),
            direction=ExecutionDirection.BUY,
            originating_candidate_id=candidate.candidate_id,
            confidence=Decimal("0.8"),
            reason_code=ExecutionReasonCode.CONTEXT_READY,
        ).intent_id,
        contour_name="phase10_execution_contour",
        execution_name="phase10_foundation_execution",
        symbol="BTC/USDT",
        exchange="bybit",
        timeframe=MarketDataTimeframe.M1,
        freshness=ExecutionFreshness(
            generated_at=now,
            expires_at=now.replace(minute=6),
        ),
        validity=ExecutionValidity(
            status=ExecutionValidityStatus.VALID,
            observed_inputs=1,
            required_inputs=1,
        ),
        status=ExecutionStatus.EXECUTABLE,
        direction=ExecutionDirection.BUY,
        originating_candidate_id=candidate.candidate_id,
        confidence=Decimal("0.8"),
        reason_code=ExecutionReasonCode.CONTEXT_READY,
    )


def make_selected_opportunity_candidate() -> OpportunitySelectionCandidate:
    now = datetime(2026, 3, 20, 12, 1, tzinfo=UTC)
    intent = make_executable_execution_intent()
    return OpportunitySelectionCandidate(
        selection_id=OpportunitySelectionCandidate.candidate(
            contour_name="phase11_opportunity_contour",
            selection_name="phase11_foundation_selection",
            symbol="BTC/USDT",
            exchange="bybit",
            timeframe=MarketDataTimeframe.M1,
            source=OpportunitySource.EXECUTION_INTENT,
            freshness=OpportunityFreshness(
                generated_at=now,
                expires_at=now.replace(minute=6),
            ),
            validity=OpportunityValidity(
                status=OpportunityValidityStatus.VALID,
                observed_inputs=1,
                required_inputs=1,
            ),
            direction=OpportunityDirection.LONG,
            originating_intent_id=intent.intent_id,
            confidence=Decimal("0.8"),
            priority_score=Decimal("0.8"),
            reason_code=OpportunityReasonCode.CONTEXT_READY,
        ).selection_id,
        contour_name="phase11_opportunity_contour",
        selection_name="phase11_foundation_selection",
        symbol="BTC/USDT",
        exchange="bybit",
        timeframe=MarketDataTimeframe.M1,
        source=OpportunitySource.EXECUTION_INTENT,
        freshness=OpportunityFreshness(
            generated_at=now,
            expires_at=now.replace(minute=6),
        ),
        validity=OpportunityValidity(
            status=OpportunityValidityStatus.VALID,
            observed_inputs=1,
            required_inputs=1,
        ),
        status=OpportunityStatus.SELECTED,
        direction=OpportunityDirection.LONG,
        originating_intent_id=intent.intent_id,
        confidence=Decimal("0.8"),
        priority_score=Decimal("0.8"),
        reason_code=OpportunityReasonCode.CONTEXT_READY,
    )


def make_forwarded_orchestration_decision() -> OrchestrationDecisionCandidate:
    now = datetime(2026, 3, 20, 12, 1, tzinfo=UTC)
    selection = make_selected_opportunity_candidate()
    return OrchestrationDecisionCandidate(
        decision_id=OrchestrationDecisionCandidate.candidate(
            contour_name="phase12_orchestration_contour",
            orchestration_name="phase12_meta_orchestration",
            symbol="BTC/USDT",
            exchange="bybit",
            timeframe=MarketDataTimeframe.M1,
            source=OrchestrationSource.OPPORTUNITY_SELECTION,
            freshness=OrchestrationFreshness(
                generated_at=now,
                expires_at=now.replace(minute=6),
            ),
            validity=OrchestrationValidity(
                status=OrchestrationValidityStatus.VALID,
                observed_inputs=1,
                required_inputs=1,
            ),
            decision=OrchestrationDecision.FORWARD,
            confidence=Decimal("0.8"),
            priority_score=Decimal("0.8"),
            reason_code=OrchestrationReasonCode.CONTEXT_READY,
            status=OrchestrationStatus.ORCHESTRATED,
            direction=OpportunityDirection.LONG,
            originating_selection_id=selection.selection_id,
        ).decision_id,
        contour_name="phase12_orchestration_contour",
        orchestration_name="phase12_meta_orchestration",
        symbol="BTC/USDT",
        exchange="bybit",
        timeframe=MarketDataTimeframe.M1,
        source=OrchestrationSource.OPPORTUNITY_SELECTION,
        freshness=OrchestrationFreshness(
            generated_at=now,
            expires_at=now.replace(minute=6),
        ),
        validity=OrchestrationValidity(
            status=OrchestrationValidityStatus.VALID,
            observed_inputs=1,
            required_inputs=1,
        ),
        status=OrchestrationStatus.ORCHESTRATED,
        decision=OrchestrationDecision.FORWARD,
        direction=OpportunityDirection.LONG,
        originating_selection_id=selection.selection_id,
        confidence=Decimal("0.8"),
        priority_score=Decimal("0.8"),
        reason_code=OrchestrationReasonCode.CONTEXT_READY,
    )


def make_expandable_position_expansion_candidate() -> PositionExpansionCandidate:
    now = datetime(2026, 3, 20, 12, 1, tzinfo=UTC)
    decision = make_forwarded_orchestration_decision()
    return PositionExpansionCandidate(
        expansion_id=PositionExpansionCandidate.candidate(
            contour_name="phase13_position_expansion_contour",
            expansion_name="phase13_position_expansion",
            symbol="BTC/USDT",
            exchange="bybit",
            timeframe=MarketDataTimeframe.M1,
            source=ExpansionSource.ORCHESTRATION_DECISION,
            freshness=ExpansionFreshness(
                generated_at=now,
                expires_at=now.replace(minute=6),
            ),
            validity=ExpansionValidity(
                status=ExpansionValidityStatus.VALID,
                observed_inputs=1,
                required_inputs=1,
            ),
            decision=ExpansionDecision.ADD,
            status=ExpansionStatus.EXPANDABLE,
            direction=ExpansionDirection.LONG,
            originating_decision_id=decision.decision_id,
            confidence=Decimal("0.8"),
            priority_score=Decimal("0.8"),
            reason_code=ExpansionReasonCode.CONTEXT_READY,
        ).expansion_id,
        contour_name="phase13_position_expansion_contour",
        expansion_name="phase13_position_expansion",
        symbol="BTC/USDT",
        exchange="bybit",
        timeframe=MarketDataTimeframe.M1,
        source=ExpansionSource.ORCHESTRATION_DECISION,
        freshness=ExpansionFreshness(
            generated_at=now,
            expires_at=now.replace(minute=6),
        ),
        validity=ExpansionValidity(
            status=ExpansionValidityStatus.VALID,
            observed_inputs=1,
            required_inputs=1,
        ),
        status=ExpansionStatus.EXPANDABLE,
        decision=ExpansionDecision.ADD,
        direction=ExpansionDirection.LONG,
        originating_decision_id=decision.decision_id,
        confidence=Decimal("0.8"),
        priority_score=Decimal("0.8"),
        reason_code=ExpansionReasonCode.CONTEXT_READY,
    )


def make_approved_portfolio_governor_candidate() -> PortfolioGovernorCandidate:
    now = datetime(2026, 3, 20, 12, 1, tzinfo=UTC)
    expansion = make_expandable_position_expansion_candidate()
    return PortfolioGovernorCandidate(
        governor_id=PortfolioGovernorCandidate.candidate(
            contour_name="phase14_portfolio_governor_contour",
            governor_name="phase14_portfolio_governor",
            symbol="BTC/USDT",
            exchange="bybit",
            timeframe=MarketDataTimeframe.M1,
            source=GovernorSource.POSITION_EXPANSION,
            freshness=GovernorFreshness(
                generated_at=now,
                expires_at=now.replace(minute=6),
            ),
            validity=GovernorValidity(
                status=GovernorValidityStatus.VALID,
                observed_inputs=1,
                required_inputs=1,
            ),
            status=GovernorStatus.APPROVED,
            decision=GovernorDecision.APPROVE,
            direction=GovernorDirection.LONG,
            originating_expansion_id=expansion.expansion_id,
            confidence=Decimal("0.8"),
            priority_score=Decimal("0.8"),
            capital_fraction=Decimal("0.1"),
            reason_code=GovernorReasonCode.CONTEXT_READY,
        ).governor_id,
        contour_name="phase14_portfolio_governor_contour",
        governor_name="phase14_portfolio_governor",
        symbol="BTC/USDT",
        exchange="bybit",
        timeframe=MarketDataTimeframe.M1,
        source=GovernorSource.POSITION_EXPANSION,
        freshness=GovernorFreshness(
            generated_at=now,
            expires_at=now.replace(minute=6),
        ),
        validity=GovernorValidity(
            status=GovernorValidityStatus.VALID,
            observed_inputs=1,
            required_inputs=1,
        ),
        status=GovernorStatus.APPROVED,
        decision=GovernorDecision.APPROVE,
        direction=GovernorDirection.LONG,
        originating_expansion_id=expansion.expansion_id,
        confidence=Decimal("0.8"),
        priority_score=Decimal("0.8"),
        capital_fraction=Decimal("0.1"),
        reason_code=GovernorReasonCode.CONTEXT_READY,
    )


def make_non_approved_portfolio_governor_candidate() -> PortfolioGovernorCandidate:
    now = datetime(2026, 3, 20, 12, 2, tzinfo=UTC)
    expansion = make_expandable_position_expansion_candidate()
    approved = make_approved_portfolio_governor_candidate()
    return PortfolioGovernorCandidate(
        governor_id=approved.governor_id,
        contour_name=approved.contour_name,
        governor_name=approved.governor_name,
        symbol=approved.symbol,
        exchange=approved.exchange,
        timeframe=approved.timeframe,
        source=approved.source,
        freshness=GovernorFreshness(
            generated_at=now,
            expires_at=now.replace(minute=7),
        ),
        validity=GovernorValidity(
            status=GovernorValidityStatus.INVALID,
            observed_inputs=1,
            required_inputs=1,
            invalid_reason="governor_not_approved",
        ),
        status=GovernorStatus.REJECTED,
        decision=GovernorDecision.REJECT,
        direction=None,
        originating_expansion_id=expansion.expansion_id,
        confidence=Decimal("0.4"),
        priority_score=Decimal("0.8"),
        capital_fraction=Decimal("0.1"),
        reason_code=GovernorReasonCode.CONTEXT_INCOMPLETE,
    )


def _fake_shutdown_with_component_stop(
    runtime,
    *,
    components_stopped: list[str],
):
    async def _shutdown(*, force: bool = False) -> ShutdownResult:
        _ = force
        if runtime.orchestration_runtime.is_started:
            await runtime.orchestration_runtime.stop()
        if runtime.position_expansion_runtime.is_started:
            await runtime.position_expansion_runtime.stop()
        if runtime.portfolio_governor_runtime.is_started:
            await runtime.portfolio_governor_runtime.stop()
        if runtime.protection_runtime.is_started:
            await runtime.protection_runtime.stop()
        if runtime.execution_runtime.is_started:
            await runtime.execution_runtime.stop()
        if runtime.opportunity_runtime.is_started:
            await runtime.opportunity_runtime.stop()
        if runtime.strategy_runtime.is_started:
            await runtime.strategy_runtime.stop()
        if runtime.signal_runtime.is_started:
            await runtime.signal_runtime.stop()
        if runtime.intelligence_runtime.is_started:
            await runtime.intelligence_runtime.stop()
        if runtime.shared_analysis_runtime.is_started:
            await runtime.shared_analysis_runtime.stop()
        if runtime.market_data_runtime.is_started:
            await runtime.market_data_runtime.stop()
        return ShutdownResult(
            success=True,
            duration_ms=3,
            phase_reached=ShutdownPhase.COMPLETED,
            components_stopped=components_stopped,
        )

    return _shutdown


@pytest.fixture
def isolated_global_listener_registry():
    """Изолировать глобальный ListenerRegistry для bootstrap-тестов."""
    original_registry = getattr(listeners_base_module, "_listener_registry", None)
    listeners_base_module._listener_registry = ListenerRegistry()
    try:
        yield listeners_base_module._listener_registry
    finally:
        listeners_base_module._listener_registry = original_registry


class TestProductionBootstrap:
    """Тесты composition root Шага 2."""

    @pytest.mark.asyncio
    async def test_builds_official_production_composition_root(self) -> None:  # noqa: PLR0915
        """Bootstrap должен собирать единый production runtime."""
        runtime = await build_production_runtime(
            settings=make_settings(),
            policy=ProductionBootstrapPolicy(
                test_mode=True,
                enable_event_bus_persistence=False,
                enable_risk_persistence=False,
                include_legacy_risk_listener=False,
            ),
        )

        assert runtime.identity.bootstrap_module == "cryptotechnolog.bootstrap"
        assert runtime.identity.version == __version__
        assert runtime.identity.version == runtime.settings.project_version
        assert runtime.identity.active_risk_path == PHASE5_RISK_PATH
        assert runtime.identity.config_identity == runtime.settings.get_config_identity()
        assert runtime.identity.config_revision == runtime.settings.get_config_revision()
        assert runtime.event_bus.listener_registry is runtime.listener_registry
        assert runtime.event_bus.active_risk_path == PHASE5_RISK_PATH
        assert runtime.event_bus.enforce_single_risk_path is True
        assert runtime.health_checker.get_runtime_identity() == runtime.identity
        assert runtime.get_runtime_diagnostics()["composition_root_built"] is True
        assert runtime.get_runtime_diagnostics()["runtime_ready"] is False
        assert (
            runtime.get_runtime_diagnostics()["config_identity"] == runtime.identity.config_identity
        )
        assert (
            runtime.get_runtime_diagnostics()["config_revision"] == runtime.identity.config_revision
        )
        assert runtime.get_runtime_diagnostics()["market_data_runtime"]["started"] is False
        assert runtime.get_runtime_diagnostics()["market_data_runtime"]["ready"] is False
        assert runtime.get_runtime_diagnostics()["shared_analysis_runtime"]["started"] is False
        assert runtime.get_runtime_diagnostics()["shared_analysis_runtime"]["ready"] is False
        assert runtime.get_runtime_diagnostics()["intelligence_runtime"]["started"] is False
        assert runtime.get_runtime_diagnostics()["intelligence_runtime"]["ready"] is False
        assert runtime.get_runtime_diagnostics()["signal_runtime"]["started"] is False
        assert runtime.get_runtime_diagnostics()["signal_runtime"]["ready"] is False
        assert runtime.get_runtime_diagnostics()["strategy_runtime"]["started"] is False
        assert runtime.get_runtime_diagnostics()["strategy_runtime"]["ready"] is False
        assert runtime.get_runtime_diagnostics()["execution_runtime"]["started"] is False
        assert runtime.get_runtime_diagnostics()["execution_runtime"]["ready"] is False
        assert runtime.get_runtime_diagnostics()["oms_runtime"]["started"] is False
        assert runtime.get_runtime_diagnostics()["oms_runtime"]["ready"] is False
        assert runtime.get_runtime_diagnostics()["opportunity_runtime"]["started"] is False
        assert runtime.get_runtime_diagnostics()["opportunity_runtime"]["ready"] is False
        assert runtime.get_runtime_diagnostics()["orchestration_runtime"]["started"] is False
        assert runtime.get_runtime_diagnostics()["orchestration_runtime"]["ready"] is False
        assert runtime.get_runtime_diagnostics()["position_expansion_runtime"]["started"] is False
        assert runtime.get_runtime_diagnostics()["position_expansion_runtime"]["ready"] is False
        assert runtime.get_runtime_diagnostics()["portfolio_governor_runtime"]["started"] is False
        assert runtime.get_runtime_diagnostics()["portfolio_governor_runtime"]["ready"] is False
        assert runtime.get_runtime_diagnostics()["protection_runtime"]["started"] is False
        assert runtime.get_runtime_diagnostics()["protection_runtime"]["ready"] is False
        controller_component = runtime.controller.get_component("event_bus")
        assert controller_component is not None
        assert controller_component is runtime.event_bus
        assert runtime.controller.get_component("phase5_risk_runtime") is runtime.risk_runtime
        assert (
            runtime.controller.get_component("phase6_market_data_runtime")
            is runtime.market_data_runtime
        )
        assert (
            runtime.controller.get_component("phase7_intelligence_runtime")
            is runtime.intelligence_runtime
        )
        assert (
            runtime.controller.get_component("c7r_shared_analysis_runtime")
            is runtime.shared_analysis_runtime
        )
        assert runtime.controller.get_component("phase8_signal_runtime") is runtime.signal_runtime
        assert (
            runtime.controller.get_component("phase9_strategy_runtime") is runtime.strategy_runtime
        )
        assert (
            runtime.controller.get_component("phase10_execution_runtime")
            is runtime.execution_runtime
        )
        assert runtime.controller.get_component("phase16_oms_runtime") is runtime.oms_runtime
        assert (
            runtime.controller.get_component("phase11_opportunity_runtime")
            is runtime.opportunity_runtime
        )
        assert (
            runtime.controller.get_component("phase12_orchestration_runtime")
            is runtime.orchestration_runtime
        )
        assert (
            runtime.controller.get_component("phase13_position_expansion_runtime")
            is runtime.position_expansion_runtime
        )
        assert (
            runtime.controller.get_component("phase14_portfolio_governor_runtime")
            is runtime.portfolio_governor_runtime
        )
        assert (
            runtime.controller.get_component("phase15_protection_runtime")
            is runtime.protection_runtime
        )
        assert SystemEventType.BAR_COMPLETED in runtime.event_bus.handlers
        assert len(runtime.event_bus.handlers[SystemEventType.BAR_COMPLETED]) == 3
        assert len(runtime.event_bus.handlers[SignalEventType.SIGNAL_SNAPSHOT_UPDATED.value]) == 1
        assert len(runtime.event_bus.handlers[SignalEventType.SIGNAL_EMITTED.value]) == 1
        assert len(runtime.event_bus.handlers[SignalEventType.SIGNAL_INVALIDATED.value]) == 1
        assert (
            len(runtime.event_bus.handlers[StrategyEventType.STRATEGY_CANDIDATE_UPDATED.value]) == 1
        )
        assert len(runtime.event_bus.handlers[StrategyEventType.STRATEGY_ACTIONABLE.value]) == 1
        assert len(runtime.event_bus.handlers[StrategyEventType.STRATEGY_INVALIDATED.value]) == 1
        assert (
            len(runtime.event_bus.handlers[ExecutionEventType.EXECUTION_INTENT_UPDATED.value]) == 2
        )
        assert len(runtime.event_bus.handlers[ExecutionEventType.EXECUTION_REQUESTED.value]) == 2
        assert len(runtime.event_bus.handlers[ExecutionEventType.EXECUTION_INVALIDATED.value]) == 2
        assert (
            len(
                runtime.event_bus.handlers[OpportunityEventType.OPPORTUNITY_CANDIDATE_UPDATED.value]
            )
            == 1
        )
        assert len(runtime.event_bus.handlers[OpportunityEventType.OPPORTUNITY_SELECTED.value]) == 1
        assert (
            len(runtime.event_bus.handlers[OpportunityEventType.OPPORTUNITY_INVALIDATED.value]) == 1
        )
        assert (
            len(
                runtime.event_bus.handlers[
                    OrchestrationEventType.ORCHESTRATION_CANDIDATE_UPDATED.value
                ]
            )
            == 1
        )
        assert (
            len(runtime.event_bus.handlers[OrchestrationEventType.ORCHESTRATION_DECIDED.value]) == 1
        )
        assert (
            len(runtime.event_bus.handlers[OrchestrationEventType.ORCHESTRATION_INVALIDATED.value])
            == 1
        )
        assert (
            len(
                runtime.event_bus.handlers[
                    PositionExpansionEventType.POSITION_EXPANSION_CANDIDATE_UPDATED.value
                ]
            )
            == 1
        )
        assert (
            len(
                runtime.event_bus.handlers[
                    PositionExpansionEventType.POSITION_EXPANSION_APPROVED.value
                ]
            )
            == 1
        )
        assert (
            len(
                runtime.event_bus.handlers[
                    PositionExpansionEventType.POSITION_EXPANSION_INVALIDATED.value
                ]
            )
            == 1
        )
        assert (
            len(
                runtime.event_bus.handlers[
                    PortfolioGovernorEventType.PORTFOLIO_GOVERNOR_CANDIDATE_UPDATED.value
                ]
            )
            == 1
        )
        assert (
            len(
                runtime.event_bus.handlers[
                    PortfolioGovernorEventType.PORTFOLIO_GOVERNOR_APPROVED.value
                ]
            )
            == 1
        )
        assert (
            len(
                runtime.event_bus.handlers[
                    PortfolioGovernorEventType.PORTFOLIO_GOVERNOR_INVALIDATED.value
                ]
            )
            == 1
        )
        assert SystemEventType.BAR_COMPLETED not in runtime.risk_runtime.risk_listener.event_types
        assert SystemEventType.RISK_BAR_COMPLETED in runtime.risk_runtime.risk_listener.event_types

        listener_names = [listener.name for listener in runtime.listener_registry.all_listeners]
        assert "risk_check_listener" not in listener_names
        assert "risk_engine_listener" not in listener_names

    @pytest.mark.asyncio
    async def test_runtime_startup_validates_started_runtime_contract(self) -> None:  # noqa: PLR0915
        """startup() должен проверять обязательный runtime contract composition root."""
        runtime = await build_production_runtime(
            settings=make_settings(),
            policy=ProductionBootstrapPolicy(
                test_mode=True,
                enable_event_bus_persistence=False,
                enable_risk_persistence=False,
                include_legacy_risk_listener=False,
            ),
        )

        runtime.controller.startup = AsyncMock(  # type: ignore[method-assign]
            return_value=StartupResult(
                success=True,
                duration_ms=5,
                phase_reached=StartupPhase.READY,
                components_initialized=["database", "redis", "event_bus", "phase5_risk_runtime"],
                components_failed=[],
            )
        )
        runtime.health_checker.check_system = AsyncMock(  # type: ignore[method-assign]
            return_value=SystemHealth(
                overall_status=HealthStatus.HEALTHY,
                components={},
                runtime_identity=runtime.identity,
            )
        )
        runtime.db_manager._connected = True
        runtime.db_manager._pool = Mock()
        runtime.redis_manager._connected = True
        runtime.redis_manager._redis = Mock()
        runtime.event_bus.register_listener(runtime.risk_runtime.risk_listener)
        runtime.risk_runtime._listener_registered = True
        runtime.market_data_runtime._started = True
        runtime.market_data_runtime._refresh_diagnostics(  # type: ignore[attr-defined]
            ready=True,
            lifecycle_state="ready",
            readiness_reasons=(),
            degraded_reasons=(),
        )
        runtime.shared_analysis_runtime._started = True
        runtime.shared_analysis_runtime._refresh_diagnostics(  # type: ignore[attr-defined]
            ready=True,
            lifecycle_state="ready",
            readiness_reasons=(),
        )
        runtime.intelligence_runtime._started = True
        runtime.intelligence_runtime._refresh_diagnostics(  # type: ignore[attr-defined]
            ready=True,
            lifecycle_state="ready",
            readiness_reasons=(),
            degraded_reasons=(),
        )
        runtime.signal_runtime._started = True
        runtime.signal_runtime._refresh_diagnostics(  # type: ignore[attr-defined]
            ready=True,
            lifecycle_state="ready",
            readiness_reasons=(),
            degraded_reasons=(),
        )
        runtime.strategy_runtime._started = True
        runtime.strategy_runtime._refresh_diagnostics(  # type: ignore[attr-defined]
            ready=True,
            lifecycle_state="ready",
            readiness_reasons=(),
            degraded_reasons=(),
        )
        runtime.execution_runtime._started = True
        runtime.execution_runtime._refresh_diagnostics(  # type: ignore[attr-defined]
            ready=True,
            lifecycle_state="ready",
            readiness_reasons=(),
            degraded_reasons=(),
        )
        runtime.opportunity_runtime._started = True
        runtime.opportunity_runtime._refresh_diagnostics(  # type: ignore[attr-defined]
            ready=True,
            lifecycle_state="ready",
            readiness_reasons=(),
            degraded_reasons=(),
        )
        runtime.orchestration_runtime._started = True
        runtime.orchestration_runtime._refresh_diagnostics(  # type: ignore[attr-defined]
            ready=True,
            lifecycle_state="ready",
            readiness_reasons=(),
            degraded_reasons=(),
        )
        runtime.position_expansion_runtime._started = True
        runtime.position_expansion_runtime._refresh_diagnostics(  # type: ignore[attr-defined]
            ready=True,
            lifecycle_state="ready",
            readiness_reasons=(),
            degraded_reasons=(),
        )
        runtime.portfolio_governor_runtime._started = True
        runtime.portfolio_governor_runtime._refresh_diagnostics(  # type: ignore[attr-defined]
            ready=True,
            lifecycle_state="ready",
            readiness_reasons=(),
            degraded_reasons=(),
        )
        runtime.protection_runtime._started = True
        runtime.protection_runtime._refresh_diagnostics(  # type: ignore[attr-defined]
            ready=True,
            lifecycle_state="ready",
            readiness_reasons=(),
            degraded_reasons=(),
        )

        result = await runtime.startup()

        assert result.phase_reached == StartupPhase.READY
        assert runtime.is_started is True
        assert runtime.last_health is not None
        diagnostics = runtime.get_runtime_diagnostics()
        assert diagnostics["runtime_started"] is True
        assert diagnostics["runtime_ready"] is True
        assert diagnostics["active_risk_path"] == PHASE5_RISK_PATH
        assert diagnostics["config_identity"] == runtime.identity.config_identity
        assert diagnostics["config_revision"] == runtime.identity.config_revision
        assert diagnostics["protection_runtime"]["started"] is True
        assert diagnostics["protection_runtime"]["ready"] is True
        assert diagnostics["market_data_runtime"]["ready"] is True
        assert diagnostics["shared_analysis_runtime"]["ready"] is True
        assert diagnostics["intelligence_runtime"]["ready"] is True
        assert diagnostics["signal_runtime"]["ready"] is True
        assert diagnostics["strategy_runtime"]["ready"] is True
        assert diagnostics["execution_runtime"]["ready"] is True
        assert diagnostics["opportunity_runtime"]["ready"] is True
        assert diagnostics["orchestration_runtime"]["ready"] is True
        assert diagnostics["position_expansion_runtime"]["ready"] is True
        assert diagnostics["portfolio_governor_runtime"]["ready"] is True

    @pytest.mark.asyncio
    async def test_runtime_startup_fail_fast_exposes_block_reason_in_diagnostics(self) -> None:
        """Fail-fast path должен быть виден в readiness и runtime diagnostics."""
        runtime = await build_production_runtime(
            settings=make_settings(),
            policy=ProductionBootstrapPolicy(
                test_mode=True,
                enable_event_bus_persistence=False,
                enable_risk_persistence=False,
                include_legacy_risk_listener=False,
            ),
        )

        runtime.controller.startup = AsyncMock(  # type: ignore[method-assign]
            return_value=StartupResult(
                success=True,
                duration_ms=5,
                phase_reached=StartupPhase.READY,
                components_initialized=["database", "redis", "event_bus", "phase5_risk_runtime"],
                components_failed=[],
            )
        )

        with pytest.raises(ProductionBootstrapError, match="подключение к БД"):
            await runtime.startup()

        diagnostics = runtime.get_runtime_diagnostics()
        assert diagnostics["runtime_started"] is False
        assert diagnostics["runtime_ready"] is False
        assert diagnostics["startup_state"] == "failed"
        assert "подключение к БД" in diagnostics["failure_reason"]

        health = await runtime.health_checker.check_system()
        assert health.readiness_status == "not_ready"
        assert any(reason.startswith("startup_failed:") for reason in health.readiness_reasons)

    @pytest.mark.asyncio
    async def test_runtime_startup_exposes_market_data_not_ready_as_degraded(self) -> None:  # noqa: PLR0915
        """Production startup не должен маскировать неготовый market data слой как ready."""
        runtime = await build_production_runtime(
            settings=make_settings(),
            policy=ProductionBootstrapPolicy(
                test_mode=True,
                enable_event_bus_persistence=False,
                enable_risk_persistence=False,
                include_legacy_risk_listener=False,
            ),
        )

        runtime.controller.startup = AsyncMock(  # type: ignore[method-assign]
            return_value=StartupResult(
                success=True,
                duration_ms=5,
                phase_reached=StartupPhase.READY,
                components_initialized=[
                    "database",
                    "redis",
                    "event_bus",
                    "phase5_risk_runtime",
                    "phase6_market_data_runtime",
                    "c7r_shared_analysis_runtime",
                    "phase7_intelligence_runtime",
                ],
                components_failed=[],
            )
        )
        runtime.health_checker.check_system = AsyncMock(  # type: ignore[method-assign]
            return_value=SystemHealth(
                overall_status=HealthStatus.HEALTHY,
                components={},
                runtime_identity=runtime.identity,
                diagnostics={
                    "market_data_runtime": runtime.market_data_runtime.get_runtime_diagnostics()
                },
            )
        )
        runtime.db_manager._connected = True
        runtime.db_manager._pool = Mock()
        runtime.redis_manager._connected = True
        runtime.redis_manager._redis = Mock()
        runtime.event_bus.register_listener(runtime.risk_runtime.risk_listener)
        runtime.risk_runtime._listener_registered = True
        runtime.market_data_runtime._started = True
        runtime.market_data_runtime._refresh_diagnostics(  # type: ignore[attr-defined]
            ready=False,
            lifecycle_state="not_ready",
            readiness_reasons=("no_raw_universe_snapshot", "no_universe_quality_assessment"),
            degraded_reasons=(),
        )
        runtime.shared_analysis_runtime._started = True
        runtime.shared_analysis_runtime._refresh_diagnostics(  # type: ignore[attr-defined]
            ready=False,
            lifecycle_state="warming",
            readiness_reasons=("derived_inputs_warming",),
        )
        runtime.intelligence_runtime._started = True
        runtime.intelligence_runtime._refresh_diagnostics(  # type: ignore[attr-defined]
            ready=False,
            lifecycle_state="warming",
            readiness_reasons=("derya_history_warming",),
            degraded_reasons=(),
        )
        runtime.signal_runtime._started = True
        runtime.signal_runtime._refresh_diagnostics(  # type: ignore[attr-defined]
            ready=False,
            lifecycle_state="warming",
            readiness_reasons=("no_signal_context_processed",),
            degraded_reasons=(),
        )
        runtime.strategy_runtime._started = True
        runtime.strategy_runtime._refresh_diagnostics(  # type: ignore[attr-defined]
            ready=False,
            lifecycle_state="warming",
            readiness_reasons=("no_strategy_context_processed",),
            degraded_reasons=(),
        )
        runtime.execution_runtime._started = True
        runtime.execution_runtime._refresh_diagnostics(  # type: ignore[attr-defined]
            ready=False,
            lifecycle_state="warming",
            readiness_reasons=("no_execution_context_processed",),
            degraded_reasons=(),
        )
        runtime.opportunity_runtime._started = True
        runtime.opportunity_runtime._refresh_diagnostics(  # type: ignore[attr-defined]
            ready=False,
            lifecycle_state="warming",
            readiness_reasons=("no_selection_context_processed",),
            degraded_reasons=(),
        )
        runtime.orchestration_runtime._started = True
        runtime.orchestration_runtime._refresh_diagnostics(  # type: ignore[attr-defined]
            ready=False,
            lifecycle_state="warming",
            readiness_reasons=("no_orchestration_context_processed",),
            degraded_reasons=(),
        )
        runtime.position_expansion_runtime._started = True
        runtime.position_expansion_runtime._refresh_diagnostics(  # type: ignore[attr-defined]
            ready=False,
            lifecycle_state="warming",
            readiness_reasons=("no_position_expansion_context_processed",),
            degraded_reasons=(),
        )
        runtime.portfolio_governor_runtime._started = True
        runtime.portfolio_governor_runtime._refresh_diagnostics(  # type: ignore[attr-defined]
            ready=False,
            lifecycle_state="warming",
            readiness_reasons=("no_portfolio_governor_context_processed",),
            degraded_reasons=(),
        )
        runtime.protection_runtime._started = True
        runtime.protection_runtime._refresh_diagnostics(  # type: ignore[attr-defined]
            ready=False,
            lifecycle_state="warming",
            readiness_reasons=("no_protection_context_processed",),
            degraded_reasons=(),
        )

        await runtime.startup()

        diagnostics = runtime.get_runtime_diagnostics()
        assert diagnostics["runtime_started"] is True
        assert diagnostics["runtime_ready"] is False
        assert diagnostics["startup_state"] == "degraded"
        assert "phase6_market_data:not_ready" in diagnostics["degraded_reasons"]
        assert "c7r_shared_analysis:not_ready" in diagnostics["degraded_reasons"]
        assert "phase7_intelligence:not_ready" in diagnostics["degraded_reasons"]
        assert "phase8_signal:not_ready" in diagnostics["degraded_reasons"]
        assert "phase9_strategy:not_ready" in diagnostics["degraded_reasons"]
        assert "phase10_execution:not_ready" in diagnostics["degraded_reasons"]
        assert diagnostics["market_data_runtime"]["ready"] is False
        assert diagnostics["shared_analysis_runtime"]["ready"] is False
        assert diagnostics["intelligence_runtime"]["ready"] is False
        assert diagnostics["signal_runtime"]["ready"] is False
        assert diagnostics["strategy_runtime"]["ready"] is False
        assert diagnostics["execution_runtime"]["ready"] is False
        assert diagnostics["opportunity_runtime"]["ready"] is False
        assert diagnostics["orchestration_runtime"]["ready"] is False
        assert diagnostics["position_expansion_runtime"]["ready"] is False
        assert diagnostics["portfolio_governor_runtime"]["ready"] is False
        assert diagnostics["protection_runtime"]["ready"] is False
        assert "phase15_protection:not_ready" in diagnostics["degraded_reasons"]

    @pytest.mark.asyncio
    async def test_runtime_startup_exposes_degraded_readiness_when_health_is_degraded(self) -> None:
        """Деградированный startup не должен выглядеть как fully ready."""
        runtime = await build_production_runtime(
            settings=make_settings(),
            policy=ProductionBootstrapPolicy(
                test_mode=True,
                enable_event_bus_persistence=False,
                enable_risk_persistence=False,
                include_legacy_risk_listener=False,
            ),
        )

        runtime.controller.startup = AsyncMock(  # type: ignore[method-assign]
            return_value=StartupResult(
                success=True,
                duration_ms=5,
                phase_reached=StartupPhase.READY,
                components_initialized=["database", "redis", "event_bus", "phase5_risk_runtime"],
                components_failed=[],
            )
        )
        runtime.health_checker.check_system = AsyncMock(  # type: ignore[method-assign]
            return_value=SystemHealth(
                overall_status=HealthStatus.DEGRADED,
                components={
                    "metrics": Mock(
                        component="metrics",
                        status=HealthStatus.DEGRADED,
                    )
                },
                runtime_identity=runtime.identity,
            )
        )
        runtime.db_manager._connected = True
        runtime.db_manager._pool = Mock()
        runtime.redis_manager._connected = True
        runtime.redis_manager._redis = Mock()
        runtime.event_bus.register_listener(runtime.risk_runtime.risk_listener)
        runtime.risk_runtime._listener_registered = True
        runtime.strategy_runtime._started = True
        runtime.execution_runtime._started = True
        runtime.opportunity_runtime._started = True
        runtime.orchestration_runtime._started = True
        runtime.position_expansion_runtime._started = True
        runtime.portfolio_governor_runtime._started = True
        runtime.protection_runtime._started = True

        await runtime.startup()

        diagnostics = runtime.get_runtime_diagnostics()
        assert diagnostics["runtime_started"] is True
        assert diagnostics["runtime_ready"] is False
        assert diagnostics["startup_state"] == "degraded"
        assert "metrics:degraded" in diagnostics["degraded_reasons"]

    @pytest.mark.asyncio
    async def test_runtime_shutdown_updates_runtime_diagnostics(self) -> None:  # noqa: PLR0915
        """Shutdown lifecycle должен отражаться в operator-facing diagnostics."""
        runtime = await build_production_runtime(
            settings=make_settings(),
            policy=ProductionBootstrapPolicy(
                test_mode=True,
                enable_event_bus_persistence=False,
                enable_risk_persistence=False,
                include_legacy_risk_listener=False,
            ),
        )

        runtime.controller.startup = AsyncMock(  # type: ignore[method-assign]
            return_value=StartupResult(
                success=True,
                duration_ms=5,
                phase_reached=StartupPhase.READY,
                components_initialized=["database", "redis", "event_bus", "phase5_risk_runtime"],
                components_failed=[],
            )
        )
        runtime.controller.shutdown = AsyncMock(  # type: ignore[method-assign]
            side_effect=_fake_shutdown_with_component_stop(
                runtime,
                components_stopped=["phase5_risk_runtime", "event_bus"],
            )
        )
        runtime.health_checker.check_system = AsyncMock(  # type: ignore[method-assign]
            return_value=SystemHealth(
                overall_status=HealthStatus.HEALTHY,
                components={},
                runtime_identity=runtime.identity,
            )
        )
        runtime.db_manager._connected = True
        runtime.db_manager._pool = Mock()
        runtime.redis_manager._connected = True
        runtime.redis_manager._redis = Mock()
        runtime.event_bus.register_listener(runtime.risk_runtime.risk_listener)
        runtime.risk_runtime._listener_registered = True
        runtime.market_data_runtime._started = True
        runtime.market_data_runtime._refresh_diagnostics(  # type: ignore[attr-defined]
            ready=True,
            lifecycle_state="ready",
            readiness_reasons=(),
            degraded_reasons=(),
        )
        runtime.shared_analysis_runtime._started = True
        runtime.shared_analysis_runtime._refresh_diagnostics(  # type: ignore[attr-defined]
            ready=True,
            lifecycle_state="ready",
            readiness_reasons=(),
        )
        runtime.intelligence_runtime._started = True
        runtime.intelligence_runtime._refresh_diagnostics(  # type: ignore[attr-defined]
            ready=True,
            lifecycle_state="ready",
            readiness_reasons=(),
            degraded_reasons=(),
        )
        runtime.signal_runtime._started = True
        runtime.signal_runtime._refresh_diagnostics(  # type: ignore[attr-defined]
            ready=True,
            lifecycle_state="ready",
            readiness_reasons=(),
            degraded_reasons=(),
        )
        runtime.strategy_runtime._started = True
        runtime.strategy_runtime._refresh_diagnostics(  # type: ignore[attr-defined]
            ready=True,
            lifecycle_state="ready",
            readiness_reasons=(),
            degraded_reasons=(),
        )
        runtime.execution_runtime._started = True
        runtime.execution_runtime._refresh_diagnostics(  # type: ignore[attr-defined]
            ready=True,
            lifecycle_state="ready",
            readiness_reasons=(),
            degraded_reasons=(),
        )
        runtime.opportunity_runtime._started = True
        runtime.opportunity_runtime._refresh_diagnostics(  # type: ignore[attr-defined]
            ready=True,
            lifecycle_state="ready",
            readiness_reasons=(),
            degraded_reasons=(),
        )
        runtime.orchestration_runtime._started = True
        runtime.orchestration_runtime._refresh_diagnostics(  # type: ignore[attr-defined]
            ready=True,
            lifecycle_state="ready",
            readiness_reasons=(),
            degraded_reasons=(),
        )
        runtime.position_expansion_runtime._started = True
        runtime.position_expansion_runtime._refresh_diagnostics(  # type: ignore[attr-defined]
            ready=True,
            lifecycle_state="ready",
            readiness_reasons=(),
            degraded_reasons=(),
        )
        runtime.portfolio_governor_runtime._started = True
        runtime.portfolio_governor_runtime._refresh_diagnostics(  # type: ignore[attr-defined]
            ready=True,
            lifecycle_state="ready",
            readiness_reasons=(),
            degraded_reasons=(),
        )
        runtime.protection_runtime._started = True
        runtime.protection_runtime._refresh_diagnostics(  # type: ignore[attr-defined]
            ready=True,
            lifecycle_state="ready",
            readiness_reasons=(),
            degraded_reasons=(),
        )

        await runtime.startup()
        shutdown_result = await runtime.shutdown()

        diagnostics = runtime.get_runtime_diagnostics()
        assert shutdown_result.phase_reached == ShutdownPhase.COMPLETED
        assert runtime.is_started is False
        assert diagnostics["runtime_started"] is False
        assert diagnostics["runtime_ready"] is False
        assert diagnostics["shutdown_state"] == ShutdownPhase.COMPLETED.value
        assert "runtime_stopped" in diagnostics["degraded_reasons"]
        assert diagnostics["shared_analysis_runtime"]["started"] is False
        assert diagnostics["shared_analysis_runtime"]["ready"] is False
        assert diagnostics["shared_analysis_runtime"]["lifecycle_state"] == "stopped"
        assert diagnostics["shared_analysis_runtime"]["readiness_reasons"] == ["runtime_stopped"]
        assert diagnostics["intelligence_runtime"]["started"] is False
        assert diagnostics["intelligence_runtime"]["ready"] is False
        assert diagnostics["intelligence_runtime"]["lifecycle_state"] == "stopped"
        assert diagnostics["intelligence_runtime"]["readiness_reasons"] == ["runtime_stopped"]
        assert diagnostics["intelligence_runtime"]["degraded_reasons"] == []
        assert diagnostics["signal_runtime"]["started"] is False
        assert diagnostics["signal_runtime"]["ready"] is False
        assert diagnostics["signal_runtime"]["lifecycle_state"] == "stopped"
        assert diagnostics["signal_runtime"]["tracked_signal_keys"] == 0
        assert diagnostics["signal_runtime"]["readiness_reasons"] == ["runtime_stopped"]
        assert diagnostics["strategy_runtime"]["started"] is False
        assert diagnostics["strategy_runtime"]["ready"] is False
        assert diagnostics["strategy_runtime"]["lifecycle_state"] == "stopped"
        assert diagnostics["strategy_runtime"]["tracked_candidate_keys"] == 0
        assert diagnostics["strategy_runtime"]["readiness_reasons"] == ["runtime_stopped"]
        assert diagnostics["execution_runtime"]["started"] is False
        assert diagnostics["execution_runtime"]["ready"] is False
        assert diagnostics["execution_runtime"]["lifecycle_state"] == "stopped"
        assert diagnostics["execution_runtime"]["tracked_intent_keys"] == 0
        assert diagnostics["execution_runtime"]["readiness_reasons"] == ["runtime_stopped"]
        assert diagnostics["opportunity_runtime"]["started"] is False
        assert diagnostics["opportunity_runtime"]["ready"] is False
        assert diagnostics["opportunity_runtime"]["lifecycle_state"] == "stopped"
        assert diagnostics["opportunity_runtime"]["tracked_selection_keys"] == 0
        assert diagnostics["opportunity_runtime"]["readiness_reasons"] == ["runtime_stopped"]
        assert diagnostics["orchestration_runtime"]["started"] is False
        assert diagnostics["orchestration_runtime"]["ready"] is False
        assert diagnostics["orchestration_runtime"]["lifecycle_state"] == "stopped"
        assert diagnostics["orchestration_runtime"]["tracked_decision_keys"] == 0
        assert diagnostics["orchestration_runtime"]["readiness_reasons"] == ["runtime_stopped"]
        assert diagnostics["position_expansion_runtime"]["started"] is False
        assert diagnostics["position_expansion_runtime"]["ready"] is False
        assert diagnostics["position_expansion_runtime"]["lifecycle_state"] == "stopped"
        assert diagnostics["position_expansion_runtime"]["tracked_expansion_keys"] == 0
        assert diagnostics["position_expansion_runtime"]["readiness_reasons"] == ["runtime_stopped"]
        assert diagnostics["portfolio_governor_runtime"]["started"] is False
        assert diagnostics["portfolio_governor_runtime"]["ready"] is False
        assert diagnostics["portfolio_governor_runtime"]["lifecycle_state"] == "stopped"
        assert diagnostics["portfolio_governor_runtime"]["tracked_governor_keys"] == 0
        assert diagnostics["portfolio_governor_runtime"]["readiness_reasons"] == ["runtime_stopped"]
        assert diagnostics["protection_runtime"]["started"] is False
        assert diagnostics["protection_runtime"]["ready"] is False
        assert diagnostics["protection_runtime"]["lifecycle_state"] == "stopped"
        assert diagnostics["protection_runtime"]["tracked_protection_keys"] == 0
        assert diagnostics["protection_runtime"]["readiness_reasons"] == ["runtime_stopped"]

    @pytest.mark.asyncio
    async def test_start_production_runtime_preserves_fail_fast_truth_after_cleanup(self) -> None:
        """Entry helper не должен маскировать startup failure как обычный stopped runtime."""
        runtime = await build_production_runtime(
            settings=make_settings(),
            policy=ProductionBootstrapPolicy(
                test_mode=True,
                enable_event_bus_persistence=False,
                enable_risk_persistence=False,
                include_legacy_risk_listener=False,
            ),
        )
        runtime.controller.startup = AsyncMock(  # type: ignore[method-assign]
            return_value=StartupResult(
                success=True,
                duration_ms=5,
                phase_reached=StartupPhase.READY,
                components_initialized=["database", "redis", "event_bus", "phase5_risk_runtime"],
                components_failed=[],
            )
        )
        runtime.controller.shutdown = AsyncMock(  # type: ignore[method-assign]
            return_value=ShutdownResult(
                success=True,
                duration_ms=3,
                phase_reached=ShutdownPhase.COMPLETED,
                components_stopped=[],
            )
        )
        runtime.health_checker.check_system = AsyncMock(  # type: ignore[method-assign]
            return_value=SystemHealth(
                overall_status=HealthStatus.UNKNOWN,
                components={},
                runtime_identity=runtime.identity,
            )
        )

        with (
            patch(
                "cryptotechnolog.bootstrap.build_production_runtime",
                new=AsyncMock(return_value=runtime),
            ),
            pytest.raises(ProductionBootstrapError, match="подключение к БД"),
        ):
            await start_production_runtime(
                settings=make_settings(),
                policy=ProductionBootstrapPolicy(
                    test_mode=True,
                    enable_event_bus_persistence=False,
                    enable_risk_persistence=False,
                    include_legacy_risk_listener=False,
                ),
            )

        runtime.controller.shutdown.assert_awaited_once_with(force=True)
        diagnostics = runtime.get_runtime_diagnostics()
        assert diagnostics["runtime_started"] is False
        assert diagnostics["runtime_ready"] is False
        assert diagnostics["startup_state"] == "failed"
        assert diagnostics["shutdown_state"] == ShutdownPhase.COMPLETED.value
        assert "подключение к БД" in diagnostics["failure_reason"]
        assert diagnostics["degraded_reasons"] == ["startup_failed_cleanup"]

    @pytest.mark.asyncio
    async def test_enable_listeners_rejects_legacy_global_registry_after_startup(
        self,
        isolated_global_listener_registry: ListenerRegistry,
    ) -> None:
        """После startup production runtime не должен принимать global legacy registry."""
        runtime = await build_production_runtime(
            settings=make_settings(),
            policy=ProductionBootstrapPolicy(
                test_mode=True,
                enable_event_bus_persistence=False,
                enable_risk_persistence=False,
                include_legacy_risk_listener=False,
            ),
        )

        runtime.event_bus.register_listener(runtime.risk_runtime.risk_listener)
        runtime.risk_runtime._listener_registered = True
        runtime.event_bus.seal_risk_path_policy()

        isolated_global_listener_registry.register(RiskListener())

        with pytest.raises(ValueError):
            runtime.event_bus.enable_listeners()

    @pytest.mark.asyncio
    async def test_direct_registry_replacement_rejects_mixed_risk_registry_after_startup(
        self,
    ) -> None:
        """После startup production runtime не должен принимать mixed registry."""
        runtime = await build_production_runtime(
            settings=make_settings(),
            policy=ProductionBootstrapPolicy(
                test_mode=True,
                enable_event_bus_persistence=False,
                enable_risk_persistence=False,
                include_legacy_risk_listener=False,
            ),
        )

        runtime.event_bus.register_listener(runtime.risk_runtime.risk_listener)
        runtime.risk_runtime._listener_registered = True
        runtime.event_bus.seal_risk_path_policy()

        mixed_registry = ListenerRegistry()
        mixed_registry.register(runtime.risk_runtime.risk_listener)
        mixed_registry.register(RiskListener())

        with pytest.raises(ValueError):
            runtime.event_bus.listener_registry = mixed_registry

    @pytest.mark.asyncio
    async def test_production_runtime_rejects_legacy_risk_listener_policy(self) -> None:
        """Production root не должен позволять legacy risk path."""
        with pytest.raises(ProductionBootstrapError):
            await build_production_runtime(
                settings=make_settings(),
                policy=ProductionBootstrapPolicy(
                    test_mode=True,
                    enable_event_bus_persistence=False,
                    enable_risk_persistence=False,
                    include_legacy_risk_listener=True,
                ),
            )

    @pytest.mark.asyncio
    async def test_event_bus_blocks_double_risk_wiring_in_production_runtime(self) -> None:
        """После подключения Phase 5 path legacy listener не должен регистрироваться."""
        runtime = await build_production_runtime(
            settings=make_settings(),
            policy=ProductionBootstrapPolicy(
                test_mode=True,
                enable_event_bus_persistence=False,
                enable_risk_persistence=False,
                include_legacy_risk_listener=False,
            ),
        )

        await runtime.risk_runtime.start()

        with pytest.raises(ValueError):
            runtime.event_bus.register_listener(RiskListener())

        await runtime.risk_runtime.stop()

    @pytest.mark.asyncio
    async def test_bar_completed_wiring_marks_intelligence_runtime_degraded_on_ingest_failure(
        self,
    ) -> None:
        """BAR_COMPLETED wiring должен честно переводить intelligence runtime в degraded."""
        runtime = await build_production_runtime(
            settings=make_settings(),
            policy=ProductionBootstrapPolicy(
                test_mode=True,
                enable_event_bus_persistence=False,
                enable_risk_persistence=False,
                include_legacy_risk_listener=False,
            ),
        )

        runtime.intelligence_runtime._started = True
        runtime.intelligence_runtime.ingest_bar_completed_payload = Mock(  # type: ignore[method-assign]
            side_effect=RuntimeError("derya_ingest_failure")
        )
        handler = runtime.event_bus.handlers[SystemEventType.BAR_COMPLETED][0]
        event = build_market_data_event(
            event_type=MarketDataEventType.BAR_COMPLETED,
            payload=BarCompletedPayload.from_contract(make_completed_bar()),
        )

        with pytest.raises(RuntimeError, match="derya_ingest_failure"):
            await handler(event)

        diagnostics = runtime.intelligence_runtime.get_runtime_diagnostics()
        assert diagnostics["started"] is True
        assert diagnostics["ready"] is False
        assert diagnostics["lifecycle_state"] == "degraded"
        assert diagnostics["last_failure_reason"] == "bar_ingest_failed:derya_ingest_failure"
        assert diagnostics["degraded_reasons"] == ["bar_ingest_failed:derya_ingest_failure"]

    @pytest.mark.asyncio
    async def test_bar_completed_wiring_marks_shared_analysis_runtime_degraded_on_ingest_failure(
        self,
    ) -> None:
        """BAR_COMPLETED wiring должен честно переводить shared analysis runtime в degraded."""
        runtime = await build_production_runtime(
            settings=make_settings(),
            policy=ProductionBootstrapPolicy(
                test_mode=True,
                enable_event_bus_persistence=False,
                enable_risk_persistence=False,
                include_legacy_risk_listener=False,
            ),
        )

        runtime.shared_analysis_runtime._started = True
        runtime.shared_analysis_runtime.ingest_bar_completed_payload = Mock(  # type: ignore[method-assign]
            side_effect=RuntimeError("analysis_ingest_failure")
        )
        handler = runtime.event_bus.handlers[SystemEventType.BAR_COMPLETED][1]
        event = build_market_data_event(
            event_type=MarketDataEventType.BAR_COMPLETED,
            payload=BarCompletedPayload.from_contract(make_completed_bar()),
        )

        with pytest.raises(
            RuntimeError, match="shared_analysis_bar_ingest_failed:analysis_ingest_failure"
        ):
            await handler(event)

        diagnostics = runtime.shared_analysis_runtime.get_runtime_diagnostics()
        assert diagnostics["started"] is True
        assert diagnostics["ready"] is False
        assert diagnostics["lifecycle_state"] == "degraded"
        assert diagnostics["last_failure_reason"] == "bar_ingest_failed:analysis_ingest_failure"
        assert diagnostics["degraded_reasons"] == ["bar_ingest_failed:analysis_ingest_failure"]

    @pytest.mark.asyncio
    async def test_bar_completed_wiring_marks_signal_runtime_degraded_on_ingest_failure(
        self,
    ) -> None:
        """BAR_COMPLETED wiring должен честно переводить signal runtime в degraded."""
        runtime = await build_production_runtime(
            settings=make_settings(),
            policy=ProductionBootstrapPolicy(
                test_mode=True,
                enable_event_bus_persistence=False,
                enable_risk_persistence=False,
                include_legacy_risk_listener=False,
            ),
        )

        runtime.signal_runtime._started = True
        runtime.signal_runtime.ingest_bar_completed_payload = Mock(  # type: ignore[method-assign]
            side_effect=RuntimeError("signal_ingest_failure")
        )
        handler = runtime.event_bus.handlers[SystemEventType.BAR_COMPLETED][2]
        event = build_market_data_event(
            event_type=MarketDataEventType.BAR_COMPLETED,
            payload=BarCompletedPayload.from_contract(make_completed_bar()),
        )

        with pytest.raises(RuntimeError, match="signal_bar_ingest_failed:signal_ingest_failure"):
            await handler(event)

        diagnostics = runtime.signal_runtime.get_runtime_diagnostics()
        assert diagnostics["started"] is True
        assert diagnostics["ready"] is False
        assert diagnostics["lifecycle_state"] == "degraded"
        assert diagnostics["last_failure_reason"] == "bar_ingest_failed:signal_ingest_failure"
        assert diagnostics["degraded_reasons"] == ["bar_ingest_failed:signal_ingest_failure"]

    @pytest.mark.asyncio
    async def test_signal_event_wiring_marks_strategy_runtime_degraded_on_ingest_failure(
        self,
    ) -> None:
        """Signal-event wiring должен честно переводить strategy runtime в degraded."""
        runtime = await build_production_runtime(
            settings=make_settings(),
            policy=ProductionBootstrapPolicy(
                test_mode=True,
                enable_event_bus_persistence=False,
                enable_risk_persistence=False,
                include_legacy_risk_listener=False,
            ),
        )

        runtime.strategy_runtime._started = True
        runtime.strategy_runtime.ingest_signal = Mock(  # type: ignore[method-assign]
            side_effect=RuntimeError("strategy_ingest_failure")
        )
        handler = runtime.event_bus.handlers[SignalEventType.SIGNAL_EMITTED.value][0]
        signal_event = Event.new(
            SignalEventType.SIGNAL_EMITTED.value,
            "SIGNAL_RUNTIME",
            {
                "symbol": "BTC/USDT",
                "exchange": "bybit",
                "timeframe": MarketDataTimeframe.M1.value,
                "generated_at": datetime.now(UTC).isoformat(),
            },
        )

        with pytest.raises(
            RuntimeError,
            match="strategy_signal_ingest_failed:strategy_signal_truth_missing_for_event",
        ):
            await handler(signal_event)

        runtime.signal_runtime.get_signal = Mock(  # type: ignore[method-assign]
            return_value=Mock(
                signal_id="sig-1",
                symbol="BTC/USDT",
                exchange="bybit",
                timeframe=MarketDataTimeframe.M1,
                freshness=Mock(generated_at=datetime.now(UTC)),
            )
        )

        with pytest.raises(
            RuntimeError, match="strategy_signal_ingest_failed:strategy_ingest_failure"
        ):
            await handler(signal_event)

        diagnostics = runtime.strategy_runtime.get_runtime_diagnostics()
        assert diagnostics["started"] is True
        assert diagnostics["ready"] is False
        assert diagnostics["lifecycle_state"] == "degraded"
        assert diagnostics["last_failure_reason"] == "signal_ingest_failed:strategy_ingest_failure"
        assert diagnostics["degraded_reasons"] == ["signal_ingest_failed:strategy_ingest_failure"]

    @pytest.mark.asyncio
    async def test_bar_completed_wiring_keeps_signal_context_assembly_inside_signal_runtime(
        self,
    ) -> None:
        """Composition root должен передавать truths в SignalRuntime, а не собирать SignalContext."""
        runtime = await build_production_runtime(
            settings=make_settings(),
            policy=ProductionBootstrapPolicy(
                test_mode=True,
                enable_event_bus_persistence=False,
                enable_risk_persistence=False,
                include_legacy_risk_listener=False,
            ),
        )

        runtime.signal_runtime._started = True
        runtime.signal_runtime.ingest_truths = Mock()  # type: ignore[method-assign]
        runtime.signal_runtime.ingest_bar_completed_payload = Mock(  # type: ignore[method-assign]
            side_effect=runtime.signal_runtime.ingest_bar_completed_payload
        )
        handler = runtime.event_bus.handlers[SystemEventType.BAR_COMPLETED][2]
        event = build_market_data_event(
            event_type=MarketDataEventType.BAR_COMPLETED,
            payload=BarCompletedPayload.from_contract(make_completed_bar()),
        )

        await handler(event)

        runtime.signal_runtime.ingest_bar_completed_payload.assert_called_once()
        runtime.signal_runtime.ingest_truths.assert_called_once()

    @pytest.mark.asyncio
    async def test_signal_event_wiring_keeps_strategy_context_assembly_inside_strategy_runtime(
        self,
    ) -> None:
        """Composition root должен передавать signal truth в StrategyRuntime, а не собирать StrategyContext."""
        runtime = await build_production_runtime(
            settings=make_settings(),
            policy=ProductionBootstrapPolicy(
                test_mode=True,
                enable_event_bus_persistence=False,
                enable_risk_persistence=False,
                include_legacy_risk_listener=False,
            ),
        )

        runtime.strategy_runtime._started = True
        runtime.strategy_runtime._assemble_strategy_context = Mock(  # type: ignore[attr-defined, method-assign]
            wraps=runtime.strategy_runtime._assemble_strategy_context  # type: ignore[attr-defined]
        )
        runtime.strategy_runtime.ingest_signal = Mock(  # type: ignore[method-assign]
            side_effect=runtime.strategy_runtime.ingest_signal
        )
        runtime.signal_runtime.get_signal = Mock(  # type: ignore[method-assign]
            return_value=make_active_signal_snapshot()
        )
        handler = runtime.event_bus.handlers[SignalEventType.SIGNAL_EMITTED.value][0]
        signal_event = Event.new(
            SignalEventType.SIGNAL_EMITTED.value,
            "SIGNAL_RUNTIME",
            {
                "symbol": "BTC/USDT",
                "exchange": "bybit",
                "timeframe": MarketDataTimeframe.M1.value,
                "generated_at": datetime.now(UTC).isoformat(),
            },
        )

        await handler(signal_event)

        runtime.strategy_runtime.ingest_signal.assert_called_once()
        runtime.strategy_runtime._assemble_strategy_context.assert_called_once()  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_strategy_event_wiring_marks_execution_runtime_degraded_on_ingest_failure(
        self,
    ) -> None:
        """Strategy-event wiring должен честно переводить execution runtime в degraded."""
        runtime = await build_production_runtime(
            settings=make_settings(),
            policy=ProductionBootstrapPolicy(
                test_mode=True,
                enable_event_bus_persistence=False,
                enable_risk_persistence=False,
                include_legacy_risk_listener=False,
            ),
        )

        runtime.execution_runtime._started = True
        runtime.execution_runtime.ingest_candidate = Mock(  # type: ignore[method-assign]
            side_effect=RuntimeError("execution_ingest_failure")
        )
        handler = runtime.event_bus.handlers[StrategyEventType.STRATEGY_ACTIONABLE.value][0]
        strategy_event = Event.new(
            StrategyEventType.STRATEGY_ACTIONABLE.value,
            "STRATEGY_RUNTIME",
            {
                "symbol": "BTC/USDT",
                "exchange": "bybit",
                "timeframe": MarketDataTimeframe.M1.value,
                "generated_at": datetime.now(UTC).isoformat(),
            },
        )

        with pytest.raises(
            RuntimeError,
            match="execution_candidate_ingest_failed:execution_strategy_truth_missing_for_event",
        ):
            await handler(strategy_event)

        runtime.strategy_runtime.get_candidate = Mock(  # type: ignore[method-assign]
            return_value=make_actionable_strategy_candidate()
        )

        with pytest.raises(
            RuntimeError,
            match="execution_candidate_ingest_failed:execution_ingest_failure",
        ):
            await handler(strategy_event)

        diagnostics = runtime.execution_runtime.get_runtime_diagnostics()
        assert diagnostics["started"] is True
        assert diagnostics["ready"] is False
        assert diagnostics["lifecycle_state"] == "degraded"
        assert (
            diagnostics["last_failure_reason"] == "candidate_ingest_failed:execution_ingest_failure"
        )
        assert diagnostics["degraded_reasons"] == [
            "candidate_ingest_failed:execution_ingest_failure"
        ]

    @pytest.mark.asyncio
    async def test_strategy_event_wiring_keeps_execution_context_assembly_inside_execution_runtime(
        self,
    ) -> None:
        """Composition root должен передавать strategy truth в ExecutionRuntime, а не собирать ExecutionContext."""
        runtime = await build_production_runtime(
            settings=make_settings(),
            policy=ProductionBootstrapPolicy(
                test_mode=True,
                enable_event_bus_persistence=False,
                enable_risk_persistence=False,
                include_legacy_risk_listener=False,
            ),
        )

        runtime.execution_runtime._started = True
        runtime.execution_runtime._assemble_execution_context = Mock(  # type: ignore[attr-defined, method-assign]
            wraps=runtime.execution_runtime._assemble_execution_context  # type: ignore[attr-defined]
        )
        runtime.execution_runtime.ingest_candidate = Mock(  # type: ignore[method-assign]
            side_effect=runtime.execution_runtime.ingest_candidate
        )
        runtime.strategy_runtime.get_candidate = Mock(  # type: ignore[method-assign]
            return_value=make_actionable_strategy_candidate()
        )
        handler = runtime.event_bus.handlers[StrategyEventType.STRATEGY_ACTIONABLE.value][0]
        strategy_event = Event.new(
            StrategyEventType.STRATEGY_ACTIONABLE.value,
            "STRATEGY_RUNTIME",
            {
                "symbol": "BTC/USDT",
                "exchange": "bybit",
                "timeframe": MarketDataTimeframe.M1.value,
                "generated_at": datetime.now(UTC).isoformat(),
            },
        )

        await handler(strategy_event)

        runtime.execution_runtime.ingest_candidate.assert_called_once()
        runtime.execution_runtime._assemble_execution_context.assert_called_once()  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_execution_event_wiring_marks_opportunity_runtime_degraded_on_ingest_failure(
        self,
    ) -> None:
        """Execution-event wiring должен честно переводить opportunity runtime в degraded."""
        runtime = await build_production_runtime(
            settings=make_settings(),
            policy=ProductionBootstrapPolicy(
                test_mode=True,
                enable_event_bus_persistence=False,
                enable_risk_persistence=False,
                include_legacy_risk_listener=False,
            ),
        )

        runtime.opportunity_runtime._started = True
        runtime.opportunity_runtime.ingest_intent = Mock(  # type: ignore[method-assign]
            side_effect=RuntimeError("opportunity_ingest_failure")
        )
        handler = runtime.event_bus.handlers[ExecutionEventType.EXECUTION_REQUESTED.value][0]
        execution_event = Event.new(
            ExecutionEventType.EXECUTION_REQUESTED.value,
            "EXECUTION_RUNTIME",
            {
                "symbol": "BTC/USDT",
                "exchange": "bybit",
                "timeframe": MarketDataTimeframe.M1.value,
                "generated_at": datetime(2026, 3, 20, 12, 2, tzinfo=UTC).isoformat(),
            },
        )

        with pytest.raises(
            RuntimeError,
            match="opportunity_intent_ingest_failed:opportunity_execution_truth_missing_for_event",
        ):
            await handler(execution_event)

        runtime.execution_runtime.get_intent = Mock(  # type: ignore[method-assign]
            return_value=make_executable_execution_intent()
        )

        with pytest.raises(
            RuntimeError,
            match="opportunity_intent_ingest_failed:opportunity_ingest_failure",
        ):
            await handler(execution_event)

        diagnostics = runtime.opportunity_runtime.get_runtime_diagnostics()
        assert diagnostics["started"] is True
        assert diagnostics["ready"] is False
        assert diagnostics["lifecycle_state"] == "degraded"
        assert (
            diagnostics["last_failure_reason"] == "intent_ingest_failed:opportunity_ingest_failure"
        )
        assert diagnostics["degraded_reasons"] == [
            "intent_ingest_failed:opportunity_ingest_failure"
        ]

    @pytest.mark.asyncio
    async def test_execution_event_wiring_keeps_opportunity_context_assembly_inside_opportunity_runtime(
        self,
    ) -> None:
        """Composition root должен передавать execution truth в OpportunityRuntime, а не собирать OpportunityContext."""
        runtime = await build_production_runtime(
            settings=make_settings(),
            policy=ProductionBootstrapPolicy(
                test_mode=True,
                enable_event_bus_persistence=False,
                enable_risk_persistence=False,
                include_legacy_risk_listener=False,
            ),
        )

        runtime.opportunity_runtime._started = True
        runtime.opportunity_runtime._assemble_opportunity_context = Mock(  # type: ignore[attr-defined, method-assign]
            wraps=runtime.opportunity_runtime._assemble_opportunity_context  # type: ignore[attr-defined]
        )
        runtime.opportunity_runtime.ingest_intent = Mock(  # type: ignore[method-assign]
            side_effect=runtime.opportunity_runtime.ingest_intent
        )
        runtime.execution_runtime.get_intent = Mock(  # type: ignore[method-assign]
            return_value=make_executable_execution_intent()
        )
        handler = runtime.event_bus.handlers[ExecutionEventType.EXECUTION_REQUESTED.value][0]
        execution_event = Event.new(
            ExecutionEventType.EXECUTION_REQUESTED.value,
            "EXECUTION_RUNTIME",
            {
                "symbol": "BTC/USDT",
                "exchange": "bybit",
                "timeframe": MarketDataTimeframe.M1.value,
                "generated_at": datetime(2026, 3, 20, 12, 2, tzinfo=UTC).isoformat(),
            },
        )

        await handler(execution_event)

        runtime.opportunity_runtime.ingest_intent.assert_called_once()
        runtime.opportunity_runtime._assemble_opportunity_context.assert_called_once()  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_execution_event_wiring_marks_oms_runtime_degraded_on_ingest_failure(
        self,
    ) -> None:
        """Execution-event wiring должен честно переводить OMS runtime в degraded."""
        runtime = await build_production_runtime(
            settings=make_settings(),
            policy=ProductionBootstrapPolicy(
                test_mode=True,
                enable_event_bus_persistence=False,
                enable_risk_persistence=False,
                include_legacy_risk_listener=False,
            ),
        )

        runtime.oms_runtime._started = True
        runtime.oms_runtime.ingest_intent = Mock(  # type: ignore[method-assign]
            side_effect=RuntimeError("oms_ingest_failure")
        )
        handler = runtime.event_bus.handlers[ExecutionEventType.EXECUTION_REQUESTED.value][1]
        execution_event = Event.new(
            ExecutionEventType.EXECUTION_REQUESTED.value,
            "EXECUTION_RUNTIME",
            {
                "symbol": "BTC/USDT",
                "exchange": "bybit",
                "timeframe": MarketDataTimeframe.M1.value,
                "generated_at": datetime.now(UTC).isoformat(),
            },
        )

        with pytest.raises(
            RuntimeError,
            match="oms_intent_ingest_failed:oms_execution_truth_missing_for_event",
        ):
            await handler(execution_event)

        runtime.execution_runtime.get_intent = Mock(  # type: ignore[method-assign]
            return_value=make_executable_execution_intent()
        )

        with pytest.raises(
            RuntimeError,
            match="oms_intent_ingest_failed:oms_ingest_failure",
        ):
            await handler(execution_event)

        diagnostics = runtime.oms_runtime.get_runtime_diagnostics()
        assert diagnostics["started"] is True
        assert diagnostics["ready"] is False
        assert diagnostics["lifecycle_state"] == "degraded"
        assert diagnostics["last_failure_reason"] == "intent_ingest_failed:oms_ingest_failure"
        assert diagnostics["degraded_reasons"] == ["intent_ingest_failed:oms_ingest_failure"]

    @pytest.mark.asyncio
    async def test_execution_event_wiring_keeps_oms_context_assembly_inside_oms_runtime(
        self,
    ) -> None:
        """Composition root должен передавать execution truth в OmsRuntime, а не собирать OmsContext."""
        runtime = await build_production_runtime(
            settings=make_settings(),
            policy=ProductionBootstrapPolicy(
                test_mode=True,
                enable_event_bus_persistence=False,
                enable_risk_persistence=False,
                include_legacy_risk_listener=False,
            ),
        )

        runtime.oms_runtime._started = True
        runtime.oms_runtime._assemble_oms_context = Mock(  # type: ignore[attr-defined, method-assign]
            wraps=runtime.oms_runtime._assemble_oms_context  # type: ignore[attr-defined]
        )
        runtime.oms_runtime.ingest_intent = Mock(  # type: ignore[method-assign]
            side_effect=runtime.oms_runtime.ingest_intent
        )
        runtime.execution_runtime.get_intent = Mock(  # type: ignore[method-assign]
            return_value=make_executable_execution_intent()
        )
        handler = runtime.event_bus.handlers[ExecutionEventType.EXECUTION_REQUESTED.value][1]
        execution_event = Event.new(
            ExecutionEventType.EXECUTION_REQUESTED.value,
            "EXECUTION_RUNTIME",
            {
                "symbol": "BTC/USDT",
                "exchange": "bybit",
                "timeframe": MarketDataTimeframe.M1.value,
                "generated_at": datetime.now(UTC).isoformat(),
            },
        )

        await handler(execution_event)

        runtime.oms_runtime.ingest_intent.assert_called_once()
        runtime.oms_runtime._assemble_oms_context.assert_called_once()  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_opportunity_event_wiring_marks_orchestration_runtime_degraded_on_ingest_failure(
        self,
    ) -> None:
        """Opportunity-event wiring должен честно переводить orchestration runtime в degraded."""
        runtime = await build_production_runtime(
            settings=make_settings(),
            policy=ProductionBootstrapPolicy(
                test_mode=True,
                enable_event_bus_persistence=False,
                enable_risk_persistence=False,
                include_legacy_risk_listener=False,
            ),
        )

        runtime.orchestration_runtime._started = True
        runtime.orchestration_runtime.ingest_selection = Mock(  # type: ignore[method-assign]
            side_effect=RuntimeError("orchestration_ingest_failure")
        )
        handler = runtime.event_bus.handlers[OpportunityEventType.OPPORTUNITY_SELECTED.value][0]
        opportunity_event = Event.new(
            OpportunityEventType.OPPORTUNITY_SELECTED.value,
            "OPPORTUNITY_RUNTIME",
            {
                "symbol": "BTC/USDT",
                "exchange": "bybit",
                "timeframe": MarketDataTimeframe.M1.value,
                "generated_at": datetime.now(UTC).isoformat(),
            },
        )

        with pytest.raises(
            RuntimeError,
            match="orchestration_selection_ingest_failed:orchestration_opportunity_truth_missing_for_event",
        ):
            await handler(opportunity_event)

        runtime.opportunity_runtime.get_selection = Mock(  # type: ignore[method-assign]
            return_value=make_selected_opportunity_candidate()
        )

        with pytest.raises(
            RuntimeError,
            match="orchestration_selection_ingest_failed:orchestration_ingest_failure",
        ):
            await handler(opportunity_event)

        diagnostics = runtime.orchestration_runtime.get_runtime_diagnostics()
        assert diagnostics["started"] is True
        assert diagnostics["ready"] is False
        assert diagnostics["lifecycle_state"] == "degraded"
        assert (
            diagnostics["last_failure_reason"]
            == "selection_ingest_failed:orchestration_ingest_failure"
        )
        assert diagnostics["degraded_reasons"] == [
            "selection_ingest_failed:orchestration_ingest_failure"
        ]

    @pytest.mark.asyncio
    async def test_opportunity_event_wiring_keeps_orchestration_context_assembly_inside_orchestration_runtime(
        self,
    ) -> None:
        """Composition root должен передавать opportunity truth в OrchestrationRuntime, а не собирать OrchestrationContext."""
        runtime = await build_production_runtime(
            settings=make_settings(),
            policy=ProductionBootstrapPolicy(
                test_mode=True,
                enable_event_bus_persistence=False,
                enable_risk_persistence=False,
                include_legacy_risk_listener=False,
            ),
        )

        runtime.orchestration_runtime._started = True
        runtime.orchestration_runtime._assemble_orchestration_context = Mock(  # type: ignore[attr-defined, method-assign]
            wraps=runtime.orchestration_runtime._assemble_orchestration_context  # type: ignore[attr-defined]
        )
        runtime.orchestration_runtime.ingest_selection = Mock(  # type: ignore[method-assign]
            side_effect=runtime.orchestration_runtime.ingest_selection
        )
        runtime.opportunity_runtime.get_selection = Mock(  # type: ignore[method-assign]
            return_value=make_selected_opportunity_candidate()
        )
        handler = runtime.event_bus.handlers[OpportunityEventType.OPPORTUNITY_SELECTED.value][0]
        opportunity_event = Event.new(
            OpportunityEventType.OPPORTUNITY_SELECTED.value,
            "OPPORTUNITY_RUNTIME",
            {
                "symbol": "BTC/USDT",
                "exchange": "bybit",
                "timeframe": MarketDataTimeframe.M1.value,
                "generated_at": datetime.now(UTC).isoformat(),
            },
        )

        await handler(opportunity_event)

        runtime.orchestration_runtime.ingest_selection.assert_called_once()
        runtime.orchestration_runtime._assemble_orchestration_context.assert_called_once()  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_orchestration_event_wiring_marks_position_expansion_runtime_degraded_on_ingest_failure(
        self,
    ) -> None:
        """Orchestration-event wiring должен честно переводить position-expansion runtime в degraded."""
        runtime = await build_production_runtime(
            settings=make_settings(),
            policy=ProductionBootstrapPolicy(
                test_mode=True,
                enable_event_bus_persistence=False,
                enable_risk_persistence=False,
                include_legacy_risk_listener=False,
            ),
        )

        runtime.position_expansion_runtime._started = True
        runtime.position_expansion_runtime.ingest_decision = Mock(  # type: ignore[method-assign]
            side_effect=RuntimeError("position_expansion_ingest_failure")
        )
        handler = runtime.event_bus.handlers[OrchestrationEventType.ORCHESTRATION_DECIDED.value][0]
        orchestration_event = Event.new(
            OrchestrationEventType.ORCHESTRATION_DECIDED.value,
            "ORCHESTRATION_RUNTIME",
            {
                "symbol": "BTC/USDT",
                "exchange": "bybit",
                "timeframe": MarketDataTimeframe.M1.value,
                "generated_at": datetime.now(UTC).isoformat(),
            },
        )

        with pytest.raises(
            RuntimeError,
            match="position_expansion_decision_ingest_failed:position_expansion_orchestration_truth_missing_for_event",
        ):
            await handler(orchestration_event)

        runtime.orchestration_runtime.get_decision = Mock(  # type: ignore[method-assign]
            return_value=make_forwarded_orchestration_decision()
        )

        with pytest.raises(
            RuntimeError,
            match="position_expansion_decision_ingest_failed:position_expansion_ingest_failure",
        ):
            await handler(orchestration_event)

        diagnostics = runtime.position_expansion_runtime.get_runtime_diagnostics()
        assert diagnostics["started"] is True
        assert diagnostics["ready"] is False
        assert diagnostics["lifecycle_state"] == "degraded"
        assert (
            diagnostics["last_failure_reason"]
            == "decision_ingest_failed:position_expansion_ingest_failure"
        )
        assert diagnostics["degraded_reasons"] == [
            "decision_ingest_failed:position_expansion_ingest_failure"
        ]

    @pytest.mark.asyncio
    async def test_orchestration_event_wiring_keeps_expansion_context_assembly_inside_position_expansion_runtime(
        self,
    ) -> None:
        """Composition root должен передавать orchestration truth в PositionExpansionRuntime, а не собирать ExpansionContext."""
        runtime = await build_production_runtime(
            settings=make_settings(),
            policy=ProductionBootstrapPolicy(
                test_mode=True,
                enable_event_bus_persistence=False,
                enable_risk_persistence=False,
                include_legacy_risk_listener=False,
            ),
        )

        runtime.position_expansion_runtime._started = True
        runtime.position_expansion_runtime._assemble_expansion_context = Mock(  # type: ignore[attr-defined, method-assign]
            wraps=runtime.position_expansion_runtime._assemble_expansion_context  # type: ignore[attr-defined]
        )
        runtime.position_expansion_runtime.ingest_decision = Mock(  # type: ignore[method-assign]
            side_effect=runtime.position_expansion_runtime.ingest_decision
        )
        runtime.orchestration_runtime.get_decision = Mock(  # type: ignore[method-assign]
            return_value=make_forwarded_orchestration_decision()
        )
        handler = runtime.event_bus.handlers[OrchestrationEventType.ORCHESTRATION_DECIDED.value][0]
        orchestration_event = Event.new(
            OrchestrationEventType.ORCHESTRATION_DECIDED.value,
            "ORCHESTRATION_RUNTIME",
            {
                "symbol": "BTC/USDT",
                "exchange": "bybit",
                "timeframe": MarketDataTimeframe.M1.value,
                "generated_at": datetime.now(UTC).isoformat(),
            },
        )

        await handler(orchestration_event)

        runtime.position_expansion_runtime.ingest_decision.assert_called_once()
        runtime.position_expansion_runtime._assemble_expansion_context.assert_called_once()  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_position_expansion_event_wiring_marks_portfolio_governor_runtime_degraded_on_ingest_failure(
        self,
    ) -> None:
        """Position-expansion wiring должен честно переводить portfolio-governor runtime в degraded."""
        runtime = await build_production_runtime(
            settings=make_settings(),
            policy=ProductionBootstrapPolicy(
                test_mode=True,
                enable_event_bus_persistence=False,
                enable_risk_persistence=False,
                include_legacy_risk_listener=False,
            ),
        )

        runtime.portfolio_governor_runtime._started = True
        runtime.portfolio_governor_runtime.ingest_expansion = Mock(  # type: ignore[method-assign]
            side_effect=RuntimeError("portfolio_governor_ingest_failure")
        )
        handler = runtime.event_bus.handlers[
            PositionExpansionEventType.POSITION_EXPANSION_APPROVED.value
        ][0]
        expansion_event = Event.new(
            PositionExpansionEventType.POSITION_EXPANSION_APPROVED.value,
            "POSITION_EXPANSION_RUNTIME",
            {
                "symbol": "BTC/USDT",
                "exchange": "bybit",
                "timeframe": MarketDataTimeframe.M1.value,
                "generated_at": datetime.now(UTC).isoformat(),
            },
        )

        with pytest.raises(
            RuntimeError,
            match="portfolio_governor_expansion_ingest_failed:portfolio_governor_expansion_truth_missing_for_event",
        ):
            await handler(expansion_event)

        runtime.position_expansion_runtime.get_candidate = Mock(  # type: ignore[method-assign]
            return_value=make_expandable_position_expansion_candidate()
        )

        with pytest.raises(
            RuntimeError,
            match="portfolio_governor_expansion_ingest_failed:portfolio_governor_ingest_failure",
        ):
            await handler(expansion_event)

        diagnostics = runtime.portfolio_governor_runtime.get_runtime_diagnostics()
        assert diagnostics["started"] is True
        assert diagnostics["ready"] is False
        assert diagnostics["lifecycle_state"] == "degraded"
        assert (
            diagnostics["last_failure_reason"]
            == "expansion_ingest_failed:portfolio_governor_ingest_failure"
        )
        assert diagnostics["degraded_reasons"] == [
            "expansion_ingest_failed:portfolio_governor_ingest_failure"
        ]

    @pytest.mark.asyncio
    async def test_position_expansion_event_wiring_keeps_governor_context_assembly_inside_portfolio_governor_runtime(
        self,
    ) -> None:
        """Composition root должен передавать expansion truth в PortfolioGovernorRuntime, а не собирать GovernorContext."""
        runtime = await build_production_runtime(
            settings=make_settings(),
            policy=ProductionBootstrapPolicy(
                test_mode=True,
                enable_event_bus_persistence=False,
                enable_risk_persistence=False,
                include_legacy_risk_listener=False,
            ),
        )

        runtime.portfolio_governor_runtime._started = True
        runtime.portfolio_governor_runtime._assemble_governor_context = Mock(  # type: ignore[attr-defined, method-assign]
            wraps=runtime.portfolio_governor_runtime._assemble_governor_context  # type: ignore[attr-defined]
        )
        runtime.portfolio_governor_runtime.ingest_expansion = Mock(  # type: ignore[method-assign]
            side_effect=runtime.portfolio_governor_runtime.ingest_expansion
        )
        runtime.position_expansion_runtime.get_candidate = Mock(  # type: ignore[method-assign]
            return_value=make_expandable_position_expansion_candidate()
        )
        handler = runtime.event_bus.handlers[
            PositionExpansionEventType.POSITION_EXPANSION_APPROVED.value
        ][0]
        expansion_event = Event.new(
            PositionExpansionEventType.POSITION_EXPANSION_APPROVED.value,
            "POSITION_EXPANSION_RUNTIME",
            {
                "symbol": "BTC/USDT",
                "exchange": "bybit",
                "timeframe": MarketDataTimeframe.M1.value,
                "generated_at": datetime.now(UTC).isoformat(),
            },
        )

        await handler(expansion_event)

        runtime.portfolio_governor_runtime.ingest_expansion.assert_called_once()
        runtime.portfolio_governor_runtime._assemble_governor_context.assert_called_once()  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_portfolio_governor_event_wiring_marks_protection_runtime_degraded_on_ingest_failure(
        self,
    ) -> None:
        """Portfolio-governor wiring должен честно переводить protection runtime в degraded."""
        runtime = await build_production_runtime(
            settings=make_settings(),
            policy=ProductionBootstrapPolicy(
                test_mode=True,
                enable_event_bus_persistence=False,
                enable_risk_persistence=False,
                include_legacy_risk_listener=False,
            ),
        )

        runtime.protection_runtime._started = True
        runtime.protection_runtime.ingest_governor = Mock(  # type: ignore[method-assign]
            side_effect=RuntimeError("protection_ingest_failure")
        )
        handler = runtime.event_bus.handlers[
            PortfolioGovernorEventType.PORTFOLIO_GOVERNOR_APPROVED.value
        ][0]
        governor_event = Event.new(
            PortfolioGovernorEventType.PORTFOLIO_GOVERNOR_APPROVED.value,
            "PORTFOLIO_GOVERNOR_RUNTIME",
            {
                "symbol": "BTC/USDT",
                "exchange": "bybit",
                "timeframe": MarketDataTimeframe.M1.value,
                "generated_at": datetime.now(UTC).isoformat(),
            },
        )

        with pytest.raises(
            RuntimeError,
            match="protection_governor_ingest_failed:protection_governor_truth_missing_for_event",
        ):
            await handler(governor_event)

        runtime.portfolio_governor_runtime.get_candidate = Mock(  # type: ignore[method-assign]
            return_value=make_approved_portfolio_governor_candidate()
        )

        with pytest.raises(
            RuntimeError,
            match="protection_governor_ingest_failed:protection_ingest_failure",
        ):
            await handler(governor_event)

        diagnostics = runtime.protection_runtime.get_runtime_diagnostics()
        assert diagnostics["started"] is True
        assert diagnostics["ready"] is False
        assert diagnostics["lifecycle_state"] == "degraded"
        assert (
            diagnostics["last_failure_reason"] == "governor_ingest_failed:protection_ingest_failure"
        )
        assert diagnostics["degraded_reasons"] == [
            "governor_ingest_failed:protection_ingest_failure"
        ]

    @pytest.mark.asyncio
    async def test_portfolio_governor_event_wiring_keeps_protection_context_assembly_inside_protection_runtime(
        self,
    ) -> None:
        """Composition root должен передавать governor truth в ProtectionRuntime, а не собирать ProtectionContext."""
        runtime = await build_production_runtime(
            settings=make_settings(),
            policy=ProductionBootstrapPolicy(
                test_mode=True,
                enable_event_bus_persistence=False,
                enable_risk_persistence=False,
                include_legacy_risk_listener=False,
            ),
        )

        runtime.protection_runtime._started = True
        runtime.protection_runtime._assemble_protection_context = Mock(  # type: ignore[attr-defined, method-assign]
            wraps=runtime.protection_runtime._assemble_protection_context  # type: ignore[attr-defined]
        )
        runtime.protection_runtime.ingest_governor = Mock(  # type: ignore[method-assign]
            side_effect=runtime.protection_runtime.ingest_governor
        )
        runtime.portfolio_governor_runtime.get_candidate = Mock(  # type: ignore[method-assign]
            return_value=make_approved_portfolio_governor_candidate()
        )
        handler = runtime.event_bus.handlers[
            PortfolioGovernorEventType.PORTFOLIO_GOVERNOR_APPROVED.value
        ][0]
        governor_event = Event.new(
            PortfolioGovernorEventType.PORTFOLIO_GOVERNOR_APPROVED.value,
            "PORTFOLIO_GOVERNOR_RUNTIME",
            {
                "symbol": "BTC/USDT",
                "exchange": "bybit",
                "timeframe": MarketDataTimeframe.M1.value,
                "generated_at": datetime.now(UTC).isoformat(),
            },
        )

        await handler(governor_event)

        runtime.protection_runtime.ingest_governor.assert_called_once()
        runtime.protection_runtime._assemble_protection_context.assert_called_once()  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_portfolio_governor_candidate_event_publishes_protection_candidate_update(
        self,
    ) -> None:
        """Candidate governor truth должна публиковать узкий PROTECTION_CANDIDATE_UPDATED path."""
        runtime = await build_production_runtime(
            settings=make_settings(),
            policy=ProductionBootstrapPolicy(
                test_mode=True,
                enable_event_bus_persistence=False,
                enable_risk_persistence=False,
                include_legacy_risk_listener=False,
            ),
        )

        await runtime.protection_runtime.start()
        runtime.portfolio_governor_runtime.get_candidate = Mock(  # type: ignore[method-assign]
            return_value=make_non_approved_portfolio_governor_candidate()
        )
        captured_protection_events: list[Event] = []
        runtime.event_bus.on(
            "PROTECTION_CANDIDATE_UPDATED",
            captured_protection_events.append,
        )
        handler = runtime.event_bus.handlers[
            PortfolioGovernorEventType.PORTFOLIO_GOVERNOR_CANDIDATE_UPDATED.value
        ][0]
        governor_event = Event.new(
            PortfolioGovernorEventType.PORTFOLIO_GOVERNOR_CANDIDATE_UPDATED.value,
            "PORTFOLIO_GOVERNOR_RUNTIME",
            {
                "symbol": "BTC/USDT",
                "exchange": "bybit",
                "timeframe": MarketDataTimeframe.M1.value,
                "generated_at": datetime.now(UTC).isoformat(),
            },
        )

        await handler(governor_event)

        candidate = runtime.protection_runtime.get_candidate(
            exchange="bybit",
            symbol="BTC/USDT",
            timeframe=MarketDataTimeframe.M1,
        )
        diagnostics = runtime.protection_runtime.get_runtime_diagnostics()

        assert candidate is not None
        assert candidate.status.value == "candidate"
        assert candidate.decision.value == "protect"
        assert diagnostics["tracked_protection_keys"] == 1
        assert diagnostics["last_event_type"] == "PROTECTION_CANDIDATE_UPDATED"
        assert captured_protection_events
        assert captured_protection_events[-1].payload["status"] == "candidate"
        assert captured_protection_events[-1].payload["decision"] == "protect"
        assert captured_protection_events[-1].payload["reason_code"] == "governor_not_approved"

    @pytest.mark.asyncio
    async def test_composition_root_keeps_market_data_bar_boundary_separate_from_risk_listener(
        self,
    ) -> None:
        """Composition root не должен смешивать raw BAR_COMPLETED с risk-специфичным bar path."""
        runtime = await build_production_runtime(
            settings=make_settings(),
            policy=ProductionBootstrapPolicy(
                test_mode=True,
                enable_event_bus_persistence=False,
                enable_risk_persistence=False,
                include_legacy_risk_listener=False,
            ),
        )

        assert SystemEventType.BAR_COMPLETED in runtime.event_bus.handlers
        assert SystemEventType.BAR_COMPLETED not in runtime.risk_runtime.risk_listener.event_types
        assert SystemEventType.RISK_BAR_COMPLETED in runtime.risk_runtime.risk_listener.event_types

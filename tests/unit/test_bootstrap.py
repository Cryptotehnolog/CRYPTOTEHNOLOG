from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

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
from cryptotechnolog.manager import (
    ManagerDecision,
    ManagerEventType,
    ManagerFreshness,
    ManagerReasonCode,
    ManagerRuntimeLifecycleState,
    ManagerSource,
    ManagerStatus,
    ManagerValidity,
    ManagerValidityStatus,
    ManagerWorkflowCandidate,
)
from cryptotechnolog.market_data import MarketDataTimeframe, OHLCVBarContract
from cryptotechnolog.market_data.events import (
    BarCompletedPayload,
    MarketDataEventType,
    build_market_data_event,
)
from cryptotechnolog.oms import (
    OmsFreshness,
    OmsOrderRecord,
    OmsReasonCode,
    OmsValidity,
    OmsValidityStatus,
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
from cryptotechnolog.paper import PaperEventType, PaperRuntimeLifecycleState
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
from cryptotechnolog.protection import (
    ProtectionDecision,
    ProtectionFreshness,
    ProtectionReasonCode,
    ProtectionSource,
    ProtectionStatus,
    ProtectionSupervisorCandidate,
    ProtectionValidity,
    ProtectionValidityStatus,
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
from cryptotechnolog.validation import (
    ValidationDecision,
    ValidationEventType,
    ValidationFreshness,
    ValidationReasonCode,
    ValidationReviewCandidate,
    ValidationRuntimeLifecycleState,
    ValidationSource,
    ValidationStatus,
    ValidationValidity,
    ValidationValidityStatus,
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


def make_active_oms_order() -> OmsOrderRecord:
    now = datetime(2026, 3, 20, 12, 2, tzinfo=UTC)
    intent = make_executable_execution_intent()
    return OmsOrderRecord.registered(
        contour_name="phase16_oms_contour",
        oms_name="phase16_oms",
        symbol=intent.symbol,
        exchange=intent.exchange,
        timeframe=intent.timeframe,
        freshness=OmsFreshness(
            generated_at=now,
            expires_at=now + timedelta(minutes=5),
        ),
        validity=OmsValidity(
            status=OmsValidityStatus.VALID,
            observed_inputs=3,
            required_inputs=3,
        ),
        originating_intent_id=intent.intent_id,
        client_order_id="OID-1",
        reason_code=OmsReasonCode.ORDER_REGISTERED,
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


def make_protected_protection_candidate() -> ProtectionSupervisorCandidate:
    now = datetime(2026, 3, 20, 12, 3, tzinfo=UTC)
    governor = make_approved_portfolio_governor_candidate()
    return ProtectionSupervisorCandidate(
        protection_id=ProtectionSupervisorCandidate.candidate(
            contour_name="phase15_protection_contour",
            supervisor_name="phase15_protection",
            symbol=governor.symbol,
            exchange=governor.exchange,
            timeframe=governor.timeframe,
            source=ProtectionSource.PORTFOLIO_GOVERNOR,
            freshness=ProtectionFreshness(
                generated_at=now,
                expires_at=now.replace(minute=8),
            ),
            validity=ProtectionValidity(
                status=ProtectionValidityStatus.VALID,
                observed_inputs=1,
                required_inputs=1,
            ),
            decision=ProtectionDecision.PROTECT,
            status=ProtectionStatus.PROTECTED,
            originating_governor_id=governor.governor_id,
            confidence=Decimal("0.8"),
            priority_score=Decimal("0.8"),
            reason_code=ProtectionReasonCode.CONTEXT_READY,
        ).protection_id,
        contour_name="phase15_protection_contour",
        supervisor_name="phase15_protection",
        symbol=governor.symbol,
        exchange=governor.exchange,
        timeframe=governor.timeframe,
        source=ProtectionSource.PORTFOLIO_GOVERNOR,
        freshness=ProtectionFreshness(
            generated_at=now,
            expires_at=now.replace(minute=8),
        ),
        validity=ProtectionValidity(
            status=ProtectionValidityStatus.VALID,
            observed_inputs=1,
            required_inputs=1,
        ),
        status=ProtectionStatus.PROTECTED,
        decision=ProtectionDecision.PROTECT,
        originating_governor_id=governor.governor_id,
        confidence=Decimal("0.8"),
        priority_score=Decimal("0.8"),
        reason_code=ProtectionReasonCode.CONTEXT_READY,
    )


def make_coordinated_manager_candidate() -> ManagerWorkflowCandidate:
    now = datetime(2026, 3, 20, 12, 4, tzinfo=UTC)
    governor = make_approved_portfolio_governor_candidate()
    protection = make_protected_protection_candidate()
    return ManagerWorkflowCandidate.candidate(
        contour_name="phase17_manager_contour",
        manager_name="phase17_manager",
        symbol=protection.symbol,
        exchange=protection.exchange,
        timeframe=protection.timeframe,
        source=ManagerSource.WORKFLOW_FOUNDATIONS,
        freshness=ManagerFreshness(
            generated_at=now,
            expires_at=now.replace(minute=9),
        ),
        validity=ManagerValidity(
            status=ManagerValidityStatus.VALID,
            observed_inputs=5,
            required_inputs=5,
        ),
        decision=ManagerDecision.COORDINATE,
        status=ManagerStatus.COORDINATED,
        originating_selection_id=uuid4(),
        originating_decision_id=uuid4(),
        originating_expansion_id=governor.originating_expansion_id,
        originating_governor_id=governor.governor_id,
        originating_protection_id=protection.protection_id,
        confidence=Decimal("0.8"),
        priority_score=Decimal("0.8"),
        reason_code=ManagerReasonCode.MANAGER_COORDINATED,
    )


def make_validated_validation_candidate() -> ValidationReviewCandidate:
    now = datetime(2026, 3, 20, 12, 5, tzinfo=UTC)
    manager = make_coordinated_manager_candidate()
    governor = make_approved_portfolio_governor_candidate()
    protection = make_protected_protection_candidate()
    oms_order = make_active_oms_order()
    return ValidationReviewCandidate.candidate(
        contour_name="phase18_validation_contour",
        validation_name="phase18_validation",
        symbol=manager.symbol,
        exchange=manager.exchange,
        timeframe=manager.timeframe,
        source=ValidationSource.RUNTIME_FOUNDATIONS,
        freshness=ValidationFreshness(
            generated_at=now,
            expires_at=now.replace(minute=10),
        ),
        validity=ValidationValidity(
            status=ValidationValidityStatus.VALID,
            observed_inputs=4,
            required_inputs=4,
        ),
        decision=ValidationDecision.VALIDATE,
        status=ValidationStatus.VALIDATED,
        originating_workflow_id=manager.workflow_id,
        originating_governor_id=governor.governor_id,
        originating_protection_id=protection.protection_id,
        originating_oms_order_id=oms_order.oms_order_id,
        confidence=Decimal("0.8"),
        review_score=Decimal("1.0"),
        reason_code=ValidationReasonCode.VALIDATION_CONFIRMED,
    )


def make_invalidated_validation_candidate() -> ValidationReviewCandidate:
    now = datetime(2026, 3, 20, 12, 6, tzinfo=UTC)
    manager = make_coordinated_manager_candidate()
    governor = make_approved_portfolio_governor_candidate()
    protection = make_protected_protection_candidate()
    oms_order = make_active_oms_order()
    return ValidationReviewCandidate.candidate(
        contour_name="phase18_validation_contour",
        validation_name="phase18_validation",
        symbol=manager.symbol,
        exchange=manager.exchange,
        timeframe=manager.timeframe,
        source=ValidationSource.RUNTIME_FOUNDATIONS,
        freshness=ValidationFreshness(
            generated_at=now,
            expires_at=now.replace(minute=11),
        ),
        validity=ValidationValidity(
            status=ValidationValidityStatus.INVALID,
            observed_inputs=4,
            required_inputs=4,
            invalid_reason="validation_invalidated",
        ),
        decision=ValidationDecision.ABSTAIN,
        status=ValidationStatus.INVALIDATED,
        originating_workflow_id=manager.workflow_id,
        originating_governor_id=governor.governor_id,
        originating_protection_id=protection.protection_id,
        originating_oms_order_id=oms_order.oms_order_id,
        confidence=Decimal("0.8"),
        review_score=Decimal("1.0"),
        reason_code=ValidationReasonCode.VALIDATION_INVALIDATED,
    )


def _fake_shutdown_with_component_stop(
    runtime,
    *,
    components_stopped: list[str],
):
    async def _shutdown(*, force: bool = False) -> ShutdownResult:  # noqa: PLR0912
        _ = force
        if runtime.oms_runtime.is_started:
            await runtime.oms_runtime.stop()
        if runtime.manager_runtime.is_started:
            await runtime.manager_runtime.stop()
        if runtime.validation_runtime.is_started:
            await runtime.validation_runtime.stop()
        if runtime.paper_runtime.is_started:
            await runtime.paper_runtime.stop()
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
        assert runtime.get_runtime_diagnostics()["manager_runtime"]["started"] is False
        assert runtime.get_runtime_diagnostics()["manager_runtime"]["ready"] is False
        assert runtime.get_runtime_diagnostics()["validation_runtime"]["started"] is False
        assert runtime.get_runtime_diagnostics()["validation_runtime"]["ready"] is False
        assert runtime.get_runtime_diagnostics()["paper_runtime"]["started"] is False
        assert runtime.get_runtime_diagnostics()["paper_runtime"]["ready"] is False
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
        assert (
            runtime.controller.get_component("phase17_manager_runtime") is runtime.manager_runtime
        )
        assert (
            runtime.controller.get_component("phase18_validation_runtime")
            is runtime.validation_runtime
        )
        assert runtime.controller.get_component("phase19_paper_runtime") is runtime.paper_runtime
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
            len(runtime.event_bus.handlers[ValidationEventType.VALIDATION_CANDIDATE_UPDATED.value])
            == 1
        )
        assert (
            len(runtime.event_bus.handlers[ValidationEventType.VALIDATION_WORKFLOW_VALIDATED.value])
            == 1
        )
        assert (
            len(runtime.event_bus.handlers[ValidationEventType.VALIDATION_WORKFLOW_ABSTAINED.value])
            == 1
        )
        assert (
            len(
                runtime.event_bus.handlers[
                    ValidationEventType.VALIDATION_WORKFLOW_INVALIDATED.value
                ]
            )
            == 1
        )
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
            len(runtime.event_bus.handlers[ManagerEventType.MANAGER_CANDIDATE_UPDATED.value]) == 1
        )
        assert (
            len(runtime.event_bus.handlers[ManagerEventType.MANAGER_WORKFLOW_COORDINATED.value])
            == 1
        )
        assert (
            len(runtime.event_bus.handlers[ManagerEventType.MANAGER_WORKFLOW_ABSTAINED.value]) == 1
        )
        assert (
            len(runtime.event_bus.handlers[ManagerEventType.MANAGER_WORKFLOW_INVALIDATED.value])
            == 1
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
        assert len(runtime.event_bus.handlers["PROTECTION_CANDIDATE_UPDATED"]) == 1
        assert len(runtime.event_bus.handlers["PROTECTION_PROTECTED"]) == 1
        assert len(runtime.event_bus.handlers["PROTECTION_HALTED"]) == 1
        assert len(runtime.event_bus.handlers["PROTECTION_FROZEN"]) == 1
        assert len(runtime.event_bus.handlers["PROTECTION_INVALIDATED"]) == 1
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
        runtime.oms_runtime._started = True
        runtime.oms_runtime._refresh_diagnostics(  # type: ignore[attr-defined]
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
        runtime.manager_runtime._started = True
        runtime.manager_runtime._refresh_diagnostics(  # type: ignore[attr-defined]
            ready=True,
            lifecycle_state=ManagerRuntimeLifecycleState.READY,
            readiness_reasons=(),
            degraded_reasons=(),
        )
        runtime.validation_runtime._started = True
        runtime.validation_runtime._refresh_diagnostics(  # type: ignore[attr-defined]
            ready=True,
            lifecycle_state=ValidationRuntimeLifecycleState.READY,
            readiness_reasons=(),
            degraded_reasons=(),
        )
        runtime.paper_runtime._started = True
        runtime.paper_runtime._refresh_diagnostics(  # type: ignore[attr-defined]
            ready=True,
            lifecycle_state=PaperRuntimeLifecycleState.READY,
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
        assert diagnostics["oms_runtime"]["started"] is True
        assert diagnostics["oms_runtime"]["ready"] is True
        assert diagnostics["opportunity_runtime"]["ready"] is True
        assert diagnostics["orchestration_runtime"]["ready"] is True
        assert diagnostics["position_expansion_runtime"]["ready"] is True
        assert diagnostics["portfolio_governor_runtime"]["ready"] is True
        assert diagnostics["manager_runtime"]["started"] is True
        assert diagnostics["manager_runtime"]["ready"] is True
        assert diagnostics["validation_runtime"]["started"] is True
        assert diagnostics["validation_runtime"]["ready"] is True
        assert diagnostics["paper_runtime"]["started"] is True
        assert diagnostics["paper_runtime"]["ready"] is True

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
        runtime.oms_runtime._started = True
        runtime.oms_runtime._refresh_diagnostics(  # type: ignore[attr-defined]
            ready=False,
            lifecycle_state="warming",
            readiness_reasons=("no_execution_intent_processed",),
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
        runtime.manager_runtime._started = True
        runtime.manager_runtime._refresh_diagnostics(  # type: ignore[attr-defined]
            ready=False,
            lifecycle_state=ManagerRuntimeLifecycleState.WARMING,
            readiness_reasons=("no_manager_workflow_processed",),
            degraded_reasons=(),
        )
        runtime.validation_runtime._started = True
        runtime.validation_runtime._refresh_diagnostics(  # type: ignore[attr-defined]
            ready=False,
            lifecycle_state=ValidationRuntimeLifecycleState.WARMING,
            readiness_reasons=("no_validation_review_processed",),
            degraded_reasons=(),
        )
        runtime.paper_runtime._started = True
        runtime.paper_runtime._refresh_diagnostics(  # type: ignore[attr-defined]
            ready=False,
            lifecycle_state=PaperRuntimeLifecycleState.WARMING,
            readiness_reasons=("no_paper_rehearsal_processed",),
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
        assert diagnostics["oms_runtime"]["ready"] is False
        assert diagnostics["opportunity_runtime"]["ready"] is False
        assert diagnostics["orchestration_runtime"]["ready"] is False
        assert diagnostics["position_expansion_runtime"]["ready"] is False
        assert diagnostics["portfolio_governor_runtime"]["ready"] is False
        assert diagnostics["protection_runtime"]["ready"] is False
        assert diagnostics["manager_runtime"]["ready"] is False
        assert diagnostics["validation_runtime"]["ready"] is False
        assert diagnostics["paper_runtime"]["ready"] is False
        assert "phase16_oms:not_ready" in diagnostics["degraded_reasons"]
        assert "phase15_protection:not_ready" in diagnostics["degraded_reasons"]
        assert "phase17_manager:not_ready" in diagnostics["degraded_reasons"]
        assert "phase18_validation:not_ready" in diagnostics["degraded_reasons"]
        assert "phase19_paper:not_ready" in diagnostics["degraded_reasons"]

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
        runtime.oms_runtime._started = True
        runtime.opportunity_runtime._started = True
        runtime.orchestration_runtime._started = True
        runtime.position_expansion_runtime._started = True
        runtime.portfolio_governor_runtime._started = True
        runtime.protection_runtime._started = True
        runtime.manager_runtime._started = True
        runtime.validation_runtime._started = True
        runtime.paper_runtime._started = True

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
        runtime.oms_runtime._started = True
        runtime.oms_runtime._refresh_diagnostics(  # type: ignore[attr-defined]
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
        runtime.manager_runtime._started = True
        runtime.manager_runtime._refresh_diagnostics(  # type: ignore[attr-defined]
            ready=True,
            lifecycle_state=ManagerRuntimeLifecycleState.READY,
            readiness_reasons=(),
            degraded_reasons=(),
        )
        runtime.validation_runtime._started = True
        runtime.validation_runtime._refresh_diagnostics(  # type: ignore[attr-defined]
            ready=True,
            lifecycle_state=ValidationRuntimeLifecycleState.READY,
            readiness_reasons=(),
            degraded_reasons=(),
        )
        runtime.paper_runtime._started = True
        runtime.paper_runtime._refresh_diagnostics(  # type: ignore[attr-defined]
            ready=True,
            lifecycle_state=PaperRuntimeLifecycleState.READY,
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
        assert diagnostics["oms_runtime"]["started"] is False
        assert diagnostics["oms_runtime"]["ready"] is False
        assert diagnostics["oms_runtime"]["lifecycle_state"] == "stopped"
        assert diagnostics["oms_runtime"]["tracked_contexts"] == 0
        assert diagnostics["oms_runtime"]["tracked_active_orders"] == 0
        assert diagnostics["oms_runtime"]["tracked_historical_orders"] == 0
        assert diagnostics["oms_runtime"]["readiness_reasons"] == ["runtime_stopped"]
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
        assert diagnostics["manager_runtime"]["started"] is False
        assert diagnostics["manager_runtime"]["ready"] is False
        assert diagnostics["manager_runtime"]["lifecycle_state"] == "stopped"
        assert diagnostics["manager_runtime"]["tracked_contexts"] == 0
        assert diagnostics["manager_runtime"]["tracked_active_workflows"] == 0
        assert diagnostics["manager_runtime"]["tracked_historical_workflows"] == 0
        assert diagnostics["manager_runtime"]["readiness_reasons"] == ["runtime_stopped"]
        assert diagnostics["validation_runtime"]["started"] is False
        assert diagnostics["validation_runtime"]["ready"] is False
        assert diagnostics["validation_runtime"]["lifecycle_state"] == "stopped"
        assert diagnostics["validation_runtime"]["tracked_contexts"] == 0
        assert diagnostics["validation_runtime"]["tracked_active_reviews"] == 0
        assert diagnostics["validation_runtime"]["tracked_historical_reviews"] == 0
        assert diagnostics["validation_runtime"]["readiness_reasons"] == ["runtime_stopped"]
        assert diagnostics["paper_runtime"]["started"] is False
        assert diagnostics["paper_runtime"]["ready"] is False
        assert diagnostics["paper_runtime"]["lifecycle_state"] == "stopped"
        assert diagnostics["paper_runtime"]["tracked_contexts"] == 0
        assert diagnostics["paper_runtime"]["tracked_active_rehearsals"] == 0
        assert diagnostics["paper_runtime"]["tracked_historical_rehearsals"] == 0
        assert diagnostics["paper_runtime"]["readiness_reasons"] == ["runtime_stopped"]

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
    async def test_protection_event_wiring_marks_manager_runtime_degraded_on_ingest_failure(
        self,
    ) -> None:
        """Protection-event wiring должен честно переводить manager runtime в degraded."""
        runtime = await build_production_runtime(
            settings=make_settings(),
            policy=ProductionBootstrapPolicy(
                test_mode=True,
                enable_event_bus_persistence=False,
                enable_risk_persistence=False,
                include_legacy_risk_listener=False,
            ),
        )

        runtime.manager_runtime._started = True
        runtime.manager_runtime.ingest_truths = Mock(  # type: ignore[method-assign]
            side_effect=RuntimeError("manager_ingest_failure")
        )
        handler = runtime.event_bus.handlers["PROTECTION_PROTECTED"][0]
        protection_event = Event.new(
            "PROTECTION_PROTECTED",
            "PROTECTION_RUNTIME",
            {
                "symbol": "BTC/USDT",
                "exchange": "bybit",
                "timeframe": MarketDataTimeframe.M1.value,
                "generated_at": datetime.now(UTC).isoformat(),
            },
        )

        with pytest.raises(
            RuntimeError,
            match="manager_workflow_ingest_failed:manager_ingest_failure",
        ):
            await handler(protection_event)

        diagnostics = runtime.manager_runtime.get_runtime_diagnostics()
        assert diagnostics["started"] is True
        assert diagnostics["ready"] is False
        assert diagnostics["lifecycle_state"] == "degraded"
        assert diagnostics["last_failure_reason"] == "workflow_ingest_failed:manager_ingest_failure"
        assert diagnostics["degraded_reasons"] == ["workflow_ingest_failed:manager_ingest_failure"]

    @pytest.mark.asyncio
    async def test_protection_event_wiring_keeps_manager_context_assembly_inside_manager_runtime(
        self,
    ) -> None:
        """Composition root должен передавать workflow truths в ManagerRuntime, а не собирать ManagerContext."""
        runtime = await build_production_runtime(
            settings=make_settings(),
            policy=ProductionBootstrapPolicy(
                test_mode=True,
                enable_event_bus_persistence=False,
                enable_risk_persistence=False,
                include_legacy_risk_listener=False,
            ),
        )

        runtime.manager_runtime._started = True
        runtime.manager_runtime._assemble_manager_context = Mock(  # type: ignore[attr-defined, method-assign]
            wraps=runtime.manager_runtime._assemble_manager_context  # type: ignore[attr-defined]
        )
        runtime.manager_runtime.ingest_truths = Mock(  # type: ignore[method-assign]
            side_effect=runtime.manager_runtime.ingest_truths
        )
        runtime.opportunity_runtime.get_selection = Mock(  # type: ignore[method-assign]
            return_value=make_selected_opportunity_candidate()
        )
        runtime.orchestration_runtime.get_decision = Mock(  # type: ignore[method-assign]
            return_value=make_forwarded_orchestration_decision()
        )
        runtime.position_expansion_runtime.get_candidate = Mock(  # type: ignore[method-assign]
            return_value=make_expandable_position_expansion_candidate()
        )
        runtime.portfolio_governor_runtime.get_candidate = Mock(  # type: ignore[method-assign]
            return_value=make_approved_portfolio_governor_candidate()
        )
        runtime.protection_runtime.get_candidate = Mock(  # type: ignore[method-assign]
            return_value=make_protected_protection_candidate()
        )
        handler = runtime.event_bus.handlers["PROTECTION_PROTECTED"][0]
        protection_event = Event.new(
            "PROTECTION_PROTECTED",
            "PROTECTION_RUNTIME",
            {
                "symbol": "BTC/USDT",
                "exchange": "bybit",
                "timeframe": MarketDataTimeframe.M1.value,
                "generated_at": datetime.now(UTC).isoformat(),
            },
        )

        await handler(protection_event)

        runtime.manager_runtime.ingest_truths.assert_called_once()
        runtime.manager_runtime._assemble_manager_context.assert_called_once()  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_protection_event_publishes_manager_workflow_coordinated_update(
        self,
    ) -> None:
        """Protection truth должна публиковать узкий MANAGER_WORKFLOW_COORDINATED path."""
        runtime = await build_production_runtime(
            settings=make_settings(),
            policy=ProductionBootstrapPolicy(
                test_mode=True,
                enable_event_bus_persistence=False,
                enable_risk_persistence=False,
                include_legacy_risk_listener=False,
            ),
        )

        await runtime.manager_runtime.start()
        runtime.opportunity_runtime.get_selection = Mock(  # type: ignore[method-assign]
            return_value=make_selected_opportunity_candidate()
        )
        runtime.orchestration_runtime.get_decision = Mock(  # type: ignore[method-assign]
            return_value=make_forwarded_orchestration_decision()
        )
        runtime.position_expansion_runtime.get_candidate = Mock(  # type: ignore[method-assign]
            return_value=make_expandable_position_expansion_candidate()
        )
        runtime.portfolio_governor_runtime.get_candidate = Mock(  # type: ignore[method-assign]
            return_value=make_approved_portfolio_governor_candidate()
        )
        protection_candidate = make_protected_protection_candidate()
        runtime.protection_runtime.get_candidate = Mock(  # type: ignore[method-assign]
            return_value=protection_candidate
        )
        captured_manager_events: list[Event] = []
        runtime.event_bus.on(
            ManagerEventType.MANAGER_WORKFLOW_COORDINATED.value,
            captured_manager_events.append,
        )
        handler = runtime.event_bus.handlers["PROTECTION_PROTECTED"][0]
        protection_event = Event.new(
            "PROTECTION_PROTECTED",
            "PROTECTION_RUNTIME",
            {
                "symbol": "BTC/USDT",
                "exchange": "bybit",
                "timeframe": MarketDataTimeframe.M1.value,
                "generated_at": protection_candidate.freshness.generated_at.isoformat(),
            },
        )

        await handler(protection_event)

        candidate = runtime.manager_runtime.get_candidate(
            exchange="bybit",
            symbol="BTC/USDT",
            timeframe=MarketDataTimeframe.M1,
        )
        diagnostics = runtime.manager_runtime.get_runtime_diagnostics()

        assert candidate is not None
        assert candidate.status.value == "coordinated"
        assert candidate.decision.value == "coordinate"
        assert diagnostics["tracked_active_workflows"] == 1
        assert diagnostics["last_event_type"] == ManagerEventType.MANAGER_WORKFLOW_COORDINATED.value
        assert captured_manager_events
        assert captured_manager_events[-1].payload["status"] == "coordinated"
        assert captured_manager_events[-1].payload["decision"] == "coordinate"

    @pytest.mark.asyncio
    async def test_manager_event_wiring_marks_validation_runtime_degraded_on_ingest_failure(
        self,
    ) -> None:
        """Manager-event wiring должен честно переводить validation runtime в degraded."""
        runtime = await build_production_runtime(
            settings=make_settings(),
            policy=ProductionBootstrapPolicy(
                test_mode=True,
                enable_event_bus_persistence=False,
                enable_risk_persistence=False,
                include_legacy_risk_listener=False,
            ),
        )

        runtime.validation_runtime._started = True
        runtime.validation_runtime.ingest_truths = Mock(  # type: ignore[method-assign]
            side_effect=RuntimeError("validation_ingest_failure")
        )
        handler = runtime.event_bus.handlers[ManagerEventType.MANAGER_WORKFLOW_COORDINATED.value][0]
        manager_event = Event.new(
            ManagerEventType.MANAGER_WORKFLOW_COORDINATED.value,
            "MANAGER_RUNTIME",
            {
                "symbol": "BTC/USDT",
                "exchange": "bybit",
                "timeframe": MarketDataTimeframe.M1.value,
                "generated_at": datetime.now(UTC).isoformat(),
            },
        )

        with pytest.raises(
            RuntimeError,
            match="validation_review_ingest_failed:validation_ingest_failure",
        ):
            await handler(manager_event)

        diagnostics = runtime.validation_runtime.get_runtime_diagnostics()
        assert diagnostics["started"] is True
        assert diagnostics["ready"] is False
        assert diagnostics["lifecycle_state"] == "degraded"
        assert (
            diagnostics["last_failure_reason"] == "review_ingest_failed:validation_ingest_failure"
        )
        assert diagnostics["degraded_reasons"] == ["review_ingest_failed:validation_ingest_failure"]

    @pytest.mark.asyncio
    async def test_manager_event_wiring_keeps_validation_context_assembly_inside_validation_runtime(
        self,
    ) -> None:
        """Composition root должен передавать existing truths в ValidationRuntime, а не собирать ValidationContext."""
        runtime = await build_production_runtime(
            settings=make_settings(),
            policy=ProductionBootstrapPolicy(
                test_mode=True,
                enable_event_bus_persistence=False,
                enable_risk_persistence=False,
                include_legacy_risk_listener=False,
            ),
        )

        runtime.validation_runtime._started = True
        runtime.validation_runtime._assemble_validation_context = Mock(  # type: ignore[attr-defined, method-assign]
            wraps=runtime.validation_runtime._assemble_validation_context  # type: ignore[attr-defined]
        )
        runtime.validation_runtime.ingest_truths = Mock(  # type: ignore[method-assign]
            side_effect=runtime.validation_runtime.ingest_truths
        )
        runtime.manager_runtime.get_candidate = Mock(  # type: ignore[method-assign]
            return_value=make_coordinated_manager_candidate()
        )
        runtime.portfolio_governor_runtime.get_candidate = Mock(  # type: ignore[method-assign]
            return_value=make_approved_portfolio_governor_candidate()
        )
        runtime.protection_runtime.get_candidate = Mock(  # type: ignore[method-assign]
            return_value=make_protected_protection_candidate()
        )
        runtime.oms_runtime.list_active_orders = Mock(  # type: ignore[method-assign]
            return_value=(make_active_oms_order(),)
        )
        runtime.oms_runtime.list_historical_orders = Mock(  # type: ignore[method-assign]
            return_value=()
        )
        handler = runtime.event_bus.handlers[ManagerEventType.MANAGER_WORKFLOW_COORDINATED.value][0]
        manager_event = Event.new(
            ManagerEventType.MANAGER_WORKFLOW_COORDINATED.value,
            "MANAGER_RUNTIME",
            {
                "symbol": "BTC/USDT",
                "exchange": "bybit",
                "timeframe": MarketDataTimeframe.M1.value,
                "generated_at": datetime.now(UTC).isoformat(),
            },
        )

        await handler(manager_event)

        runtime.validation_runtime.ingest_truths.assert_called_once()
        runtime.validation_runtime._assemble_validation_context.assert_called_once()  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_manager_event_publishes_validation_review_validated_update(self) -> None:
        """Manager truth должна публиковать узкий VALIDATION_WORKFLOW_VALIDATED path."""
        runtime = await build_production_runtime(
            settings=make_settings(),
            policy=ProductionBootstrapPolicy(
                test_mode=True,
                enable_event_bus_persistence=False,
                enable_risk_persistence=False,
                include_legacy_risk_listener=False,
            ),
        )

        await runtime.validation_runtime.start()
        runtime.manager_runtime.get_candidate = Mock(  # type: ignore[method-assign]
            return_value=make_coordinated_manager_candidate()
        )
        runtime.portfolio_governor_runtime.get_candidate = Mock(  # type: ignore[method-assign]
            return_value=make_approved_portfolio_governor_candidate()
        )
        runtime.protection_runtime.get_candidate = Mock(  # type: ignore[method-assign]
            return_value=make_protected_protection_candidate()
        )
        runtime.oms_runtime.list_active_orders = Mock(  # type: ignore[method-assign]
            return_value=(make_active_oms_order(),)
        )
        runtime.oms_runtime.list_historical_orders = Mock(  # type: ignore[method-assign]
            return_value=()
        )
        captured_validation_events: list[Event] = []
        runtime.event_bus.on(
            ValidationEventType.VALIDATION_WORKFLOW_VALIDATED.value,
            captured_validation_events.append,
        )
        handler = runtime.event_bus.handlers[ManagerEventType.MANAGER_WORKFLOW_COORDINATED.value][0]
        manager_candidate = make_coordinated_manager_candidate()
        manager_event = Event.new(
            ManagerEventType.MANAGER_WORKFLOW_COORDINATED.value,
            "MANAGER_RUNTIME",
            {
                "symbol": "BTC/USDT",
                "exchange": "bybit",
                "timeframe": MarketDataTimeframe.M1.value,
                "generated_at": manager_candidate.freshness.generated_at.isoformat(),
            },
        )

        await handler(manager_event)

        candidate = runtime.validation_runtime.get_candidate(
            exchange="bybit",
            symbol="BTC/USDT",
            timeframe=MarketDataTimeframe.M1,
        )
        diagnostics = runtime.validation_runtime.get_runtime_diagnostics()

        assert candidate is not None
        assert candidate.status.value == "validated"
        assert candidate.decision.value == "validate"
        assert diagnostics["tracked_active_reviews"] == 1
        assert (
            diagnostics["last_event_type"]
            == ValidationEventType.VALIDATION_WORKFLOW_VALIDATED.value
        )
        assert captured_validation_events
        assert captured_validation_events[-1].payload["status"] == "validated"
        assert captured_validation_events[-1].payload["decision"] == "validate"

    @pytest.mark.asyncio
    async def test_validation_event_wiring_marks_paper_runtime_degraded_on_ingest_failure(
        self,
    ) -> None:
        """Validation-event wiring должен честно переводить paper runtime в degraded."""
        runtime = await build_production_runtime(
            settings=make_settings(),
            policy=ProductionBootstrapPolicy(
                test_mode=True,
                enable_event_bus_persistence=False,
                enable_risk_persistence=False,
                include_legacy_risk_listener=False,
            ),
        )

        runtime.paper_runtime._started = True
        runtime.paper_runtime.ingest_truths = Mock(  # type: ignore[method-assign]
            side_effect=RuntimeError("paper_ingest_failure")
        )
        handler = runtime.event_bus.handlers[
            ValidationEventType.VALIDATION_WORKFLOW_VALIDATED.value
        ][0]
        validation_event = Event.new(
            ValidationEventType.VALIDATION_WORKFLOW_VALIDATED.value,
            "VALIDATION_RUNTIME",
            {
                "symbol": "BTC/USDT",
                "exchange": "bybit",
                "timeframe": MarketDataTimeframe.M1.value,
                "generated_at": datetime.now(UTC).isoformat(),
            },
        )

        with pytest.raises(
            RuntimeError,
            match="paper_rehearsal_ingest_failed:paper_ingest_failure",
        ):
            await handler(validation_event)

        diagnostics = runtime.paper_runtime.get_runtime_diagnostics()
        assert diagnostics["started"] is True
        assert diagnostics["ready"] is False
        assert diagnostics["lifecycle_state"] == "degraded"
        assert diagnostics["last_failure_reason"] == "rehearsal_ingest_failed:paper_ingest_failure"
        assert diagnostics["degraded_reasons"] == ["rehearsal_ingest_failed:paper_ingest_failure"]

    @pytest.mark.asyncio
    async def test_validation_event_wiring_keeps_paper_context_assembly_inside_paper_runtime(
        self,
    ) -> None:
        """Composition root должен передавать truths в PaperRuntime, а не собирать PaperContext."""
        runtime = await build_production_runtime(
            settings=make_settings(),
            policy=ProductionBootstrapPolicy(
                test_mode=True,
                enable_event_bus_persistence=False,
                enable_risk_persistence=False,
                include_legacy_risk_listener=False,
            ),
        )

        runtime.paper_runtime._started = True
        runtime.paper_runtime._assemble_paper_context = Mock(  # type: ignore[attr-defined, method-assign]
            wraps=runtime.paper_runtime._assemble_paper_context  # type: ignore[attr-defined]
        )
        runtime.paper_runtime.ingest_truths = Mock(  # type: ignore[method-assign]
            side_effect=runtime.paper_runtime.ingest_truths
        )
        runtime.validation_runtime.get_candidate = Mock(  # type: ignore[method-assign]
            return_value=make_validated_validation_candidate()
        )
        runtime.manager_runtime.get_candidate = Mock(  # type: ignore[method-assign]
            return_value=make_coordinated_manager_candidate()
        )
        runtime.oms_runtime.list_active_orders = Mock(  # type: ignore[method-assign]
            return_value=(make_active_oms_order(),)
        )
        runtime.oms_runtime.list_historical_orders = Mock(  # type: ignore[method-assign]
            return_value=()
        )
        handler = runtime.event_bus.handlers[
            ValidationEventType.VALIDATION_WORKFLOW_VALIDATED.value
        ][0]
        validation_candidate = make_validated_validation_candidate()
        validation_event = Event.new(
            ValidationEventType.VALIDATION_WORKFLOW_VALIDATED.value,
            "VALIDATION_RUNTIME",
            {
                "symbol": "BTC/USDT",
                "exchange": "bybit",
                "timeframe": MarketDataTimeframe.M1.value,
                "generated_at": validation_candidate.freshness.generated_at.isoformat(),
            },
        )

        await handler(validation_event)

        runtime.paper_runtime.ingest_truths.assert_called_once()
        runtime.paper_runtime._assemble_paper_context.assert_called_once()  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_validation_event_publishes_paper_rehearsal_rehearsed_update(self) -> None:
        """Validation truth должна публиковать узкий PAPER_REHEARSAL_REHEARSED path."""
        runtime = await build_production_runtime(
            settings=make_settings(),
            policy=ProductionBootstrapPolicy(
                test_mode=True,
                enable_event_bus_persistence=False,
                enable_risk_persistence=False,
                include_legacy_risk_listener=False,
            ),
        )

        await runtime.paper_runtime.start()
        runtime.validation_runtime.get_candidate = Mock(  # type: ignore[method-assign]
            return_value=make_validated_validation_candidate()
        )
        runtime.manager_runtime.get_candidate = Mock(  # type: ignore[method-assign]
            return_value=make_coordinated_manager_candidate()
        )
        runtime.oms_runtime.list_active_orders = Mock(  # type: ignore[method-assign]
            return_value=(make_active_oms_order(),)
        )
        runtime.oms_runtime.list_historical_orders = Mock(  # type: ignore[method-assign]
            return_value=()
        )
        captured_paper_events: list[Event] = []
        runtime.event_bus.on(
            PaperEventType.PAPER_REHEARSAL_REHEARSED.value,
            captured_paper_events.append,
        )
        handler = runtime.event_bus.handlers[
            ValidationEventType.VALIDATION_WORKFLOW_VALIDATED.value
        ][0]
        validation_candidate = make_validated_validation_candidate()
        validation_event = Event.new(
            ValidationEventType.VALIDATION_WORKFLOW_VALIDATED.value,
            "VALIDATION_RUNTIME",
            {
                "symbol": "BTC/USDT",
                "exchange": "bybit",
                "timeframe": MarketDataTimeframe.M1.value,
                "generated_at": validation_candidate.freshness.generated_at.isoformat(),
            },
        )

        await handler(validation_event)

        candidate = runtime.paper_runtime.get_candidate((
            "BTC/USDT",
            "bybit",
            MarketDataTimeframe.M1,
        ))
        diagnostics = runtime.paper_runtime.get_runtime_diagnostics()

        assert candidate is not None
        assert candidate.status.value == "rehearsed"
        assert candidate.decision.value == "rehearse"
        assert diagnostics["tracked_active_rehearsals"] == 1
        assert diagnostics["last_event_type"] == PaperEventType.PAPER_REHEARSAL_REHEARSED.value
        assert captured_paper_events
        assert captured_paper_events[-1].payload["status"] == "rehearsed"
        assert captured_paper_events[-1].payload["decision"] == "rehearse"

    @pytest.mark.asyncio
    async def test_validation_invalidated_event_publishes_paper_rehearsal_invalidated_update(
        self,
    ) -> None:
        """Historical validation invalidation должна публиковать узкий PAPER_REHEARSAL_INVALIDATED path."""
        runtime = await build_production_runtime(
            settings=make_settings(),
            policy=ProductionBootstrapPolicy(
                test_mode=True,
                enable_event_bus_persistence=False,
                enable_risk_persistence=False,
                include_legacy_risk_listener=False,
            ),
        )

        await runtime.paper_runtime.start()
        runtime.validation_runtime.get_candidate = Mock(  # type: ignore[method-assign]
            return_value=make_validated_validation_candidate()
        )
        runtime.validation_runtime.get_historical_candidate = Mock(  # type: ignore[method-assign]
            return_value=None
        )
        runtime.manager_runtime.get_candidate = Mock(  # type: ignore[method-assign]
            return_value=make_coordinated_manager_candidate()
        )
        runtime.manager_runtime.get_historical_candidate = Mock(  # type: ignore[method-assign]
            return_value=None
        )
        runtime.oms_runtime.list_active_orders = Mock(  # type: ignore[method-assign]
            return_value=(make_active_oms_order(),)
        )
        runtime.oms_runtime.list_historical_orders = Mock(  # type: ignore[method-assign]
            return_value=()
        )
        rehearsed_handler = runtime.event_bus.handlers[
            ValidationEventType.VALIDATION_WORKFLOW_VALIDATED.value
        ][0]
        rehearsed_validation = make_validated_validation_candidate()
        rehearsed_event = Event.new(
            ValidationEventType.VALIDATION_WORKFLOW_VALIDATED.value,
            "VALIDATION_RUNTIME",
            {
                "symbol": "BTC/USDT",
                "exchange": "bybit",
                "timeframe": MarketDataTimeframe.M1.value,
                "generated_at": rehearsed_validation.freshness.generated_at.isoformat(),
            },
        )

        await rehearsed_handler(rehearsed_event)

        invalidated_validation = make_invalidated_validation_candidate()
        runtime.validation_runtime.get_candidate = Mock(  # type: ignore[method-assign]
            return_value=None
        )
        runtime.validation_runtime.get_historical_candidate = Mock(  # type: ignore[method-assign]
            return_value=invalidated_validation
        )
        captured_paper_events: list[Event] = []
        runtime.event_bus.on(
            PaperEventType.PAPER_REHEARSAL_INVALIDATED.value,
            captured_paper_events.append,
        )
        invalidated_handler = runtime.event_bus.handlers[
            ValidationEventType.VALIDATION_WORKFLOW_INVALIDATED.value
        ][0]
        invalidated_event = Event.new(
            ValidationEventType.VALIDATION_WORKFLOW_INVALIDATED.value,
            "VALIDATION_RUNTIME",
            {
                "symbol": "BTC/USDT",
                "exchange": "bybit",
                "timeframe": MarketDataTimeframe.M1.value,
                "generated_at": invalidated_validation.freshness.generated_at.isoformat(),
            },
        )

        await invalidated_handler(invalidated_event)

        key = ("BTC/USDT", "bybit", MarketDataTimeframe.M1)
        candidate = runtime.paper_runtime.get_candidate(key)
        historical = runtime.paper_runtime.get_historical_candidate(key)
        diagnostics = runtime.paper_runtime.get_runtime_diagnostics()

        assert candidate is None
        assert historical is not None
        assert historical.status.value == "invalidated"
        assert historical.decision.value == "abstain"
        assert diagnostics["tracked_active_rehearsals"] == 0
        assert diagnostics["tracked_historical_rehearsals"] == 1
        assert diagnostics["last_event_type"] == PaperEventType.PAPER_REHEARSAL_INVALIDATED.value
        assert captured_paper_events
        assert captured_paper_events[-1].payload["status"] == "invalidated"
        assert captured_paper_events[-1].payload["decision"] == "abstain"

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

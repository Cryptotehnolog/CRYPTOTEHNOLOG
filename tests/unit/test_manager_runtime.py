from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from cryptotechnolog.execution import (
    ExecutionDirection,
    ExecutionFreshness,
    ExecutionOrderIntent,
    ExecutionReasonCode,
    ExecutionValidity,
    ExecutionValidityStatus,
)
from cryptotechnolog.manager import (
    ManagerDecision,
    ManagerEventType,
    ManagerRuntimeLifecycleState,
    ManagerStatus,
    create_manager_runtime,
)
from cryptotechnolog.market_data import MarketDataTimeframe
from cryptotechnolog.opportunity import (
    OpportunityDirection,
    OpportunityFreshness,
    OpportunityReasonCode,
    OpportunitySelectionCandidate,
    OpportunitySource,
    OpportunityValidity,
    OpportunityValidityStatus,
)
from cryptotechnolog.orchestration import (
    OrchestrationDecision,
    OrchestrationDecisionCandidate,
    OrchestrationFreshness,
    OrchestrationReasonCode,
    OrchestrationSource,
    OrchestrationStatus,
    OrchestrationValidity,
    OrchestrationValidityStatus,
)
from cryptotechnolog.portfolio_governor import (
    GovernorDecision,
    GovernorFreshness,
    GovernorReasonCode,
    GovernorSource,
    GovernorStatus,
    GovernorValidity,
    GovernorValidityStatus,
    PortfolioGovernorCandidate,
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


def _now() -> datetime:
    return datetime(2026, 3, 23, 12, 0, tzinfo=UTC)


def _execution_intent() -> ExecutionOrderIntent:
    current_time = _now()
    return ExecutionOrderIntent.candidate(
        contour_name="phase10_execution_contour",
        execution_name="phase10_execution",
        symbol="BTCUSDT",
        exchange="BINANCE",
        timeframe=MarketDataTimeframe.M15,
        freshness=ExecutionFreshness(
            generated_at=current_time,
            expires_at=current_time + timedelta(minutes=20),
        ),
        validity=ExecutionValidity(
            status=ExecutionValidityStatus.VALID,
            observed_inputs=3,
            required_inputs=3,
        ),
        direction=ExecutionDirection.BUY,
        originating_candidate_id=uuid4(),
        confidence=Decimal("0.90"),
        reason_code=ExecutionReasonCode.CONTEXT_READY,
    )


def _selection() -> OpportunitySelectionCandidate:
    intent = _execution_intent()
    current_time = _now()
    return OpportunitySelectionCandidate.candidate(
        contour_name="phase11_opportunity_contour",
        selection_name="phase11_opportunity",
        symbol=intent.symbol,
        exchange=intent.exchange,
        timeframe=intent.timeframe,
        source=OpportunitySource.EXECUTION_INTENT,
        freshness=OpportunityFreshness(
            generated_at=current_time,
            expires_at=current_time + timedelta(minutes=15),
        ),
        validity=OpportunityValidity(
            status=OpportunityValidityStatus.VALID,
            observed_inputs=2,
            required_inputs=2,
        ),
        direction=OpportunityDirection.LONG,
        originating_intent_id=intent.intent_id,
        confidence=Decimal("0.80"),
        priority_score=Decimal("0.60"),
        reason_code=OpportunityReasonCode.CONTEXT_READY,
    )


def _orchestration() -> OrchestrationDecisionCandidate:
    selection = _selection()
    current_time = _now()
    return OrchestrationDecisionCandidate.candidate(
        contour_name="phase12_orchestration_contour",
        orchestration_name="phase12_orchestration",
        symbol=selection.symbol,
        exchange=selection.exchange,
        timeframe=selection.timeframe,
        source=OrchestrationSource.OPPORTUNITY_SELECTION,
        freshness=OrchestrationFreshness(
            generated_at=current_time,
            expires_at=current_time + timedelta(minutes=14),
        ),
        validity=OrchestrationValidity(
            status=OrchestrationValidityStatus.VALID,
            observed_inputs=2,
            required_inputs=2,
        ),
        decision=OrchestrationDecision.FORWARD,
        status=OrchestrationStatus.ORCHESTRATED,
        direction=selection.direction,
        originating_selection_id=selection.selection_id,
        confidence=Decimal("0.81"),
        priority_score=Decimal("0.61"),
        reason_code=OrchestrationReasonCode.CONTEXT_READY,
    )


def _expansion() -> PositionExpansionCandidate:
    decision = _orchestration()
    current_time = _now()
    return PositionExpansionCandidate.candidate(
        contour_name="phase13_expansion_contour",
        expansion_name="phase13_expansion",
        symbol=decision.symbol,
        exchange=decision.exchange,
        timeframe=decision.timeframe,
        source=ExpansionSource.ORCHESTRATION_DECISION,
        freshness=ExpansionFreshness(
            generated_at=current_time,
            expires_at=current_time + timedelta(minutes=13),
        ),
        validity=ExpansionValidity(
            status=ExpansionValidityStatus.VALID,
            observed_inputs=2,
            required_inputs=2,
        ),
        decision=ExpansionDecision.ADD,
        status=ExpansionStatus.EXPANDABLE,
        direction=ExpansionDirection.LONG,
        originating_decision_id=decision.decision_id,
        confidence=Decimal("0.82"),
        priority_score=Decimal("0.62"),
        reason_code=ExpansionReasonCode.CONTEXT_READY,
    )


def _governor() -> PortfolioGovernorCandidate:
    expansion = _expansion()
    current_time = _now()
    return PortfolioGovernorCandidate.candidate(
        contour_name="phase14_governor_contour",
        governor_name="phase14_governor",
        symbol=expansion.symbol,
        exchange=expansion.exchange,
        timeframe=expansion.timeframe,
        source=GovernorSource.POSITION_EXPANSION,
        freshness=GovernorFreshness(
            generated_at=current_time,
            expires_at=current_time + timedelta(minutes=12),
        ),
        validity=GovernorValidity(
            status=GovernorValidityStatus.VALID,
            observed_inputs=2,
            required_inputs=2,
        ),
        decision=GovernorDecision.APPROVE,
        status=GovernorStatus.APPROVED,
        direction=expansion.direction,
        originating_expansion_id=expansion.expansion_id,
        confidence=Decimal("0.83"),
        priority_score=Decimal("0.63"),
        capital_fraction=Decimal("0.25"),
        reason_code=GovernorReasonCode.CONTEXT_READY,
    )


def _protection(
    status: ProtectionStatus = ProtectionStatus.PROTECTED,
) -> ProtectionSupervisorCandidate:
    governor = _governor()
    current_time = _now()
    decision = (
        ProtectionDecision.PROTECT
        if status == ProtectionStatus.PROTECTED
        else ProtectionDecision.HALT
        if status == ProtectionStatus.HALTED
        else ProtectionDecision.FREEZE
    )
    return ProtectionSupervisorCandidate.candidate(
        contour_name="phase15_protection_contour",
        supervisor_name="phase15_protection",
        symbol=governor.symbol,
        exchange=governor.exchange,
        timeframe=governor.timeframe,
        source=ProtectionSource.PORTFOLIO_GOVERNOR,
        freshness=ProtectionFreshness(
            generated_at=current_time,
            expires_at=current_time + timedelta(minutes=11),
        ),
        validity=ProtectionValidity(
            status=ProtectionValidityStatus.VALID,
            observed_inputs=2,
            required_inputs=2,
        ),
        decision=decision,
        status=status,
        originating_governor_id=governor.governor_id,
        confidence=Decimal("0.84"),
        priority_score=Decimal("0.64"),
        reason_code=ProtectionReasonCode.CONTEXT_READY,
    )


@pytest.mark.asyncio
async def test_manager_runtime_starts_and_stops_explicitly() -> None:
    runtime = create_manager_runtime()

    assert runtime.is_started is False

    await runtime.start()
    started = runtime.get_runtime_diagnostics()
    assert started["started"] is True
    assert started["lifecycle_state"] == ManagerRuntimeLifecycleState.WARMING.value

    await runtime.stop()
    stopped = runtime.get_runtime_diagnostics()
    assert stopped["started"] is False
    assert stopped["lifecycle_state"] == ManagerRuntimeLifecycleState.STOPPED.value
    assert stopped["tracked_active_workflows"] == 0


@pytest.mark.asyncio
async def test_manager_runtime_builds_coordinated_candidate_from_valid_truths() -> None:
    runtime = create_manager_runtime()
    await runtime.start()

    update = runtime.ingest_truths(
        opportunity=_selection(),
        orchestration=_orchestration(),
        expansion=_expansion(),
        governor=_governor(),
        protection=_protection(),
        reference_time=_now(),
    )

    assert update.context is not None
    assert update.context.validity.is_valid is True
    assert update.workflow_candidate is not None
    assert update.workflow_candidate.status == ManagerStatus.COORDINATED
    assert update.workflow_candidate.decision == ManagerDecision.COORDINATE
    assert update.event_type == ManagerEventType.MANAGER_WORKFLOW_COORDINATED

    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["ready"] is True
    assert diagnostics["tracked_active_workflows"] == 1


@pytest.mark.asyncio
async def test_manager_runtime_abstains_when_protection_is_halted() -> None:
    runtime = create_manager_runtime()
    await runtime.start()

    update = runtime.ingest_truths(
        opportunity=_selection(),
        orchestration=_orchestration(),
        expansion=_expansion(),
        governor=_governor(),
        protection=_protection(ProtectionStatus.HALTED),
        reference_time=_now(),
    )

    assert update.workflow_candidate is not None
    assert update.workflow_candidate.status == ManagerStatus.ABSTAINED
    assert update.workflow_candidate.decision == ManagerDecision.ABSTAIN
    assert update.event_type == ManagerEventType.MANAGER_WORKFLOW_ABSTAINED


@pytest.mark.asyncio
async def test_manager_runtime_handles_missing_inputs_without_hidden_bootstrap() -> None:
    runtime = create_manager_runtime()
    await runtime.start()

    update = runtime.ingest_truths(
        opportunity=_selection(),
        orchestration=_orchestration(),
        expansion=_expansion(),
        governor=_governor(),
        protection=None,
        reference_time=_now(),
    )

    assert update.context is None
    assert update.workflow_candidate is None
    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["ready"] is False
    assert "protection" in diagnostics["readiness_reasons"]


@pytest.mark.asyncio
async def test_manager_runtime_invalidates_existing_workflow_when_chain_becomes_invalid() -> None:
    runtime = create_manager_runtime()
    await runtime.start()
    runtime.ingest_truths(
        opportunity=_selection(),
        orchestration=_orchestration(),
        expansion=_expansion(),
        governor=_governor(),
        protection=_protection(),
        reference_time=_now(),
    )

    invalid_protection = ProtectionSupervisorCandidate.candidate(
        contour_name="phase15_protection_contour",
        supervisor_name="phase15_protection",
        symbol="BTCUSDT",
        exchange="BINANCE",
        timeframe=MarketDataTimeframe.M15,
        source=ProtectionSource.PORTFOLIO_GOVERNOR,
        freshness=ProtectionFreshness(
            generated_at=_now(),
            expires_at=_now() + timedelta(minutes=5),
        ),
        validity=ProtectionValidity(
            status=ProtectionValidityStatus.INVALID,
            observed_inputs=2,
            required_inputs=2,
            invalid_reason="protection_invalidated",
        ),
        decision=ProtectionDecision.PROTECT,
        status=ProtectionStatus.INVALIDATED,
        originating_governor_id=_governor().governor_id,
        reason_code=ProtectionReasonCode.PROTECTION_INVALIDATED,
    )

    update = runtime.ingest_truths(
        opportunity=_selection(),
        orchestration=_orchestration(),
        expansion=_expansion(),
        governor=_governor(),
        protection=invalid_protection,
        reference_time=_now(),
    )

    assert update.workflow_candidate is not None
    assert update.workflow_candidate.status == ManagerStatus.INVALIDATED
    assert update.event_type == ManagerEventType.MANAGER_WORKFLOW_INVALIDATED
    assert len(runtime.list_historical_candidates()) == 1


@pytest.mark.asyncio
async def test_manager_runtime_expires_active_workflow_into_historical_registry() -> None:
    runtime = create_manager_runtime()
    await runtime.start()
    reference_time = _now()
    update = runtime.ingest_truths(
        opportunity=_selection(),
        orchestration=_orchestration(),
        expansion=_expansion(),
        governor=_governor(),
        protection=_protection(),
        reference_time=reference_time,
    )

    assert update.workflow_candidate is not None

    expired = runtime.expire_candidates(reference_time=reference_time + timedelta(minutes=30))

    assert len(expired) == 1
    assert expired[0].status == ManagerStatus.EXPIRED
    assert runtime.list_active_candidates() == ()
    assert len(runtime.list_historical_candidates()) == 1

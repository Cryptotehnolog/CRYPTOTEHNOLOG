from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from cryptotechnolog.execution import (
    ExecutionDirection,
    ExecutionFreshness,
    ExecutionOrderIntent,
    ExecutionValidity,
    ExecutionValidityStatus,
)
from cryptotechnolog.manager import (
    ManagerContext,
    ManagerDecision,
    ManagerEventType,
    ManagerFreshness,
    ManagerReasonCode,
    ManagerRuntimeConfig,
    ManagerSource,
    ManagerStatus,
    ManagerValidity,
    ManagerValidityStatus,
    ManagerWorkflowCandidate,
    ManagerWorkflowPayload,
    build_manager_event,
    create_manager_runtime,
    default_priority_for_manager_event,
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
            expires_at=current_time + timedelta(minutes=15),
        ),
        validity=ExecutionValidity(
            status=ExecutionValidityStatus.VALID,
            observed_inputs=3,
            required_inputs=3,
        ),
        direction=ExecutionDirection.BUY,
        originating_candidate_id=uuid4(),
        confidence=Decimal("0.90"),
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
            expires_at=current_time + timedelta(minutes=10),
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
            expires_at=current_time + timedelta(minutes=10),
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
            expires_at=current_time + timedelta(minutes=10),
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
            expires_at=current_time + timedelta(minutes=10),
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


def _protection() -> ProtectionSupervisorCandidate:
    governor = _governor()
    current_time = _now()
    return ProtectionSupervisorCandidate.candidate(
        contour_name="phase15_protection_contour",
        supervisor_name="phase15_protection",
        symbol=governor.symbol,
        exchange=governor.exchange,
        timeframe=governor.timeframe,
        source=ProtectionSource.PORTFOLIO_GOVERNOR,
        freshness=ProtectionFreshness(
            generated_at=current_time,
            expires_at=current_time + timedelta(minutes=10),
        ),
        validity=ProtectionValidity(
            status=ProtectionValidityStatus.VALID,
            observed_inputs=2,
            required_inputs=2,
        ),
        decision=ProtectionDecision.PROTECT,
        status=ProtectionStatus.PROTECTED,
        originating_governor_id=governor.governor_id,
        confidence=Decimal("0.84"),
        priority_score=Decimal("0.64"),
        reason_code=ProtectionReasonCode.CONTEXT_READY,
    )


def _context(validity: ManagerValidity | None = None) -> ManagerContext:
    protection = _protection()
    return ManagerContext(
        manager_name="phase17_manager",
        contour_name="phase17_manager_contour",
        symbol=protection.symbol,
        exchange=protection.exchange,
        timeframe=protection.timeframe,
        observed_at=_now(),
        source=ManagerSource.WORKFLOW_FOUNDATIONS,
        opportunity=_selection(),
        orchestration=_orchestration(),
        expansion=_expansion(),
        governor=_governor(),
        protection=protection,
        validity=validity
        or ManagerValidity(
            status=ManagerValidityStatus.VALID,
            observed_inputs=5,
            required_inputs=5,
        ),
    )


def test_manager_validity_readiness_ratio_is_normalized() -> None:
    validity = ManagerValidity(
        status=ManagerValidityStatus.WARMING,
        observed_inputs=2,
        required_inputs=5,
        missing_inputs=("protection", "governor", "expansion"),
    )

    assert validity.readiness_ratio == Decimal("0.4000")
    assert validity.is_warming is True
    assert validity.missing_inputs_count == 3


def test_valid_manager_context_requires_explicit_protection_candidate() -> None:
    current_time = _now()
    governor = _governor()
    invalid_protection = ProtectionSupervisorCandidate.candidate(
        contour_name="phase15_protection_contour",
        supervisor_name="phase15_protection",
        symbol=governor.symbol,
        exchange=governor.exchange,
        timeframe=governor.timeframe,
        source=ProtectionSource.PORTFOLIO_GOVERNOR,
        freshness=ProtectionFreshness(
            generated_at=current_time,
            expires_at=current_time + timedelta(minutes=10),
        ),
        validity=ProtectionValidity(
            status=ProtectionValidityStatus.VALID,
            observed_inputs=2,
            required_inputs=2,
        ),
        decision=ProtectionDecision.PROTECT,
        status=ProtectionStatus.CANDIDATE,
        confidence=Decimal("0.84"),
        priority_score=Decimal("0.64"),
        reason_code=ProtectionReasonCode.CONTEXT_READY,
    )

    with pytest.raises(
        ValueError,
        match="VALID ManagerContext требует explicit protection supervisory candidate",
    ):
        ManagerContext(
            manager_name="phase17_manager",
            contour_name="phase17_manager_contour",
            symbol=invalid_protection.symbol,
            exchange=invalid_protection.exchange,
            timeframe=invalid_protection.timeframe,
            observed_at=current_time,
            source=ManagerSource.WORKFLOW_FOUNDATIONS,
            opportunity=_selection(),
            orchestration=_orchestration(),
            expansion=_expansion(),
            governor=governor,
            protection=invalid_protection,
            validity=ManagerValidity(
                status=ManagerValidityStatus.VALID,
                observed_inputs=5,
                required_inputs=5,
            ),
        )


def test_coordinated_manager_candidate_requires_full_upstream_chain() -> None:
    context = _context()

    with pytest.raises(
        ValueError,
        match="COORDINATED candidate обязан ссылаться на upstream workflow chain",
    ):
        ManagerWorkflowCandidate.candidate(
            contour_name=context.contour_name,
            manager_name=context.manager_name,
            symbol=context.symbol,
            exchange=context.exchange,
            timeframe=context.timeframe,
            source=context.source,
            freshness=ManagerFreshness(
                generated_at=_now(),
                expires_at=_now() + timedelta(minutes=10),
            ),
            validity=context.validity,
            decision=ManagerDecision.COORDINATE,
            status=ManagerStatus.COORDINATED,
            originating_selection_id=context.opportunity.selection_id,
            originating_decision_id=context.orchestration.decision_id,
            originating_expansion_id=context.expansion.expansion_id,
            originating_governor_id=context.governor.governor_id,
            reason_code=ManagerReasonCode.MANAGER_COORDINATED,
        )


def test_manager_candidate_exposes_narrow_coordination_truth() -> None:
    context = _context()
    candidate = ManagerWorkflowCandidate.candidate(
        contour_name=context.contour_name,
        manager_name=context.manager_name,
        symbol=context.symbol,
        exchange=context.exchange,
        timeframe=context.timeframe,
        source=context.source,
        freshness=ManagerFreshness(
            generated_at=_now(),
            expires_at=_now() + timedelta(minutes=10),
        ),
        validity=context.validity,
        decision=ManagerDecision.COORDINATE,
        status=ManagerStatus.COORDINATED,
        originating_selection_id=context.opportunity.selection_id,
        originating_decision_id=context.orchestration.decision_id,
        originating_expansion_id=context.expansion.expansion_id,
        originating_governor_id=context.governor.governor_id,
        originating_protection_id=context.protection.protection_id,
        confidence=Decimal("0.85"),
        priority_score=Decimal("0.65"),
        reason_code=ManagerReasonCode.MANAGER_COORDINATED,
    )

    assert candidate.is_coordinated is True
    assert candidate.is_abstained is False


def test_manager_event_payload_remains_narrow() -> None:
    context = _context()
    candidate = ManagerWorkflowCandidate.candidate(
        contour_name=context.contour_name,
        manager_name=context.manager_name,
        symbol=context.symbol,
        exchange=context.exchange,
        timeframe=context.timeframe,
        source=context.source,
        freshness=ManagerFreshness(
            generated_at=_now(),
            expires_at=_now() + timedelta(minutes=10),
        ),
        validity=context.validity,
        decision=ManagerDecision.COORDINATE,
        status=ManagerStatus.COORDINATED,
        originating_selection_id=context.opportunity.selection_id,
        originating_decision_id=context.orchestration.decision_id,
        originating_expansion_id=context.expansion.expansion_id,
        originating_governor_id=context.governor.governor_id,
        originating_protection_id=context.protection.protection_id,
        reason_code=ManagerReasonCode.MANAGER_COORDINATED,
    )

    payload = ManagerWorkflowPayload.from_candidate(candidate)
    event = build_manager_event(
        event_type=ManagerEventType.MANAGER_WORKFLOW_COORDINATED,
        payload=payload,
    )

    assert event.event_type == ManagerEventType.MANAGER_WORKFLOW_COORDINATED.value
    assert event.source == "MANAGER_RUNTIME"
    assert event.payload["workflow_id"] == str(candidate.workflow_id)
    assert event.payload["originating_protection_id"] == str(candidate.originating_protection_id)
    assert (
        default_priority_for_manager_event(ManagerEventType.MANAGER_WORKFLOW_COORDINATED).value
        == event.priority.value
    )


def test_manager_runtime_boundary_is_locked_for_next_step() -> None:
    runtime = create_manager_runtime()
    config = ManagerRuntimeConfig()

    assert runtime.is_started is False
    assert config.manager_name == "phase17_manager"

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from cryptotechnolog.manager import (
    ManagerDecision,
    ManagerFreshness,
    ManagerReasonCode,
    ManagerSource,
    ManagerStatus,
    ManagerValidity,
    ManagerValidityStatus,
    ManagerWorkflowCandidate,
)
from cryptotechnolog.market_data import MarketDataTimeframe
from cryptotechnolog.oms import (
    OmsFreshness,
    OmsLifecycleStatus,
    OmsOrderRecord,
    OmsReasonCode,
    OmsValidity,
    OmsValidityStatus,
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
from cryptotechnolog.validation import (
    ValidationDecision,
    ValidationEventType,
    ValidationRuntimeLifecycleState,
    ValidationStatus,
    create_validation_runtime,
)


def _now() -> datetime:
    return datetime(2026, 3, 23, 12, 0, tzinfo=UTC)


def _manager() -> ManagerWorkflowCandidate:
    current_time = _now()
    return ManagerWorkflowCandidate.candidate(
        contour_name="phase17_manager_contour",
        manager_name="phase17_manager",
        symbol="BTCUSDT",
        exchange="BINANCE",
        timeframe=MarketDataTimeframe.M15,
        source=ManagerSource.WORKFLOW_FOUNDATIONS,
        freshness=ManagerFreshness(
            generated_at=current_time,
            expires_at=current_time + timedelta(minutes=20),
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
        originating_expansion_id=uuid4(),
        originating_governor_id=uuid4(),
        originating_protection_id=uuid4(),
        confidence=Decimal("0.85"),
        priority_score=Decimal("0.65"),
        reason_code=ManagerReasonCode.MANAGER_COORDINATED,
    )


def _governor() -> PortfolioGovernorCandidate:
    current_time = _now()
    return PortfolioGovernorCandidate.candidate(
        contour_name="phase14_governor_contour",
        governor_name="phase14_governor",
        symbol="BTCUSDT",
        exchange="BINANCE",
        timeframe=MarketDataTimeframe.M15,
        source=GovernorSource.POSITION_EXPANSION,
        freshness=GovernorFreshness(
            generated_at=current_time,
            expires_at=current_time + timedelta(minutes=19),
        ),
        validity=GovernorValidity(
            status=GovernorValidityStatus.VALID,
            observed_inputs=2,
            required_inputs=2,
        ),
        decision=GovernorDecision.APPROVE,
        status=GovernorStatus.APPROVED,
        direction=GovernorDirection.LONG,
        originating_expansion_id=uuid4(),
        confidence=Decimal("0.83"),
        priority_score=Decimal("0.63"),
        capital_fraction=Decimal("0.25"),
        reason_code=GovernorReasonCode.CONTEXT_READY,
    )


def _protection() -> ProtectionSupervisorCandidate:
    current_time = _now()
    return ProtectionSupervisorCandidate.candidate(
        contour_name="phase15_protection_contour",
        supervisor_name="phase15_protection",
        symbol="BTCUSDT",
        exchange="BINANCE",
        timeframe=MarketDataTimeframe.M15,
        source=ProtectionSource.PORTFOLIO_GOVERNOR,
        freshness=ProtectionFreshness(
            generated_at=current_time,
            expires_at=current_time + timedelta(minutes=18),
        ),
        validity=ProtectionValidity(
            status=ProtectionValidityStatus.VALID,
            observed_inputs=2,
            required_inputs=2,
        ),
        decision=ProtectionDecision.PROTECT,
        status=ProtectionStatus.PROTECTED,
        originating_governor_id=uuid4(),
        confidence=Decimal("0.84"),
        priority_score=Decimal("0.64"),
        reason_code=ProtectionReasonCode.CONTEXT_READY,
    )


def _oms_order(
    lifecycle_status: OmsLifecycleStatus = OmsLifecycleStatus.ACCEPTED,
) -> OmsOrderRecord:
    current_time = _now()
    reason_code = {
        OmsLifecycleStatus.REGISTERED: OmsReasonCode.ORDER_REGISTERED,
        OmsLifecycleStatus.SUBMITTED: OmsReasonCode.ORDER_SUBMITTED,
        OmsLifecycleStatus.ACCEPTED: OmsReasonCode.ORDER_ACCEPTED,
        OmsLifecycleStatus.PARTIALLY_FILLED: OmsReasonCode.ORDER_PARTIALLY_FILLED,
        OmsLifecycleStatus.FILLED: OmsReasonCode.ORDER_FILLED,
        OmsLifecycleStatus.CANCELLED: OmsReasonCode.ORDER_CANCELLED,
        OmsLifecycleStatus.REJECTED: OmsReasonCode.ORDER_REJECTED,
        OmsLifecycleStatus.EXPIRED: OmsReasonCode.ORDER_EXPIRED,
    }[lifecycle_status]
    base = OmsOrderRecord.registered(
        contour_name="phase16_oms_contour",
        oms_name="phase16_oms",
        symbol="BTCUSDT",
        exchange="BINANCE",
        timeframe=MarketDataTimeframe.M15,
        freshness=OmsFreshness(
            generated_at=current_time,
            expires_at=current_time + timedelta(minutes=17),
        ),
        validity=OmsValidity(
            status=OmsValidityStatus.VALID,
            observed_inputs=3,
            required_inputs=3,
        ),
        originating_intent_id=uuid4(),
        client_order_id="OID-1",
    )
    return replace(
        base,
        lifecycle_status=lifecycle_status,
        reason_code=reason_code,
    )


@pytest.mark.asyncio
async def test_validation_runtime_starts_and_stops_explicitly() -> None:
    runtime = create_validation_runtime()

    assert runtime.is_started is False

    await runtime.start()
    started = runtime.get_runtime_diagnostics()
    assert started["started"] is True
    assert started["lifecycle_state"] == ValidationRuntimeLifecycleState.WARMING.value

    await runtime.stop()
    stopped = runtime.get_runtime_diagnostics()
    assert stopped["started"] is False
    assert stopped["lifecycle_state"] == ValidationRuntimeLifecycleState.STOPPED.value
    assert stopped["tracked_active_reviews"] == 0


@pytest.mark.asyncio
async def test_validation_runtime_builds_validated_candidate_from_valid_truths() -> None:
    runtime = create_validation_runtime()
    await runtime.start()

    update = runtime.ingest_truths(
        manager=_manager(),
        governor=_governor(),
        protection=_protection(),
        oms_order=_oms_order(),
        reference_time=_now(),
    )

    assert update.context is not None
    assert update.context.validity.is_valid is True
    assert update.review_candidate is not None
    assert update.review_candidate.status == ValidationStatus.VALIDATED
    assert update.review_candidate.decision == ValidationDecision.VALIDATE
    assert update.event_type == ValidationEventType.VALIDATION_WORKFLOW_VALIDATED

    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["ready"] is True
    assert diagnostics["tracked_active_reviews"] == 1


@pytest.mark.asyncio
async def test_validation_runtime_abstains_for_terminal_negative_oms_truth() -> None:
    runtime = create_validation_runtime()
    await runtime.start()

    update = runtime.ingest_truths(
        manager=_manager(),
        governor=_governor(),
        protection=_protection(),
        oms_order=_oms_order(OmsLifecycleStatus.CANCELLED),
        reference_time=_now(),
    )

    assert update.review_candidate is not None
    assert update.review_candidate.status == ValidationStatus.ABSTAINED
    assert update.review_candidate.decision == ValidationDecision.ABSTAIN
    assert update.event_type == ValidationEventType.VALIDATION_WORKFLOW_ABSTAINED


@pytest.mark.asyncio
async def test_validation_runtime_handles_missing_inputs_without_hidden_bootstrap() -> None:
    runtime = create_validation_runtime()
    await runtime.start()

    update = runtime.ingest_truths(
        manager=_manager(),
        governor=_governor(),
        protection=None,
        oms_order=None,
        reference_time=_now(),
    )

    assert update.context is None
    assert update.review_candidate is None
    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["ready"] is False
    assert "protection" in diagnostics["readiness_reasons"]


@pytest.mark.asyncio
async def test_validation_runtime_invalidates_existing_review_when_chain_becomes_invalid() -> None:
    runtime = create_validation_runtime()
    await runtime.start()
    runtime.ingest_truths(
        manager=_manager(),
        governor=_governor(),
        protection=_protection(),
        oms_order=_oms_order(),
        reference_time=_now(),
    )

    invalid_manager = ManagerWorkflowCandidate.candidate(
        contour_name="phase17_manager_contour",
        manager_name="phase17_manager",
        symbol="BTCUSDT",
        exchange="BINANCE",
        timeframe=MarketDataTimeframe.M15,
        source=ManagerSource.WORKFLOW_FOUNDATIONS,
        freshness=ManagerFreshness(
            generated_at=_now(),
            expires_at=_now() + timedelta(minutes=5),
        ),
        validity=ManagerValidity(
            status=ManagerValidityStatus.INVALID,
            observed_inputs=5,
            required_inputs=5,
            invalid_reason="manager_invalidated",
        ),
        decision=ManagerDecision.ABSTAIN,
        status=ManagerStatus.INVALIDATED,
        reason_code=ManagerReasonCode.MANAGER_INVALIDATED,
    )

    update = runtime.ingest_truths(
        manager=invalid_manager,
        governor=_governor(),
        protection=_protection(),
        oms_order=_oms_order(),
        reference_time=_now(),
    )

    assert update.review_candidate is not None
    assert update.review_candidate.status == ValidationStatus.INVALIDATED
    assert update.event_type == ValidationEventType.VALIDATION_WORKFLOW_INVALIDATED
    assert len(runtime.list_historical_candidates()) == 1


@pytest.mark.asyncio
async def test_validation_runtime_expires_active_review_into_historical_registry() -> None:
    runtime = create_validation_runtime()
    await runtime.start()
    reference_time = _now()
    update = runtime.ingest_truths(
        manager=_manager(),
        governor=_governor(),
        protection=_protection(),
        oms_order=_oms_order(),
        reference_time=reference_time,
    )

    assert update.review_candidate is not None

    expired = runtime.expire_candidates(reference_time=reference_time + timedelta(minutes=30))

    assert len(expired) == 1
    assert expired[0].status == ValidationStatus.EXPIRED
    assert runtime.list_active_candidates() == ()
    assert len(runtime.list_historical_candidates()) == 1

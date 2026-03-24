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
from cryptotechnolog.paper import (
    PaperDecision,
    PaperEventType,
    PaperRuntimeLifecycleState,
    PaperStatus,
    create_paper_runtime,
)
from cryptotechnolog.validation import (
    ValidationDecision,
    ValidationFreshness,
    ValidationReasonCode,
    ValidationReviewCandidate,
    ValidationSource,
    ValidationStatus,
    ValidationValidity,
    ValidationValidityStatus,
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


def _validation() -> ValidationReviewCandidate:
    current_time = _now()
    return ValidationReviewCandidate.candidate(
        contour_name="phase18_validation_contour",
        validation_name="phase18_validation",
        symbol="BTCUSDT",
        exchange="BINANCE",
        timeframe=MarketDataTimeframe.M15,
        source=ValidationSource.RUNTIME_FOUNDATIONS,
        freshness=ValidationFreshness(
            generated_at=current_time,
            expires_at=current_time + timedelta(minutes=19),
        ),
        validity=ValidationValidity(
            status=ValidationValidityStatus.VALID,
            observed_inputs=4,
            required_inputs=4,
        ),
        decision=ValidationDecision.VALIDATE,
        status=ValidationStatus.VALIDATED,
        originating_workflow_id=uuid4(),
        originating_governor_id=uuid4(),
        originating_protection_id=uuid4(),
        originating_oms_order_id=uuid4(),
        confidence=Decimal("0.86"),
        review_score=Decimal("0.70"),
        reason_code=ValidationReasonCode.VALIDATION_CONFIRMED,
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
            expires_at=current_time + timedelta(minutes=18),
        ),
        validity=OmsValidity(
            status=OmsValidityStatus.VALID,
            observed_inputs=3,
            required_inputs=3,
        ),
        originating_intent_id=uuid4(),
        client_order_id="OID-1",
    )
    return replace(base, lifecycle_status=lifecycle_status, reason_code=reason_code)


@pytest.mark.asyncio
async def test_paper_runtime_starts_and_stops_explicitly() -> None:
    runtime = create_paper_runtime()

    assert runtime.is_started is False

    await runtime.start()
    started = runtime.get_runtime_diagnostics()
    assert started["started"] is True
    assert started["lifecycle_state"] == PaperRuntimeLifecycleState.WARMING.value

    await runtime.stop()
    stopped = runtime.get_runtime_diagnostics()
    assert stopped["started"] is False
    assert stopped["lifecycle_state"] == PaperRuntimeLifecycleState.STOPPED.value
    assert stopped["tracked_active_rehearsals"] == 0


@pytest.mark.asyncio
async def test_paper_runtime_builds_rehearsed_candidate_from_valid_truths() -> None:
    runtime = create_paper_runtime()
    await runtime.start()

    update = runtime.ingest_truths(
        manager=_manager(),
        validation=_validation(),
        oms_order=_oms_order(),
        reference_time=_now(),
    )

    assert update.context is not None
    assert update.context.validity.is_valid is True
    assert update.rehearsal_candidate is not None
    assert update.rehearsal_candidate.status == PaperStatus.REHEARSED
    assert update.rehearsal_candidate.decision == PaperDecision.REHEARSE
    assert update.event_type == PaperEventType.PAPER_REHEARSAL_REHEARSED

    key = ("BTCUSDT", "BINANCE", MarketDataTimeframe.M15)
    assert runtime.get_context(key) is not None
    assert runtime.get_candidate(key) is not None
    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["ready"] is True
    assert diagnostics["tracked_active_rehearsals"] == 1


@pytest.mark.asyncio
async def test_paper_runtime_abstains_for_terminal_negative_oms_truth() -> None:
    runtime = create_paper_runtime()
    await runtime.start()

    update = runtime.ingest_truths(
        manager=_manager(),
        validation=_validation(),
        oms_order=_oms_order(OmsLifecycleStatus.CANCELLED),
        reference_time=_now(),
    )

    assert update.rehearsal_candidate is not None
    assert update.rehearsal_candidate.status == PaperStatus.ABSTAINED
    assert update.rehearsal_candidate.decision == PaperDecision.ABSTAIN
    assert update.event_type == PaperEventType.PAPER_REHEARSAL_ABSTAINED


@pytest.mark.asyncio
async def test_paper_runtime_handles_missing_inputs_without_hidden_bootstrap() -> None:
    runtime = create_paper_runtime()
    await runtime.start()

    update = runtime.ingest_truths(
        manager=_manager(),
        validation=None,
        oms_order=None,
        reference_time=_now(),
    )

    assert update.context is None
    assert update.rehearsal_candidate is None
    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["ready"] is False
    assert "validation" in diagnostics["readiness_reasons"]


@pytest.mark.asyncio
async def test_paper_runtime_invalidates_existing_rehearsal_when_chain_becomes_invalid() -> None:
    runtime = create_paper_runtime()
    await runtime.start()
    runtime.ingest_truths(
        manager=_manager(),
        validation=_validation(),
        oms_order=_oms_order(),
        reference_time=_now(),
    )

    invalid_validation = ValidationReviewCandidate.candidate(
        contour_name="phase18_validation_contour",
        validation_name="phase18_validation",
        symbol="BTCUSDT",
        exchange="BINANCE",
        timeframe=MarketDataTimeframe.M15,
        source=ValidationSource.RUNTIME_FOUNDATIONS,
        freshness=ValidationFreshness(
            generated_at=_now(),
            expires_at=_now() + timedelta(minutes=5),
        ),
        validity=ValidationValidity(
            status=ValidationValidityStatus.INVALID,
            observed_inputs=4,
            required_inputs=4,
            invalid_reason="validation_invalidated",
        ),
        decision=ValidationDecision.ABSTAIN,
        status=ValidationStatus.INVALIDATED,
        reason_code=ValidationReasonCode.VALIDATION_INVALIDATED,
    )

    update = runtime.ingest_truths(
        manager=_manager(),
        validation=invalid_validation,
        oms_order=_oms_order(),
        reference_time=_now(),
    )

    assert update.rehearsal_candidate is not None
    assert update.rehearsal_candidate.status == PaperStatus.INVALIDATED
    assert update.event_type == PaperEventType.PAPER_REHEARSAL_INVALIDATED
    assert len(runtime.list_historical_candidates()) == 1


@pytest.mark.asyncio
async def test_paper_runtime_expires_active_rehearsal_into_historical_registry() -> None:
    runtime = create_paper_runtime()
    await runtime.start()
    reference_time = _now()
    update = runtime.ingest_truths(
        manager=_manager(),
        validation=_validation(),
        oms_order=_oms_order(),
        reference_time=reference_time,
    )

    assert update.rehearsal_candidate is not None

    expired = runtime.expire_candidates(reference_time=reference_time + timedelta(minutes=30))

    assert len(expired) == 1
    assert expired[0].status == PaperStatus.EXPIRED
    assert runtime.list_active_candidates() == ()
    assert len(runtime.list_historical_candidates()) == 1

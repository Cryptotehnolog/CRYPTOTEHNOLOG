from __future__ import annotations

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
    OmsOrderRecord,
    OmsReasonCode,
    OmsValidity,
    OmsValidityStatus,
)
from cryptotechnolog.paper import (
    PaperContext,
    PaperDecision,
    PaperEventType,
    PaperFreshness,
    PaperReasonCode,
    PaperRehearsalCandidate,
    PaperRehearsalPayload,
    PaperRuntimeConfig,
    PaperSource,
    PaperStatus,
    PaperValidity,
    PaperValidityStatus,
    build_paper_event,
    create_paper_runtime,
    default_priority_for_paper_event,
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
            expires_at=current_time + timedelta(minutes=10),
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
            expires_at=current_time + timedelta(minutes=10),
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


def _oms_order() -> OmsOrderRecord:
    current_time = _now()
    return OmsOrderRecord.registered(
        contour_name="phase16_oms_contour",
        oms_name="phase16_oms",
        symbol="BTCUSDT",
        exchange="BINANCE",
        timeframe=MarketDataTimeframe.M15,
        freshness=OmsFreshness(
            generated_at=current_time,
            expires_at=current_time + timedelta(minutes=10),
        ),
        validity=OmsValidity(
            status=OmsValidityStatus.VALID,
            observed_inputs=3,
            required_inputs=3,
        ),
        originating_intent_id=uuid4(),
        client_order_id="OID-1",
        reason_code=OmsReasonCode.ORDER_REGISTERED,
    )


def _context(validity: PaperValidity | None = None) -> PaperContext:
    return PaperContext(
        paper_name="phase19_paper",
        contour_name="phase19_paper_contour",
        symbol="BTCUSDT",
        exchange="BINANCE",
        timeframe=MarketDataTimeframe.M15,
        observed_at=_now(),
        source=PaperSource.RUNTIME_FOUNDATIONS,
        manager=_manager(),
        validation=_validation(),
        oms_order=_oms_order(),
        validity=validity
        or PaperValidity(
            status=PaperValidityStatus.VALID,
            observed_inputs=3,
            required_inputs=3,
        ),
    )


def test_paper_validity_readiness_ratio_is_normalized() -> None:
    validity = PaperValidity(
        status=PaperValidityStatus.WARMING,
        observed_inputs=2,
        required_inputs=3,
        missing_inputs=("oms",),
    )

    assert validity.readiness_ratio == Decimal("0.6667")
    assert validity.is_warming is True
    assert validity.missing_inputs_count == 1


def test_valid_paper_context_requires_validated_review_truth() -> None:
    current_time = _now()
    invalid_validation = ValidationReviewCandidate.candidate(
        contour_name="phase18_validation_contour",
        validation_name="phase18_validation",
        symbol="BTCUSDT",
        exchange="BINANCE",
        timeframe=MarketDataTimeframe.M15,
        source=ValidationSource.RUNTIME_FOUNDATIONS,
        freshness=ValidationFreshness(
            generated_at=current_time,
            expires_at=current_time + timedelta(minutes=10),
        ),
        validity=ValidationValidity(
            status=ValidationValidityStatus.VALID,
            observed_inputs=4,
            required_inputs=4,
        ),
        decision=ValidationDecision.ABSTAIN,
        status=ValidationStatus.ABSTAINED,
        originating_workflow_id=uuid4(),
        originating_governor_id=uuid4(),
        originating_protection_id=uuid4(),
        reason_code=ValidationReasonCode.VALIDATION_ABSTAINED,
    )

    with pytest.raises(
        ValueError,
        match="VALID PaperContext требует validated review truth",
    ):
        PaperContext(
            paper_name="phase19_paper",
            contour_name="phase19_paper_contour",
            symbol="BTCUSDT",
            exchange="BINANCE",
            timeframe=MarketDataTimeframe.M15,
            observed_at=current_time,
            source=PaperSource.RUNTIME_FOUNDATIONS,
            manager=_manager(),
            validation=invalid_validation,
            oms_order=_oms_order(),
            validity=PaperValidity(
                status=PaperValidityStatus.VALID,
                observed_inputs=3,
                required_inputs=3,
            ),
        )


def test_rehearsed_candidate_requires_upstream_rehearsal_chain() -> None:
    context = _context()

    with pytest.raises(
        ValueError,
        match="REHEARSED candidate обязан ссылаться на upstream rehearsal chain",
    ):
        PaperRehearsalCandidate.candidate(
            contour_name=context.contour_name,
            paper_name=context.paper_name,
            symbol=context.symbol,
            exchange=context.exchange,
            timeframe=context.timeframe,
            source=context.source,
            freshness=PaperFreshness(
                generated_at=_now(),
                expires_at=_now() + timedelta(minutes=10),
            ),
            validity=context.validity,
            decision=PaperDecision.REHEARSE,
            status=PaperStatus.REHEARSED,
            originating_workflow_id=context.manager.workflow_id,
            reason_code=PaperReasonCode.PAPER_REHEARSED,
        )


def test_paper_candidate_exposes_narrow_rehearsal_truth() -> None:
    context = _context()
    candidate = PaperRehearsalCandidate.candidate(
        contour_name=context.contour_name,
        paper_name=context.paper_name,
        symbol=context.symbol,
        exchange=context.exchange,
        timeframe=context.timeframe,
        source=context.source,
        freshness=PaperFreshness(
            generated_at=_now(),
            expires_at=_now() + timedelta(minutes=10),
        ),
        validity=context.validity,
        decision=PaperDecision.REHEARSE,
        status=PaperStatus.REHEARSED,
        originating_workflow_id=context.manager.workflow_id,
        originating_review_id=context.validation.review_id,
        originating_oms_order_id=context.oms_order.oms_order_id if context.oms_order else None,
        confidence=Decimal("0.87"),
        rehearsal_score=Decimal("0.73"),
        reason_code=PaperReasonCode.PAPER_REHEARSED,
    )

    assert candidate.is_rehearsed is True
    assert candidate.is_abstained is False


def test_paper_event_payload_remains_narrow() -> None:
    context = _context()
    candidate = PaperRehearsalCandidate.candidate(
        contour_name=context.contour_name,
        paper_name=context.paper_name,
        symbol=context.symbol,
        exchange=context.exchange,
        timeframe=context.timeframe,
        source=context.source,
        freshness=PaperFreshness(
            generated_at=_now(),
            expires_at=_now() + timedelta(minutes=10),
        ),
        validity=context.validity,
        decision=PaperDecision.REHEARSE,
        status=PaperStatus.REHEARSED,
        originating_workflow_id=context.manager.workflow_id,
        originating_review_id=context.validation.review_id,
        originating_oms_order_id=context.oms_order.oms_order_id if context.oms_order else None,
        reason_code=PaperReasonCode.PAPER_REHEARSED,
    )

    payload = PaperRehearsalPayload.from_candidate(candidate)
    event = build_paper_event(
        event_type=PaperEventType.PAPER_REHEARSAL_REHEARSED,
        payload=payload,
    )

    assert event.event_type == PaperEventType.PAPER_REHEARSAL_REHEARSED.value
    assert event.source == "PAPER_RUNTIME"
    assert event.payload["rehearsal_id"] == str(candidate.rehearsal_id)
    assert event.payload["originating_review_id"] == str(candidate.originating_review_id)
    assert default_priority_for_paper_event(PaperEventType.PAPER_REHEARSAL_REHEARSED).value == (
        event.priority.value
    )


def test_paper_runtime_boundary_is_locked_for_next_step() -> None:
    runtime = create_paper_runtime()
    config = PaperRuntimeConfig()

    assert runtime.is_started is False
    assert config.paper_name == "phase19_paper"

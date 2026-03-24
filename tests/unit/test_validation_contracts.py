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
    ValidationContext,
    ValidationDecision,
    ValidationEventType,
    ValidationFreshness,
    ValidationReasonCode,
    ValidationReviewCandidate,
    ValidationReviewPayload,
    ValidationRuntimeConfig,
    ValidationSource,
    ValidationStatus,
    ValidationValidity,
    ValidationValidityStatus,
    build_validation_event,
    create_validation_runtime,
    default_priority_for_validation_event,
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
            expires_at=current_time + timedelta(minutes=10),
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
            expires_at=current_time + timedelta(minutes=10),
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


def _context(validity: ValidationValidity | None = None) -> ValidationContext:
    return ValidationContext(
        validation_name="phase18_validation",
        contour_name="phase18_validation_contour",
        symbol="BTCUSDT",
        exchange="BINANCE",
        timeframe=MarketDataTimeframe.M15,
        observed_at=_now(),
        source=ValidationSource.RUNTIME_FOUNDATIONS,
        manager=_manager(),
        governor=_governor(),
        protection=_protection(),
        oms_order=_oms_order(),
        validity=validity
        or ValidationValidity(
            status=ValidationValidityStatus.VALID,
            observed_inputs=4,
            required_inputs=4,
        ),
    )


def test_validation_validity_readiness_ratio_is_normalized() -> None:
    validity = ValidationValidity(
        status=ValidationValidityStatus.WARMING,
        observed_inputs=2,
        required_inputs=4,
        missing_inputs=("protection", "oms"),
    )

    assert validity.readiness_ratio == Decimal("0.5000")
    assert validity.is_warming is True
    assert validity.missing_inputs_count == 2


def test_valid_validation_context_requires_protected_supervisory_truth() -> None:
    current_time = _now()
    invalid_protection = ProtectionSupervisorCandidate.candidate(
        contour_name="phase15_protection_contour",
        supervisor_name="phase15_protection",
        symbol="BTCUSDT",
        exchange="BINANCE",
        timeframe=MarketDataTimeframe.M15,
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
        decision=ProtectionDecision.HALT,
        status=ProtectionStatus.HALTED,
        originating_governor_id=uuid4(),
        confidence=Decimal("0.84"),
        priority_score=Decimal("0.64"),
        reason_code=ProtectionReasonCode.CONTEXT_READY,
    )

    with pytest.raises(
        ValueError,
        match="VALID ValidationContext требует protected supervisory truth",
    ):
        ValidationContext(
            validation_name="phase18_validation",
            contour_name="phase18_validation_contour",
            symbol="BTCUSDT",
            exchange="BINANCE",
            timeframe=MarketDataTimeframe.M15,
            observed_at=current_time,
            source=ValidationSource.RUNTIME_FOUNDATIONS,
            manager=_manager(),
            governor=_governor(),
            protection=invalid_protection,
            oms_order=_oms_order(),
            validity=ValidationValidity(
                status=ValidationValidityStatus.VALID,
                observed_inputs=4,
                required_inputs=4,
            ),
        )


def test_validated_review_candidate_requires_upstream_review_chain() -> None:
    context = _context()

    with pytest.raises(
        ValueError,
        match="VALIDATED candidate обязан ссылаться на upstream review chain",
    ):
        ValidationReviewCandidate.candidate(
            contour_name=context.contour_name,
            validation_name=context.validation_name,
            symbol=context.symbol,
            exchange=context.exchange,
            timeframe=context.timeframe,
            source=context.source,
            freshness=ValidationFreshness(
                generated_at=_now(),
                expires_at=_now() + timedelta(minutes=10),
            ),
            validity=context.validity,
            decision=ValidationDecision.VALIDATE,
            status=ValidationStatus.VALIDATED,
            originating_workflow_id=context.manager.workflow_id,
            originating_governor_id=context.governor.governor_id,
            reason_code=ValidationReasonCode.VALIDATION_CONFIRMED,
        )


def test_validation_candidate_exposes_narrow_review_truth() -> None:
    context = _context()
    candidate = ValidationReviewCandidate.candidate(
        contour_name=context.contour_name,
        validation_name=context.validation_name,
        symbol=context.symbol,
        exchange=context.exchange,
        timeframe=context.timeframe,
        source=context.source,
        freshness=ValidationFreshness(
            generated_at=_now(),
            expires_at=_now() + timedelta(minutes=10),
        ),
        validity=context.validity,
        decision=ValidationDecision.VALIDATE,
        status=ValidationStatus.VALIDATED,
        originating_workflow_id=context.manager.workflow_id,
        originating_governor_id=context.governor.governor_id,
        originating_protection_id=context.protection.protection_id,
        originating_oms_order_id=context.oms_order.oms_order_id if context.oms_order else None,
        confidence=Decimal("0.86"),
        review_score=Decimal("0.70"),
        reason_code=ValidationReasonCode.VALIDATION_CONFIRMED,
    )

    assert candidate.is_validated is True
    assert candidate.is_abstained is False


def test_validation_event_payload_remains_narrow() -> None:
    context = _context()
    candidate = ValidationReviewCandidate.candidate(
        contour_name=context.contour_name,
        validation_name=context.validation_name,
        symbol=context.symbol,
        exchange=context.exchange,
        timeframe=context.timeframe,
        source=context.source,
        freshness=ValidationFreshness(
            generated_at=_now(),
            expires_at=_now() + timedelta(minutes=10),
        ),
        validity=context.validity,
        decision=ValidationDecision.VALIDATE,
        status=ValidationStatus.VALIDATED,
        originating_workflow_id=context.manager.workflow_id,
        originating_governor_id=context.governor.governor_id,
        originating_protection_id=context.protection.protection_id,
        originating_oms_order_id=context.oms_order.oms_order_id if context.oms_order else None,
        reason_code=ValidationReasonCode.VALIDATION_CONFIRMED,
    )

    payload = ValidationReviewPayload.from_candidate(candidate)
    event = build_validation_event(
        event_type=ValidationEventType.VALIDATION_WORKFLOW_VALIDATED,
        payload=payload,
    )

    assert event.event_type == ValidationEventType.VALIDATION_WORKFLOW_VALIDATED.value
    assert event.source == "VALIDATION_RUNTIME"
    assert event.payload["review_id"] == str(candidate.review_id)
    assert event.payload["originating_workflow_id"] == str(candidate.originating_workflow_id)
    assert (
        default_priority_for_validation_event(
            ValidationEventType.VALIDATION_WORKFLOW_VALIDATED
        ).value
        == event.priority.value
    )


def test_validation_runtime_boundary_is_locked_for_next_step() -> None:
    runtime = create_validation_runtime()
    config = ValidationRuntimeConfig()

    assert runtime.is_started is False
    assert config.validation_name == "phase18_validation"

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from cryptotechnolog.market_data import MarketDataTimeframe
from cryptotechnolog.opportunity import OpportunityDirection
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
from cryptotechnolog.position_expansion import (
    ExpansionDecision,
    ExpansionReasonCode,
    ExpansionStatus,
    ExpansionValidityStatus,
    PositionExpansionEventType,
    PositionExpansionRuntime,
    PositionExpansionRuntimeConfig,
    PositionExpansionRuntimeLifecycleState,
    create_position_expansion_runtime,
)


def _make_orchestration_decision(
    *,
    status: OrchestrationStatus = OrchestrationStatus.ORCHESTRATED,
    decision: OrchestrationDecision = OrchestrationDecision.FORWARD,
    direction: OpportunityDirection | None = OpportunityDirection.LONG,
    confidence: str | None = "0.87",
    priority_score: str | None = "0.9100",
    generated_at: datetime | None = None,
    expires_at: datetime | None = None,
) -> OrchestrationDecisionCandidate:
    now = generated_at or datetime(2026, 3, 22, 12, 0, tzinfo=UTC)
    validity = (
        OrchestrationValidity(
            status=OrchestrationValidityStatus.VALID,
            observed_inputs=1,
            required_inputs=1,
        )
        if status in {OrchestrationStatus.ORCHESTRATED, OrchestrationStatus.ABSTAINED}
        else OrchestrationValidity(
            status=OrchestrationValidityStatus.INVALID,
            observed_inputs=1,
            required_inputs=1,
            invalid_reason="orchestration_lost",
        )
    )
    return OrchestrationDecisionCandidate(
        decision_id=uuid4(),
        contour_name="phase12_orchestration_contour",
        orchestration_name="phase12_meta_orchestration",
        symbol="BTCUSDT",
        exchange="BINANCE",
        timeframe=MarketDataTimeframe.M5,
        source=OrchestrationSource.OPPORTUNITY_SELECTION,
        freshness=OrchestrationFreshness(
            generated_at=now,
            expires_at=expires_at or (now + timedelta(minutes=5)),
        ),
        validity=validity,
        status=status,
        decision=decision,
        direction=direction,
        originating_selection_id=uuid4() if status != OrchestrationStatus.CANDIDATE else None,
        confidence=Decimal(confidence) if confidence is not None else None,
        priority_score=Decimal(priority_score) if priority_score is not None else None,
        reason_code=(
            OrchestrationReasonCode.CONTEXT_READY
            if status == OrchestrationStatus.ORCHESTRATED
            else OrchestrationReasonCode.ORCHESTRATION_ABSTAINED
        ),
    )


def test_position_expansion_runtime_requires_explicit_start() -> None:
    runtime = create_position_expansion_runtime()

    with pytest.raises(RuntimeError, match="не запущен"):
        runtime.ingest_decision(
            decision=_make_orchestration_decision(),
            reference_time=datetime(2026, 3, 22, 12, 1, tzinfo=UTC),
        )


def test_position_expansion_runtime_start_and_stop_reset_operator_state() -> None:
    runtime = create_position_expansion_runtime()

    asyncio.run(runtime.start())
    runtime.mark_degraded("decision_ingest_failed")
    runtime.ingest_decision(
        decision=_make_orchestration_decision(),
        reference_time=datetime(2026, 3, 22, 12, 1, tzinfo=UTC),
    )
    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["started"] is True
    assert diagnostics["tracked_expansion_keys"] == 1

    asyncio.run(runtime.stop())
    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["started"] is False
    assert diagnostics["tracked_context_keys"] == 0
    assert diagnostics["tracked_expansion_keys"] == 0
    assert diagnostics["expandable_keys"] == 0
    assert diagnostics["abstained_keys"] == 0
    assert diagnostics["rejected_keys"] == 0
    assert diagnostics["invalidated_expansion_keys"] == 0
    assert diagnostics["expired_expansion_keys"] == 0
    assert diagnostics["last_decision_id"] is None
    assert diagnostics["last_expansion_id"] is None
    assert diagnostics["last_event_type"] is None
    assert diagnostics["last_failure_reason"] is None
    assert diagnostics["lifecycle_state"] == PositionExpansionRuntimeLifecycleState.STOPPED.value
    assert diagnostics["readiness_reasons"] == ["runtime_stopped"]
    assert (
        runtime.get_candidate(
            symbol="BTCUSDT",
            exchange="BINANCE",
            timeframe=MarketDataTimeframe.M5,
        )
        is None
    )
    assert (
        runtime.get_context(
            symbol="BTCUSDT",
            exchange="BINANCE",
            timeframe=MarketDataTimeframe.M5,
        )
        is None
    )


def test_position_expansion_runtime_builds_expandable_candidate_from_forwarded_decision() -> None:
    runtime = create_position_expansion_runtime()
    asyncio.run(runtime.start())

    update = runtime.ingest_decision(
        decision=_make_orchestration_decision(
            status=OrchestrationStatus.ORCHESTRATED,
            decision=OrchestrationDecision.FORWARD,
            direction=OpportunityDirection.LONG,
            confidence="0.88",
            priority_score="0.91",
        ),
        reference_time=datetime(2026, 3, 22, 12, 1, tzinfo=UTC),
    )

    assert update.candidate is not None
    assert update.candidate.status == ExpansionStatus.EXPANDABLE
    assert update.candidate.decision == ExpansionDecision.ADD
    assert update.candidate.reason_code == ExpansionReasonCode.CONTEXT_READY
    assert update.event_type == PositionExpansionEventType.POSITION_EXPANSION_APPROVED
    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["ready"] is True
    assert diagnostics["lifecycle_state"] == PositionExpansionRuntimeLifecycleState.READY.value
    assert diagnostics["expandable_keys"] == 1


def test_position_expansion_runtime_returns_abstained_candidate_when_decision_is_too_weak() -> None:
    runtime = create_position_expansion_runtime(
        config=PositionExpansionRuntimeConfig(
            min_confidence_for_add=Decimal("0.70"),
            min_priority_score_for_add=Decimal("0.70"),
        )
    )
    asyncio.run(runtime.start())

    update = runtime.ingest_decision(
        decision=_make_orchestration_decision(
            confidence="0.40",
            priority_score="0.40",
        ),
        reference_time=datetime(2026, 3, 22, 12, 1, tzinfo=UTC),
    )

    assert update.candidate is not None
    assert update.candidate.status == ExpansionStatus.ABSTAINED
    assert update.candidate.decision == ExpansionDecision.ABSTAIN
    assert update.candidate.reason_code == ExpansionReasonCode.EXPANSION_ABSTAINED
    assert update.event_type == PositionExpansionEventType.POSITION_EXPANSION_CANDIDATE_UPDATED


def test_position_expansion_runtime_creates_warming_context_for_candidate_decision() -> None:
    runtime = create_position_expansion_runtime()
    asyncio.run(runtime.start())

    update = runtime.ingest_decision(
        decision=_make_orchestration_decision(
            status=OrchestrationStatus.CANDIDATE,
            decision=OrchestrationDecision.ABSTAIN,
            direction=None,
            confidence=None,
            priority_score=None,
        ),
        reference_time=datetime(2026, 3, 22, 12, 1, tzinfo=UTC),
    )

    assert update.context.validity.status == ExpansionValidityStatus.WARMING
    assert update.context.validity.missing_inputs == ("forwardable_decision",)
    assert update.candidate is not None
    assert update.candidate.status == ExpansionStatus.CANDIDATE
    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["ready"] is False
    assert diagnostics["lifecycle_state"] == PositionExpansionRuntimeLifecycleState.WARMING.value


def test_position_expansion_runtime_rejects_non_forwardable_decision_without_previous_active_state() -> (
    None
):
    runtime = create_position_expansion_runtime()
    asyncio.run(runtime.start())

    update = runtime.ingest_decision(
        decision=_make_orchestration_decision(
            status=OrchestrationStatus.ABSTAINED,
            decision=OrchestrationDecision.ABSTAIN,
            direction=None,
        ),
        reference_time=datetime(2026, 3, 22, 12, 1, tzinfo=UTC),
    )

    assert update.candidate is not None
    assert update.candidate.status == ExpansionStatus.REJECTED
    assert update.candidate.decision == ExpansionDecision.REJECT
    assert update.candidate.reason_code == ExpansionReasonCode.EXPANSION_REJECTED
    assert update.event_type == PositionExpansionEventType.POSITION_EXPANSION_CANDIDATE_UPDATED
    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["rejected_keys"] == 1


def test_position_expansion_runtime_invalidates_previous_candidate_when_decision_breaks() -> None:
    runtime = create_position_expansion_runtime()
    asyncio.run(runtime.start())

    first = runtime.ingest_decision(
        decision=_make_orchestration_decision(),
        reference_time=datetime(2026, 3, 22, 12, 1, tzinfo=UTC),
    )
    assert first.candidate is not None
    assert first.candidate.status == ExpansionStatus.EXPANDABLE

    second = runtime.ingest_decision(
        decision=_make_orchestration_decision(
            status=OrchestrationStatus.INVALIDATED,
            decision=OrchestrationDecision.ABSTAIN,
            direction=None,
        ),
        reference_time=datetime(2026, 3, 22, 12, 2, tzinfo=UTC),
    )

    assert second.candidate is not None
    assert second.candidate.status == ExpansionStatus.INVALIDATED
    assert second.candidate.expansion_id == first.candidate.expansion_id
    assert second.event_type == PositionExpansionEventType.POSITION_EXPANSION_INVALIDATED
    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["invalidated_expansion_keys"] == 1


def test_position_expansion_runtime_expires_candidate_only_against_reference_time() -> None:
    runtime = create_position_expansion_runtime(
        config=PositionExpansionRuntimeConfig(max_candidate_age_seconds=60),
    )
    asyncio.run(runtime.start())

    generated_at = datetime(2026, 3, 22, 12, 0, tzinfo=UTC)
    update = runtime.ingest_decision(
        decision=_make_orchestration_decision(
            generated_at=generated_at,
            expires_at=generated_at + timedelta(minutes=5),
        ),
        reference_time=generated_at,
    )
    assert update.candidate is not None

    not_expired = runtime.get_candidate(
        symbol="BTCUSDT",
        exchange="BINANCE",
        timeframe=MarketDataTimeframe.M5,
    )
    assert not_expired is not None
    assert not_expired.status == ExpansionStatus.EXPANDABLE

    expired = runtime.expire_candidates(reference_time=generated_at + timedelta(seconds=60))
    assert len(expired) == 1
    assert expired[0].candidate is not None
    assert expired[0].candidate.status == ExpansionStatus.EXPIRED
    assert expired[0].candidate.reason_code == ExpansionReasonCode.EXPANSION_EXPIRED
    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["expired_expansion_keys"] == 1
    assert (
        diagnostics["last_event_type"]
        == PositionExpansionEventType.POSITION_EXPANSION_INVALIDATED.value
    )


def test_position_expansion_runtime_marks_degraded_and_keeps_operator_truth_visible() -> None:
    runtime = PositionExpansionRuntime()

    asyncio.run(runtime.start())
    runtime.mark_degraded("decision_ingest_failed")
    diagnostics = runtime.get_runtime_diagnostics()

    assert diagnostics["ready"] is False
    assert diagnostics["lifecycle_state"] == PositionExpansionRuntimeLifecycleState.DEGRADED.value
    assert diagnostics["last_failure_reason"] == "decision_ingest_failed"
    assert diagnostics["degraded_reasons"] == ["decision_ingest_failed"]


def test_position_expansion_runtime_uses_runtime_config_in_state_keying() -> None:
    runtime = create_position_expansion_runtime(
        config=PositionExpansionRuntimeConfig(
            contour_name="custom_position_expansion_contour",
            expansion_name="custom_position_expansion",
        )
    )
    asyncio.run(runtime.start())

    runtime.ingest_decision(
        decision=_make_orchestration_decision(),
        reference_time=datetime(2026, 3, 22, 12, 1, tzinfo=UTC),
    )

    candidate = runtime.get_candidate(
        symbol="BTCUSDT",
        exchange="BINANCE",
        timeframe=MarketDataTimeframe.M5,
    )
    context = runtime.get_context(
        symbol="BTCUSDT",
        exchange="BINANCE",
        timeframe=MarketDataTimeframe.M5,
    )

    assert candidate is not None
    assert candidate.contour_name == "custom_position_expansion_contour"
    assert candidate.expansion_name == "custom_position_expansion"
    assert context is not None
    assert context.contour_name == "custom_position_expansion_contour"
    assert context.expansion_name == "custom_position_expansion"

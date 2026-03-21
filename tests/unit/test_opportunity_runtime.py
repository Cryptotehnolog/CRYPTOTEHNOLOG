from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from cryptotechnolog.execution import (
    ExecutionDirection,
    ExecutionFreshness,
    ExecutionOrderIntent,
    ExecutionReasonCode,
    ExecutionStatus,
    ExecutionValidity,
    ExecutionValidityStatus,
)
from cryptotechnolog.market_data import MarketDataTimeframe
from cryptotechnolog.opportunity import (
    OpportunityEventType,
    OpportunityReasonCode,
    OpportunityRuntime,
    OpportunityRuntimeConfig,
    OpportunityRuntimeLifecycleState,
    OpportunityStatus,
    OpportunityValidityStatus,
    create_opportunity_runtime,
)


def _make_execution_intent(
    *,
    status: ExecutionStatus = ExecutionStatus.EXECUTABLE,
    direction: ExecutionDirection | None = ExecutionDirection.BUY,
    confidence: str | None = "0.87",
    generated_at: datetime | None = None,
    expires_at: datetime | None = None,
) -> ExecutionOrderIntent:
    now = generated_at or datetime(2026, 3, 22, 12, 0, tzinfo=UTC)
    validity = (
        ExecutionValidity(
            status=ExecutionValidityStatus.VALID,
            observed_inputs=1,
            required_inputs=1,
        )
        if status in {ExecutionStatus.EXECUTABLE, ExecutionStatus.SUPPRESSED}
        else ExecutionValidity(
            status=ExecutionValidityStatus.INVALID,
            observed_inputs=1,
            required_inputs=1,
            invalid_reason="intent_lost",
        )
    )
    return ExecutionOrderIntent(
        intent_id=uuid4(),
        contour_name="phase10_execution_contour",
        execution_name="phase10_foundation_execution",
        symbol="BTCUSDT",
        exchange="BINANCE",
        timeframe=MarketDataTimeframe.M5,
        freshness=ExecutionFreshness(
            generated_at=now,
            expires_at=expires_at or (now + timedelta(minutes=5)),
        ),
        validity=validity,
        status=status,
        direction=direction,
        originating_candidate_id=uuid4() if direction is not None else None,
        confidence=Decimal(confidence) if confidence is not None else None,
        reason_code=(
            ExecutionReasonCode.CONTEXT_READY
            if status == ExecutionStatus.EXECUTABLE
            else ExecutionReasonCode.EXECUTION_RULE_BLOCKED
        ),
    )


def test_opportunity_runtime_requires_explicit_start() -> None:
    runtime = create_opportunity_runtime()

    with pytest.raises(RuntimeError, match="не запущен"):
        runtime.ingest_intent(
            intent=_make_execution_intent(),
            reference_time=datetime(2026, 3, 22, 12, 1, tzinfo=UTC),
        )


def test_opportunity_runtime_start_and_stop_reset_operator_state() -> None:
    runtime = create_opportunity_runtime()

    asyncio.run(runtime.start())
    runtime.mark_degraded("synthetic_failure")
    runtime.ingest_intent(
        intent=_make_execution_intent(),
        reference_time=datetime(2026, 3, 22, 12, 1, tzinfo=UTC),
    )
    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["started"] is True
    assert diagnostics["tracked_selection_keys"] == 1

    asyncio.run(runtime.stop())
    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["started"] is False
    assert diagnostics["tracked_context_keys"] == 0
    assert diagnostics["tracked_selection_keys"] == 0
    assert diagnostics["selected_keys"] == 0
    assert diagnostics["invalidated_selection_keys"] == 0
    assert diagnostics["expired_selection_keys"] == 0
    assert diagnostics["last_intent_id"] is None
    assert diagnostics["last_selection_id"] is None
    assert diagnostics["last_event_type"] is None
    assert diagnostics["last_failure_reason"] is None
    assert diagnostics["lifecycle_state"] == OpportunityRuntimeLifecycleState.STOPPED.value
    assert diagnostics["readiness_reasons"] == ["runtime_stopped"]
    assert (
        runtime.get_selection(
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


def test_opportunity_runtime_builds_selected_long_candidate_from_executable_buy_intent() -> None:
    runtime = create_opportunity_runtime()
    asyncio.run(runtime.start())

    update = runtime.ingest_intent(
        intent=_make_execution_intent(
            status=ExecutionStatus.EXECUTABLE,
            direction=ExecutionDirection.BUY,
            confidence="0.88",
        ),
        reference_time=datetime(2026, 3, 22, 12, 1, tzinfo=UTC),
    )

    assert update.candidate is not None
    assert update.candidate.status == OpportunityStatus.SELECTED
    assert update.candidate.direction is not None
    assert update.event_type == OpportunityEventType.OPPORTUNITY_SELECTED
    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["ready"] is True
    assert diagnostics["lifecycle_state"] == OpportunityRuntimeLifecycleState.READY.value
    assert diagnostics["selected_keys"] == 1


def test_opportunity_runtime_returns_suppressed_candidate_when_confidence_too_low() -> None:
    runtime = create_opportunity_runtime(
        config=OpportunityRuntimeConfig(
            min_intent_confidence_for_selection=Decimal("0.70"),
            min_priority_score_for_selected=Decimal("0.70"),
        )
    )
    asyncio.run(runtime.start())

    update = runtime.ingest_intent(
        intent=_make_execution_intent(confidence="0.40"),
        reference_time=datetime(2026, 3, 22, 12, 1, tzinfo=UTC),
    )

    assert update.candidate is not None
    assert update.candidate.status == OpportunityStatus.SUPPRESSED
    assert update.candidate.reason_code == OpportunityReasonCode.SELECTION_RULE_BLOCKED
    assert update.event_type == OpportunityEventType.OPPORTUNITY_CANDIDATE_UPDATED


def test_opportunity_runtime_creates_warming_context_for_suppressed_intent() -> None:
    runtime = create_opportunity_runtime()
    asyncio.run(runtime.start())

    update = runtime.ingest_intent(
        intent=_make_execution_intent(
            status=ExecutionStatus.SUPPRESSED,
            direction=None,
        ),
        reference_time=datetime(2026, 3, 22, 12, 1, tzinfo=UTC),
    )

    assert update.context.validity.status == OpportunityValidityStatus.WARMING
    assert update.context.validity.missing_inputs == ("selectable_intent",)
    assert update.candidate is not None
    assert update.candidate.status == OpportunityStatus.CANDIDATE
    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["ready"] is False
    assert diagnostics["lifecycle_state"] == OpportunityRuntimeLifecycleState.WARMING.value


def test_opportunity_runtime_invalidates_previous_selected_candidate_when_intent_breaks() -> None:
    runtime = create_opportunity_runtime()
    asyncio.run(runtime.start())

    first = runtime.ingest_intent(
        intent=_make_execution_intent(),
        reference_time=datetime(2026, 3, 22, 12, 1, tzinfo=UTC),
    )
    assert first.candidate is not None
    assert first.candidate.status == OpportunityStatus.SELECTED

    second = runtime.ingest_intent(
        intent=_make_execution_intent(
            status=ExecutionStatus.INVALIDATED,
            direction=ExecutionDirection.BUY,
        ),
        reference_time=datetime(2026, 3, 22, 12, 2, tzinfo=UTC),
    )

    assert second.candidate is not None
    assert second.candidate.status == OpportunityStatus.INVALIDATED
    assert second.candidate.selection_id == first.candidate.selection_id
    assert second.event_type == OpportunityEventType.OPPORTUNITY_INVALIDATED
    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["ready"] is True
    assert diagnostics["invalidated_selection_keys"] == 1


def test_opportunity_runtime_expires_candidate_only_against_reference_time() -> None:
    runtime = create_opportunity_runtime(
        config=OpportunityRuntimeConfig(max_selection_age_seconds=60),
    )
    asyncio.run(runtime.start())

    generated_at = datetime(2026, 3, 22, 12, 0, tzinfo=UTC)
    update = runtime.ingest_intent(
        intent=_make_execution_intent(
            generated_at=generated_at,
            expires_at=generated_at + timedelta(minutes=5),
        ),
        reference_time=generated_at,
    )
    assert update.candidate is not None

    not_expired = runtime.get_selection(
        symbol="BTCUSDT",
        exchange="BINANCE",
        timeframe=MarketDataTimeframe.M5,
    )
    assert not_expired is not None
    assert not_expired.status == OpportunityStatus.SELECTED

    expired = runtime.expire_candidates(reference_time=generated_at + timedelta(seconds=60))
    assert len(expired) == 1
    assert expired[0].candidate is not None
    assert expired[0].candidate.status == OpportunityStatus.EXPIRED
    assert expired[0].candidate.reason_code == OpportunityReasonCode.OPPORTUNITY_EXPIRED
    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["expired_selection_keys"] == 1
    assert diagnostics["last_event_type"] == OpportunityEventType.OPPORTUNITY_INVALIDATED.value


def test_opportunity_runtime_marks_degraded_and_keeps_operator_truth_visible() -> None:
    runtime = OpportunityRuntime()

    asyncio.run(runtime.start())
    runtime.mark_degraded("intent_ingest_failed")
    diagnostics = runtime.get_runtime_diagnostics()

    assert diagnostics["ready"] is False
    assert diagnostics["lifecycle_state"] == OpportunityRuntimeLifecycleState.DEGRADED.value
    assert diagnostics["last_failure_reason"] == "intent_ingest_failed"
    assert diagnostics["degraded_reasons"] == ["intent_ingest_failed"]


def test_opportunity_runtime_uses_runtime_config_in_state_keying() -> None:
    runtime = create_opportunity_runtime(
        config=OpportunityRuntimeConfig(
            contour_name="custom_opportunity_contour",
            selection_name="custom_selection",
        )
    )
    asyncio.run(runtime.start())

    runtime.ingest_intent(
        intent=_make_execution_intent(),
        reference_time=datetime(2026, 3, 22, 12, 1, tzinfo=UTC),
    )

    candidate = runtime.get_selection(
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
    assert candidate.contour_name == "custom_opportunity_contour"
    assert candidate.selection_name == "custom_selection"
    assert context is not None
    assert context.contour_name == "custom_opportunity_contour"
    assert context.selection_name == "custom_selection"

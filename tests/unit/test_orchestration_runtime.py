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
    ExecutionValidity,
    ExecutionValidityStatus,
)
from cryptotechnolog.market_data import MarketDataTimeframe
from cryptotechnolog.opportunity import (
    OpportunityDirection,
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
    OrchestrationEventType,
    OrchestrationReasonCode,
    OrchestrationRuntime,
    OrchestrationRuntimeConfig,
    OrchestrationRuntimeLifecycleState,
    OrchestrationStatus,
    OrchestrationValidityStatus,
    create_orchestration_runtime,
)
from cryptotechnolog.signals import (
    SignalDirection,
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
    StrategyFreshness,
    StrategyReasonCode,
    StrategyValidity,
    StrategyValidityStatus,
)


def _build_signal_snapshot() -> SignalSnapshot:
    now = datetime.now(UTC)
    return SignalSnapshot(
        signal_id=SignalSnapshot.candidate(
            contour_name="phase8_signal_contour",
            symbol="BTCUSDT",
            exchange="BINANCE",
            timeframe=MarketDataTimeframe.M5,
            freshness=SignalFreshness(generated_at=now, expires_at=now + timedelta(minutes=5)),
            validity=SignalValidity(
                status=SignalValidityStatus.VALID,
                observed_inputs=4,
                required_inputs=4,
            ),
            direction=SignalDirection.BUY,
            confidence=Decimal("0.91"),
            entry_price=Decimal("100"),
            stop_loss=Decimal("95"),
            take_profit=Decimal("110"),
            reason_code=SignalReasonCode.CONTEXT_READY,
        ).signal_id,
        contour_name="phase8_signal_contour",
        symbol="BTCUSDT",
        exchange="BINANCE",
        timeframe=MarketDataTimeframe.M5,
        freshness=SignalFreshness(generated_at=now, expires_at=now + timedelta(minutes=5)),
        validity=SignalValidity(
            status=SignalValidityStatus.VALID,
            observed_inputs=4,
            required_inputs=4,
        ),
        status=SignalStatus.ACTIVE,
        direction=SignalDirection.BUY,
        confidence=Decimal("0.91"),
        entry_price=Decimal("100"),
        stop_loss=Decimal("95"),
        take_profit=Decimal("110"),
        reason_code=SignalReasonCode.CONTEXT_READY,
    )


def _build_strategy_candidate() -> StrategyActionCandidate:
    now = datetime.now(UTC)
    signal = _build_signal_snapshot()
    return StrategyActionCandidate.candidate(
        contour_name="phase9_strategy_contour",
        strategy_name="phase9_foundation_strategy",
        symbol="BTCUSDT",
        exchange="BINANCE",
        timeframe=MarketDataTimeframe.M5,
        freshness=StrategyFreshness(generated_at=now, expires_at=now + timedelta(minutes=5)),
        validity=StrategyValidity(
            status=StrategyValidityStatus.VALID,
            observed_inputs=1,
            required_inputs=1,
        ),
        direction=StrategyDirection.LONG,
        originating_signal_id=signal.signal_id,
        confidence=Decimal("0.88"),
        reason_code=StrategyReasonCode.CONTEXT_READY,
    )


def _build_execution_intent() -> ExecutionOrderIntent:
    now = datetime.now(UTC)
    candidate = _build_strategy_candidate()
    return ExecutionOrderIntent.candidate(
        contour_name="phase10_execution_contour",
        execution_name="phase10_foundation_execution",
        symbol="BTCUSDT",
        exchange="BINANCE",
        timeframe=MarketDataTimeframe.M5,
        freshness=ExecutionFreshness(generated_at=now, expires_at=now + timedelta(minutes=5)),
        validity=ExecutionValidity(
            status=ExecutionValidityStatus.VALID,
            observed_inputs=1,
            required_inputs=1,
        ),
        direction=ExecutionDirection.BUY,
        originating_candidate_id=candidate.candidate_id,
        confidence=Decimal("0.87"),
        reason_code=ExecutionReasonCode.CONTEXT_READY,
    )


def _make_opportunity_candidate(
    *,
    status: OpportunityStatus = OpportunityStatus.SELECTED,
    direction: OpportunityDirection | None = OpportunityDirection.LONG,
    confidence: str | None = "0.87",
    priority_score: str | None = "0.9100",
    generated_at: datetime | None = None,
    expires_at: datetime | None = None,
) -> OpportunitySelectionCandidate:
    now = generated_at or datetime(2026, 3, 22, 12, 0, tzinfo=UTC)
    intent = _build_execution_intent()
    validity = (
        OpportunityValidity(
            status=OpportunityValidityStatus.VALID,
            observed_inputs=1,
            required_inputs=1,
        )
        if status in {OpportunityStatus.SELECTED, OpportunityStatus.SUPPRESSED}
        else OpportunityValidity(
            status=OpportunityValidityStatus.INVALID,
            observed_inputs=1,
            required_inputs=1,
            invalid_reason="selection_lost",
        )
    )
    return OpportunitySelectionCandidate(
        selection_id=uuid4(),
        contour_name="phase11_opportunity_contour",
        selection_name="phase11_foundation_selection",
        symbol="BTCUSDT",
        exchange="BINANCE",
        timeframe=MarketDataTimeframe.M5,
        source=OpportunitySource.EXECUTION_INTENT,
        freshness=OpportunityFreshness(
            generated_at=now,
            expires_at=expires_at or (now + timedelta(minutes=5)),
        ),
        validity=validity,
        status=status,
        direction=direction,
        originating_intent_id=intent.intent_id if direction is not None else None,
        confidence=Decimal(confidence) if confidence is not None else None,
        priority_score=Decimal(priority_score) if priority_score is not None else None,
        reason_code=(
            OpportunityReasonCode.CONTEXT_READY
            if status == OpportunityStatus.SELECTED
            else OpportunityReasonCode.SELECTION_RULE_BLOCKED
        ),
    )


def test_orchestration_runtime_requires_explicit_start() -> None:
    runtime = create_orchestration_runtime()

    with pytest.raises(RuntimeError, match="не запущен"):
        runtime.ingest_selection(
            selection=_make_opportunity_candidate(),
            reference_time=datetime(2026, 3, 22, 12, 1, tzinfo=UTC),
        )


def test_orchestration_runtime_start_and_stop_reset_operator_state() -> None:
    runtime = create_orchestration_runtime()

    asyncio.run(runtime.start())
    runtime.mark_degraded("synthetic_failure")
    runtime.ingest_selection(
        selection=_make_opportunity_candidate(),
        reference_time=datetime(2026, 3, 22, 12, 1, tzinfo=UTC),
    )
    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["started"] is True
    assert diagnostics["tracked_decision_keys"] == 1

    asyncio.run(runtime.stop())
    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["started"] is False
    assert diagnostics["tracked_context_keys"] == 0
    assert diagnostics["tracked_decision_keys"] == 0
    assert diagnostics["forwarded_keys"] == 0
    assert diagnostics["abstained_keys"] == 0
    assert diagnostics["invalidated_decision_keys"] == 0
    assert diagnostics["expired_decision_keys"] == 0
    assert diagnostics["last_selection_id"] is None
    assert diagnostics["last_decision_id"] is None
    assert diagnostics["last_event_type"] is None
    assert diagnostics["last_failure_reason"] is None
    assert diagnostics["lifecycle_state"] == OrchestrationRuntimeLifecycleState.STOPPED.value
    assert diagnostics["readiness_reasons"] == ["runtime_stopped"]
    assert (
        runtime.get_decision(
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


def test_orchestration_runtime_builds_forwarded_decision_from_selected_opportunity() -> None:
    runtime = create_orchestration_runtime()
    asyncio.run(runtime.start())

    update = runtime.ingest_selection(
        selection=_make_opportunity_candidate(
            status=OpportunityStatus.SELECTED,
            direction=OpportunityDirection.LONG,
            confidence="0.88",
            priority_score="0.91",
        ),
        reference_time=datetime(2026, 3, 22, 12, 1, tzinfo=UTC),
    )

    assert update.decision is not None
    assert update.decision.status == OrchestrationStatus.ORCHESTRATED
    assert update.decision.decision == OrchestrationDecision.FORWARD
    assert update.event_type == OrchestrationEventType.ORCHESTRATION_DECIDED
    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["ready"] is True
    assert diagnostics["lifecycle_state"] == OrchestrationRuntimeLifecycleState.READY.value
    assert diagnostics["forwarded_keys"] == 1


def test_orchestration_runtime_returns_abstained_decision_when_selection_is_too_weak() -> None:
    runtime = create_orchestration_runtime(
        config=OrchestrationRuntimeConfig(
            min_selection_confidence_for_forward=Decimal("0.70"),
            min_priority_score_for_forward=Decimal("0.70"),
        )
    )
    asyncio.run(runtime.start())

    update = runtime.ingest_selection(
        selection=_make_opportunity_candidate(
            status=OpportunityStatus.SELECTED,
            confidence="0.40",
            priority_score="0.40",
        ),
        reference_time=datetime(2026, 3, 22, 12, 1, tzinfo=UTC),
    )

    assert update.decision is not None
    assert update.decision.status == OrchestrationStatus.ABSTAINED
    assert update.decision.decision == OrchestrationDecision.ABSTAIN
    assert update.decision.reason_code == OrchestrationReasonCode.ORCHESTRATION_ABSTAINED
    assert update.event_type == OrchestrationEventType.ORCHESTRATION_DECIDED


def test_orchestration_runtime_creates_warming_context_for_candidate_selection() -> None:
    runtime = create_orchestration_runtime()
    asyncio.run(runtime.start())

    update = runtime.ingest_selection(
        selection=_make_opportunity_candidate(
            status=OpportunityStatus.CANDIDATE,
            direction=None,
        ),
        reference_time=datetime(2026, 3, 22, 12, 1, tzinfo=UTC),
    )

    assert update.context.validity.status == OrchestrationValidityStatus.WARMING
    assert update.context.validity.missing_inputs == ("ready_opportunity",)
    assert update.decision is not None
    assert update.decision.status == OrchestrationStatus.CANDIDATE
    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["ready"] is False
    assert diagnostics["lifecycle_state"] == OrchestrationRuntimeLifecycleState.WARMING.value


def test_orchestration_runtime_invalidates_previous_decision_when_selection_breaks() -> None:
    runtime = create_orchestration_runtime()
    asyncio.run(runtime.start())

    first = runtime.ingest_selection(
        selection=_make_opportunity_candidate(),
        reference_time=datetime(2026, 3, 22, 12, 1, tzinfo=UTC),
    )
    assert first.decision is not None
    assert first.decision.status == OrchestrationStatus.ORCHESTRATED

    second = runtime.ingest_selection(
        selection=_make_opportunity_candidate(
            status=OpportunityStatus.INVALIDATED,
            direction=OpportunityDirection.LONG,
        ),
        reference_time=datetime(2026, 3, 22, 12, 2, tzinfo=UTC),
    )

    assert second.decision is not None
    assert second.decision.status == OrchestrationStatus.INVALIDATED
    assert second.decision.decision_id == first.decision.decision_id
    assert second.event_type == OrchestrationEventType.ORCHESTRATION_INVALIDATED
    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["ready"] is True
    assert diagnostics["invalidated_decision_keys"] == 1


def test_orchestration_runtime_expires_decision_only_against_reference_time() -> None:
    runtime = create_orchestration_runtime(
        config=OrchestrationRuntimeConfig(max_decision_age_seconds=60),
    )
    asyncio.run(runtime.start())

    generated_at = datetime(2026, 3, 22, 12, 0, tzinfo=UTC)
    update = runtime.ingest_selection(
        selection=_make_opportunity_candidate(
            generated_at=generated_at,
            expires_at=generated_at + timedelta(minutes=5),
        ),
        reference_time=generated_at,
    )
    assert update.decision is not None

    not_expired = runtime.get_decision(
        symbol="BTCUSDT",
        exchange="BINANCE",
        timeframe=MarketDataTimeframe.M5,
    )
    assert not_expired is not None
    assert not_expired.status == OrchestrationStatus.ORCHESTRATED

    expired = runtime.expire_decisions(reference_time=generated_at + timedelta(seconds=60))
    assert len(expired) == 1
    assert expired[0].decision is not None
    assert expired[0].decision.status == OrchestrationStatus.EXPIRED
    assert expired[0].decision.reason_code == OrchestrationReasonCode.ORCHESTRATION_EXPIRED
    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["expired_decision_keys"] == 1
    assert diagnostics["last_event_type"] == OrchestrationEventType.ORCHESTRATION_INVALIDATED.value


def test_orchestration_runtime_marks_degraded_and_keeps_operator_truth_visible() -> None:
    runtime = OrchestrationRuntime()

    asyncio.run(runtime.start())
    runtime.mark_degraded("selection_ingest_failed")
    diagnostics = runtime.get_runtime_diagnostics()

    assert diagnostics["ready"] is False
    assert diagnostics["lifecycle_state"] == OrchestrationRuntimeLifecycleState.DEGRADED.value
    assert diagnostics["last_failure_reason"] == "selection_ingest_failed"
    assert diagnostics["degraded_reasons"] == ["selection_ingest_failed"]


def test_orchestration_runtime_uses_runtime_config_in_state_keying() -> None:
    runtime = create_orchestration_runtime(
        config=OrchestrationRuntimeConfig(
            contour_name="custom_orchestration_contour",
            orchestration_name="custom_meta_orchestration",
        )
    )
    asyncio.run(runtime.start())

    runtime.ingest_selection(
        selection=_make_opportunity_candidate(),
        reference_time=datetime(2026, 3, 22, 12, 1, tzinfo=UTC),
    )

    decision = runtime.get_decision(
        symbol="BTCUSDT",
        exchange="BINANCE",
        timeframe=MarketDataTimeframe.M5,
    )
    context = runtime.get_context(
        symbol="BTCUSDT",
        exchange="BINANCE",
        timeframe=MarketDataTimeframe.M5,
    )

    assert decision is not None
    assert decision.contour_name == "custom_orchestration_contour"
    assert decision.orchestration_name == "custom_meta_orchestration"
    assert context is not None
    assert context.contour_name == "custom_orchestration_contour"
    assert context.orchestration_name == "custom_meta_orchestration"

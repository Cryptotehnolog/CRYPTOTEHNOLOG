from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from cryptotechnolog.execution import (
    ExecutionDirection,
    ExecutionEventType,
    ExecutionReasonCode,
    ExecutionRuntime,
    ExecutionRuntimeConfig,
    ExecutionRuntimeLifecycleState,
    ExecutionStatus,
    ExecutionValidityStatus,
    create_execution_runtime,
)
from cryptotechnolog.market_data import MarketDataTimeframe
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
    StrategyStatus,
    StrategyValidity,
    StrategyValidityStatus,
)


def _make_signal_snapshot() -> SignalSnapshot:
    now = datetime(2026, 3, 21, 12, 0, tzinfo=UTC)
    return SignalSnapshot(
        signal_id=SignalSnapshot.candidate(
            contour_name="phase8_signal_contour",
            symbol="BTCUSDT",
            exchange="BINANCE",
            timeframe=MarketDataTimeframe.M5,
            freshness=SignalFreshness(
                generated_at=now,
                expires_at=now + timedelta(minutes=5),
            ),
            validity=SignalValidity(
                status=SignalValidityStatus.VALID,
                observed_inputs=4,
                required_inputs=4,
            ),
            direction=SignalDirection.BUY,
            confidence=Decimal("0.80"),
            entry_price=Decimal("100"),
            stop_loss=Decimal("95"),
            take_profit=Decimal("110"),
            reason_code=SignalReasonCode.CONTEXT_READY,
        ).signal_id,
        contour_name="phase8_signal_contour",
        symbol="BTCUSDT",
        exchange="BINANCE",
        timeframe=MarketDataTimeframe.M5,
        freshness=SignalFreshness(
            generated_at=now,
            expires_at=now + timedelta(minutes=5),
        ),
        validity=SignalValidity(
            status=SignalValidityStatus.VALID,
            observed_inputs=4,
            required_inputs=4,
        ),
        status=SignalStatus.ACTIVE,
        direction=SignalDirection.BUY,
        confidence=Decimal("0.80"),
        entry_price=Decimal("100"),
        stop_loss=Decimal("95"),
        take_profit=Decimal("110"),
        reason_code=SignalReasonCode.CONTEXT_READY,
    )


def _make_candidate(
    *,
    status: StrategyStatus = StrategyStatus.ACTIONABLE,
    direction: StrategyDirection | None = StrategyDirection.LONG,
    confidence: str | None = "0.80",
    generated_at: datetime | None = None,
    expires_at: datetime | None = None,
) -> StrategyActionCandidate:
    now = generated_at or datetime(2026, 3, 21, 12, 0, tzinfo=UTC)
    signal = _make_signal_snapshot()
    validity = (
        StrategyValidity(
            status=StrategyValidityStatus.VALID,
            observed_inputs=1,
            required_inputs=1,
        )
        if status in {StrategyStatus.ACTIONABLE, StrategyStatus.SUPPRESSED}
        else StrategyValidity(
            status=StrategyValidityStatus.INVALID,
            observed_inputs=1,
            required_inputs=1,
            invalid_reason="candidate_lost",
        )
    )
    return StrategyActionCandidate(
        candidate_id=uuid4(),
        contour_name="phase9_strategy_contour",
        strategy_name="phase9_foundation_strategy",
        symbol="BTCUSDT",
        exchange="BINANCE",
        timeframe=MarketDataTimeframe.M5,
        freshness=StrategyFreshness(
            generated_at=now,
            expires_at=expires_at or (now + timedelta(minutes=5)),
        ),
        validity=validity,
        status=status,
        direction=direction,
        originating_signal_id=signal.signal_id if direction is not None else None,
        confidence=Decimal(confidence) if confidence is not None else None,
        reason_code=(
            StrategyReasonCode.CONTEXT_READY
            if status == StrategyStatus.ACTIONABLE
            else StrategyReasonCode.STRATEGY_RULE_BLOCKED
        ),
    )


def test_execution_runtime_requires_explicit_start() -> None:
    runtime = create_execution_runtime()

    with pytest.raises(RuntimeError, match="не запущен"):
        runtime.ingest_candidate(
            candidate=_make_candidate(),
            reference_time=datetime(2026, 3, 21, 12, 1, tzinfo=UTC),
        )


def test_execution_runtime_start_and_stop_reset_operator_state() -> None:
    runtime = create_execution_runtime()

    asyncio.run(runtime.start())
    runtime.mark_degraded("synthetic_failure")
    runtime.ingest_candidate(
        candidate=_make_candidate(),
        reference_time=datetime(2026, 3, 21, 12, 1, tzinfo=UTC),
    )
    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["started"] is True
    assert diagnostics["tracked_intent_keys"] == 1

    asyncio.run(runtime.stop())
    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["started"] is False
    assert diagnostics["tracked_context_keys"] == 0
    assert diagnostics["tracked_intent_keys"] == 0
    assert diagnostics["executable_intent_keys"] == 0
    assert diagnostics["invalidated_intent_keys"] == 0
    assert diagnostics["expired_intent_keys"] == 0
    assert diagnostics["last_candidate_id"] is None
    assert diagnostics["last_intent_id"] is None
    assert diagnostics["last_event_type"] is None
    assert diagnostics["last_failure_reason"] is None
    assert diagnostics["lifecycle_state"] == ExecutionRuntimeLifecycleState.STOPPED.value
    assert diagnostics["readiness_reasons"] == ["runtime_stopped"]
    assert (
        runtime.get_intent(
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


def test_execution_runtime_builds_executable_buy_intent_from_actionable_candidate() -> None:
    runtime = create_execution_runtime()
    asyncio.run(runtime.start())

    update = runtime.ingest_candidate(
        candidate=_make_candidate(
            status=StrategyStatus.ACTIONABLE, direction=StrategyDirection.LONG
        ),
        reference_time=datetime(2026, 3, 21, 12, 1, tzinfo=UTC),
    )

    assert update.intent is not None
    assert update.intent.status == ExecutionStatus.EXECUTABLE
    assert update.intent.direction == ExecutionDirection.BUY
    assert update.event_type == ExecutionEventType.EXECUTION_REQUESTED
    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["ready"] is True
    assert diagnostics["lifecycle_state"] == ExecutionRuntimeLifecycleState.READY.value
    assert diagnostics["executable_intent_keys"] == 1


def test_execution_runtime_returns_suppressed_intent_when_confidence_too_low() -> None:
    runtime = create_execution_runtime(
        config=ExecutionRuntimeConfig(min_candidate_confidence_for_execution=Decimal("0.70"))
    )
    asyncio.run(runtime.start())

    update = runtime.ingest_candidate(
        candidate=_make_candidate(confidence="0.40"),
        reference_time=datetime(2026, 3, 21, 12, 1, tzinfo=UTC),
    )

    assert update.intent is not None
    assert update.intent.status == ExecutionStatus.SUPPRESSED
    assert update.intent.direction is None
    assert update.event_type == ExecutionEventType.EXECUTION_INTENT_UPDATED


def test_execution_runtime_creates_warming_context_for_suppressed_candidate() -> None:
    runtime = create_execution_runtime()
    asyncio.run(runtime.start())

    update = runtime.ingest_candidate(
        candidate=_make_candidate(status=StrategyStatus.SUPPRESSED, direction=None),
        reference_time=datetime(2026, 3, 21, 12, 1, tzinfo=UTC),
    )

    assert update.context.validity.status == ExecutionValidityStatus.WARMING
    assert update.context.validity.missing_inputs == ("executable_candidate",)
    assert update.intent is not None
    assert update.intent.status == ExecutionStatus.CANDIDATE
    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["ready"] is False
    assert diagnostics["lifecycle_state"] == ExecutionRuntimeLifecycleState.WARMING.value


def test_execution_runtime_invalidates_previous_executable_intent_when_candidate_breaks() -> None:
    runtime = create_execution_runtime()
    asyncio.run(runtime.start())

    first = runtime.ingest_candidate(
        candidate=_make_candidate(),
        reference_time=datetime(2026, 3, 21, 12, 1, tzinfo=UTC),
    )
    assert first.intent is not None
    assert first.intent.status == ExecutionStatus.EXECUTABLE

    second = runtime.ingest_candidate(
        candidate=_make_candidate(
            status=StrategyStatus.INVALIDATED,
            direction=StrategyDirection.LONG,
        ),
        reference_time=datetime(2026, 3, 21, 12, 2, tzinfo=UTC),
    )

    assert second.intent is not None
    assert second.intent.status == ExecutionStatus.INVALIDATED
    assert second.intent.intent_id == first.intent.intent_id
    assert second.event_type == ExecutionEventType.EXECUTION_INVALIDATED
    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["ready"] is False
    assert diagnostics["lifecycle_state"] == ExecutionRuntimeLifecycleState.DEGRADED.value
    assert diagnostics["invalidated_intent_keys"] == 1


def test_execution_runtime_expires_intent_only_against_reference_time() -> None:
    runtime = create_execution_runtime(
        config=ExecutionRuntimeConfig(max_intent_age_seconds=60),
    )
    asyncio.run(runtime.start())

    generated_at = datetime(2026, 3, 21, 12, 0, tzinfo=UTC)
    update = runtime.ingest_candidate(
        candidate=_make_candidate(
            generated_at=generated_at,
            expires_at=generated_at + timedelta(minutes=5),
        ),
        reference_time=generated_at,
    )
    assert update.intent is not None

    not_expired = runtime.get_intent(
        symbol="BTCUSDT",
        exchange="BINANCE",
        timeframe=MarketDataTimeframe.M5,
    )
    assert not_expired is not None
    assert not_expired.status == ExecutionStatus.EXECUTABLE

    expired = runtime.expire_intents(reference_time=generated_at + timedelta(seconds=60))
    assert len(expired) == 1
    assert expired[0].status == ExecutionStatus.EXPIRED
    assert expired[0].reason_code == ExecutionReasonCode.EXECUTION_EXPIRED
    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["expired_intent_keys"] == 1
    assert diagnostics["last_event_type"] == ExecutionEventType.EXECUTION_INVALIDATED.value


def test_execution_runtime_marks_degraded_and_keeps_operator_truth_visible() -> None:
    runtime = ExecutionRuntime()

    asyncio.run(runtime.start())
    runtime.mark_degraded("candidate_ingest_failed")
    diagnostics = runtime.get_runtime_diagnostics()

    assert diagnostics["ready"] is False
    assert diagnostics["lifecycle_state"] == ExecutionRuntimeLifecycleState.DEGRADED.value
    assert diagnostics["last_failure_reason"] == "candidate_ingest_failed"
    assert diagnostics["degraded_reasons"] == ["candidate_ingest_failed"]

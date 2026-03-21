from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

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
    StrategyDirection,
    StrategyEventType,
    StrategyReasonCode,
    StrategyRuntime,
    StrategyRuntimeConfig,
    StrategyRuntimeLifecycleState,
    StrategyStatus,
    StrategyValidityStatus,
    create_strategy_runtime,
)


def _make_signal(
    *,
    status: SignalStatus = SignalStatus.ACTIVE,
    direction: SignalDirection | None = SignalDirection.BUY,
    confidence: str | None = "0.80",
    generated_at: datetime | None = None,
    expires_at: datetime | None = None,
) -> SignalSnapshot:
    now = generated_at or datetime(2026, 3, 21, 12, 0, tzinfo=UTC)
    return SignalSnapshot(
        signal_id=SignalSnapshot.candidate(
            contour_name="phase8_signal_contour",
            symbol="BTCUSDT",
            exchange="BINANCE",
            timeframe=MarketDataTimeframe.M5,
            freshness=SignalFreshness(
                generated_at=now,
                expires_at=expires_at or (now + timedelta(minutes=5)),
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
            expires_at=expires_at or (now + timedelta(minutes=5)),
        ),
        validity=SignalValidity(
            status=(
                SignalValidityStatus.VALID
                if status in {SignalStatus.ACTIVE, SignalStatus.SUPPRESSED}
                else SignalValidityStatus.INVALID
            ),
            observed_inputs=4,
            required_inputs=4,
            invalid_reason=(
                None if status in {SignalStatus.ACTIVE, SignalStatus.SUPPRESSED} else "signal_lost"
            ),
        ),
        status=status,
        direction=direction,
        confidence=Decimal(confidence) if confidence is not None else None,
        entry_price=Decimal("100")
        if direction is not None and status == SignalStatus.ACTIVE
        else None,
        stop_loss=Decimal("95")
        if direction is not None and status == SignalStatus.ACTIVE
        else None,
        take_profit=Decimal("110")
        if direction is not None and status == SignalStatus.ACTIVE
        else None,
        reason_code=(
            SignalReasonCode.CONTEXT_READY
            if status == SignalStatus.ACTIVE
            else SignalReasonCode.SIGNAL_RULE_BLOCKED
        ),
    )


def test_strategy_runtime_requires_explicit_start() -> None:
    runtime = create_strategy_runtime()

    with pytest.raises(RuntimeError, match="не запущен"):
        runtime.ingest_signal(
            signal=_make_signal(),
            reference_time=datetime(2026, 3, 21, 12, 1, tzinfo=UTC),
        )


def test_strategy_runtime_start_and_stop_reset_operator_state() -> None:
    runtime = create_strategy_runtime()

    asyncio.run(runtime.start())
    runtime.mark_degraded("synthetic_failure")
    runtime.ingest_signal(
        signal=_make_signal(),
        reference_time=datetime(2026, 3, 21, 12, 1, tzinfo=UTC),
    )
    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["started"] is True
    assert diagnostics["tracked_candidate_keys"] == 1

    asyncio.run(runtime.stop())
    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["started"] is False
    assert diagnostics["tracked_context_keys"] == 0
    assert diagnostics["tracked_candidate_keys"] == 0
    assert diagnostics["actionable_candidate_keys"] == 0
    assert diagnostics["invalidated_candidate_keys"] == 0
    assert diagnostics["expired_candidate_keys"] == 0
    assert diagnostics["last_signal_id"] is None
    assert diagnostics["last_candidate_id"] is None
    assert diagnostics["last_event_type"] is None
    assert diagnostics["last_failure_reason"] is None
    assert diagnostics["lifecycle_state"] == StrategyRuntimeLifecycleState.STOPPED.value
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


def test_strategy_runtime_builds_actionable_long_candidate_from_active_signal() -> None:
    runtime = create_strategy_runtime()
    asyncio.run(runtime.start())

    update = runtime.ingest_signal(
        signal=_make_signal(status=SignalStatus.ACTIVE, direction=SignalDirection.BUY),
        reference_time=datetime(2026, 3, 21, 12, 1, tzinfo=UTC),
    )

    assert update.candidate is not None
    assert update.candidate.status == StrategyStatus.ACTIONABLE
    assert update.candidate.direction == StrategyDirection.LONG
    assert update.event_type == StrategyEventType.STRATEGY_ACTIONABLE
    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["ready"] is True
    assert diagnostics["lifecycle_state"] == StrategyRuntimeLifecycleState.READY.value
    assert diagnostics["actionable_candidate_keys"] == 1


def test_strategy_runtime_returns_suppressed_candidate_when_confidence_too_low() -> None:
    runtime = create_strategy_runtime(
        config=StrategyRuntimeConfig(min_signal_confidence_for_actionable=Decimal("0.70"))
    )
    asyncio.run(runtime.start())

    update = runtime.ingest_signal(
        signal=_make_signal(confidence="0.40"),
        reference_time=datetime(2026, 3, 21, 12, 1, tzinfo=UTC),
    )

    assert update.candidate is not None
    assert update.candidate.status == StrategyStatus.SUPPRESSED
    assert update.candidate.direction is None
    assert update.event_type == StrategyEventType.STRATEGY_CANDIDATE_UPDATED


def test_strategy_runtime_creates_warming_context_for_suppressed_signal() -> None:
    runtime = create_strategy_runtime()
    asyncio.run(runtime.start())

    update = runtime.ingest_signal(
        signal=_make_signal(status=SignalStatus.SUPPRESSED, direction=None),
        reference_time=datetime(2026, 3, 21, 12, 1, tzinfo=UTC),
    )

    assert update.context.validity.status == StrategyValidityStatus.WARMING
    assert update.context.validity.missing_inputs == ("actionable_signal",)
    assert update.candidate is not None
    assert update.candidate.status == StrategyStatus.CANDIDATE
    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["ready"] is False
    assert diagnostics["lifecycle_state"] == StrategyRuntimeLifecycleState.WARMING.value


def test_strategy_runtime_invalidates_previous_actionable_candidate_when_signal_breaks() -> None:
    runtime = create_strategy_runtime()
    asyncio.run(runtime.start())

    first = runtime.ingest_signal(
        signal=_make_signal(),
        reference_time=datetime(2026, 3, 21, 12, 1, tzinfo=UTC),
    )
    assert first.candidate is not None
    assert first.candidate.status == StrategyStatus.ACTIONABLE

    second = runtime.ingest_signal(
        signal=_make_signal(status=SignalStatus.INVALIDATED, direction=SignalDirection.BUY),
        reference_time=datetime(2026, 3, 21, 12, 2, tzinfo=UTC),
    )

    assert second.candidate is not None
    assert second.candidate.status == StrategyStatus.INVALIDATED
    assert second.candidate.candidate_id == first.candidate.candidate_id
    assert second.event_type == StrategyEventType.STRATEGY_INVALIDATED
    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["ready"] is False
    assert diagnostics["lifecycle_state"] == StrategyRuntimeLifecycleState.DEGRADED.value
    assert diagnostics["invalidated_candidate_keys"] == 1


def test_strategy_runtime_expires_candidate_only_against_reference_time() -> None:
    runtime = create_strategy_runtime(
        config=StrategyRuntimeConfig(max_candidate_age_seconds=60),
    )
    asyncio.run(runtime.start())

    generated_at = datetime(2026, 3, 21, 12, 0, tzinfo=UTC)
    update = runtime.ingest_signal(
        signal=_make_signal(
            generated_at=generated_at, expires_at=generated_at + timedelta(minutes=5)
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
    assert not_expired.status == StrategyStatus.ACTIONABLE

    expired = runtime.expire_candidates(reference_time=generated_at + timedelta(seconds=60))
    assert len(expired) == 1
    assert expired[0].status == StrategyStatus.EXPIRED
    assert expired[0].reason_code == StrategyReasonCode.STRATEGY_EXPIRED
    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["expired_candidate_keys"] == 1
    assert diagnostics["last_event_type"] == StrategyEventType.STRATEGY_INVALIDATED.value


def test_strategy_runtime_marks_degraded_and_keeps_operator_truth_visible() -> None:
    runtime = StrategyRuntime()

    asyncio.run(runtime.start())
    runtime.mark_degraded("signal_ingest_failed")
    diagnostics = runtime.get_runtime_diagnostics()

    assert diagnostics["ready"] is False
    assert diagnostics["lifecycle_state"] == StrategyRuntimeLifecycleState.DEGRADED.value
    assert diagnostics["last_failure_reason"] == "signal_ingest_failed"
    assert diagnostics["degraded_reasons"] == ["signal_ingest_failed"]

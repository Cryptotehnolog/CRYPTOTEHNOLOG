from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from cryptotechnolog.core.event import Priority
from cryptotechnolog.execution import (
    ExecutionContext,
    ExecutionDirection,
    ExecutionEventType,
    ExecutionFreshness,
    ExecutionOrderIntent,
    ExecutionOrderIntentPayload,
    ExecutionReasonCode,
    ExecutionRuntimeConfig,
    ExecutionRuntimeDiagnostics,
    ExecutionRuntimeLifecycleState,
    ExecutionRuntimeUpdate,
    ExecutionStatus,
    ExecutionValidity,
    ExecutionValidityStatus,
    build_execution_event,
    default_priority_for_execution_event,
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
        freshness=StrategyFreshness(
            generated_at=now,
            expires_at=now + timedelta(minutes=5),
        ),
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


class TestExecutionContracts:
    def test_execution_validity_readiness_ratio_is_normalized(self) -> None:
        validity = ExecutionValidity(
            status=ExecutionValidityStatus.WARMING,
            observed_inputs=1,
            required_inputs=3,
            missing_inputs=("candidate", "reference_time"),
        )

        assert validity.is_valid is False
        assert validity.is_warming is True
        assert validity.missing_inputs_count == 2
        assert validity.readiness_ratio == Decimal("0.3333")

    def test_execution_freshness_requires_reference_time_for_expiry(self) -> None:
        now = datetime.now(UTC)
        freshness = ExecutionFreshness(
            generated_at=now,
            expires_at=now + timedelta(minutes=1),
        )

        assert freshness.has_structurally_valid_expiry_window is True
        assert freshness.is_expired_at(now + timedelta(minutes=2)) is True
        assert freshness.is_expired_at(now + timedelta(seconds=30)) is False

    def test_valid_execution_context_requires_actionable_strategy_candidate(self) -> None:
        candidate = _build_strategy_candidate()
        context = ExecutionContext(
            execution_name="phase10_foundation_execution",
            contour_name="phase10_execution_contour",
            symbol="BTCUSDT",
            exchange="BINANCE",
            timeframe=MarketDataTimeframe.M5,
            observed_at=datetime.now(UTC),
            candidate=candidate,
            validity=ExecutionValidity(
                status=ExecutionValidityStatus.VALID,
                observed_inputs=1,
                required_inputs=1,
            ),
        )

        assert context.validity.is_valid is True
        assert context.candidate.is_actionable is True

    def test_executable_intent_requires_direction_and_candidate_id(self) -> None:
        now = datetime.now(UTC)
        candidate = _build_strategy_candidate()

        intent = ExecutionOrderIntent.candidate(
            contour_name="phase10_execution_contour",
            execution_name="phase10_foundation_execution",
            symbol="BTCUSDT",
            exchange="BINANCE",
            timeframe=MarketDataTimeframe.M5,
            freshness=ExecutionFreshness(
                generated_at=now,
                expires_at=now + timedelta(minutes=5),
            ),
            validity=ExecutionValidity(
                status=ExecutionValidityStatus.VALID,
                observed_inputs=1,
                required_inputs=1,
            ),
            direction=ExecutionDirection.BUY,
            originating_candidate_id=candidate.candidate_id,
            confidence=Decimal("0.88"),
            reason_code=ExecutionReasonCode.CONTEXT_READY,
        )

        assert intent.status == ExecutionStatus.EXECUTABLE
        assert intent.is_executable is True

    def test_invalidated_intent_cannot_keep_validity_valid(self) -> None:
        now = datetime.now(UTC)

        with pytest.raises(ValueError, match="INVALIDATED"):
            ExecutionOrderIntent(
                intent_id=ExecutionOrderIntent.candidate(
                    contour_name="phase10_execution_contour",
                    execution_name="phase10_foundation_execution",
                    symbol="BTCUSDT",
                    exchange="BINANCE",
                    timeframe=MarketDataTimeframe.M5,
                    freshness=ExecutionFreshness(generated_at=now),
                    validity=ExecutionValidity(
                        status=ExecutionValidityStatus.WARMING,
                        observed_inputs=0,
                        required_inputs=1,
                    ),
                ).intent_id,
                contour_name="phase10_execution_contour",
                execution_name="phase10_foundation_execution",
                symbol="BTCUSDT",
                exchange="BINANCE",
                timeframe=MarketDataTimeframe.M5,
                freshness=ExecutionFreshness(generated_at=now),
                validity=ExecutionValidity(
                    status=ExecutionValidityStatus.VALID,
                    observed_inputs=1,
                    required_inputs=1,
                ),
                status=ExecutionStatus.INVALIDATED,
                reason_code=ExecutionReasonCode.EXECUTION_INVALIDATED,
            )


class TestExecutionEventsAndRuntimeShape:
    def test_execution_event_payload_is_transport_compatible(self) -> None:
        now = datetime.now(UTC)
        candidate = _build_strategy_candidate()
        intent = ExecutionOrderIntent.candidate(
            contour_name="phase10_execution_contour",
            execution_name="phase10_foundation_execution",
            symbol="BTCUSDT",
            exchange="BINANCE",
            timeframe=MarketDataTimeframe.M5,
            freshness=ExecutionFreshness(
                generated_at=now,
                expires_at=now + timedelta(minutes=5),
            ),
            validity=ExecutionValidity(
                status=ExecutionValidityStatus.VALID,
                observed_inputs=1,
                required_inputs=1,
            ),
            direction=ExecutionDirection.BUY,
            originating_candidate_id=candidate.candidate_id,
            reason_code=ExecutionReasonCode.CONTEXT_READY,
        )

        payload = ExecutionOrderIntentPayload.from_intent(intent)
        event = build_execution_event(
            event_type=ExecutionEventType.EXECUTION_REQUESTED,
            payload=payload,
        )

        assert event.event_type == ExecutionEventType.EXECUTION_REQUESTED.value
        assert event.priority == Priority.HIGH
        assert event.payload["symbol"] == "BTCUSDT"
        assert event.payload["execution_name"] == "phase10_foundation_execution"

    def test_default_priority_for_execution_event_is_narrow_and_predictable(self) -> None:
        assert (
            default_priority_for_execution_event(ExecutionEventType.EXECUTION_REQUESTED)
            == Priority.HIGH
        )
        assert (
            default_priority_for_execution_event(ExecutionEventType.EXECUTION_INTENT_UPDATED)
            == Priority.NORMAL
        )

    def test_strategy_direction_is_normalized_to_execution_direction(self) -> None:
        assert (
            ExecutionOrderIntent.direction_from_strategy(StrategyDirection.LONG)
            == ExecutionDirection.BUY
        )
        assert (
            ExecutionOrderIntent.direction_from_strategy(StrategyDirection.SHORT)
            == ExecutionDirection.SELL
        )

    def test_runtime_boundary_shape_is_explicit(self) -> None:
        config = ExecutionRuntimeConfig()
        diagnostics = ExecutionRuntimeDiagnostics(
            started=True,
            ready=False,
            lifecycle_state=ExecutionRuntimeLifecycleState.WARMING,
            readiness_reasons=("waiting_for_strategy_truth",),
        )
        context = ExecutionContext(
            execution_name=config.execution_name,
            contour_name=config.contour_name,
            symbol="BTCUSDT",
            exchange="BINANCE",
            timeframe=MarketDataTimeframe.M5,
            observed_at=datetime.now(UTC),
            candidate=_build_strategy_candidate(),
            validity=ExecutionValidity(
                status=ExecutionValidityStatus.VALID,
                observed_inputs=1,
                required_inputs=1,
            ),
        )
        intent = ExecutionOrderIntent.candidate(
            contour_name=config.contour_name,
            execution_name=config.execution_name,
            symbol="BTCUSDT",
            exchange="BINANCE",
            timeframe=MarketDataTimeframe.M5,
            freshness=ExecutionFreshness(generated_at=datetime.now(UTC)),
            validity=ExecutionValidity(
                status=ExecutionValidityStatus.VALID,
                observed_inputs=1,
                required_inputs=1,
            ),
            direction=ExecutionDirection.BUY,
            originating_candidate_id=context.candidate.candidate_id,
            reason_code=ExecutionReasonCode.CONTEXT_READY,
        )
        update = ExecutionRuntimeUpdate(
            context=context,
            intent=intent,
            event_type=ExecutionEventType.EXECUTION_REQUESTED,
            emitted_payload=None,
        )

        assert config.contour_name == "phase10_execution_contour"
        assert diagnostics.to_dict()["lifecycle_state"] == ExecutionRuntimeLifecycleState.WARMING
        assert update.intent is intent

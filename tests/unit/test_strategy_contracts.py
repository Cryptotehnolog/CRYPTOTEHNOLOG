from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from cryptotechnolog.core.event import Priority
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
    StrategyActionCandidatePayload,
    StrategyContext,
    StrategyDirection,
    StrategyEventType,
    StrategyFreshness,
    StrategyReasonCode,
    StrategyRuntimeConfig,
    StrategyRuntimeDiagnostics,
    StrategyRuntimeLifecycleState,
    StrategyRuntimeUpdate,
    StrategyStatus,
    StrategyValidity,
    StrategyValidityStatus,
    build_strategy_event,
    default_priority_for_strategy_event,
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


class TestStrategyContracts:
    def test_strategy_validity_readiness_ratio_is_normalized(self) -> None:
        validity = StrategyValidity(
            status=StrategyValidityStatus.WARMING,
            observed_inputs=1,
            required_inputs=3,
            missing_inputs=("signal", "reference_time"),
        )

        assert validity.is_valid is False
        assert validity.is_warming is True
        assert validity.missing_inputs_count == 2
        assert validity.readiness_ratio == Decimal("0.3333")

    def test_strategy_freshness_requires_reference_time_for_expiry(self) -> None:
        now = datetime.now(UTC)
        freshness = StrategyFreshness(
            generated_at=now,
            expires_at=now + timedelta(minutes=1),
        )

        assert freshness.has_structurally_valid_expiry_window is True
        assert freshness.is_expired_at(now + timedelta(minutes=2)) is True
        assert freshness.is_expired_at(now + timedelta(seconds=30)) is False

    def test_valid_strategy_context_requires_actionable_signal(self) -> None:
        signal = _build_signal_snapshot()
        context = StrategyContext(
            strategy_name="phase9_foundation_strategy",
            contour_name="phase9_strategy_contour",
            symbol="BTCUSDT",
            exchange="BINANCE",
            timeframe=MarketDataTimeframe.M5,
            observed_at=datetime.now(UTC),
            signal=signal,
            validity=StrategyValidity(
                status=StrategyValidityStatus.VALID,
                observed_inputs=1,
                required_inputs=1,
            ),
        )

        assert context.validity.is_valid is True
        assert context.signal.is_actionable is True

    def test_actionable_candidate_requires_direction_and_signal_id(self) -> None:
        now = datetime.now(UTC)
        signal = _build_signal_snapshot()

        candidate = StrategyActionCandidate.candidate(
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

        assert candidate.status == StrategyStatus.ACTIONABLE
        assert candidate.is_actionable is True

    def test_invalidated_candidate_cannot_keep_validity_valid(self) -> None:
        now = datetime.now(UTC)

        with pytest.raises(ValueError, match="INVALIDATED"):
            StrategyActionCandidate(
                candidate_id=StrategyActionCandidate.candidate(
                    contour_name="phase9_strategy_contour",
                    strategy_name="phase9_foundation_strategy",
                    symbol="BTCUSDT",
                    exchange="BINANCE",
                    timeframe=MarketDataTimeframe.M5,
                    freshness=StrategyFreshness(generated_at=now),
                    validity=StrategyValidity(
                        status=StrategyValidityStatus.WARMING,
                        observed_inputs=0,
                        required_inputs=1,
                    ),
                ).candidate_id,
                contour_name="phase9_strategy_contour",
                strategy_name="phase9_foundation_strategy",
                symbol="BTCUSDT",
                exchange="BINANCE",
                timeframe=MarketDataTimeframe.M5,
                freshness=StrategyFreshness(generated_at=now),
                validity=StrategyValidity(
                    status=StrategyValidityStatus.VALID,
                    observed_inputs=1,
                    required_inputs=1,
                ),
                status=StrategyStatus.INVALIDATED,
                reason_code=StrategyReasonCode.STRATEGY_INVALIDATED,
            )


class TestStrategyEventsAndRuntimeShape:
    def test_strategy_event_payload_is_transport_compatible(self) -> None:
        now = datetime.now(UTC)
        signal = _build_signal_snapshot()
        candidate = StrategyActionCandidate.candidate(
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
            reason_code=StrategyReasonCode.CONTEXT_READY,
        )

        payload = StrategyActionCandidatePayload.from_candidate(candidate)
        event = build_strategy_event(
            event_type=StrategyEventType.STRATEGY_ACTIONABLE,
            payload=payload,
        )

        assert event.event_type == StrategyEventType.STRATEGY_ACTIONABLE.value
        assert event.priority == Priority.HIGH
        assert event.payload["symbol"] == "BTCUSDT"
        assert event.payload["strategy_name"] == "phase9_foundation_strategy"

    def test_default_priority_for_strategy_event_is_narrow_and_predictable(self) -> None:
        assert (
            default_priority_for_strategy_event(StrategyEventType.STRATEGY_ACTIONABLE)
            == Priority.HIGH
        )
        assert (
            default_priority_for_strategy_event(StrategyEventType.STRATEGY_CANDIDATE_UPDATED)
            == Priority.NORMAL
        )

    def test_runtime_boundary_shape_is_explicit(self) -> None:
        config = StrategyRuntimeConfig()
        diagnostics = StrategyRuntimeDiagnostics(
            started=True,
            ready=False,
            lifecycle_state=StrategyRuntimeLifecycleState.WARMING,
            readiness_reasons=("waiting_for_signal_truth",),
        )
        context = StrategyContext(
            strategy_name=config.strategy_name,
            contour_name=config.contour_name,
            symbol="BTCUSDT",
            exchange="BINANCE",
            timeframe=MarketDataTimeframe.M5,
            observed_at=datetime.now(UTC),
            signal=_build_signal_snapshot(),
            validity=StrategyValidity(
                status=StrategyValidityStatus.VALID,
                observed_inputs=1,
                required_inputs=1,
            ),
        )
        candidate = StrategyActionCandidate.candidate(
            contour_name=config.contour_name,
            strategy_name=config.strategy_name,
            symbol="BTCUSDT",
            exchange="BINANCE",
            timeframe=MarketDataTimeframe.M5,
            freshness=StrategyFreshness(generated_at=datetime.now(UTC)),
            validity=StrategyValidity(
                status=StrategyValidityStatus.VALID,
                observed_inputs=1,
                required_inputs=1,
            ),
            direction=StrategyDirection.LONG,
            originating_signal_id=context.signal.signal_id,
            reason_code=StrategyReasonCode.CONTEXT_READY,
        )
        update = StrategyRuntimeUpdate(
            context=context,
            candidate=candidate,
            event_type=StrategyEventType.STRATEGY_ACTIONABLE,
            emitted_payload=None,
        )

        assert config.contour_name == "phase9_strategy_contour"
        assert diagnostics.to_dict()["lifecycle_state"] == StrategyRuntimeLifecycleState.WARMING
        assert update.candidate is candidate

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from cryptotechnolog.core.event import Priority
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
    OpportunityContext,
    OpportunityDirection,
    OpportunityEventType,
    OpportunityFreshness,
    OpportunityReasonCode,
    OpportunityRuntimeConfig,
    OpportunityRuntimeDiagnostics,
    OpportunityRuntimeLifecycleState,
    OpportunityRuntimeUpdate,
    OpportunitySelectionCandidate,
    OpportunitySelectionPayload,
    OpportunitySource,
    OpportunityStatus,
    OpportunityValidity,
    OpportunityValidityStatus,
    build_opportunity_event,
    default_priority_for_opportunity_event,
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


class TestOpportunityContracts:
    def test_opportunity_validity_readiness_ratio_is_normalized(self) -> None:
        validity = OpportunityValidity(
            status=OpportunityValidityStatus.WARMING,
            observed_inputs=1,
            required_inputs=3,
            missing_inputs=("intent", "reference_time"),
        )

        assert validity.is_valid is False
        assert validity.is_warming is True
        assert validity.missing_inputs_count == 2
        assert validity.readiness_ratio == Decimal("0.3333")

    def test_opportunity_freshness_requires_reference_time_for_expiry(self) -> None:
        now = datetime.now(UTC)
        freshness = OpportunityFreshness(generated_at=now, expires_at=now + timedelta(minutes=1))

        assert freshness.has_structurally_valid_expiry_window is True
        assert freshness.is_expired_at(now + timedelta(minutes=2)) is True
        assert freshness.is_expired_at(now + timedelta(seconds=30)) is False

    def test_valid_opportunity_context_requires_executable_intent(self) -> None:
        intent = _build_execution_intent()
        context = OpportunityContext(
            selection_name="phase11_foundation_selection",
            contour_name="phase11_opportunity_contour",
            symbol="BTCUSDT",
            exchange="BINANCE",
            timeframe=MarketDataTimeframe.M5,
            observed_at=datetime.now(UTC),
            source=OpportunitySource.EXECUTION_INTENT,
            intent=intent,
            validity=OpportunityValidity(
                status=OpportunityValidityStatus.VALID,
                observed_inputs=1,
                required_inputs=1,
            ),
        )

        assert context.validity.is_valid is True
        assert context.intent.is_executable is True

    def test_selected_candidate_requires_direction_and_intent_id(self) -> None:
        now = datetime.now(UTC)
        intent = _build_execution_intent()
        candidate = OpportunitySelectionCandidate.candidate(
            contour_name="phase11_opportunity_contour",
            selection_name="phase11_foundation_selection",
            symbol="BTCUSDT",
            exchange="BINANCE",
            timeframe=MarketDataTimeframe.M5,
            source=OpportunitySource.EXECUTION_INTENT,
            freshness=OpportunityFreshness(generated_at=now, expires_at=now + timedelta(minutes=5)),
            validity=OpportunityValidity(
                status=OpportunityValidityStatus.VALID,
                observed_inputs=1,
                required_inputs=1,
            ),
            direction=OpportunityDirection.LONG,
            originating_intent_id=intent.intent_id,
            confidence=Decimal("0.87"),
            priority_score=Decimal("0.9100"),
            reason_code=OpportunityReasonCode.CONTEXT_READY,
        )

        assert candidate.status == OpportunityStatus.SELECTED
        assert candidate.is_selected is True

    def test_invalidated_candidate_cannot_keep_validity_valid(self) -> None:
        now = datetime.now(UTC)
        with pytest.raises(ValueError, match="INVALIDATED"):
            OpportunitySelectionCandidate(
                selection_id=OpportunitySelectionCandidate.candidate(
                    contour_name="phase11_opportunity_contour",
                    selection_name="phase11_foundation_selection",
                    symbol="BTCUSDT",
                    exchange="BINANCE",
                    timeframe=MarketDataTimeframe.M5,
                    source=OpportunitySource.EXECUTION_INTENT,
                    freshness=OpportunityFreshness(generated_at=now),
                    validity=OpportunityValidity(
                        status=OpportunityValidityStatus.WARMING,
                        observed_inputs=0,
                        required_inputs=1,
                    ),
                ).selection_id,
                contour_name="phase11_opportunity_contour",
                selection_name="phase11_foundation_selection",
                symbol="BTCUSDT",
                exchange="BINANCE",
                timeframe=MarketDataTimeframe.M5,
                source=OpportunitySource.EXECUTION_INTENT,
                freshness=OpportunityFreshness(generated_at=now),
                validity=OpportunityValidity(
                    status=OpportunityValidityStatus.VALID,
                    observed_inputs=1,
                    required_inputs=1,
                ),
                status=OpportunityStatus.INVALIDATED,
                reason_code=OpportunityReasonCode.OPPORTUNITY_INVALIDATED,
            )


class TestOpportunityEventsAndRuntimeShape:
    def test_opportunity_event_payload_is_transport_compatible(self) -> None:
        now = datetime.now(UTC)
        intent = _build_execution_intent()
        candidate = OpportunitySelectionCandidate.candidate(
            contour_name="phase11_opportunity_contour",
            selection_name="phase11_foundation_selection",
            symbol="BTCUSDT",
            exchange="BINANCE",
            timeframe=MarketDataTimeframe.M5,
            source=OpportunitySource.EXECUTION_INTENT,
            freshness=OpportunityFreshness(generated_at=now, expires_at=now + timedelta(minutes=5)),
            validity=OpportunityValidity(
                status=OpportunityValidityStatus.VALID,
                observed_inputs=1,
                required_inputs=1,
            ),
            direction=OpportunityDirection.LONG,
            originating_intent_id=intent.intent_id,
            reason_code=OpportunityReasonCode.CONTEXT_READY,
        )

        payload = OpportunitySelectionPayload.from_candidate(candidate)
        event = build_opportunity_event(
            event_type=OpportunityEventType.OPPORTUNITY_SELECTED,
            payload=payload,
        )

        assert event.event_type == OpportunityEventType.OPPORTUNITY_SELECTED.value
        assert event.priority == Priority.HIGH
        assert event.payload["symbol"] == "BTCUSDT"
        assert event.payload["selection_name"] == "phase11_foundation_selection"

    def test_default_priority_for_opportunity_event_is_narrow_and_predictable(self) -> None:
        assert (
            default_priority_for_opportunity_event(OpportunityEventType.OPPORTUNITY_SELECTED)
            == Priority.HIGH
        )
        assert (
            default_priority_for_opportunity_event(
                OpportunityEventType.OPPORTUNITY_CANDIDATE_UPDATED
            )
            == Priority.NORMAL
        )
        assert (
            default_priority_for_opportunity_event(OpportunityEventType.OPPORTUNITY_INVALIDATED)
            == Priority.NORMAL
        )

    def test_execution_direction_is_normalized_to_opportunity_direction(self) -> None:
        assert (
            OpportunitySelectionCandidate.direction_from_execution(ExecutionDirection.BUY)
            == OpportunityDirection.LONG
        )
        assert (
            OpportunitySelectionCandidate.direction_from_execution(ExecutionDirection.SELL)
            == OpportunityDirection.SHORT
        )

    def test_runtime_boundary_shape_is_explicit(self) -> None:
        config = OpportunityRuntimeConfig()
        diagnostics = OpportunityRuntimeDiagnostics()
        update = OpportunityRuntimeUpdate(
            context=OpportunityContext(
                selection_name="phase11_foundation_selection",
                contour_name="phase11_opportunity_contour",
                symbol="BTCUSDT",
                exchange="BINANCE",
                timeframe=MarketDataTimeframe.M5,
                observed_at=datetime.now(UTC),
                source=OpportunitySource.EXECUTION_INTENT,
                intent=_build_execution_intent(),
                validity=OpportunityValidity(
                    status=OpportunityValidityStatus.VALID,
                    observed_inputs=1,
                    required_inputs=1,
                ),
            ),
            candidate=None,
            event_type=OpportunityEventType.OPPORTUNITY_CANDIDATE_UPDATED,
        )

        assert config.selection_name == "phase11_foundation_selection"
        assert diagnostics.lifecycle_state == OpportunityRuntimeLifecycleState.NOT_STARTED
        assert update.event_type == OpportunityEventType.OPPORTUNITY_CANDIDATE_UPDATED

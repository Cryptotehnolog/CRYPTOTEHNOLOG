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
    OpportunityDirection,
    OpportunityFreshness,
    OpportunityReasonCode,
    OpportunitySelectionCandidate,
    OpportunitySource,
    OpportunityValidity,
    OpportunityValidityStatus,
)
from cryptotechnolog.orchestration import (
    OrchestrationContext,
    OrchestrationDecision,
    OrchestrationDecisionCandidate,
    OrchestrationDecisionPayload,
    OrchestrationEventType,
    OrchestrationFreshness,
    OrchestrationReasonCode,
    OrchestrationRuntimeConfig,
    OrchestrationRuntimeDiagnostics,
    OrchestrationRuntimeLifecycleState,
    OrchestrationRuntimeUpdate,
    OrchestrationSource,
    OrchestrationStatus,
    OrchestrationValidity,
    OrchestrationValidityStatus,
    build_orchestration_event,
    default_priority_for_orchestration_event,
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


def _build_opportunity_candidate() -> OpportunitySelectionCandidate:
    now = datetime.now(UTC)
    intent = _build_execution_intent()
    return OpportunitySelectionCandidate.candidate(
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


class TestOrchestrationContracts:
    def test_orchestration_validity_readiness_ratio_is_normalized(self) -> None:
        validity = OrchestrationValidity(
            status=OrchestrationValidityStatus.WARMING,
            observed_inputs=1,
            required_inputs=3,
            missing_inputs=("selection", "reference_time"),
        )

        assert validity.is_valid is False
        assert validity.is_warming is True
        assert validity.missing_inputs_count == 2
        assert validity.readiness_ratio == Decimal("0.3333")

    def test_orchestration_freshness_requires_reference_time_for_expiry(self) -> None:
        now = datetime.now(UTC)
        freshness = OrchestrationFreshness(
            generated_at=now,
            expires_at=now + timedelta(minutes=1),
        )

        assert freshness.has_structurally_valid_expiry_window is True
        assert freshness.is_expired_at(now + timedelta(minutes=2)) is True
        assert freshness.is_expired_at(now + timedelta(seconds=30)) is False

    def test_valid_orchestration_context_requires_selected_opportunity(self) -> None:
        selection = _build_opportunity_candidate()
        context = OrchestrationContext(
            orchestration_name="phase12_meta_orchestration",
            contour_name="phase12_orchestration_contour",
            symbol="BTCUSDT",
            exchange="BINANCE",
            timeframe=MarketDataTimeframe.M5,
            observed_at=datetime.now(UTC),
            source=OrchestrationSource.OPPORTUNITY_SELECTION,
            selection=selection,
            validity=OrchestrationValidity(
                status=OrchestrationValidityStatus.VALID,
                observed_inputs=1,
                required_inputs=1,
            ),
        )

        assert context.validity.is_valid is True
        assert context.selection.is_selected is True

    def test_factory_does_not_hide_runtime_lifecycle_semantics(self) -> None:
        now = datetime.now(UTC)
        selection = _build_opportunity_candidate()
        decision = OrchestrationDecisionCandidate.candidate(
            contour_name="phase12_orchestration_contour",
            orchestration_name="phase12_meta_orchestration",
            symbol="BTCUSDT",
            exchange="BINANCE",
            timeframe=MarketDataTimeframe.M5,
            source=OrchestrationSource.OPPORTUNITY_SELECTION,
            freshness=OrchestrationFreshness(
                generated_at=now,
                expires_at=now + timedelta(minutes=5),
            ),
            validity=OrchestrationValidity(
                status=OrchestrationValidityStatus.VALID,
                observed_inputs=1,
                required_inputs=1,
            ),
            decision=OrchestrationDecision.FORWARD,
            confidence=Decimal("0.87"),
            priority_score=Decimal("0.9100"),
            reason_code=OrchestrationReasonCode.CONTEXT_READY,
        )

        assert decision.status == OrchestrationStatus.CANDIDATE
        assert decision.decision == OrchestrationDecision.FORWARD
        assert decision.is_forwarded is False
        assert decision.is_abstained is False

        abstained = OrchestrationDecisionCandidate.candidate(
            contour_name="phase12_orchestration_contour",
            orchestration_name="phase12_meta_orchestration",
            symbol="BTCUSDT",
            exchange="BINANCE",
            timeframe=MarketDataTimeframe.M5,
            source=OrchestrationSource.OPPORTUNITY_SELECTION,
            freshness=OrchestrationFreshness(generated_at=now),
            validity=OrchestrationValidity(
                status=OrchestrationValidityStatus.VALID,
                observed_inputs=1,
                required_inputs=1,
            ),
            decision=OrchestrationDecision.ABSTAIN,
            originating_selection_id=selection.selection_id,
            confidence=Decimal("0.87"),
            priority_score=Decimal("0.8700"),
            reason_code=OrchestrationReasonCode.ORCHESTRATION_ABSTAINED,
        )

        assert abstained.status == OrchestrationStatus.CANDIDATE
        assert abstained.decision == OrchestrationDecision.ABSTAIN
        assert abstained.is_forwarded is False
        assert abstained.is_abstained is False

    def test_orchestrated_decision_requires_direction_and_selection_id(self) -> None:
        now = datetime.now(UTC)
        selection = _build_opportunity_candidate()
        decision = OrchestrationDecisionCandidate(
            decision_id=OrchestrationDecisionCandidate.candidate(
                contour_name="phase12_orchestration_contour",
                orchestration_name="phase12_meta_orchestration",
                symbol="BTCUSDT",
                exchange="BINANCE",
                timeframe=MarketDataTimeframe.M5,
                source=OrchestrationSource.OPPORTUNITY_SELECTION,
                freshness=OrchestrationFreshness(generated_at=now),
                validity=OrchestrationValidity(
                    status=OrchestrationValidityStatus.WARMING,
                    observed_inputs=0,
                    required_inputs=1,
                ),
                decision=OrchestrationDecision.FORWARD,
            ).decision_id,
            contour_name="phase12_orchestration_contour",
            orchestration_name="phase12_meta_orchestration",
            symbol="BTCUSDT",
            exchange="BINANCE",
            timeframe=MarketDataTimeframe.M5,
            source=OrchestrationSource.OPPORTUNITY_SELECTION,
            freshness=OrchestrationFreshness(
                generated_at=now,
                expires_at=now + timedelta(minutes=5),
            ),
            validity=OrchestrationValidity(
                status=OrchestrationValidityStatus.VALID,
                observed_inputs=1,
                required_inputs=1,
            ),
            status=OrchestrationStatus.ORCHESTRATED,
            decision=OrchestrationDecision.FORWARD,
            direction=OpportunityDirection.LONG,
            originating_selection_id=selection.selection_id,
            confidence=Decimal("0.87"),
            priority_score=Decimal("0.9100"),
            reason_code=OrchestrationReasonCode.CONTEXT_READY,
        )

        assert decision.status == OrchestrationStatus.ORCHESTRATED
        assert decision.is_forwarded is True
        assert decision.is_abstained is False

    def test_abstained_decision_requires_explicit_abstain_semantics(self) -> None:
        now = datetime.now(UTC)
        selection = _build_opportunity_candidate()
        decision = OrchestrationDecisionCandidate(
            decision_id=OrchestrationDecisionCandidate.candidate(
                contour_name="phase12_orchestration_contour",
                orchestration_name="phase12_meta_orchestration",
                symbol="BTCUSDT",
                exchange="BINANCE",
                timeframe=MarketDataTimeframe.M5,
                source=OrchestrationSource.OPPORTUNITY_SELECTION,
                freshness=OrchestrationFreshness(generated_at=now),
                validity=OrchestrationValidity(
                    status=OrchestrationValidityStatus.WARMING,
                    observed_inputs=0,
                    required_inputs=1,
                ),
                decision=OrchestrationDecision.ABSTAIN,
            ).decision_id,
            contour_name="phase12_orchestration_contour",
            orchestration_name="phase12_meta_orchestration",
            symbol="BTCUSDT",
            exchange="BINANCE",
            timeframe=MarketDataTimeframe.M5,
            source=OrchestrationSource.OPPORTUNITY_SELECTION,
            freshness=OrchestrationFreshness(generated_at=now),
            validity=OrchestrationValidity(
                status=OrchestrationValidityStatus.VALID,
                observed_inputs=1,
                required_inputs=1,
            ),
            status=OrchestrationStatus.ABSTAINED,
            decision=OrchestrationDecision.ABSTAIN,
            originating_selection_id=selection.selection_id,
            confidence=Decimal("0.87"),
            priority_score=Decimal("0.8700"),
            reason_code=OrchestrationReasonCode.ORCHESTRATION_ABSTAINED,
        )

        assert decision.status == OrchestrationStatus.ABSTAINED
        assert decision.is_forwarded is False
        assert decision.is_abstained is True
        assert decision.direction is None

    def test_invalidated_decision_cannot_keep_validity_valid(self) -> None:
        now = datetime.now(UTC)
        with pytest.raises(ValueError, match="INVALIDATED"):
            OrchestrationDecisionCandidate(
                decision_id=OrchestrationDecisionCandidate.candidate(
                    contour_name="phase12_orchestration_contour",
                    orchestration_name="phase12_meta_orchestration",
                    symbol="BTCUSDT",
                    exchange="BINANCE",
                    timeframe=MarketDataTimeframe.M5,
                    source=OrchestrationSource.OPPORTUNITY_SELECTION,
                    freshness=OrchestrationFreshness(generated_at=now),
                    validity=OrchestrationValidity(
                        status=OrchestrationValidityStatus.WARMING,
                        observed_inputs=0,
                        required_inputs=1,
                    ),
                    decision=OrchestrationDecision.ABSTAIN,
                ).decision_id,
                contour_name="phase12_orchestration_contour",
                orchestration_name="phase12_meta_orchestration",
                symbol="BTCUSDT",
                exchange="BINANCE",
                timeframe=MarketDataTimeframe.M5,
                source=OrchestrationSource.OPPORTUNITY_SELECTION,
                freshness=OrchestrationFreshness(generated_at=now),
                validity=OrchestrationValidity(
                    status=OrchestrationValidityStatus.VALID,
                    observed_inputs=1,
                    required_inputs=1,
                ),
                status=OrchestrationStatus.INVALIDATED,
                decision=OrchestrationDecision.ABSTAIN,
                reason_code=OrchestrationReasonCode.ORCHESTRATION_INVALIDATED,
            )


class TestOrchestrationEventsAndRuntimeShape:
    def test_orchestration_event_payload_is_transport_compatible(self) -> None:
        now = datetime.now(UTC)
        selection = _build_opportunity_candidate()
        decision = OrchestrationDecisionCandidate.candidate(
            contour_name="phase12_orchestration_contour",
            orchestration_name="phase12_meta_orchestration",
            symbol="BTCUSDT",
            exchange="BINANCE",
            timeframe=MarketDataTimeframe.M5,
            source=OrchestrationSource.OPPORTUNITY_SELECTION,
            freshness=OrchestrationFreshness(
                generated_at=now,
                expires_at=now + timedelta(minutes=5),
            ),
            validity=OrchestrationValidity(
                status=OrchestrationValidityStatus.VALID,
                observed_inputs=1,
                required_inputs=1,
            ),
            decision=OrchestrationDecision.FORWARD,
            direction=OpportunityDirection.LONG,
            originating_selection_id=selection.selection_id,
            reason_code=OrchestrationReasonCode.CONTEXT_READY,
        )

        payload = OrchestrationDecisionPayload.from_candidate(decision)
        event = build_orchestration_event(
            event_type=OrchestrationEventType.ORCHESTRATION_DECIDED,
            payload=payload,
        )

        assert event.event_type == OrchestrationEventType.ORCHESTRATION_DECIDED.value
        assert event.priority == Priority.HIGH
        assert event.payload["symbol"] == "BTCUSDT"
        assert event.payload["orchestration_name"] == "phase12_meta_orchestration"

    def test_default_priority_for_orchestration_event_is_narrow_and_predictable(self) -> None:
        assert (
            default_priority_for_orchestration_event(OrchestrationEventType.ORCHESTRATION_DECIDED)
            == Priority.HIGH
        )
        assert (
            default_priority_for_orchestration_event(
                OrchestrationEventType.ORCHESTRATION_CANDIDATE_UPDATED
            )
            == Priority.NORMAL
        )
        assert (
            default_priority_for_orchestration_event(
                OrchestrationEventType.ORCHESTRATION_INVALIDATED
            )
            == Priority.NORMAL
        )

    def test_runtime_boundary_shape_is_explicit(self) -> None:
        config = OrchestrationRuntimeConfig()
        diagnostics = OrchestrationRuntimeDiagnostics()
        update = OrchestrationRuntimeUpdate(
            context=OrchestrationContext(
                orchestration_name="phase12_meta_orchestration",
                contour_name="phase12_orchestration_contour",
                symbol="BTCUSDT",
                exchange="BINANCE",
                timeframe=MarketDataTimeframe.M5,
                observed_at=datetime.now(UTC),
                source=OrchestrationSource.OPPORTUNITY_SELECTION,
                selection=_build_opportunity_candidate(),
                validity=OrchestrationValidity(
                    status=OrchestrationValidityStatus.VALID,
                    observed_inputs=1,
                    required_inputs=1,
                ),
            ),
            decision=None,
            event_type=OrchestrationEventType.ORCHESTRATION_CANDIDATE_UPDATED,
        )

        assert config.orchestration_name == "phase12_meta_orchestration"
        assert diagnostics.lifecycle_state == OrchestrationRuntimeLifecycleState.NOT_STARTED
        assert update.event_type == OrchestrationEventType.ORCHESTRATION_CANDIDATE_UPDATED

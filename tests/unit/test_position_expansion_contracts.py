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
    ExpansionContext,
    ExpansionDecision,
    ExpansionDirection,
    ExpansionFreshness,
    ExpansionReasonCode,
    ExpansionSource,
    ExpansionStatus,
    ExpansionValidity,
    ExpansionValidityStatus,
    PositionExpansionCandidate,
    PositionExpansionEventType,
    PositionExpansionPayload,
    PositionExpansionRuntimeConfig,
    PositionExpansionRuntimeDiagnostics,
    PositionExpansionRuntimeLifecycleState,
    PositionExpansionRuntimeUpdate,
    build_position_expansion_event,
    default_priority_for_position_expansion_event,
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
    candidate = SignalSnapshot.candidate(
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
    )
    return SignalSnapshot(
        signal_id=candidate.signal_id,
        contour_name=candidate.contour_name,
        symbol=candidate.symbol,
        exchange=candidate.exchange,
        timeframe=candidate.timeframe,
        freshness=candidate.freshness,
        validity=candidate.validity,
        status=SignalStatus.ACTIVE,
        direction=candidate.direction,
        confidence=candidate.confidence,
        entry_price=candidate.entry_price,
        stop_loss=candidate.stop_loss,
        take_profit=candidate.take_profit,
        reason_code=candidate.reason_code,
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


def _build_orchestration_decision() -> OrchestrationDecisionCandidate:
    now = datetime.now(UTC)
    selection = _build_opportunity_candidate()
    return OrchestrationDecisionCandidate.candidate(
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


class TestPositionExpansionContracts:
    def test_expansion_validity_readiness_ratio_is_normalized(self) -> None:
        validity = ExpansionValidity(
            status=ExpansionValidityStatus.WARMING,
            observed_inputs=1,
            required_inputs=3,
            missing_inputs=("decision", "reference_time"),
        )

        assert validity.is_valid is False
        assert validity.is_warming is True
        assert validity.missing_inputs_count == 2
        assert validity.readiness_ratio == Decimal("0.3333")

    def test_expansion_freshness_requires_reference_time_for_expiry(self) -> None:
        now = datetime.now(UTC)
        freshness = ExpansionFreshness(
            generated_at=now,
            expires_at=now + timedelta(minutes=1),
        )

        assert freshness.has_structurally_valid_expiry_window is True
        assert freshness.is_expired_at(now + timedelta(minutes=2)) is True
        assert freshness.is_expired_at(now + timedelta(seconds=30)) is False

    def test_valid_expansion_context_requires_forwarded_orchestration_decision(self) -> None:
        decision = _build_orchestration_decision()
        context = ExpansionContext(
            expansion_name="phase13_position_expansion",
            contour_name="phase13_position_expansion_contour",
            symbol="BTCUSDT",
            exchange="BINANCE",
            timeframe=MarketDataTimeframe.M5,
            observed_at=datetime.now(UTC),
            source=ExpansionSource.ORCHESTRATION_DECISION,
            decision=decision,
            validity=ExpansionValidity(
                status=ExpansionValidityStatus.VALID,
                observed_inputs=1,
                required_inputs=1,
            ),
        )

        assert context.validity.is_valid is True
        assert context.decision.is_forwarded is True

    def test_factory_does_not_hide_runtime_lifecycle_semantics(self) -> None:
        now = datetime.now(UTC)
        candidate = PositionExpansionCandidate.candidate(
            contour_name="phase13_position_expansion_contour",
            expansion_name="phase13_position_expansion",
            symbol="BTCUSDT",
            exchange="BINANCE",
            timeframe=MarketDataTimeframe.M5,
            source=ExpansionSource.ORCHESTRATION_DECISION,
            freshness=ExpansionFreshness(
                generated_at=now,
                expires_at=now + timedelta(minutes=5),
            ),
            validity=ExpansionValidity(
                status=ExpansionValidityStatus.VALID,
                observed_inputs=1,
                required_inputs=1,
            ),
            decision=ExpansionDecision.ADD,
            confidence=Decimal("0.87"),
            priority_score=Decimal("0.9100"),
            reason_code=ExpansionReasonCode.CONTEXT_READY,
        )

        assert candidate.status == ExpansionStatus.CANDIDATE
        assert candidate.decision == ExpansionDecision.ADD
        assert candidate.is_expandable is False
        assert candidate.is_abstained is False
        assert candidate.is_rejected is False

        abstained = PositionExpansionCandidate.candidate(
            contour_name="phase13_position_expansion_contour",
            expansion_name="phase13_position_expansion",
            symbol="BTCUSDT",
            exchange="BINANCE",
            timeframe=MarketDataTimeframe.M5,
            source=ExpansionSource.ORCHESTRATION_DECISION,
            freshness=ExpansionFreshness(generated_at=now),
            validity=ExpansionValidity(
                status=ExpansionValidityStatus.VALID,
                observed_inputs=1,
                required_inputs=1,
            ),
            decision=ExpansionDecision.ABSTAIN,
            confidence=Decimal("0.87"),
            priority_score=Decimal("0.8700"),
            reason_code=ExpansionReasonCode.EXPANSION_ABSTAINED,
        )

        assert abstained.status == ExpansionStatus.CANDIDATE
        assert abstained.decision == ExpansionDecision.ABSTAIN
        assert abstained.is_expandable is False
        assert abstained.is_abstained is False

        rejected = PositionExpansionCandidate.candidate(
            contour_name="phase13_position_expansion_contour",
            expansion_name="phase13_position_expansion",
            symbol="BTCUSDT",
            exchange="BINANCE",
            timeframe=MarketDataTimeframe.M5,
            source=ExpansionSource.ORCHESTRATION_DECISION,
            freshness=ExpansionFreshness(generated_at=now),
            validity=ExpansionValidity(
                status=ExpansionValidityStatus.INVALID,
                observed_inputs=0,
                required_inputs=1,
                missing_inputs=("approved_add_path",),
            ),
            decision=ExpansionDecision.REJECT,
            reason_code=ExpansionReasonCode.EXPANSION_REJECTED,
        )

        assert rejected.status == ExpansionStatus.CANDIDATE
        assert rejected.decision == ExpansionDecision.REJECT
        assert rejected.is_rejected is False

    def test_expandable_candidate_requires_direction_and_decision_id(self) -> None:
        now = datetime.now(UTC)
        decision = _build_orchestration_decision()
        candidate = PositionExpansionCandidate(
            expansion_id=PositionExpansionCandidate.candidate(
                contour_name="phase13_position_expansion_contour",
                expansion_name="phase13_position_expansion",
                symbol="BTCUSDT",
                exchange="BINANCE",
                timeframe=MarketDataTimeframe.M5,
                source=ExpansionSource.ORCHESTRATION_DECISION,
                freshness=ExpansionFreshness(generated_at=now),
                validity=ExpansionValidity(
                    status=ExpansionValidityStatus.WARMING,
                    observed_inputs=0,
                    required_inputs=1,
                ),
                decision=ExpansionDecision.ADD,
            ).expansion_id,
            contour_name="phase13_position_expansion_contour",
            expansion_name="phase13_position_expansion",
            symbol="BTCUSDT",
            exchange="BINANCE",
            timeframe=MarketDataTimeframe.M5,
            source=ExpansionSource.ORCHESTRATION_DECISION,
            freshness=ExpansionFreshness(
                generated_at=now,
                expires_at=now + timedelta(minutes=5),
            ),
            validity=ExpansionValidity(
                status=ExpansionValidityStatus.VALID,
                observed_inputs=1,
                required_inputs=1,
            ),
            status=ExpansionStatus.EXPANDABLE,
            decision=ExpansionDecision.ADD,
            direction=ExpansionDirection.LONG,
            originating_decision_id=decision.decision_id,
            confidence=Decimal("0.87"),
            priority_score=Decimal("0.9100"),
            reason_code=ExpansionReasonCode.CONTEXT_READY,
        )

        assert candidate.status == ExpansionStatus.EXPANDABLE
        assert candidate.is_expandable is True
        assert candidate.is_abstained is False
        assert candidate.is_rejected is False

    def test_abstained_candidate_requires_explicit_no_expansion_semantics(self) -> None:
        now = datetime.now(UTC)
        candidate = PositionExpansionCandidate(
            expansion_id=PositionExpansionCandidate.candidate(
                contour_name="phase13_position_expansion_contour",
                expansion_name="phase13_position_expansion",
                symbol="BTCUSDT",
                exchange="BINANCE",
                timeframe=MarketDataTimeframe.M5,
                source=ExpansionSource.ORCHESTRATION_DECISION,
                freshness=ExpansionFreshness(generated_at=now),
                validity=ExpansionValidity(
                    status=ExpansionValidityStatus.WARMING,
                    observed_inputs=0,
                    required_inputs=1,
                ),
                decision=ExpansionDecision.ABSTAIN,
            ).expansion_id,
            contour_name="phase13_position_expansion_contour",
            expansion_name="phase13_position_expansion",
            symbol="BTCUSDT",
            exchange="BINANCE",
            timeframe=MarketDataTimeframe.M5,
            source=ExpansionSource.ORCHESTRATION_DECISION,
            freshness=ExpansionFreshness(generated_at=now),
            validity=ExpansionValidity(
                status=ExpansionValidityStatus.INVALID,
                observed_inputs=0,
                required_inputs=1,
                invalid_reason="confidence_below_add_threshold",
            ),
            status=ExpansionStatus.ABSTAINED,
            decision=ExpansionDecision.ABSTAIN,
            reason_code=ExpansionReasonCode.EXPANSION_ABSTAINED,
        )

        assert candidate.status == ExpansionStatus.ABSTAINED
        assert candidate.is_expandable is False
        assert candidate.is_abstained is True
        assert candidate.is_rejected is False

    def test_rejected_candidate_requires_explicit_reject_semantics(self) -> None:
        now = datetime.now(UTC)
        candidate = PositionExpansionCandidate(
            expansion_id=PositionExpansionCandidate.candidate(
                contour_name="phase13_position_expansion_contour",
                expansion_name="phase13_position_expansion",
                symbol="BTCUSDT",
                exchange="BINANCE",
                timeframe=MarketDataTimeframe.M5,
                source=ExpansionSource.ORCHESTRATION_DECISION,
                freshness=ExpansionFreshness(generated_at=now),
                validity=ExpansionValidity(
                    status=ExpansionValidityStatus.WARMING,
                    observed_inputs=0,
                    required_inputs=1,
                ),
                decision=ExpansionDecision.REJECT,
            ).expansion_id,
            contour_name="phase13_position_expansion_contour",
            expansion_name="phase13_position_expansion",
            symbol="BTCUSDT",
            exchange="BINANCE",
            timeframe=MarketDataTimeframe.M5,
            source=ExpansionSource.ORCHESTRATION_DECISION,
            freshness=ExpansionFreshness(generated_at=now),
            validity=ExpansionValidity(
                status=ExpansionValidityStatus.INVALID,
                observed_inputs=0,
                required_inputs=1,
                invalid_reason="position_expansion_not_admissible",
            ),
            status=ExpansionStatus.REJECTED,
            decision=ExpansionDecision.REJECT,
            reason_code=ExpansionReasonCode.EXPANSION_REJECTED,
        )

        assert candidate.status == ExpansionStatus.REJECTED
        assert candidate.is_expandable is False
        assert candidate.is_abstained is False
        assert candidate.is_rejected is True

    def test_invalidated_candidate_cannot_keep_validity_valid(self) -> None:
        now = datetime.now(UTC)
        with pytest.raises(ValueError, match="не может иметь validity=VALID"):
            PositionExpansionCandidate(
                expansion_id=PositionExpansionCandidate.candidate(
                    contour_name="phase13_position_expansion_contour",
                    expansion_name="phase13_position_expansion",
                    symbol="BTCUSDT",
                    exchange="BINANCE",
                    timeframe=MarketDataTimeframe.M5,
                    source=ExpansionSource.ORCHESTRATION_DECISION,
                    freshness=ExpansionFreshness(generated_at=now),
                    validity=ExpansionValidity(
                        status=ExpansionValidityStatus.WARMING,
                        observed_inputs=0,
                        required_inputs=1,
                    ),
                    decision=ExpansionDecision.ADD,
                ).expansion_id,
                contour_name="phase13_position_expansion_contour",
                expansion_name="phase13_position_expansion",
                symbol="BTCUSDT",
                exchange="BINANCE",
                timeframe=MarketDataTimeframe.M5,
                source=ExpansionSource.ORCHESTRATION_DECISION,
                freshness=ExpansionFreshness(generated_at=now),
                validity=ExpansionValidity(
                    status=ExpansionValidityStatus.VALID,
                    observed_inputs=1,
                    required_inputs=1,
                ),
                status=ExpansionStatus.INVALIDATED,
                decision=ExpansionDecision.REJECT,
                reason_code=ExpansionReasonCode.EXPANSION_INVALIDATED,
            )

    def test_position_expansion_event_payload_is_transport_compatible(self) -> None:
        candidate = PositionExpansionCandidate(
            expansion_id=PositionExpansionCandidate.candidate(
                contour_name="phase13_position_expansion_contour",
                expansion_name="phase13_position_expansion",
                symbol="BTCUSDT",
                exchange="BINANCE",
                timeframe=MarketDataTimeframe.M5,
                source=ExpansionSource.ORCHESTRATION_DECISION,
                freshness=ExpansionFreshness(generated_at=datetime.now(UTC)),
                validity=ExpansionValidity(
                    status=ExpansionValidityStatus.WARMING,
                    observed_inputs=0,
                    required_inputs=1,
                ),
                decision=ExpansionDecision.ADD,
            ).expansion_id,
            contour_name="phase13_position_expansion_contour",
            expansion_name="phase13_position_expansion",
            symbol="BTCUSDT",
            exchange="BINANCE",
            timeframe=MarketDataTimeframe.M5,
            source=ExpansionSource.ORCHESTRATION_DECISION,
            freshness=ExpansionFreshness(
                generated_at=datetime.now(UTC),
                expires_at=datetime.now(UTC) + timedelta(minutes=5),
            ),
            validity=ExpansionValidity(
                status=ExpansionValidityStatus.VALID,
                observed_inputs=1,
                required_inputs=1,
            ),
            status=ExpansionStatus.EXPANDABLE,
            decision=ExpansionDecision.ADD,
            direction=ExpansionDirection.LONG,
            originating_decision_id=_build_orchestration_decision().decision_id,
            confidence=Decimal("0.8700"),
            priority_score=Decimal("0.9100"),
            reason_code=ExpansionReasonCode.CONTEXT_READY,
            metadata={"source_layer": "phase12_orchestration"},
        )

        payload = PositionExpansionPayload.from_candidate(candidate)
        event = build_position_expansion_event(
            event_type=PositionExpansionEventType.POSITION_EXPANSION_APPROVED,
            payload=payload,
        )

        assert payload.status == "expandable"
        assert payload.decision == "add"
        assert payload.direction == "LONG"
        assert event.payload["status"] == "expandable"
        assert event.payload["decision"] == "add"
        assert event.priority == Priority.HIGH

    def test_default_priority_for_position_expansion_event_is_narrow_and_predictable(
        self,
    ) -> None:
        assert (
            default_priority_for_position_expansion_event(
                PositionExpansionEventType.POSITION_EXPANSION_CANDIDATE_UPDATED
            )
            == Priority.NORMAL
        )
        assert (
            default_priority_for_position_expansion_event(
                PositionExpansionEventType.POSITION_EXPANSION_APPROVED
            )
            == Priority.HIGH
        )
        assert (
            default_priority_for_position_expansion_event(
                PositionExpansionEventType.POSITION_EXPANSION_INVALIDATED
            )
            == Priority.NORMAL
        )

    def test_orchestration_direction_is_normalized_to_expansion_direction(self) -> None:
        decision = _build_orchestration_decision()
        assert decision.direction == OpportunityDirection.LONG
        assert ExpansionDirection.LONG.value == decision.direction.value

    def test_runtime_boundary_types_are_instantiable_for_next_step(self) -> None:
        diagnostics = PositionExpansionRuntimeDiagnostics(
            lifecycle_state=PositionExpansionRuntimeLifecycleState.WARMING
        )
        config = PositionExpansionRuntimeConfig()
        update = PositionExpansionRuntimeUpdate(
            context=ExpansionContext(
                expansion_name="phase13_position_expansion",
                contour_name="phase13_position_expansion_contour",
                symbol="BTCUSDT",
                exchange="BINANCE",
                timeframe=MarketDataTimeframe.M5,
                observed_at=datetime.now(UTC),
                source=ExpansionSource.ORCHESTRATION_DECISION,
                decision=_build_orchestration_decision(),
                validity=ExpansionValidity(
                    status=ExpansionValidityStatus.VALID,
                    observed_inputs=1,
                    required_inputs=1,
                ),
            ),
            candidate=None,
            event_type=PositionExpansionEventType.POSITION_EXPANSION_CANDIDATE_UPDATED,
            emitted_payload=None,
        )

        assert diagnostics.to_dict()["lifecycle_state"] == "warming"
        assert config.contour_name == "phase13_position_expansion_contour"
        assert update.event_type == PositionExpansionEventType.POSITION_EXPANSION_CANDIDATE_UPDATED

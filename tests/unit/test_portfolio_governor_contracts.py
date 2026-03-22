from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from cryptotechnolog.core.event import Priority
from cryptotechnolog.market_data import MarketDataTimeframe
from cryptotechnolog.portfolio_governor import (
    GovernorContext,
    GovernorDecision,
    GovernorDirection,
    GovernorFreshness,
    GovernorReasonCode,
    GovernorSource,
    GovernorStatus,
    GovernorValidity,
    GovernorValidityStatus,
    PortfolioGovernorCandidate,
    PortfolioGovernorEventType,
    PortfolioGovernorPayload,
    PortfolioGovernorRuntimeConfig,
    PortfolioGovernorRuntimeDiagnostics,
    PortfolioGovernorRuntimeLifecycleState,
    PortfolioGovernorRuntimeUpdate,
    build_portfolio_governor_event,
    create_portfolio_governor_runtime,
    default_priority_for_portfolio_governor_event,
)
from cryptotechnolog.position_expansion import (
    ExpansionDecision,
    ExpansionDirection,
    ExpansionFreshness,
    ExpansionReasonCode,
    ExpansionSource,
    ExpansionStatus,
    ExpansionValidity,
    ExpansionValidityStatus,
    PositionExpansionCandidate,
)


def _build_expandable_expansion() -> PositionExpansionCandidate:
    now = datetime.now(UTC)
    return PositionExpansionCandidate(
        expansion_id=uuid4(),
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
        originating_decision_id=uuid4(),
        confidence=Decimal("0.8700"),
        priority_score=Decimal("0.9100"),
        reason_code=ExpansionReasonCode.CONTEXT_READY,
    )


class TestPortfolioGovernorContracts:
    def test_governor_validity_readiness_ratio_is_normalized(self) -> None:
        validity = GovernorValidity(
            status=GovernorValidityStatus.WARMING,
            observed_inputs=1,
            required_inputs=3,
            missing_inputs=("portfolio_capacity", "capital_fraction"),
        )

        assert validity.is_valid is False
        assert validity.is_warming is True
        assert validity.missing_inputs_count == 2
        assert validity.readiness_ratio == Decimal("0.3333")

    def test_governor_freshness_requires_reference_time_for_expiry(self) -> None:
        now = datetime.now(UTC)
        freshness = GovernorFreshness(
            generated_at=now,
            expires_at=now + timedelta(minutes=1),
        )

        assert freshness.has_structurally_valid_expiry_window is True
        assert freshness.is_expired_at(now + timedelta(minutes=2)) is True
        assert freshness.is_expired_at(now + timedelta(seconds=30)) is False

    def test_valid_governor_context_requires_expandable_position_expansion_candidate(
        self,
    ) -> None:
        expansion = _build_expandable_expansion()
        context = GovernorContext(
            governor_name="phase14_portfolio_governor",
            contour_name="phase14_portfolio_governor_contour",
            symbol="BTCUSDT",
            exchange="BINANCE",
            timeframe=MarketDataTimeframe.M5,
            observed_at=datetime.now(UTC),
            source=GovernorSource.POSITION_EXPANSION,
            expansion=expansion,
            validity=GovernorValidity(
                status=GovernorValidityStatus.VALID,
                observed_inputs=1,
                required_inputs=1,
            ),
        )

        assert context.validity.is_valid is True
        assert context.expansion.is_expandable is True

    def test_factory_does_not_hide_runtime_lifecycle_semantics(self) -> None:
        now = datetime.now(UTC)
        candidate = PortfolioGovernorCandidate.candidate(
            contour_name="phase14_portfolio_governor_contour",
            governor_name="phase14_portfolio_governor",
            symbol="BTCUSDT",
            exchange="BINANCE",
            timeframe=MarketDataTimeframe.M5,
            source=GovernorSource.POSITION_EXPANSION,
            freshness=GovernorFreshness(
                generated_at=now,
                expires_at=now + timedelta(minutes=5),
            ),
            validity=GovernorValidity(
                status=GovernorValidityStatus.VALID,
                observed_inputs=1,
                required_inputs=1,
            ),
            decision=GovernorDecision.APPROVE,
            confidence=Decimal("0.87"),
            priority_score=Decimal("0.9100"),
            capital_fraction=Decimal("0.1000"),
            reason_code=GovernorReasonCode.CONTEXT_READY,
        )

        assert candidate.status == GovernorStatus.CANDIDATE
        assert candidate.decision == GovernorDecision.APPROVE
        assert candidate.is_approved is False
        assert candidate.is_abstained is False
        assert candidate.is_rejected is False

        abstained = PortfolioGovernorCandidate.candidate(
            contour_name="phase14_portfolio_governor_contour",
            governor_name="phase14_portfolio_governor",
            symbol="BTCUSDT",
            exchange="BINANCE",
            timeframe=MarketDataTimeframe.M5,
            source=GovernorSource.POSITION_EXPANSION,
            freshness=GovernorFreshness(generated_at=now),
            validity=GovernorValidity(
                status=GovernorValidityStatus.VALID,
                observed_inputs=1,
                required_inputs=1,
            ),
            decision=GovernorDecision.ABSTAIN,
            reason_code=GovernorReasonCode.GOVERNOR_ABSTAINED,
        )

        assert abstained.status == GovernorStatus.CANDIDATE
        assert abstained.is_abstained is False

        rejected = PortfolioGovernorCandidate.candidate(
            contour_name="phase14_portfolio_governor_contour",
            governor_name="phase14_portfolio_governor",
            symbol="BTCUSDT",
            exchange="BINANCE",
            timeframe=MarketDataTimeframe.M5,
            source=GovernorSource.POSITION_EXPANSION,
            freshness=GovernorFreshness(generated_at=now),
            validity=GovernorValidity(
                status=GovernorValidityStatus.INVALID,
                observed_inputs=0,
                required_inputs=1,
                missing_inputs=("expandable_candidate",),
            ),
            decision=GovernorDecision.REJECT,
            reason_code=GovernorReasonCode.GOVERNOR_REJECTED,
        )

        assert rejected.status == GovernorStatus.CANDIDATE
        assert rejected.is_rejected is False

    def test_approved_candidate_requires_direction_expansion_id_and_capital_fraction(
        self,
    ) -> None:
        now = datetime.now(UTC)
        expansion = _build_expandable_expansion()
        candidate = PortfolioGovernorCandidate(
            governor_id=uuid4(),
            contour_name="phase14_portfolio_governor_contour",
            governor_name="phase14_portfolio_governor",
            symbol="BTCUSDT",
            exchange="BINANCE",
            timeframe=MarketDataTimeframe.M5,
            source=GovernorSource.POSITION_EXPANSION,
            freshness=GovernorFreshness(
                generated_at=now,
                expires_at=now + timedelta(minutes=5),
            ),
            validity=GovernorValidity(
                status=GovernorValidityStatus.VALID,
                observed_inputs=1,
                required_inputs=1,
            ),
            status=GovernorStatus.APPROVED,
            decision=GovernorDecision.APPROVE,
            direction=GovernorDirection.LONG,
            originating_expansion_id=expansion.expansion_id,
            confidence=Decimal("0.87"),
            priority_score=Decimal("0.9100"),
            capital_fraction=Decimal("0.1000"),
            reason_code=GovernorReasonCode.CONTEXT_READY,
        )

        assert candidate.status == GovernorStatus.APPROVED
        assert candidate.is_approved is True
        assert candidate.capital_fraction == Decimal("0.1000")

    def test_abstained_candidate_requires_explicit_no_admission_semantics(self) -> None:
        now = datetime.now(UTC)
        candidate = PortfolioGovernorCandidate(
            governor_id=uuid4(),
            contour_name="phase14_portfolio_governor_contour",
            governor_name="phase14_portfolio_governor",
            symbol="BTCUSDT",
            exchange="BINANCE",
            timeframe=MarketDataTimeframe.M5,
            source=GovernorSource.POSITION_EXPANSION,
            freshness=GovernorFreshness(generated_at=now),
            validity=GovernorValidity(
                status=GovernorValidityStatus.INVALID,
                observed_inputs=0,
                required_inputs=1,
                invalid_reason="capital_fraction_below_threshold",
            ),
            status=GovernorStatus.ABSTAINED,
            decision=GovernorDecision.ABSTAIN,
            reason_code=GovernorReasonCode.GOVERNOR_ABSTAINED,
        )

        assert candidate.status == GovernorStatus.ABSTAINED
        assert candidate.is_abstained is True
        assert candidate.is_rejected is False

    def test_rejected_candidate_requires_explicit_reject_semantics(self) -> None:
        now = datetime.now(UTC)
        candidate = PortfolioGovernorCandidate(
            governor_id=uuid4(),
            contour_name="phase14_portfolio_governor_contour",
            governor_name="phase14_portfolio_governor",
            symbol="BTCUSDT",
            exchange="BINANCE",
            timeframe=MarketDataTimeframe.M5,
            source=GovernorSource.POSITION_EXPANSION,
            freshness=GovernorFreshness(generated_at=now),
            validity=GovernorValidity(
                status=GovernorValidityStatus.INVALID,
                observed_inputs=0,
                required_inputs=1,
                invalid_reason="portfolio_admission_not_allowed",
            ),
            status=GovernorStatus.REJECTED,
            decision=GovernorDecision.REJECT,
            reason_code=GovernorReasonCode.GOVERNOR_REJECTED,
        )

        assert candidate.status == GovernorStatus.REJECTED
        assert candidate.is_rejected is True
        assert candidate.is_abstained is False

    def test_invalidated_candidate_cannot_keep_validity_valid(self) -> None:
        now = datetime.now(UTC)
        with pytest.raises(ValueError, match="не может иметь validity=VALID"):
            PortfolioGovernorCandidate(
                governor_id=uuid4(),
                contour_name="phase14_portfolio_governor_contour",
                governor_name="phase14_portfolio_governor",
                symbol="BTCUSDT",
                exchange="BINANCE",
                timeframe=MarketDataTimeframe.M5,
                source=GovernorSource.POSITION_EXPANSION,
                freshness=GovernorFreshness(generated_at=now),
                validity=GovernorValidity(
                    status=GovernorValidityStatus.VALID,
                    observed_inputs=1,
                    required_inputs=1,
                ),
                status=GovernorStatus.INVALIDATED,
                decision=GovernorDecision.REJECT,
                reason_code=GovernorReasonCode.GOVERNOR_INVALIDATED,
            )

    def test_portfolio_governor_event_payload_is_transport_compatible(self) -> None:
        expansion = _build_expandable_expansion()
        candidate = PortfolioGovernorCandidate(
            governor_id=uuid4(),
            contour_name="phase14_portfolio_governor_contour",
            governor_name="phase14_portfolio_governor",
            symbol="BTCUSDT",
            exchange="BINANCE",
            timeframe=MarketDataTimeframe.M5,
            source=GovernorSource.POSITION_EXPANSION,
            freshness=GovernorFreshness(
                generated_at=datetime.now(UTC),
                expires_at=datetime.now(UTC) + timedelta(minutes=5),
            ),
            validity=GovernorValidity(
                status=GovernorValidityStatus.VALID,
                observed_inputs=1,
                required_inputs=1,
            ),
            status=GovernorStatus.APPROVED,
            decision=GovernorDecision.APPROVE,
            direction=GovernorDirection.LONG,
            originating_expansion_id=expansion.expansion_id,
            confidence=Decimal("0.8700"),
            priority_score=Decimal("0.9100"),
            capital_fraction=Decimal("0.1000"),
            reason_code=GovernorReasonCode.CONTEXT_READY,
            metadata={"source_layer": "phase13_position_expansion"},
        )

        payload = PortfolioGovernorPayload.from_candidate(candidate)
        event = build_portfolio_governor_event(
            event_type=PortfolioGovernorEventType.PORTFOLIO_GOVERNOR_APPROVED,
            payload=payload,
        )

        assert payload.status == "approved"
        assert payload.decision == "approve"
        assert payload.direction == "LONG"
        assert payload.capital_fraction == "0.1000"
        assert event.payload["status"] == "approved"
        assert event.payload["decision"] == "approve"
        assert event.priority == Priority.HIGH

    def test_default_priority_for_portfolio_governor_event_is_narrow_and_predictable(
        self,
    ) -> None:
        assert (
            default_priority_for_portfolio_governor_event(
                PortfolioGovernorEventType.PORTFOLIO_GOVERNOR_CANDIDATE_UPDATED
            )
            == Priority.NORMAL
        )
        assert (
            default_priority_for_portfolio_governor_event(
                PortfolioGovernorEventType.PORTFOLIO_GOVERNOR_APPROVED
            )
            == Priority.HIGH
        )
        assert (
            default_priority_for_portfolio_governor_event(
                PortfolioGovernorEventType.PORTFOLIO_GOVERNOR_INVALIDATED
            )
            == Priority.NORMAL
        )

    def test_expansion_direction_is_normalized_to_governor_direction(self) -> None:
        expansion = _build_expandable_expansion()
        assert expansion.direction == ExpansionDirection.LONG
        assert GovernorDirection.LONG.value == expansion.direction.value

    def test_runtime_boundary_types_are_instantiable_for_next_step(self) -> None:
        diagnostics = PortfolioGovernorRuntimeDiagnostics(
            lifecycle_state=PortfolioGovernorRuntimeLifecycleState.WARMING
        )
        config = PortfolioGovernorRuntimeConfig()
        update = PortfolioGovernorRuntimeUpdate(
            context=GovernorContext(
                governor_name="phase14_portfolio_governor",
                contour_name="phase14_portfolio_governor_contour",
                symbol="BTCUSDT",
                exchange="BINANCE",
                timeframe=MarketDataTimeframe.M5,
                observed_at=datetime.now(UTC),
                source=GovernorSource.POSITION_EXPANSION,
                expansion=_build_expandable_expansion(),
                validity=GovernorValidity(
                    status=GovernorValidityStatus.VALID,
                    observed_inputs=1,
                    required_inputs=1,
                ),
            ),
            candidate=None,
            event_type=PortfolioGovernorEventType.PORTFOLIO_GOVERNOR_CANDIDATE_UPDATED,
            emitted_payload=None,
        )

        assert diagnostics.to_dict()["lifecycle_state"] == "warming"
        assert config.contour_name == "phase14_portfolio_governor_contour"
        assert config.default_capital_fraction == Decimal("0.1000")
        assert update.event_type == PortfolioGovernorEventType.PORTFOLIO_GOVERNOR_CANDIDATE_UPDATED
        runtime = create_portfolio_governor_runtime(config)
        assert runtime.get_runtime_diagnostics()["started"] is False

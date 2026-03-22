from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from cryptotechnolog.core.event import Priority
from cryptotechnolog.market_data import MarketDataTimeframe
from cryptotechnolog.portfolio_governor import (
    GovernorDecision,
    GovernorDirection,
    GovernorFreshness,
    GovernorReasonCode,
    GovernorSource,
    GovernorStatus,
    GovernorValidity,
    GovernorValidityStatus,
    PortfolioGovernorCandidate,
)
from cryptotechnolog.protection import (
    ProtectionContext,
    ProtectionDecision,
    ProtectionEventType,
    ProtectionFreshness,
    ProtectionPayload,
    ProtectionReasonCode,
    ProtectionRuntimeConfig,
    ProtectionRuntimeDiagnostics,
    ProtectionRuntimeLifecycleState,
    ProtectionRuntimeUpdate,
    ProtectionSource,
    ProtectionStatus,
    ProtectionSupervisorCandidate,
    ProtectionValidity,
    ProtectionValidityStatus,
    build_protection_event,
    create_protection_runtime,
    default_priority_for_protection_event,
)


def _build_approved_governor() -> PortfolioGovernorCandidate:
    now = datetime.now(UTC)
    return PortfolioGovernorCandidate(
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
        originating_expansion_id=uuid4(),
        confidence=Decimal("0.8700"),
        priority_score=Decimal("0.9100"),
        capital_fraction=Decimal("0.1000"),
        reason_code=GovernorReasonCode.CONTEXT_READY,
    )


class TestProtectionContracts:
    def test_protection_validity_readiness_ratio_is_normalized(self) -> None:
        validity = ProtectionValidity(
            status=ProtectionValidityStatus.WARMING,
            observed_inputs=1,
            required_inputs=3,
            missing_inputs=("approved_governor", "supervisory_policy"),
        )

        assert validity.is_valid is False
        assert validity.is_warming is True
        assert validity.missing_inputs_count == 2
        assert validity.readiness_ratio == Decimal("0.3333")

    def test_protection_freshness_requires_reference_time_for_expiry(self) -> None:
        now = datetime.now(UTC)
        freshness = ProtectionFreshness(
            generated_at=now,
            expires_at=now + timedelta(minutes=1),
        )

        assert freshness.has_structurally_valid_expiry_window is True
        assert freshness.is_expired_at(now + timedelta(minutes=2)) is True
        assert freshness.is_expired_at(now + timedelta(seconds=30)) is False

    def test_valid_protection_context_requires_approved_portfolio_governor_candidate(
        self,
    ) -> None:
        governor = _build_approved_governor()
        context = ProtectionContext(
            supervisor_name="phase15_protection",
            contour_name="phase15_protection_contour",
            symbol="BTCUSDT",
            exchange="BINANCE",
            timeframe=MarketDataTimeframe.M5,
            observed_at=datetime.now(UTC),
            source=ProtectionSource.PORTFOLIO_GOVERNOR,
            governor=governor,
            validity=ProtectionValidity(
                status=ProtectionValidityStatus.VALID,
                observed_inputs=1,
                required_inputs=1,
            ),
        )

        assert context.validity.is_valid is True
        assert context.governor.is_approved is True

    def test_factory_does_not_hide_runtime_lifecycle_semantics(self) -> None:
        now = datetime.now(UTC)
        governor = _build_approved_governor()
        candidate = ProtectionSupervisorCandidate.candidate(
            contour_name="phase15_protection_contour",
            supervisor_name="phase15_protection",
            symbol="BTCUSDT",
            exchange="BINANCE",
            timeframe=MarketDataTimeframe.M5,
            source=ProtectionSource.PORTFOLIO_GOVERNOR,
            freshness=ProtectionFreshness(
                generated_at=now,
                expires_at=now + timedelta(minutes=5),
            ),
            validity=ProtectionValidity(
                status=ProtectionValidityStatus.VALID,
                observed_inputs=1,
                required_inputs=1,
            ),
            decision=ProtectionDecision.PROTECT,
            originating_governor_id=governor.governor_id,
            confidence=Decimal("0.87"),
            priority_score=Decimal("0.9100"),
            reason_code=ProtectionReasonCode.CONTEXT_READY,
        )

        assert candidate.status == ProtectionStatus.CANDIDATE
        assert candidate.decision == ProtectionDecision.PROTECT
        assert candidate.is_protected is False
        assert candidate.is_halted is False
        assert candidate.is_frozen is False

    def test_protected_candidate_requires_validity_and_governor_id(self) -> None:
        governor = _build_approved_governor()
        candidate = ProtectionSupervisorCandidate(
            protection_id=uuid4(),
            contour_name="phase15_protection_contour",
            supervisor_name="phase15_protection",
            symbol="BTCUSDT",
            exchange="BINANCE",
            timeframe=MarketDataTimeframe.M5,
            source=ProtectionSource.PORTFOLIO_GOVERNOR,
            freshness=ProtectionFreshness(generated_at=datetime.now(UTC)),
            validity=ProtectionValidity(
                status=ProtectionValidityStatus.VALID,
                observed_inputs=1,
                required_inputs=1,
            ),
            status=ProtectionStatus.PROTECTED,
            decision=ProtectionDecision.PROTECT,
            originating_governor_id=governor.governor_id,
            confidence=Decimal("0.87"),
            priority_score=Decimal("0.9100"),
            reason_code=ProtectionReasonCode.PROTECTION_PROTECTED,
        )

        assert candidate.is_protected is True
        assert candidate.is_halted is False
        assert candidate.is_frozen is False

    def test_halted_candidate_requires_explicit_halt_semantics(self) -> None:
        governor = _build_approved_governor()
        candidate = ProtectionSupervisorCandidate(
            protection_id=uuid4(),
            contour_name="phase15_protection_contour",
            supervisor_name="phase15_protection",
            symbol="BTCUSDT",
            exchange="BINANCE",
            timeframe=MarketDataTimeframe.M5,
            source=ProtectionSource.PORTFOLIO_GOVERNOR,
            freshness=ProtectionFreshness(generated_at=datetime.now(UTC)),
            validity=ProtectionValidity(
                status=ProtectionValidityStatus.VALID,
                observed_inputs=1,
                required_inputs=1,
            ),
            status=ProtectionStatus.HALTED,
            decision=ProtectionDecision.HALT,
            originating_governor_id=governor.governor_id,
            confidence=Decimal("0.87"),
            priority_score=Decimal("0.9500"),
            reason_code=ProtectionReasonCode.PROTECTION_HALTED,
        )

        assert candidate.is_halted is True
        assert candidate.is_protected is False
        assert candidate.is_frozen is False

    def test_frozen_candidate_requires_explicit_freeze_semantics(self) -> None:
        governor = _build_approved_governor()
        candidate = ProtectionSupervisorCandidate(
            protection_id=uuid4(),
            contour_name="phase15_protection_contour",
            supervisor_name="phase15_protection",
            symbol="BTCUSDT",
            exchange="BINANCE",
            timeframe=MarketDataTimeframe.M5,
            source=ProtectionSource.PORTFOLIO_GOVERNOR,
            freshness=ProtectionFreshness(generated_at=datetime.now(UTC)),
            validity=ProtectionValidity(
                status=ProtectionValidityStatus.VALID,
                observed_inputs=1,
                required_inputs=1,
            ),
            status=ProtectionStatus.FROZEN,
            decision=ProtectionDecision.FREEZE,
            originating_governor_id=governor.governor_id,
            confidence=Decimal("0.87"),
            priority_score=Decimal("0.9900"),
            reason_code=ProtectionReasonCode.PROTECTION_FROZEN,
        )

        assert candidate.is_frozen is True
        assert candidate.is_protected is False
        assert candidate.is_halted is False

    def test_invalidated_candidate_cannot_keep_validity_valid(self) -> None:
        with pytest.raises(ValueError, match="не может иметь validity=VALID"):
            ProtectionSupervisorCandidate(
                protection_id=uuid4(),
                contour_name="phase15_protection_contour",
                supervisor_name="phase15_protection",
                symbol="BTCUSDT",
                exchange="BINANCE",
                timeframe=MarketDataTimeframe.M5,
                source=ProtectionSource.PORTFOLIO_GOVERNOR,
                freshness=ProtectionFreshness(generated_at=datetime.now(UTC)),
                validity=ProtectionValidity(
                    status=ProtectionValidityStatus.VALID,
                    observed_inputs=1,
                    required_inputs=1,
                ),
                status=ProtectionStatus.INVALIDATED,
                decision=ProtectionDecision.HALT,
                reason_code=ProtectionReasonCode.PROTECTION_INVALIDATED,
            )

    def test_protection_event_payload_is_transport_compatible(self) -> None:
        governor = _build_approved_governor()
        candidate = ProtectionSupervisorCandidate(
            protection_id=uuid4(),
            contour_name="phase15_protection_contour",
            supervisor_name="phase15_protection",
            symbol="BTCUSDT",
            exchange="BINANCE",
            timeframe=MarketDataTimeframe.M5,
            source=ProtectionSource.PORTFOLIO_GOVERNOR,
            freshness=ProtectionFreshness(
                generated_at=datetime.now(UTC),
                expires_at=datetime.now(UTC) + timedelta(minutes=5),
            ),
            validity=ProtectionValidity(
                status=ProtectionValidityStatus.VALID,
                observed_inputs=1,
                required_inputs=1,
            ),
            status=ProtectionStatus.HALTED,
            decision=ProtectionDecision.HALT,
            originating_governor_id=governor.governor_id,
            confidence=Decimal("0.8700"),
            priority_score=Decimal("0.9500"),
            reason_code=ProtectionReasonCode.PROTECTION_HALTED,
            metadata={"source_layer": "phase14_portfolio_governor"},
        )

        payload = ProtectionPayload.from_candidate(candidate)
        event = build_protection_event(
            event_type=ProtectionEventType.PROTECTION_HALTED,
            payload=payload,
        )

        assert payload.status == "halted"
        assert payload.decision == "halt"
        assert event.payload["status"] == "halted"
        assert event.payload["decision"] == "halt"
        assert event.priority == Priority.HIGH

    def test_default_priority_for_protection_event_is_narrow_and_predictable(
        self,
    ) -> None:
        assert (
            default_priority_for_protection_event(ProtectionEventType.PROTECTION_CANDIDATE_UPDATED)
            == Priority.NORMAL
        )
        assert (
            default_priority_for_protection_event(ProtectionEventType.PROTECTION_PROTECTED)
            == Priority.NORMAL
        )
        assert (
            default_priority_for_protection_event(ProtectionEventType.PROTECTION_HALTED)
            == Priority.HIGH
        )
        assert (
            default_priority_for_protection_event(ProtectionEventType.PROTECTION_FROZEN)
            == Priority.HIGH
        )

    def test_runtime_boundary_types_are_instantiable_for_next_step(self) -> None:
        diagnostics = ProtectionRuntimeDiagnostics(
            lifecycle_state=ProtectionRuntimeLifecycleState.WARMING
        )
        config = ProtectionRuntimeConfig()
        update = ProtectionRuntimeUpdate(
            context=ProtectionContext(
                supervisor_name="phase15_protection",
                contour_name="phase15_protection_contour",
                symbol="BTCUSDT",
                exchange="BINANCE",
                timeframe=MarketDataTimeframe.M5,
                observed_at=datetime.now(UTC),
                source=ProtectionSource.PORTFOLIO_GOVERNOR,
                governor=_build_approved_governor(),
                validity=ProtectionValidity(
                    status=ProtectionValidityStatus.VALID,
                    observed_inputs=1,
                    required_inputs=1,
                ),
            ),
            candidate=None,
            event_type=ProtectionEventType.PROTECTION_CANDIDATE_UPDATED,
            emitted_payload=None,
        )

        assert diagnostics.to_dict()["lifecycle_state"] == "warming"
        assert config.contour_name == "phase15_protection_contour"
        assert config.halt_priority_threshold == Decimal("0.9000")
        assert config.freeze_priority_threshold == Decimal("0.9750")
        assert update.event_type == ProtectionEventType.PROTECTION_CANDIDATE_UPDATED
        runtime = create_protection_runtime(config)
        assert runtime.get_runtime_diagnostics()["started"] is False
        assert runtime.get_runtime_diagnostics()["lifecycle_state"] == "not_started"

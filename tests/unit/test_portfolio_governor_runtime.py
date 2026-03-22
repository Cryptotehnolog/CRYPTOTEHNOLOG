from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from cryptotechnolog.market_data import MarketDataTimeframe
from cryptotechnolog.portfolio_governor import (
    GovernorDecision,
    GovernorReasonCode,
    GovernorStatus,
    GovernorValidityStatus,
    PortfolioGovernorEventType,
    PortfolioGovernorRuntime,
    PortfolioGovernorRuntimeConfig,
    PortfolioGovernorRuntimeLifecycleState,
    create_portfolio_governor_runtime,
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


def _make_expansion_candidate(
    *,
    status: ExpansionStatus = ExpansionStatus.EXPANDABLE,
    decision: ExpansionDecision = ExpansionDecision.ADD,
    direction: ExpansionDirection | None = ExpansionDirection.LONG,
    confidence: str | None = "0.87",
    priority_score: str | None = "0.9100",
    generated_at: datetime | None = None,
    expires_at: datetime | None = None,
) -> PositionExpansionCandidate:
    now = generated_at or datetime(2026, 3, 22, 12, 0, tzinfo=UTC)
    validity = (
        ExpansionValidity(
            status=ExpansionValidityStatus.VALID,
            observed_inputs=1,
            required_inputs=1,
        )
        if status in {ExpansionStatus.EXPANDABLE, ExpansionStatus.ABSTAINED}
        else ExpansionValidity(
            status=ExpansionValidityStatus.INVALID,
            observed_inputs=1,
            required_inputs=1,
            invalid_reason="position_expansion_lost",
        )
    )
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
            expires_at=expires_at or (now + timedelta(minutes=5)),
        ),
        validity=validity,
        status=status,
        decision=decision,
        direction=direction,
        originating_decision_id=uuid4() if status != ExpansionStatus.CANDIDATE else None,
        confidence=Decimal(confidence) if confidence is not None else None,
        priority_score=Decimal(priority_score) if priority_score is not None else None,
        reason_code=(
            ExpansionReasonCode.CONTEXT_READY
            if status == ExpansionStatus.EXPANDABLE
            else ExpansionReasonCode.EXPANSION_ABSTAINED
        ),
    )


def test_portfolio_governor_runtime_requires_explicit_start() -> None:
    runtime = create_portfolio_governor_runtime()

    with pytest.raises(RuntimeError, match="не запущен"):
        runtime.ingest_expansion(
            expansion=_make_expansion_candidate(),
            reference_time=datetime(2026, 3, 22, 12, 1, tzinfo=UTC),
        )


def test_portfolio_governor_runtime_start_and_stop_reset_operator_state() -> None:
    runtime = create_portfolio_governor_runtime()

    asyncio.run(runtime.start())
    runtime.mark_degraded("governor_ingest_failed")
    runtime.ingest_expansion(
        expansion=_make_expansion_candidate(),
        reference_time=datetime(2026, 3, 22, 12, 1, tzinfo=UTC),
    )
    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["started"] is True
    assert diagnostics["tracked_governor_keys"] == 1

    asyncio.run(runtime.stop())
    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["started"] is False
    assert diagnostics["tracked_context_keys"] == 0
    assert diagnostics["tracked_governor_keys"] == 0
    assert diagnostics["approved_keys"] == 0
    assert diagnostics["abstained_keys"] == 0
    assert diagnostics["rejected_keys"] == 0
    assert diagnostics["invalidated_governor_keys"] == 0
    assert diagnostics["expired_governor_keys"] == 0
    assert diagnostics["last_expansion_id"] is None
    assert diagnostics["last_governor_id"] is None
    assert diagnostics["last_event_type"] is None
    assert diagnostics["last_failure_reason"] is None
    assert diagnostics["lifecycle_state"] == PortfolioGovernorRuntimeLifecycleState.STOPPED.value
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


def test_portfolio_governor_runtime_builds_approved_candidate_from_expandable_expansion() -> None:
    runtime = create_portfolio_governor_runtime()
    asyncio.run(runtime.start())

    update = runtime.ingest_expansion(
        expansion=_make_expansion_candidate(
            status=ExpansionStatus.EXPANDABLE,
            decision=ExpansionDecision.ADD,
            direction=ExpansionDirection.LONG,
            confidence="0.88",
            priority_score="0.91",
        ),
        reference_time=datetime(2026, 3, 22, 12, 1, tzinfo=UTC),
    )

    assert update.candidate is not None
    assert update.candidate.status == GovernorStatus.APPROVED
    assert update.candidate.decision == GovernorDecision.APPROVE
    assert update.candidate.reason_code == GovernorReasonCode.CONTEXT_READY
    assert update.candidate.capital_fraction == Decimal("0.1000")
    assert update.event_type == PortfolioGovernorEventType.PORTFOLIO_GOVERNOR_APPROVED
    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["ready"] is True
    assert diagnostics["lifecycle_state"] == PortfolioGovernorRuntimeLifecycleState.READY.value
    assert diagnostics["approved_keys"] == 1


def test_portfolio_governor_runtime_returns_abstained_candidate_when_expansion_is_too_weak() -> (
    None
):
    runtime = create_portfolio_governor_runtime(
        config=PortfolioGovernorRuntimeConfig(
            min_confidence_for_approval=Decimal("0.70"),
            min_priority_score_for_approval=Decimal("0.70"),
        )
    )
    asyncio.run(runtime.start())

    update = runtime.ingest_expansion(
        expansion=_make_expansion_candidate(
            confidence="0.40",
            priority_score="0.40",
        ),
        reference_time=datetime(2026, 3, 22, 12, 1, tzinfo=UTC),
    )

    assert update.candidate is not None
    assert update.candidate.status == GovernorStatus.ABSTAINED
    assert update.candidate.decision == GovernorDecision.ABSTAIN
    assert update.candidate.reason_code == GovernorReasonCode.GOVERNOR_ABSTAINED
    assert update.event_type == PortfolioGovernorEventType.PORTFOLIO_GOVERNOR_CANDIDATE_UPDATED


def test_portfolio_governor_runtime_creates_warming_context_for_candidate_expansion() -> None:
    runtime = create_portfolio_governor_runtime()
    asyncio.run(runtime.start())

    update = runtime.ingest_expansion(
        expansion=_make_expansion_candidate(
            status=ExpansionStatus.CANDIDATE,
            decision=ExpansionDecision.ABSTAIN,
            direction=None,
            confidence=None,
            priority_score=None,
        ),
        reference_time=datetime(2026, 3, 22, 12, 1, tzinfo=UTC),
    )

    assert update.context.validity.status == GovernorValidityStatus.WARMING
    assert update.context.validity.missing_inputs == ("approvable_expansion",)
    assert update.candidate is not None
    assert update.candidate.status == GovernorStatus.CANDIDATE
    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["ready"] is False
    assert diagnostics["lifecycle_state"] == PortfolioGovernorRuntimeLifecycleState.WARMING.value


def test_portfolio_governor_runtime_rejects_non_approvable_expansion_without_previous_active_state() -> (
    None
):
    runtime = create_portfolio_governor_runtime()
    asyncio.run(runtime.start())

    update = runtime.ingest_expansion(
        expansion=_make_expansion_candidate(
            status=ExpansionStatus.ABSTAINED,
            decision=ExpansionDecision.ABSTAIN,
            direction=None,
        ),
        reference_time=datetime(2026, 3, 22, 12, 1, tzinfo=UTC),
    )

    assert update.candidate is not None
    assert update.candidate.status == GovernorStatus.REJECTED
    assert update.candidate.decision == GovernorDecision.REJECT
    assert update.candidate.reason_code == GovernorReasonCode.GOVERNOR_REJECTED
    assert update.event_type == PortfolioGovernorEventType.PORTFOLIO_GOVERNOR_CANDIDATE_UPDATED
    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["rejected_keys"] == 1


def test_portfolio_governor_runtime_invalidates_previous_candidate_when_expansion_breaks() -> None:
    runtime = create_portfolio_governor_runtime()
    asyncio.run(runtime.start())

    first = runtime.ingest_expansion(
        expansion=_make_expansion_candidate(),
        reference_time=datetime(2026, 3, 22, 12, 1, tzinfo=UTC),
    )
    assert first.candidate is not None
    assert first.candidate.status == GovernorStatus.APPROVED

    second = runtime.ingest_expansion(
        expansion=_make_expansion_candidate(
            status=ExpansionStatus.INVALIDATED,
            decision=ExpansionDecision.REJECT,
            direction=None,
        ),
        reference_time=datetime(2026, 3, 22, 12, 2, tzinfo=UTC),
    )

    assert second.candidate is not None
    assert second.candidate.status == GovernorStatus.INVALIDATED
    assert second.candidate.governor_id == first.candidate.governor_id
    assert second.event_type == PortfolioGovernorEventType.PORTFOLIO_GOVERNOR_INVALIDATED
    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["invalidated_governor_keys"] == 1


def test_portfolio_governor_runtime_expires_candidate_only_against_reference_time() -> None:
    runtime = create_portfolio_governor_runtime(
        config=PortfolioGovernorRuntimeConfig(max_candidate_age_seconds=60),
    )
    asyncio.run(runtime.start())

    generated_at = datetime(2026, 3, 22, 12, 0, tzinfo=UTC)
    update = runtime.ingest_expansion(
        expansion=_make_expansion_candidate(
            generated_at=generated_at,
            expires_at=generated_at + timedelta(minutes=5),
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
    assert not_expired.status == GovernorStatus.APPROVED

    expired = runtime.expire_candidates(reference_time=generated_at + timedelta(seconds=60))
    assert len(expired) == 1
    assert expired[0].candidate is not None
    assert expired[0].candidate.status == GovernorStatus.EXPIRED
    assert expired[0].candidate.reason_code == GovernorReasonCode.GOVERNOR_EXPIRED
    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["expired_governor_keys"] == 1
    assert (
        diagnostics["last_event_type"]
        == PortfolioGovernorEventType.PORTFOLIO_GOVERNOR_INVALIDATED.value
    )


def test_portfolio_governor_runtime_marks_degraded_and_keeps_operator_truth_visible() -> None:
    runtime = PortfolioGovernorRuntime()

    asyncio.run(runtime.start())
    runtime.mark_degraded("governor_ingest_failed")
    diagnostics = runtime.get_runtime_diagnostics()

    assert diagnostics["ready"] is False
    assert diagnostics["lifecycle_state"] == PortfolioGovernorRuntimeLifecycleState.DEGRADED.value
    assert diagnostics["last_failure_reason"] == "governor_ingest_failed"
    assert diagnostics["degraded_reasons"] == ["governor_ingest_failed"]


def test_portfolio_governor_runtime_uses_runtime_config_in_state_keying() -> None:
    runtime = create_portfolio_governor_runtime(
        config=PortfolioGovernorRuntimeConfig(
            contour_name="custom_portfolio_governor_contour",
            governor_name="custom_portfolio_governor",
        )
    )
    asyncio.run(runtime.start())

    runtime.ingest_expansion(
        expansion=_make_expansion_candidate(),
        reference_time=datetime(2026, 3, 22, 12, 1, tzinfo=UTC),
    )

    candidate = runtime.get_candidate(
        symbol="BTCUSDT",
        exchange="BINANCE",
        timeframe=MarketDataTimeframe.M5,
    )
    context = runtime.get_context(
        symbol="BTCUSDT",
        exchange="BINANCE",
        timeframe=MarketDataTimeframe.M5,
    )

    assert candidate is not None
    assert candidate.contour_name == "custom_portfolio_governor_contour"
    assert candidate.governor_name == "custom_portfolio_governor"
    assert context is not None
    assert context.contour_name == "custom_portfolio_governor_contour"
    assert context.governor_name == "custom_portfolio_governor"

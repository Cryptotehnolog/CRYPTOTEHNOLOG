from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

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
    ProtectionDecision,
    ProtectionEventType,
    ProtectionReasonCode,
    ProtectionRuntime,
    ProtectionRuntimeConfig,
    ProtectionRuntimeLifecycleState,
    ProtectionStatus,
    create_protection_runtime,
)


def _make_governor_candidate(
    *,
    status: GovernorStatus = GovernorStatus.APPROVED,
    decision: GovernorDecision = GovernorDecision.APPROVE,
    confidence: str | None = "0.87",
    priority_score: str | None = "0.8800",
    generated_at: datetime | None = None,
    expires_at: datetime | None = None,
) -> PortfolioGovernorCandidate:
    now = generated_at or datetime(2026, 3, 22, 12, 0, tzinfo=UTC)
    validity = (
        GovernorValidity(
            status=GovernorValidityStatus.VALID,
            observed_inputs=1,
            required_inputs=1,
        )
        if status in {GovernorStatus.APPROVED, GovernorStatus.CANDIDATE}
        else GovernorValidity(
            status=GovernorValidityStatus.INVALID,
            observed_inputs=1,
            required_inputs=1,
            invalid_reason="portfolio_governor_lost",
        )
    )
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
            expires_at=expires_at or (now + timedelta(minutes=5)),
        ),
        validity=validity,
        status=status,
        decision=decision,
        direction=GovernorDirection.LONG if status == GovernorStatus.APPROVED else None,
        originating_expansion_id=uuid4() if status != GovernorStatus.CANDIDATE else None,
        confidence=Decimal(confidence) if confidence is not None else None,
        priority_score=Decimal(priority_score) if priority_score is not None else None,
        capital_fraction=Decimal("0.1000") if status == GovernorStatus.APPROVED else None,
        reason_code=(
            GovernorReasonCode.CONTEXT_READY
            if status == GovernorStatus.APPROVED
            else GovernorReasonCode.CONTEXT_INCOMPLETE
        ),
    )


def test_protection_runtime_requires_explicit_start() -> None:
    runtime = create_protection_runtime()

    with pytest.raises(RuntimeError, match="не запущен"):
        runtime.ingest_governor(
            governor=_make_governor_candidate(),
            reference_time=datetime(2026, 3, 22, 12, 1, tzinfo=UTC),
        )


def test_protection_runtime_start_and_stop_reset_operator_state() -> None:
    runtime = create_protection_runtime()

    asyncio.run(runtime.start())
    runtime.mark_degraded("protection_ingest_failed")
    runtime.ingest_governor(
        governor=_make_governor_candidate(),
        reference_time=datetime(2026, 3, 22, 12, 1, tzinfo=UTC),
    )
    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["started"] is True
    assert diagnostics["tracked_protection_keys"] == 1

    asyncio.run(runtime.stop())
    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["started"] is False
    assert diagnostics["tracked_context_keys"] == 0
    assert diagnostics["tracked_protection_keys"] == 0
    assert diagnostics["protected_keys"] == 0
    assert diagnostics["halted_keys"] == 0
    assert diagnostics["frozen_keys"] == 0
    assert diagnostics["invalidated_protection_keys"] == 0
    assert diagnostics["expired_protection_keys"] == 0
    assert diagnostics["last_governor_id"] is None
    assert diagnostics["last_protection_id"] is None
    assert diagnostics["last_event_type"] is None
    assert diagnostics["last_failure_reason"] is None
    assert diagnostics["lifecycle_state"] == ProtectionRuntimeLifecycleState.STOPPED.value
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


def test_protection_runtime_builds_protected_candidate_from_approved_governor() -> None:
    runtime = create_protection_runtime()
    asyncio.run(runtime.start())

    update = runtime.ingest_governor(
        governor=_make_governor_candidate(priority_score="0.8800"),
        reference_time=datetime(2026, 3, 22, 12, 1, tzinfo=UTC),
    )

    assert update.candidate is not None
    assert update.candidate.status == ProtectionStatus.PROTECTED
    assert update.candidate.decision == ProtectionDecision.PROTECT
    assert update.candidate.reason_code == ProtectionReasonCode.PROTECTION_PROTECTED
    assert update.event_type == ProtectionEventType.PROTECTION_PROTECTED
    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["ready"] is True
    assert diagnostics["lifecycle_state"] == ProtectionRuntimeLifecycleState.READY.value
    assert diagnostics["protected_keys"] == 1


def test_protection_runtime_builds_halted_candidate_at_halt_threshold() -> None:
    runtime = create_protection_runtime(
        config=ProtectionRuntimeConfig(halt_priority_threshold=Decimal("0.90"))
    )
    asyncio.run(runtime.start())

    update = runtime.ingest_governor(
        governor=_make_governor_candidate(priority_score="0.9300"),
        reference_time=datetime(2026, 3, 22, 12, 1, tzinfo=UTC),
    )

    assert update.candidate is not None
    assert update.candidate.status == ProtectionStatus.HALTED
    assert update.candidate.decision == ProtectionDecision.HALT
    assert update.candidate.reason_code == ProtectionReasonCode.PROTECTION_HALTED
    assert update.event_type == ProtectionEventType.PROTECTION_HALTED
    assert runtime.get_runtime_diagnostics()["halted_keys"] == 1


def test_protection_runtime_builds_frozen_candidate_at_freeze_threshold() -> None:
    runtime = create_protection_runtime(
        config=ProtectionRuntimeConfig(
            halt_priority_threshold=Decimal("0.90"),
            freeze_priority_threshold=Decimal("0.97"),
        )
    )
    asyncio.run(runtime.start())

    update = runtime.ingest_governor(
        governor=_make_governor_candidate(priority_score="0.9900"),
        reference_time=datetime(2026, 3, 22, 12, 1, tzinfo=UTC),
    )

    assert update.candidate is not None
    assert update.candidate.status == ProtectionStatus.FROZEN
    assert update.candidate.decision == ProtectionDecision.FREEZE
    assert update.candidate.reason_code == ProtectionReasonCode.PROTECTION_FROZEN
    assert update.event_type == ProtectionEventType.PROTECTION_FROZEN
    assert runtime.get_runtime_diagnostics()["frozen_keys"] == 1


def test_protection_runtime_creates_warming_context_for_candidate_governor() -> None:
    runtime = create_protection_runtime()
    asyncio.run(runtime.start())

    update = runtime.ingest_governor(
        governor=_make_governor_candidate(
            status=GovernorStatus.CANDIDATE,
            decision=GovernorDecision.APPROVE,
            confidence=None,
            priority_score=None,
        ),
        reference_time=datetime(2026, 3, 22, 12, 1, tzinfo=UTC),
    )

    assert update.context.validity.status == GovernorValidityStatus.WARMING
    assert update.context.validity.missing_inputs == ("approved_governor",)
    assert update.candidate is not None
    assert update.candidate.status == ProtectionStatus.CANDIDATE
    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["ready"] is False
    assert diagnostics["lifecycle_state"] == ProtectionRuntimeLifecycleState.WARMING.value


def test_protection_runtime_keeps_candidate_for_non_approved_governor_without_previous_active_state() -> (
    None
):
    runtime = create_protection_runtime()
    asyncio.run(runtime.start())

    update = runtime.ingest_governor(
        governor=_make_governor_candidate(
            status=GovernorStatus.REJECTED,
            decision=GovernorDecision.REJECT,
            confidence=None,
            priority_score=None,
        ),
        reference_time=datetime(2026, 3, 22, 12, 1, tzinfo=UTC),
    )

    assert update.candidate is not None
    assert update.candidate.status == ProtectionStatus.CANDIDATE
    assert update.candidate.decision == ProtectionDecision.PROTECT
    assert update.candidate.reason_code == ProtectionReasonCode.GOVERNOR_NOT_APPROVED
    assert update.event_type == ProtectionEventType.PROTECTION_CANDIDATE_UPDATED


def test_protection_runtime_invalidates_previous_candidate_when_governor_breaks() -> None:
    runtime = create_protection_runtime()
    asyncio.run(runtime.start())

    first = runtime.ingest_governor(
        governor=_make_governor_candidate(priority_score="0.8800"),
        reference_time=datetime(2026, 3, 22, 12, 1, tzinfo=UTC),
    )
    assert first.candidate is not None
    assert first.candidate.status == ProtectionStatus.PROTECTED

    second = runtime.ingest_governor(
        governor=_make_governor_candidate(
            status=GovernorStatus.INVALIDATED,
            decision=GovernorDecision.REJECT,
            confidence=None,
            priority_score=None,
        ),
        reference_time=datetime(2026, 3, 22, 12, 2, tzinfo=UTC),
    )

    assert second.candidate is not None
    assert second.candidate.status == ProtectionStatus.INVALIDATED
    assert second.candidate.protection_id == first.candidate.protection_id
    assert second.event_type == ProtectionEventType.PROTECTION_INVALIDATED
    assert runtime.get_runtime_diagnostics()["invalidated_protection_keys"] == 1


def test_protection_runtime_expires_candidate_only_against_reference_time() -> None:
    runtime = create_protection_runtime(
        config=ProtectionRuntimeConfig(max_candidate_age_seconds=60),
    )
    asyncio.run(runtime.start())

    generated_at = datetime(2026, 3, 22, 12, 0, tzinfo=UTC)
    update = runtime.ingest_governor(
        governor=_make_governor_candidate(
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
    assert not_expired.status == ProtectionStatus.PROTECTED

    expired = runtime.expire_candidates(reference_time=generated_at + timedelta(seconds=60))
    assert len(expired) == 1
    assert expired[0].candidate is not None
    assert expired[0].candidate.status == ProtectionStatus.EXPIRED
    assert expired[0].candidate.reason_code == ProtectionReasonCode.PROTECTION_EXPIRED
    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["expired_protection_keys"] == 1
    assert diagnostics["last_event_type"] == ProtectionEventType.PROTECTION_INVALIDATED.value


def test_protection_runtime_marks_degraded_and_keeps_operator_truth_visible() -> None:
    runtime = ProtectionRuntime()

    asyncio.run(runtime.start())
    runtime.mark_degraded("protection_ingest_failed")
    diagnostics = runtime.get_runtime_diagnostics()

    assert diagnostics["ready"] is False
    assert diagnostics["lifecycle_state"] == ProtectionRuntimeLifecycleState.DEGRADED.value
    assert diagnostics["last_failure_reason"] == "protection_ingest_failed"
    assert diagnostics["degraded_reasons"] == ["protection_ingest_failed"]


def test_protection_runtime_uses_runtime_config_in_state_keying() -> None:
    runtime = create_protection_runtime(
        config=ProtectionRuntimeConfig(
            contour_name="custom_protection_contour",
            supervisor_name="custom_protection",
        )
    )
    asyncio.run(runtime.start())

    runtime.ingest_governor(
        governor=_make_governor_candidate(),
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
    assert candidate.contour_name == "custom_protection_contour"
    assert candidate.supervisor_name == "custom_protection"
    assert context is not None
    assert context.contour_name == "custom_protection_contour"
    assert context.supervisor_name == "custom_protection"

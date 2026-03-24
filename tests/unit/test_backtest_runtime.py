from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from cryptotechnolog.backtest import (
    HistoricalInputContract,
    HistoricalInputKind,
    ReplayCoverageWindow,
    ReplayDecision,
    ReplayEventType,
    ReplayIntegrityStatus,
    ReplayReasonCode,
    ReplayRuntimeLifecycleState,
    ReplayStatus,
    ReplayValidityStatus,
    create_replay_runtime,
)
from cryptotechnolog.market_data import MarketDataTimeframe


def _now() -> datetime:
    return datetime(2026, 3, 24, 12, 0, tzinfo=UTC)


def _historical_input(
    *,
    observed_events: int = 10,
    expected_events: int = 10,
    metadata: dict[str, object] | None = None,
) -> HistoricalInputContract:
    return HistoricalInputContract.candidate(
        input_name="btcusdt_m1_window",
        symbol="BTCUSDT",
        exchange="BINANCE",
        kind=HistoricalInputKind.BAR_STREAM,
        timeframe=MarketDataTimeframe.M1,
        coverage_window=ReplayCoverageWindow(
            start_at=_now() - timedelta(minutes=5),
            end_at=_now(),
            observed_events=observed_events,
            expected_events=expected_events,
        ),
        source_reference="fixtures/btcusdt_m1.csv",
        metadata={} if metadata is None else metadata,
    )


@pytest.mark.asyncio
async def test_replay_runtime_starts_and_stops_explicitly() -> None:
    runtime = create_replay_runtime()

    assert runtime.is_started is False

    await runtime.start()
    started = runtime.get_runtime_diagnostics()
    assert started["started"] is True
    assert started["lifecycle_state"] == ReplayRuntimeLifecycleState.WARMING.value

    await runtime.stop()
    stopped = runtime.get_runtime_diagnostics()
    assert stopped["started"] is False
    assert stopped["lifecycle_state"] == ReplayRuntimeLifecycleState.STOPPED.value
    assert stopped["tracked_inputs"] == 0
    assert stopped["tracked_active_replays"] == 0


@pytest.mark.asyncio
async def test_replay_runtime_builds_replayed_candidate_from_ready_historical_input() -> None:
    runtime = create_replay_runtime()
    await runtime.start()

    validation_review_id = uuid4()
    paper_rehearsal_id = uuid4()
    update = runtime.ingest_historical_input(
        historical_input=_historical_input(
            metadata={
                "validation_review_id": validation_review_id,
                "paper_rehearsal_id": str(paper_rehearsal_id),
                "recorded_events": 10,
                "persisted_artifact": False,
                "last_recorded_at": _now(),
            }
        ),
        reference_time=_now(),
    )

    assert update.historical_input is not None
    assert update.context is not None
    assert update.context.validity.is_valid is True
    assert update.context.validation_review_id == validation_review_id
    assert update.context.paper_rehearsal_id == paper_rehearsal_id
    assert update.replay_candidate is not None
    assert update.replay_candidate.status == ReplayStatus.REPLAYED
    assert update.replay_candidate.decision == ReplayDecision.REPLAY
    assert update.event_type == ReplayEventType.REPLAY_EXECUTED
    assert update.replay_candidate.recorder_state is not None
    assert update.emitted_input_payload is not None
    assert update.emitted_candidate_payload is not None

    key = ("BTCUSDT", "BINANCE", MarketDataTimeframe.M1.value)
    assert runtime.get_input(key) is not None
    assert runtime.get_context(key) is not None
    assert runtime.get_candidate(key) is not None
    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["ready"] is True
    assert diagnostics["tracked_inputs"] == 1
    assert diagnostics["tracked_active_replays"] == 1


@pytest.mark.asyncio
async def test_replay_runtime_creates_warming_candidate_for_incomplete_window() -> None:
    runtime = create_replay_runtime()
    await runtime.start()

    update = runtime.ingest_historical_input(
        historical_input=_historical_input(observed_events=6, expected_events=10),
        reference_time=_now(),
    )

    assert update.context is not None
    assert update.context.validity.status == ReplayValidityStatus.WARMING
    assert update.replay_candidate is not None
    assert update.replay_candidate.status == ReplayStatus.CANDIDATE
    assert update.replay_candidate.decision == ReplayDecision.ABSTAIN
    assert update.event_type == ReplayEventType.REPLAY_CANDIDATE_UPDATED

    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["ready"] is False
    assert "coverage_window_incomplete" in diagnostics["readiness_reasons"]


@pytest.mark.asyncio
async def test_replay_runtime_abstains_for_invalid_historical_input() -> None:
    runtime = create_replay_runtime()
    await runtime.start()

    update = runtime.ingest_historical_input(
        historical_input=_historical_input(observed_events=0, expected_events=10),
        reference_time=_now(),
    )

    assert update.context is not None
    assert update.context.validity.status == ReplayValidityStatus.INVALID
    assert update.replay_candidate is not None
    assert update.replay_candidate.status == ReplayStatus.ABSTAINED
    assert update.replay_candidate.decision == ReplayDecision.ABSTAIN
    assert update.event_type == ReplayEventType.REPLAY_ABSTAINED

    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["ready"] is False
    assert diagnostics["lifecycle_state"] == ReplayRuntimeLifecycleState.DEGRADED.value
    assert diagnostics["last_failure_reason"] == "historical_input_empty_or_invalid"


@pytest.mark.asyncio
async def test_replay_runtime_blocks_lookahead_historical_input() -> None:
    runtime = create_replay_runtime()
    await runtime.start()

    update = runtime.ingest_historical_input(
        historical_input=_historical_input(),
        reference_time=_now() - timedelta(minutes=1),
    )

    assert update.context is not None
    assert update.context.validity.status == ReplayValidityStatus.INVALID
    assert update.context.validity.invalid_reason == "historical_input_lookahead_detected"
    assert update.replay_candidate is not None
    assert update.replay_candidate.status == ReplayStatus.ABSTAINED
    assert update.replay_candidate.decision == ReplayDecision.ABSTAIN
    assert update.replay_candidate.reason_code == ReplayReasonCode.INPUT_WINDOW_LOOKAHEAD
    assert update.event_type == ReplayEventType.REPLAY_ABSTAINED

    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["ready"] is False
    assert diagnostics["last_failure_reason"] == "historical_input_lookahead_detected"
    assert "historical_input_lookahead_detected" in diagnostics["degraded_reasons"]


@pytest.mark.asyncio
async def test_replay_runtime_rejects_regressive_historical_window_for_same_state_key() -> None:
    runtime = create_replay_runtime()
    await runtime.start()
    runtime.ingest_historical_input(
        historical_input=_historical_input(),
        reference_time=_now(),
    )

    update = runtime.ingest_historical_input(
        historical_input=HistoricalInputContract.candidate(
            input_name="btcusdt_m1_window",
            symbol="BTCUSDT",
            exchange="BINANCE",
            kind=HistoricalInputKind.BAR_STREAM,
            timeframe=MarketDataTimeframe.M1,
            coverage_window=ReplayCoverageWindow(
                start_at=_now() - timedelta(minutes=6),
                end_at=_now() - timedelta(minutes=1),
                observed_events=6,
                expected_events=6,
            ),
            source_reference="fixtures/btcusdt_m1_regressed.csv",
        ),
        reference_time=_now(),
    )

    assert update.context is not None
    assert update.context.integrity.status == ReplayIntegrityStatus.REGRESSED
    assert update.context.validity.status == ReplayValidityStatus.INVALID
    assert update.context.validity.invalid_reason == "historical_input_window_regressed"
    assert update.replay_candidate is not None
    assert update.replay_candidate.status == ReplayStatus.INVALIDATED
    assert update.event_type == ReplayEventType.REPLAY_INVALIDATED

    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["last_failure_reason"] == "historical_input_window_regressed"
    assert "historical_input_window_regressed" in diagnostics["degraded_reasons"]


@pytest.mark.asyncio
async def test_replay_runtime_rejects_coverage_drift_for_same_window() -> None:
    runtime = create_replay_runtime()
    await runtime.start()
    runtime.ingest_historical_input(
        historical_input=_historical_input(observed_events=10, expected_events=10),
        reference_time=_now(),
    )

    update = runtime.ingest_historical_input(
        historical_input=_historical_input(observed_events=9, expected_events=10),
        reference_time=_now(),
    )

    assert update.context is not None
    assert update.context.integrity.status == ReplayIntegrityStatus.DRIFTED
    assert update.context.validity.status == ReplayValidityStatus.INVALID
    assert update.context.validity.invalid_reason == "historical_input_coverage_drift_detected"
    assert update.replay_candidate is not None
    assert update.replay_candidate.status == ReplayStatus.INVALIDATED
    assert update.event_type == ReplayEventType.REPLAY_INVALIDATED

    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["last_failure_reason"] == "historical_input_coverage_drift_detected"
    assert "historical_input_coverage_drift_detected" in diagnostics["degraded_reasons"]


@pytest.mark.asyncio
async def test_replay_runtime_invalidates_existing_candidate_when_input_becomes_invalid() -> None:
    runtime = create_replay_runtime()
    await runtime.start()
    runtime.ingest_historical_input(
        historical_input=_historical_input(),
        reference_time=_now(),
    )

    update = runtime.ingest_historical_input(
        historical_input=_historical_input(observed_events=0, expected_events=10),
        reference_time=_now() + timedelta(minutes=1),
    )

    assert update.replay_candidate is not None
    assert update.replay_candidate.status == ReplayStatus.INVALIDATED
    assert update.event_type == ReplayEventType.REPLAY_INVALIDATED
    assert runtime.list_active_candidates() == ()
    assert len(runtime.list_historical_candidates()) == 1


@pytest.mark.asyncio
async def test_replay_runtime_expires_active_candidate_into_historical_registry() -> None:
    runtime = create_replay_runtime()
    await runtime.start()
    reference_time = _now()
    update = runtime.ingest_historical_input(
        historical_input=_historical_input(),
        reference_time=reference_time,
    )

    assert update.replay_candidate is not None

    expired = runtime.expire_candidates(reference_time=reference_time + timedelta(hours=2))

    assert len(expired) == 1
    assert expired[0].status == ReplayStatus.EXPIRED
    assert runtime.list_active_candidates() == ()
    assert len(runtime.list_historical_candidates()) == 1


@pytest.mark.asyncio
async def test_replay_runtime_rejects_ingest_before_explicit_start() -> None:
    runtime = create_replay_runtime()

    with pytest.raises(RuntimeError, match="явно запущен"):
        runtime.ingest_historical_input(
            historical_input=_historical_input(),
            reference_time=_now(),
        )


@pytest.mark.asyncio
async def test_replay_runtime_mark_degraded_updates_operator_truth() -> None:
    runtime = create_replay_runtime()
    await runtime.start()

    runtime.mark_degraded("manual_replay_degraded")

    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["lifecycle_state"] == ReplayRuntimeLifecycleState.DEGRADED.value
    assert diagnostics["ready"] is False
    assert "manual_replay_degraded" in diagnostics["degraded_reasons"]

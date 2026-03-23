from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

import cryptotechnolog.backtest as backtest_package
from cryptotechnolog.backtest import (
    HistoricalInputContract,
    HistoricalInputKind,
    HistoricalInputPayload,
    ReplayCandidate,
    ReplayCandidatePayload,
    ReplayContext,
    ReplayCoverageWindow,
    ReplayDecision,
    ReplayEngine,
    ReplayEventSource,
    ReplayEventType,
    ReplayFreshness,
    ReplayReasonCode,
    ReplayRecorderState,
    ReplayRuntimeConfig,
    ReplayRuntimeDiagnostics,
    ReplayRuntimeLifecycleState,
    ReplayRuntimeUpdate,
    ReplaySource,
    ReplayStatus,
    ReplayValidity,
    ReplayValidityStatus,
    build_replay_event,
    create_replay_runtime,
)
from cryptotechnolog.market_data import MarketDataTimeframe


class TestReplayCoverageWindow:
    def test_coverage_ratio_is_normalized(self) -> None:
        window = ReplayCoverageWindow(
            start_at=datetime(2026, 3, 24, 10, 0, tzinfo=UTC),
            end_at=datetime(2026, 3, 24, 11, 0, tzinfo=UTC),
            observed_events=75,
            expected_events=100,
        )

        assert window.duration_seconds == 3600
        assert window.coverage_ratio == Decimal("0.7500")

    def test_invalid_window_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="end_at >= start_at"):
            ReplayCoverageWindow(
                start_at=datetime(2026, 3, 24, 11, 0, tzinfo=UTC),
                end_at=datetime(2026, 3, 24, 10, 0, tzinfo=UTC),
                observed_events=10,
                expected_events=10,
            )


class TestHistoricalInputContract:
    def test_candidate_defaults_to_historical_inputs_source(self) -> None:
        window = ReplayCoverageWindow(
            start_at=datetime(2026, 3, 24, 10, 0, tzinfo=UTC),
            end_at=datetime(2026, 3, 24, 10, 5, tzinfo=UTC),
            observed_events=5,
            expected_events=5,
        )

        historical_input = HistoricalInputContract.candidate(
            input_name="btcusdt_m1_window",
            symbol="BTC/USDT",
            exchange="bybit",
            kind=HistoricalInputKind.BAR_STREAM,
            timeframe=MarketDataTimeframe.M1,
            coverage_window=window,
            source_reference="fixtures/btcusdt_m1.csv",
        )

        assert historical_input.source == ReplaySource.HISTORICAL_INPUTS
        assert historical_input.timeframe == MarketDataTimeframe.M1


class TestReplayValidity:
    def test_readiness_ratio_is_normalized(self) -> None:
        validity = ReplayValidity(
            status=ReplayValidityStatus.WARMING,
            observed_inputs=2,
            required_inputs=3,
            missing_inputs=("recorder_state",),
        )

        assert validity.is_warming is True
        assert validity.readiness_ratio == Decimal("0.6667")


class TestReplayContracts:
    def test_replayed_candidate_requires_validity_and_historical_input(self) -> None:
        window = ReplayCoverageWindow(
            start_at=datetime(2026, 3, 24, 10, 0, tzinfo=UTC),
            end_at=datetime(2026, 3, 24, 10, 5, tzinfo=UTC),
            observed_events=5,
            expected_events=5,
        )
        freshness = ReplayFreshness(
            generated_at=datetime(2026, 3, 24, 10, 6, tzinfo=UTC),
            expires_at=datetime(2026, 3, 24, 11, 6, tzinfo=UTC),
        )

        with pytest.raises(ValueError, match="historical input"):
            ReplayCandidate.candidate(
                contour_name="phase20_replay_contour",
                replay_name="phase20_backtest",
                symbol="BTC/USDT",
                exchange="bybit",
                source=ReplaySource.HISTORICAL_INPUTS,
                freshness=freshness,
                coverage_window=window,
                validity=ReplayValidity(
                    status=ReplayValidityStatus.VALID,
                    observed_inputs=1,
                    required_inputs=1,
                ),
                decision=ReplayDecision.REPLAY,
                status=ReplayStatus.REPLAYED,
            )

    def test_replay_context_distinguishes_validation_and_paper_truth(self) -> None:
        window = ReplayCoverageWindow(
            start_at=datetime(2026, 3, 24, 10, 0, tzinfo=UTC),
            end_at=datetime(2026, 3, 24, 10, 5, tzinfo=UTC),
            observed_events=5,
            expected_events=5,
        )
        historical_input = HistoricalInputContract.candidate(
            input_name="btcusdt_m1_window",
            symbol="BTC/USDT",
            exchange="bybit",
            kind=HistoricalInputKind.BAR_STREAM,
            timeframe=MarketDataTimeframe.M1,
            coverage_window=window,
        )
        validation_review_id = uuid4()
        paper_rehearsal_id = uuid4()

        context = ReplayContext(
            replay_name="phase20_backtest",
            contour_name="phase20_replay_contour",
            observed_at=datetime(2026, 3, 24, 10, 6, tzinfo=UTC),
            source=ReplaySource.HISTORICAL_INPUTS,
            historical_input=historical_input,
            validity=ReplayValidity(
                status=ReplayValidityStatus.VALID,
                observed_inputs=1,
                required_inputs=1,
            ),
            validation_review_id=validation_review_id,
            paper_rehearsal_id=paper_rehearsal_id,
        )

        assert context.validation_review_id == validation_review_id
        assert context.paper_rehearsal_id == paper_rehearsal_id
        assert context.source == ReplaySource.HISTORICAL_INPUTS

    def test_replay_candidate_can_carry_minimal_recorder_state_without_analytics_ownership(
        self,
    ) -> None:
        window = ReplayCoverageWindow(
            start_at=datetime(2026, 3, 24, 10, 0, tzinfo=UTC),
            end_at=datetime(2026, 3, 24, 10, 5, tzinfo=UTC),
            observed_events=5,
            expected_events=5,
        )
        historical_input = HistoricalInputContract.candidate(
            input_name="btcusdt_m1_window",
            symbol="BTC/USDT",
            exchange="bybit",
            kind=HistoricalInputKind.BAR_STREAM,
            timeframe=MarketDataTimeframe.M1,
            coverage_window=window,
        )

        candidate = ReplayCandidate.candidate(
            contour_name="phase20_replay_contour",
            replay_name="phase20_backtest",
            symbol="BTC/USDT",
            exchange="bybit",
            source=ReplaySource.HISTORICAL_INPUTS,
            freshness=ReplayFreshness(
                generated_at=datetime(2026, 3, 24, 10, 6, tzinfo=UTC),
                expires_at=datetime(2026, 3, 24, 11, 6, tzinfo=UTC),
            ),
            coverage_window=historical_input.coverage_window,
            validity=ReplayValidity(
                status=ReplayValidityStatus.VALID,
                observed_inputs=1,
                required_inputs=1,
            ),
            decision=ReplayDecision.REPLAY,
            status=ReplayStatus.REPLAYED,
            historical_input_id=historical_input.input_id,
            timeframe=historical_input.timeframe,
            recorder_state=ReplayRecorderState(
                recorded_events=5,
                persisted_artifact=False,
                last_recorded_at=datetime(2026, 3, 24, 10, 6, tzinfo=UTC),
            ),
            reason_code=ReplayReasonCode.REPLAY_EXECUTED,
        )

        assert candidate.is_replayed is True
        assert candidate.recorder_state is not None
        assert candidate.recorder_state.recorded_events == 5


class TestReplayEvents:
    def test_historical_input_payload_is_typed(self) -> None:
        window = ReplayCoverageWindow(
            start_at=datetime(2026, 3, 24, 10, 0, tzinfo=UTC),
            end_at=datetime(2026, 3, 24, 10, 5, tzinfo=UTC),
            observed_events=5,
            expected_events=5,
        )
        historical_input = HistoricalInputContract.candidate(
            input_name="btcusdt_m1_window",
            symbol="BTC/USDT",
            exchange="bybit",
            kind=HistoricalInputKind.BAR_STREAM,
            timeframe=MarketDataTimeframe.M1,
            coverage_window=window,
        )
        payload = HistoricalInputPayload.from_input(historical_input)
        event = build_replay_event(
            event_type=ReplayEventType.REPLAY_INPUT_REGISTERED,
            payload=payload,
            source=ReplayEventSource.REPLAY_RUNTIME.value,
        )

        assert event.event_type == ReplayEventType.REPLAY_INPUT_REGISTERED.value
        assert event.source == ReplayEventSource.REPLAY_RUNTIME.value
        assert event.payload["input_name"] == "btcusdt_m1_window"

    def test_replay_candidate_payload_is_typed(self) -> None:
        window = ReplayCoverageWindow(
            start_at=datetime(2026, 3, 24, 10, 0, tzinfo=UTC),
            end_at=datetime(2026, 3, 24, 10, 5, tzinfo=UTC),
            observed_events=5,
            expected_events=5,
        )
        candidate = ReplayCandidate.candidate(
            contour_name="phase20_replay_contour",
            replay_name="phase20_backtest",
            symbol="BTC/USDT",
            exchange="bybit",
            source=ReplaySource.HISTORICAL_INPUTS,
            freshness=ReplayFreshness(
                generated_at=datetime(2026, 3, 24, 10, 6, tzinfo=UTC),
                expires_at=datetime(2026, 3, 24, 11, 6, tzinfo=UTC),
            ),
            coverage_window=window,
            validity=ReplayValidity(
                status=ReplayValidityStatus.VALID,
                observed_inputs=1,
                required_inputs=1,
            ),
            decision=ReplayDecision.REPLAY,
            status=ReplayStatus.REPLAYED,
            historical_input_id=uuid4(),
            reason_code=ReplayReasonCode.REPLAY_EXECUTED,
        )
        payload = ReplayCandidatePayload.from_candidate(candidate)
        event = build_replay_event(
            event_type=ReplayEventType.REPLAY_EXECUTED,
            payload=payload,
        )

        assert event.event_type == ReplayEventType.REPLAY_EXECUTED.value
        assert event.payload["status"] == ReplayStatus.REPLAYED.value
        assert event.payload["decision"] == ReplayDecision.REPLAY.value


class TestReplayRuntimeBoundary:
    def test_runtime_boundary_shape_is_explicit_but_not_implemented_yet(self) -> None:
        config = ReplayRuntimeConfig(
            contour_name="phase20_replay_contour",
            replay_name="phase20_backtest",
            max_replay_age_seconds=timedelta(hours=1).seconds,
        )
        diagnostics = ReplayRuntimeDiagnostics(
            lifecycle_state=ReplayRuntimeLifecycleState.NOT_STARTED,
        )
        update = ReplayRuntimeUpdate(
            historical_input=None,
            context=None,
            replay_candidate=None,
            event_type=None,
        )

        assert config.replay_name == "phase20_backtest"
        assert diagnostics.to_dict()["lifecycle_state"] == "not_started"
        assert update.replay_candidate is None

        with pytest.raises(NotImplementedError, match="Replay Runtime Foundation"):
            create_replay_runtime(config)


class TestBacktestPackageSurface:
    def test_authoritative_package_surface_excludes_legacy_exports(self) -> None:
        exported = set(backtest_package.__all__)

        assert "ReplayCandidate" in exported
        assert "ReplayEventType" in exported
        assert "ReplayRuntimeConfig" in exported
        assert "ReplayEngine" not in exported
        assert "ReplayConfig" not in exported
        assert "EventRecorder" not in exported
        assert "TickEvent" not in exported
        assert "OrderEvent" not in exported

    def test_legacy_compatibility_names_remain_available(self) -> None:
        assert ReplayEngine is backtest_package.ReplayEngine
        assert hasattr(backtest_package, "ReplayConfig")
        assert hasattr(backtest_package, "EventRecorder")
        assert hasattr(backtest_package, "TickEvent")

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from cryptotechnolog.backtest import (
    HistoricalInputContract,
    HistoricalInputKind,
    ReplayCandidate,
    ReplayCoverageWindow,
    ReplayDecision,
    ReplayFreshness,
    ReplayReasonCode,
    ReplaySource,
    ReplayStatus,
    ReplayValidity,
    ReplayValidityStatus,
)
from cryptotechnolog.manager import (
    ManagerDecision,
    ManagerFreshness,
    ManagerReasonCode,
    ManagerSource,
    ManagerStatus,
    ManagerValidity,
    ManagerValidityStatus,
    ManagerWorkflowCandidate,
)
from cryptotechnolog.market_data import MarketDataTimeframe
from cryptotechnolog.oms import (
    OmsFreshness,
    OmsOrderRecord,
    OmsReasonCode,
    OmsValidity,
    OmsValidityStatus,
)
from cryptotechnolog.paper import (
    PaperDecision,
    PaperFreshness,
    PaperReasonCode,
    PaperRehearsalCandidate,
    PaperSource,
    PaperStatus,
    PaperValidity,
    PaperValidityStatus,
)
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
    ProtectionFreshness,
    ProtectionReasonCode,
    ProtectionSource,
    ProtectionStatus,
    ProtectionSupervisorCandidate,
    ProtectionValidity,
    ProtectionValidityStatus,
)
from cryptotechnolog.reporting import (
    ReportingArtifactKind,
    ReportingSourceLayer,
    assemble_paper_report_artifact,
    assemble_replay_report_artifact,
    assemble_reporting_artifact_bundle,
    assemble_reporting_bundle_from_candidates,
    assemble_validation_report_artifact,
)
from cryptotechnolog.validation import (
    ValidationDecision,
    ValidationFreshness,
    ValidationReasonCode,
    ValidationReviewCandidate,
    ValidationSource,
    ValidationStatus,
    ValidationValidity,
    ValidationValidityStatus,
)


def _now() -> datetime:
    return datetime(2026, 3, 24, 12, 0, tzinfo=UTC)


def _manager() -> ManagerWorkflowCandidate:
    current_time = _now()
    return ManagerWorkflowCandidate.candidate(
        contour_name="phase17_manager_contour",
        manager_name="phase17_manager",
        symbol="BTCUSDT",
        exchange="BINANCE",
        timeframe=MarketDataTimeframe.M15,
        source=ManagerSource.WORKFLOW_FOUNDATIONS,
        freshness=ManagerFreshness(
            generated_at=current_time,
            expires_at=current_time + timedelta(minutes=10),
        ),
        validity=ManagerValidity(
            status=ManagerValidityStatus.VALID,
            observed_inputs=5,
            required_inputs=5,
        ),
        decision=ManagerDecision.COORDINATE,
        status=ManagerStatus.COORDINATED,
        originating_selection_id=uuid4(),
        originating_decision_id=uuid4(),
        originating_expansion_id=uuid4(),
        originating_governor_id=uuid4(),
        originating_protection_id=uuid4(),
        confidence=Decimal("0.85"),
        priority_score=Decimal("0.65"),
        reason_code=ManagerReasonCode.MANAGER_COORDINATED,
    )


def _governor() -> PortfolioGovernorCandidate:
    current_time = _now()
    return PortfolioGovernorCandidate.candidate(
        contour_name="phase14_governor_contour",
        governor_name="phase14_governor",
        symbol="BTCUSDT",
        exchange="BINANCE",
        timeframe=MarketDataTimeframe.M15,
        source=GovernorSource.POSITION_EXPANSION,
        freshness=GovernorFreshness(
            generated_at=current_time,
            expires_at=current_time + timedelta(minutes=10),
        ),
        validity=GovernorValidity(
            status=GovernorValidityStatus.VALID,
            observed_inputs=2,
            required_inputs=2,
        ),
        decision=GovernorDecision.APPROVE,
        status=GovernorStatus.APPROVED,
        direction=GovernorDirection.LONG,
        originating_expansion_id=uuid4(),
        confidence=Decimal("0.83"),
        priority_score=Decimal("0.63"),
        capital_fraction=Decimal("0.25"),
        reason_code=GovernorReasonCode.CONTEXT_READY,
    )


def _protection() -> ProtectionSupervisorCandidate:
    current_time = _now()
    return ProtectionSupervisorCandidate.candidate(
        contour_name="phase15_protection_contour",
        supervisor_name="phase15_protection",
        symbol="BTCUSDT",
        exchange="BINANCE",
        timeframe=MarketDataTimeframe.M15,
        source=ProtectionSource.PORTFOLIO_GOVERNOR,
        freshness=ProtectionFreshness(
            generated_at=current_time,
            expires_at=current_time + timedelta(minutes=10),
        ),
        validity=ProtectionValidity(
            status=ProtectionValidityStatus.VALID,
            observed_inputs=2,
            required_inputs=2,
        ),
        decision=ProtectionDecision.PROTECT,
        status=ProtectionStatus.PROTECTED,
        originating_governor_id=uuid4(),
        confidence=Decimal("0.84"),
        priority_score=Decimal("0.64"),
        reason_code=ProtectionReasonCode.CONTEXT_READY,
    )


def _oms_order() -> OmsOrderRecord:
    current_time = _now()
    return OmsOrderRecord.registered(
        contour_name="phase16_oms_contour",
        oms_name="phase16_oms",
        symbol="BTCUSDT",
        exchange="BINANCE",
        timeframe=MarketDataTimeframe.M15,
        freshness=OmsFreshness(
            generated_at=current_time,
            expires_at=current_time + timedelta(minutes=10),
        ),
        validity=OmsValidity(
            status=OmsValidityStatus.VALID,
            observed_inputs=3,
            required_inputs=3,
        ),
        originating_intent_id=uuid4(),
        client_order_id="OID-1",
        reason_code=OmsReasonCode.ORDER_REGISTERED,
    )


def _validation_candidate() -> ValidationReviewCandidate:
    current_time = _now()
    return ValidationReviewCandidate.candidate(
        contour_name="phase18_validation_contour",
        validation_name="phase18_validation",
        symbol="BTCUSDT",
        exchange="BINANCE",
        timeframe=MarketDataTimeframe.M15,
        source=ValidationSource.RUNTIME_FOUNDATIONS,
        freshness=ValidationFreshness(
            generated_at=current_time,
            expires_at=current_time + timedelta(minutes=10),
        ),
        validity=ValidationValidity(
            status=ValidationValidityStatus.VALID,
            observed_inputs=4,
            required_inputs=4,
        ),
        decision=ValidationDecision.VALIDATE,
        status=ValidationStatus.VALIDATED,
        originating_workflow_id=_manager().workflow_id,
        originating_governor_id=_governor().governor_id,
        originating_protection_id=_protection().protection_id,
        originating_oms_order_id=_oms_order().oms_order_id,
        confidence=Decimal("0.86"),
        review_score=Decimal("0.70"),
        reason_code=ValidationReasonCode.VALIDATION_CONFIRMED,
    )


def _paper_candidate() -> PaperRehearsalCandidate:
    current_time = _now()
    return PaperRehearsalCandidate.candidate(
        contour_name="phase19_paper_contour",
        paper_name="phase19_paper",
        symbol="BTCUSDT",
        exchange="BINANCE",
        timeframe=MarketDataTimeframe.M15,
        source=PaperSource.RUNTIME_FOUNDATIONS,
        freshness=PaperFreshness(
            generated_at=current_time,
            expires_at=current_time + timedelta(minutes=10),
        ),
        validity=PaperValidity(
            status=PaperValidityStatus.VALID,
            observed_inputs=3,
            required_inputs=3,
        ),
        decision=PaperDecision.REHEARSE,
        status=PaperStatus.REHEARSED,
        originating_workflow_id=_manager().workflow_id,
        originating_review_id=_validation_candidate().review_id,
        originating_oms_order_id=_oms_order().oms_order_id,
        confidence=Decimal("0.81"),
        rehearsal_score=Decimal("0.67"),
        reason_code=PaperReasonCode.PAPER_REHEARSED,
    )


def _replay_candidate() -> ReplayCandidate:
    current_time = _now()
    window = ReplayCoverageWindow(
        start_at=current_time - timedelta(minutes=15),
        end_at=current_time,
        observed_events=15,
        expected_events=15,
    )
    historical_input = HistoricalInputContract.candidate(
        input_name="btcusdt_m15_window",
        symbol="BTCUSDT",
        exchange="BINANCE",
        kind=HistoricalInputKind.BAR_STREAM,
        timeframe=MarketDataTimeframe.M15,
        coverage_window=window,
    )
    return ReplayCandidate.candidate(
        contour_name="phase20_replay_contour",
        replay_name="phase20_backtest",
        symbol="BTCUSDT",
        exchange="BINANCE",
        source=ReplaySource.HISTORICAL_INPUTS,
        freshness=ReplayFreshness(
            generated_at=current_time,
            expires_at=current_time + timedelta(minutes=10),
        ),
        coverage_window=window,
        validity=ReplayValidity(
            status=ReplayValidityStatus.VALID,
            observed_inputs=1,
            required_inputs=1,
        ),
        decision=ReplayDecision.REPLAY,
        status=ReplayStatus.REPLAYED,
        historical_input_id=historical_input.input_id,
        timeframe=historical_input.timeframe,
        reason_code=ReplayReasonCode.REPLAY_EXECUTED,
    )


def test_single_artifact_assembly_helpers_preserve_expected_kinds() -> None:
    assert (
        assemble_validation_report_artifact(_validation_candidate()).kind
        == ReportingArtifactKind.VALIDATION_REPORT
    )
    assert (
        assemble_paper_report_artifact(_paper_candidate()).kind
        == ReportingArtifactKind.PAPER_REPORT
    )
    assert (
        assemble_replay_report_artifact(_replay_candidate()).kind
        == ReportingArtifactKind.REPLAY_REPORT
    )


def test_bundle_assembly_is_deterministic_by_source_layer_order() -> None:
    replay_artifact = assemble_replay_report_artifact(_replay_candidate())
    validation_artifact = assemble_validation_report_artifact(_validation_candidate())
    paper_artifact = assemble_paper_report_artifact(_paper_candidate())

    bundle = assemble_reporting_artifact_bundle(
        reporting_name="phase21_reporting",
        artifacts=(replay_artifact, validation_artifact, paper_artifact),
    )

    assert [artifact.source_layer for artifact in bundle.artifacts] == [
        ReportingSourceLayer.VALIDATION,
        ReportingSourceLayer.PAPER,
        ReportingSourceLayer.REPLAY,
    ]


def test_bundle_can_be_assembled_directly_from_candidate_set() -> None:
    bundle = assemble_reporting_bundle_from_candidates(
        reporting_name="phase21_reporting",
        validation=_validation_candidate(),
        paper=_paper_candidate(),
        replay=_replay_candidate(),
    )

    assert bundle.reporting_name == "phase21_reporting"
    assert bundle.symbol == "BTCUSDT"
    assert bundle.exchange == "BINANCE"
    assert bundle.timeframe == MarketDataTimeframe.M15
    assert len(bundle.artifacts) == 3


def test_candidate_set_rejects_coordinate_drift_between_inputs() -> None:
    replay = _replay_candidate()
    shifted_validation = ValidationReviewCandidate.candidate(
        contour_name="phase18_validation_contour",
        validation_name="phase18_validation",
        symbol="ETHUSDT",
        exchange="BINANCE",
        timeframe=MarketDataTimeframe.M15,
        source=ValidationSource.RUNTIME_FOUNDATIONS,
        freshness=ValidationFreshness(
            generated_at=_now(),
            expires_at=_now() + timedelta(minutes=10),
        ),
        validity=ValidationValidity(
            status=ValidationValidityStatus.VALID,
            observed_inputs=4,
            required_inputs=4,
        ),
        decision=ValidationDecision.VALIDATE,
        status=ValidationStatus.VALIDATED,
        originating_workflow_id=_manager().workflow_id,
        originating_governor_id=_governor().governor_id,
        originating_protection_id=_protection().protection_id,
        originating_oms_order_id=_oms_order().oms_order_id,
        confidence=Decimal("0.86"),
        review_score=Decimal("0.70"),
        reason_code=ValidationReasonCode.VALIDATION_CONFIRMED,
    )

    with pytest.raises(ValueError, match="symbol должен совпадать"):
        assemble_reporting_bundle_from_candidates(
            reporting_name="phase21_reporting",
            validation=shifted_validation,
            replay=replay,
        )


def test_bundle_generation_time_tracks_latest_artifact_timestamp() -> None:
    validation_artifact = assemble_validation_report_artifact(_validation_candidate())
    paper_candidate = _paper_candidate()
    delayed_paper = PaperRehearsalCandidate.candidate(
        contour_name=paper_candidate.contour_name,
        paper_name=paper_candidate.paper_name,
        symbol=paper_candidate.symbol,
        exchange=paper_candidate.exchange,
        timeframe=paper_candidate.timeframe,
        source=paper_candidate.source,
        freshness=PaperFreshness(
            generated_at=_now() + timedelta(minutes=2),
            expires_at=_now() + timedelta(minutes=12),
        ),
        validity=paper_candidate.validity,
        decision=paper_candidate.decision,
        status=paper_candidate.status,
        originating_workflow_id=paper_candidate.originating_workflow_id,
        originating_review_id=paper_candidate.originating_review_id,
        originating_oms_order_id=paper_candidate.originating_oms_order_id,
        confidence=paper_candidate.confidence,
        rehearsal_score=paper_candidate.rehearsal_score,
        reason_code=paper_candidate.reason_code,
    )
    paper_artifact = assemble_paper_report_artifact(delayed_paper)

    bundle = assemble_reporting_artifact_bundle(
        reporting_name="phase21_reporting",
        artifacts=(validation_artifact, paper_artifact),
    )

    assert bundle.generated_at == paper_artifact.generated_at
    assert not hasattr(bundle, "start")

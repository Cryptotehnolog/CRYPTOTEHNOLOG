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
    PaperReportArtifact,
    ReplayReportArtifact,
    ReportingArtifactBundle,
    ReportingArtifactKind,
    ReportingArtifactProvenance,
    ReportingArtifactStatus,
    ReportingSourceLayer,
    ValidationReportArtifact,
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


def test_provenance_requires_derived_read_only_semantics() -> None:
    with pytest.raises(ValueError, match="derived/read-only semantics"):
        ReportingArtifactProvenance(
            source_layer=ReportingSourceLayer.VALIDATION,
            source_candidate_id=uuid4(),
            source_status="validated",
            source_reason_code="validation_confirmed",
            source_generated_at=_now(),
            source_expires_at=_now() + timedelta(minutes=10),
            derived_from_read_only_truth=False,
        )


def test_validation_report_artifact_preserves_source_reference() -> None:
    artifact = ValidationReportArtifact.from_candidate(_validation_candidate())

    assert artifact.kind == ReportingArtifactKind.VALIDATION_REPORT
    assert artifact.source_layer == ReportingSourceLayer.VALIDATION
    assert artifact.status == ReportingArtifactStatus.READY
    assert artifact.source_candidate_id == artifact.provenance.source_candidate_id
    assert artifact.summary == "validation:validated"
    assert not hasattr(artifact, "source_candidate")


def test_paper_report_artifact_is_derived_not_rehearsal_owner() -> None:
    artifact = PaperReportArtifact.from_candidate(_paper_candidate())

    assert artifact.kind == ReportingArtifactKind.PAPER_REPORT
    assert artifact.source_layer == ReportingSourceLayer.PAPER
    assert artifact.provenance.derived_from_read_only_truth is True
    assert artifact.summary == "paper:rehearsed"
    assert not hasattr(artifact, "rehearsal_runtime")


def test_replay_report_artifact_carries_replay_reference_without_ownership_takeover() -> None:
    artifact = ReplayReportArtifact.from_candidate(_replay_candidate())

    assert artifact.kind == ReportingArtifactKind.REPLAY_REPORT
    assert artifact.source_layer == ReportingSourceLayer.REPLAY
    assert artifact.provenance.source_status == ReplayStatus.REPLAYED.value
    assert artifact.summary == "replay:replayed"
    assert not hasattr(artifact, "historical_input")


def test_bundle_requires_non_empty_unique_source_layers() -> None:
    validation_artifact = ValidationReportArtifact.from_candidate(_validation_candidate())

    with pytest.raises(ValueError, match="хотя бы один artifact"):
        ReportingArtifactBundle(
            bundle_id=uuid4(),
            reporting_name="phase21_reporting",
            symbol="BTCUSDT",
            exchange="BINANCE",
            timeframe=MarketDataTimeframe.M15,
            generated_at=_now(),
            artifacts=(),
        )

    with pytest.raises(ValueError, match="несколько artifacts одного source layer"):
        ReportingArtifactBundle(
            bundle_id=uuid4(),
            reporting_name="phase21_reporting",
            symbol="BTCUSDT",
            exchange="BINANCE",
            timeframe=MarketDataTimeframe.M15,
            generated_at=_now(),
            artifacts=(validation_artifact, validation_artifact),
        )


def test_bundle_coordinates_must_match_artifacts() -> None:
    validation_artifact = ValidationReportArtifact.from_candidate(_validation_candidate())
    paper_artifact = PaperReportArtifact.from_candidate(_paper_candidate())
    replay_artifact = ReplayReportArtifact.from_candidate(_replay_candidate())

    bundle = ReportingArtifactBundle(
        bundle_id=uuid4(),
        reporting_name="phase21_reporting",
        symbol="BTCUSDT",
        exchange="BINANCE",
        timeframe=MarketDataTimeframe.M15,
        generated_at=_now(),
        artifacts=(validation_artifact, paper_artifact, replay_artifact),
    )

    assert len(bundle.artifacts) == 3
    assert {artifact.source_layer for artifact in bundle.artifacts} == {
        ReportingSourceLayer.VALIDATION,
        ReportingSourceLayer.PAPER,
        ReportingSourceLayer.REPLAY,
    }

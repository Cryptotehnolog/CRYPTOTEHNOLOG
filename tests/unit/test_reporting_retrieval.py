from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

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
    assemble_validation_report_artifact,
    build_reporting_artifact_catalog,
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


def test_catalog_can_lookup_artifacts_by_id_and_kind() -> None:
    validation_artifact = assemble_validation_report_artifact(_validation_candidate())
    paper_artifact = assemble_paper_report_artifact(_paper_candidate())

    catalog = build_reporting_artifact_catalog(
        artifacts=(paper_artifact, validation_artifact),
    )

    assert catalog.get_artifact(validation_artifact.artifact_id) == validation_artifact
    assert catalog.list_artifacts(kind=ReportingArtifactKind.VALIDATION_REPORT) == (
        validation_artifact,
    )


def test_catalog_can_find_artifacts_by_source_candidate_id() -> None:
    replay_candidate = _replay_candidate()
    replay_artifact = assemble_replay_report_artifact(replay_candidate)
    catalog = build_reporting_artifact_catalog(artifacts=(replay_artifact,))

    found = catalog.find_by_source_candidate_id(
        replay_candidate.replay_id,
        source_layer=ReportingSourceLayer.REPLAY,
    )

    assert found == (replay_artifact,)


def test_catalog_can_lookup_bundle_and_bundle_contents() -> None:
    validation_artifact = assemble_validation_report_artifact(_validation_candidate())
    paper_artifact = assemble_paper_report_artifact(_paper_candidate())
    bundle = assemble_reporting_artifact_bundle(
        reporting_name="phase21_reporting",
        artifacts=(validation_artifact, paper_artifact),
    )
    catalog = build_reporting_artifact_catalog(
        bundles=(bundle,),
    )

    assert catalog.get_bundle(bundle.bundle_id) == bundle
    assert catalog.get_bundle_artifacts(bundle.bundle_id) == bundle.artifacts


def test_catalog_keeps_read_only_semantics_without_service_drift() -> None:
    replay_artifact = assemble_replay_report_artifact(_replay_candidate())
    catalog = build_reporting_artifact_catalog(artifacts=(replay_artifact,))

    assert not hasattr(catalog, "start")
    assert not hasattr(catalog, "stop")
    assert not hasattr(catalog, "publish")
    assert catalog.get_bundle_artifacts(uuid4()) == ()


def test_catalog_rejects_conflicting_duplicate_artifact_ids() -> None:
    base_artifact = assemble_validation_report_artifact(_validation_candidate())
    conflicting_artifact = assemble_validation_report_artifact(_validation_candidate())
    conflicting_artifact = type(conflicting_artifact)(
        artifact_id=base_artifact.artifact_id,
        kind=conflicting_artifact.kind,
        source_layer=conflicting_artifact.source_layer,
        source_candidate_id=conflicting_artifact.source_candidate_id,
        generated_at=conflicting_artifact.generated_at,
        symbol=conflicting_artifact.symbol,
        exchange=conflicting_artifact.exchange,
        timeframe=conflicting_artifact.timeframe,
        status=conflicting_artifact.status,
        summary=conflicting_artifact.summary,
        provenance=conflicting_artifact.provenance,
        review_score=conflicting_artifact.review_score,
        confidence=conflicting_artifact.confidence,
        metadata={"conflict": True},
    )

    try:
        build_reporting_artifact_catalog(
            artifacts=(base_artifact, conflicting_artifact),
        )
    except ValueError as exc:
        assert "conflicting artifacts" in str(exc)
    else:
        raise AssertionError("Catalog должен отклонять conflicting duplicate artifact ids")

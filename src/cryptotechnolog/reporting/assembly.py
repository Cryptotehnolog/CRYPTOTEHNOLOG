"""
Deterministic assembly helpers для Phase 21 reporting artifact layer.

Этот модуль intentionally не является runtime/service boundary.
Он только собирает typed artifacts и bundles поверх existing upstream truths.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import uuid4

from cryptotechnolog.reporting.models import (
    PaperReportArtifact,
    ReplayReportArtifact,
    ReportArtifact,
    ReportingArtifactBundle,
    ReportingSourceLayer,
    ValidationReportArtifact,
)

if TYPE_CHECKING:
    from datetime import datetime

    from cryptotechnolog.backtest import ReplayCandidate
    from cryptotechnolog.market_data import MarketDataTimeframe
    from cryptotechnolog.paper import PaperRehearsalCandidate
    from cryptotechnolog.validation import ValidationReviewCandidate


_ARTIFACT_ORDER: dict[ReportingSourceLayer, int] = {
    ReportingSourceLayer.VALIDATION: 0,
    ReportingSourceLayer.PAPER: 1,
    ReportingSourceLayer.REPLAY: 2,
}


@dataclass(slots=True, frozen=True)
class ReportingCandidateSet:
    """Нормализованный read-only набор upstream candidates для assembly."""

    validation: ValidationReviewCandidate | None = None
    paper: PaperRehearsalCandidate | None = None
    replay: ReplayCandidate | None = None

    def __post_init__(self) -> None:
        if self.validation is None and self.paper is None and self.replay is None:
            raise ValueError("ReportingCandidateSet требует хотя бы один upstream candidate")
        self._validate_coordinates()

    def _validate_coordinates(self) -> None:
        candidates = tuple(
            candidate
            for candidate in (self.validation, self.paper, self.replay)
            if candidate is not None
        )
        if not candidates:
            return
        symbol = candidates[0].symbol
        exchange = candidates[0].exchange
        timeframe = candidates[0].timeframe
        for candidate in candidates[1:]:
            if candidate.symbol != symbol:
                raise ValueError("ReportingCandidateSet symbol должен совпадать у всех candidates")
            if candidate.exchange != exchange:
                raise ValueError(
                    "ReportingCandidateSet exchange должен совпадать у всех candidates"
                )
            if candidate.timeframe != timeframe:
                raise ValueError(
                    "ReportingCandidateSet timeframe должен совпадать у всех candidates"
                )

    @property
    def symbol(self) -> str:
        for candidate in (self.validation, self.paper, self.replay):
            if candidate is not None:
                return candidate.symbol
        raise RuntimeError("ReportingCandidateSet пуст")

    @property
    def exchange(self) -> str:
        for candidate in (self.validation, self.paper, self.replay):
            if candidate is not None:
                return candidate.exchange
        raise RuntimeError("ReportingCandidateSet пуст")

    @property
    def timeframe(self) -> MarketDataTimeframe | None:
        for candidate in (self.validation, self.paper, self.replay):
            if candidate is not None:
                return candidate.timeframe
        raise RuntimeError("ReportingCandidateSet пуст")


def assemble_validation_report_artifact(
    candidate: ValidationReviewCandidate,
    *,
    metadata: dict[str, object] | None = None,
) -> ValidationReportArtifact:
    """Собрать validation report artifact из narrow validation truth."""
    return ValidationReportArtifact.from_candidate(candidate, metadata=metadata)


def assemble_paper_report_artifact(
    candidate: PaperRehearsalCandidate,
    *,
    metadata: dict[str, object] | None = None,
) -> PaperReportArtifact:
    """Собрать paper report artifact из narrow rehearsal truth."""
    return PaperReportArtifact.from_candidate(candidate, metadata=metadata)


def assemble_replay_report_artifact(
    candidate: ReplayCandidate,
    *,
    metadata: dict[str, object] | None = None,
) -> ReplayReportArtifact:
    """Собрать replay report artifact из narrow replay truth."""
    return ReplayReportArtifact.from_candidate(candidate, metadata=metadata)


def _sorted_artifacts(artifacts: tuple[ReportArtifact, ...]) -> tuple[ReportArtifact, ...]:
    return tuple(
        sorted(
            artifacts,
            key=lambda artifact: (
                _ARTIFACT_ORDER[artifact.source_layer],
                artifact.generated_at,
                str(artifact.source_candidate_id),
            ),
        )
    )


def _resolve_bundle_generated_at(artifacts: tuple[ReportArtifact, ...]) -> datetime:
    return max(artifact.generated_at for artifact in artifacts)


def assemble_reporting_artifact_bundle(
    *,
    reporting_name: str,
    artifacts: tuple[ReportArtifact, ...],
    metadata: dict[str, object] | None = None,
) -> ReportingArtifactBundle:
    """
    Собрать deterministic reporting bundle из уже готовых artifacts.

    Bundle остаётся derived/read-only collection и не вводит runtime semantics.
    """

    ordered_artifacts = _sorted_artifacts(artifacts)
    first_artifact = ordered_artifacts[0]
    return ReportingArtifactBundle(
        bundle_id=uuid4(),
        reporting_name=reporting_name,
        symbol=first_artifact.symbol,
        exchange=first_artifact.exchange,
        timeframe=first_artifact.timeframe,
        generated_at=_resolve_bundle_generated_at(ordered_artifacts),
        artifacts=ordered_artifacts,
        metadata={} if metadata is None else metadata.copy(),
    )


def assemble_reporting_bundle_from_candidates(
    *,
    reporting_name: str,
    validation: ValidationReviewCandidate | None = None,
    paper: PaperRehearsalCandidate | None = None,
    replay: ReplayCandidate | None = None,
    metadata: dict[str, object] | None = None,
) -> ReportingArtifactBundle:
    """
    Собрать deterministic reporting bundle прямо из upstream candidates.

    Этот helper не хранит state и не оркестрирует lifecycle;
    он только нормализует construction path для artifact-first reporting line.
    """

    candidate_set = ReportingCandidateSet(
        validation=validation,
        paper=paper,
        replay=replay,
    )
    artifacts: list[ReportArtifact] = []
    if candidate_set.validation is not None:
        artifacts.append(assemble_validation_report_artifact(candidate_set.validation))
    if candidate_set.paper is not None:
        artifacts.append(assemble_paper_report_artifact(candidate_set.paper))
    if candidate_set.replay is not None:
        artifacts.append(assemble_replay_report_artifact(candidate_set.replay))
    return assemble_reporting_artifact_bundle(
        reporting_name=reporting_name,
        artifacts=tuple(artifacts),
        metadata=metadata,
    )

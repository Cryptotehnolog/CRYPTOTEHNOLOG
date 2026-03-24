"""
Contract-first модели Phase 21 для narrow reporting artifact layer.

Этот модуль фиксирует минимальный opening scope:
- typed provenance/reference contract;
- typed report artifact kind/status semantics;
- typed reporting artifacts поверх existing truths;
- bundle truth и derived/read-only semantics.

Reporting layer intentionally не включает:
- analytics runtime/platform semantics;
- dashboard / operator semantics;
- comparison / ranking ownership;
- re-ownership Validation / Paper / Replay / Execution / OMS / Manager.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from cryptotechnolog.backtest import ReplayCandidate, ReplayValidityStatus
from cryptotechnolog.paper import PaperRehearsalCandidate, PaperValidityStatus
from cryptotechnolog.validation import ValidationReviewCandidate, ValidationValidityStatus

if TYPE_CHECKING:
    from datetime import datetime
    from decimal import Decimal

    from cryptotechnolog.market_data import MarketDataTimeframe


class ReportingSourceLayer(StrEnum):
    """Нормализованный upstream source layer reporting artifacts."""

    VALIDATION = "validation"
    PAPER = "paper"
    REPLAY = "replay"


class ReportingArtifactKind(StrEnum):
    """Typed kind semantics для reporting artifact layer."""

    VALIDATION_REPORT = "validation_report"
    PAPER_REPORT = "paper_report"
    REPLAY_REPORT = "replay_report"


class ReportingArtifactStatus(StrEnum):
    """Узкий derived status для report artifacts."""

    READY = "ready"
    WARMING = "warming"
    INVALID = "invalid"


@dataclass(slots=True, frozen=True)
class ReportingArtifactProvenance:
    """
    Typed provenance/reference contract для reporting artifacts.

    Provenance фиксирует derived/read-only semantics и не даёт artifact layer
    подменять собой source-of-truth.
    """

    source_layer: ReportingSourceLayer
    source_candidate_id: UUID
    source_status: str
    source_reason_code: str | None
    source_generated_at: datetime
    source_expires_at: datetime | None
    derived_from_read_only_truth: bool = True
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.derived_from_read_only_truth:
            raise ValueError("ReportingArtifactProvenance требует derived/read-only semantics")
        if self.source_expires_at is not None and self.source_expires_at < self.source_generated_at:
            raise ValueError("source_expires_at не может быть раньше source_generated_at")


def _artifact_status_from_validation(
    candidate: ValidationReviewCandidate,
) -> ReportingArtifactStatus:
    if candidate.validity.status == ValidationValidityStatus.VALID:
        return ReportingArtifactStatus.READY
    if candidate.validity.status == ValidationValidityStatus.WARMING:
        return ReportingArtifactStatus.WARMING
    return ReportingArtifactStatus.INVALID


def _artifact_status_from_paper(candidate: PaperRehearsalCandidate) -> ReportingArtifactStatus:
    if candidate.validity.status == PaperValidityStatus.VALID:
        return ReportingArtifactStatus.READY
    if candidate.validity.status == PaperValidityStatus.WARMING:
        return ReportingArtifactStatus.WARMING
    return ReportingArtifactStatus.INVALID


def _artifact_status_from_replay(candidate: ReplayCandidate) -> ReportingArtifactStatus:
    if candidate.validity.status == ReplayValidityStatus.VALID:
        return ReportingArtifactStatus.READY
    if candidate.validity.status == ReplayValidityStatus.WARMING:
        return ReportingArtifactStatus.WARMING
    return ReportingArtifactStatus.INVALID


@dataclass(slots=True, frozen=True)
class ValidationReportArtifact:
    """Derived report artifact поверх narrow validation truth."""

    artifact_id: UUID
    kind: ReportingArtifactKind
    source_layer: ReportingSourceLayer
    source_candidate_id: UUID
    generated_at: datetime
    symbol: str
    exchange: str
    timeframe: MarketDataTimeframe
    status: ReportingArtifactStatus
    summary: str
    provenance: ReportingArtifactProvenance
    review_score: Decimal | None = None
    confidence: Decimal | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.kind != ReportingArtifactKind.VALIDATION_REPORT:
            raise ValueError("ValidationReportArtifact kind должен быть VALIDATION_REPORT")
        if self.source_layer != ReportingSourceLayer.VALIDATION:
            raise ValueError("ValidationReportArtifact source_layer должен быть VALIDATION")
        if self.source_candidate_id != self.provenance.source_candidate_id:
            raise ValueError(
                "ValidationReportArtifact provenance должен ссылаться на source candidate"
            )

    @classmethod
    def from_candidate(
        cls,
        candidate: ValidationReviewCandidate,
        *,
        metadata: dict[str, object] | None = None,
    ) -> ValidationReportArtifact:
        return cls(
            artifact_id=uuid4(),
            kind=ReportingArtifactKind.VALIDATION_REPORT,
            source_layer=ReportingSourceLayer.VALIDATION,
            source_candidate_id=candidate.review_id,
            generated_at=candidate.freshness.generated_at,
            symbol=candidate.symbol,
            exchange=candidate.exchange,
            timeframe=candidate.timeframe,
            status=_artifact_status_from_validation(candidate),
            summary=f"validation:{candidate.status.value}",
            provenance=ReportingArtifactProvenance(
                source_layer=ReportingSourceLayer.VALIDATION,
                source_candidate_id=candidate.review_id,
                source_status=candidate.status.value,
                source_reason_code=(
                    candidate.reason_code.value if candidate.reason_code is not None else None
                ),
                source_generated_at=candidate.freshness.generated_at,
                source_expires_at=candidate.freshness.expires_at,
            ),
            review_score=candidate.review_score,
            confidence=candidate.confidence,
            metadata={} if metadata is None else metadata.copy(),
        )


@dataclass(slots=True, frozen=True)
class PaperReportArtifact:
    """Derived report artifact поверх narrow paper rehearsal truth."""

    artifact_id: UUID
    kind: ReportingArtifactKind
    source_layer: ReportingSourceLayer
    source_candidate_id: UUID
    generated_at: datetime
    symbol: str
    exchange: str
    timeframe: MarketDataTimeframe
    status: ReportingArtifactStatus
    summary: str
    provenance: ReportingArtifactProvenance
    rehearsal_score: Decimal | None = None
    confidence: Decimal | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.kind != ReportingArtifactKind.PAPER_REPORT:
            raise ValueError("PaperReportArtifact kind должен быть PAPER_REPORT")
        if self.source_layer != ReportingSourceLayer.PAPER:
            raise ValueError("PaperReportArtifact source_layer должен быть PAPER")
        if self.source_candidate_id != self.provenance.source_candidate_id:
            raise ValueError("PaperReportArtifact provenance должен ссылаться на source candidate")

    @classmethod
    def from_candidate(
        cls,
        candidate: PaperRehearsalCandidate,
        *,
        metadata: dict[str, object] | None = None,
    ) -> PaperReportArtifact:
        return cls(
            artifact_id=uuid4(),
            kind=ReportingArtifactKind.PAPER_REPORT,
            source_layer=ReportingSourceLayer.PAPER,
            source_candidate_id=candidate.rehearsal_id,
            generated_at=candidate.freshness.generated_at,
            symbol=candidate.symbol,
            exchange=candidate.exchange,
            timeframe=candidate.timeframe,
            status=_artifact_status_from_paper(candidate),
            summary=f"paper:{candidate.status.value}",
            provenance=ReportingArtifactProvenance(
                source_layer=ReportingSourceLayer.PAPER,
                source_candidate_id=candidate.rehearsal_id,
                source_status=candidate.status.value,
                source_reason_code=(
                    candidate.reason_code.value if candidate.reason_code is not None else None
                ),
                source_generated_at=candidate.freshness.generated_at,
                source_expires_at=candidate.freshness.expires_at,
            ),
            rehearsal_score=candidate.rehearsal_score,
            confidence=candidate.confidence,
            metadata={} if metadata is None else metadata.copy(),
        )


@dataclass(slots=True, frozen=True)
class ReplayReportArtifact:
    """Derived report artifact поверх narrow replay truth."""

    artifact_id: UUID
    kind: ReportingArtifactKind
    source_layer: ReportingSourceLayer
    source_candidate_id: UUID
    generated_at: datetime
    symbol: str
    exchange: str
    timeframe: MarketDataTimeframe | None
    status: ReportingArtifactStatus
    summary: str
    provenance: ReportingArtifactProvenance
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.kind != ReportingArtifactKind.REPLAY_REPORT:
            raise ValueError("ReplayReportArtifact kind должен быть REPLAY_REPORT")
        if self.source_layer != ReportingSourceLayer.REPLAY:
            raise ValueError("ReplayReportArtifact source_layer должен быть REPLAY")
        if self.source_candidate_id != self.provenance.source_candidate_id:
            raise ValueError("ReplayReportArtifact provenance должен ссылаться на source candidate")

    @classmethod
    def from_candidate(
        cls,
        candidate: ReplayCandidate,
        *,
        metadata: dict[str, object] | None = None,
    ) -> ReplayReportArtifact:
        return cls(
            artifact_id=uuid4(),
            kind=ReportingArtifactKind.REPLAY_REPORT,
            source_layer=ReportingSourceLayer.REPLAY,
            source_candidate_id=candidate.replay_id,
            generated_at=candidate.freshness.generated_at,
            symbol=candidate.symbol,
            exchange=candidate.exchange,
            timeframe=candidate.timeframe,
            status=_artifact_status_from_replay(candidate),
            summary=f"replay:{candidate.status.value}",
            provenance=ReportingArtifactProvenance(
                source_layer=ReportingSourceLayer.REPLAY,
                source_candidate_id=candidate.replay_id,
                source_status=candidate.status.value,
                source_reason_code=(
                    candidate.reason_code.value if candidate.reason_code is not None else None
                ),
                source_generated_at=candidate.freshness.generated_at,
                source_expires_at=candidate.freshness.expires_at,
            ),
            metadata={} if metadata is None else metadata.copy(),
        )


ReportArtifact = ValidationReportArtifact | PaperReportArtifact | ReplayReportArtifact


@dataclass(slots=True, frozen=True)
class ReportingArtifactBundle:
    """Typed bundle contract для narrow reporting artifact layer."""

    bundle_id: UUID
    reporting_name: str
    symbol: str
    exchange: str
    timeframe: MarketDataTimeframe | None
    generated_at: datetime
    artifacts: tuple[ReportArtifact, ...]
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.artifacts:
            raise ValueError("ReportingArtifactBundle требует хотя бы один artifact")
        self._validate_coordinates()
        self._validate_unique_layers()

    def _validate_coordinates(self) -> None:
        for artifact in self.artifacts:
            if artifact.symbol != self.symbol:
                raise ValueError(
                    "ReportingArtifactBundle symbol должен совпадать с artifact symbol"
                )
            if artifact.exchange != self.exchange:
                raise ValueError(
                    "ReportingArtifactBundle exchange должен совпадать с artifact exchange"
                )
            if (
                self.timeframe is not None
                and artifact.timeframe is not None
                and artifact.timeframe != self.timeframe
            ):
                raise ValueError(
                    "ReportingArtifactBundle timeframe должен совпадать с artifact timeframe"
                )

    def _validate_unique_layers(self) -> None:
        layers = [artifact.source_layer for artifact in self.artifacts]
        if len(layers) != len(set(layers)):
            raise ValueError(
                "ReportingArtifactBundle не должен содержать несколько artifacts одного source layer"
            )

"""
Admissibility policy foundation для Phase 6.

Модуль не содержит scheduler/runtime loop UniverseEngine.
Он детерминированно преобразует raw universe + metrics + quality state
в admissible snapshot и quality assessment.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from .models import (
    AdmissibleSymbolContract,
    AdmissibleUniverseSnapshot,
    DataQualityIssueType,
    DataQualitySignal,
    ExcludedUniverseSymbol,
    RawUniverseSnapshot,
    SymbolMetricsContract,
    UniverseAdmissionReason,
    UniverseConfidenceState,
    UniverseExclusionReason,
    UniverseQualityAssessment,
    build_symbol_identity,
)

if TYPE_CHECKING:
    from cryptotechnolog.config.settings import Settings

    from .models import SymbolIdentity


@dataclass(slots=True, frozen=True)
class UniversePolicyConfig:
    """Консервативные thresholds admissibility policy."""

    max_spread_bps: Decimal = Decimal("25")
    min_top_of_book_depth_usd: Decimal = Decimal("75000")
    min_depth_5bps_usd: Decimal = Decimal("200000")
    max_latency_ms: Decimal = Decimal("250")
    min_coverage_ratio: Decimal = Decimal("0.90")
    max_data_freshness_ms: int = 3000
    min_quality_score: Decimal = Decimal("0.60")
    min_admissible_count_ready: int = 5
    min_admissible_ratio_degraded: Decimal = Decimal("0.10")
    min_confidence_ready: Decimal = Decimal("0.70")
    min_confidence_degraded: Decimal = Decimal("0.45")

    @classmethod
    def from_settings(cls, settings: Settings) -> UniversePolicyConfig:
        """Собрать admissibility policy из project settings."""
        return cls(
            max_spread_bps=Decimal(str(settings.universe_max_spread_bps)),
            min_top_of_book_depth_usd=Decimal(str(settings.universe_min_top_depth_usd)),
            min_depth_5bps_usd=Decimal(str(settings.universe_min_depth_5bps_usd)),
            max_latency_ms=Decimal(str(settings.universe_max_latency_ms)),
            min_coverage_ratio=Decimal(str(settings.universe_min_coverage_ratio)),
            max_data_freshness_ms=settings.universe_max_data_age_ms,
            min_quality_score=Decimal(str(settings.universe_min_quality_score)),
            min_admissible_count_ready=settings.universe_min_ready_instruments,
            min_admissible_ratio_degraded=Decimal(
                str(settings.universe_min_degraded_instruments_ratio)
            ),
            min_confidence_ready=Decimal(str(settings.universe_min_ready_confidence)),
            min_confidence_degraded=Decimal(str(settings.universe_min_degraded_confidence)),
        )


@dataclass(slots=True, frozen=True)
class UniversePolicyResult:
    """Результат применения admissibility policy."""

    snapshot: AdmissibleUniverseSnapshot
    assessment: UniverseQualityAssessment
    exclusion_reasons: dict[SymbolIdentity, tuple[UniverseExclusionReason, ...]]


class UniversePolicy:
    """Детерминированный policy-layer для admissible universe."""

    def __init__(self, config: UniversePolicyConfig | None = None) -> None:
        self._config = config or UniversePolicyConfig()

    @property
    def config(self) -> UniversePolicyConfig:
        """Доступ к policy config."""
        return self._config

    def build_admissible_universe(
        self,
        *,
        raw_snapshot: RawUniverseSnapshot,
        metrics_by_identity: dict[SymbolIdentity, SymbolMetricsContract],
        quality_signals_by_identity: dict[SymbolIdentity, tuple[DataQualitySignal, ...]]
        | None = None,
        measured_at: datetime | None = None,
    ) -> UniversePolicyResult:
        """Преобразовать raw universe в admissible snapshot и quality assessment."""
        observed_at = (measured_at or raw_snapshot.created_at).astimezone(UTC)
        quality_signals_by_identity = quality_signals_by_identity or {}

        admitted: list[AdmissibleSymbolContract] = []
        excluded_symbols: list[ExcludedUniverseSymbol] = []
        exclusion_map: dict[SymbolIdentity, tuple[UniverseExclusionReason, ...]] = {}

        for symbol_contract in raw_snapshot.symbols:
            identity = build_symbol_identity(symbol_contract.symbol, symbol_contract.exchange)
            reasons: list[UniverseExclusionReason] = []
            metrics = metrics_by_identity.get(identity)
            if metrics is None:
                reasons.append(UniverseExclusionReason.METRICS_UNAVAILABLE)
            else:
                reasons.extend(self._evaluate_metrics(metrics))
                reasons.extend(
                    self._evaluate_quality_signals(quality_signals_by_identity.get(identity, ()))
                )

            if reasons:
                excluded_symbols.append(
                    ExcludedUniverseSymbol(
                        symbol=symbol_contract.symbol,
                        exchange=symbol_contract.exchange,
                    )
                )
                exclusion_map[identity] = tuple(dict.fromkeys(reasons))
                continue

            assert metrics is not None
            admitted.append(
                AdmissibleSymbolContract(
                    symbol=symbol_contract,
                    metrics=metrics,
                    admitted_at=observed_at,
                    admission_reasons=(
                        UniverseAdmissionReason.LIQUIDITY_OK,
                        UniverseAdmissionReason.DEPTH_OK,
                        UniverseAdmissionReason.QUALITY_OK,
                        UniverseAdmissionReason.COVERAGE_OK,
                    ),
                )
            )

        confidence = self._calculate_confidence(admitted, raw_count=len(raw_snapshot.symbols))
        snapshot = AdmissibleUniverseSnapshot(
            version=raw_snapshot.version,
            created_at=observed_at,
            symbols=tuple(admitted),
            confidence=confidence,
            excluded_symbols=tuple(excluded_symbols),
        )
        assessment = self._build_assessment(
            raw_snapshot=raw_snapshot,
            snapshot=snapshot,
            confidence=confidence,
            measured_at=observed_at,
        )
        return UniversePolicyResult(
            snapshot=snapshot,
            assessment=assessment,
            exclusion_reasons=exclusion_map,
        )

    def _evaluate_metrics(self, metrics: SymbolMetricsContract) -> list[UniverseExclusionReason]:
        reasons: list[UniverseExclusionReason] = []
        if metrics.spread_bps > self._config.max_spread_bps:
            reasons.append(UniverseExclusionReason.SPREAD_TOO_WIDE)
        if metrics.top_of_book_depth_usd < self._config.min_top_of_book_depth_usd:
            reasons.append(UniverseExclusionReason.DEPTH_TOO_SHALLOW)
        if metrics.depth_5bps_usd < self._config.min_depth_5bps_usd:
            reasons.append(UniverseExclusionReason.DEPTH_TOO_SHALLOW)
        if metrics.latency_ms > self._config.max_latency_ms:
            reasons.append(UniverseExclusionReason.LOW_CONFIDENCE)
        if metrics.coverage_ratio < self._config.min_coverage_ratio:
            reasons.append(UniverseExclusionReason.LOW_CONFIDENCE)
        if metrics.data_freshness_ms > self._config.max_data_freshness_ms:
            reasons.append(UniverseExclusionReason.DATA_STALE)
        if metrics.quality_score < self._config.min_quality_score:
            reasons.append(UniverseExclusionReason.LOW_CONFIDENCE)
        return reasons

    def _evaluate_quality_signals(
        self,
        signals: tuple[DataQualitySignal, ...],
    ) -> list[UniverseExclusionReason]:
        reasons: list[UniverseExclusionReason] = []
        for signal in signals:
            match signal.issue_type:
                case DataQualityIssueType.GAP:
                    reasons.append(UniverseExclusionReason.DATA_GAP)
                case DataQualityIssueType.STALE:
                    reasons.append(UniverseExclusionReason.DATA_STALE)
                case DataQualityIssueType.OUTLIER:
                    reasons.append(UniverseExclusionReason.OUTLIER_DETECTED)
                case DataQualityIssueType.SOURCE_DEGRADED:
                    reasons.append(UniverseExclusionReason.LOW_CONFIDENCE)
                case _:
                    continue
        return reasons

    def _calculate_confidence(
        self,
        admitted: list[AdmissibleSymbolContract],
        *,
        raw_count: int,
    ) -> Decimal:
        if raw_count <= 0 or not admitted:
            return Decimal("0")

        admissible_ratio = Decimal(len(admitted)) / Decimal(raw_count)
        mean_quality = sum(item.metrics.quality_score for item in admitted) / Decimal(len(admitted))
        return min(admissible_ratio, mean_quality).quantize(Decimal("0.0001"))

    def _build_assessment(
        self,
        *,
        raw_snapshot: RawUniverseSnapshot,
        snapshot: AdmissibleUniverseSnapshot,
        confidence: Decimal,
        measured_at: datetime,
    ) -> UniverseQualityAssessment:
        raw_count = len(raw_snapshot.symbols)
        admissible_count = len(snapshot.symbols)
        admissible_ratio = (
            Decimal(admissible_count) / Decimal(raw_count) if raw_count > 0 else Decimal("0")
        )

        blocking_reasons: list[str] = []
        if admissible_count == 0:
            blocking_reasons.append("universe_empty")
            state = UniverseConfidenceState.BLOCKED
        elif (
            admissible_count < self._config.min_admissible_count_ready
            or confidence < self._config.min_confidence_ready
        ):
            if (
                admissible_ratio < self._config.min_admissible_ratio_degraded
                or confidence < self._config.min_confidence_degraded
            ):
                state = UniverseConfidenceState.BLOCKED
            else:
                state = UniverseConfidenceState.DEGRADED
        else:
            state = UniverseConfidenceState.READY

        if confidence < self._config.min_confidence_ready:
            blocking_reasons.append("confidence_below_ready_threshold")
        if admissible_count < self._config.min_admissible_count_ready:
            blocking_reasons.append("admissible_count_below_ready_threshold")
        if admissible_ratio < self._config.min_admissible_ratio_degraded:
            blocking_reasons.append("admissible_ratio_below_degraded_threshold")

        worst_symbols = tuple(
            item.symbol.symbol
            for item in sorted(
                snapshot.symbols, key=lambda admitted: admitted.metrics.quality_score
            )[:3]
        )
        return UniverseQualityAssessment(
            version=raw_snapshot.version,
            measured_at=measured_at,
            confidence=confidence,
            state=state,
            raw_count=raw_count,
            admissible_count=admissible_count,
            ranked_count=0,
            blocking_reasons=tuple(dict.fromkeys(blocking_reasons)),
            worst_symbols=worst_symbols,
        )

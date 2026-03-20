"""
Contract-first модели Phase 7 для indicators и intelligence слоя.

Этот модуль фиксирует минимальный, но production-compatible foundation:
- typed indicator snapshot contracts;
- validity / warming semantics;
- transport-neutral intelligence assessment contracts;
- DERYA contract shape и deterministic regime semantics basis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datetime import datetime

    from cryptotechnolog.market_data import MarketDataTimeframe


class IndicatorValueStatus(StrEnum):
    """Состояние доступности indicator value для consumers."""

    VALID = "valid"
    WARMING = "warming"
    INVALID = "invalid"


class IntelligenceAssessmentKind(StrEnum):
    """Тип assessment внутри intelligence layer."""

    GENERIC = "generic"
    DERYA = "derya"


class DeryaRegime(StrEnum):
    """Четыре базовых режима DERYA в рамках P_7."""

    EXPANSION = "EXPANSION"
    EXHAUSTION = "EXHAUSTION"
    COLLAPSE = "COLLAPSE"
    RECOVERY = "RECOVERY"


class DeryaResolutionState(StrEnum):
    """Явная интерпретация результата stateful DERYA update."""

    NOT_READY = "not_ready"
    STABLE = "stable"
    CARRIED_FORWARD = "carried_forward"
    TRANSITIONED = "transitioned"


@dataclass(slots=True, frozen=True)
class IndicatorValidity:
    """
    Typed semantics валидности indicator value.

    `VALID`:
    - окно данных накоплено;
    - значение можно использовать как analysis truth.

    `WARMING`:
    - значение ещё формируется;
    - потребитель обязан понимать, сколько баров не хватает.

    `INVALID`:
    - значение не может считаться корректным из-за bad input или
      domain-level ограничения.
    """

    status: IndicatorValueStatus
    observed_bars: int
    required_bars: int
    invalid_reason: str | None = None

    @property
    def is_valid(self) -> bool:
        """Проверить, готово ли значение к production-использованию."""
        return self.status == IndicatorValueStatus.VALID

    @property
    def is_warming(self) -> bool:
        """Проверить, находится ли значение в warming-state."""
        return self.status == IndicatorValueStatus.WARMING

    @property
    def warming_bars_remaining(self) -> int:
        """Вернуть, сколько баров не хватает до полной валидности."""
        return max(self.required_bars - self.observed_bars, 0)


@dataclass(slots=True, frozen=True)
class IndicatorSnapshot:
    """
    Transport-neutral snapshot значения одного индикатора.

    Контракт intentionally не вшивает strategy/signal semantics.
    """

    symbol: str
    exchange: str
    timeframe: MarketDataTimeframe
    indicator_name: str
    value: Decimal | None
    updated_at: datetime
    validity: IndicatorValidity
    parameters: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class IntelligenceAssessment:
    """
    Базовый intelligence assessment contract.

    Нужен как transport-neutral foundation между indicator layer
    и будущими consumers analysis truth.
    """

    assessment_kind: IntelligenceAssessmentKind
    symbol: str
    exchange: str
    timeframe: MarketDataTimeframe
    updated_at: datetime
    validity: IndicatorValidity
    confidence: Decimal | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class DeryaObservation:
    """
    Нормализованное наблюдение для deterministic DERYA classification.

    Это ещё не полноценный engine state, а минимальный contract,
    достаточный для фиксирования будущей regime machine.
    """

    raw_efficiency: Decimal
    smoothed_efficiency: Decimal
    efficiency_slope: Decimal
    observed_bars: int


@dataclass(slots=True, frozen=True)
class DeryaClassificationBasis:
    """
    Жёсткая basis для deterministic DERYA regime classification.

    Правила следующего шага должны интерпретироваться так:

    1. Если `smoothed_efficiency >= high_efficiency_threshold`:
       - `efficiency_slope > slope_flat_threshold`  -> `EXPANSION`
       - иначе                                      -> `EXHAUSTION`

    2. Если `smoothed_efficiency <= low_efficiency_threshold`:
       - `efficiency_slope < -slope_flat_threshold` -> `COLLAPSE`
       - иначе                                      -> `RECOVERY`

    3. Если значение находится между high/low thresholds:
       - новый режим не рождается;
       - engine обязан либо удерживать предыдущий режим по hysteresis/persistence,
         либо оставлять assessment в non-ready state.

    4. Transition допускается только после `min_persistence_bars`,
       если hysteresis уже не удерживает предыдущий режим.
    """

    high_efficiency_threshold: Decimal = Decimal("0.68")
    low_efficiency_threshold: Decimal = Decimal("0.32")
    slope_flat_threshold: Decimal = Decimal("0.015")
    hysteresis_band: Decimal = Decimal("0.04")
    min_persistence_bars: int = 3


DEFAULT_DERYA_CLASSIFICATION_BASIS = DeryaClassificationBasis()


@dataclass(slots=True, frozen=True)
class DeryaAssessment(IntelligenceAssessment):
    """
    Typed contract DERYA как bar-efficiency intelligence factor.

    Честная инженерная truth для P_7:
    - DERYA основан на OHLCV bar-efficiency proxy;
    - это не tick-level microstructure engine;
    - regime semantics определяются детерминированно через thresholds,
      slope, hysteresis и persistence policy.
    """

    raw_efficiency: Decimal | None = None
    smoothed_efficiency: Decimal | None = None
    efficiency_slope: Decimal | None = None
    current_regime: DeryaRegime | None = None
    previous_regime: DeryaRegime | None = None
    resolution_state: DeryaResolutionState = DeryaResolutionState.NOT_READY
    regime_duration_bars: int = 0
    regime_persistence_ratio: Decimal = Decimal("0")
    classification_basis: DeryaClassificationBasis = field(
        default_factory=lambda: DEFAULT_DERYA_CLASSIFICATION_BASIS
    )
    assessment_kind: IntelligenceAssessmentKind = field(
        init=False,
        default=IntelligenceAssessmentKind.DERYA,
    )


def classify_derya_regime_candidate(
    observation: DeryaObservation,
    basis: DeryaClassificationBasis = DEFAULT_DERYA_CLASSIFICATION_BASIS,
) -> DeryaRegime | None:
    """
    Определить candidate regime без учёта persistence carry-forward.

    Функция нужна для contract lock:
    она фиксирует саму classification basis, но ещё не является
    полноценным stateful engine.
    """

    smoothed = observation.smoothed_efficiency
    slope = observation.efficiency_slope

    if smoothed >= basis.high_efficiency_threshold:
        if slope > basis.slope_flat_threshold:
            return DeryaRegime.EXPANSION
        return DeryaRegime.EXHAUSTION

    if smoothed <= basis.low_efficiency_threshold:
        if slope < -basis.slope_flat_threshold:
            return DeryaRegime.COLLAPSE
        return DeryaRegime.RECOVERY

    return None


def resolve_derya_regime(
    *,
    observation: DeryaObservation,
    previous_regime: DeryaRegime | None,
    previous_regime_duration_bars: int,
    basis: DeryaClassificationBasis = DEFAULT_DERYA_CLASSIFICATION_BASIS,
) -> DeryaRegime | None:
    """
    Разрешить итоговый regime с учётом hysteresis и persistence policy.

    Нормализация для следующего шага:
    - neutral zone между thresholds не создаёт новый режим;
    - при недостаточной persistence удерживается previous regime;
    - hysteresis удерживает previous regime, пока значение не вышло
      за его защитную границу.
    """

    candidate = classify_derya_regime_candidate(observation, basis)
    if candidate is None:
        return previous_regime

    if previous_regime is None or candidate == previous_regime:
        return candidate

    if previous_regime_duration_bars < basis.min_persistence_bars:
        return previous_regime

    smoothed = observation.smoothed_efficiency
    if previous_regime in {DeryaRegime.EXPANSION, DeryaRegime.EXHAUSTION} and smoothed >= (
        basis.high_efficiency_threshold - basis.hysteresis_band
    ):
        return previous_regime
    if previous_regime in {DeryaRegime.COLLAPSE, DeryaRegime.RECOVERY} and smoothed <= (
        basis.low_efficiency_threshold + basis.hysteresis_band
    ):
        return previous_regime

    return candidate


def calculate_derya_confidence(
    *,
    regime: DeryaRegime | None,
    observation: DeryaObservation,
    basis: DeryaClassificationBasis = DEFAULT_DERYA_CLASSIFICATION_BASIS,
) -> Decimal | None:
    """
    Рассчитать простую и объяснимую confidence-оценку DERYA.

    Логика намеренно простая:
    - для high-regimes confidence растёт по мере удаления smoothed efficiency
      выше high threshold;
    - для low-regimes confidence растёт по мере удаления ниже low threshold;
    - шкала нормируется через hysteresis band;
    - внутри neutral zone confidence отсутствует.
    """

    if regime is None or basis.hysteresis_band <= 0:
        return None

    if regime in {DeryaRegime.EXPANSION, DeryaRegime.EXHAUSTION}:
        margin = observation.smoothed_efficiency - basis.high_efficiency_threshold
    else:
        margin = basis.low_efficiency_threshold - observation.smoothed_efficiency

    if margin <= 0:
        return Decimal("0")

    confidence = min(margin / basis.hysteresis_band, Decimal("1"))
    return confidence.quantize(Decimal("0.0001"))


__all__ = [
    "DEFAULT_DERYA_CLASSIFICATION_BASIS",
    "DeryaAssessment",
    "DeryaClassificationBasis",
    "DeryaObservation",
    "DeryaRegime",
    "DeryaResolutionState",
    "IndicatorSnapshot",
    "IndicatorValidity",
    "IndicatorValueStatus",
    "IntelligenceAssessment",
    "IntelligenceAssessmentKind",
    "calculate_derya_confidence",
    "classify_derya_regime_candidate",
    "resolve_derya_regime",
]

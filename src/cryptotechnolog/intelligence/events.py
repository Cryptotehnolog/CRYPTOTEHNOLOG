"""
Analysis-level event contracts для Phase 7.

Здесь фиксируется только typed event surface indicators/intelligence слоя.
Никакой trading-signal semantics этот модуль не вводит.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Protocol, cast

from cryptotechnolog.core.event import Event, Priority

if TYPE_CHECKING:
    from uuid import UUID

    from .models import DeryaAssessment, IndicatorSnapshot


class IntelligenceEventType(StrEnum):
    """Минимальный event vocabulary Phase 7."""

    INDICATOR_UPDATED = "INDICATOR_UPDATED"
    INTELLIGENCE_ASSESSMENT_UPDATED = "INTELLIGENCE_ASSESSMENT_UPDATED"
    DERYA_REGIME_CHANGED = "DERYA_REGIME_CHANGED"


class IntelligenceEventSource(StrEnum):
    """Стандартные источники analysis-level событий Phase 7."""

    INDICATOR_ENGINE = "INDICATOR_ENGINE"
    INTELLIGENCE_RUNTIME = "INTELLIGENCE_RUNTIME"
    DERYA_ENGINE = "DERYA_ENGINE"


class SupportsIntelligencePayload(Protocol):
    """Протокол для typed intelligence payloads."""

    def to_payload(self) -> dict[str, object]:
        """Конвертировать контракт в Event payload."""


def _slots_dataclass_to_payload(instance: object) -> dict[str, object]:
    """Преобразовать slots-dataclass в payload без зависимости от __dict__."""
    dataclass_type = cast("Any", instance.__class__)
    return {field.name: getattr(instance, field.name) for field in fields(dataclass_type)}


def default_priority_for_intelligence_event(event_type: IntelligenceEventType) -> Priority:
    """Определить приоритет analysis-level события."""
    if event_type == IntelligenceEventType.DERYA_REGIME_CHANGED:
        return Priority.HIGH
    return Priority.NORMAL


@dataclass(slots=True, frozen=True)
class IndicatorUpdatedPayload:
    """Payload для публикации обновлённого indicator snapshot."""

    symbol: str
    exchange: str
    timeframe: str
    indicator_name: str
    value: str | None
    updated_at: str
    validity_status: str
    observed_bars: int
    required_bars: int
    warming_bars_remaining: int
    invalid_reason: str | None
    parameters: dict[str, object]
    metadata: dict[str, object]

    @classmethod
    def from_snapshot(cls, snapshot: IndicatorSnapshot) -> IndicatorUpdatedPayload:
        """Сконвертировать indicator snapshot в event payload."""
        return cls(
            symbol=snapshot.symbol,
            exchange=snapshot.exchange,
            timeframe=snapshot.timeframe.value,
            indicator_name=snapshot.indicator_name,
            value=str(snapshot.value) if snapshot.value is not None else None,
            updated_at=snapshot.updated_at.isoformat(),
            validity_status=snapshot.validity.status.value,
            observed_bars=snapshot.validity.observed_bars,
            required_bars=snapshot.validity.required_bars,
            warming_bars_remaining=snapshot.validity.warming_bars_remaining,
            invalid_reason=snapshot.validity.invalid_reason,
            parameters=snapshot.parameters.copy(),
            metadata=snapshot.metadata.copy(),
        )

    def to_payload(self) -> dict[str, object]:
        """Конвертировать контракт в Event payload."""
        return _slots_dataclass_to_payload(self)


@dataclass(slots=True, frozen=True)
class IntelligenceAssessmentPayload:
    """Общий payload для transport-neutral intelligence assessment."""

    assessment_kind: str
    symbol: str
    exchange: str
    timeframe: str
    updated_at: str
    validity_status: str
    confidence: str | None
    metadata: dict[str, object]

    def to_payload(self) -> dict[str, object]:
        """Конвертировать контракт в Event payload."""
        return _slots_dataclass_to_payload(self)


@dataclass(slots=True, frozen=True)
class DeryaRegimeChangedPayload:
    """Payload для typed DERYA regime transition event."""

    symbol: str
    exchange: str
    timeframe: str
    current_regime: str | None
    previous_regime: str | None
    raw_efficiency: str | None
    smoothed_efficiency: str | None
    efficiency_slope: str | None
    regime_duration_bars: int
    regime_persistence_ratio: str
    resolution_state: str
    confidence: str | None
    updated_at: str
    classification_basis: dict[str, object]

    @classmethod
    def from_assessment(cls, assessment: DeryaAssessment) -> DeryaRegimeChangedPayload:
        """Сконвертировать DERYA assessment в regime-change payload."""
        basis = assessment.classification_basis
        return cls(
            symbol=assessment.symbol,
            exchange=assessment.exchange,
            timeframe=assessment.timeframe.value,
            current_regime=(
                assessment.current_regime.value if assessment.current_regime is not None else None
            ),
            previous_regime=(
                assessment.previous_regime.value if assessment.previous_regime is not None else None
            ),
            raw_efficiency=(
                str(assessment.raw_efficiency) if assessment.raw_efficiency is not None else None
            ),
            smoothed_efficiency=(
                str(assessment.smoothed_efficiency)
                if assessment.smoothed_efficiency is not None
                else None
            ),
            efficiency_slope=(
                str(assessment.efficiency_slope)
                if assessment.efficiency_slope is not None
                else None
            ),
            regime_duration_bars=assessment.regime_duration_bars,
            regime_persistence_ratio=str(assessment.regime_persistence_ratio),
            resolution_state=assessment.resolution_state.value,
            confidence=str(assessment.confidence) if assessment.confidence is not None else None,
            updated_at=assessment.updated_at.isoformat(),
            classification_basis={
                "high_efficiency_threshold": str(basis.high_efficiency_threshold),
                "low_efficiency_threshold": str(basis.low_efficiency_threshold),
                "slope_flat_threshold": str(basis.slope_flat_threshold),
                "hysteresis_band": str(basis.hysteresis_band),
                "min_persistence_bars": basis.min_persistence_bars,
            },
        )

    def to_payload(self) -> dict[str, object]:
        """Конвертировать контракт в Event payload."""
        return _slots_dataclass_to_payload(self)


def build_intelligence_event(
    *,
    event_type: IntelligenceEventType,
    payload: SupportsIntelligencePayload,
    source: str = IntelligenceEventSource.INTELLIGENCE_RUNTIME.value,
    correlation_id: UUID | None = None,
    priority: Priority | None = None,
) -> Event:
    """Построить Event Bus-compatible событие для Phase 7 analysis layer."""
    event = Event.new(
        event_type=event_type.value,
        source=source,
        payload=payload.to_payload(),
    )
    event.priority = priority or default_priority_for_intelligence_event(event_type)
    if correlation_id is not None:
        event.correlation_id = correlation_id
    return event


__all__ = [
    "DeryaRegimeChangedPayload",
    "IndicatorUpdatedPayload",
    "IntelligenceAssessmentPayload",
    "IntelligenceEventSource",
    "IntelligenceEventType",
    "build_intelligence_event",
    "default_priority_for_intelligence_event",
]

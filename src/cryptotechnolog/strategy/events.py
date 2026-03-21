"""
Typed event contracts для Phase 9 strategy foundation.

Этот vocabulary intentionally узкий:
- без portfolio/supervisor/opportunity/meta semantics;
- только для strategy layer как отдельного consumer contour.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Protocol, cast

from cryptotechnolog.core.event import Event, Priority

if TYPE_CHECKING:
    from uuid import UUID

    from .models import StrategyActionCandidate


class StrategyEventType(StrEnum):
    """Минимальный event vocabulary Phase 9 foundation."""

    STRATEGY_CANDIDATE_UPDATED = "STRATEGY_CANDIDATE_UPDATED"
    STRATEGY_ACTIONABLE = "STRATEGY_ACTIONABLE"
    STRATEGY_INVALIDATED = "STRATEGY_INVALIDATED"


class StrategyEventSource(StrEnum):
    """Стандартные источники событий strategy layer."""

    STRATEGY_RUNTIME = "STRATEGY_RUNTIME"
    STRATEGY_CONTOUR = "STRATEGY_CONTOUR"


class SupportsStrategyPayload(Protocol):
    """Протокол для typed strategy payload contracts."""

    def to_payload(self) -> dict[str, object]:
        """Конвертировать контракт в Event payload."""


def _slots_dataclass_to_payload(instance: object) -> dict[str, object]:
    """Преобразовать slots-dataclass в payload без зависимости от __dict__."""
    dataclass_type = cast("Any", instance.__class__)
    return {field.name: getattr(instance, field.name) for field in fields(dataclass_type)}


def default_priority_for_strategy_event(event_type: StrategyEventType) -> Priority:
    """Определить приоритет foundation strategy event."""
    if event_type == StrategyEventType.STRATEGY_ACTIONABLE:
        return Priority.HIGH
    return Priority.NORMAL


@dataclass(slots=True, frozen=True)
class StrategyActionCandidatePayload:
    """Payload strategy action candidate для event publication."""

    candidate_id: str
    contour_name: str
    strategy_name: str
    symbol: str
    exchange: str
    timeframe: str
    direction: str | None
    status: str
    validity_status: str
    originating_signal_id: str | None
    confidence: str | None
    reason_code: str | None
    generated_at: str
    expires_at: str | None
    missing_inputs: tuple[str, ...]
    metadata: dict[str, object]

    @classmethod
    def from_candidate(cls, candidate: StrategyActionCandidate) -> StrategyActionCandidatePayload:
        """Сконвертировать typed strategy candidate в event payload."""
        return cls(
            candidate_id=str(candidate.candidate_id),
            contour_name=candidate.contour_name,
            strategy_name=candidate.strategy_name,
            symbol=candidate.symbol,
            exchange=candidate.exchange,
            timeframe=candidate.timeframe.value,
            direction=candidate.direction.value if candidate.direction is not None else None,
            status=candidate.status.value,
            validity_status=candidate.validity.status.value,
            originating_signal_id=(
                str(candidate.originating_signal_id)
                if candidate.originating_signal_id is not None
                else None
            ),
            confidence=str(candidate.confidence) if candidate.confidence is not None else None,
            reason_code=candidate.reason_code.value if candidate.reason_code is not None else None,
            generated_at=candidate.freshness.generated_at.isoformat(),
            expires_at=(
                candidate.freshness.expires_at.isoformat()
                if candidate.freshness.expires_at is not None
                else None
            ),
            missing_inputs=candidate.validity.missing_inputs,
            metadata=candidate.metadata.copy(),
        )

    def to_payload(self) -> dict[str, object]:
        """Конвертировать контракт в Event payload."""
        return _slots_dataclass_to_payload(self)


def build_strategy_event(
    *,
    event_type: StrategyEventType,
    payload: SupportsStrategyPayload,
    source: str = StrategyEventSource.STRATEGY_RUNTIME.value,
    correlation_id: UUID | None = None,
    priority: Priority | None = None,
) -> Event:
    """Построить Event Bus-compatible событие для strategy layer."""
    event = Event.new(
        event_type=event_type.value,
        source=source,
        payload=payload.to_payload(),
    )
    event.priority = priority or default_priority_for_strategy_event(event_type)
    if correlation_id is not None:
        event.correlation_id = correlation_id
    return event


__all__ = [
    "StrategyActionCandidatePayload",
    "StrategyEventSource",
    "StrategyEventType",
    "build_strategy_event",
    "default_priority_for_strategy_event",
]

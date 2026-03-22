"""
Typed event contracts для Phase 13 position-expansion foundation.

Этот vocabulary intentionally узкий:
- без portfolio governor / protection / OMS semantics;
- только для position-expansion layer как отдельного consumer contour.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Protocol, cast

from cryptotechnolog.core.event import Event, Priority

if TYPE_CHECKING:
    from uuid import UUID

    from .models import PositionExpansionCandidate


class PositionExpansionEventType(StrEnum):
    """Минимальный event vocabulary Phase 13 foundation."""

    POSITION_EXPANSION_CANDIDATE_UPDATED = "POSITION_EXPANSION_CANDIDATE_UPDATED"
    POSITION_EXPANSION_APPROVED = "POSITION_EXPANSION_APPROVED"
    POSITION_EXPANSION_INVALIDATED = "POSITION_EXPANSION_INVALIDATED"


class PositionExpansionEventSource(StrEnum):
    """Стандартные источники событий position-expansion layer."""

    POSITION_EXPANSION_RUNTIME = "POSITION_EXPANSION_RUNTIME"
    POSITION_EXPANSION_CONTOUR = "POSITION_EXPANSION_CONTOUR"


class SupportsPositionExpansionPayload(Protocol):
    """Протокол для typed position-expansion payload contracts."""

    def to_payload(self) -> dict[str, object]:
        """Конвертировать контракт в Event payload."""


def _slots_dataclass_to_payload(instance: object) -> dict[str, object]:
    """Преобразовать slots-dataclass в payload без зависимости от __dict__."""
    dataclass_type = cast("Any", instance.__class__)
    return {field.name: getattr(instance, field.name) for field in fields(dataclass_type)}


def default_priority_for_position_expansion_event(
    event_type: PositionExpansionEventType,
) -> Priority:
    """Определить приоритет foundation position-expansion event."""
    if event_type == PositionExpansionEventType.POSITION_EXPANSION_APPROVED:
        return Priority.HIGH
    return Priority.NORMAL


@dataclass(slots=True, frozen=True)
class PositionExpansionPayload:
    """Payload expansion candidate для event publication."""

    expansion_id: str
    contour_name: str
    expansion_name: str
    symbol: str
    exchange: str
    timeframe: str
    source: str
    status: str
    decision: str
    validity_status: str
    direction: str | None
    originating_decision_id: str | None
    confidence: str | None
    priority_score: str | None
    reason_code: str | None
    generated_at: str
    expires_at: str | None
    missing_inputs: tuple[str, ...]
    metadata: dict[str, object]

    @classmethod
    def from_candidate(
        cls,
        candidate: PositionExpansionCandidate,
    ) -> PositionExpansionPayload:
        """Сконвертировать typed expansion candidate в event payload."""
        return cls(
            expansion_id=str(candidate.expansion_id),
            contour_name=candidate.contour_name,
            expansion_name=candidate.expansion_name,
            symbol=candidate.symbol,
            exchange=candidate.exchange,
            timeframe=candidate.timeframe.value,
            source=candidate.source.value,
            status=candidate.status.value,
            decision=candidate.decision.value,
            validity_status=candidate.validity.status.value,
            direction=candidate.direction.value if candidate.direction is not None else None,
            originating_decision_id=(
                str(candidate.originating_decision_id)
                if candidate.originating_decision_id is not None
                else None
            ),
            confidence=str(candidate.confidence) if candidate.confidence is not None else None,
            priority_score=(
                str(candidate.priority_score) if candidate.priority_score is not None else None
            ),
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


def build_position_expansion_event(
    *,
    event_type: PositionExpansionEventType,
    payload: SupportsPositionExpansionPayload,
    source: str = PositionExpansionEventSource.POSITION_EXPANSION_RUNTIME.value,
    correlation_id: UUID | None = None,
    priority: Priority | None = None,
) -> Event:
    """Построить Event Bus-compatible событие для position-expansion layer."""
    event = Event.new(
        event_type=event_type.value,
        source=source,
        payload=payload.to_payload(),
    )
    event.priority = priority or default_priority_for_position_expansion_event(event_type)
    if correlation_id is not None:
        event.correlation_id = correlation_id
    return event


__all__ = [
    "PositionExpansionEventSource",
    "PositionExpansionEventType",
    "PositionExpansionPayload",
    "build_position_expansion_event",
    "default_priority_for_position_expansion_event",
]

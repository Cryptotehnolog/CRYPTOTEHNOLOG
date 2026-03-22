"""
Typed event contracts для Phase 11 opportunity foundation.

Этот vocabulary intentionally узкий:
- без OMS / meta / strategy-manager semantics;
- только для selection layer как отдельного consumer contour.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Protocol, cast

from cryptotechnolog.core.event import Event, Priority

if TYPE_CHECKING:
    from uuid import UUID

    from .models import OpportunitySelectionCandidate


class OpportunityEventType(StrEnum):
    """Минимальный event vocabulary Phase 11 foundation."""

    OPPORTUNITY_CANDIDATE_UPDATED = "OPPORTUNITY_CANDIDATE_UPDATED"
    OPPORTUNITY_SELECTED = "OPPORTUNITY_SELECTED"
    OPPORTUNITY_INVALIDATED = "OPPORTUNITY_INVALIDATED"


class OpportunityEventSource(StrEnum):
    """Стандартные источники событий selection layer."""

    OPPORTUNITY_RUNTIME = "OPPORTUNITY_RUNTIME"
    OPPORTUNITY_CONTOUR = "OPPORTUNITY_CONTOUR"


class SupportsOpportunityPayload(Protocol):
    """Протокол для typed opportunity payload contracts."""

    def to_payload(self) -> dict[str, object]:
        """Конвертировать контракт в Event payload."""


def _slots_dataclass_to_payload(instance: object) -> dict[str, object]:
    """Преобразовать slots-dataclass в payload без зависимости от __dict__."""
    dataclass_type = cast("Any", instance.__class__)
    return {field.name: getattr(instance, field.name) for field in fields(dataclass_type)}


def default_priority_for_opportunity_event(event_type: OpportunityEventType) -> Priority:
    """Определить приоритет foundation opportunity event."""
    if event_type == OpportunityEventType.OPPORTUNITY_SELECTED:
        return Priority.HIGH
    return Priority.NORMAL


@dataclass(slots=True, frozen=True)
class OpportunitySelectionPayload:
    """Payload selection candidate для event publication."""

    selection_id: str
    contour_name: str
    selection_name: str
    symbol: str
    exchange: str
    timeframe: str
    source: str
    direction: str | None
    status: str
    validity_status: str
    originating_intent_id: str | None
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
        candidate: OpportunitySelectionCandidate,
    ) -> OpportunitySelectionPayload:
        """Сконвертировать typed selection candidate в event payload."""
        return cls(
            selection_id=str(candidate.selection_id),
            contour_name=candidate.contour_name,
            selection_name=candidate.selection_name,
            symbol=candidate.symbol,
            exchange=candidate.exchange,
            timeframe=candidate.timeframe.value,
            source=candidate.source.value,
            direction=candidate.direction.value if candidate.direction is not None else None,
            status=candidate.status.value,
            validity_status=candidate.validity.status.value,
            originating_intent_id=(
                str(candidate.originating_intent_id)
                if candidate.originating_intent_id is not None
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


def build_opportunity_event(
    *,
    event_type: OpportunityEventType,
    payload: SupportsOpportunityPayload,
    source: str = OpportunityEventSource.OPPORTUNITY_RUNTIME.value,
    correlation_id: UUID | None = None,
    priority: Priority | None = None,
) -> Event:
    """Построить Event Bus-compatible событие для selection layer."""
    event = Event.new(
        event_type=event_type.value,
        source=source,
        payload=payload.to_payload(),
    )
    event.priority = priority or default_priority_for_opportunity_event(event_type)
    if correlation_id is not None:
        event.correlation_id = correlation_id
    return event


__all__ = [
    "OpportunityEventSource",
    "OpportunityEventType",
    "OpportunitySelectionPayload",
    "build_opportunity_event",
    "default_priority_for_opportunity_event",
]

"""
Typed event contracts для Phase 12 orchestration foundation.

Этот vocabulary intentionally узкий:
- без full StrategyManager / OMS / kill switch semantics;
- только для orchestration layer как отдельного meta contour.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Protocol, cast

from cryptotechnolog.core.event import Event, Priority

if TYPE_CHECKING:
    from uuid import UUID

    from .models import OrchestrationDecisionCandidate


class OrchestrationEventType(StrEnum):
    """Минимальный event vocabulary Phase 12 foundation."""

    ORCHESTRATION_CANDIDATE_UPDATED = "ORCHESTRATION_CANDIDATE_UPDATED"
    ORCHESTRATION_DECIDED = "ORCHESTRATION_DECIDED"
    ORCHESTRATION_INVALIDATED = "ORCHESTRATION_INVALIDATED"


class OrchestrationEventSource(StrEnum):
    """Стандартные источники событий orchestration layer."""

    ORCHESTRATION_RUNTIME = "ORCHESTRATION_RUNTIME"
    ORCHESTRATION_CONTOUR = "ORCHESTRATION_CONTOUR"


class SupportsOrchestrationPayload(Protocol):
    """Протокол для typed orchestration payload contracts."""

    def to_payload(self) -> dict[str, object]:
        """Конвертировать контракт в Event payload."""


def _slots_dataclass_to_payload(instance: object) -> dict[str, object]:
    """Преобразовать slots-dataclass в payload без зависимости от __dict__."""
    dataclass_type = cast("Any", instance.__class__)
    return {field.name: getattr(instance, field.name) for field in fields(dataclass_type)}


def default_priority_for_orchestration_event(
    event_type: OrchestrationEventType,
) -> Priority:
    """Определить приоритет foundation orchestration event."""
    if event_type == OrchestrationEventType.ORCHESTRATION_DECIDED:
        return Priority.HIGH
    return Priority.NORMAL


@dataclass(slots=True, frozen=True)
class OrchestrationDecisionPayload:
    """Payload orchestration decision candidate для event publication."""

    decision_id: str
    contour_name: str
    orchestration_name: str
    symbol: str
    exchange: str
    timeframe: str
    source: str
    status: str
    decision: str
    validity_status: str
    direction: str | None
    originating_selection_id: str | None
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
        candidate: OrchestrationDecisionCandidate,
    ) -> OrchestrationDecisionPayload:
        """Сконвертировать typed orchestration candidate в event payload."""
        return cls(
            decision_id=str(candidate.decision_id),
            contour_name=candidate.contour_name,
            orchestration_name=candidate.orchestration_name,
            symbol=candidate.symbol,
            exchange=candidate.exchange,
            timeframe=candidate.timeframe.value,
            source=candidate.source.value,
            status=candidate.status.value,
            decision=candidate.decision.value,
            validity_status=candidate.validity.status.value,
            direction=candidate.direction.value if candidate.direction is not None else None,
            originating_selection_id=(
                str(candidate.originating_selection_id)
                if candidate.originating_selection_id is not None
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


def build_orchestration_event(
    *,
    event_type: OrchestrationEventType,
    payload: SupportsOrchestrationPayload,
    source: str = OrchestrationEventSource.ORCHESTRATION_RUNTIME.value,
    correlation_id: UUID | None = None,
    priority: Priority | None = None,
) -> Event:
    """Построить Event Bus-compatible событие для orchestration layer."""
    event = Event.new(
        event_type=event_type.value,
        source=source,
        payload=payload.to_payload(),
    )
    event.priority = priority or default_priority_for_orchestration_event(event_type)
    if correlation_id is not None:
        event.correlation_id = correlation_id
    return event


__all__ = [
    "OrchestrationDecisionPayload",
    "OrchestrationEventSource",
    "OrchestrationEventType",
    "build_orchestration_event",
    "default_priority_for_orchestration_event",
]

"""
Typed event contracts для Phase 10 execution foundation.

Этот vocabulary intentionally узкий:
- без OMS / router / advanced execution semantics;
- только для execution layer как отдельного consumer contour.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Protocol, cast

from cryptotechnolog.core.event import Event, Priority

if TYPE_CHECKING:
    from uuid import UUID

    from .models import ExecutionOrderIntent


class ExecutionEventType(StrEnum):
    """Минимальный event vocabulary Phase 10 foundation."""

    EXECUTION_INTENT_UPDATED = "EXECUTION_INTENT_UPDATED"
    EXECUTION_REQUESTED = "EXECUTION_REQUESTED"
    EXECUTION_INVALIDATED = "EXECUTION_INVALIDATED"


class ExecutionEventSource(StrEnum):
    """Стандартные источники событий execution layer."""

    EXECUTION_RUNTIME = "EXECUTION_RUNTIME"
    EXECUTION_CONTOUR = "EXECUTION_CONTOUR"


class SupportsExecutionPayload(Protocol):
    """Протокол для typed execution payload contracts."""

    def to_payload(self) -> dict[str, object]:
        """Конвертировать контракт в Event payload."""


def _slots_dataclass_to_payload(instance: object) -> dict[str, object]:
    """Преобразовать slots-dataclass в payload без зависимости от __dict__."""
    dataclass_type = cast("Any", instance.__class__)
    return {field.name: getattr(instance, field.name) for field in fields(dataclass_type)}


def default_priority_for_execution_event(event_type: ExecutionEventType) -> Priority:
    """Определить приоритет foundation execution event."""
    if event_type == ExecutionEventType.EXECUTION_REQUESTED:
        return Priority.HIGH
    return Priority.NORMAL


@dataclass(slots=True, frozen=True)
class ExecutionOrderIntentPayload:
    """Payload execution order-intent для event publication."""

    intent_id: str
    contour_name: str
    execution_name: str
    symbol: str
    exchange: str
    timeframe: str
    direction: str | None
    status: str
    validity_status: str
    originating_candidate_id: str | None
    confidence: str | None
    reason_code: str | None
    generated_at: str
    expires_at: str | None
    missing_inputs: tuple[str, ...]
    metadata: dict[str, object]

    @classmethod
    def from_intent(cls, intent: ExecutionOrderIntent) -> ExecutionOrderIntentPayload:
        """Сконвертировать typed execution intent в event payload."""
        return cls(
            intent_id=str(intent.intent_id),
            contour_name=intent.contour_name,
            execution_name=intent.execution_name,
            symbol=intent.symbol,
            exchange=intent.exchange,
            timeframe=intent.timeframe.value,
            direction=intent.direction.value if intent.direction is not None else None,
            status=intent.status.value,
            validity_status=intent.validity.status.value,
            originating_candidate_id=(
                str(intent.originating_candidate_id)
                if intent.originating_candidate_id is not None
                else None
            ),
            confidence=str(intent.confidence) if intent.confidence is not None else None,
            reason_code=intent.reason_code.value if intent.reason_code is not None else None,
            generated_at=intent.freshness.generated_at.isoformat(),
            expires_at=(
                intent.freshness.expires_at.isoformat()
                if intent.freshness.expires_at is not None
                else None
            ),
            missing_inputs=intent.validity.missing_inputs,
            metadata=intent.metadata.copy(),
        )

    def to_payload(self) -> dict[str, object]:
        """Конвертировать контракт в Event payload."""
        return _slots_dataclass_to_payload(self)


def build_execution_event(
    *,
    event_type: ExecutionEventType,
    payload: SupportsExecutionPayload,
    source: str = ExecutionEventSource.EXECUTION_RUNTIME.value,
    correlation_id: UUID | None = None,
    priority: Priority | None = None,
) -> Event:
    """Построить Event Bus-compatible событие для execution layer."""
    event = Event.new(
        event_type=event_type.value,
        source=source,
        payload=payload.to_payload(),
    )
    event.priority = priority or default_priority_for_execution_event(event_type)
    if correlation_id is not None:
        event.correlation_id = correlation_id
    return event


__all__ = [
    "ExecutionEventSource",
    "ExecutionEventType",
    "ExecutionOrderIntentPayload",
    "build_execution_event",
    "default_priority_for_execution_event",
]

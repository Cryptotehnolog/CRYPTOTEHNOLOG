"""
Typed event contracts для Phase 15 protection foundation.

Этот vocabulary intentionally узкий:
- без OMS / liquidation / notifications semantics;
- только для protection layer как отдельного consumer contour.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Protocol, cast

from cryptotechnolog.core.event import Event, Priority

if TYPE_CHECKING:
    from uuid import UUID

    from .models import ProtectionSupervisorCandidate


class ProtectionEventType(StrEnum):
    """Минимальный event vocabulary Phase 15 foundation."""

    PROTECTION_CANDIDATE_UPDATED = "PROTECTION_CANDIDATE_UPDATED"
    PROTECTION_PROTECTED = "PROTECTION_PROTECTED"
    PROTECTION_HALTED = "PROTECTION_HALTED"
    PROTECTION_FROZEN = "PROTECTION_FROZEN"
    PROTECTION_INVALIDATED = "PROTECTION_INVALIDATED"


class ProtectionEventSource(StrEnum):
    """Стандартные источники событий protection layer."""

    PROTECTION_RUNTIME = "PROTECTION_RUNTIME"
    PROTECTION_CONTOUR = "PROTECTION_CONTOUR"


class SupportsProtectionPayload(Protocol):
    """Протокол для typed protection payload contracts."""

    def to_payload(self) -> dict[str, object]:
        """Конвертировать контракт в Event payload."""


def _slots_dataclass_to_payload(instance: object) -> dict[str, object]:
    """Преобразовать slots-dataclass в payload без зависимости от __dict__."""
    dataclass_type = cast("Any", instance.__class__)
    return {field.name: getattr(instance, field.name) for field in fields(dataclass_type)}


def default_priority_for_protection_event(
    event_type: ProtectionEventType,
) -> Priority:
    """Определить приоритет foundation protection event."""
    if event_type in {
        ProtectionEventType.PROTECTION_HALTED,
        ProtectionEventType.PROTECTION_FROZEN,
    }:
        return Priority.HIGH
    return Priority.NORMAL


@dataclass(slots=True, frozen=True)
class ProtectionPayload:
    """Payload protection candidate для event publication."""

    protection_id: str
    contour_name: str
    supervisor_name: str
    symbol: str
    exchange: str
    timeframe: str
    source: str
    status: str
    decision: str
    validity_status: str
    originating_governor_id: str | None
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
        candidate: ProtectionSupervisorCandidate,
    ) -> ProtectionPayload:
        """Сконвертировать typed protection candidate в event payload."""
        return cls(
            protection_id=str(candidate.protection_id),
            contour_name=candidate.contour_name,
            supervisor_name=candidate.supervisor_name,
            symbol=candidate.symbol,
            exchange=candidate.exchange,
            timeframe=candidate.timeframe.value,
            source=candidate.source.value,
            status=candidate.status.value,
            decision=candidate.decision.value,
            validity_status=candidate.validity.status.value,
            originating_governor_id=(
                str(candidate.originating_governor_id)
                if candidate.originating_governor_id is not None
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


def build_protection_event(
    *,
    event_type: ProtectionEventType,
    payload: SupportsProtectionPayload,
    source: str = ProtectionEventSource.PROTECTION_RUNTIME.value,
    correlation_id: UUID | None = None,
    priority: Priority | None = None,
) -> Event:
    """Построить Event Bus-compatible событие для protection layer."""
    event = Event.new(
        event_type=event_type.value,
        source=source,
        payload=payload.to_payload(),
    )
    event.priority = priority or default_priority_for_protection_event(event_type)
    if correlation_id is not None:
        event.correlation_id = correlation_id
    return event


__all__ = [
    "ProtectionEventSource",
    "ProtectionEventType",
    "ProtectionPayload",
    "build_protection_event",
    "default_priority_for_protection_event",
]

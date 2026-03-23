"""
Typed event contracts для Phase 17 manager foundation.

Этот vocabulary intentionally узкий:
- без Execution / OMS ownership semantics;
- без notifications / approval / liquidation / validation semantics;
- только для manager layer как отдельного workflow-coordination contour.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Protocol, cast

from cryptotechnolog.core.event import Event, Priority

if TYPE_CHECKING:
    from uuid import UUID

    from .models import ManagerWorkflowCandidate


class ManagerEventType(StrEnum):
    """Минимальный event vocabulary Phase 17 foundation."""

    MANAGER_CANDIDATE_UPDATED = "MANAGER_CANDIDATE_UPDATED"
    MANAGER_WORKFLOW_COORDINATED = "MANAGER_WORKFLOW_COORDINATED"
    MANAGER_WORKFLOW_ABSTAINED = "MANAGER_WORKFLOW_ABSTAINED"
    MANAGER_WORKFLOW_INVALIDATED = "MANAGER_WORKFLOW_INVALIDATED"


class ManagerEventSource(StrEnum):
    """Стандартные источники событий manager layer."""

    MANAGER_RUNTIME = "MANAGER_RUNTIME"
    MANAGER_CONTOUR = "MANAGER_CONTOUR"


class SupportsManagerPayload(Protocol):
    """Протокол для typed manager payload contracts."""

    def to_payload(self) -> dict[str, object]:
        """Конвертировать контракт в Event payload."""


def _slots_dataclass_to_payload(instance: object) -> dict[str, object]:
    """Преобразовать slots-dataclass в payload без зависимости от __dict__."""
    dataclass_type = cast("Any", instance.__class__)
    return {field.name: getattr(instance, field.name) for field in fields(dataclass_type)}


def default_priority_for_manager_event(event_type: ManagerEventType) -> Priority:
    """Определить приоритет foundation manager event."""
    if event_type == ManagerEventType.MANAGER_WORKFLOW_COORDINATED:
        return Priority.HIGH
    return Priority.NORMAL


@dataclass(slots=True, frozen=True)
class ManagerWorkflowPayload:
    """Payload manager workflow candidate для event publication."""

    workflow_id: str
    contour_name: str
    manager_name: str
    symbol: str
    exchange: str
    timeframe: str
    source: str
    status: str
    decision: str
    validity_status: str
    originating_selection_id: str | None
    originating_decision_id: str | None
    originating_expansion_id: str | None
    originating_governor_id: str | None
    originating_protection_id: str | None
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
        candidate: ManagerWorkflowCandidate,
    ) -> ManagerWorkflowPayload:
        """Сконвертировать typed manager candidate в event payload."""
        return cls(
            workflow_id=str(candidate.workflow_id),
            contour_name=candidate.contour_name,
            manager_name=candidate.manager_name,
            symbol=candidate.symbol,
            exchange=candidate.exchange,
            timeframe=candidate.timeframe.value,
            source=candidate.source.value,
            status=candidate.status.value,
            decision=candidate.decision.value,
            validity_status=candidate.validity.status.value,
            originating_selection_id=(
                str(candidate.originating_selection_id)
                if candidate.originating_selection_id is not None
                else None
            ),
            originating_decision_id=(
                str(candidate.originating_decision_id)
                if candidate.originating_decision_id is not None
                else None
            ),
            originating_expansion_id=(
                str(candidate.originating_expansion_id)
                if candidate.originating_expansion_id is not None
                else None
            ),
            originating_governor_id=(
                str(candidate.originating_governor_id)
                if candidate.originating_governor_id is not None
                else None
            ),
            originating_protection_id=(
                str(candidate.originating_protection_id)
                if candidate.originating_protection_id is not None
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


def build_manager_event(
    *,
    event_type: ManagerEventType,
    payload: SupportsManagerPayload,
    source: str = ManagerEventSource.MANAGER_RUNTIME.value,
    correlation_id: UUID | None = None,
    priority: Priority | None = None,
) -> Event:
    """Построить Event Bus-compatible событие для manager layer."""
    event = Event.new(
        event_type=event_type.value,
        source=source,
        payload=payload.to_payload(),
    )
    event.priority = priority or default_priority_for_manager_event(event_type)
    if correlation_id is not None:
        event.correlation_id = correlation_id
    return event


__all__ = [
    "ManagerEventSource",
    "ManagerEventType",
    "ManagerWorkflowPayload",
    "build_manager_event",
    "default_priority_for_manager_event",
]

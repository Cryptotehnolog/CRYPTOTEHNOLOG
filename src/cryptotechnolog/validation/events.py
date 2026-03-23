"""
Typed event contracts для Phase 18 validation foundation.

Этот vocabulary intentionally узкий:
- без analytics / reporting ownership;
- без backtesting / paper-trading semantics;
- без notifications / approval / liquidation / dashboard semantics;
- только для validation layer как narrow review contour.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Protocol, cast

from cryptotechnolog.core.event import Event, Priority

if TYPE_CHECKING:
    from uuid import UUID

    from .models import ValidationReviewCandidate


class ValidationEventType(StrEnum):
    """Минимальный event vocabulary Phase 18 foundation."""

    VALIDATION_CANDIDATE_UPDATED = "VALIDATION_CANDIDATE_UPDATED"
    VALIDATION_WORKFLOW_VALIDATED = "VALIDATION_WORKFLOW_VALIDATED"
    VALIDATION_WORKFLOW_ABSTAINED = "VALIDATION_WORKFLOW_ABSTAINED"
    VALIDATION_WORKFLOW_INVALIDATED = "VALIDATION_WORKFLOW_INVALIDATED"


class ValidationEventSource(StrEnum):
    """Стандартные источники событий validation layer."""

    VALIDATION_RUNTIME = "VALIDATION_RUNTIME"
    VALIDATION_CONTOUR = "VALIDATION_CONTOUR"


class SupportsValidationPayload(Protocol):
    """Протокол для typed validation payload contracts."""

    def to_payload(self) -> dict[str, object]:
        """Конвертировать контракт в Event payload."""


def _slots_dataclass_to_payload(instance: object) -> dict[str, object]:
    """Преобразовать slots-dataclass в payload без зависимости от __dict__."""
    dataclass_type = cast("Any", instance.__class__)
    return {field.name: getattr(instance, field.name) for field in fields(dataclass_type)}


def default_priority_for_validation_event(event_type: ValidationEventType) -> Priority:
    """Определить приоритет foundation validation event."""
    if event_type == ValidationEventType.VALIDATION_WORKFLOW_VALIDATED:
        return Priority.HIGH
    return Priority.NORMAL


@dataclass(slots=True, frozen=True)
class ValidationReviewPayload:
    """Payload validation review candidate для event publication."""

    review_id: str
    contour_name: str
    validation_name: str
    symbol: str
    exchange: str
    timeframe: str
    source: str
    status: str
    decision: str
    validity_status: str
    originating_workflow_id: str | None
    originating_governor_id: str | None
    originating_protection_id: str | None
    originating_oms_order_id: str | None
    confidence: str | None
    review_score: str | None
    reason_code: str | None
    generated_at: str
    expires_at: str | None
    missing_inputs: tuple[str, ...]
    metadata: dict[str, object]

    @classmethod
    def from_candidate(
        cls,
        candidate: ValidationReviewCandidate,
    ) -> ValidationReviewPayload:
        """Сконвертировать typed validation candidate в event payload."""
        return cls(
            review_id=str(candidate.review_id),
            contour_name=candidate.contour_name,
            validation_name=candidate.validation_name,
            symbol=candidate.symbol,
            exchange=candidate.exchange,
            timeframe=candidate.timeframe.value,
            source=candidate.source.value,
            status=candidate.status.value,
            decision=candidate.decision.value,
            validity_status=candidate.validity.status.value,
            originating_workflow_id=(
                str(candidate.originating_workflow_id)
                if candidate.originating_workflow_id is not None
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
            originating_oms_order_id=(
                str(candidate.originating_oms_order_id)
                if candidate.originating_oms_order_id is not None
                else None
            ),
            confidence=str(candidate.confidence) if candidate.confidence is not None else None,
            review_score=str(candidate.review_score)
            if candidate.review_score is not None
            else None,
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


def build_validation_event(
    *,
    event_type: ValidationEventType,
    payload: SupportsValidationPayload,
    source: str = ValidationEventSource.VALIDATION_RUNTIME.value,
    correlation_id: UUID | None = None,
    priority: Priority | None = None,
) -> Event:
    """Построить Event Bus-compatible событие для validation layer."""
    event = Event.new(
        event_type=event_type.value,
        source=source,
        payload=payload.to_payload(),
    )
    event.priority = priority or default_priority_for_validation_event(event_type)
    if correlation_id is not None:
        event.correlation_id = correlation_id
    return event


__all__ = [
    "ValidationEventSource",
    "ValidationEventType",
    "ValidationReviewPayload",
    "build_validation_event",
    "default_priority_for_validation_event",
]

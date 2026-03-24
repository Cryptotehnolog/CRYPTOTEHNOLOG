"""
Typed event contracts для Phase 19 paper foundation.

Этот vocabulary intentionally узкий:
- без analytics / reporting ownership;
- без backtesting / replay semantics;
- без dashboard / operator semantics;
- без notifications / approval / liquidation semantics;
- только для paper layer как narrow rehearsal contour.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Protocol, cast

from cryptotechnolog.core.event import Event, Priority

if TYPE_CHECKING:
    from uuid import UUID

    from .models import PaperRehearsalCandidate


class PaperEventType(StrEnum):
    """Минимальный event vocabulary Phase 19 foundation."""

    PAPER_CANDIDATE_UPDATED = "PAPER_CANDIDATE_UPDATED"
    PAPER_REHEARSAL_REHEARSED = "PAPER_REHEARSAL_REHEARSED"
    PAPER_REHEARSAL_ABSTAINED = "PAPER_REHEARSAL_ABSTAINED"
    PAPER_REHEARSAL_INVALIDATED = "PAPER_REHEARSAL_INVALIDATED"


class PaperEventSource(StrEnum):
    """Стандартные источники событий paper layer."""

    PAPER_RUNTIME = "PAPER_RUNTIME"
    PAPER_CONTOUR = "PAPER_CONTOUR"


class SupportsPaperPayload(Protocol):
    """Протокол для typed paper payload contracts."""

    def to_payload(self) -> dict[str, object]:
        """Конвертировать контракт в Event payload."""


def _slots_dataclass_to_payload(instance: object) -> dict[str, object]:
    """Преобразовать slots-dataclass в payload без зависимости от __dict__."""
    dataclass_type = cast("Any", instance.__class__)
    return {field.name: getattr(instance, field.name) for field in fields(dataclass_type)}


def default_priority_for_paper_event(event_type: PaperEventType) -> Priority:
    """Определить приоритет foundation paper event."""
    if event_type == PaperEventType.PAPER_REHEARSAL_REHEARSED:
        return Priority.HIGH
    return Priority.NORMAL


@dataclass(slots=True, frozen=True)
class PaperRehearsalPayload:
    """Payload paper rehearsal candidate для event publication."""

    rehearsal_id: str
    contour_name: str
    paper_name: str
    symbol: str
    exchange: str
    timeframe: str
    source: str
    status: str
    decision: str
    validity_status: str
    originating_workflow_id: str | None
    originating_review_id: str | None
    originating_oms_order_id: str | None
    confidence: str | None
    rehearsal_score: str | None
    reason_code: str | None
    generated_at: str
    expires_at: str | None
    missing_inputs: tuple[str, ...]
    metadata: dict[str, object]

    @classmethod
    def from_candidate(
        cls,
        candidate: PaperRehearsalCandidate,
    ) -> PaperRehearsalPayload:
        """Сконвертировать typed paper candidate в event payload."""
        return cls(
            rehearsal_id=str(candidate.rehearsal_id),
            contour_name=candidate.contour_name,
            paper_name=candidate.paper_name,
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
            originating_review_id=(
                str(candidate.originating_review_id)
                if candidate.originating_review_id is not None
                else None
            ),
            originating_oms_order_id=(
                str(candidate.originating_oms_order_id)
                if candidate.originating_oms_order_id is not None
                else None
            ),
            confidence=str(candidate.confidence) if candidate.confidence is not None else None,
            rehearsal_score=(
                str(candidate.rehearsal_score) if candidate.rehearsal_score is not None else None
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


def build_paper_event(
    *,
    event_type: PaperEventType,
    payload: SupportsPaperPayload,
    source: str = PaperEventSource.PAPER_RUNTIME.value,
    correlation_id: UUID | None = None,
    priority: Priority | None = None,
) -> Event:
    """Построить Event Bus-compatible событие для paper layer."""
    event = Event.new(
        event_type=event_type.value,
        source=source,
        payload=payload.to_payload(),
    )
    event.priority = priority or default_priority_for_paper_event(event_type)
    if correlation_id is not None:
        event.correlation_id = correlation_id
    return event


__all__ = [
    "PaperEventSource",
    "PaperEventType",
    "PaperRehearsalPayload",
    "build_paper_event",
    "default_priority_for_paper_event",
]

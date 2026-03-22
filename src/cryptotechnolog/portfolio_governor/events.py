"""
Typed event contracts для Phase 14 portfolio-governor foundation.

Этот vocabulary intentionally узкий:
- без protection / supervisor / OMS semantics;
- только для portfolio-governor layer как отдельного consumer contour.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Protocol, cast

from cryptotechnolog.core.event import Event, Priority

if TYPE_CHECKING:
    from uuid import UUID

    from .models import PortfolioGovernorCandidate


class PortfolioGovernorEventType(StrEnum):
    """Минимальный event vocabulary Phase 14 foundation."""

    PORTFOLIO_GOVERNOR_CANDIDATE_UPDATED = "PORTFOLIO_GOVERNOR_CANDIDATE_UPDATED"
    PORTFOLIO_GOVERNOR_APPROVED = "PORTFOLIO_GOVERNOR_APPROVED"
    PORTFOLIO_GOVERNOR_INVALIDATED = "PORTFOLIO_GOVERNOR_INVALIDATED"


class PortfolioGovernorEventSource(StrEnum):
    """Стандартные источники событий portfolio-governor layer."""

    PORTFOLIO_GOVERNOR_RUNTIME = "PORTFOLIO_GOVERNOR_RUNTIME"
    PORTFOLIO_GOVERNOR_CONTOUR = "PORTFOLIO_GOVERNOR_CONTOUR"


class SupportsPortfolioGovernorPayload(Protocol):
    """Протокол для typed portfolio-governor payload contracts."""

    def to_payload(self) -> dict[str, object]:
        """Конвертировать контракт в Event payload."""


def _slots_dataclass_to_payload(instance: object) -> dict[str, object]:
    """Преобразовать slots-dataclass в payload без зависимости от __dict__."""
    dataclass_type = cast("Any", instance.__class__)
    return {field.name: getattr(instance, field.name) for field in fields(dataclass_type)}


def default_priority_for_portfolio_governor_event(
    event_type: PortfolioGovernorEventType,
) -> Priority:
    """Определить приоритет foundation portfolio-governor event."""
    if event_type == PortfolioGovernorEventType.PORTFOLIO_GOVERNOR_APPROVED:
        return Priority.HIGH
    return Priority.NORMAL


@dataclass(slots=True, frozen=True)
class PortfolioGovernorPayload:
    """Payload governor candidate для event publication."""

    governor_id: str
    contour_name: str
    governor_name: str
    symbol: str
    exchange: str
    timeframe: str
    source: str
    status: str
    decision: str
    validity_status: str
    direction: str | None
    originating_expansion_id: str | None
    confidence: str | None
    priority_score: str | None
    capital_fraction: str | None
    reason_code: str | None
    generated_at: str
    expires_at: str | None
    missing_inputs: tuple[str, ...]
    metadata: dict[str, object]

    @classmethod
    def from_candidate(
        cls,
        candidate: PortfolioGovernorCandidate,
    ) -> PortfolioGovernorPayload:
        """Сконвертировать typed governor candidate в event payload."""
        return cls(
            governor_id=str(candidate.governor_id),
            contour_name=candidate.contour_name,
            governor_name=candidate.governor_name,
            symbol=candidate.symbol,
            exchange=candidate.exchange,
            timeframe=candidate.timeframe.value,
            source=candidate.source.value,
            status=candidate.status.value,
            decision=candidate.decision.value,
            validity_status=candidate.validity.status.value,
            direction=candidate.direction.value if candidate.direction is not None else None,
            originating_expansion_id=(
                str(candidate.originating_expansion_id)
                if candidate.originating_expansion_id is not None
                else None
            ),
            confidence=str(candidate.confidence) if candidate.confidence is not None else None,
            priority_score=(
                str(candidate.priority_score) if candidate.priority_score is not None else None
            ),
            capital_fraction=(
                str(candidate.capital_fraction) if candidate.capital_fraction is not None else None
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


def build_portfolio_governor_event(
    *,
    event_type: PortfolioGovernorEventType,
    payload: SupportsPortfolioGovernorPayload,
    source: str = PortfolioGovernorEventSource.PORTFOLIO_GOVERNOR_RUNTIME.value,
    correlation_id: UUID | None = None,
    priority: Priority | None = None,
) -> Event:
    """Построить Event Bus-compatible событие для portfolio-governor layer."""
    event = Event.new(
        event_type=event_type.value,
        source=source,
        payload=payload.to_payload(),
    )
    event.priority = priority or default_priority_for_portfolio_governor_event(event_type)
    if correlation_id is not None:
        event.correlation_id = correlation_id
    return event


__all__ = [
    "PortfolioGovernorEventSource",
    "PortfolioGovernorEventType",
    "PortfolioGovernorPayload",
    "build_portfolio_governor_event",
    "default_priority_for_portfolio_governor_event",
]

"""
Typed event contracts для Phase 8 signal foundation.

Этот vocabulary intentionally узкий:
- без opportunity/meta/pyramiding semantics;
- только для signal layer как отдельного consumer contour.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Protocol, cast

from cryptotechnolog.core.event import Event, Priority

if TYPE_CHECKING:
    from uuid import UUID

    from .models import SignalSnapshot


class SignalEventType(StrEnum):
    """Минимальный event vocabulary Phase 8 foundation."""

    SIGNAL_SNAPSHOT_UPDATED = "SIGNAL_SNAPSHOT_UPDATED"
    SIGNAL_EMITTED = "SIGNAL_EMITTED"
    SIGNAL_INVALIDATED = "SIGNAL_INVALIDATED"


class SignalEventSource(StrEnum):
    """Стандартные источники событий signal layer."""

    SIGNAL_RUNTIME = "SIGNAL_RUNTIME"
    SIGNAL_CONTOUR = "SIGNAL_CONTOUR"


class SupportsSignalPayload(Protocol):
    """Протокол для typed signal payload contracts."""

    def to_payload(self) -> dict[str, object]:
        """Конвертировать контракт в Event payload."""


def _slots_dataclass_to_payload(instance: object) -> dict[str, object]:
    """Преобразовать slots-dataclass в payload без зависимости от __dict__."""
    dataclass_type = cast("Any", instance.__class__)
    return {field.name: getattr(instance, field.name) for field in fields(dataclass_type)}


def default_priority_for_signal_event(event_type: SignalEventType) -> Priority:
    """Определить приоритет foundation signal event."""
    if event_type == SignalEventType.SIGNAL_EMITTED:
        return Priority.HIGH
    return Priority.NORMAL


@dataclass(slots=True, frozen=True)
class SignalSnapshotPayload:
    """Payload signal snapshot для event publication."""

    signal_id: str
    contour_name: str
    symbol: str
    exchange: str
    timeframe: str
    direction: str | None
    status: str
    validity_status: str
    confidence: str | None
    entry_price: str | None
    stop_loss: str | None
    take_profit: str | None
    reason_code: str | None
    generated_at: str
    expires_at: str | None
    missing_inputs: tuple[str, ...]
    metadata: dict[str, object]

    @classmethod
    def from_snapshot(cls, snapshot: SignalSnapshot) -> SignalSnapshotPayload:
        """Сконвертировать typed signal snapshot в event payload."""
        return cls(
            signal_id=str(snapshot.signal_id),
            contour_name=snapshot.contour_name,
            symbol=snapshot.symbol,
            exchange=snapshot.exchange,
            timeframe=snapshot.timeframe.value,
            direction=snapshot.direction.value if snapshot.direction is not None else None,
            status=snapshot.status.value,
            validity_status=snapshot.validity.status.value,
            confidence=str(snapshot.confidence) if snapshot.confidence is not None else None,
            entry_price=str(snapshot.entry_price) if snapshot.entry_price is not None else None,
            stop_loss=str(snapshot.stop_loss) if snapshot.stop_loss is not None else None,
            take_profit=str(snapshot.take_profit) if snapshot.take_profit is not None else None,
            reason_code=snapshot.reason_code.value if snapshot.reason_code is not None else None,
            generated_at=snapshot.freshness.generated_at.isoformat(),
            expires_at=(
                snapshot.freshness.expires_at.isoformat()
                if snapshot.freshness.expires_at is not None
                else None
            ),
            missing_inputs=snapshot.validity.missing_inputs,
            metadata=snapshot.metadata.copy(),
        )

    def to_payload(self) -> dict[str, object]:
        """Конвертировать контракт в Event payload."""
        return _slots_dataclass_to_payload(self)


def build_signal_event(
    *,
    event_type: SignalEventType,
    payload: SupportsSignalPayload,
    source: str = SignalEventSource.SIGNAL_RUNTIME.value,
    correlation_id: UUID | None = None,
    priority: Priority | None = None,
) -> Event:
    """Построить Event Bus-compatible событие для signal layer."""
    event = Event.new(
        event_type=event_type.value,
        source=source,
        payload=payload.to_payload(),
    )
    event.priority = priority or default_priority_for_signal_event(event_type)
    if correlation_id is not None:
        event.correlation_id = correlation_id
    return event


__all__ = [
    "SignalEventSource",
    "SignalEventType",
    "SignalSnapshotPayload",
    "build_signal_event",
    "default_priority_for_signal_event",
]

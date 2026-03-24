"""
Typed event contracts для Phase 16 OMS foundation.

Этот vocabulary intentionally узкий:
- без liquidation / notifications / approval workflow semantics;
- только для OMS layer как отдельного order-state contour.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Protocol, cast

from cryptotechnolog.core.event import Event, Priority

if TYPE_CHECKING:
    from uuid import UUID

    from .models import OmsOrderRecord


class OmsEventType(StrEnum):
    """Минимальный event vocabulary Phase 16 foundation."""

    OMS_ORDER_REGISTERED = "OMS_ORDER_REGISTERED"
    OMS_ORDER_SUBMITTED = "OMS_ORDER_SUBMITTED"
    OMS_ORDER_ACCEPTED = "OMS_ORDER_ACCEPTED"
    OMS_ORDER_PARTIALLY_FILLED = "OMS_ORDER_PARTIALLY_FILLED"
    OMS_ORDER_FILLED = "OMS_ORDER_FILLED"
    OMS_ORDER_CANCELLED = "OMS_ORDER_CANCELLED"
    OMS_ORDER_REJECTED = "OMS_ORDER_REJECTED"
    OMS_ORDER_EXPIRED = "OMS_ORDER_EXPIRED"


class OmsEventSource(StrEnum):
    """Стандартные источники событий OMS layer."""

    OMS_RUNTIME = "OMS_RUNTIME"
    OMS_CONTOUR = "OMS_CONTOUR"


class SupportsOmsPayload(Protocol):
    """Протокол для typed OMS payload contracts."""

    def to_payload(self) -> dict[str, object]:
        """Конвертировать контракт в Event payload."""


def _slots_dataclass_to_payload(instance: object) -> dict[str, object]:
    """Преобразовать slots-dataclass в payload без зависимости от __dict__."""
    dataclass_type = cast("Any", instance.__class__)
    return {field.name: getattr(instance, field.name) for field in fields(dataclass_type)}


def default_priority_for_oms_event(event_type: OmsEventType) -> Priority:
    """Определить приоритет foundation OMS event."""
    if event_type in {
        OmsEventType.OMS_ORDER_FILLED,
        OmsEventType.OMS_ORDER_CANCELLED,
        OmsEventType.OMS_ORDER_REJECTED,
        OmsEventType.OMS_ORDER_EXPIRED,
    }:
        return Priority.HIGH
    return Priority.NORMAL


@dataclass(slots=True, frozen=True)
class OmsOrderPayload:
    """Payload centralized order-state для event publication."""

    oms_order_id: str
    contour_name: str
    oms_name: str
    symbol: str
    exchange: str
    timeframe: str
    source: str
    lifecycle_status: str
    validity_status: str
    originating_intent_id: str | None
    client_order_id: str | None
    external_order_id: str | None
    query_scope: str
    state_version: int
    reason_code: str | None
    generated_at: str
    expires_at: str | None
    missing_inputs: tuple[str, ...]
    metadata: dict[str, object]

    @classmethod
    def from_record(cls, record: OmsOrderRecord) -> OmsOrderPayload:
        """Сконвертировать typed OMS record в event payload."""
        return cls(
            oms_order_id=str(record.oms_order_id),
            contour_name=record.contour_name,
            oms_name=record.oms_name,
            symbol=record.symbol,
            exchange=record.exchange,
            timeframe=record.timeframe.value,
            source=record.source.value,
            lifecycle_status=record.lifecycle_status.value,
            validity_status=record.validity.status.value,
            originating_intent_id=(
                str(record.originating_intent_id)
                if record.originating_intent_id is not None
                else None
            ),
            client_order_id=record.client_order_id,
            external_order_id=record.external_order_id,
            query_scope=record.locator.query_scope.value,
            state_version=record.state_version,
            reason_code=record.reason_code.value if record.reason_code is not None else None,
            generated_at=record.freshness.generated_at.isoformat(),
            expires_at=(
                record.freshness.expires_at.isoformat()
                if record.freshness.expires_at is not None
                else None
            ),
            missing_inputs=record.validity.missing_inputs,
            metadata=record.metadata.copy(),
        )

    def to_payload(self) -> dict[str, object]:
        """Конвертировать контракт в Event payload."""
        return _slots_dataclass_to_payload(self)


def build_oms_event(
    *,
    event_type: OmsEventType,
    payload: SupportsOmsPayload,
    source: str = OmsEventSource.OMS_RUNTIME.value,
    correlation_id: UUID | None = None,
    priority: Priority | None = None,
) -> Event:
    """Построить Event Bus-compatible событие для OMS layer."""
    event = Event.new(
        event_type=event_type.value,
        source=source,
        payload=payload.to_payload(),
    )
    event.priority = priority or default_priority_for_oms_event(event_type)
    if correlation_id is not None:
        event.correlation_id = correlation_id
    return event


__all__ = [
    "OmsEventSource",
    "OmsEventType",
    "OmsOrderPayload",
    "build_oms_event",
    "default_priority_for_oms_event",
]

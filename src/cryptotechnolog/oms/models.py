"""
Contract-first модели Phase 16 для OMS layer.

Этот модуль фиксирует минимальный foundation scope:
- typed order-lifecycle semantics;
- centralized order-state / order-registry truth;
- typed OMS context contract;
- базовые invariants OMS layer без liquidation / notifications / broader ops логики.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from datetime import datetime

    from cryptotechnolog.execution import ExecutionOrderIntent
    from cryptotechnolog.market_data import MarketDataTimeframe


class OmsLifecycleStatus(StrEnum):
    """Lifecycle-состояние OMS order-state."""

    REGISTERED = "registered"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class OmsValidityStatus(StrEnum):
    """Состояние готовности OMS context или OMS record."""

    VALID = "valid"
    WARMING = "warming"
    INVALID = "invalid"


class OmsReasonCode(StrEnum):
    """Узкие reason semantics для foundation OMS layer."""

    CONTEXT_READY = "context_ready"
    CONTEXT_INCOMPLETE = "context_incomplete"
    EXECUTION_NOT_EXECUTABLE = "execution_not_executable"
    ORDER_REGISTERED = "order_registered"
    ORDER_SUBMITTED = "order_submitted"
    ORDER_ACCEPTED = "order_accepted"
    ORDER_PARTIALLY_FILLED = "order_partially_filled"
    ORDER_FILLED = "order_filled"
    ORDER_CANCELLED = "order_cancelled"
    ORDER_REJECTED = "order_rejected"
    ORDER_EXPIRED = "order_expired"


class OmsSource(StrEnum):
    """Нормализованный upstream source для foundation OMS layer."""

    EXECUTION = "execution"


class OmsQueryScope(StrEnum):
    """Нормализованный scope query/state surface для OMS."""

    ACTIVE = "active"
    HISTORICAL = "historical"
    ALL = "all"


@dataclass(slots=True, frozen=True)
class OmsValidity:
    """Typed semantics готовности OMS context или OMS order-state."""

    status: OmsValidityStatus
    observed_inputs: int
    required_inputs: int
    missing_inputs: tuple[str, ...] = ()
    invalid_reason: str | None = None

    @property
    def is_valid(self) -> bool:
        """Проверить, готов ли контракт к production-использованию."""
        return self.status == OmsValidityStatus.VALID

    @property
    def is_warming(self) -> bool:
        """Проверить, находится ли контракт в warming-state."""
        return self.status == OmsValidityStatus.WARMING

    @property
    def missing_inputs_count(self) -> int:
        """Вернуть число недостающих inputs."""
        return len(self.missing_inputs)

    @property
    def readiness_ratio(self) -> Decimal:
        """Вернуть нормированную readiness-оценку от 0 до 1."""
        if self.required_inputs <= 0:
            return Decimal("1")
        ratio = Decimal(self.observed_inputs) / Decimal(self.required_inputs)
        if ratio <= 0:
            return Decimal("0")
        if ratio >= 1:
            return Decimal("1")
        return ratio.quantize(Decimal("0.0001"))


@dataclass(slots=True, frozen=True)
class OmsFreshness:
    """Freshness semantics OMS order-state."""

    generated_at: datetime
    expires_at: datetime | None = None

    @property
    def has_structurally_valid_expiry_window(self) -> bool:
        """Проверить только структурную корректность expiry window."""
        return self.expires_at is None or self.expires_at >= self.generated_at

    def is_expired_at(self, reference_time: datetime) -> bool:
        """Определить, истёк ли order-state относительно reference time."""
        return self.expires_at is not None and reference_time >= self.expires_at


@dataclass(slots=True, frozen=True)
class OmsContext:
    """
    Typed context OMS layer поверх execution truth.

    OMS layer здесь выступает только consumer-ом `ExecutionOrderIntent`.
    """

    oms_name: str
    contour_name: str
    symbol: str
    exchange: str
    timeframe: MarketDataTimeframe
    observed_at: datetime
    source: OmsSource
    intent: ExecutionOrderIntent
    validity: OmsValidity
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Проверить базовые structural invariants OMS context."""
        if self.source != OmsSource.EXECUTION:
            raise ValueError("OmsContext source должен быть EXECUTION")
        if self.symbol != self.intent.symbol:
            raise ValueError("OmsContext symbol должен совпадать с intent symbol")
        if self.exchange != self.intent.exchange:
            raise ValueError("OmsContext exchange должен совпадать с intent exchange")
        if self.timeframe != self.intent.timeframe:
            raise ValueError("OmsContext timeframe должен совпадать с intent timeframe")
        if self.validity.is_valid and not self.intent.is_executable:
            raise ValueError("VALID OmsContext требует executable execution intent")


@dataclass(slots=True, frozen=True)
class OmsOrderLocator:
    """Query-state identifiers для active / historical order truth."""

    oms_order_id: UUID
    originating_intent_id: UUID | None
    symbol: str
    exchange: str
    timeframe: MarketDataTimeframe
    query_scope: OmsQueryScope = OmsQueryScope.ACTIVE


@dataclass(slots=True, frozen=True)
class OmsOrderRecord:
    """
    Typed centralized order-state contract для Phase 16 foundation.

    Контракт intentionally не включает:
    - liquidation semantics;
    - notifications / approval workflow;
    - broader ops platform;
    - smart-routing / advanced execution ownership.
    """

    oms_order_id: UUID
    contour_name: str
    oms_name: str
    symbol: str
    exchange: str
    timeframe: MarketDataTimeframe
    source: OmsSource
    freshness: OmsFreshness
    validity: OmsValidity
    lifecycle_status: OmsLifecycleStatus
    originating_intent_id: UUID | None
    locator: OmsOrderLocator
    client_order_id: str | None = None
    external_order_id: str | None = None
    reason_code: OmsReasonCode | None = None
    state_version: int = 1
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Проверить базовые structural invariants OMS record."""
        if not self.freshness.has_structurally_valid_expiry_window:
            raise ValueError("OMS order-state требует expires_at >= generated_at")
        if self.source != OmsSource.EXECUTION:
            raise ValueError("OMS order-state source должен быть EXECUTION")
        if self.state_version <= 0:
            raise ValueError("state_version должен быть положительным")
        if self.originating_intent_id is None:
            raise ValueError("OMS order-state обязан ссылаться на originating_intent_id")
        if self.locator.oms_order_id != self.oms_order_id:
            raise ValueError("OmsOrderLocator oms_order_id должен совпадать с oms_order_id")
        if self.locator.originating_intent_id != self.originating_intent_id:
            raise ValueError(
                "OmsOrderLocator originating_intent_id должен совпадать с originating_intent_id"
            )
        if self.locator.symbol != self.symbol:
            raise ValueError("OmsOrderLocator symbol должен совпадать с symbol")
        if self.locator.exchange != self.exchange:
            raise ValueError("OmsOrderLocator exchange должен совпадать с exchange")
        if self.locator.timeframe != self.timeframe:
            raise ValueError("OmsOrderLocator timeframe должен совпадать с timeframe")

    @property
    def is_active(self) -> bool:
        """Проверить, относится ли order-state к active registry truth."""
        return self.lifecycle_status in {
            OmsLifecycleStatus.REGISTERED,
            OmsLifecycleStatus.SUBMITTED,
            OmsLifecycleStatus.ACCEPTED,
            OmsLifecycleStatus.PARTIALLY_FILLED,
        }

    @property
    def is_terminal(self) -> bool:
        """Проверить, относится ли order-state к historical / terminal truth."""
        return self.lifecycle_status in {
            OmsLifecycleStatus.FILLED,
            OmsLifecycleStatus.CANCELLED,
            OmsLifecycleStatus.REJECTED,
            OmsLifecycleStatus.EXPIRED,
        }

    @classmethod
    def registered(
        cls,
        *,
        contour_name: str,
        oms_name: str,
        symbol: str,
        exchange: str,
        timeframe: MarketDataTimeframe,
        freshness: OmsFreshness,
        validity: OmsValidity,
        originating_intent_id: UUID,
        client_order_id: str | None = None,
        external_order_id: str | None = None,
        reason_code: OmsReasonCode | None = OmsReasonCode.ORDER_REGISTERED,
        query_scope: OmsQueryScope = OmsQueryScope.ACTIVE,
        metadata: dict[str, object] | None = None,
    ) -> OmsOrderRecord:
        """Построить новый OMS record с автоматически сгенерированным ID."""
        oms_order_id = uuid4()
        return cls(
            oms_order_id=oms_order_id,
            contour_name=contour_name,
            oms_name=oms_name,
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
            source=OmsSource.EXECUTION,
            freshness=freshness,
            validity=validity,
            lifecycle_status=OmsLifecycleStatus.REGISTERED,
            originating_intent_id=originating_intent_id,
            locator=OmsOrderLocator(
                oms_order_id=oms_order_id,
                originating_intent_id=originating_intent_id,
                symbol=symbol,
                exchange=exchange,
                timeframe=timeframe,
                query_scope=query_scope,
            ),
            client_order_id=client_order_id,
            external_order_id=external_order_id,
            reason_code=reason_code,
            metadata={} if metadata is None else metadata.copy(),
        )


__all__ = [
    "OmsContext",
    "OmsFreshness",
    "OmsLifecycleStatus",
    "OmsOrderLocator",
    "OmsOrderRecord",
    "OmsQueryScope",
    "OmsReasonCode",
    "OmsSource",
    "OmsValidity",
    "OmsValidityStatus",
]

"""
Contract-first модели Phase 8 для signal layer.

Этот модуль фиксирует минимальный foundation scope:
- typed signal validity / readiness semantics;
- typed signal context contract;
- typed signal output contract;
- базовые invariants signal layer без strategy/orchestration логики.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from datetime import datetime

    from cryptotechnolog.analysis import RiskDerivedInputsSnapshot
    from cryptotechnolog.intelligence import DeryaAssessment
    from cryptotechnolog.market_data import (
        MarketDataTimeframe,
        OHLCVBarContract,
        OrderBookSnapshotContract,
    )


class SignalDirection(StrEnum):
    """Направление signal output."""

    BUY = "BUY"
    SELL = "SELL"


class SignalStatus(StrEnum):
    """Lifecycle-состояние signal output."""

    CANDIDATE = "candidate"
    ACTIVE = "active"
    SUPPRESSED = "suppressed"
    INVALIDATED = "invalidated"
    EXPIRED = "expired"


class SignalValidityStatus(StrEnum):
    """Состояние готовности signal output или signal context."""

    VALID = "valid"
    WARMING = "warming"
    INVALID = "invalid"


class SignalReasonCode(StrEnum):
    """Узкие reason semantics для foundation signal layer."""

    CONTEXT_READY = "context_ready"
    CONTEXT_INCOMPLETE = "context_incomplete"
    SIGNAL_RULE_BLOCKED = "signal_rule_blocked"
    SIGNAL_INVALIDATED = "signal_invalidated"
    SIGNAL_EXPIRED = "signal_expired"


@dataclass(slots=True, frozen=True)
class SignalValidity:
    """Typed semantics готовности signal output или signal context."""

    status: SignalValidityStatus
    observed_inputs: int
    required_inputs: int
    missing_inputs: tuple[str, ...] = ()
    invalid_reason: str | None = None

    @property
    def is_valid(self) -> bool:
        """Проверить, готов ли контракт к production-использованию."""
        return self.status == SignalValidityStatus.VALID

    @property
    def is_warming(self) -> bool:
        """Проверить, находится ли контракт в warming-state."""
        return self.status == SignalValidityStatus.WARMING

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
class SignalFreshness:
    """Freshness semantics signal snapshot."""

    generated_at: datetime
    expires_at: datetime | None = None

    @property
    def has_structurally_valid_expiry_window(self) -> bool:
        """
        Проверить только структурную корректность expiry window.

        Это не runtime-temporal truth:
        метод не отвечает на вопрос, истёк ли сигнал "сейчас",
        а только проверяет, что `expires_at` не раньше `generated_at`.
        """
        return self.expires_at is None or self.expires_at >= self.generated_at

    def is_expired_at(self, reference_time: datetime) -> bool:
        """
        Определить, истёк ли сигнал относительно явного reference time.

        Runtime-слой обязан передавать сюда собственный временной контекст,
        вместо неявной зависимости от глобального времени внутри dataclass.
        """
        return self.expires_at is not None and reference_time >= self.expires_at


@dataclass(slots=True, frozen=True)
class SignalContext:
    """
    Typed context signal layer поверх существующих truth layers.

    Signal layer здесь выступает только consumer-ом:
    - raw market data;
    - shared analysis truth;
    - intelligence truth.
    """

    symbol: str
    exchange: str
    timeframe: MarketDataTimeframe
    observed_at: datetime
    bar: OHLCVBarContract
    orderbook: OrderBookSnapshotContract | None
    derived_inputs: RiskDerivedInputsSnapshot | None
    derya: DeryaAssessment | None
    validity: SignalValidity
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class SignalSnapshot:
    """
    Typed signal output contract для Phase 8 foundation.

    Контракт intentionally не включает:
    - portfolio-level orchestration;
    - opportunity/meta semantics;
    - execution lifecycle beyond signal foundation.
    """

    signal_id: UUID
    contour_name: str
    symbol: str
    exchange: str
    timeframe: MarketDataTimeframe
    freshness: SignalFreshness
    validity: SignalValidity
    status: SignalStatus
    direction: SignalDirection | None = None
    confidence: Decimal | None = None
    entry_price: Decimal | None = None
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None
    reason_code: SignalReasonCode | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Проверить базовые structural invariants signal output."""
        if not self.freshness.has_structurally_valid_expiry_window:
            raise ValueError("Signal output требует expires_at >= generated_at")
        if self.status == SignalStatus.ACTIVE and not self.validity.is_valid:
            raise ValueError("ACTIVE сигнал требует validity=VALID")
        if self.status == SignalStatus.ACTIVE and self.direction is None:
            raise ValueError("ACTIVE сигнал обязан иметь direction")
        if (
            self.status in {SignalStatus.EXPIRED, SignalStatus.INVALIDATED}
            and self.validity.is_valid
        ):
            raise ValueError("EXPIRED/INVALIDATED сигнал не может иметь validity=VALID")

        prices = (self.entry_price, self.stop_loss, self.take_profit)
        if any(price is not None for price in prices):
            if not all(price is not None for price in prices):
                raise ValueError("Signal output с ценами обязан содержать entry/stop/take_profit")
            if self.direction is None:
                raise ValueError("Signal output с ценами обязан иметь direction")
            entry_price = self.entry_price
            stop_loss = self.stop_loss
            take_profit = self.take_profit
            assert entry_price is not None
            assert stop_loss is not None
            assert take_profit is not None
            if entry_price <= 0 or stop_loss <= 0 or take_profit <= 0:
                raise ValueError("Signal output не допускает неположительные цены")
            if self.direction == SignalDirection.BUY and not (
                stop_loss < entry_price < take_profit
            ):
                raise ValueError("BUY сигнал требует stop_loss < entry_price < take_profit")
            if self.direction == SignalDirection.SELL and not (
                take_profit < entry_price < stop_loss
            ):
                raise ValueError("SELL сигнал требует take_profit < entry_price < stop_loss")

    @property
    def is_actionable(self) -> bool:
        """Проверить, является ли сигнал actionable для следующего consumer-а."""
        return self.validity.is_valid and self.status == SignalStatus.ACTIVE

    @classmethod
    def candidate(
        cls,
        *,
        contour_name: str,
        symbol: str,
        exchange: str,
        timeframe: MarketDataTimeframe,
        freshness: SignalFreshness,
        validity: SignalValidity,
        direction: SignalDirection | None = None,
        confidence: Decimal | None = None,
        entry_price: Decimal | None = None,
        stop_loss: Decimal | None = None,
        take_profit: Decimal | None = None,
        reason_code: SignalReasonCode | None = None,
        metadata: dict[str, object] | None = None,
    ) -> SignalSnapshot:
        """Построить новый signal snapshot с автоматически сгенерированным ID."""
        return cls(
            signal_id=uuid4(),
            contour_name=contour_name,
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
            freshness=freshness,
            validity=validity,
            status=SignalStatus.CANDIDATE if not validity.is_valid else SignalStatus.ACTIVE,
            direction=direction,
            confidence=confidence,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            reason_code=reason_code,
            metadata={} if metadata is None else metadata.copy(),
        )


__all__ = [
    "SignalContext",
    "SignalDirection",
    "SignalFreshness",
    "SignalReasonCode",
    "SignalSnapshot",
    "SignalStatus",
    "SignalValidity",
    "SignalValidityStatus",
]

"""
Contract-first модели Phase 9 для strategy layer.

Этот модуль фиксирует минимальный foundation scope:
- typed strategy validity / readiness semantics;
- typed strategy context contract;
- typed strategy action candidate contract;
- базовые invariants strategy layer без portfolio/orchestration логики.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from datetime import datetime

    from cryptotechnolog.market_data import MarketDataTimeframe
    from cryptotechnolog.signals import SignalSnapshot


class StrategyDirection(StrEnum):
    """Направление strategy action candidate."""

    LONG = "LONG"
    SHORT = "SHORT"


class StrategyStatus(StrEnum):
    """Lifecycle-состояние strategy candidate."""

    CANDIDATE = "candidate"
    ACTIONABLE = "actionable"
    SUPPRESSED = "suppressed"
    INVALIDATED = "invalidated"
    EXPIRED = "expired"


class StrategyValidityStatus(StrEnum):
    """Состояние готовности strategy context или strategy candidate."""

    VALID = "valid"
    WARMING = "warming"
    INVALID = "invalid"


class StrategyReasonCode(StrEnum):
    """Узкие reason semantics для foundation strategy layer."""

    CONTEXT_READY = "context_ready"
    CONTEXT_INCOMPLETE = "context_incomplete"
    SIGNAL_NOT_ACTIONABLE = "signal_not_actionable"
    STRATEGY_RULE_BLOCKED = "strategy_rule_blocked"
    STRATEGY_INVALIDATED = "strategy_invalidated"
    STRATEGY_EXPIRED = "strategy_expired"


@dataclass(slots=True, frozen=True)
class StrategyValidity:
    """Typed semantics готовности strategy context или strategy candidate."""

    status: StrategyValidityStatus
    observed_inputs: int
    required_inputs: int
    missing_inputs: tuple[str, ...] = ()
    invalid_reason: str | None = None

    @property
    def is_valid(self) -> bool:
        """Проверить, готов ли контракт к production-использованию."""
        return self.status == StrategyValidityStatus.VALID

    @property
    def is_warming(self) -> bool:
        """Проверить, находится ли контракт в warming-state."""
        return self.status == StrategyValidityStatus.WARMING

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
class StrategyFreshness:
    """Freshness semantics strategy candidate."""

    generated_at: datetime
    expires_at: datetime | None = None

    @property
    def has_structurally_valid_expiry_window(self) -> bool:
        """
        Проверить только структурную корректность expiry window.

        Это не runtime-temporal truth:
        метод не отвечает на вопрос, истёк ли strategy candidate "сейчас",
        а только проверяет, что `expires_at` не раньше `generated_at`.
        """
        return self.expires_at is None or self.expires_at >= self.generated_at

    def is_expired_at(self, reference_time: datetime) -> bool:
        """
        Определить, истёк ли strategy candidate относительно reference time.

        Runtime-слой обязан передавать сюда собственный временной контекст.
        """
        return self.expires_at is not None and reference_time >= self.expires_at


@dataclass(slots=True, frozen=True)
class StrategyContext:
    """
    Typed context strategy layer поверх signal truth.

    Strategy layer здесь выступает только consumer-ом `SignalSnapshot`.
    """

    strategy_name: str
    contour_name: str
    symbol: str
    exchange: str
    timeframe: MarketDataTimeframe
    observed_at: datetime
    signal: SignalSnapshot
    validity: StrategyValidity
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Проверить базовые structural invariants strategy context."""
        if self.symbol != self.signal.symbol:
            raise ValueError("StrategyContext symbol должен совпадать с signal symbol")
        if self.exchange != self.signal.exchange:
            raise ValueError("StrategyContext exchange должен совпадать с signal exchange")
        if self.timeframe != self.signal.timeframe:
            raise ValueError("StrategyContext timeframe должен совпадать с signal timeframe")
        if self.validity.is_valid and not self.signal.is_actionable:
            raise ValueError("VALID StrategyContext требует actionable signal")


@dataclass(slots=True, frozen=True)
class StrategyActionCandidate:
    """
    Typed strategy output contract для Phase 9 foundation.

    Контракт intentionally не включает:
    - portfolio governance;
    - execution lifecycle;
    - multi-strategy orchestration;
    - opportunity/meta semantics.
    """

    candidate_id: UUID
    contour_name: str
    strategy_name: str
    symbol: str
    exchange: str
    timeframe: MarketDataTimeframe
    freshness: StrategyFreshness
    validity: StrategyValidity
    status: StrategyStatus
    direction: StrategyDirection | None = None
    originating_signal_id: UUID | None = None
    confidence: Decimal | None = None
    reason_code: StrategyReasonCode | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Проверить базовые structural invariants strategy output."""
        if not self.freshness.has_structurally_valid_expiry_window:
            raise ValueError("Strategy output требует expires_at >= generated_at")
        if self.status == StrategyStatus.ACTIONABLE and not self.validity.is_valid:
            raise ValueError("ACTIONABLE strategy candidate требует validity=VALID")
        if self.status == StrategyStatus.ACTIONABLE and self.direction is None:
            raise ValueError("ACTIONABLE strategy candidate обязан иметь direction")
        if self.status == StrategyStatus.ACTIONABLE and self.originating_signal_id is None:
            raise ValueError("ACTIONABLE strategy candidate обязан ссылаться на signal_id")
        if (
            self.status in {StrategyStatus.EXPIRED, StrategyStatus.INVALIDATED}
            and self.validity.is_valid
        ):
            raise ValueError("EXPIRED/INVALIDATED strategy candidate не может иметь validity=VALID")

    @property
    def is_actionable(self) -> bool:
        """Проверить, является ли strategy candidate actionable для следующего consumer-а."""
        return self.validity.is_valid and self.status == StrategyStatus.ACTIONABLE

    @classmethod
    def candidate(
        cls,
        *,
        contour_name: str,
        strategy_name: str,
        symbol: str,
        exchange: str,
        timeframe: MarketDataTimeframe,
        freshness: StrategyFreshness,
        validity: StrategyValidity,
        direction: StrategyDirection | None = None,
        originating_signal_id: UUID | None = None,
        confidence: Decimal | None = None,
        reason_code: StrategyReasonCode | None = None,
        metadata: dict[str, object] | None = None,
    ) -> StrategyActionCandidate:
        """Построить новый strategy action candidate с автоматически сгенерированным ID."""
        return cls(
            candidate_id=uuid4(),
            contour_name=contour_name,
            strategy_name=strategy_name,
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
            freshness=freshness,
            validity=validity,
            status=(StrategyStatus.ACTIONABLE if validity.is_valid else StrategyStatus.CANDIDATE),
            direction=direction,
            originating_signal_id=originating_signal_id,
            confidence=confidence,
            reason_code=reason_code,
            metadata={} if metadata is None else metadata.copy(),
        )


__all__ = [
    "StrategyActionCandidate",
    "StrategyContext",
    "StrategyDirection",
    "StrategyFreshness",
    "StrategyReasonCode",
    "StrategyStatus",
    "StrategyValidity",
    "StrategyValidityStatus",
]

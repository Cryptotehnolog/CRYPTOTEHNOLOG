"""
Contract-first модели Phase 10 для execution layer.

Этот модуль фиксирует минимальный foundation scope:
- typed execution validity / readiness semantics;
- typed execution context contract;
- typed execution request / order-intent contract;
- базовые invariants execution layer без OMS / routing / portfolio логики.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from cryptotechnolog.strategy import StrategyDirection

if TYPE_CHECKING:
    from datetime import datetime

    from cryptotechnolog.market_data import MarketDataTimeframe
    from cryptotechnolog.strategy import StrategyActionCandidate


class ExecutionDirection(StrEnum):
    """Направление минимального execution intent."""

    BUY = "BUY"
    SELL = "SELL"


class ExecutionStatus(StrEnum):
    """Lifecycle-состояние execution order-intent."""

    CANDIDATE = "candidate"
    EXECUTABLE = "executable"
    SUPPRESSED = "suppressed"
    INVALIDATED = "invalidated"
    EXPIRED = "expired"


class ExecutionValidityStatus(StrEnum):
    """Состояние готовности execution context или execution intent."""

    VALID = "valid"
    WARMING = "warming"
    INVALID = "invalid"


class ExecutionReasonCode(StrEnum):
    """Узкие reason semantics для foundation execution layer."""

    CONTEXT_READY = "context_ready"
    CONTEXT_INCOMPLETE = "context_incomplete"
    STRATEGY_NOT_ACTIONABLE = "strategy_not_actionable"
    EXECUTION_RULE_BLOCKED = "execution_rule_blocked"
    EXECUTION_INVALIDATED = "execution_invalidated"
    EXECUTION_EXPIRED = "execution_expired"


@dataclass(slots=True, frozen=True)
class ExecutionValidity:
    """Typed semantics готовности execution context или execution intent."""

    status: ExecutionValidityStatus
    observed_inputs: int
    required_inputs: int
    missing_inputs: tuple[str, ...] = ()
    invalid_reason: str | None = None

    @property
    def is_valid(self) -> bool:
        """Проверить, готов ли контракт к production-использованию."""
        return self.status == ExecutionValidityStatus.VALID

    @property
    def is_warming(self) -> bool:
        """Проверить, находится ли контракт в warming-state."""
        return self.status == ExecutionValidityStatus.WARMING

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
class ExecutionFreshness:
    """Freshness semantics execution intent."""

    generated_at: datetime
    expires_at: datetime | None = None

    @property
    def has_structurally_valid_expiry_window(self) -> bool:
        """
        Проверить только структурную корректность expiry window.

        Это не runtime-temporal truth:
        метод не отвечает на вопрос, истёк ли execution intent "сейчас",
        а только проверяет, что `expires_at` не раньше `generated_at`.
        """
        return self.expires_at is None or self.expires_at >= self.generated_at

    def is_expired_at(self, reference_time: datetime) -> bool:
        """
        Определить, истёк ли execution intent относительно reference time.

        Runtime-слой обязан передавать сюда собственный временной контекст.
        """
        return self.expires_at is not None and reference_time >= self.expires_at


@dataclass(slots=True, frozen=True)
class ExecutionContext:
    """
    Typed context execution layer поверх strategy truth.

    Execution layer здесь выступает только consumer-ом `StrategyActionCandidate`.
    """

    execution_name: str
    contour_name: str
    symbol: str
    exchange: str
    timeframe: MarketDataTimeframe
    observed_at: datetime
    candidate: StrategyActionCandidate
    validity: ExecutionValidity
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Проверить базовые structural invariants execution context."""
        if self.symbol != self.candidate.symbol:
            raise ValueError("ExecutionContext symbol должен совпадать с candidate symbol")
        if self.exchange != self.candidate.exchange:
            raise ValueError("ExecutionContext exchange должен совпадать с candidate exchange")
        if self.timeframe != self.candidate.timeframe:
            raise ValueError("ExecutionContext timeframe должен совпадать с candidate timeframe")
        if self.validity.is_valid and not self.candidate.is_actionable:
            raise ValueError("VALID ExecutionContext требует actionable strategy candidate")


@dataclass(slots=True, frozen=True)
class ExecutionOrderIntent:
    """
    Typed execution output contract для Phase 10 foundation.

    Контракт intentionally не включает:
    - OMS lifecycle;
    - smart routing;
    - exchange-specific semantics;
    - portfolio governance.
    """

    intent_id: UUID
    contour_name: str
    execution_name: str
    symbol: str
    exchange: str
    timeframe: MarketDataTimeframe
    freshness: ExecutionFreshness
    validity: ExecutionValidity
    status: ExecutionStatus
    direction: ExecutionDirection | None = None
    originating_candidate_id: UUID | None = None
    confidence: Decimal | None = None
    reason_code: ExecutionReasonCode | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Проверить базовые structural invariants execution output."""
        if not self.freshness.has_structurally_valid_expiry_window:
            raise ValueError("Execution output требует expires_at >= generated_at")
        if self.status == ExecutionStatus.EXECUTABLE and not self.validity.is_valid:
            raise ValueError("EXECUTABLE execution intent требует validity=VALID")
        if self.status == ExecutionStatus.EXECUTABLE and self.direction is None:
            raise ValueError("EXECUTABLE execution intent обязан иметь direction")
        if self.status == ExecutionStatus.EXECUTABLE and self.originating_candidate_id is None:
            raise ValueError("EXECUTABLE execution intent обязан ссылаться на candidate_id")
        if (
            self.status in {ExecutionStatus.EXPIRED, ExecutionStatus.INVALIDATED}
            and self.validity.is_valid
        ):
            raise ValueError("EXPIRED/INVALIDATED execution intent не может иметь validity=VALID")

    @property
    def is_executable(self) -> bool:
        """Проверить, является ли execution intent executable для следующего consumer-а."""
        return self.validity.is_valid and self.status == ExecutionStatus.EXECUTABLE

    @classmethod
    def candidate(
        cls,
        *,
        contour_name: str,
        execution_name: str,
        symbol: str,
        exchange: str,
        timeframe: MarketDataTimeframe,
        freshness: ExecutionFreshness,
        validity: ExecutionValidity,
        direction: ExecutionDirection | None = None,
        originating_candidate_id: UUID | None = None,
        confidence: Decimal | None = None,
        reason_code: ExecutionReasonCode | None = None,
        metadata: dict[str, object] | None = None,
    ) -> ExecutionOrderIntent:
        """Построить новый execution intent с автоматически сгенерированным ID."""
        return cls(
            intent_id=uuid4(),
            contour_name=contour_name,
            execution_name=execution_name,
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
            freshness=freshness,
            validity=validity,
            status=(ExecutionStatus.EXECUTABLE if validity.is_valid else ExecutionStatus.CANDIDATE),
            direction=direction,
            originating_candidate_id=originating_candidate_id,
            confidence=confidence,
            reason_code=reason_code,
            metadata={} if metadata is None else metadata.copy(),
        )

    @classmethod
    def direction_from_strategy(
        cls,
        strategy_direction: StrategyDirection,
    ) -> ExecutionDirection:
        """Нормализовать направление execution intent из strategy direction."""
        if strategy_direction == StrategyDirection.LONG:
            return ExecutionDirection.BUY
        return ExecutionDirection.SELL


__all__ = [
    "ExecutionContext",
    "ExecutionDirection",
    "ExecutionFreshness",
    "ExecutionOrderIntent",
    "ExecutionReasonCode",
    "ExecutionStatus",
    "ExecutionValidity",
    "ExecutionValidityStatus",
]

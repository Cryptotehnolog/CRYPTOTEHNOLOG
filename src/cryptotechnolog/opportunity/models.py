"""
Contract-first модели Phase 11 для opportunity / selection layer.

Этот модуль фиксирует минимальный foundation scope:
- typed opportunity validity / readiness semantics;
- typed opportunity context contract;
- typed selection candidate contract;
- базовые invariants selection layer без OMS / meta / orchestration логики.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from cryptotechnolog.execution import ExecutionDirection

if TYPE_CHECKING:
    from datetime import datetime

    from cryptotechnolog.execution import ExecutionOrderIntent
    from cryptotechnolog.market_data import MarketDataTimeframe


class OpportunityDirection(StrEnum):
    """Направление selection candidate."""

    LONG = "LONG"
    SHORT = "SHORT"


class OpportunityStatus(StrEnum):
    """Lifecycle-состояние selection candidate."""

    CANDIDATE = "candidate"
    SELECTED = "selected"
    SUPPRESSED = "suppressed"
    INVALIDATED = "invalidated"
    EXPIRED = "expired"


class OpportunityValidityStatus(StrEnum):
    """Состояние готовности opportunity context или selection candidate."""

    VALID = "valid"
    WARMING = "warming"
    INVALID = "invalid"


class OpportunityReasonCode(StrEnum):
    """Узкие reason semantics для foundation selection layer."""

    CONTEXT_READY = "context_ready"
    CONTEXT_INCOMPLETE = "context_incomplete"
    EXECUTION_NOT_EXECUTABLE = "execution_not_executable"
    SELECTION_RULE_BLOCKED = "selection_rule_blocked"
    OPPORTUNITY_INVALIDATED = "opportunity_invalidated"
    OPPORTUNITY_EXPIRED = "opportunity_expired"


class OpportunitySource(StrEnum):
    """Нормализованный upstream source для foundation selection layer."""

    EXECUTION_INTENT = "execution_intent"


@dataclass(slots=True, frozen=True)
class OpportunityValidity:
    """Typed semantics готовности opportunity context или selection candidate."""

    status: OpportunityValidityStatus
    observed_inputs: int
    required_inputs: int
    missing_inputs: tuple[str, ...] = ()
    invalid_reason: str | None = None

    @property
    def is_valid(self) -> bool:
        """Проверить, готов ли контракт к production-использованию."""
        return self.status == OpportunityValidityStatus.VALID

    @property
    def is_warming(self) -> bool:
        """Проверить, находится ли контракт в warming-state."""
        return self.status == OpportunityValidityStatus.WARMING

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
class OpportunityFreshness:
    """Freshness semantics selection candidate."""

    generated_at: datetime
    expires_at: datetime | None = None

    @property
    def has_structurally_valid_expiry_window(self) -> bool:
        """
        Проверить только структурную корректность expiry window.

        Это не runtime-temporal truth:
        метод не отвечает на вопрос, истёк ли selection candidate "сейчас",
        а только проверяет, что `expires_at` не раньше `generated_at`.
        """
        return self.expires_at is None or self.expires_at >= self.generated_at

    def is_expired_at(self, reference_time: datetime) -> bool:
        """
        Определить, истёк ли selection candidate относительно reference time.

        Runtime-слой обязан передавать сюда собственный временной контекст.
        """
        return self.expires_at is not None and reference_time >= self.expires_at


@dataclass(slots=True, frozen=True)
class OpportunityContext:
    """
    Typed context selection layer поверх execution truth.

    Opportunity layer здесь выступает только consumer-ом `ExecutionOrderIntent`.
    """

    selection_name: str
    contour_name: str
    symbol: str
    exchange: str
    timeframe: MarketDataTimeframe
    observed_at: datetime
    source: OpportunitySource
    intent: ExecutionOrderIntent
    validity: OpportunityValidity
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Проверить базовые structural invariants selection context."""
        if self.source != OpportunitySource.EXECUTION_INTENT:
            raise ValueError("OpportunityContext source должен быть EXECUTION_INTENT")
        if self.symbol != self.intent.symbol:
            raise ValueError("OpportunityContext symbol должен совпадать с intent symbol")
        if self.exchange != self.intent.exchange:
            raise ValueError("OpportunityContext exchange должен совпадать с intent exchange")
        if self.timeframe != self.intent.timeframe:
            raise ValueError("OpportunityContext timeframe должен совпадать с intent timeframe")
        if self.validity.is_valid and not self.intent.is_executable:
            raise ValueError("VALID OpportunityContext требует executable intent")


@dataclass(slots=True, frozen=True)
class OpportunitySelectionCandidate:
    """
    Typed selection output contract для Phase 11 foundation.

    Контракт intentionally не включает:
    - OMS lifecycle;
    - meta / orchestration semantics;
    - portfolio governance;
    - advanced execution coordination.
    """

    selection_id: UUID
    contour_name: str
    selection_name: str
    symbol: str
    exchange: str
    timeframe: MarketDataTimeframe
    source: OpportunitySource
    freshness: OpportunityFreshness
    validity: OpportunityValidity
    status: OpportunityStatus
    direction: OpportunityDirection | None = None
    originating_intent_id: UUID | None = None
    confidence: Decimal | None = None
    priority_score: Decimal | None = None
    reason_code: OpportunityReasonCode | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Проверить базовые structural invariants selection output."""
        if not self.freshness.has_structurally_valid_expiry_window:
            raise ValueError("Opportunity output требует expires_at >= generated_at")
        if self.status == OpportunityStatus.SELECTED and not self.validity.is_valid:
            raise ValueError("SELECTED opportunity candidate требует validity=VALID")
        if self.status == OpportunityStatus.SELECTED and self.direction is None:
            raise ValueError("SELECTED opportunity candidate обязан иметь direction")
        if self.status == OpportunityStatus.SELECTED and self.originating_intent_id is None:
            raise ValueError("SELECTED opportunity candidate обязан ссылаться на intent_id")
        if self.priority_score is not None and self.priority_score < Decimal("0"):
            raise ValueError("priority_score не может быть отрицательным")
        if (
            self.status in {OpportunityStatus.EXPIRED, OpportunityStatus.INVALIDATED}
            and self.validity.is_valid
        ):
            raise ValueError(
                "EXPIRED/INVALIDATED selection candidate не может иметь validity=VALID"
            )

    @property
    def is_selected(self) -> bool:
        """Проверить, выбран ли candidate для следующего consumer-а."""
        return self.validity.is_valid and self.status == OpportunityStatus.SELECTED

    @classmethod
    def candidate(
        cls,
        *,
        contour_name: str,
        selection_name: str,
        symbol: str,
        exchange: str,
        timeframe: MarketDataTimeframe,
        source: OpportunitySource,
        freshness: OpportunityFreshness,
        validity: OpportunityValidity,
        direction: OpportunityDirection | None = None,
        originating_intent_id: UUID | None = None,
        confidence: Decimal | None = None,
        priority_score: Decimal | None = None,
        reason_code: OpportunityReasonCode | None = None,
        metadata: dict[str, object] | None = None,
    ) -> OpportunitySelectionCandidate:
        """Построить новый selection candidate с автоматически сгенерированным ID."""
        return cls(
            selection_id=uuid4(),
            contour_name=contour_name,
            selection_name=selection_name,
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
            source=source,
            freshness=freshness,
            validity=validity,
            status=(
                OpportunityStatus.SELECTED if validity.is_valid else OpportunityStatus.CANDIDATE
            ),
            direction=direction,
            originating_intent_id=originating_intent_id,
            confidence=confidence,
            priority_score=priority_score,
            reason_code=reason_code,
            metadata={} if metadata is None else metadata.copy(),
        )

    @classmethod
    def direction_from_execution(
        cls,
        execution_direction: ExecutionDirection,
    ) -> OpportunityDirection:
        """Нормализовать направление selection candidate из execution direction."""
        if execution_direction == ExecutionDirection.BUY:
            return OpportunityDirection.LONG
        return OpportunityDirection.SHORT


__all__ = [
    "OpportunityContext",
    "OpportunityDirection",
    "OpportunityFreshness",
    "OpportunityReasonCode",
    "OpportunitySelectionCandidate",
    "OpportunitySource",
    "OpportunityStatus",
    "OpportunityValidity",
    "OpportunityValidityStatus",
]

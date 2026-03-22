"""
Contract-first модели Phase 13 для position-expansion layer.

Этот модуль фиксирует минимальный foundation scope:
- typed position-expansion validity / readiness semantics;
- typed expansion context contract;
- typed add-to-position candidate contract;
- abstain / reject / no-expansion semantics без portfolio / protection / OMS логики.
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
    from cryptotechnolog.orchestration import OrchestrationDecisionCandidate


class ExpansionDirection(StrEnum):
    """Направление add-to-position candidate."""

    LONG = "LONG"
    SHORT = "SHORT"


class ExpansionDecision(StrEnum):
    """Нормализованный decision foundation position-expansion layer."""

    ADD = "add"
    ABSTAIN = "abstain"
    REJECT = "reject"


class ExpansionStatus(StrEnum):
    """Lifecycle-состояние position-expansion candidate."""

    CANDIDATE = "candidate"
    EXPANDABLE = "expandable"
    ABSTAINED = "abstained"
    REJECTED = "rejected"
    INVALIDATED = "invalidated"
    EXPIRED = "expired"


class ExpansionValidityStatus(StrEnum):
    """Состояние готовности expansion context или expansion candidate."""

    VALID = "valid"
    WARMING = "warming"
    INVALID = "invalid"


class ExpansionReasonCode(StrEnum):
    """Узкие reason semantics для foundation position-expansion layer."""

    CONTEXT_READY = "context_ready"
    CONTEXT_INCOMPLETE = "context_incomplete"
    ORCHESTRATION_NOT_FORWARDABLE = "orchestration_not_forwardable"
    EXPANSION_ABSTAINED = "expansion_abstained"
    EXPANSION_REJECTED = "expansion_rejected"
    EXPANSION_INVALIDATED = "expansion_invalidated"
    EXPANSION_EXPIRED = "expansion_expired"


class ExpansionSource(StrEnum):
    """Нормализованный upstream source для foundation position-expansion layer."""

    ORCHESTRATION_DECISION = "orchestration_decision"


@dataclass(slots=True, frozen=True)
class ExpansionValidity:
    """Typed semantics готовности expansion context или expansion candidate."""

    status: ExpansionValidityStatus
    observed_inputs: int
    required_inputs: int
    missing_inputs: tuple[str, ...] = ()
    invalid_reason: str | None = None

    @property
    def is_valid(self) -> bool:
        """Проверить, готов ли контракт к production-использованию."""
        return self.status == ExpansionValidityStatus.VALID

    @property
    def is_warming(self) -> bool:
        """Проверить, находится ли контракт в warming-state."""
        return self.status == ExpansionValidityStatus.WARMING

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
class ExpansionFreshness:
    """Freshness semantics expansion candidate."""

    generated_at: datetime
    expires_at: datetime | None = None

    @property
    def has_structurally_valid_expiry_window(self) -> bool:
        """
        Проверить только структурную корректность expiry window.

        Это не runtime-temporal truth:
        метод не отвечает на вопрос, истёк ли expansion candidate "сейчас",
        а только проверяет, что `expires_at` не раньше `generated_at`.
        """
        return self.expires_at is None or self.expires_at >= self.generated_at

    def is_expired_at(self, reference_time: datetime) -> bool:
        """
        Определить, истёк ли expansion candidate относительно reference time.

        Runtime-слой обязан передавать сюда собственный временной контекст.
        """
        return self.expires_at is not None and reference_time >= self.expires_at


@dataclass(slots=True, frozen=True)
class ExpansionContext:
    """
    Typed context position-expansion layer поверх orchestration truth.

    Position-expansion layer здесь выступает только consumer-ом
    `OrchestrationDecisionCandidate`.
    """

    expansion_name: str
    contour_name: str
    symbol: str
    exchange: str
    timeframe: MarketDataTimeframe
    observed_at: datetime
    source: ExpansionSource
    decision: OrchestrationDecisionCandidate
    validity: ExpansionValidity
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Проверить базовые structural invariants expansion context."""
        if self.source != ExpansionSource.ORCHESTRATION_DECISION:
            raise ValueError("ExpansionContext source должен быть ORCHESTRATION_DECISION")
        if self.symbol != self.decision.symbol:
            raise ValueError("ExpansionContext symbol должен совпадать с decision symbol")
        if self.exchange != self.decision.exchange:
            raise ValueError("ExpansionContext exchange должен совпадать с decision exchange")
        if self.timeframe != self.decision.timeframe:
            raise ValueError("ExpansionContext timeframe должен совпадать с decision timeframe")
        if self.validity.is_valid and not self.decision.is_forwarded:
            raise ValueError("VALID ExpansionContext требует forwarded orchestration decision")


@dataclass(slots=True, frozen=True)
class PositionExpansionCandidate:
    """
    Typed add-to-position output contract для Phase 13 foundation.

    Контракт intentionally не включает:
    - portfolio-wide capital governance;
    - protection / kill switch semantics;
    - OMS lifecycle;
    - broad workflow / manager semantics.
    """

    expansion_id: UUID
    contour_name: str
    expansion_name: str
    symbol: str
    exchange: str
    timeframe: MarketDataTimeframe
    source: ExpansionSource
    freshness: ExpansionFreshness
    validity: ExpansionValidity
    status: ExpansionStatus
    decision: ExpansionDecision
    direction: ExpansionDirection | None = None
    originating_decision_id: UUID | None = None
    confidence: Decimal | None = None
    priority_score: Decimal | None = None
    reason_code: ExpansionReasonCode | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Проверить базовые structural invariants expansion output."""
        if not self.freshness.has_structurally_valid_expiry_window:
            raise ValueError("Expansion output требует expires_at >= generated_at")
        if self.status == ExpansionStatus.EXPANDABLE and self.decision != ExpansionDecision.ADD:
            raise ValueError("EXPANDABLE candidate обязан иметь decision=ADD")
        if self.status == ExpansionStatus.EXPANDABLE and not self.validity.is_valid:
            raise ValueError("EXPANDABLE candidate требует validity=VALID")
        if self.status == ExpansionStatus.EXPANDABLE and self.direction is None:
            raise ValueError("EXPANDABLE candidate обязан иметь direction")
        if self.status == ExpansionStatus.EXPANDABLE and self.originating_decision_id is None:
            raise ValueError("EXPANDABLE candidate обязан ссылаться на decision_id")
        if self.status == ExpansionStatus.ABSTAINED and self.decision != ExpansionDecision.ABSTAIN:
            raise ValueError("ABSTAINED candidate обязан иметь decision=ABSTAIN")
        if self.status == ExpansionStatus.ABSTAINED and self.direction is not None:
            raise ValueError("ABSTAINED candidate не должен иметь direction")
        if self.status == ExpansionStatus.REJECTED and self.decision != ExpansionDecision.REJECT:
            raise ValueError("REJECTED candidate обязан иметь decision=REJECT")
        if self.status == ExpansionStatus.REJECTED and self.direction is not None:
            raise ValueError("REJECTED candidate не должен иметь direction")
        if self.priority_score is not None and self.priority_score < Decimal("0"):
            raise ValueError("priority_score не может быть отрицательным")
        if (
            self.status in {ExpansionStatus.EXPIRED, ExpansionStatus.INVALIDATED}
            and self.validity.is_valid
        ):
            raise ValueError(
                "EXPIRED/INVALIDATED expansion candidate не может иметь validity=VALID"
            )

    @property
    def is_expandable(self) -> bool:
        """Проверить, готов ли candidate к узкому add-to-position path."""
        return (
            self.validity.is_valid
            and self.status == ExpansionStatus.EXPANDABLE
            and self.decision == ExpansionDecision.ADD
        )

    @property
    def is_abstained(self) -> bool:
        """Проверить, выражает ли candidate явный no-expansion abstain."""
        return self.status == ExpansionStatus.ABSTAINED

    @property
    def is_rejected(self) -> bool:
        """Проверить, выражает ли candidate явный no-expansion reject."""
        return self.status == ExpansionStatus.REJECTED

    @classmethod
    def candidate(
        cls,
        *,
        contour_name: str,
        expansion_name: str,
        symbol: str,
        exchange: str,
        timeframe: MarketDataTimeframe,
        source: ExpansionSource,
        freshness: ExpansionFreshness,
        validity: ExpansionValidity,
        decision: ExpansionDecision,
        status: ExpansionStatus = ExpansionStatus.CANDIDATE,
        direction: ExpansionDirection | None = None,
        originating_decision_id: UUID | None = None,
        confidence: Decimal | None = None,
        priority_score: Decimal | None = None,
        reason_code: ExpansionReasonCode | None = None,
        metadata: dict[str, object] | None = None,
    ) -> PositionExpansionCandidate:
        """
        Построить новый expansion candidate с автоматически сгенерированным ID.

        Factory намеренно не выводит lifecycle-status из `validity + decision`.
        Ownership runtime-truth остаётся у runtime следующего шага.
        """
        return cls(
            expansion_id=uuid4(),
            contour_name=contour_name,
            expansion_name=expansion_name,
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
            source=source,
            freshness=freshness,
            validity=validity,
            status=status,
            decision=decision,
            direction=direction,
            originating_decision_id=originating_decision_id,
            confidence=confidence,
            priority_score=priority_score,
            reason_code=reason_code,
            metadata={} if metadata is None else metadata.copy(),
        )


__all__ = [
    "ExpansionContext",
    "ExpansionDecision",
    "ExpansionDirection",
    "ExpansionFreshness",
    "ExpansionReasonCode",
    "ExpansionSource",
    "ExpansionStatus",
    "ExpansionValidity",
    "ExpansionValidityStatus",
    "PositionExpansionCandidate",
]

"""
Contract-first модели Phase 12 для orchestration / meta layer.

Этот модуль фиксирует минимальный foundation scope:
- typed orchestration validity / readiness semantics;
- typed orchestration context contract;
- typed meta-decision / arbitration contract;
- abstain / no-decision semantics без full StrategyManager логики.
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
    from cryptotechnolog.opportunity import (
        OpportunityDirection,
        OpportunitySelectionCandidate,
    )


class OrchestrationDecision(StrEnum):
    """Нормализованный meta-decision foundation orchestration layer."""

    FORWARD = "forward"
    ABSTAIN = "abstain"


class OrchestrationStatus(StrEnum):
    """Lifecycle-состояние orchestration decision candidate."""

    CANDIDATE = "candidate"
    ORCHESTRATED = "orchestrated"
    ABSTAINED = "abstained"
    INVALIDATED = "invalidated"
    EXPIRED = "expired"


class OrchestrationValidityStatus(StrEnum):
    """Состояние готовности orchestration context или meta-decision."""

    VALID = "valid"
    WARMING = "warming"
    INVALID = "invalid"


class OrchestrationReasonCode(StrEnum):
    """Узкие reason semantics для foundation orchestration layer."""

    CONTEXT_READY = "context_ready"
    CONTEXT_INCOMPLETE = "context_incomplete"
    OPPORTUNITY_NOT_SELECTED = "opportunity_not_selected"
    ORCHESTRATION_ABSTAINED = "orchestration_abstained"
    ORCHESTRATION_INVALIDATED = "orchestration_invalidated"
    ORCHESTRATION_EXPIRED = "orchestration_expired"


class OrchestrationSource(StrEnum):
    """Нормализованный upstream source для foundation orchestration layer."""

    OPPORTUNITY_SELECTION = "opportunity_selection"


@dataclass(slots=True, frozen=True)
class OrchestrationValidity:
    """Typed semantics готовности orchestration context или meta-decision."""

    status: OrchestrationValidityStatus
    observed_inputs: int
    required_inputs: int
    missing_inputs: tuple[str, ...] = ()
    invalid_reason: str | None = None

    @property
    def is_valid(self) -> bool:
        """Проверить, готов ли контракт к production-использованию."""
        return self.status == OrchestrationValidityStatus.VALID

    @property
    def is_warming(self) -> bool:
        """Проверить, находится ли контракт в warming-state."""
        return self.status == OrchestrationValidityStatus.WARMING

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
class OrchestrationFreshness:
    """Freshness semantics orchestration decision."""

    generated_at: datetime
    expires_at: datetime | None = None

    @property
    def has_structurally_valid_expiry_window(self) -> bool:
        """
        Проверить только структурную корректность expiry window.

        Это не runtime-temporal truth:
        метод не отвечает на вопрос, истёк ли orchestration decision "сейчас",
        а только проверяет, что `expires_at` не раньше `generated_at`.
        """
        return self.expires_at is None or self.expires_at >= self.generated_at

    def is_expired_at(self, reference_time: datetime) -> bool:
        """
        Определить, истёк ли orchestration decision относительно reference time.

        Runtime-слой обязан передавать сюда собственный временной контекст.
        """
        return self.expires_at is not None and reference_time >= self.expires_at


@dataclass(slots=True, frozen=True)
class OrchestrationContext:
    """
    Typed context orchestration layer поверх opportunity truth.

    Orchestration layer здесь выступает только consumer-ом
    `OpportunitySelectionCandidate`.
    """

    orchestration_name: str
    contour_name: str
    symbol: str
    exchange: str
    timeframe: MarketDataTimeframe
    observed_at: datetime
    source: OrchestrationSource
    selection: OpportunitySelectionCandidate
    validity: OrchestrationValidity
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Проверить базовые structural invariants orchestration context."""
        if self.source != OrchestrationSource.OPPORTUNITY_SELECTION:
            raise ValueError("OrchestrationContext source должен быть OPPORTUNITY_SELECTION")
        if self.symbol != self.selection.symbol:
            raise ValueError("OrchestrationContext symbol должен совпадать с selection symbol")
        if self.exchange != self.selection.exchange:
            raise ValueError("OrchestrationContext exchange должен совпадать с selection exchange")
        if self.timeframe != self.selection.timeframe:
            raise ValueError(
                "OrchestrationContext timeframe должен совпадать с selection timeframe"
            )
        if self.validity.is_valid and not self.selection.is_selected:
            raise ValueError("VALID OrchestrationContext требует selected opportunity")


@dataclass(slots=True, frozen=True)
class OrchestrationDecisionCandidate:
    """
    Typed meta-decision output contract для Phase 12 foundation.

    Контракт intentionally не включает:
    - full StrategyManager semantics;
    - OMS / execution submission;
    - kill switch / protection logic;
    - portfolio / supervisor governance.
    """

    decision_id: UUID
    contour_name: str
    orchestration_name: str
    symbol: str
    exchange: str
    timeframe: MarketDataTimeframe
    source: OrchestrationSource
    freshness: OrchestrationFreshness
    validity: OrchestrationValidity
    status: OrchestrationStatus
    decision: OrchestrationDecision
    direction: OpportunityDirection | None = None
    originating_selection_id: UUID | None = None
    confidence: Decimal | None = None
    priority_score: Decimal | None = None
    reason_code: OrchestrationReasonCode | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Проверить базовые structural invariants orchestration output."""
        if not self.freshness.has_structurally_valid_expiry_window:
            raise ValueError("Orchestration output требует expires_at >= generated_at")
        if (
            self.status == OrchestrationStatus.ORCHESTRATED
            and self.decision != OrchestrationDecision.FORWARD
        ):
            raise ValueError("ORCHESTRATED decision обязан иметь decision=FORWARD")
        if self.status == OrchestrationStatus.ORCHESTRATED and not self.validity.is_valid:
            raise ValueError("ORCHESTRATED decision требует validity=VALID")
        if self.status == OrchestrationStatus.ORCHESTRATED and self.direction is None:
            raise ValueError("ORCHESTRATED decision обязан иметь direction")
        if (
            self.status == OrchestrationStatus.ORCHESTRATED
            and self.originating_selection_id is None
        ):
            raise ValueError("ORCHESTRATED decision обязан ссылаться на selection_id")
        if (
            self.status == OrchestrationStatus.ABSTAINED
            and self.decision != OrchestrationDecision.ABSTAIN
        ):
            raise ValueError("ABSTAINED decision обязан иметь decision=ABSTAIN")
        if self.status == OrchestrationStatus.ABSTAINED and self.direction is not None:
            raise ValueError("ABSTAINED decision не должен иметь direction")
        if self.priority_score is not None and self.priority_score < Decimal("0"):
            raise ValueError("priority_score не может быть отрицательным")
        if (
            self.status in {OrchestrationStatus.EXPIRED, OrchestrationStatus.INVALIDATED}
            and self.validity.is_valid
        ):
            raise ValueError(
                "EXPIRED/INVALIDATED orchestration decision не может иметь validity=VALID"
            )

    @property
    def is_forwarded(self) -> bool:
        """Проверить, форвардится ли decision следующему consumer-у."""
        return (
            self.validity.is_valid
            and self.status == OrchestrationStatus.ORCHESTRATED
            and self.decision == OrchestrationDecision.FORWARD
        )

    @property
    def is_abstained(self) -> bool:
        """Проверить, выражает ли decision явное abstain-состояние."""
        return self.status == OrchestrationStatus.ABSTAINED

    @classmethod
    def candidate(
        cls,
        *,
        contour_name: str,
        orchestration_name: str,
        symbol: str,
        exchange: str,
        timeframe: MarketDataTimeframe,
        source: OrchestrationSource,
        freshness: OrchestrationFreshness,
        validity: OrchestrationValidity,
        status: OrchestrationStatus = OrchestrationStatus.CANDIDATE,
        decision: OrchestrationDecision,
        direction: OpportunityDirection | None = None,
        originating_selection_id: UUID | None = None,
        confidence: Decimal | None = None,
        priority_score: Decimal | None = None,
        reason_code: OrchestrationReasonCode | None = None,
        metadata: dict[str, object] | None = None,
    ) -> OrchestrationDecisionCandidate:
        """
        Построить новый meta-decision candidate с автоматически сгенерированным ID.

        Factory намеренно не выводит lifecycle-status из `validity + decision`.
        Ownership runtime-truth остаётся у orchestration runtime следующего шага.
        """
        return cls(
            decision_id=uuid4(),
            contour_name=contour_name,
            orchestration_name=orchestration_name,
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
            source=source,
            freshness=freshness,
            validity=validity,
            status=status,
            decision=decision,
            direction=direction,
            originating_selection_id=originating_selection_id,
            confidence=confidence,
            priority_score=priority_score,
            reason_code=reason_code,
            metadata={} if metadata is None else metadata.copy(),
        )


__all__ = [
    "OrchestrationContext",
    "OrchestrationDecision",
    "OrchestrationDecisionCandidate",
    "OrchestrationFreshness",
    "OrchestrationReasonCode",
    "OrchestrationSource",
    "OrchestrationStatus",
    "OrchestrationValidity",
    "OrchestrationValidityStatus",
]

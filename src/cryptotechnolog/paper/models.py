"""
Contract-first модели Phase 19 для narrow paper-trading layer.

Этот модуль фиксирует минимальный foundation scope:
- typed paper validity / readiness semantics;
- typed paper context contract поверх existing runtime truths;
- typed rehearsal / simulated-decision candidate contract;
- paper semantics без analytics / reporting / backtesting / dashboard ownership
  и без re-ownership соседних runtime layers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from datetime import datetime

    from cryptotechnolog.manager import ManagerWorkflowCandidate
    from cryptotechnolog.market_data import MarketDataTimeframe
    from cryptotechnolog.oms import OmsOrderRecord
    from cryptotechnolog.validation import ValidationReviewCandidate


class PaperDecision(StrEnum):
    """Нормализованный decision foundation paper layer."""

    REHEARSE = "rehearse"
    ABSTAIN = "abstain"


class PaperStatus(StrEnum):
    """Lifecycle-состояние paper rehearsal candidate."""

    CANDIDATE = "candidate"
    REHEARSED = "rehearsed"
    ABSTAINED = "abstained"
    INVALIDATED = "invalidated"
    EXPIRED = "expired"


class PaperValidityStatus(StrEnum):
    """Состояние готовности paper context или rehearsal candidate."""

    VALID = "valid"
    WARMING = "warming"
    INVALID = "invalid"


class PaperReasonCode(StrEnum):
    """Узкие reason semantics для foundation paper layer."""

    CONTEXT_READY = "context_ready"
    CONTEXT_INCOMPLETE = "context_incomplete"
    MANAGER_NOT_COORDINATED = "manager_not_coordinated"
    VALIDATION_NOT_READY = "validation_not_ready"
    OMS_STATE_MISSING = "oms_state_missing"
    PAPER_REHEARSED = "paper_rehearsed"
    PAPER_ABSTAINED = "paper_abstained"
    PAPER_INVALIDATED = "paper_invalidated"
    PAPER_EXPIRED = "paper_expired"


class PaperSource(StrEnum):
    """Нормализованный upstream source для foundation paper layer."""

    RUNTIME_FOUNDATIONS = "runtime_foundations"


@dataclass(slots=True, frozen=True)
class PaperValidity:
    """Typed semantics готовности paper context или rehearsal candidate."""

    status: PaperValidityStatus
    observed_inputs: int
    required_inputs: int
    missing_inputs: tuple[str, ...] = ()
    invalid_reason: str | None = None

    @property
    def is_valid(self) -> bool:
        """Проверить, готов ли контракт к production-использованию."""
        return self.status == PaperValidityStatus.VALID

    @property
    def is_warming(self) -> bool:
        """Проверить, находится ли контракт в warming-state."""
        return self.status == PaperValidityStatus.WARMING

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
class PaperFreshness:
    """Freshness semantics paper rehearsal candidate."""

    generated_at: datetime
    expires_at: datetime | None = None

    @property
    def has_structurally_valid_expiry_window(self) -> bool:
        """Проверить только структурную корректность expiry window."""
        return self.expires_at is None or self.expires_at >= self.generated_at

    def is_expired_at(self, reference_time: datetime) -> bool:
        """Определить, истёк ли rehearsal candidate относительно reference time."""
        return self.expires_at is not None and reference_time >= self.expires_at


@dataclass(slots=True, frozen=True)
class PaperContext:
    """
    Typed context paper layer поверх уже отделённых runtime truths.

    Paper layer выступает только consumer-ом manager / validation / optional OMS truth
    и не забирает ownership у Execution / OMS / Manager / Validation.
    """

    paper_name: str
    contour_name: str
    symbol: str
    exchange: str
    timeframe: MarketDataTimeframe
    observed_at: datetime
    source: PaperSource
    manager: ManagerWorkflowCandidate
    validation: ValidationReviewCandidate
    oms_order: OmsOrderRecord | None
    validity: PaperValidity
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Проверить базовые structural invariants paper context."""
        if self.source != PaperSource.RUNTIME_FOUNDATIONS:
            raise ValueError("PaperContext source должен быть RUNTIME_FOUNDATIONS")
        self._validate_shared_coordinates()
        if self.validity.is_valid:
            self._validate_valid_context()

    def _validate_shared_coordinates(self) -> None:
        upstreams = (
            ("manager", self.manager.symbol, self.manager.exchange, self.manager.timeframe),
            (
                "validation",
                self.validation.symbol,
                self.validation.exchange,
                self.validation.timeframe,
            ),
        )
        for name, symbol, exchange, timeframe in upstreams:
            if self.symbol != symbol:
                raise ValueError(f"PaperContext symbol должен совпадать с {name} symbol")
            if self.exchange != exchange:
                raise ValueError(f"PaperContext exchange должен совпадать с {name} exchange")
            if self.timeframe != timeframe:
                raise ValueError(f"PaperContext timeframe должен совпадать с {name} timeframe")
        if self.oms_order is not None:
            if self.symbol != self.oms_order.locator.symbol:
                raise ValueError("PaperContext symbol должен совпадать с oms symbol")
            if self.exchange != self.oms_order.locator.exchange:
                raise ValueError("PaperContext exchange должен совпадать с oms exchange")
            if self.timeframe != self.oms_order.locator.timeframe:
                raise ValueError("PaperContext timeframe должен совпадать с oms timeframe")

    def _validate_valid_context(self) -> None:
        if not self.manager.is_coordinated:
            raise ValueError("VALID PaperContext требует coordinated manager workflow")
        if not self.validation.is_validated:
            raise ValueError("VALID PaperContext требует validated review truth")


@dataclass(slots=True, frozen=True)
class PaperRehearsalCandidate:
    """
    Typed paper rehearsal output contract для Phase 19 foundation.

    Контракт intentionally не включает:
    - analytics / reporting ownership;
    - backtesting / replay ownership;
    - dashboard / operator semantics;
    - notifications / approval / liquidation semantics;
    - re-ownership Execution / OMS / Manager / Validation.
    """

    rehearsal_id: UUID
    contour_name: str
    paper_name: str
    symbol: str
    exchange: str
    timeframe: MarketDataTimeframe
    source: PaperSource
    freshness: PaperFreshness
    validity: PaperValidity
    status: PaperStatus
    decision: PaperDecision
    originating_workflow_id: UUID | None = None
    originating_review_id: UUID | None = None
    originating_oms_order_id: UUID | None = None
    confidence: Decimal | None = None
    rehearsal_score: Decimal | None = None
    reason_code: PaperReasonCode | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Проверить базовые structural invariants paper output."""
        if not self.freshness.has_structurally_valid_expiry_window:
            raise ValueError("Paper output требует expires_at >= generated_at")
        self._validate_status_invariants()
        if self.rehearsal_score is not None and self.rehearsal_score < Decimal("0"):
            raise ValueError("rehearsal_score не может быть отрицательным")
        if self.status in {PaperStatus.EXPIRED, PaperStatus.INVALIDATED} and self.validity.is_valid:
            raise ValueError("EXPIRED/INVALIDATED paper candidate не может иметь VALID")

    def _validate_status_invariants(self) -> None:
        if self.status == PaperStatus.REHEARSED:
            if self.decision != PaperDecision.REHEARSE:
                raise ValueError("REHEARSED candidate обязан иметь decision=REHEARSE")
            if not self.validity.is_valid:
                raise ValueError("REHEARSED candidate требует validity=VALID")
            required_ids = (self.originating_workflow_id, self.originating_review_id)
            if any(value is None for value in required_ids):
                raise ValueError("REHEARSED candidate обязан ссылаться на upstream rehearsal chain")
            return
        if self.status == PaperStatus.ABSTAINED and self.decision != PaperDecision.ABSTAIN:
            raise ValueError("ABSTAINED candidate обязан иметь decision=ABSTAIN")

    @property
    def is_rehearsed(self) -> bool:
        """Проверить, выражает ли candidate успешную narrow rehearsal truth."""
        return (
            self.validity.is_valid
            and self.status == PaperStatus.REHEARSED
            and self.decision == PaperDecision.REHEARSE
        )

    @property
    def is_abstained(self) -> bool:
        """Проверить, выражает ли candidate явный paper abstain."""
        return self.status == PaperStatus.ABSTAINED

    @classmethod
    def candidate(
        cls,
        *,
        contour_name: str,
        paper_name: str,
        symbol: str,
        exchange: str,
        timeframe: MarketDataTimeframe,
        source: PaperSource,
        freshness: PaperFreshness,
        validity: PaperValidity,
        decision: PaperDecision,
        status: PaperStatus = PaperStatus.CANDIDATE,
        originating_workflow_id: UUID | None = None,
        originating_review_id: UUID | None = None,
        originating_oms_order_id: UUID | None = None,
        confidence: Decimal | None = None,
        rehearsal_score: Decimal | None = None,
        reason_code: PaperReasonCode | None = None,
        metadata: dict[str, object] | None = None,
    ) -> PaperRehearsalCandidate:
        """Построить новый paper candidate с автоматически сгенерированным ID."""
        return cls(
            rehearsal_id=uuid4(),
            contour_name=contour_name,
            paper_name=paper_name,
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
            source=source,
            freshness=freshness,
            validity=validity,
            status=status,
            decision=decision,
            originating_workflow_id=originating_workflow_id,
            originating_review_id=originating_review_id,
            originating_oms_order_id=originating_oms_order_id,
            confidence=confidence,
            rehearsal_score=rehearsal_score,
            reason_code=reason_code,
            metadata={} if metadata is None else metadata.copy(),
        )


__all__ = [
    "PaperContext",
    "PaperDecision",
    "PaperFreshness",
    "PaperReasonCode",
    "PaperRehearsalCandidate",
    "PaperSource",
    "PaperStatus",
    "PaperValidity",
    "PaperValidityStatus",
]

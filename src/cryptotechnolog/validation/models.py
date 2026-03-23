"""
Contract-first модели Phase 18 для narrow validation layer.

Этот модуль фиксирует минимальный foundation scope:
- typed validation validity / readiness semantics;
- typed validation context contract поверх existing runtime truths;
- typed validation / review candidate contract;
- validation semantics без analytics / reporting / backtesting / paper-trading
  ownership и без re-ownership соседних runtime layers.
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
    from cryptotechnolog.portfolio_governor import PortfolioGovernorCandidate
    from cryptotechnolog.protection import ProtectionSupervisorCandidate


class ValidationDecision(StrEnum):
    """Нормализованный decision foundation validation layer."""

    VALIDATE = "validate"
    ABSTAIN = "abstain"


class ValidationStatus(StrEnum):
    """Lifecycle-состояние validation review candidate."""

    CANDIDATE = "candidate"
    VALIDATED = "validated"
    ABSTAINED = "abstained"
    INVALIDATED = "invalidated"
    EXPIRED = "expired"


class ValidationValidityStatus(StrEnum):
    """Состояние готовности validation context или review candidate."""

    VALID = "valid"
    WARMING = "warming"
    INVALID = "invalid"


class ValidationReasonCode(StrEnum):
    """Узкие reason semantics для foundation validation layer."""

    CONTEXT_READY = "context_ready"
    CONTEXT_INCOMPLETE = "context_incomplete"
    MANAGER_NOT_COORDINATED = "manager_not_coordinated"
    GOVERNOR_NOT_APPROVED = "governor_not_approved"
    PROTECTION_NOT_PROTECTED = "protection_not_protected"
    OMS_STATE_MISSING = "oms_state_missing"
    VALIDATION_CONFIRMED = "validation_confirmed"
    VALIDATION_ABSTAINED = "validation_abstained"
    VALIDATION_INVALIDATED = "validation_invalidated"
    VALIDATION_EXPIRED = "validation_expired"


class ValidationSource(StrEnum):
    """Нормализованный upstream source для foundation validation layer."""

    RUNTIME_FOUNDATIONS = "runtime_foundations"


@dataclass(slots=True, frozen=True)
class ValidationValidity:
    """Typed semantics готовности validation context или review candidate."""

    status: ValidationValidityStatus
    observed_inputs: int
    required_inputs: int
    missing_inputs: tuple[str, ...] = ()
    invalid_reason: str | None = None

    @property
    def is_valid(self) -> bool:
        """Проверить, готов ли контракт к production-использованию."""
        return self.status == ValidationValidityStatus.VALID

    @property
    def is_warming(self) -> bool:
        """Проверить, находится ли контракт в warming-state."""
        return self.status == ValidationValidityStatus.WARMING

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
class ValidationFreshness:
    """Freshness semantics validation review candidate."""

    generated_at: datetime
    expires_at: datetime | None = None

    @property
    def has_structurally_valid_expiry_window(self) -> bool:
        """Проверить только структурную корректность expiry window."""
        return self.expires_at is None or self.expires_at >= self.generated_at

    def is_expired_at(self, reference_time: datetime) -> bool:
        """Определить, истёк ли review candidate относительно reference time."""
        return self.expires_at is not None and reference_time >= self.expires_at


@dataclass(slots=True, frozen=True)
class ValidationContext:
    """
    Typed context validation layer поверх уже отделённых runtime truths.

    Validation layer выступает только review / assessment consumer-ом и
    не забирает ownership у Execution / OMS / Manager / Governor / Protection.
    """

    validation_name: str
    contour_name: str
    symbol: str
    exchange: str
    timeframe: MarketDataTimeframe
    observed_at: datetime
    source: ValidationSource
    manager: ManagerWorkflowCandidate
    governor: PortfolioGovernorCandidate
    protection: ProtectionSupervisorCandidate
    oms_order: OmsOrderRecord | None
    validity: ValidationValidity
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Проверить базовые structural invariants validation context."""
        if self.source != ValidationSource.RUNTIME_FOUNDATIONS:
            raise ValueError("ValidationContext source должен быть RUNTIME_FOUNDATIONS")
        self._validate_shared_coordinates()
        if self.validity.is_valid:
            self._validate_valid_context()

    def _validate_shared_coordinates(self) -> None:
        upstreams = (
            ("manager", self.manager.symbol, self.manager.exchange, self.manager.timeframe),
            ("governor", self.governor.symbol, self.governor.exchange, self.governor.timeframe),
            (
                "protection",
                self.protection.symbol,
                self.protection.exchange,
                self.protection.timeframe,
            ),
        )
        for name, symbol, exchange, timeframe in upstreams:
            if self.symbol != symbol:
                raise ValueError(f"ValidationContext symbol должен совпадать с {name} symbol")
            if self.exchange != exchange:
                raise ValueError(f"ValidationContext exchange должен совпадать с {name} exchange")
            if self.timeframe != timeframe:
                raise ValueError(f"ValidationContext timeframe должен совпадать с {name} timeframe")
        if self.oms_order is not None:
            if self.symbol != self.oms_order.locator.symbol:
                raise ValueError("ValidationContext symbol должен совпадать с oms symbol")
            if self.exchange != self.oms_order.locator.exchange:
                raise ValueError("ValidationContext exchange должен совпадать с oms exchange")
            if self.timeframe != self.oms_order.locator.timeframe:
                raise ValueError("ValidationContext timeframe должен совпадать с oms timeframe")

    def _validate_valid_context(self) -> None:
        if not self.manager.is_coordinated:
            raise ValueError("VALID ValidationContext требует coordinated manager workflow")
        if not self.governor.is_approved:
            raise ValueError("VALID ValidationContext требует approved governor candidate")
        if not self.protection.is_protected:
            raise ValueError("VALID ValidationContext требует protected supervisory truth")


@dataclass(slots=True, frozen=True)
class ValidationReviewCandidate:
    """
    Typed validation / review output contract для Phase 18 foundation.

    Контракт intentionally не включает:
    - analytics / reporting ownership;
    - backtesting / paper-trading semantics;
    - notifications / approval / liquidation / dashboard semantics;
    - re-ownership Execution / OMS / Manager / Governor / Protection.
    """

    review_id: UUID
    contour_name: str
    validation_name: str
    symbol: str
    exchange: str
    timeframe: MarketDataTimeframe
    source: ValidationSource
    freshness: ValidationFreshness
    validity: ValidationValidity
    status: ValidationStatus
    decision: ValidationDecision
    originating_workflow_id: UUID | None = None
    originating_governor_id: UUID | None = None
    originating_protection_id: UUID | None = None
    originating_oms_order_id: UUID | None = None
    confidence: Decimal | None = None
    review_score: Decimal | None = None
    reason_code: ValidationReasonCode | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Проверить базовые structural invariants validation output."""
        if not self.freshness.has_structurally_valid_expiry_window:
            raise ValueError("Validation output требует expires_at >= generated_at")
        self._validate_status_invariants()
        if self.review_score is not None and self.review_score < Decimal("0"):
            raise ValueError("review_score не может быть отрицательным")
        if (
            self.status in {ValidationStatus.EXPIRED, ValidationStatus.INVALIDATED}
            and self.validity.is_valid
        ):
            raise ValueError("EXPIRED/INVALIDATED validation candidate не может иметь VALID")

    def _validate_status_invariants(self) -> None:
        if self.status == ValidationStatus.VALIDATED:
            if self.decision != ValidationDecision.VALIDATE:
                raise ValueError("VALIDATED candidate обязан иметь decision=VALIDATE")
            if not self.validity.is_valid:
                raise ValueError("VALIDATED candidate требует validity=VALID")
            required_ids = (
                self.originating_workflow_id,
                self.originating_governor_id,
                self.originating_protection_id,
            )
            if any(value is None for value in required_ids):
                raise ValueError("VALIDATED candidate обязан ссылаться на upstream review chain")
            return
        if (
            self.status == ValidationStatus.ABSTAINED
            and self.decision != ValidationDecision.ABSTAIN
        ):
            raise ValueError("ABSTAINED candidate обязан иметь decision=ABSTAIN")

    @property
    def is_validated(self) -> bool:
        """Проверить, выражает ли candidate успешную narrow validation truth."""
        return (
            self.validity.is_valid
            and self.status == ValidationStatus.VALIDATED
            and self.decision == ValidationDecision.VALIDATE
        )

    @property
    def is_abstained(self) -> bool:
        """Проверить, выражает ли candidate явный validation abstain."""
        return self.status == ValidationStatus.ABSTAINED

    @classmethod
    def candidate(
        cls,
        *,
        contour_name: str,
        validation_name: str,
        symbol: str,
        exchange: str,
        timeframe: MarketDataTimeframe,
        source: ValidationSource,
        freshness: ValidationFreshness,
        validity: ValidationValidity,
        decision: ValidationDecision,
        status: ValidationStatus = ValidationStatus.CANDIDATE,
        originating_workflow_id: UUID | None = None,
        originating_governor_id: UUID | None = None,
        originating_protection_id: UUID | None = None,
        originating_oms_order_id: UUID | None = None,
        confidence: Decimal | None = None,
        review_score: Decimal | None = None,
        reason_code: ValidationReasonCode | None = None,
        metadata: dict[str, object] | None = None,
    ) -> ValidationReviewCandidate:
        """Построить новый validation candidate с автоматически сгенерированным ID."""
        return cls(
            review_id=uuid4(),
            contour_name=contour_name,
            validation_name=validation_name,
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
            source=source,
            freshness=freshness,
            validity=validity,
            status=status,
            decision=decision,
            originating_workflow_id=originating_workflow_id,
            originating_governor_id=originating_governor_id,
            originating_protection_id=originating_protection_id,
            originating_oms_order_id=originating_oms_order_id,
            confidence=confidence,
            review_score=review_score,
            reason_code=reason_code,
            metadata={} if metadata is None else metadata.copy(),
        )


__all__ = [
    "ValidationContext",
    "ValidationDecision",
    "ValidationFreshness",
    "ValidationReasonCode",
    "ValidationReviewCandidate",
    "ValidationSource",
    "ValidationStatus",
    "ValidationValidity",
    "ValidationValidityStatus",
]

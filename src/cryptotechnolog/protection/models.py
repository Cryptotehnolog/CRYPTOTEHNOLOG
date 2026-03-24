"""
Contract-first модели Phase 15 для protection / supervisor layer.

Этот модуль фиксирует минимальный foundation scope:
- typed protection validity / readiness semantics;
- typed protection context contract;
- typed supervisory candidate contract;
- freeze / halt / protect semantics без OMS / notifications / manager логики.
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
    from cryptotechnolog.portfolio_governor import PortfolioGovernorCandidate


class ProtectionDecision(StrEnum):
    """Нормализованный decision foundation protection layer."""

    PROTECT = "protect"
    HALT = "halt"
    FREEZE = "freeze"


class ProtectionStatus(StrEnum):
    """Lifecycle-состояние protection candidate."""

    CANDIDATE = "candidate"
    PROTECTED = "protected"
    HALTED = "halted"
    FROZEN = "frozen"
    INVALIDATED = "invalidated"
    EXPIRED = "expired"


class ProtectionValidityStatus(StrEnum):
    """Состояние готовности protection context или protection candidate."""

    VALID = "valid"
    WARMING = "warming"
    INVALID = "invalid"


class ProtectionReasonCode(StrEnum):
    """Узкие reason semantics для foundation protection layer."""

    CONTEXT_READY = "context_ready"
    CONTEXT_INCOMPLETE = "context_incomplete"
    GOVERNOR_NOT_APPROVED = "governor_not_approved"
    PROTECTION_PROTECTED = "protection_protected"
    PROTECTION_HALTED = "protection_halted"
    PROTECTION_FROZEN = "protection_frozen"
    PROTECTION_INVALIDATED = "protection_invalidated"
    PROTECTION_EXPIRED = "protection_expired"


class ProtectionSource(StrEnum):
    """Нормализованный upstream source для foundation protection layer."""

    PORTFOLIO_GOVERNOR = "portfolio_governor"


@dataclass(slots=True, frozen=True)
class ProtectionValidity:
    """Typed semantics готовности protection context или protection candidate."""

    status: ProtectionValidityStatus
    observed_inputs: int
    required_inputs: int
    missing_inputs: tuple[str, ...] = ()
    invalid_reason: str | None = None

    @property
    def is_valid(self) -> bool:
        """Проверить, готов ли контракт к production-использованию."""
        return self.status == ProtectionValidityStatus.VALID

    @property
    def is_warming(self) -> bool:
        """Проверить, находится ли контракт в warming-state."""
        return self.status == ProtectionValidityStatus.WARMING

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
class ProtectionFreshness:
    """Freshness semantics protection candidate."""

    generated_at: datetime
    expires_at: datetime | None = None

    @property
    def has_structurally_valid_expiry_window(self) -> bool:
        """Проверить только структурную корректность expiry window."""
        return self.expires_at is None or self.expires_at >= self.generated_at

    def is_expired_at(self, reference_time: datetime) -> bool:
        """Определить, истёк ли protection candidate относительно reference time."""
        return self.expires_at is not None and reference_time >= self.expires_at


@dataclass(slots=True, frozen=True)
class ProtectionContext:
    """
    Typed context protection layer поверх portfolio-governor truth.

    Protection layer здесь выступает только consumer-ом
    `PortfolioGovernorCandidate`.
    """

    supervisor_name: str
    contour_name: str
    symbol: str
    exchange: str
    timeframe: MarketDataTimeframe
    observed_at: datetime
    source: ProtectionSource
    governor: PortfolioGovernorCandidate
    validity: ProtectionValidity
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Проверить базовые structural invariants protection context."""
        if self.source != ProtectionSource.PORTFOLIO_GOVERNOR:
            raise ValueError("ProtectionContext source должен быть PORTFOLIO_GOVERNOR")
        if self.symbol != self.governor.symbol:
            raise ValueError("ProtectionContext symbol должен совпадать с governor symbol")
        if self.exchange != self.governor.exchange:
            raise ValueError("ProtectionContext exchange должен совпадать с governor exchange")
        if self.timeframe != self.governor.timeframe:
            raise ValueError("ProtectionContext timeframe должен совпадать с governor timeframe")
        if self.validity.is_valid and not self.governor.is_approved:
            raise ValueError(
                "VALID ProtectionContext требует approved portfolio-governor candidate"
            )


@dataclass(slots=True, frozen=True)
class ProtectionSupervisorCandidate:
    """
    Typed supervisory output contract для Phase 15 foundation.

    Контракт intentionally не включает:
    - OMS lifecycle;
    - broad liquidation engine semantics;
    - notifications / escalation delivery;
    - broader manager / workflow semantics.
    """

    protection_id: UUID
    contour_name: str
    supervisor_name: str
    symbol: str
    exchange: str
    timeframe: MarketDataTimeframe
    source: ProtectionSource
    freshness: ProtectionFreshness
    validity: ProtectionValidity
    status: ProtectionStatus
    decision: ProtectionDecision
    originating_governor_id: UUID | None = None
    confidence: Decimal | None = None
    priority_score: Decimal | None = None
    reason_code: ProtectionReasonCode | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Проверить базовые structural invariants protection output."""
        if not self.freshness.has_structurally_valid_expiry_window:
            raise ValueError("Protection output требует expires_at >= generated_at")
        self._validate_status_invariants()
        if self.priority_score is not None and self.priority_score < Decimal("0"):
            raise ValueError("priority_score не может быть отрицательным")
        if (
            self.status in {ProtectionStatus.EXPIRED, ProtectionStatus.INVALIDATED}
            and self.validity.is_valid
        ):
            raise ValueError(
                "EXPIRED/INVALIDATED protection candidate не может иметь validity=VALID"
            )

    def _validate_status_invariants(self) -> None:
        """Проверить status-specific invariants без смешения с runtime truth."""
        if self.status == ProtectionStatus.PROTECTED:
            if self.decision != ProtectionDecision.PROTECT:
                raise ValueError("PROTECTED candidate обязан иметь decision=PROTECT")
            if not self.validity.is_valid:
                raise ValueError("PROTECTED candidate требует validity=VALID")
            if self.originating_governor_id is None:
                raise ValueError("PROTECTED candidate обязан ссылаться на governor_id")
            return
        if self.status == ProtectionStatus.HALTED:
            if self.decision != ProtectionDecision.HALT:
                raise ValueError("HALTED candidate обязан иметь decision=HALT")
            if not self.validity.is_valid:
                raise ValueError("HALTED candidate требует validity=VALID")
            if self.originating_governor_id is None:
                raise ValueError("HALTED candidate обязан ссылаться на governor_id")
            return
        if self.status == ProtectionStatus.FROZEN:
            if self.decision != ProtectionDecision.FREEZE:
                raise ValueError("FROZEN candidate обязан иметь decision=FREEZE")
            if not self.validity.is_valid:
                raise ValueError("FROZEN candidate требует validity=VALID")
            if self.originating_governor_id is None:
                raise ValueError("FROZEN candidate обязан ссылаться на governor_id")

    @property
    def is_protected(self) -> bool:
        """Проверить, выражает ли candidate узкую protect semantics."""
        return (
            self.validity.is_valid
            and self.status == ProtectionStatus.PROTECTED
            and self.decision == ProtectionDecision.PROTECT
        )

    @property
    def is_halted(self) -> bool:
        """Проверить, выражает ли candidate явный halt semantics."""
        return (
            self.validity.is_valid
            and self.status == ProtectionStatus.HALTED
            and self.decision == ProtectionDecision.HALT
        )

    @property
    def is_frozen(self) -> bool:
        """Проверить, выражает ли candidate явный freeze semantics."""
        return (
            self.validity.is_valid
            and self.status == ProtectionStatus.FROZEN
            and self.decision == ProtectionDecision.FREEZE
        )

    @classmethod
    def candidate(
        cls,
        *,
        contour_name: str,
        supervisor_name: str,
        symbol: str,
        exchange: str,
        timeframe: MarketDataTimeframe,
        source: ProtectionSource,
        freshness: ProtectionFreshness,
        validity: ProtectionValidity,
        decision: ProtectionDecision,
        status: ProtectionStatus = ProtectionStatus.CANDIDATE,
        originating_governor_id: UUID | None = None,
        confidence: Decimal | None = None,
        priority_score: Decimal | None = None,
        reason_code: ProtectionReasonCode | None = None,
        metadata: dict[str, object] | None = None,
    ) -> ProtectionSupervisorCandidate:
        """Построить новый protection candidate с автоматически сгенерированным ID."""
        return cls(
            protection_id=uuid4(),
            contour_name=contour_name,
            supervisor_name=supervisor_name,
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
            source=source,
            freshness=freshness,
            validity=validity,
            status=status,
            decision=decision,
            originating_governor_id=originating_governor_id,
            confidence=confidence,
            priority_score=priority_score,
            reason_code=reason_code,
            metadata={} if metadata is None else metadata.copy(),
        )


__all__ = [
    "ProtectionContext",
    "ProtectionDecision",
    "ProtectionFreshness",
    "ProtectionReasonCode",
    "ProtectionSource",
    "ProtectionStatus",
    "ProtectionSupervisorCandidate",
    "ProtectionValidity",
    "ProtectionValidityStatus",
]

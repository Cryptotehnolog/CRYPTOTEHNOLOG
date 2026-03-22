"""
Contract-first модели Phase 14 для portfolio-governor layer.

Этот модуль фиксирует минимальный foundation scope:
- typed portfolio-governor validity / readiness semantics;
- typed governor context contract;
- typed portfolio-admission candidate contract;
- approve / abstain / reject semantics без protection / OMS / manager логики.
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
    from cryptotechnolog.position_expansion import PositionExpansionCandidate


class GovernorDirection(StrEnum):
    """Направление portfolio-admission candidate."""

    LONG = "LONG"
    SHORT = "SHORT"


class GovernorDecision(StrEnum):
    """Нормализованный decision foundation portfolio-governor layer."""

    APPROVE = "approve"
    ABSTAIN = "abstain"
    REJECT = "reject"


class GovernorStatus(StrEnum):
    """Lifecycle-состояние portfolio-governor candidate."""

    CANDIDATE = "candidate"
    APPROVED = "approved"
    ABSTAINED = "abstained"
    REJECTED = "rejected"
    INVALIDATED = "invalidated"
    EXPIRED = "expired"


class GovernorValidityStatus(StrEnum):
    """Состояние готовности governor context или governor candidate."""

    VALID = "valid"
    WARMING = "warming"
    INVALID = "invalid"


class GovernorReasonCode(StrEnum):
    """Узкие reason semantics для foundation portfolio-governor layer."""

    CONTEXT_READY = "context_ready"
    CONTEXT_INCOMPLETE = "context_incomplete"
    EXPANSION_NOT_APPROVABLE = "expansion_not_approvable"
    GOVERNOR_ABSTAINED = "governor_abstained"
    GOVERNOR_REJECTED = "governor_rejected"
    GOVERNOR_INVALIDATED = "governor_invalidated"
    GOVERNOR_EXPIRED = "governor_expired"


class GovernorSource(StrEnum):
    """Нормализованный upstream source для foundation portfolio-governor layer."""

    POSITION_EXPANSION = "position_expansion"


@dataclass(slots=True, frozen=True)
class GovernorValidity:
    """Typed semantics готовности governor context или governor candidate."""

    status: GovernorValidityStatus
    observed_inputs: int
    required_inputs: int
    missing_inputs: tuple[str, ...] = ()
    invalid_reason: str | None = None

    @property
    def is_valid(self) -> bool:
        """Проверить, готов ли контракт к production-использованию."""
        return self.status == GovernorValidityStatus.VALID

    @property
    def is_warming(self) -> bool:
        """Проверить, находится ли контракт в warming-state."""
        return self.status == GovernorValidityStatus.WARMING

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
class GovernorFreshness:
    """Freshness semantics governor candidate."""

    generated_at: datetime
    expires_at: datetime | None = None

    @property
    def has_structurally_valid_expiry_window(self) -> bool:
        """
        Проверить только структурную корректность expiry window.

        Это не runtime-temporal truth:
        метод не отвечает на вопрос, истёк ли governor candidate "сейчас",
        а только проверяет, что `expires_at` не раньше `generated_at`.
        """
        return self.expires_at is None or self.expires_at >= self.generated_at

    def is_expired_at(self, reference_time: datetime) -> bool:
        """
        Определить, истёк ли governor candidate относительно reference time.

        Runtime-слой обязан передавать сюда собственный временной контекст.
        """
        return self.expires_at is not None and reference_time >= self.expires_at


@dataclass(slots=True, frozen=True)
class GovernorContext:
    """
    Typed context portfolio-governor layer поверх position-expansion truth.

    Portfolio-governor layer здесь выступает только consumer-ом
    `PositionExpansionCandidate`.
    """

    governor_name: str
    contour_name: str
    symbol: str
    exchange: str
    timeframe: MarketDataTimeframe
    observed_at: datetime
    source: GovernorSource
    expansion: PositionExpansionCandidate
    validity: GovernorValidity
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Проверить базовые structural invariants governor context."""
        if self.source != GovernorSource.POSITION_EXPANSION:
            raise ValueError("GovernorContext source должен быть POSITION_EXPANSION")
        if self.symbol != self.expansion.symbol:
            raise ValueError("GovernorContext symbol должен совпадать с expansion symbol")
        if self.exchange != self.expansion.exchange:
            raise ValueError("GovernorContext exchange должен совпадать с expansion exchange")
        if self.timeframe != self.expansion.timeframe:
            raise ValueError("GovernorContext timeframe должен совпадать с expansion timeframe")
        if self.validity.is_valid and not self.expansion.is_expandable:
            raise ValueError(
                "VALID GovernorContext требует expandable position-expansion candidate"
            )


@dataclass(slots=True, frozen=True)
class PortfolioGovernorCandidate:
    """
    Typed portfolio-admission output contract для Phase 14 foundation.

    Контракт intentionally не включает:
    - protection / kill switch semantics;
    - OMS lifecycle;
    - broad workflow / manager semantics;
    - analytics / validation / notifications semantics.
    """

    governor_id: UUID
    contour_name: str
    governor_name: str
    symbol: str
    exchange: str
    timeframe: MarketDataTimeframe
    source: GovernorSource
    freshness: GovernorFreshness
    validity: GovernorValidity
    status: GovernorStatus
    decision: GovernorDecision
    direction: GovernorDirection | None = None
    originating_expansion_id: UUID | None = None
    confidence: Decimal | None = None
    priority_score: Decimal | None = None
    capital_fraction: Decimal | None = None
    reason_code: GovernorReasonCode | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Проверить базовые structural invariants governor output."""
        if not self.freshness.has_structurally_valid_expiry_window:
            raise ValueError("Governor output требует expires_at >= generated_at")
        self._validate_status_invariants()
        if self.priority_score is not None and self.priority_score < Decimal("0"):
            raise ValueError("priority_score не может быть отрицательным")
        if self.capital_fraction is not None and not (
            Decimal("0") < self.capital_fraction <= Decimal("1")
        ):
            raise ValueError("capital_fraction должен находиться в диапазоне (0, 1]")
        if (
            self.status in {GovernorStatus.EXPIRED, GovernorStatus.INVALIDATED}
            and self.validity.is_valid
        ):
            raise ValueError("EXPIRED/INVALIDATED governor candidate не может иметь validity=VALID")

    def _validate_status_invariants(self) -> None:
        """Проверить status-specific invariants без смешения с runtime truth."""
        if self.status == GovernorStatus.APPROVED:
            if self.decision != GovernorDecision.APPROVE:
                raise ValueError("APPROVED candidate обязан иметь decision=APPROVE")
            if not self.validity.is_valid:
                raise ValueError("APPROVED candidate требует validity=VALID")
            if self.direction is None:
                raise ValueError("APPROVED candidate обязан иметь direction")
            if self.originating_expansion_id is None:
                raise ValueError("APPROVED candidate обязан ссылаться на expansion_id")
            if self.capital_fraction is None:
                raise ValueError("APPROVED candidate обязан иметь capital_fraction")
            return
        if self.status == GovernorStatus.ABSTAINED:
            if self.decision != GovernorDecision.ABSTAIN:
                raise ValueError("ABSTAINED candidate обязан иметь decision=ABSTAIN")
            if self.direction is not None:
                raise ValueError("ABSTAINED candidate не должен иметь direction")
            return
        if self.status == GovernorStatus.REJECTED:
            if self.decision != GovernorDecision.REJECT:
                raise ValueError("REJECTED candidate обязан иметь decision=REJECT")
            if self.direction is not None:
                raise ValueError("REJECTED candidate не должен иметь direction")

    @property
    def is_approved(self) -> bool:
        """Проверить, готов ли candidate к узкому governor-approval path."""
        return (
            self.validity.is_valid
            and self.status == GovernorStatus.APPROVED
            and self.decision == GovernorDecision.APPROVE
        )

    @property
    def is_abstained(self) -> bool:
        """Проверить, выражает ли candidate явный no-admission abstain."""
        return self.status == GovernorStatus.ABSTAINED

    @property
    def is_rejected(self) -> bool:
        """Проверить, выражает ли candidate явный no-admission reject."""
        return self.status == GovernorStatus.REJECTED

    @classmethod
    def candidate(
        cls,
        *,
        contour_name: str,
        governor_name: str,
        symbol: str,
        exchange: str,
        timeframe: MarketDataTimeframe,
        source: GovernorSource,
        freshness: GovernorFreshness,
        validity: GovernorValidity,
        decision: GovernorDecision,
        status: GovernorStatus = GovernorStatus.CANDIDATE,
        direction: GovernorDirection | None = None,
        originating_expansion_id: UUID | None = None,
        confidence: Decimal | None = None,
        priority_score: Decimal | None = None,
        capital_fraction: Decimal | None = None,
        reason_code: GovernorReasonCode | None = None,
        metadata: dict[str, object] | None = None,
    ) -> PortfolioGovernorCandidate:
        """
        Построить новый governor candidate с автоматически сгенерированным ID.

        Factory намеренно не выводит lifecycle-status из `validity + decision`.
        Ownership runtime-truth остаётся у runtime следующего шага.
        """
        return cls(
            governor_id=uuid4(),
            contour_name=contour_name,
            governor_name=governor_name,
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
            source=source,
            freshness=freshness,
            validity=validity,
            status=status,
            decision=decision,
            direction=direction,
            originating_expansion_id=originating_expansion_id,
            confidence=confidence,
            priority_score=priority_score,
            capital_fraction=capital_fraction,
            reason_code=reason_code,
            metadata={} if metadata is None else metadata.copy(),
        )


__all__ = [
    "GovernorContext",
    "GovernorDecision",
    "GovernorDirection",
    "GovernorFreshness",
    "GovernorReasonCode",
    "GovernorSource",
    "GovernorStatus",
    "GovernorValidity",
    "GovernorValidityStatus",
    "PortfolioGovernorCandidate",
]

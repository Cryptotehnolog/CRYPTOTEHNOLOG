"""
Contract-first модели Phase 17 для manager / workflow layer.

Этот модуль фиксирует минимальный foundation scope:
- typed manager validity / readiness semantics;
- typed manager context contract;
- typed workflow-coordination candidate contract;
- coordination / abstain semantics без Execution / OMS ownership.
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
    from cryptotechnolog.opportunity import OpportunitySelectionCandidate
    from cryptotechnolog.orchestration import OrchestrationDecisionCandidate
    from cryptotechnolog.portfolio_governor import PortfolioGovernorCandidate
    from cryptotechnolog.position_expansion import PositionExpansionCandidate
    from cryptotechnolog.protection import ProtectionSupervisorCandidate


class ManagerDecision(StrEnum):
    """Нормализованный decision foundation manager layer."""

    COORDINATE = "coordinate"
    ABSTAIN = "abstain"


class ManagerStatus(StrEnum):
    """Lifecycle-состояние manager workflow candidate."""

    CANDIDATE = "candidate"
    COORDINATED = "coordinated"
    ABSTAINED = "abstained"
    INVALIDATED = "invalidated"
    EXPIRED = "expired"


class ManagerValidityStatus(StrEnum):
    """Состояние готовности manager context или workflow candidate."""

    VALID = "valid"
    WARMING = "warming"
    INVALID = "invalid"


class ManagerReasonCode(StrEnum):
    """Узкие reason semantics для foundation manager layer."""

    CONTEXT_READY = "context_ready"
    CONTEXT_INCOMPLETE = "context_incomplete"
    OPPORTUNITY_NOT_SELECTED = "opportunity_not_selected"
    ORCHESTRATION_NOT_FORWARDED = "orchestration_not_forwarded"
    EXPANSION_NOT_EXPANDABLE = "expansion_not_expandable"
    GOVERNOR_NOT_APPROVED = "governor_not_approved"
    PROTECTION_NOT_COORDINATABLE = "protection_not_coordinatable"
    MANAGER_COORDINATED = "manager_coordinated"
    MANAGER_ABSTAINED = "manager_abstained"
    MANAGER_INVALIDATED = "manager_invalidated"
    MANAGER_EXPIRED = "manager_expired"


class ManagerSource(StrEnum):
    """Нормализованный upstream source для foundation manager layer."""

    WORKFLOW_FOUNDATIONS = "workflow_foundations"


@dataclass(slots=True, frozen=True)
class ManagerValidity:
    """Typed semantics готовности manager context или workflow candidate."""

    status: ManagerValidityStatus
    observed_inputs: int
    required_inputs: int
    missing_inputs: tuple[str, ...] = ()
    invalid_reason: str | None = None

    @property
    def is_valid(self) -> bool:
        """Проверить, готов ли контракт к production-использованию."""
        return self.status == ManagerValidityStatus.VALID

    @property
    def is_warming(self) -> bool:
        """Проверить, находится ли контракт в warming-state."""
        return self.status == ManagerValidityStatus.WARMING

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
class ManagerFreshness:
    """Freshness semantics manager workflow candidate."""

    generated_at: datetime
    expires_at: datetime | None = None

    @property
    def has_structurally_valid_expiry_window(self) -> bool:
        """Проверить только структурную корректность expiry window."""
        return self.expires_at is None or self.expires_at >= self.generated_at

    def is_expired_at(self, reference_time: datetime) -> bool:
        """Определить, истёк ли workflow candidate относительно reference time."""
        return self.expires_at is not None and reference_time >= self.expires_at


@dataclass(slots=True, frozen=True)
class ManagerContext:
    """
    Typed context manager layer поверх already existing workflow truths.

    Manager layer здесь выступает только consumer-ом соседних foundation layers
    и не забирает ownership у Execution / OMS / protection / governor.
    """

    manager_name: str
    contour_name: str
    symbol: str
    exchange: str
    timeframe: MarketDataTimeframe
    observed_at: datetime
    source: ManagerSource
    opportunity: OpportunitySelectionCandidate
    orchestration: OrchestrationDecisionCandidate
    expansion: PositionExpansionCandidate
    governor: PortfolioGovernorCandidate
    protection: ProtectionSupervisorCandidate
    validity: ManagerValidity
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Проверить базовые structural invariants manager context."""
        if self.source != ManagerSource.WORKFLOW_FOUNDATIONS:
            raise ValueError("ManagerContext source должен быть WORKFLOW_FOUNDATIONS")
        self._validate_shared_coordinates()
        if self.validity.is_valid:
            self._validate_valid_context()

    def _validate_shared_coordinates(self) -> None:
        if self.symbol != self.opportunity.symbol:
            raise ValueError("ManagerContext symbol должен совпадать с opportunity symbol")
        if self.exchange != self.opportunity.exchange:
            raise ValueError("ManagerContext exchange должен совпадать с opportunity exchange")
        if self.timeframe != self.opportunity.timeframe:
            raise ValueError("ManagerContext timeframe должен совпадать с opportunity timeframe")

        upstreams = (
            (
                "orchestration",
                self.orchestration.symbol,
                self.orchestration.exchange,
                self.orchestration.timeframe,
            ),
            ("expansion", self.expansion.symbol, self.expansion.exchange, self.expansion.timeframe),
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
                raise ValueError(f"ManagerContext symbol должен совпадать с {name} symbol")
            if self.exchange != exchange:
                raise ValueError(f"ManagerContext exchange должен совпадать с {name} exchange")
            if self.timeframe != timeframe:
                raise ValueError(f"ManagerContext timeframe должен совпадать с {name} timeframe")

    def _validate_valid_context(self) -> None:
        if not self.opportunity.is_selected:
            raise ValueError("VALID ManagerContext требует selected opportunity")
        if not self.orchestration.is_forwarded:
            raise ValueError("VALID ManagerContext требует forwarded orchestration decision")
        if not self.expansion.is_expandable:
            raise ValueError("VALID ManagerContext требует expandable position-expansion candidate")
        if not self.governor.is_approved:
            raise ValueError("VALID ManagerContext требует approved portfolio-governor candidate")
        if not (
            self.protection.is_protected or self.protection.is_halted or self.protection.is_frozen
        ):
            raise ValueError(
                "VALID ManagerContext требует explicit protection supervisory candidate"
            )


@dataclass(slots=True, frozen=True)
class ManagerWorkflowCandidate:
    """
    Typed workflow-coordination output contract для Phase 17 foundation.

    Контракт intentionally не включает:
    - Execution / OMS ownership;
    - notifications / approval workflow;
    - liquidation / ops semantics;
    - broad validation / dashboard / multi-strategy platform semantics.
    """

    workflow_id: UUID
    contour_name: str
    manager_name: str
    symbol: str
    exchange: str
    timeframe: MarketDataTimeframe
    source: ManagerSource
    freshness: ManagerFreshness
    validity: ManagerValidity
    status: ManagerStatus
    decision: ManagerDecision
    originating_selection_id: UUID | None = None
    originating_decision_id: UUID | None = None
    originating_expansion_id: UUID | None = None
    originating_governor_id: UUID | None = None
    originating_protection_id: UUID | None = None
    confidence: Decimal | None = None
    priority_score: Decimal | None = None
    reason_code: ManagerReasonCode | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Проверить базовые structural invariants manager output."""
        if not self.freshness.has_structurally_valid_expiry_window:
            raise ValueError("Manager output требует expires_at >= generated_at")
        self._validate_status_invariants()
        if self.priority_score is not None and self.priority_score < Decimal("0"):
            raise ValueError("priority_score не может быть отрицательным")
        if (
            self.status in {ManagerStatus.EXPIRED, ManagerStatus.INVALIDATED}
            and self.validity.is_valid
        ):
            raise ValueError("EXPIRED/INVALIDATED manager candidate не может иметь validity=VALID")

    def _validate_status_invariants(self) -> None:
        if self.status == ManagerStatus.COORDINATED:
            if self.decision != ManagerDecision.COORDINATE:
                raise ValueError("COORDINATED candidate обязан иметь decision=COORDINATE")
            if not self.validity.is_valid:
                raise ValueError("COORDINATED candidate требует validity=VALID")
            required_ids = (
                self.originating_selection_id,
                self.originating_decision_id,
                self.originating_expansion_id,
                self.originating_governor_id,
                self.originating_protection_id,
            )
            if any(value is None for value in required_ids):
                raise ValueError(
                    "COORDINATED candidate обязан ссылаться на upstream workflow chain"
                )
            return
        if self.status == ManagerStatus.ABSTAINED and self.decision != ManagerDecision.ABSTAIN:
            raise ValueError("ABSTAINED candidate обязан иметь decision=ABSTAIN")

    @property
    def is_coordinated(self) -> bool:
        """Проверить, готов ли candidate к narrow workflow-coordination path."""
        return (
            self.validity.is_valid
            and self.status == ManagerStatus.COORDINATED
            and self.decision == ManagerDecision.COORDINATE
        )

    @property
    def is_abstained(self) -> bool:
        """Проверить, выражает ли candidate явный manager abstain."""
        return self.status == ManagerStatus.ABSTAINED

    @classmethod
    def candidate(
        cls,
        *,
        contour_name: str,
        manager_name: str,
        symbol: str,
        exchange: str,
        timeframe: MarketDataTimeframe,
        source: ManagerSource,
        freshness: ManagerFreshness,
        validity: ManagerValidity,
        decision: ManagerDecision,
        status: ManagerStatus = ManagerStatus.CANDIDATE,
        originating_selection_id: UUID | None = None,
        originating_decision_id: UUID | None = None,
        originating_expansion_id: UUID | None = None,
        originating_governor_id: UUID | None = None,
        originating_protection_id: UUID | None = None,
        confidence: Decimal | None = None,
        priority_score: Decimal | None = None,
        reason_code: ManagerReasonCode | None = None,
        metadata: dict[str, object] | None = None,
    ) -> ManagerWorkflowCandidate:
        """Построить новый manager candidate с автоматически сгенерированным ID."""
        return cls(
            workflow_id=uuid4(),
            contour_name=contour_name,
            manager_name=manager_name,
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
            source=source,
            freshness=freshness,
            validity=validity,
            status=status,
            decision=decision,
            originating_selection_id=originating_selection_id,
            originating_decision_id=originating_decision_id,
            originating_expansion_id=originating_expansion_id,
            originating_governor_id=originating_governor_id,
            originating_protection_id=originating_protection_id,
            confidence=confidence,
            priority_score=priority_score,
            reason_code=reason_code,
            metadata={} if metadata is None else metadata.copy(),
        )


__all__ = [
    "ManagerContext",
    "ManagerDecision",
    "ManagerFreshness",
    "ManagerReasonCode",
    "ManagerSource",
    "ManagerStatus",
    "ManagerValidity",
    "ManagerValidityStatus",
    "ManagerWorkflowCandidate",
]

"""
Узкий explicit runtime foundation для Phase 14 Portfolio Governor Foundation.

Этот runtime:
- стартует и останавливается явно;
- не делает hidden bootstrap;
- собирает typed governor context из position-expansion truth;
- поддерживает один минимальный deterministic governor contour;
- хранит query/state-first truth и operator-visible diagnostics.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from cryptotechnolog.market_data import MarketDataTimeframe
from cryptotechnolog.position_expansion import ExpansionStatus, PositionExpansionCandidate

from .events import PortfolioGovernorEventType, PortfolioGovernorPayload
from .models import (
    GovernorContext,
    GovernorDecision,
    GovernorDirection,
    GovernorFreshness,
    GovernorReasonCode,
    GovernorSource,
    GovernorStatus,
    GovernorValidity,
    GovernorValidityStatus,
    PortfolioGovernorCandidate,
)

if TYPE_CHECKING:
    from collections.abc import Callable


type PortfolioGovernorStateKey = tuple[str, str, MarketDataTimeframe, str, str]


class PortfolioGovernorRuntimeLifecycleState(StrEnum):
    """Lifecycle-состояние portfolio-governor runtime."""

    NOT_STARTED = "not_started"
    WARMING = "warming"
    READY = "ready"
    DEGRADED = "degraded"
    STOPPED = "stopped"


@dataclass(slots=True, frozen=True)
class PortfolioGovernorRuntimeConfig:
    """Typed runtime-конфигурация следующего шага P_14."""

    contour_name: str = "phase14_portfolio_governor_contour"
    governor_name: str = "phase14_portfolio_governor"
    max_candidate_age_seconds: int = 300
    min_confidence_for_approval: Decimal = Decimal("0.5000")
    min_priority_score_for_approval: Decimal = Decimal("0.5000")
    default_capital_fraction: Decimal = Decimal("0.1000")

    def __post_init__(self) -> None:
        if self.max_candidate_age_seconds <= 0:
            raise ValueError("max_candidate_age_seconds должен быть положительным")
        if not (Decimal("0") <= self.min_confidence_for_approval <= Decimal("1")):
            raise ValueError("min_confidence_for_approval должен находиться в диапазоне [0, 1]")
        if not (Decimal("0") <= self.min_priority_score_for_approval <= Decimal("1")):
            raise ValueError("min_priority_score_for_approval должен находиться в диапазоне [0, 1]")
        if not (Decimal("0") < self.default_capital_fraction <= Decimal("1")):
            raise ValueError("default_capital_fraction должен находиться в диапазоне (0, 1]")


@dataclass(slots=True)
class PortfolioGovernorRuntimeDiagnostics:
    """Operator-visible diagnostics contract portfolio-governor runtime."""

    started: bool = False
    ready: bool = False
    lifecycle_state: PortfolioGovernorRuntimeLifecycleState = (
        PortfolioGovernorRuntimeLifecycleState.NOT_STARTED
    )
    tracked_context_keys: int = 0
    tracked_governor_keys: int = 0
    approved_keys: int = 0
    abstained_keys: int = 0
    rejected_keys: int = 0
    invalidated_governor_keys: int = 0
    expired_governor_keys: int = 0
    last_expansion_id: str | None = None
    last_governor_id: str | None = None
    last_event_type: str | None = None
    last_failure_reason: str | None = None
    readiness_reasons: list[str] = field(default_factory=list)
    degraded_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        """Преобразовать diagnostics в operator-facing словарь."""
        return {
            "started": self.started,
            "ready": self.ready,
            "lifecycle_state": self.lifecycle_state.value,
            "tracked_context_keys": self.tracked_context_keys,
            "tracked_governor_keys": self.tracked_governor_keys,
            "approved_keys": self.approved_keys,
            "abstained_keys": self.abstained_keys,
            "rejected_keys": self.rejected_keys,
            "invalidated_governor_keys": self.invalidated_governor_keys,
            "expired_governor_keys": self.expired_governor_keys,
            "last_expansion_id": self.last_expansion_id,
            "last_governor_id": self.last_governor_id,
            "last_event_type": self.last_event_type,
            "last_failure_reason": self.last_failure_reason,
            "readiness_reasons": list(self.readiness_reasons),
            "degraded_reasons": list(self.degraded_reasons),
        }


@dataclass(slots=True, frozen=True)
class PortfolioGovernorRuntimeUpdate:
    """Typed update contract portfolio-governor runtime foundation."""

    context: GovernorContext
    candidate: PortfolioGovernorCandidate | None
    event_type: PortfolioGovernorEventType
    emitted_payload: PortfolioGovernorPayload | None = None


class PortfolioGovernorRuntime:
    """Explicit runtime foundation для portfolio-governor layer Phase 14."""

    def __init__(
        self,
        config: PortfolioGovernorRuntimeConfig | None = None,
        *,
        diagnostics_sink: Callable[[dict[str, object]], None] | None = None,
    ) -> None:
        self.config = config or PortfolioGovernorRuntimeConfig()
        self._diagnostics_sink = diagnostics_sink
        self._diagnostics = PortfolioGovernorRuntimeDiagnostics()
        self._started = False
        self._contexts: dict[PortfolioGovernorStateKey, GovernorContext] = {}
        self._candidates: dict[PortfolioGovernorStateKey, PortfolioGovernorCandidate] = {}
        self._push_diagnostics()

    @property
    def is_started(self) -> bool:
        """Проверить, активирован ли runtime."""
        return self._started

    async def start(self) -> None:
        """Поднять runtime без hidden bootstrap."""
        if self._started:
            return
        self._started = True
        self._refresh_diagnostics(
            lifecycle_state=PortfolioGovernorRuntimeLifecycleState.WARMING,
            ready=False,
            last_failure_reason=None,
            readiness_reasons=("no_portfolio_governor_context_processed",),
            degraded_reasons=(),
        )

    async def stop(self) -> None:
        """Остановить runtime и очистить operator-visible state."""
        if not self._started:
            return
        self._started = False
        self._contexts = {}
        self._candidates = {}
        self._refresh_diagnostics(
            lifecycle_state=PortfolioGovernorRuntimeLifecycleState.STOPPED,
            ready=False,
            tracked_context_keys=0,
            tracked_governor_keys=0,
            approved_keys=0,
            abstained_keys=0,
            rejected_keys=0,
            invalidated_governor_keys=0,
            expired_governor_keys=0,
            last_expansion_id=None,
            last_governor_id=None,
            last_event_type=None,
            last_failure_reason=None,
            readiness_reasons=("runtime_stopped",),
            degraded_reasons=(),
        )

    def ingest_expansion(
        self,
        *,
        expansion: PositionExpansionCandidate,
        reference_time: datetime,
        metadata: dict[str, object] | None = None,
    ) -> PortfolioGovernorRuntimeUpdate:
        """Принять position-expansion truth, собрать governor context и обновить state."""
        self._ensure_started("ingest_expansion")
        context = self._assemble_governor_context(
            expansion=expansion,
            reference_time=reference_time,
            metadata=metadata,
        )
        return self._ingest_governor_context(context, reference_time=reference_time)

    def get_candidate(
        self,
        *,
        symbol: str,
        exchange: str,
        timeframe: MarketDataTimeframe,
    ) -> PortfolioGovernorCandidate | None:
        """Вернуть текущее governor state по ключу."""
        return self._candidates.get(
            self._build_state_key(exchange=exchange, symbol=symbol, timeframe=timeframe)
        )

    def get_context(
        self,
        *,
        symbol: str,
        exchange: str,
        timeframe: MarketDataTimeframe,
    ) -> GovernorContext | None:
        """Вернуть последний assembled governor context."""
        return self._contexts.get(
            self._build_state_key(exchange=exchange, symbol=symbol, timeframe=timeframe)
        )

    def expire_candidates(
        self,
        *,
        reference_time: datetime,
    ) -> tuple[PortfolioGovernorRuntimeUpdate, ...]:
        """Переоценить lifecycle truth относительно reference time."""
        self._ensure_started("expire_candidates")
        updates: list[PortfolioGovernorRuntimeUpdate] = []
        for key, candidate in tuple(self._candidates.items()):
            updated = self._expire_candidate_if_needed(candidate, reference_time=reference_time)
            if updated is not candidate:
                self._candidates[key] = updated
                context = self._contexts[key]
                payload = PortfolioGovernorPayload.from_candidate(updated)
                updates.append(
                    PortfolioGovernorRuntimeUpdate(
                        context=context,
                        candidate=updated,
                        event_type=PortfolioGovernorEventType.PORTFOLIO_GOVERNOR_INVALIDATED,
                        emitted_payload=payload,
                    )
                )
                self._update_diagnostics_for_candidate(
                    candidate=updated,
                    event_type=PortfolioGovernorEventType.PORTFOLIO_GOVERNOR_INVALIDATED,
                )
        return tuple(updates)

    def mark_degraded(self, reason: str) -> None:
        """Зафиксировать деградацию ingest/runtime path."""
        self._refresh_diagnostics(
            lifecycle_state=PortfolioGovernorRuntimeLifecycleState.DEGRADED,
            ready=False,
            last_failure_reason=reason,
            degraded_reasons=(reason,),
        )

    def get_runtime_diagnostics(self) -> dict[str, object]:
        """Вернуть operator-visible diagnostics."""
        return self._diagnostics.to_dict()

    def _assemble_governor_context(
        self,
        *,
        expansion: PositionExpansionCandidate,
        reference_time: datetime,
        metadata: dict[str, object] | None,
    ) -> GovernorContext:
        observed_inputs = 1
        required_inputs = 1
        missing_inputs: list[str] = []
        invalid_reason: str | None = None

        if (
            expansion.freshness.is_expired_at(reference_time)
            or expansion.status == ExpansionStatus.EXPIRED
        ):
            invalid_reason = "position_expansion_expired"
        elif expansion.status == ExpansionStatus.INVALIDATED:
            invalid_reason = "position_expansion_invalidated"
        elif expansion.status == ExpansionStatus.REJECTED:
            invalid_reason = "position_expansion_rejected"
        elif expansion.status == ExpansionStatus.ABSTAINED:
            invalid_reason = "position_expansion_abstained"
        elif expansion.status == ExpansionStatus.CANDIDATE:
            missing_inputs.append("approvable_expansion")
        elif expansion.is_expandable:
            pass
        else:
            invalid_reason = "position_expansion_not_approvable"

        if invalid_reason is not None:
            validity = GovernorValidity(
                status=GovernorValidityStatus.INVALID,
                observed_inputs=observed_inputs,
                required_inputs=required_inputs,
                invalid_reason=invalid_reason,
            )
        elif missing_inputs:
            validity = GovernorValidity(
                status=GovernorValidityStatus.WARMING,
                observed_inputs=observed_inputs - len(missing_inputs),
                required_inputs=required_inputs,
                missing_inputs=tuple(missing_inputs),
            )
        else:
            validity = GovernorValidity(
                status=GovernorValidityStatus.VALID,
                observed_inputs=observed_inputs,
                required_inputs=required_inputs,
            )

        context_metadata: dict[str, object] = {
            "expansion_status": expansion.status.value,
            "expansion_decision": expansion.decision.value,
            "expansion_direction": expansion.direction.value
            if expansion.direction is not None
            else None,
        }
        if metadata:
            context_metadata.update(metadata)

        return GovernorContext(
            governor_name=self.config.governor_name,
            contour_name=self.config.contour_name,
            symbol=expansion.symbol,
            exchange=expansion.exchange,
            timeframe=expansion.timeframe,
            observed_at=reference_time,
            source=GovernorSource.POSITION_EXPANSION,
            expansion=expansion,
            validity=validity,
            metadata=context_metadata,
        )

    def _ingest_governor_context(
        self,
        context: GovernorContext,
        *,
        reference_time: datetime,
    ) -> PortfolioGovernorRuntimeUpdate:
        key = self._build_state_key(
            exchange=context.exchange,
            symbol=context.symbol,
            timeframe=context.timeframe,
        )
        self._contexts[key] = context
        previous_candidate = self._candidates.get(key)
        candidate = self._build_candidate_from_context(
            context=context,
            reference_time=reference_time,
            previous_candidate=previous_candidate,
        )
        candidate = self._expire_candidate_if_needed(candidate, reference_time=reference_time)
        self._candidates[key] = candidate

        payload = PortfolioGovernorPayload.from_candidate(candidate)
        event_type = self._resolve_event_type(candidate=candidate)
        self._update_diagnostics_for_candidate(candidate=candidate, event_type=event_type)

        return PortfolioGovernorRuntimeUpdate(
            context=context,
            candidate=candidate,
            event_type=event_type,
            emitted_payload=payload,
        )

    def _build_candidate_from_context(
        self,
        *,
        context: GovernorContext,
        reference_time: datetime,
        previous_candidate: PortfolioGovernorCandidate | None,
    ) -> PortfolioGovernorCandidate:
        freshness = GovernorFreshness(
            generated_at=reference_time,
            expires_at=reference_time + timedelta(seconds=self.config.max_candidate_age_seconds),
        )

        if context.validity.status == GovernorValidityStatus.INVALID:
            if self._should_invalidate_previous_candidate(previous_candidate):
                assert previous_candidate is not None
                return self._build_invalidated_candidate(
                    freshness=freshness,
                    context=context,
                    previous_candidate=previous_candidate,
                )
            return PortfolioGovernorCandidate(
                governor_id=self._resolve_governor_id(previous_candidate),
                contour_name=self.config.contour_name,
                governor_name=self.config.governor_name,
                symbol=context.symbol,
                exchange=context.exchange,
                timeframe=context.timeframe,
                source=context.source,
                freshness=freshness,
                validity=context.validity,
                status=GovernorStatus.REJECTED,
                decision=GovernorDecision.REJECT,
                direction=None,
                originating_expansion_id=context.expansion.expansion_id,
                confidence=context.expansion.confidence,
                priority_score=context.expansion.priority_score,
                capital_fraction=None,
                reason_code=GovernorReasonCode.GOVERNOR_REJECTED,
                metadata={"invalid_reason": context.validity.invalid_reason},
            )

        if context.validity.is_warming:
            if self._should_invalidate_previous_candidate(previous_candidate):
                assert previous_candidate is not None
                return self._build_invalidated_candidate(
                    freshness=freshness,
                    context=context,
                    previous_candidate=previous_candidate,
                )
            return PortfolioGovernorCandidate.candidate(
                contour_name=self.config.contour_name,
                governor_name=self.config.governor_name,
                symbol=context.symbol,
                exchange=context.exchange,
                timeframe=context.timeframe,
                source=context.source,
                freshness=freshness,
                validity=context.validity,
                decision=GovernorDecision.ABSTAIN,
                status=GovernorStatus.CANDIDATE,
                confidence=context.expansion.confidence,
                priority_score=context.expansion.priority_score,
                reason_code=GovernorReasonCode.CONTEXT_INCOMPLETE,
                metadata={"missing_inputs": context.validity.missing_inputs},
            )

        approved_candidate = self._evaluate_minimal_contour(
            context=context,
            freshness=freshness,
            previous_candidate=previous_candidate,
        )
        if approved_candidate is not None:
            return approved_candidate

        expansion = context.expansion
        return PortfolioGovernorCandidate(
            governor_id=self._resolve_governor_id(previous_candidate),
            contour_name=self.config.contour_name,
            governor_name=self.config.governor_name,
            symbol=context.symbol,
            exchange=context.exchange,
            timeframe=context.timeframe,
            source=context.source,
            freshness=freshness,
            validity=context.validity,
            status=GovernorStatus.ABSTAINED,
            decision=GovernorDecision.ABSTAIN,
            direction=None,
            originating_expansion_id=expansion.expansion_id,
            confidence=expansion.confidence,
            priority_score=expansion.priority_score,
            capital_fraction=None,
            reason_code=GovernorReasonCode.GOVERNOR_ABSTAINED,
            metadata={
                "expansion_status": expansion.status.value,
                "priority_score": str(expansion.priority_score or Decimal("0")),
            },
        )

    def _evaluate_minimal_contour(
        self,
        *,
        context: GovernorContext,
        freshness: GovernorFreshness,
        previous_candidate: PortfolioGovernorCandidate | None,
    ) -> PortfolioGovernorCandidate | None:
        expansion = context.expansion
        if not expansion.is_expandable or expansion.direction is None:
            return None

        confidence = expansion.confidence or Decimal("0")
        priority_score = expansion.priority_score or confidence
        if confidence < self.config.min_confidence_for_approval:
            return None
        if priority_score < self.config.min_priority_score_for_approval:
            return None

        return PortfolioGovernorCandidate(
            governor_id=self._resolve_governor_id(previous_candidate),
            contour_name=self.config.contour_name,
            governor_name=self.config.governor_name,
            symbol=context.symbol,
            exchange=context.exchange,
            timeframe=context.timeframe,
            source=context.source,
            freshness=freshness,
            validity=context.validity,
            status=GovernorStatus.APPROVED,
            decision=GovernorDecision.APPROVE,
            direction=GovernorDirection(expansion.direction.value),
            originating_expansion_id=expansion.expansion_id,
            confidence=confidence,
            priority_score=priority_score,
            capital_fraction=self.config.default_capital_fraction,
            reason_code=GovernorReasonCode.CONTEXT_READY,
            metadata={
                "expansion_status": expansion.status.value,
                "expansion_direction": expansion.direction.value,
                "priority_score": str(priority_score),
                "capital_fraction": str(self.config.default_capital_fraction),
            },
        )

    def _build_invalidated_candidate(
        self,
        *,
        freshness: GovernorFreshness,
        context: GovernorContext,
        previous_candidate: PortfolioGovernorCandidate,
    ) -> PortfolioGovernorCandidate:
        metadata = previous_candidate.metadata.copy()
        metadata["invalid_reason"] = context.validity.invalid_reason or ",".join(
            context.validity.missing_inputs
        )
        invalid_validity = GovernorValidity(
            status=GovernorValidityStatus.INVALID,
            observed_inputs=context.validity.observed_inputs,
            required_inputs=context.validity.required_inputs,
            missing_inputs=context.validity.missing_inputs,
            invalid_reason=context.validity.invalid_reason or "portfolio_governor_invalidated",
        )
        return PortfolioGovernorCandidate(
            governor_id=previous_candidate.governor_id,
            contour_name=previous_candidate.contour_name,
            governor_name=previous_candidate.governor_name,
            symbol=previous_candidate.symbol,
            exchange=previous_candidate.exchange,
            timeframe=previous_candidate.timeframe,
            source=previous_candidate.source,
            freshness=freshness,
            validity=invalid_validity,
            status=GovernorStatus.INVALIDATED,
            decision=GovernorDecision.REJECT,
            direction=None,
            originating_expansion_id=previous_candidate.originating_expansion_id,
            confidence=previous_candidate.confidence,
            priority_score=previous_candidate.priority_score,
            capital_fraction=None,
            reason_code=GovernorReasonCode.GOVERNOR_INVALIDATED,
            metadata=metadata,
        )

    def _expire_candidate_if_needed(
        self,
        candidate: PortfolioGovernorCandidate,
        *,
        reference_time: datetime,
    ) -> PortfolioGovernorCandidate:
        if candidate.status == GovernorStatus.EXPIRED:
            return candidate
        if not candidate.freshness.is_expired_at(reference_time):
            return candidate
        expired_validity = candidate.validity
        if expired_validity.status == GovernorValidityStatus.VALID:
            expired_validity = GovernorValidity(
                status=GovernorValidityStatus.INVALID,
                observed_inputs=expired_validity.observed_inputs,
                required_inputs=expired_validity.required_inputs,
                missing_inputs=expired_validity.missing_inputs,
                invalid_reason="portfolio_governor_expired",
            )
        return replace(
            candidate,
            validity=expired_validity,
            status=GovernorStatus.EXPIRED,
            capital_fraction=None,
            reason_code=GovernorReasonCode.GOVERNOR_EXPIRED,
        )

    def _resolve_event_type(
        self,
        *,
        candidate: PortfolioGovernorCandidate,
    ) -> PortfolioGovernorEventType:
        if candidate.status in {GovernorStatus.INVALIDATED, GovernorStatus.EXPIRED}:
            return PortfolioGovernorEventType.PORTFOLIO_GOVERNOR_INVALIDATED
        if candidate.status == GovernorStatus.APPROVED:
            return PortfolioGovernorEventType.PORTFOLIO_GOVERNOR_APPROVED
        return PortfolioGovernorEventType.PORTFOLIO_GOVERNOR_CANDIDATE_UPDATED

    def _update_diagnostics_for_candidate(
        self,
        *,
        candidate: PortfolioGovernorCandidate,
        event_type: PortfolioGovernorEventType,
    ) -> None:
        tracked_context_keys = len(self._contexts)
        tracked_governor_keys = len(self._candidates)
        approved_keys = sum(
            1
            for snapshot in self._candidates.values()
            if snapshot.status == GovernorStatus.APPROVED
        )
        abstained_keys = sum(
            1
            for snapshot in self._candidates.values()
            if snapshot.status == GovernorStatus.ABSTAINED
        )
        rejected_keys = sum(
            1
            for snapshot in self._candidates.values()
            if snapshot.status == GovernorStatus.REJECTED
        )
        invalidated_governor_keys = sum(
            1
            for snapshot in self._candidates.values()
            if snapshot.status == GovernorStatus.INVALIDATED
        )
        expired_governor_keys = sum(
            1 for snapshot in self._candidates.values() if snapshot.status == GovernorStatus.EXPIRED
        )

        readiness_reasons: tuple[str, ...] = ()
        lifecycle_state = PortfolioGovernorRuntimeLifecycleState.READY
        ready = True

        if tracked_context_keys == 0:
            lifecycle_state = PortfolioGovernorRuntimeLifecycleState.WARMING
            ready = False
            readiness_reasons = ("no_portfolio_governor_context_processed",)
        elif candidate.validity.is_warming:
            lifecycle_state = PortfolioGovernorRuntimeLifecycleState.WARMING
            ready = False
            readiness_reasons = tuple(candidate.validity.missing_inputs) or (
                "portfolio_governor_context_warming",
            )
        elif self._diagnostics.degraded_reasons:
            lifecycle_state = PortfolioGovernorRuntimeLifecycleState.DEGRADED
            ready = False
            readiness_reasons = ("runtime_degraded",)

        self._refresh_diagnostics(
            lifecycle_state=lifecycle_state,
            ready=ready,
            tracked_context_keys=tracked_context_keys,
            tracked_governor_keys=tracked_governor_keys,
            approved_keys=approved_keys,
            abstained_keys=abstained_keys,
            rejected_keys=rejected_keys,
            invalidated_governor_keys=invalidated_governor_keys,
            expired_governor_keys=expired_governor_keys,
            last_expansion_id=str(candidate.originating_expansion_id)
            if candidate.originating_expansion_id is not None
            else None,
            last_governor_id=str(candidate.governor_id),
            last_event_type=event_type.value,
            readiness_reasons=readiness_reasons,
        )

    def _build_state_key(
        self,
        *,
        exchange: str,
        symbol: str,
        timeframe: MarketDataTimeframe,
    ) -> PortfolioGovernorStateKey:
        return (
            exchange,
            symbol,
            timeframe,
            self.config.contour_name,
            self.config.governor_name,
        )

    @staticmethod
    def _should_invalidate_previous_candidate(
        previous_candidate: PortfolioGovernorCandidate | None,
    ) -> bool:
        return (
            previous_candidate is not None
            and previous_candidate.validity.is_valid
            and previous_candidate.status
            not in {GovernorStatus.EXPIRED, GovernorStatus.INVALIDATED}
        )

    @staticmethod
    def _resolve_governor_id(previous_candidate: PortfolioGovernorCandidate | None) -> UUID:
        if previous_candidate is not None:
            return previous_candidate.governor_id
        return uuid4()

    def _ensure_started(self, operation: str) -> None:
        if not self._started:
            raise RuntimeError(
                f"PortfolioGovernorRuntime не запущен. Операция {operation} недоступна до start()."
            )

    def _refresh_diagnostics(self, **updates: object) -> None:
        current = asdict(self._diagnostics)
        current.update(updates)
        self._diagnostics = PortfolioGovernorRuntimeDiagnostics(
            started=self._started,
            ready=bool(current["ready"]),
            lifecycle_state=PortfolioGovernorRuntimeLifecycleState(current["lifecycle_state"]),
            tracked_context_keys=int(current["tracked_context_keys"]),
            tracked_governor_keys=int(current["tracked_governor_keys"]),
            approved_keys=int(current["approved_keys"]),
            abstained_keys=int(current["abstained_keys"]),
            rejected_keys=int(current["rejected_keys"]),
            invalidated_governor_keys=int(current["invalidated_governor_keys"]),
            expired_governor_keys=int(current["expired_governor_keys"]),
            last_expansion_id=current["last_expansion_id"],
            last_governor_id=current["last_governor_id"],
            last_event_type=current["last_event_type"],
            last_failure_reason=current["last_failure_reason"],
            readiness_reasons=list(current["readiness_reasons"]),
            degraded_reasons=list(current["degraded_reasons"]),
        )
        self._push_diagnostics()

    def _push_diagnostics(self) -> None:
        if self._diagnostics_sink is not None:
            self._diagnostics_sink(self._diagnostics.to_dict())


def create_portfolio_governor_runtime(
    config: PortfolioGovernorRuntimeConfig | None = None,
    *,
    diagnostics_sink: Callable[[dict[str, object]], None] | None = None,
) -> PortfolioGovernorRuntime:
    """Фабрика explicit runtime foundation portfolio-governor layer."""
    return PortfolioGovernorRuntime(
        config=config,
        diagnostics_sink=diagnostics_sink,
    )


__all__ = [
    "PortfolioGovernorRuntime",
    "PortfolioGovernorRuntimeConfig",
    "PortfolioGovernorRuntimeDiagnostics",
    "PortfolioGovernorRuntimeLifecycleState",
    "PortfolioGovernorRuntimeUpdate",
    "PortfolioGovernorStateKey",
    "create_portfolio_governor_runtime",
]

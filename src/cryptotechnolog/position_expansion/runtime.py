"""
Узкий explicit runtime foundation для Phase 13 Position Expansion Foundation.

Этот runtime:
- стартует и останавливается явно;
- не делает hidden bootstrap;
- собирает typed expansion context из orchestration truth;
- поддерживает один минимальный deterministic add-to-position contour;
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
from cryptotechnolog.orchestration import OrchestrationDecisionCandidate, OrchestrationStatus

from .events import PositionExpansionEventType, PositionExpansionPayload
from .models import (
    ExpansionContext,
    ExpansionDecision,
    ExpansionDirection,
    ExpansionFreshness,
    ExpansionReasonCode,
    ExpansionSource,
    ExpansionStatus,
    ExpansionValidity,
    ExpansionValidityStatus,
    PositionExpansionCandidate,
)

if TYPE_CHECKING:
    from collections.abc import Callable


type PositionExpansionStateKey = tuple[str, str, MarketDataTimeframe, str, str]


class PositionExpansionRuntimeLifecycleState(StrEnum):
    """Lifecycle-состояние position-expansion runtime."""

    NOT_STARTED = "not_started"
    WARMING = "warming"
    READY = "ready"
    DEGRADED = "degraded"
    STOPPED = "stopped"


@dataclass(slots=True, frozen=True)
class PositionExpansionRuntimeConfig:
    """Typed runtime-конфигурация следующего шага P_13."""

    contour_name: str = "phase13_position_expansion_contour"
    expansion_name: str = "phase13_position_expansion"
    max_candidate_age_seconds: int = 300
    min_confidence_for_add: Decimal = Decimal("0.5000")
    min_priority_score_for_add: Decimal = Decimal("0.5000")

    def __post_init__(self) -> None:
        if self.max_candidate_age_seconds <= 0:
            raise ValueError("max_candidate_age_seconds должен быть положительным")
        if not (Decimal("0") <= self.min_confidence_for_add <= Decimal("1")):
            raise ValueError("min_confidence_for_add должен находиться в диапазоне [0, 1]")
        if not (Decimal("0") <= self.min_priority_score_for_add <= Decimal("1")):
            raise ValueError("min_priority_score_for_add должен находиться в диапазоне [0, 1]")


@dataclass(slots=True)
class PositionExpansionRuntimeDiagnostics:
    """Operator-visible diagnostics contract position-expansion runtime."""

    started: bool = False
    ready: bool = False
    lifecycle_state: PositionExpansionRuntimeLifecycleState = (
        PositionExpansionRuntimeLifecycleState.NOT_STARTED
    )
    tracked_context_keys: int = 0
    tracked_expansion_keys: int = 0
    expandable_keys: int = 0
    abstained_keys: int = 0
    rejected_keys: int = 0
    invalidated_expansion_keys: int = 0
    expired_expansion_keys: int = 0
    last_decision_id: str | None = None
    last_expansion_id: str | None = None
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
            "tracked_expansion_keys": self.tracked_expansion_keys,
            "expandable_keys": self.expandable_keys,
            "abstained_keys": self.abstained_keys,
            "rejected_keys": self.rejected_keys,
            "invalidated_expansion_keys": self.invalidated_expansion_keys,
            "expired_expansion_keys": self.expired_expansion_keys,
            "last_decision_id": self.last_decision_id,
            "last_expansion_id": self.last_expansion_id,
            "last_event_type": self.last_event_type,
            "last_failure_reason": self.last_failure_reason,
            "readiness_reasons": list(self.readiness_reasons),
            "degraded_reasons": list(self.degraded_reasons),
        }


@dataclass(slots=True, frozen=True)
class PositionExpansionRuntimeUpdate:
    """Typed update contract position-expansion runtime foundation."""

    context: ExpansionContext
    candidate: PositionExpansionCandidate | None
    event_type: PositionExpansionEventType
    emitted_payload: PositionExpansionPayload | None = None


class PositionExpansionRuntime:
    """Explicit runtime foundation для position-expansion layer Phase 13."""

    def __init__(
        self,
        config: PositionExpansionRuntimeConfig | None = None,
        *,
        diagnostics_sink: Callable[[dict[str, object]], None] | None = None,
    ) -> None:
        self.config = config or PositionExpansionRuntimeConfig()
        self._diagnostics_sink = diagnostics_sink
        self._diagnostics = PositionExpansionRuntimeDiagnostics()
        self._started = False
        self._contexts: dict[PositionExpansionStateKey, ExpansionContext] = {}
        self._candidates: dict[PositionExpansionStateKey, PositionExpansionCandidate] = {}
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
            lifecycle_state=PositionExpansionRuntimeLifecycleState.WARMING,
            ready=False,
            last_failure_reason=None,
            readiness_reasons=("no_position_expansion_context_processed",),
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
            lifecycle_state=PositionExpansionRuntimeLifecycleState.STOPPED,
            ready=False,
            tracked_context_keys=0,
            tracked_expansion_keys=0,
            expandable_keys=0,
            abstained_keys=0,
            rejected_keys=0,
            invalidated_expansion_keys=0,
            expired_expansion_keys=0,
            last_decision_id=None,
            last_expansion_id=None,
            last_event_type=None,
            last_failure_reason=None,
            readiness_reasons=("runtime_stopped",),
            degraded_reasons=(),
        )

    def ingest_decision(
        self,
        *,
        decision: OrchestrationDecisionCandidate,
        reference_time: datetime,
        metadata: dict[str, object] | None = None,
    ) -> PositionExpansionRuntimeUpdate:
        """Принять orchestration truth, собрать expansion context и обновить state."""
        self._ensure_started("ingest_decision")
        context = self._assemble_expansion_context(
            decision=decision,
            reference_time=reference_time,
            metadata=metadata,
        )
        return self._ingest_expansion_context(context, reference_time=reference_time)

    def get_candidate(
        self,
        *,
        symbol: str,
        exchange: str,
        timeframe: MarketDataTimeframe,
    ) -> PositionExpansionCandidate | None:
        """Вернуть текущее expansion state по ключу."""
        return self._candidates.get(
            self._build_state_key(exchange=exchange, symbol=symbol, timeframe=timeframe)
        )

    def get_context(
        self,
        *,
        symbol: str,
        exchange: str,
        timeframe: MarketDataTimeframe,
    ) -> ExpansionContext | None:
        """Вернуть последний assembled expansion context."""
        return self._contexts.get(
            self._build_state_key(exchange=exchange, symbol=symbol, timeframe=timeframe)
        )

    def expire_candidates(
        self,
        *,
        reference_time: datetime,
    ) -> tuple[PositionExpansionRuntimeUpdate, ...]:
        """Переоценить lifecycle truth относительно reference time."""
        self._ensure_started("expire_candidates")
        updates: list[PositionExpansionRuntimeUpdate] = []
        for key, candidate in tuple(self._candidates.items()):
            updated = self._expire_candidate_if_needed(candidate, reference_time=reference_time)
            if updated is not candidate:
                self._candidates[key] = updated
                context = self._contexts[key]
                payload = PositionExpansionPayload.from_candidate(updated)
                updates.append(
                    PositionExpansionRuntimeUpdate(
                        context=context,
                        candidate=updated,
                        event_type=PositionExpansionEventType.POSITION_EXPANSION_INVALIDATED,
                        emitted_payload=payload,
                    )
                )
                self._update_diagnostics_for_candidate(
                    candidate=updated,
                    event_type=PositionExpansionEventType.POSITION_EXPANSION_INVALIDATED,
                )
        return tuple(updates)

    def mark_degraded(self, reason: str) -> None:
        """Зафиксировать деградацию ingest/runtime path."""
        self._refresh_diagnostics(
            lifecycle_state=PositionExpansionRuntimeLifecycleState.DEGRADED,
            ready=False,
            last_failure_reason=reason,
            degraded_reasons=(reason,),
        )

    def get_runtime_diagnostics(self) -> dict[str, object]:
        """Вернуть operator-visible diagnostics."""
        return self._diagnostics.to_dict()

    def _assemble_expansion_context(
        self,
        *,
        decision: OrchestrationDecisionCandidate,
        reference_time: datetime,
        metadata: dict[str, object] | None,
    ) -> ExpansionContext:
        observed_inputs = 1
        required_inputs = 1
        missing_inputs: list[str] = []
        invalid_reason: str | None = None

        if (
            decision.freshness.is_expired_at(reference_time)
            or decision.status == OrchestrationStatus.EXPIRED
        ):
            invalid_reason = "orchestration_decision_expired"
        elif decision.status == OrchestrationStatus.INVALIDATED:
            invalid_reason = "orchestration_decision_invalidated"
        elif decision.status == OrchestrationStatus.ABSTAINED:
            invalid_reason = "orchestration_decision_abstained"
        elif decision.status == OrchestrationStatus.CANDIDATE:
            missing_inputs.append("forwardable_decision")
        elif decision.is_forwarded:
            pass
        else:
            invalid_reason = "orchestration_decision_not_forwardable"

        if invalid_reason is not None:
            validity = ExpansionValidity(
                status=ExpansionValidityStatus.INVALID,
                observed_inputs=observed_inputs,
                required_inputs=required_inputs,
                invalid_reason=invalid_reason,
            )
        elif missing_inputs:
            validity = ExpansionValidity(
                status=ExpansionValidityStatus.WARMING,
                observed_inputs=observed_inputs - len(missing_inputs),
                required_inputs=required_inputs,
                missing_inputs=tuple(missing_inputs),
            )
        else:
            validity = ExpansionValidity(
                status=ExpansionValidityStatus.VALID,
                observed_inputs=observed_inputs,
                required_inputs=required_inputs,
            )

        context_metadata: dict[str, object] = {
            "decision_status": decision.status.value,
            "decision_value": decision.decision.value,
            "decision_direction": decision.direction.value
            if decision.direction is not None
            else None,
        }
        if metadata:
            context_metadata.update(metadata)

        return ExpansionContext(
            expansion_name=self.config.expansion_name,
            contour_name=self.config.contour_name,
            symbol=decision.symbol,
            exchange=decision.exchange,
            timeframe=decision.timeframe,
            observed_at=reference_time,
            source=ExpansionSource.ORCHESTRATION_DECISION,
            decision=decision,
            validity=validity,
            metadata=context_metadata,
        )

    def _ingest_expansion_context(
        self,
        context: ExpansionContext,
        *,
        reference_time: datetime,
    ) -> PositionExpansionRuntimeUpdate:
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

        payload = PositionExpansionPayload.from_candidate(candidate)
        event_type = self._resolve_event_type(candidate=candidate)
        self._update_diagnostics_for_candidate(candidate=candidate, event_type=event_type)

        return PositionExpansionRuntimeUpdate(
            context=context,
            candidate=candidate,
            event_type=event_type,
            emitted_payload=payload,
        )

    def _build_candidate_from_context(
        self,
        *,
        context: ExpansionContext,
        reference_time: datetime,
        previous_candidate: PositionExpansionCandidate | None,
    ) -> PositionExpansionCandidate:
        freshness = ExpansionFreshness(
            generated_at=reference_time,
            expires_at=reference_time + timedelta(seconds=self.config.max_candidate_age_seconds),
        )

        if context.validity.status == ExpansionValidityStatus.INVALID:
            if self._should_invalidate_previous_candidate(previous_candidate):
                assert previous_candidate is not None
                return self._build_invalidated_candidate(
                    freshness=freshness,
                    context=context,
                    previous_candidate=previous_candidate,
                )
            return PositionExpansionCandidate(
                expansion_id=self._resolve_expansion_id(previous_candidate),
                contour_name=self.config.contour_name,
                expansion_name=self.config.expansion_name,
                symbol=context.symbol,
                exchange=context.exchange,
                timeframe=context.timeframe,
                source=context.source,
                freshness=freshness,
                validity=context.validity,
                status=ExpansionStatus.REJECTED,
                decision=ExpansionDecision.REJECT,
                direction=None,
                originating_decision_id=context.decision.decision_id,
                confidence=context.decision.confidence,
                priority_score=context.decision.priority_score,
                reason_code=ExpansionReasonCode.EXPANSION_REJECTED,
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
            return PositionExpansionCandidate.candidate(
                contour_name=self.config.contour_name,
                expansion_name=self.config.expansion_name,
                symbol=context.symbol,
                exchange=context.exchange,
                timeframe=context.timeframe,
                source=context.source,
                freshness=freshness,
                validity=context.validity,
                decision=ExpansionDecision.ABSTAIN,
                status=ExpansionStatus.CANDIDATE,
                confidence=context.decision.confidence,
                priority_score=context.decision.priority_score,
                reason_code=ExpansionReasonCode.CONTEXT_INCOMPLETE,
                metadata={"missing_inputs": context.validity.missing_inputs},
            )

        expandable_candidate = self._evaluate_minimal_contour(
            context=context,
            freshness=freshness,
            previous_candidate=previous_candidate,
        )
        if expandable_candidate is not None:
            return expandable_candidate

        decision = context.decision
        return PositionExpansionCandidate(
            expansion_id=self._resolve_expansion_id(previous_candidate),
            contour_name=self.config.contour_name,
            expansion_name=self.config.expansion_name,
            symbol=context.symbol,
            exchange=context.exchange,
            timeframe=context.timeframe,
            source=context.source,
            freshness=freshness,
            validity=context.validity,
            status=ExpansionStatus.ABSTAINED,
            decision=ExpansionDecision.ABSTAIN,
            direction=None,
            originating_decision_id=decision.decision_id,
            confidence=decision.confidence,
            priority_score=decision.priority_score,
            reason_code=ExpansionReasonCode.EXPANSION_ABSTAINED,
            metadata={
                "decision_status": decision.status.value,
                "priority_score": str(decision.priority_score or Decimal("0")),
            },
        )

    def _evaluate_minimal_contour(
        self,
        *,
        context: ExpansionContext,
        freshness: ExpansionFreshness,
        previous_candidate: PositionExpansionCandidate | None,
    ) -> PositionExpansionCandidate | None:
        decision = context.decision
        if not decision.is_forwarded or decision.direction is None:
            return None

        confidence = decision.confidence or Decimal("0")
        priority_score = decision.priority_score or confidence
        if confidence < self.config.min_confidence_for_add:
            return None
        if priority_score < self.config.min_priority_score_for_add:
            return None

        return PositionExpansionCandidate(
            expansion_id=self._resolve_expansion_id(previous_candidate),
            contour_name=self.config.contour_name,
            expansion_name=self.config.expansion_name,
            symbol=context.symbol,
            exchange=context.exchange,
            timeframe=context.timeframe,
            source=context.source,
            freshness=freshness,
            validity=context.validity,
            status=ExpansionStatus.EXPANDABLE,
            decision=ExpansionDecision.ADD,
            direction=ExpansionDirection(decision.direction.value),
            originating_decision_id=decision.decision_id,
            confidence=confidence,
            priority_score=priority_score,
            reason_code=ExpansionReasonCode.CONTEXT_READY,
            metadata={
                "decision_status": decision.status.value,
                "decision_direction": decision.direction.value,
                "priority_score": str(priority_score),
            },
        )

    def _build_invalidated_candidate(
        self,
        *,
        freshness: ExpansionFreshness,
        context: ExpansionContext,
        previous_candidate: PositionExpansionCandidate,
    ) -> PositionExpansionCandidate:
        metadata = previous_candidate.metadata.copy()
        metadata["invalid_reason"] = context.validity.invalid_reason or ",".join(
            context.validity.missing_inputs
        )
        invalid_validity = ExpansionValidity(
            status=ExpansionValidityStatus.INVALID,
            observed_inputs=context.validity.observed_inputs,
            required_inputs=context.validity.required_inputs,
            missing_inputs=context.validity.missing_inputs,
            invalid_reason=context.validity.invalid_reason or "position_expansion_invalidated",
        )
        return PositionExpansionCandidate(
            expansion_id=previous_candidate.expansion_id,
            contour_name=previous_candidate.contour_name,
            expansion_name=previous_candidate.expansion_name,
            symbol=previous_candidate.symbol,
            exchange=previous_candidate.exchange,
            timeframe=previous_candidate.timeframe,
            source=previous_candidate.source,
            freshness=freshness,
            validity=invalid_validity,
            status=ExpansionStatus.INVALIDATED,
            decision=ExpansionDecision.REJECT,
            direction=None,
            originating_decision_id=previous_candidate.originating_decision_id,
            confidence=previous_candidate.confidence,
            priority_score=previous_candidate.priority_score,
            reason_code=ExpansionReasonCode.EXPANSION_INVALIDATED,
            metadata=metadata,
        )

    def _expire_candidate_if_needed(
        self,
        candidate: PositionExpansionCandidate,
        *,
        reference_time: datetime,
    ) -> PositionExpansionCandidate:
        if candidate.status == ExpansionStatus.EXPIRED:
            return candidate
        if not candidate.freshness.is_expired_at(reference_time):
            return candidate
        expired_validity = candidate.validity
        if expired_validity.status == ExpansionValidityStatus.VALID:
            expired_validity = ExpansionValidity(
                status=ExpansionValidityStatus.INVALID,
                observed_inputs=expired_validity.observed_inputs,
                required_inputs=expired_validity.required_inputs,
                missing_inputs=expired_validity.missing_inputs,
                invalid_reason="position_expansion_expired",
            )
        return replace(
            candidate,
            validity=expired_validity,
            status=ExpansionStatus.EXPIRED,
            reason_code=ExpansionReasonCode.EXPANSION_EXPIRED,
        )

    def _resolve_event_type(
        self,
        *,
        candidate: PositionExpansionCandidate,
    ) -> PositionExpansionEventType:
        if candidate.status in {ExpansionStatus.INVALIDATED, ExpansionStatus.EXPIRED}:
            return PositionExpansionEventType.POSITION_EXPANSION_INVALIDATED
        if candidate.status == ExpansionStatus.EXPANDABLE:
            return PositionExpansionEventType.POSITION_EXPANSION_APPROVED
        return PositionExpansionEventType.POSITION_EXPANSION_CANDIDATE_UPDATED

    def _update_diagnostics_for_candidate(
        self,
        *,
        candidate: PositionExpansionCandidate,
        event_type: PositionExpansionEventType,
    ) -> None:
        tracked_context_keys = len(self._contexts)
        tracked_expansion_keys = len(self._candidates)
        expandable_keys = sum(
            1
            for snapshot in self._candidates.values()
            if snapshot.status == ExpansionStatus.EXPANDABLE
        )
        abstained_keys = sum(
            1
            for snapshot in self._candidates.values()
            if snapshot.status == ExpansionStatus.ABSTAINED
        )
        rejected_keys = sum(
            1
            for snapshot in self._candidates.values()
            if snapshot.status == ExpansionStatus.REJECTED
        )
        invalidated_expansion_keys = sum(
            1
            for snapshot in self._candidates.values()
            if snapshot.status == ExpansionStatus.INVALIDATED
        )
        expired_expansion_keys = sum(
            1
            for snapshot in self._candidates.values()
            if snapshot.status == ExpansionStatus.EXPIRED
        )

        readiness_reasons: tuple[str, ...] = ()
        lifecycle_state = PositionExpansionRuntimeLifecycleState.READY
        ready = True

        if tracked_context_keys == 0:
            lifecycle_state = PositionExpansionRuntimeLifecycleState.WARMING
            ready = False
            readiness_reasons = ("no_position_expansion_context_processed",)
        elif candidate.validity.is_warming:
            lifecycle_state = PositionExpansionRuntimeLifecycleState.WARMING
            ready = False
            readiness_reasons = tuple(candidate.validity.missing_inputs) or (
                "position_expansion_context_warming",
            )
        elif self._diagnostics.degraded_reasons:
            lifecycle_state = PositionExpansionRuntimeLifecycleState.DEGRADED
            ready = False
            readiness_reasons = ("runtime_degraded",)

        self._refresh_diagnostics(
            lifecycle_state=lifecycle_state,
            ready=ready,
            tracked_context_keys=tracked_context_keys,
            tracked_expansion_keys=tracked_expansion_keys,
            expandable_keys=expandable_keys,
            abstained_keys=abstained_keys,
            rejected_keys=rejected_keys,
            invalidated_expansion_keys=invalidated_expansion_keys,
            expired_expansion_keys=expired_expansion_keys,
            last_decision_id=str(candidate.originating_decision_id)
            if candidate.originating_decision_id is not None
            else None,
            last_expansion_id=str(candidate.expansion_id),
            last_event_type=event_type.value,
            readiness_reasons=readiness_reasons,
        )

    def _build_state_key(
        self,
        *,
        exchange: str,
        symbol: str,
        timeframe: MarketDataTimeframe,
    ) -> PositionExpansionStateKey:
        return (
            exchange,
            symbol,
            timeframe,
            self.config.contour_name,
            self.config.expansion_name,
        )

    @staticmethod
    def _should_invalidate_previous_candidate(
        previous_candidate: PositionExpansionCandidate | None,
    ) -> bool:
        return (
            previous_candidate is not None
            and previous_candidate.validity.is_valid
            and previous_candidate.status
            not in {ExpansionStatus.EXPIRED, ExpansionStatus.INVALIDATED}
        )

    @staticmethod
    def _resolve_expansion_id(previous_candidate: PositionExpansionCandidate | None) -> UUID:
        if previous_candidate is not None:
            return previous_candidate.expansion_id
        return uuid4()

    def _ensure_started(self, operation: str) -> None:
        if not self._started:
            raise RuntimeError(
                f"PositionExpansionRuntime не запущен. Операция {operation} недоступна до start()."
            )

    def _refresh_diagnostics(self, **updates: object) -> None:
        current = asdict(self._diagnostics)
        current.update(updates)
        self._diagnostics = PositionExpansionRuntimeDiagnostics(
            started=self._started,
            ready=bool(current["ready"]),
            lifecycle_state=PositionExpansionRuntimeLifecycleState(current["lifecycle_state"]),
            tracked_context_keys=int(current["tracked_context_keys"]),
            tracked_expansion_keys=int(current["tracked_expansion_keys"]),
            expandable_keys=int(current["expandable_keys"]),
            abstained_keys=int(current["abstained_keys"]),
            rejected_keys=int(current["rejected_keys"]),
            invalidated_expansion_keys=int(current["invalidated_expansion_keys"]),
            expired_expansion_keys=int(current["expired_expansion_keys"]),
            last_decision_id=current["last_decision_id"],
            last_expansion_id=current["last_expansion_id"],
            last_event_type=current["last_event_type"],
            last_failure_reason=current["last_failure_reason"],
            readiness_reasons=list(current["readiness_reasons"]),
            degraded_reasons=list(current["degraded_reasons"]),
        )
        self._push_diagnostics()

    def _push_diagnostics(self) -> None:
        if self._diagnostics_sink is not None:
            self._diagnostics_sink(self._diagnostics.to_dict())


def create_position_expansion_runtime(
    config: PositionExpansionRuntimeConfig | None = None,
    *,
    diagnostics_sink: Callable[[dict[str, object]], None] | None = None,
) -> PositionExpansionRuntime:
    """Фабрика explicit runtime foundation position-expansion layer."""
    return PositionExpansionRuntime(
        config=config,
        diagnostics_sink=diagnostics_sink,
    )


__all__ = [
    "PositionExpansionRuntime",
    "PositionExpansionRuntimeConfig",
    "PositionExpansionRuntimeDiagnostics",
    "PositionExpansionRuntimeLifecycleState",
    "PositionExpansionRuntimeUpdate",
    "PositionExpansionStateKey",
    "create_position_expansion_runtime",
]

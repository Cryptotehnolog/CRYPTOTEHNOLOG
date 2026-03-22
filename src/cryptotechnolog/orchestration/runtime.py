"""
Узкий explicit runtime foundation для Phase 12 Strategy Orchestration / Meta Layer.

Этот runtime:
- стартует и останавливается явно;
- не делает hidden bootstrap;
- собирает typed orchestration context из opportunity truth;
- поддерживает один минимальный deterministic orchestration contour;
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
from cryptotechnolog.opportunity import OpportunitySelectionCandidate, OpportunityStatus

from .events import OrchestrationDecisionPayload, OrchestrationEventType
from .models import (
    OrchestrationContext,
    OrchestrationDecision,
    OrchestrationDecisionCandidate,
    OrchestrationFreshness,
    OrchestrationReasonCode,
    OrchestrationSource,
    OrchestrationStatus,
    OrchestrationValidity,
    OrchestrationValidityStatus,
)

if TYPE_CHECKING:
    from collections.abc import Callable


type OrchestrationStateKey = tuple[str, str, MarketDataTimeframe, str, str]


class OrchestrationRuntimeLifecycleState(StrEnum):
    """Lifecycle-состояние orchestration runtime."""

    NOT_STARTED = "not_started"
    WARMING = "warming"
    READY = "ready"
    DEGRADED = "degraded"
    STOPPED = "stopped"


@dataclass(slots=True, frozen=True)
class OrchestrationRuntimeConfig:
    """Typed runtime-конфигурация следующего шага P_12."""

    contour_name: str = "phase12_orchestration_contour"
    orchestration_name: str = "phase12_meta_orchestration"
    max_decision_age_seconds: int = 300
    min_selection_confidence_for_forward: Decimal = Decimal("0.5000")
    min_priority_score_for_forward: Decimal = Decimal("0.5000")

    def __post_init__(self) -> None:
        if self.max_decision_age_seconds <= 0:
            raise ValueError("max_decision_age_seconds должен быть положительным")
        if not (Decimal("0") <= self.min_selection_confidence_for_forward <= Decimal("1")):
            raise ValueError(
                "min_selection_confidence_for_forward должен находиться в диапазоне [0, 1]"
            )
        if not (Decimal("0") <= self.min_priority_score_for_forward <= Decimal("1")):
            raise ValueError("min_priority_score_for_forward должен находиться в диапазоне [0, 1]")


@dataclass(slots=True)
class OrchestrationRuntimeDiagnostics:
    """Operator-visible diagnostics contract orchestration runtime."""

    started: bool = False
    ready: bool = False
    lifecycle_state: OrchestrationRuntimeLifecycleState = (
        OrchestrationRuntimeLifecycleState.NOT_STARTED
    )
    tracked_context_keys: int = 0
    tracked_decision_keys: int = 0
    forwarded_keys: int = 0
    abstained_keys: int = 0
    invalidated_decision_keys: int = 0
    expired_decision_keys: int = 0
    last_selection_id: str | None = None
    last_decision_id: str | None = None
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
            "tracked_decision_keys": self.tracked_decision_keys,
            "forwarded_keys": self.forwarded_keys,
            "abstained_keys": self.abstained_keys,
            "invalidated_decision_keys": self.invalidated_decision_keys,
            "expired_decision_keys": self.expired_decision_keys,
            "last_selection_id": self.last_selection_id,
            "last_decision_id": self.last_decision_id,
            "last_event_type": self.last_event_type,
            "last_failure_reason": self.last_failure_reason,
            "readiness_reasons": list(self.readiness_reasons),
            "degraded_reasons": list(self.degraded_reasons),
        }


@dataclass(slots=True, frozen=True)
class OrchestrationRuntimeUpdate:
    """Typed update contract orchestration runtime foundation."""

    context: OrchestrationContext
    decision: OrchestrationDecisionCandidate | None
    event_type: OrchestrationEventType
    emitted_payload: OrchestrationDecisionPayload | None = None


class OrchestrationRuntime:
    """Explicit runtime foundation для orchestration layer Phase 12."""

    def __init__(
        self,
        config: OrchestrationRuntimeConfig | None = None,
        *,
        diagnostics_sink: Callable[[dict[str, object]], None] | None = None,
    ) -> None:
        self.config = config or OrchestrationRuntimeConfig()
        self._diagnostics_sink = diagnostics_sink
        self._diagnostics = OrchestrationRuntimeDiagnostics()
        self._started = False
        self._contexts: dict[OrchestrationStateKey, OrchestrationContext] = {}
        self._decisions: dict[OrchestrationStateKey, OrchestrationDecisionCandidate] = {}
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
            lifecycle_state=OrchestrationRuntimeLifecycleState.WARMING,
            ready=False,
            last_failure_reason=None,
            readiness_reasons=("no_orchestration_context_processed",),
            degraded_reasons=(),
        )

    async def stop(self) -> None:
        """Остановить runtime и очистить operator-visible state."""
        if not self._started:
            return
        self._started = False
        self._contexts = {}
        self._decisions = {}
        self._refresh_diagnostics(
            lifecycle_state=OrchestrationRuntimeLifecycleState.STOPPED,
            ready=False,
            tracked_context_keys=0,
            tracked_decision_keys=0,
            forwarded_keys=0,
            abstained_keys=0,
            invalidated_decision_keys=0,
            expired_decision_keys=0,
            last_selection_id=None,
            last_decision_id=None,
            last_event_type=None,
            last_failure_reason=None,
            readiness_reasons=("runtime_stopped",),
            degraded_reasons=(),
        )

    def mark_degraded(self, reason: str) -> None:
        """Зафиксировать деградацию runtime/ingest path."""
        self._refresh_diagnostics(
            lifecycle_state=OrchestrationRuntimeLifecycleState.DEGRADED,
            ready=False,
            last_failure_reason=reason,
            degraded_reasons=(reason,),
        )

    def get_runtime_diagnostics(self) -> dict[str, object]:
        """Вернуть operator-visible diagnostics."""
        return self._diagnostics.to_dict()

    def ingest_selection(
        self,
        *,
        selection: OpportunitySelectionCandidate,
        reference_time: datetime,
        metadata: dict[str, object] | None = None,
    ) -> OrchestrationRuntimeUpdate:
        """Принять opportunity truth, собрать orchestration context и обновить state."""
        self._ensure_started("ingest_selection")
        context = self._assemble_orchestration_context(
            selection=selection,
            reference_time=reference_time,
            metadata=metadata,
        )
        return self._ingest_orchestration_context(context, reference_time=reference_time)

    def get_decision(
        self,
        *,
        symbol: str,
        exchange: str,
        timeframe: MarketDataTimeframe,
    ) -> OrchestrationDecisionCandidate | None:
        """Вернуть последний orchestration decision по ключу."""
        return self._decisions.get(
            self._build_state_key(exchange=exchange, symbol=symbol, timeframe=timeframe)
        )

    def get_context(
        self,
        *,
        symbol: str,
        exchange: str,
        timeframe: MarketDataTimeframe,
    ) -> OrchestrationContext | None:
        """Вернуть последний orchestration context по ключу."""
        return self._contexts.get(
            self._build_state_key(exchange=exchange, symbol=symbol, timeframe=timeframe)
        )

    def expire_decisions(
        self, *, reference_time: datetime
    ) -> tuple[OrchestrationRuntimeUpdate, ...]:
        """Перевести истёкшие decisions в `EXPIRED` по явному reference time."""
        self._ensure_started("expire_decisions")
        updates: list[OrchestrationRuntimeUpdate] = []
        for key, decision in tuple(self._decisions.items()):
            updated = self._expire_decision_if_needed(decision, reference_time=reference_time)
            if updated is not decision:
                self._decisions[key] = updated
                context = self._contexts[key]
                payload = OrchestrationDecisionPayload.from_candidate(updated)
                updates.append(
                    OrchestrationRuntimeUpdate(
                        context=context,
                        decision=updated,
                        event_type=OrchestrationEventType.ORCHESTRATION_INVALIDATED,
                        emitted_payload=payload,
                    )
                )
                self._update_diagnostics_for_decision(
                    decision=updated,
                    event_type=OrchestrationEventType.ORCHESTRATION_INVALIDATED,
                )
        return tuple(updates)

    def _assemble_orchestration_context(
        self,
        *,
        selection: OpportunitySelectionCandidate,
        reference_time: datetime,
        metadata: dict[str, object] | None,
    ) -> OrchestrationContext:
        observed_inputs = 1
        required_inputs = 1
        missing_inputs: list[str] = []
        invalid_reason: str | None = None

        if (
            selection.freshness.is_expired_at(reference_time)
            or selection.status == OpportunityStatus.EXPIRED
        ):
            invalid_reason = "opportunity_selection_expired"
        elif selection.status == OpportunityStatus.INVALIDATED:
            invalid_reason = "opportunity_selection_invalidated"
        elif selection.status == OpportunityStatus.SUPPRESSED:
            missing_inputs.append("selectable_opportunity")
        elif selection.status == OpportunityStatus.CANDIDATE:
            missing_inputs.append("ready_opportunity")
        elif selection.is_selected:
            pass
        else:
            invalid_reason = "opportunity_selection_not_selected"

        if invalid_reason is not None:
            validity = OrchestrationValidity(
                status=OrchestrationValidityStatus.INVALID,
                observed_inputs=observed_inputs,
                required_inputs=required_inputs,
                invalid_reason=invalid_reason,
            )
        elif missing_inputs:
            validity = OrchestrationValidity(
                status=OrchestrationValidityStatus.WARMING,
                observed_inputs=observed_inputs - len(missing_inputs),
                required_inputs=required_inputs,
                missing_inputs=tuple(missing_inputs),
            )
        else:
            validity = OrchestrationValidity(
                status=OrchestrationValidityStatus.VALID,
                observed_inputs=observed_inputs,
                required_inputs=required_inputs,
            )

        context_metadata: dict[str, object] = {
            "selection_status": selection.status.value,
            "selection_direction": selection.direction.value
            if selection.direction is not None
            else None,
            "selection_decision": "selected" if selection.is_selected else "not_selected",
        }
        if metadata:
            context_metadata.update(metadata)

        return OrchestrationContext(
            orchestration_name=self.config.orchestration_name,
            contour_name=self.config.contour_name,
            symbol=selection.symbol,
            exchange=selection.exchange,
            timeframe=selection.timeframe,
            observed_at=reference_time,
            source=OrchestrationSource.OPPORTUNITY_SELECTION,
            selection=selection,
            validity=validity,
            metadata=context_metadata,
        )

    def _ingest_orchestration_context(
        self,
        context: OrchestrationContext,
        *,
        reference_time: datetime,
    ) -> OrchestrationRuntimeUpdate:
        key = self._build_state_key(
            exchange=context.exchange,
            symbol=context.symbol,
            timeframe=context.timeframe,
        )
        self._contexts[key] = context
        previous_decision = self._decisions.get(key)
        decision = self._build_decision_from_context(
            context=context,
            reference_time=reference_time,
            previous_decision=previous_decision,
        )
        decision = self._expire_decision_if_needed(decision, reference_time=reference_time)
        self._decisions[key] = decision

        payload = OrchestrationDecisionPayload.from_candidate(decision)
        event_type = self._resolve_event_type(
            decision=decision,
            previous_decision=previous_decision,
        )
        self._update_diagnostics_for_decision(decision=decision, event_type=event_type)

        return OrchestrationRuntimeUpdate(
            context=context,
            decision=decision,
            event_type=event_type,
            emitted_payload=payload,
        )

    def _build_decision_from_context(
        self,
        *,
        context: OrchestrationContext,
        reference_time: datetime,
        previous_decision: OrchestrationDecisionCandidate | None,
    ) -> OrchestrationDecisionCandidate:
        freshness = OrchestrationFreshness(
            generated_at=reference_time,
            expires_at=reference_time + timedelta(seconds=self.config.max_decision_age_seconds),
        )

        if context.validity.status == OrchestrationValidityStatus.INVALID:
            if self._should_invalidate_previous_decision(previous_decision):
                assert previous_decision is not None
                return self._build_invalidated_decision(
                    freshness=freshness,
                    context=context,
                    previous_decision=previous_decision,
                )
            return OrchestrationDecisionCandidate.candidate(
                contour_name=self.config.contour_name,
                orchestration_name=self.config.orchestration_name,
                symbol=context.symbol,
                exchange=context.exchange,
                timeframe=context.timeframe,
                source=context.source,
                freshness=freshness,
                validity=context.validity,
                status=OrchestrationStatus.CANDIDATE,
                decision=OrchestrationDecision.ABSTAIN,
                reason_code=OrchestrationReasonCode.CONTEXT_INCOMPLETE,
                metadata={"invalid_reason": context.validity.invalid_reason},
            )

        if context.validity.is_warming:
            if self._should_invalidate_previous_decision(previous_decision):
                assert previous_decision is not None
                return self._build_invalidated_decision(
                    freshness=freshness,
                    context=context,
                    previous_decision=previous_decision,
                )
            return OrchestrationDecisionCandidate.candidate(
                contour_name=self.config.contour_name,
                orchestration_name=self.config.orchestration_name,
                symbol=context.symbol,
                exchange=context.exchange,
                timeframe=context.timeframe,
                source=context.source,
                freshness=freshness,
                validity=context.validity,
                status=OrchestrationStatus.CANDIDATE,
                decision=OrchestrationDecision.ABSTAIN,
                reason_code=OrchestrationReasonCode.CONTEXT_INCOMPLETE,
                metadata={"missing_inputs": context.validity.missing_inputs},
            )

        forwarded_decision = self._evaluate_minimal_contour(
            context=context,
            freshness=freshness,
            previous_decision=previous_decision,
        )
        if forwarded_decision is not None:
            return forwarded_decision

        selection = context.selection
        return OrchestrationDecisionCandidate(
            decision_id=self._resolve_decision_id(previous_decision),
            contour_name=self.config.contour_name,
            orchestration_name=self.config.orchestration_name,
            symbol=context.symbol,
            exchange=context.exchange,
            timeframe=context.timeframe,
            source=context.source,
            freshness=freshness,
            validity=context.validity,
            status=OrchestrationStatus.ABSTAINED,
            decision=OrchestrationDecision.ABSTAIN,
            direction=None,
            originating_selection_id=selection.selection_id,
            confidence=selection.confidence,
            priority_score=selection.priority_score,
            reason_code=OrchestrationReasonCode.ORCHESTRATION_ABSTAINED,
            metadata={
                "selection_status": selection.status.value,
                "priority_score": str(
                    selection.priority_score
                    if selection.priority_score is not None
                    else Decimal("0")
                ),
            },
        )

    def _evaluate_minimal_contour(
        self,
        *,
        context: OrchestrationContext,
        freshness: OrchestrationFreshness,
        previous_decision: OrchestrationDecisionCandidate | None,
    ) -> OrchestrationDecisionCandidate | None:
        selection = context.selection
        if not selection.is_selected or selection.direction is None:
            return None

        confidence = selection.confidence or Decimal("0")
        priority_score = selection.priority_score or confidence
        if confidence < self.config.min_selection_confidence_for_forward:
            return None
        if priority_score < self.config.min_priority_score_for_forward:
            return None

        return OrchestrationDecisionCandidate(
            decision_id=self._resolve_decision_id(previous_decision),
            contour_name=self.config.contour_name,
            orchestration_name=self.config.orchestration_name,
            symbol=context.symbol,
            exchange=context.exchange,
            timeframe=context.timeframe,
            source=context.source,
            freshness=freshness,
            validity=context.validity,
            status=OrchestrationStatus.ORCHESTRATED,
            decision=OrchestrationDecision.FORWARD,
            direction=selection.direction,
            originating_selection_id=selection.selection_id,
            confidence=confidence,
            priority_score=priority_score,
            reason_code=OrchestrationReasonCode.CONTEXT_READY,
            metadata={
                "selection_status": selection.status.value,
                "selection_direction": selection.direction.value,
                "priority_score": str(priority_score),
            },
        )

    def _build_invalidated_decision(
        self,
        *,
        freshness: OrchestrationFreshness,
        context: OrchestrationContext,
        previous_decision: OrchestrationDecisionCandidate,
    ) -> OrchestrationDecisionCandidate:
        metadata = previous_decision.metadata.copy()
        metadata["invalid_reason"] = context.validity.invalid_reason or ",".join(
            context.validity.missing_inputs
        )
        invalid_validity = OrchestrationValidity(
            status=OrchestrationValidityStatus.INVALID,
            observed_inputs=context.validity.observed_inputs,
            required_inputs=context.validity.required_inputs,
            missing_inputs=context.validity.missing_inputs,
            invalid_reason=context.validity.invalid_reason or "orchestration_invalidated",
        )
        return OrchestrationDecisionCandidate(
            decision_id=previous_decision.decision_id,
            contour_name=previous_decision.contour_name,
            orchestration_name=previous_decision.orchestration_name,
            symbol=previous_decision.symbol,
            exchange=previous_decision.exchange,
            timeframe=previous_decision.timeframe,
            source=previous_decision.source,
            freshness=freshness,
            validity=invalid_validity,
            status=OrchestrationStatus.INVALIDATED,
            decision=previous_decision.decision,
            direction=previous_decision.direction,
            originating_selection_id=previous_decision.originating_selection_id,
            confidence=previous_decision.confidence,
            priority_score=previous_decision.priority_score,
            reason_code=OrchestrationReasonCode.ORCHESTRATION_INVALIDATED,
            metadata=metadata,
        )

    def _expire_decision_if_needed(
        self,
        decision: OrchestrationDecisionCandidate,
        *,
        reference_time: datetime,
    ) -> OrchestrationDecisionCandidate:
        if decision.status == OrchestrationStatus.EXPIRED:
            return decision
        if not decision.freshness.is_expired_at(reference_time):
            return decision
        expired_validity = decision.validity
        if expired_validity.status == OrchestrationValidityStatus.VALID:
            expired_validity = OrchestrationValidity(
                status=OrchestrationValidityStatus.INVALID,
                observed_inputs=expired_validity.observed_inputs,
                required_inputs=expired_validity.required_inputs,
                missing_inputs=expired_validity.missing_inputs,
                invalid_reason="orchestration_expired",
            )
        return replace(
            decision,
            validity=expired_validity,
            status=OrchestrationStatus.EXPIRED,
            reason_code=OrchestrationReasonCode.ORCHESTRATION_EXPIRED,
        )

    def _resolve_event_type(
        self,
        *,
        decision: OrchestrationDecisionCandidate,
        previous_decision: OrchestrationDecisionCandidate | None,
    ) -> OrchestrationEventType:
        _ = previous_decision
        if decision.status in {OrchestrationStatus.INVALIDATED, OrchestrationStatus.EXPIRED}:
            return OrchestrationEventType.ORCHESTRATION_INVALIDATED
        if decision.status in {OrchestrationStatus.ORCHESTRATED, OrchestrationStatus.ABSTAINED}:
            return OrchestrationEventType.ORCHESTRATION_DECIDED
        return OrchestrationEventType.ORCHESTRATION_CANDIDATE_UPDATED

    def _update_diagnostics_for_decision(
        self,
        *,
        decision: OrchestrationDecisionCandidate,
        event_type: OrchestrationEventType,
    ) -> None:
        tracked_context_keys = len(self._contexts)
        tracked_decision_keys = len(self._decisions)
        forwarded_keys = sum(
            1
            for snapshot in self._decisions.values()
            if snapshot.status == OrchestrationStatus.ORCHESTRATED
        )
        abstained_keys = sum(
            1
            for snapshot in self._decisions.values()
            if snapshot.status == OrchestrationStatus.ABSTAINED
        )
        invalidated_decision_keys = sum(
            1
            for snapshot in self._decisions.values()
            if snapshot.status == OrchestrationStatus.INVALIDATED
        )
        expired_decision_keys = sum(
            1
            for snapshot in self._decisions.values()
            if snapshot.status == OrchestrationStatus.EXPIRED
        )

        readiness_reasons: tuple[str, ...] = ()
        lifecycle_state = OrchestrationRuntimeLifecycleState.READY
        ready = True

        if tracked_context_keys == 0:
            lifecycle_state = OrchestrationRuntimeLifecycleState.WARMING
            ready = False
            readiness_reasons = ("no_orchestration_context_processed",)
        elif decision.validity.is_warming:
            lifecycle_state = OrchestrationRuntimeLifecycleState.WARMING
            ready = False
            readiness_reasons = tuple(decision.validity.missing_inputs) or (
                "orchestration_context_warming",
            )
        elif self._diagnostics.degraded_reasons:
            lifecycle_state = OrchestrationRuntimeLifecycleState.DEGRADED
            ready = False
            readiness_reasons = ("runtime_degraded",)

        self._refresh_diagnostics(
            lifecycle_state=lifecycle_state,
            ready=ready,
            tracked_context_keys=tracked_context_keys,
            tracked_decision_keys=tracked_decision_keys,
            forwarded_keys=forwarded_keys,
            abstained_keys=abstained_keys,
            invalidated_decision_keys=invalidated_decision_keys,
            expired_decision_keys=expired_decision_keys,
            last_selection_id=str(decision.originating_selection_id)
            if decision.originating_selection_id is not None
            else None,
            last_decision_id=str(decision.decision_id),
            last_event_type=event_type.value,
            readiness_reasons=readiness_reasons,
        )

    def _build_state_key(
        self,
        *,
        exchange: str,
        symbol: str,
        timeframe: MarketDataTimeframe,
    ) -> OrchestrationStateKey:
        return (
            exchange,
            symbol,
            timeframe,
            self.config.contour_name,
            self.config.orchestration_name,
        )

    @staticmethod
    def _should_invalidate_previous_decision(
        previous_decision: OrchestrationDecisionCandidate | None,
    ) -> bool:
        return (
            previous_decision is not None
            and previous_decision.validity.is_valid
            and previous_decision.status
            not in {OrchestrationStatus.EXPIRED, OrchestrationStatus.INVALIDATED}
        )

    @staticmethod
    def _resolve_decision_id(previous_decision: OrchestrationDecisionCandidate | None) -> UUID:
        if previous_decision is not None:
            return previous_decision.decision_id
        return uuid4()

    def _ensure_started(self, operation: str) -> None:
        if not self._started:
            raise RuntimeError(
                f"OrchestrationRuntime не запущен. Операция {operation} недоступна до start()."
            )

    def _refresh_diagnostics(self, **updates: object) -> None:
        current = asdict(self._diagnostics)
        current.update(updates)
        self._diagnostics = OrchestrationRuntimeDiagnostics(
            started=self._started,
            ready=bool(current["ready"]),
            lifecycle_state=OrchestrationRuntimeLifecycleState(current["lifecycle_state"]),
            tracked_context_keys=int(current["tracked_context_keys"]),
            tracked_decision_keys=int(current["tracked_decision_keys"]),
            forwarded_keys=int(current["forwarded_keys"]),
            abstained_keys=int(current["abstained_keys"]),
            invalidated_decision_keys=int(current["invalidated_decision_keys"]),
            expired_decision_keys=int(current["expired_decision_keys"]),
            last_selection_id=current["last_selection_id"],
            last_decision_id=current["last_decision_id"],
            last_event_type=current["last_event_type"],
            last_failure_reason=current["last_failure_reason"],
            readiness_reasons=list(current["readiness_reasons"]),
            degraded_reasons=list(current["degraded_reasons"]),
        )
        self._push_diagnostics()

    def _push_diagnostics(self) -> None:
        if self._diagnostics_sink is not None:
            self._diagnostics_sink(self._diagnostics.to_dict())


def create_orchestration_runtime(
    config: OrchestrationRuntimeConfig | None = None,
    *,
    diagnostics_sink: Callable[[dict[str, object]], None] | None = None,
) -> OrchestrationRuntime:
    """Фабрика explicit runtime foundation orchestration layer."""
    return OrchestrationRuntime(
        config=config,
        diagnostics_sink=diagnostics_sink,
    )


__all__ = [
    "OrchestrationRuntime",
    "OrchestrationRuntimeConfig",
    "OrchestrationRuntimeDiagnostics",
    "OrchestrationRuntimeLifecycleState",
    "OrchestrationRuntimeUpdate",
    "OrchestrationStateKey",
    "create_orchestration_runtime",
]

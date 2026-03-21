"""
Узкий explicit runtime foundation для Phase 11 Opportunity / Selection Foundation.

Этот runtime:
- стартует и останавливается явно;
- не делает hidden bootstrap;
- собирает typed opportunity context из execution truth;
- поддерживает один минимальный deterministic selection contour;
- хранит query/state-first truth и operator-visible diagnostics.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from cryptotechnolog.execution import ExecutionOrderIntent, ExecutionStatus
from cryptotechnolog.market_data import MarketDataTimeframe

from .events import OpportunityEventType, OpportunitySelectionPayload
from .models import (
    OpportunityContext,
    OpportunityFreshness,
    OpportunityReasonCode,
    OpportunitySelectionCandidate,
    OpportunitySource,
    OpportunityStatus,
    OpportunityValidity,
    OpportunityValidityStatus,
)

if TYPE_CHECKING:
    from collections.abc import Callable


type OpportunityStateKey = tuple[str, str, MarketDataTimeframe, str, str]


class OpportunityRuntimeLifecycleState(StrEnum):
    """Lifecycle-состояние opportunity runtime."""

    NOT_STARTED = "not_started"
    WARMING = "warming"
    READY = "ready"
    DEGRADED = "degraded"
    STOPPED = "stopped"


@dataclass(slots=True, frozen=True)
class OpportunityRuntimeConfig:
    """Typed runtime-конфигурация следующего шага P_11."""

    contour_name: str = "phase11_opportunity_contour"
    selection_name: str = "phase11_foundation_selection"
    max_selection_age_seconds: int = 300
    min_intent_confidence_for_selection: Decimal = Decimal("0.5000")
    min_priority_score_for_selected: Decimal = Decimal("0.5000")

    def __post_init__(self) -> None:
        if self.max_selection_age_seconds <= 0:
            raise ValueError("max_selection_age_seconds должен быть положительным")
        if not (Decimal("0") <= self.min_intent_confidence_for_selection <= Decimal("1")):
            raise ValueError(
                "min_intent_confidence_for_selection должен находиться в диапазоне [0, 1]"
            )
        if not (Decimal("0") <= self.min_priority_score_for_selected <= Decimal("1")):
            raise ValueError("min_priority_score_for_selected должен находиться в диапазоне [0, 1]")


@dataclass(slots=True)
class OpportunityRuntimeDiagnostics:
    """Operator-visible diagnostics contract opportunity runtime."""

    started: bool = False
    ready: bool = False
    lifecycle_state: OpportunityRuntimeLifecycleState = OpportunityRuntimeLifecycleState.NOT_STARTED
    tracked_context_keys: int = 0
    tracked_selection_keys: int = 0
    selected_keys: int = 0
    invalidated_selection_keys: int = 0
    expired_selection_keys: int = 0
    last_intent_id: str | None = None
    last_selection_id: str | None = None
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
            "tracked_selection_keys": self.tracked_selection_keys,
            "selected_keys": self.selected_keys,
            "invalidated_selection_keys": self.invalidated_selection_keys,
            "expired_selection_keys": self.expired_selection_keys,
            "last_intent_id": self.last_intent_id,
            "last_selection_id": self.last_selection_id,
            "last_event_type": self.last_event_type,
            "last_failure_reason": self.last_failure_reason,
            "readiness_reasons": list(self.readiness_reasons),
            "degraded_reasons": list(self.degraded_reasons),
        }


@dataclass(slots=True, frozen=True)
class OpportunityRuntimeUpdate:
    """Typed update contract opportunity runtime foundation."""

    context: OpportunityContext
    candidate: OpportunitySelectionCandidate | None
    event_type: OpportunityEventType
    emitted_payload: OpportunitySelectionPayload | None = None


class OpportunityRuntime:
    """Explicit runtime foundation для opportunity layer Phase 11."""

    def __init__(
        self,
        config: OpportunityRuntimeConfig | None = None,
        *,
        diagnostics_sink: Callable[[dict[str, object]], None] | None = None,
    ) -> None:
        self.config = config or OpportunityRuntimeConfig()
        self._diagnostics_sink = diagnostics_sink
        self._diagnostics = OpportunityRuntimeDiagnostics()
        self._started = False
        self._contexts: dict[OpportunityStateKey, OpportunityContext] = {}
        self._candidates: dict[OpportunityStateKey, OpportunitySelectionCandidate] = {}
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
            lifecycle_state=OpportunityRuntimeLifecycleState.WARMING,
            ready=False,
            last_failure_reason=None,
            readiness_reasons=("no_selection_context_processed",),
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
            lifecycle_state=OpportunityRuntimeLifecycleState.STOPPED,
            ready=False,
            tracked_context_keys=0,
            tracked_selection_keys=0,
            selected_keys=0,
            invalidated_selection_keys=0,
            expired_selection_keys=0,
            last_intent_id=None,
            last_selection_id=None,
            last_event_type=None,
            last_failure_reason=None,
            readiness_reasons=("runtime_stopped",),
            degraded_reasons=(),
        )

    def mark_degraded(self, reason: str) -> None:
        """Зафиксировать деградацию runtime/ingest path."""
        self._refresh_diagnostics(
            lifecycle_state=OpportunityRuntimeLifecycleState.DEGRADED,
            ready=False,
            last_failure_reason=reason,
            degraded_reasons=(reason,),
        )

    def get_runtime_diagnostics(self) -> dict[str, object]:
        """Вернуть operator-visible diagnostics."""
        return self._diagnostics.to_dict()

    def ingest_intent(
        self,
        *,
        intent: ExecutionOrderIntent,
        reference_time: datetime,
        metadata: dict[str, object] | None = None,
    ) -> OpportunityRuntimeUpdate:
        """Принять execution truth, собрать selection context и обновить state."""
        self._ensure_started("ingest_intent")
        context = self._assemble_opportunity_context(
            intent=intent,
            reference_time=reference_time,
            metadata=metadata,
        )
        return self._ingest_opportunity_context(context, reference_time=reference_time)

    def get_selection(
        self,
        *,
        symbol: str,
        exchange: str,
        timeframe: MarketDataTimeframe,
    ) -> OpportunitySelectionCandidate | None:
        """Вернуть последний selection candidate по ключу."""
        return self._candidates.get(
            self._build_state_key(exchange=exchange, symbol=symbol, timeframe=timeframe)
        )

    def get_context(
        self,
        *,
        symbol: str,
        exchange: str,
        timeframe: MarketDataTimeframe,
    ) -> OpportunityContext | None:
        """Вернуть последний selection context по ключу."""
        return self._contexts.get(
            self._build_state_key(exchange=exchange, symbol=symbol, timeframe=timeframe)
        )

    def expire_candidates(
        self, *, reference_time: datetime
    ) -> tuple[OpportunityRuntimeUpdate, ...]:
        """Перевести истёкшие selection candidates в `EXPIRED` по явному reference time."""
        self._ensure_started("expire_candidates")
        updates: list[OpportunityRuntimeUpdate] = []
        for key, candidate in tuple(self._candidates.items()):
            updated = self._expire_candidate_if_needed(candidate, reference_time=reference_time)
            if updated is not candidate:
                self._candidates[key] = updated
                context = self._contexts[key]
                payload = OpportunitySelectionPayload.from_candidate(updated)
                updates.append(
                    OpportunityRuntimeUpdate(
                        context=context,
                        candidate=updated,
                        event_type=OpportunityEventType.OPPORTUNITY_INVALIDATED,
                        emitted_payload=payload,
                    )
                )
                self._update_diagnostics_for_candidate(
                    candidate=updated,
                    event_type=OpportunityEventType.OPPORTUNITY_INVALIDATED,
                )
        return tuple(updates)

    def _assemble_opportunity_context(
        self,
        *,
        intent: ExecutionOrderIntent,
        reference_time: datetime,
        metadata: dict[str, object] | None,
    ) -> OpportunityContext:
        observed_inputs = 1
        required_inputs = 1
        missing_inputs: list[str] = []
        invalid_reason: str | None = None

        if (
            intent.freshness.is_expired_at(reference_time)
            or intent.status == ExecutionStatus.EXPIRED
        ):
            invalid_reason = "execution_intent_expired"
        elif intent.status == ExecutionStatus.INVALIDATED:
            invalid_reason = "execution_intent_invalidated"
        elif intent.status == ExecutionStatus.SUPPRESSED:
            missing_inputs.append("selectable_intent")
        elif intent.status == ExecutionStatus.CANDIDATE:
            missing_inputs.append("ready_intent")
        elif intent.is_executable:
            pass
        else:
            invalid_reason = "execution_intent_not_executable"

        if invalid_reason is not None:
            validity = OpportunityValidity(
                status=OpportunityValidityStatus.INVALID,
                observed_inputs=observed_inputs,
                required_inputs=required_inputs,
                invalid_reason=invalid_reason,
            )
        elif missing_inputs:
            validity = OpportunityValidity(
                status=OpportunityValidityStatus.WARMING,
                observed_inputs=observed_inputs - len(missing_inputs),
                required_inputs=required_inputs,
                missing_inputs=tuple(missing_inputs),
            )
        else:
            validity = OpportunityValidity(
                status=OpportunityValidityStatus.VALID,
                observed_inputs=observed_inputs,
                required_inputs=required_inputs,
            )

        context_metadata: dict[str, object] = {
            "intent_status": intent.status.value,
            "intent_direction": intent.direction.value if intent.direction is not None else None,
        }
        if metadata:
            context_metadata.update(metadata)

        return OpportunityContext(
            selection_name=self.config.selection_name,
            contour_name=self.config.contour_name,
            symbol=intent.symbol,
            exchange=intent.exchange,
            timeframe=intent.timeframe,
            observed_at=reference_time,
            source=OpportunitySource.EXECUTION_INTENT,
            intent=intent,
            validity=validity,
            metadata=context_metadata,
        )

    def _ingest_opportunity_context(
        self,
        context: OpportunityContext,
        *,
        reference_time: datetime,
    ) -> OpportunityRuntimeUpdate:
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

        payload = OpportunitySelectionPayload.from_candidate(candidate)
        event_type = self._resolve_event_type(
            candidate=candidate, previous_candidate=previous_candidate
        )
        self._update_diagnostics_for_candidate(candidate=candidate, event_type=event_type)

        return OpportunityRuntimeUpdate(
            context=context,
            candidate=candidate,
            event_type=event_type,
            emitted_payload=payload,
        )

    def _build_candidate_from_context(
        self,
        *,
        context: OpportunityContext,
        reference_time: datetime,
        previous_candidate: OpportunitySelectionCandidate | None,
    ) -> OpportunitySelectionCandidate:
        freshness = OpportunityFreshness(
            generated_at=reference_time,
            expires_at=reference_time + timedelta(seconds=self.config.max_selection_age_seconds),
        )

        if context.validity.status == OpportunityValidityStatus.INVALID:
            if self._should_invalidate_previous_candidate(previous_candidate):
                assert previous_candidate is not None
                return self._build_invalidated_candidate(
                    freshness=freshness,
                    context=context,
                    previous_candidate=previous_candidate,
                )
            return OpportunitySelectionCandidate.candidate(
                contour_name=self.config.contour_name,
                selection_name=self.config.selection_name,
                symbol=context.symbol,
                exchange=context.exchange,
                timeframe=context.timeframe,
                source=context.source,
                freshness=freshness,
                validity=context.validity,
                reason_code=OpportunityReasonCode.CONTEXT_INCOMPLETE,
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
            return OpportunitySelectionCandidate.candidate(
                contour_name=self.config.contour_name,
                selection_name=self.config.selection_name,
                symbol=context.symbol,
                exchange=context.exchange,
                timeframe=context.timeframe,
                source=context.source,
                freshness=freshness,
                validity=context.validity,
                reason_code=OpportunityReasonCode.CONTEXT_INCOMPLETE,
                metadata={"missing_inputs": context.validity.missing_inputs},
            )

        selected_candidate = self._evaluate_minimal_contour(
            context=context,
            freshness=freshness,
            previous_candidate=previous_candidate,
        )
        if selected_candidate is not None:
            return selected_candidate

        return OpportunitySelectionCandidate(
            selection_id=self._resolve_selection_id(previous_candidate),
            contour_name=self.config.contour_name,
            selection_name=self.config.selection_name,
            symbol=context.symbol,
            exchange=context.exchange,
            timeframe=context.timeframe,
            source=context.source,
            freshness=freshness,
            validity=context.validity,
            status=OpportunityStatus.SUPPRESSED,
            direction=(
                OpportunitySelectionCandidate.direction_from_execution(context.intent.direction)
                if context.intent.direction is not None
                else None
            ),
            originating_intent_id=context.intent.intent_id,
            confidence=context.intent.confidence,
            priority_score=context.intent.confidence,
            reason_code=OpportunityReasonCode.SELECTION_RULE_BLOCKED,
            metadata={
                "intent_status": context.intent.status.value,
                "priority_score": str(context.intent.confidence or Decimal("0")),
            },
        )

    def _evaluate_minimal_contour(
        self,
        *,
        context: OpportunityContext,
        freshness: OpportunityFreshness,
        previous_candidate: OpportunitySelectionCandidate | None,
    ) -> OpportunitySelectionCandidate | None:
        intent = context.intent
        if not intent.is_executable or intent.direction is None:
            return None

        confidence = intent.confidence or Decimal("0")
        priority_score = confidence
        if confidence < self.config.min_intent_confidence_for_selection:
            return None
        if priority_score < self.config.min_priority_score_for_selected:
            return None

        direction = OpportunitySelectionCandidate.direction_from_execution(intent.direction)
        return OpportunitySelectionCandidate(
            selection_id=self._resolve_selection_id(previous_candidate),
            contour_name=self.config.contour_name,
            selection_name=self.config.selection_name,
            symbol=context.symbol,
            exchange=context.exchange,
            timeframe=context.timeframe,
            source=context.source,
            freshness=freshness,
            validity=context.validity,
            status=OpportunityStatus.SELECTED,
            direction=direction,
            originating_intent_id=intent.intent_id,
            confidence=confidence,
            priority_score=priority_score,
            reason_code=OpportunityReasonCode.CONTEXT_READY,
            metadata={
                "intent_status": intent.status.value,
                "intent_direction": intent.direction.value,
                "priority_score": str(priority_score),
            },
        )

    def _build_invalidated_candidate(
        self,
        *,
        freshness: OpportunityFreshness,
        context: OpportunityContext,
        previous_candidate: OpportunitySelectionCandidate,
    ) -> OpportunitySelectionCandidate:
        metadata = previous_candidate.metadata.copy()
        metadata["invalid_reason"] = context.validity.invalid_reason or ",".join(
            context.validity.missing_inputs
        )
        invalid_validity = OpportunityValidity(
            status=OpportunityValidityStatus.INVALID,
            observed_inputs=context.validity.observed_inputs,
            required_inputs=context.validity.required_inputs,
            missing_inputs=context.validity.missing_inputs,
            invalid_reason=context.validity.invalid_reason or "selection_invalidated",
        )
        return OpportunitySelectionCandidate(
            selection_id=previous_candidate.selection_id,
            contour_name=previous_candidate.contour_name,
            selection_name=previous_candidate.selection_name,
            symbol=previous_candidate.symbol,
            exchange=previous_candidate.exchange,
            timeframe=previous_candidate.timeframe,
            source=previous_candidate.source,
            freshness=freshness,
            validity=invalid_validity,
            status=OpportunityStatus.INVALIDATED,
            direction=previous_candidate.direction,
            originating_intent_id=previous_candidate.originating_intent_id,
            confidence=previous_candidate.confidence,
            priority_score=previous_candidate.priority_score,
            reason_code=OpportunityReasonCode.OPPORTUNITY_INVALIDATED,
            metadata=metadata,
        )

    def _expire_candidate_if_needed(
        self,
        candidate: OpportunitySelectionCandidate,
        *,
        reference_time: datetime,
    ) -> OpportunitySelectionCandidate:
        if candidate.status == OpportunityStatus.EXPIRED:
            return candidate
        if not candidate.freshness.is_expired_at(reference_time):
            return candidate
        expired_validity = candidate.validity
        if expired_validity.status == OpportunityValidityStatus.VALID:
            expired_validity = OpportunityValidity(
                status=OpportunityValidityStatus.INVALID,
                observed_inputs=expired_validity.observed_inputs,
                required_inputs=expired_validity.required_inputs,
                missing_inputs=expired_validity.missing_inputs,
                invalid_reason="opportunity_expired",
            )
        return replace(
            candidate,
            validity=expired_validity,
            status=OpportunityStatus.EXPIRED,
            reason_code=OpportunityReasonCode.OPPORTUNITY_EXPIRED,
        )

    def _resolve_event_type(
        self,
        *,
        candidate: OpportunitySelectionCandidate,
        previous_candidate: OpportunitySelectionCandidate | None,
    ) -> OpportunityEventType:
        if candidate.status in {OpportunityStatus.INVALIDATED, OpportunityStatus.EXPIRED}:
            return OpportunityEventType.OPPORTUNITY_INVALIDATED
        if candidate.status == OpportunityStatus.SELECTED:
            return OpportunityEventType.OPPORTUNITY_SELECTED
        return OpportunityEventType.OPPORTUNITY_CANDIDATE_UPDATED

    def _update_diagnostics_for_candidate(
        self,
        *,
        candidate: OpportunitySelectionCandidate,
        event_type: OpportunityEventType,
    ) -> None:
        tracked_context_keys = len(self._contexts)
        tracked_selection_keys = len(self._candidates)
        selected_keys = sum(
            1
            for snapshot in self._candidates.values()
            if snapshot.status == OpportunityStatus.SELECTED
        )
        invalidated_selection_keys = sum(
            1
            for snapshot in self._candidates.values()
            if snapshot.status == OpportunityStatus.INVALIDATED
        )
        expired_selection_keys = sum(
            1
            for snapshot in self._candidates.values()
            if snapshot.status == OpportunityStatus.EXPIRED
        )

        readiness_reasons: tuple[str, ...] = ()
        lifecycle_state = OpportunityRuntimeLifecycleState.READY
        ready = True

        if tracked_context_keys == 0:
            lifecycle_state = OpportunityRuntimeLifecycleState.WARMING
            ready = False
            readiness_reasons = ("no_selection_context_processed",)
        elif candidate.validity.is_warming:
            lifecycle_state = OpportunityRuntimeLifecycleState.WARMING
            ready = False
            readiness_reasons = tuple(candidate.validity.missing_inputs) or (
                "selection_context_warming",
            )
        elif self._diagnostics.degraded_reasons:
            lifecycle_state = OpportunityRuntimeLifecycleState.DEGRADED
            ready = False
            readiness_reasons = ("runtime_degraded",)

        self._refresh_diagnostics(
            lifecycle_state=lifecycle_state,
            ready=ready,
            tracked_context_keys=tracked_context_keys,
            tracked_selection_keys=tracked_selection_keys,
            selected_keys=selected_keys,
            invalidated_selection_keys=invalidated_selection_keys,
            expired_selection_keys=expired_selection_keys,
            last_intent_id=str(candidate.originating_intent_id)
            if candidate.originating_intent_id is not None
            else None,
            last_selection_id=str(candidate.selection_id),
            last_event_type=event_type.value,
            readiness_reasons=readiness_reasons,
        )

    def _build_state_key(
        self,
        *,
        exchange: str,
        symbol: str,
        timeframe: MarketDataTimeframe,
    ) -> OpportunityStateKey:
        return (
            exchange,
            symbol,
            timeframe,
            self.config.contour_name,
            self.config.selection_name,
        )

    @staticmethod
    def _should_invalidate_previous_candidate(
        previous_candidate: OpportunitySelectionCandidate | None,
    ) -> bool:
        return (
            previous_candidate is not None
            and previous_candidate.validity.is_valid
            and previous_candidate.status
            not in {OpportunityStatus.EXPIRED, OpportunityStatus.INVALIDATED}
        )

    @staticmethod
    def _resolve_selection_id(previous_candidate: OpportunitySelectionCandidate | None) -> UUID:
        if previous_candidate is not None:
            return previous_candidate.selection_id
        return uuid4()

    def _ensure_started(self, operation: str) -> None:
        if not self._started:
            raise RuntimeError(
                f"OpportunityRuntime не запущен. Операция {operation} недоступна до start()."
            )

    def _refresh_diagnostics(self, **updates: object) -> None:
        current = asdict(self._diagnostics)
        current.update(updates)
        self._diagnostics = OpportunityRuntimeDiagnostics(
            started=self._started,
            ready=bool(current["ready"]),
            lifecycle_state=OpportunityRuntimeLifecycleState(current["lifecycle_state"]),
            tracked_context_keys=int(current["tracked_context_keys"]),
            tracked_selection_keys=int(current["tracked_selection_keys"]),
            selected_keys=int(current["selected_keys"]),
            invalidated_selection_keys=int(current["invalidated_selection_keys"]),
            expired_selection_keys=int(current["expired_selection_keys"]),
            last_intent_id=current["last_intent_id"],
            last_selection_id=current["last_selection_id"],
            last_event_type=current["last_event_type"],
            last_failure_reason=current["last_failure_reason"],
            readiness_reasons=list(current["readiness_reasons"]),
            degraded_reasons=list(current["degraded_reasons"]),
        )
        self._push_diagnostics()

    def _push_diagnostics(self) -> None:
        if self._diagnostics_sink is not None:
            self._diagnostics_sink(self._diagnostics.to_dict())


def create_opportunity_runtime(
    config: OpportunityRuntimeConfig | None = None,
    *,
    diagnostics_sink: Callable[[dict[str, object]], None] | None = None,
) -> OpportunityRuntime:
    """Фабрика explicit runtime foundation opportunity layer."""
    return OpportunityRuntime(
        config=config,
        diagnostics_sink=diagnostics_sink,
    )


__all__ = [
    "OpportunityRuntime",
    "OpportunityRuntimeConfig",
    "OpportunityRuntimeDiagnostics",
    "OpportunityRuntimeLifecycleState",
    "OpportunityRuntimeUpdate",
    "create_opportunity_runtime",
]

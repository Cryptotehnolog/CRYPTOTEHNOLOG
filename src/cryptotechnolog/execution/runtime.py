"""
Узкий explicit runtime foundation для Phase 10 Execution Foundation.

Этот runtime:
- стартует и останавливается явно;
- не делает hidden bootstrap;
- собирает typed execution context из strategy truth;
- поддерживает один минимальный deterministic execution contour;
- хранит query/state-first truth и operator-visible diagnostics.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from cryptotechnolog.config import get_settings
from cryptotechnolog.market_data import MarketDataTimeframe
from cryptotechnolog.strategy import StrategyActionCandidate, StrategyStatus

from .events import ExecutionEventType, ExecutionOrderIntentPayload
from .models import (
    ExecutionContext,
    ExecutionFreshness,
    ExecutionOrderIntent,
    ExecutionReasonCode,
    ExecutionStatus,
    ExecutionValidity,
    ExecutionValidityStatus,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from cryptotechnolog.config.settings import Settings


type ExecutionStateKey = tuple[str, str, MarketDataTimeframe, str, str]


class ExecutionRuntimeLifecycleState(StrEnum):
    """Lifecycle-состояние execution runtime."""

    NOT_STARTED = "not_started"
    WARMING = "warming"
    READY = "ready"
    DEGRADED = "degraded"
    STOPPED = "stopped"


@dataclass(slots=True, frozen=True)
class ExecutionRuntimeConfig:
    """Typed runtime-конфигурация следующего шага P_10."""

    contour_name: str = "phase10_execution_contour"
    execution_name: str = "phase10_foundation_execution"
    max_intent_age_seconds: int = 300
    min_candidate_confidence_for_execution: Decimal = Decimal("0.5000")

    def __post_init__(self) -> None:
        if self.max_intent_age_seconds <= 0:
            raise ValueError("max_intent_age_seconds должен быть положительным")
        if not (Decimal("0") <= self.min_candidate_confidence_for_execution <= Decimal("1")):
            raise ValueError(
                "min_candidate_confidence_for_execution должен находиться в диапазоне [0, 1]"
            )

    @classmethod
    def from_settings(cls, settings: Settings) -> ExecutionRuntimeConfig:
        """Build execution runtime config from canonical project settings."""
        return cls(
            max_intent_age_seconds=settings.execution_max_intent_age_seconds,
            min_candidate_confidence_for_execution=Decimal(
                str(settings.execution_min_strategy_confidence)
            ),
        )


@dataclass(slots=True)
class ExecutionRuntimeDiagnostics:
    """Operator-visible diagnostics contract execution runtime."""

    started: bool = False
    ready: bool = False
    lifecycle_state: ExecutionRuntimeLifecycleState = ExecutionRuntimeLifecycleState.NOT_STARTED
    tracked_context_keys: int = 0
    tracked_intent_keys: int = 0
    executable_intent_keys: int = 0
    invalidated_intent_keys: int = 0
    expired_intent_keys: int = 0
    last_candidate_id: str | None = None
    last_intent_id: str | None = None
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
            "tracked_intent_keys": self.tracked_intent_keys,
            "executable_intent_keys": self.executable_intent_keys,
            "invalidated_intent_keys": self.invalidated_intent_keys,
            "expired_intent_keys": self.expired_intent_keys,
            "last_candidate_id": self.last_candidate_id,
            "last_intent_id": self.last_intent_id,
            "last_event_type": self.last_event_type,
            "last_failure_reason": self.last_failure_reason,
            "readiness_reasons": list(self.readiness_reasons),
            "degraded_reasons": list(self.degraded_reasons),
        }


@dataclass(slots=True, frozen=True)
class ExecutionRuntimeUpdate:
    """Typed update contract execution runtime foundation."""

    context: ExecutionContext
    intent: ExecutionOrderIntent | None
    event_type: ExecutionEventType
    emitted_payload: ExecutionOrderIntentPayload | None = None


class ExecutionRuntime:
    """Explicit runtime foundation для execution layer Phase 10."""

    def __init__(
        self,
        config: ExecutionRuntimeConfig | None = None,
        *,
        diagnostics_sink: Callable[[dict[str, object]], None] | None = None,
    ) -> None:
        self.config = config or ExecutionRuntimeConfig()
        self._diagnostics_sink = diagnostics_sink
        self._diagnostics = ExecutionRuntimeDiagnostics()
        self._started = False
        self._contexts: dict[ExecutionStateKey, ExecutionContext] = {}
        self._intents: dict[ExecutionStateKey, ExecutionOrderIntent] = {}
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
            lifecycle_state=ExecutionRuntimeLifecycleState.WARMING,
            ready=False,
            last_failure_reason=None,
            readiness_reasons=("no_execution_context_processed",),
            degraded_reasons=(),
        )

    async def stop(self) -> None:
        """Остановить runtime и очистить operator-visible state."""
        if not self._started:
            return
        self._started = False
        self._contexts = {}
        self._intents = {}
        self._refresh_diagnostics(
            lifecycle_state=ExecutionRuntimeLifecycleState.STOPPED,
            ready=False,
            tracked_context_keys=0,
            tracked_intent_keys=0,
            executable_intent_keys=0,
            invalidated_intent_keys=0,
            expired_intent_keys=0,
            last_candidate_id=None,
            last_intent_id=None,
            last_event_type=None,
            last_failure_reason=None,
            readiness_reasons=("runtime_stopped",),
            degraded_reasons=(),
        )

    def mark_degraded(self, reason: str) -> None:
        """Зафиксировать деградацию runtime/ingest path."""
        self._refresh_diagnostics(
            lifecycle_state=ExecutionRuntimeLifecycleState.DEGRADED,
            ready=False,
            last_failure_reason=reason,
            degraded_reasons=(reason,),
        )

    def get_runtime_diagnostics(self) -> dict[str, object]:
        """Вернуть operator-visible diagnostics."""
        return self._diagnostics.to_dict()

    def ingest_candidate(
        self,
        *,
        candidate: StrategyActionCandidate,
        reference_time: datetime,
        metadata: dict[str, object] | None = None,
    ) -> ExecutionRuntimeUpdate:
        """Принять strategy truth, собрать ExecutionContext и обновить execution state."""
        self._ensure_started("ingest_candidate")
        context = self._assemble_execution_context(
            candidate=candidate,
            reference_time=reference_time,
            metadata=metadata,
        )
        return self._ingest_execution_context(context, reference_time=reference_time)

    def get_intent(
        self,
        *,
        symbol: str,
        exchange: str,
        timeframe: MarketDataTimeframe,
    ) -> ExecutionOrderIntent | None:
        """Вернуть последний execution intent по ключу."""
        return self._intents.get(
            self._build_state_key(exchange=exchange, symbol=symbol, timeframe=timeframe)
        )

    def get_context(
        self,
        *,
        symbol: str,
        exchange: str,
        timeframe: MarketDataTimeframe,
    ) -> ExecutionContext | None:
        """Вернуть последний execution context по ключу."""
        return self._contexts.get(
            self._build_state_key(exchange=exchange, symbol=symbol, timeframe=timeframe)
        )

    def expire_intents(
        self,
        *,
        reference_time: datetime,
    ) -> tuple[ExecutionOrderIntent, ...]:
        """Перевести истёкшие execution intents в `EXPIRED` по явному reference time."""
        self._ensure_started("expire_intents")
        expired: list[ExecutionOrderIntent] = []
        for key, intent in tuple(self._intents.items()):
            updated = self._expire_intent_if_needed(intent, reference_time=reference_time)
            if updated is not intent:
                self._intents[key] = updated
                expired.append(updated)
                context = self._contexts.get(key)
                if context is not None:
                    self._refresh_runtime_state(
                        intent=updated,
                        context=context,
                        event_type=ExecutionEventType.EXECUTION_INVALIDATED,
                    )
        return tuple(expired)

    def _assemble_execution_context(
        self,
        *,
        candidate: StrategyActionCandidate,
        reference_time: datetime,
        metadata: dict[str, object] | None = None,
    ) -> ExecutionContext:
        """Детерминированно собрать typed execution context только из strategy truth."""
        observed_inputs = 0
        missing_inputs: list[str] = []
        invalid_reason: str | None = None

        if (
            candidate.freshness.is_expired_at(reference_time)
            or candidate.status == StrategyStatus.EXPIRED
        ):
            invalid_reason = "strategy_candidate_expired"
        elif candidate.status == StrategyStatus.INVALIDATED:
            invalid_reason = "strategy_candidate_invalidated"
        elif candidate.status == StrategyStatus.SUPPRESSED:
            missing_inputs.append("executable_candidate")
        elif candidate.status == StrategyStatus.CANDIDATE:
            missing_inputs.append("ready_candidate")
        elif candidate.is_actionable:
            observed_inputs += 1
        else:
            invalid_reason = "strategy_candidate_not_actionable"

        validity = self._build_context_validity(
            observed_inputs=observed_inputs,
            missing_inputs=tuple(dict.fromkeys(missing_inputs)),
            invalid_reason=invalid_reason,
        )
        return ExecutionContext(
            execution_name=self.config.execution_name,
            contour_name=self.config.contour_name,
            symbol=candidate.symbol,
            exchange=candidate.exchange,
            timeframe=candidate.timeframe,
            observed_at=reference_time,
            candidate=candidate,
            validity=validity,
            metadata={} if metadata is None else metadata.copy(),
        )

    def _ingest_execution_context(
        self,
        context: ExecutionContext,
        *,
        reference_time: datetime,
    ) -> ExecutionRuntimeUpdate:
        key = self._build_state_key(
            exchange=context.exchange,
            symbol=context.symbol,
            timeframe=context.timeframe,
        )
        self._contexts[key] = context
        previous_intent = self._intents.get(key)
        intent = self._build_intent_from_context(
            context=context,
            previous_intent=previous_intent,
        )
        intent = self._expire_intent_if_needed(intent, reference_time=reference_time)
        self._intents[key] = intent

        payload = ExecutionOrderIntentPayload.from_intent(intent)
        event_type = self._resolve_event_type(
            intent=intent,
            previous_intent=previous_intent,
        )
        self._refresh_runtime_state(
            intent=intent,
            context=context,
            event_type=event_type,
        )
        return ExecutionRuntimeUpdate(
            context=context,
            intent=intent,
            event_type=event_type,
            emitted_payload=payload,
        )

    def _build_intent_from_context(
        self,
        *,
        context: ExecutionContext,
        previous_intent: ExecutionOrderIntent | None,
    ) -> ExecutionOrderIntent:
        freshness = ExecutionFreshness(
            generated_at=context.observed_at,
            expires_at=context.observed_at + timedelta(seconds=self.config.max_intent_age_seconds),
        )

        if context.validity.status == ExecutionValidityStatus.INVALID:
            if self._should_invalidate_previous_intent(previous_intent):
                assert previous_intent is not None
                return self._build_invalidated_intent(
                    context=context,
                    freshness=freshness,
                    previous_intent=previous_intent,
                )
            return ExecutionOrderIntent.candidate(
                contour_name=self.config.contour_name,
                execution_name=self.config.execution_name,
                symbol=context.symbol,
                exchange=context.exchange,
                timeframe=context.timeframe,
                freshness=freshness,
                validity=context.validity,
                reason_code=ExecutionReasonCode.EXECUTION_RULE_BLOCKED,
                metadata={"invalid_reason": context.validity.invalid_reason},
            )

        if context.validity.status == ExecutionValidityStatus.WARMING:
            if self._should_invalidate_previous_intent(previous_intent):
                assert previous_intent is not None
                return self._build_invalidated_intent(
                    context=context,
                    freshness=freshness,
                    previous_intent=previous_intent,
                )
            return ExecutionOrderIntent.candidate(
                contour_name=self.config.contour_name,
                execution_name=self.config.execution_name,
                symbol=context.symbol,
                exchange=context.exchange,
                timeframe=context.timeframe,
                freshness=freshness,
                validity=context.validity,
                reason_code=ExecutionReasonCode.CONTEXT_INCOMPLETE,
                metadata={"missing_inputs": context.validity.missing_inputs},
            )

        executable_intent = self._evaluate_minimal_contour(
            context=context,
            freshness=freshness,
            previous_intent=previous_intent,
        )
        if executable_intent is not None:
            return executable_intent

        return ExecutionOrderIntent(
            intent_id=self._resolve_intent_id(previous_intent),
            contour_name=self.config.contour_name,
            execution_name=self.config.execution_name,
            symbol=context.symbol,
            exchange=context.exchange,
            timeframe=context.timeframe,
            freshness=freshness,
            validity=context.validity,
            status=ExecutionStatus.SUPPRESSED,
            reason_code=ExecutionReasonCode.EXECUTION_RULE_BLOCKED,
            metadata={"suppression_reason": "execution_conditions_not_met"},
        )

    def _evaluate_minimal_contour(
        self,
        *,
        context: ExecutionContext,
        freshness: ExecutionFreshness,
        previous_intent: ExecutionOrderIntent | None,
    ) -> ExecutionOrderIntent | None:
        candidate = context.candidate
        if not candidate.is_actionable or candidate.direction is None:
            return None

        confidence = candidate.confidence or Decimal("0")
        if confidence < self.config.min_candidate_confidence_for_execution:
            return None

        direction = ExecutionOrderIntent.direction_from_strategy(candidate.direction)

        return ExecutionOrderIntent(
            intent_id=self._resolve_intent_id(previous_intent),
            contour_name=self.config.contour_name,
            execution_name=self.config.execution_name,
            symbol=context.symbol,
            exchange=context.exchange,
            timeframe=context.timeframe,
            freshness=freshness,
            validity=context.validity,
            status=ExecutionStatus.EXECUTABLE,
            direction=direction,
            originating_candidate_id=candidate.candidate_id,
            confidence=confidence,
            reason_code=ExecutionReasonCode.CONTEXT_READY,
            metadata={
                "candidate_status": candidate.status.value,
                "candidate_direction": candidate.direction.value,
                "candidate_confidence": str(confidence),
            },
        )

    def _build_invalidated_intent(
        self,
        *,
        context: ExecutionContext,
        freshness: ExecutionFreshness,
        previous_intent: ExecutionOrderIntent,
    ) -> ExecutionOrderIntent:
        metadata = previous_intent.metadata.copy()
        if context.validity.invalid_reason is not None:
            metadata["invalid_reason"] = context.validity.invalid_reason
        if context.validity.missing_inputs:
            metadata["missing_inputs"] = context.validity.missing_inputs
        metadata["invalidation_reason"] = (
            context.validity.invalid_reason or "execution_input_truth_lost"
        )

        return ExecutionOrderIntent(
            intent_id=previous_intent.intent_id,
            contour_name=self.config.contour_name,
            execution_name=self.config.execution_name,
            symbol=context.symbol,
            exchange=context.exchange,
            timeframe=context.timeframe,
            freshness=freshness,
            validity=context.validity,
            status=ExecutionStatus.INVALIDATED,
            direction=previous_intent.direction,
            originating_candidate_id=previous_intent.originating_candidate_id,
            confidence=previous_intent.confidence,
            reason_code=ExecutionReasonCode.EXECUTION_INVALIDATED,
            metadata=metadata,
        )

    def _expire_intent_if_needed(
        self,
        intent: ExecutionOrderIntent,
        *,
        reference_time: datetime,
    ) -> ExecutionOrderIntent:
        if intent.status == ExecutionStatus.EXPIRED:
            return intent
        if not intent.freshness.is_expired_at(reference_time):
            return intent
        expired_validity = intent.validity
        if expired_validity.is_valid:
            expired_validity = replace(
                expired_validity,
                status=ExecutionValidityStatus.INVALID,
                invalid_reason="execution_expired",
            )
        return replace(
            intent,
            status=ExecutionStatus.EXPIRED,
            validity=expired_validity,
            reason_code=ExecutionReasonCode.EXECUTION_EXPIRED,
        )

    def _resolve_event_type(
        self,
        *,
        intent: ExecutionOrderIntent,
        previous_intent: ExecutionOrderIntent | None,
    ) -> ExecutionEventType:
        if intent.status in {ExecutionStatus.INVALIDATED, ExecutionStatus.EXPIRED}:
            return ExecutionEventType.EXECUTION_INVALIDATED
        if intent.status == ExecutionStatus.EXECUTABLE:
            return ExecutionEventType.EXECUTION_REQUESTED
        return ExecutionEventType.EXECUTION_INTENT_UPDATED

    def _refresh_runtime_state(
        self,
        *,
        intent: ExecutionOrderIntent,
        context: ExecutionContext,
        event_type: ExecutionEventType,
    ) -> None:
        tracked_context_keys = len(self._contexts)
        tracked_intent_keys = len(self._intents)
        executable_intent_keys = sum(
            1
            for snapshot in self._intents.values()
            if snapshot.status == ExecutionStatus.EXECUTABLE
        )
        invalidated_intent_keys = sum(
            1
            for snapshot in self._intents.values()
            if snapshot.status == ExecutionStatus.INVALIDATED
        )
        expired_intent_keys = sum(
            1 for snapshot in self._intents.values() if snapshot.status == ExecutionStatus.EXPIRED
        )

        ready = True
        lifecycle_state = ExecutionRuntimeLifecycleState.READY
        readiness_reasons: list[str] = []
        degraded_reasons: list[str] = []

        if tracked_context_keys == 0:
            ready = False
            lifecycle_state = ExecutionRuntimeLifecycleState.WARMING
            readiness_reasons.append("no_execution_context_processed")
        elif context.validity.status == ExecutionValidityStatus.WARMING:
            ready = False
            lifecycle_state = ExecutionRuntimeLifecycleState.WARMING
            readiness_reasons.append("execution_context_warming")
        elif context.validity.status == ExecutionValidityStatus.INVALID:
            ready = False
            lifecycle_state = ExecutionRuntimeLifecycleState.DEGRADED
            readiness_reasons.append("execution_context_invalid")
            if context.validity.invalid_reason is not None:
                degraded_reasons.append(context.validity.invalid_reason)

        self._refresh_diagnostics(
            ready=ready,
            lifecycle_state=lifecycle_state,
            tracked_context_keys=tracked_context_keys,
            tracked_intent_keys=tracked_intent_keys,
            executable_intent_keys=executable_intent_keys,
            invalidated_intent_keys=invalidated_intent_keys,
            expired_intent_keys=expired_intent_keys,
            last_candidate_id=str(context.candidate.candidate_id),
            last_intent_id=str(intent.intent_id),
            last_event_type=event_type.value,
            last_failure_reason=None,
            readiness_reasons=tuple(readiness_reasons),
            degraded_reasons=tuple(degraded_reasons),
        )

    def _build_context_validity(
        self,
        *,
        observed_inputs: int,
        missing_inputs: tuple[str, ...],
        invalid_reason: str | None,
    ) -> ExecutionValidity:
        required_inputs = 1
        if invalid_reason is not None:
            return ExecutionValidity(
                status=ExecutionValidityStatus.INVALID,
                observed_inputs=observed_inputs,
                required_inputs=required_inputs,
                missing_inputs=missing_inputs,
                invalid_reason=invalid_reason,
            )
        if missing_inputs:
            return ExecutionValidity(
                status=ExecutionValidityStatus.WARMING,
                observed_inputs=observed_inputs,
                required_inputs=required_inputs,
                missing_inputs=missing_inputs,
            )
        return ExecutionValidity(
            status=ExecutionValidityStatus.VALID,
            observed_inputs=observed_inputs,
            required_inputs=required_inputs,
        )

    def _build_state_key(
        self,
        *,
        exchange: str,
        symbol: str,
        timeframe: MarketDataTimeframe,
    ) -> ExecutionStateKey:
        return (
            exchange,
            symbol,
            timeframe,
            self.config.contour_name,
            self.config.execution_name,
        )

    @staticmethod
    def _should_invalidate_previous_intent(
        previous_intent: ExecutionOrderIntent | None,
    ) -> bool:
        return (
            previous_intent is not None
            and previous_intent.validity.is_valid
            and previous_intent.status not in {ExecutionStatus.EXPIRED, ExecutionStatus.INVALIDATED}
        )

    @staticmethod
    def _resolve_intent_id(previous_intent: ExecutionOrderIntent | None) -> UUID:
        if previous_intent is not None:
            return previous_intent.intent_id
        return uuid4()

    def _ensure_started(self, operation: str) -> None:
        if not self._started:
            raise RuntimeError(
                f"ExecutionRuntime не запущен. Операция {operation} недоступна до start()."
            )

    def _refresh_diagnostics(self, **updates: Any) -> None:
        current = asdict(self._diagnostics)
        current.update(updates)
        self._diagnostics = ExecutionRuntimeDiagnostics(
            started=self._started,
            ready=bool(current["ready"]),
            lifecycle_state=ExecutionRuntimeLifecycleState(current["lifecycle_state"]),
            tracked_context_keys=int(current["tracked_context_keys"]),
            tracked_intent_keys=int(current["tracked_intent_keys"]),
            executable_intent_keys=int(current["executable_intent_keys"]),
            invalidated_intent_keys=int(current["invalidated_intent_keys"]),
            expired_intent_keys=int(current["expired_intent_keys"]),
            last_candidate_id=current["last_candidate_id"],
            last_intent_id=current["last_intent_id"],
            last_event_type=current["last_event_type"],
            last_failure_reason=current["last_failure_reason"],
            readiness_reasons=list(current.get("readiness_reasons", [])),
            degraded_reasons=list(current.get("degraded_reasons", [])),
        )
        self._push_diagnostics()

    def _push_diagnostics(self) -> None:
        if self._diagnostics_sink is not None:
            self._diagnostics_sink(self.get_runtime_diagnostics())


def create_execution_runtime(
    config: ExecutionRuntimeConfig | None = None,
    *,
    diagnostics_sink: Callable[[dict[str, object]], None] | None = None,
) -> ExecutionRuntime:
    """Собрать explicit execution runtime foundation."""
    return ExecutionRuntime(
        config=config or ExecutionRuntimeConfig.from_settings(get_settings()),
        diagnostics_sink=diagnostics_sink,
    )


__all__ = [
    "ExecutionRuntime",
    "ExecutionRuntimeConfig",
    "ExecutionRuntimeDiagnostics",
    "ExecutionRuntimeLifecycleState",
    "ExecutionRuntimeUpdate",
    "create_execution_runtime",
]

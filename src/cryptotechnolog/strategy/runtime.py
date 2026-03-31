"""
Узкий explicit runtime foundation для Phase 9 Strategy Foundation.

Этот runtime:
- стартует и останавливается явно;
- не делает hidden bootstrap;
- собирает typed strategy context из signal truth;
- поддерживает один минимальный deterministic strategy contour;
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
from cryptotechnolog.signals import SignalDirection, SignalSnapshot, SignalStatus

from .events import StrategyActionCandidatePayload, StrategyEventType
from .models import (
    StrategyActionCandidate,
    StrategyContext,
    StrategyDirection,
    StrategyFreshness,
    StrategyReasonCode,
    StrategyStatus,
    StrategyValidity,
    StrategyValidityStatus,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from cryptotechnolog.config.settings import Settings


type StrategyStateKey = tuple[str, str, MarketDataTimeframe, str, str]


class StrategyRuntimeLifecycleState(StrEnum):
    """Lifecycle-состояние strategy runtime."""

    NOT_STARTED = "not_started"
    WARMING = "warming"
    READY = "ready"
    DEGRADED = "degraded"
    STOPPED = "stopped"


@dataclass(slots=True, frozen=True)
class StrategyRuntimeConfig:
    """Typed runtime-конфигурация следующего шага P_9."""

    contour_name: str = "phase9_strategy_contour"
    strategy_name: str = "phase9_foundation_strategy"
    max_candidate_age_seconds: int = 300
    min_signal_confidence_for_actionable: Decimal = Decimal("0.5000")

    def __post_init__(self) -> None:
        if self.max_candidate_age_seconds <= 0:
            raise ValueError("max_candidate_age_seconds должен быть положительным")
        if not (Decimal("0") <= self.min_signal_confidence_for_actionable <= Decimal("1")):
            raise ValueError(
                "min_signal_confidence_for_actionable должен находиться в диапазоне [0, 1]"
            )

    @classmethod
    def from_settings(cls, settings: Settings) -> StrategyRuntimeConfig:
        """Build strategy runtime config from canonical project settings."""
        return cls(
            max_candidate_age_seconds=settings.strategy_max_candidate_age_seconds,
            min_signal_confidence_for_actionable=Decimal(
                str(settings.strategy_min_signal_confidence)
            ),
        )


@dataclass(slots=True)
class StrategyRuntimeDiagnostics:
    """Operator-visible diagnostics contract strategy runtime."""

    started: bool = False
    ready: bool = False
    lifecycle_state: StrategyRuntimeLifecycleState = StrategyRuntimeLifecycleState.NOT_STARTED
    tracked_context_keys: int = 0
    tracked_candidate_keys: int = 0
    actionable_candidate_keys: int = 0
    invalidated_candidate_keys: int = 0
    expired_candidate_keys: int = 0
    last_signal_id: str | None = None
    last_candidate_id: str | None = None
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
            "tracked_candidate_keys": self.tracked_candidate_keys,
            "actionable_candidate_keys": self.actionable_candidate_keys,
            "invalidated_candidate_keys": self.invalidated_candidate_keys,
            "expired_candidate_keys": self.expired_candidate_keys,
            "last_signal_id": self.last_signal_id,
            "last_candidate_id": self.last_candidate_id,
            "last_event_type": self.last_event_type,
            "last_failure_reason": self.last_failure_reason,
            "readiness_reasons": list(self.readiness_reasons),
            "degraded_reasons": list(self.degraded_reasons),
        }


@dataclass(slots=True, frozen=True)
class StrategyRuntimeUpdate:
    """Typed update contract strategy runtime foundation."""

    context: StrategyContext
    candidate: StrategyActionCandidate | None
    event_type: StrategyEventType
    emitted_payload: StrategyActionCandidatePayload | None = None


class StrategyRuntime:
    """Explicit runtime foundation для strategy layer Phase 9."""

    def __init__(
        self,
        config: StrategyRuntimeConfig | None = None,
        *,
        diagnostics_sink: Callable[[dict[str, object]], None] | None = None,
    ) -> None:
        self.config = config or StrategyRuntimeConfig()
        self._diagnostics_sink = diagnostics_sink
        self._diagnostics = StrategyRuntimeDiagnostics()
        self._started = False
        self._contexts: dict[StrategyStateKey, StrategyContext] = {}
        self._candidates: dict[StrategyStateKey, StrategyActionCandidate] = {}
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
            lifecycle_state=StrategyRuntimeLifecycleState.WARMING,
            ready=False,
            last_failure_reason=None,
            readiness_reasons=("no_strategy_context_processed",),
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
            lifecycle_state=StrategyRuntimeLifecycleState.STOPPED,
            ready=False,
            tracked_context_keys=0,
            tracked_candidate_keys=0,
            actionable_candidate_keys=0,
            invalidated_candidate_keys=0,
            expired_candidate_keys=0,
            last_signal_id=None,
            last_candidate_id=None,
            last_event_type=None,
            last_failure_reason=None,
            readiness_reasons=("runtime_stopped",),
            degraded_reasons=(),
        )

    def mark_degraded(self, reason: str) -> None:
        """Зафиксировать деградацию runtime/ingest path."""
        self._refresh_diagnostics(
            lifecycle_state=StrategyRuntimeLifecycleState.DEGRADED,
            ready=False,
            last_failure_reason=reason,
            degraded_reasons=(reason,),
        )

    def get_runtime_diagnostics(self) -> dict[str, object]:
        """Вернуть operator-visible diagnostics."""
        return self._diagnostics.to_dict()

    def ingest_signal(
        self,
        *,
        signal: SignalSnapshot,
        reference_time: datetime,
        metadata: dict[str, object] | None = None,
    ) -> StrategyRuntimeUpdate:
        """Принять signal truth, собрать StrategyContext и обновить strategy state."""
        self._ensure_started("ingest_signal")
        context = self._assemble_strategy_context(
            signal=signal,
            reference_time=reference_time,
            metadata=metadata,
        )
        return self._ingest_strategy_context(context, reference_time=reference_time)

    def get_candidate(
        self,
        *,
        symbol: str,
        exchange: str,
        timeframe: MarketDataTimeframe,
    ) -> StrategyActionCandidate | None:
        """Вернуть последний strategy action candidate по ключу."""
        return self._candidates.get(
            self._build_state_key(exchange=exchange, symbol=symbol, timeframe=timeframe)
        )

    def get_context(
        self,
        *,
        symbol: str,
        exchange: str,
        timeframe: MarketDataTimeframe,
    ) -> StrategyContext | None:
        """Вернуть последний strategy context по ключу."""
        return self._contexts.get(
            self._build_state_key(exchange=exchange, symbol=symbol, timeframe=timeframe)
        )

    def expire_candidates(
        self,
        *,
        reference_time: datetime,
    ) -> tuple[StrategyActionCandidate, ...]:
        """Перевести истёкшие strategy candidates в `EXPIRED` по явному reference time."""
        self._ensure_started("expire_candidates")
        expired: list[StrategyActionCandidate] = []
        for key, candidate in tuple(self._candidates.items()):
            updated = self._expire_candidate_if_needed(candidate, reference_time=reference_time)
            if updated is not candidate:
                self._candidates[key] = updated
                expired.append(updated)
                context = self._contexts.get(key)
                if context is not None:
                    self._refresh_runtime_state(
                        candidate=updated,
                        context=context,
                        event_type=StrategyEventType.STRATEGY_INVALIDATED,
                    )
        return tuple(expired)

    def _assemble_strategy_context(
        self,
        *,
        signal: SignalSnapshot,
        reference_time: datetime,
        metadata: dict[str, object] | None = None,
    ) -> StrategyContext:
        """Детерминированно собрать typed strategy context только из signal truth."""
        observed_inputs = 0
        missing_inputs: list[str] = []
        invalid_reason: str | None = None

        if signal.freshness.is_expired_at(reference_time) or signal.status == SignalStatus.EXPIRED:
            invalid_reason = "signal_expired"
        elif signal.status == SignalStatus.INVALIDATED:
            invalid_reason = "signal_invalidated"
        elif signal.status == SignalStatus.SUPPRESSED:
            missing_inputs.append("actionable_signal")
        elif signal.status == SignalStatus.CANDIDATE:
            missing_inputs.append("ready_signal")
        elif signal.is_actionable:
            observed_inputs += 1
        else:
            invalid_reason = "signal_not_actionable"

        validity = self._build_context_validity(
            observed_inputs=observed_inputs,
            missing_inputs=tuple(dict.fromkeys(missing_inputs)),
            invalid_reason=invalid_reason,
        )
        return StrategyContext(
            strategy_name=self.config.strategy_name,
            contour_name=self.config.contour_name,
            symbol=signal.symbol,
            exchange=signal.exchange,
            timeframe=signal.timeframe,
            observed_at=reference_time,
            signal=signal,
            validity=validity,
            metadata={} if metadata is None else metadata.copy(),
        )

    def _ingest_strategy_context(
        self,
        context: StrategyContext,
        *,
        reference_time: datetime,
    ) -> StrategyRuntimeUpdate:
        key = self._build_state_key(
            exchange=context.exchange,
            symbol=context.symbol,
            timeframe=context.timeframe,
        )
        self._contexts[key] = context
        previous_candidate = self._candidates.get(key)
        candidate = self._build_candidate_from_context(
            context=context,
            previous_candidate=previous_candidate,
        )
        candidate = self._expire_candidate_if_needed(candidate, reference_time=reference_time)
        self._candidates[key] = candidate

        payload = StrategyActionCandidatePayload.from_candidate(candidate)
        event_type = self._resolve_event_type(
            candidate=candidate,
            previous_candidate=previous_candidate,
        )
        self._refresh_runtime_state(
            candidate=candidate,
            context=context,
            event_type=event_type,
        )
        return StrategyRuntimeUpdate(
            context=context,
            candidate=candidate,
            event_type=event_type,
            emitted_payload=payload,
        )

    def _build_candidate_from_context(
        self,
        *,
        context: StrategyContext,
        previous_candidate: StrategyActionCandidate | None,
    ) -> StrategyActionCandidate:
        freshness = StrategyFreshness(
            generated_at=context.observed_at,
            expires_at=context.observed_at
            + timedelta(seconds=self.config.max_candidate_age_seconds),
        )

        if context.validity.status == StrategyValidityStatus.INVALID:
            if self._should_invalidate_previous_candidate(previous_candidate):
                assert previous_candidate is not None
                return self._build_invalidated_candidate(
                    context=context,
                    freshness=freshness,
                    previous_candidate=previous_candidate,
                )
            return StrategyActionCandidate.candidate(
                contour_name=self.config.contour_name,
                strategy_name=self.config.strategy_name,
                symbol=context.symbol,
                exchange=context.exchange,
                timeframe=context.timeframe,
                freshness=freshness,
                validity=context.validity,
                reason_code=StrategyReasonCode.STRATEGY_RULE_BLOCKED,
                metadata={"invalid_reason": context.validity.invalid_reason},
            )

        if context.validity.status == StrategyValidityStatus.WARMING:
            if self._should_invalidate_previous_candidate(previous_candidate):
                assert previous_candidate is not None
                return self._build_invalidated_candidate(
                    context=context,
                    freshness=freshness,
                    previous_candidate=previous_candidate,
                )
            return StrategyActionCandidate.candidate(
                contour_name=self.config.contour_name,
                strategy_name=self.config.strategy_name,
                symbol=context.symbol,
                exchange=context.exchange,
                timeframe=context.timeframe,
                freshness=freshness,
                validity=context.validity,
                reason_code=StrategyReasonCode.CONTEXT_INCOMPLETE,
                metadata={"missing_inputs": context.validity.missing_inputs},
            )

        actionable_candidate = self._evaluate_minimal_contour(
            context=context,
            freshness=freshness,
            previous_candidate=previous_candidate,
        )
        if actionable_candidate is not None:
            return actionable_candidate

        return StrategyActionCandidate(
            candidate_id=self._resolve_candidate_id(previous_candidate),
            contour_name=self.config.contour_name,
            strategy_name=self.config.strategy_name,
            symbol=context.symbol,
            exchange=context.exchange,
            timeframe=context.timeframe,
            freshness=freshness,
            validity=context.validity,
            status=StrategyStatus.SUPPRESSED,
            reason_code=StrategyReasonCode.STRATEGY_RULE_BLOCKED,
            metadata={"suppression_reason": "strategy_conditions_not_met"},
        )

    def _evaluate_minimal_contour(
        self,
        *,
        context: StrategyContext,
        freshness: StrategyFreshness,
        previous_candidate: StrategyActionCandidate | None,
    ) -> StrategyActionCandidate | None:
        signal = context.signal
        if not signal.is_actionable or signal.direction is None:
            return None

        confidence = signal.confidence or Decimal("0")
        if confidence < self.config.min_signal_confidence_for_actionable:
            return None

        direction: StrategyDirection | None = None
        if signal.direction == SignalDirection.BUY:
            direction = StrategyDirection.LONG
        elif signal.direction == SignalDirection.SELL:
            direction = StrategyDirection.SHORT

        if direction is None:
            return None

        return StrategyActionCandidate(
            candidate_id=self._resolve_candidate_id(previous_candidate),
            contour_name=self.config.contour_name,
            strategy_name=self.config.strategy_name,
            symbol=context.symbol,
            exchange=context.exchange,
            timeframe=context.timeframe,
            freshness=freshness,
            validity=context.validity,
            status=StrategyStatus.ACTIONABLE,
            direction=direction,
            originating_signal_id=signal.signal_id,
            confidence=confidence,
            reason_code=StrategyReasonCode.CONTEXT_READY,
            metadata={
                "signal_status": signal.status.value,
                "signal_direction": signal.direction.value,
                "signal_confidence": str(confidence),
            },
        )

    def _build_invalidated_candidate(
        self,
        *,
        context: StrategyContext,
        freshness: StrategyFreshness,
        previous_candidate: StrategyActionCandidate,
    ) -> StrategyActionCandidate:
        metadata = previous_candidate.metadata.copy()
        if context.validity.invalid_reason is not None:
            metadata["invalid_reason"] = context.validity.invalid_reason
        if context.validity.missing_inputs:
            metadata["missing_inputs"] = context.validity.missing_inputs
        metadata["invalidation_reason"] = (
            context.validity.invalid_reason or "strategy_input_truth_lost"
        )

        return StrategyActionCandidate(
            candidate_id=previous_candidate.candidate_id,
            contour_name=self.config.contour_name,
            strategy_name=self.config.strategy_name,
            symbol=context.symbol,
            exchange=context.exchange,
            timeframe=context.timeframe,
            freshness=freshness,
            validity=context.validity,
            status=StrategyStatus.INVALIDATED,
            direction=previous_candidate.direction,
            originating_signal_id=previous_candidate.originating_signal_id,
            confidence=previous_candidate.confidence,
            reason_code=StrategyReasonCode.STRATEGY_INVALIDATED,
            metadata=metadata,
        )

    def _expire_candidate_if_needed(
        self,
        candidate: StrategyActionCandidate,
        *,
        reference_time: datetime,
    ) -> StrategyActionCandidate:
        if candidate.status == StrategyStatus.EXPIRED:
            return candidate
        if not candidate.freshness.is_expired_at(reference_time):
            return candidate
        expired_validity = candidate.validity
        if expired_validity.is_valid:
            expired_validity = replace(
                expired_validity,
                status=StrategyValidityStatus.INVALID,
                invalid_reason="strategy_expired",
            )
        return replace(
            candidate,
            status=StrategyStatus.EXPIRED,
            validity=expired_validity,
            reason_code=StrategyReasonCode.STRATEGY_EXPIRED,
        )

    def _resolve_event_type(
        self,
        *,
        candidate: StrategyActionCandidate,
        previous_candidate: StrategyActionCandidate | None,
    ) -> StrategyEventType:
        if candidate.status in {StrategyStatus.INVALIDATED, StrategyStatus.EXPIRED}:
            return StrategyEventType.STRATEGY_INVALIDATED
        if candidate.status == StrategyStatus.ACTIONABLE:
            return StrategyEventType.STRATEGY_ACTIONABLE
        return StrategyEventType.STRATEGY_CANDIDATE_UPDATED

    def _refresh_runtime_state(
        self,
        *,
        candidate: StrategyActionCandidate,
        context: StrategyContext,
        event_type: StrategyEventType,
    ) -> None:
        tracked_context_keys = len(self._contexts)
        tracked_candidate_keys = len(self._candidates)
        actionable_candidate_keys = sum(
            1
            for snapshot in self._candidates.values()
            if snapshot.status == StrategyStatus.ACTIONABLE
        )
        invalidated_candidate_keys = sum(
            1
            for snapshot in self._candidates.values()
            if snapshot.status == StrategyStatus.INVALIDATED
        )
        expired_candidate_keys = sum(
            1 for snapshot in self._candidates.values() if snapshot.status == StrategyStatus.EXPIRED
        )

        ready = True
        lifecycle_state = StrategyRuntimeLifecycleState.READY
        readiness_reasons: list[str] = []
        degraded_reasons: list[str] = []

        if tracked_context_keys == 0:
            ready = False
            lifecycle_state = StrategyRuntimeLifecycleState.WARMING
            readiness_reasons.append("no_strategy_context_processed")
        elif context.validity.status == StrategyValidityStatus.WARMING:
            ready = False
            lifecycle_state = StrategyRuntimeLifecycleState.WARMING
            readiness_reasons.append("strategy_context_warming")
        elif context.validity.status == StrategyValidityStatus.INVALID:
            ready = False
            lifecycle_state = StrategyRuntimeLifecycleState.DEGRADED
            readiness_reasons.append("strategy_context_invalid")
            if context.validity.invalid_reason is not None:
                degraded_reasons.append(context.validity.invalid_reason)

        self._refresh_diagnostics(
            ready=ready,
            lifecycle_state=lifecycle_state,
            tracked_context_keys=tracked_context_keys,
            tracked_candidate_keys=tracked_candidate_keys,
            actionable_candidate_keys=actionable_candidate_keys,
            invalidated_candidate_keys=invalidated_candidate_keys,
            expired_candidate_keys=expired_candidate_keys,
            last_signal_id=str(context.signal.signal_id),
            last_candidate_id=str(candidate.candidate_id),
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
    ) -> StrategyValidity:
        required_inputs = 1
        if invalid_reason is not None:
            return StrategyValidity(
                status=StrategyValidityStatus.INVALID,
                observed_inputs=observed_inputs,
                required_inputs=required_inputs,
                missing_inputs=missing_inputs,
                invalid_reason=invalid_reason,
            )
        if missing_inputs:
            return StrategyValidity(
                status=StrategyValidityStatus.WARMING,
                observed_inputs=observed_inputs,
                required_inputs=required_inputs,
                missing_inputs=missing_inputs,
            )
        return StrategyValidity(
            status=StrategyValidityStatus.VALID,
            observed_inputs=observed_inputs,
            required_inputs=required_inputs,
        )

    def _build_state_key(
        self,
        *,
        exchange: str,
        symbol: str,
        timeframe: MarketDataTimeframe,
    ) -> StrategyStateKey:
        return (
            exchange,
            symbol,
            timeframe,
            self.config.contour_name,
            self.config.strategy_name,
        )

    @staticmethod
    def _should_invalidate_previous_candidate(
        previous_candidate: StrategyActionCandidate | None,
    ) -> bool:
        return (
            previous_candidate is not None
            and previous_candidate.validity.is_valid
            and previous_candidate.status
            not in {StrategyStatus.EXPIRED, StrategyStatus.INVALIDATED}
        )

    @staticmethod
    def _resolve_candidate_id(previous_candidate: StrategyActionCandidate | None) -> UUID:
        if previous_candidate is not None:
            return previous_candidate.candidate_id
        return uuid4()

    def _ensure_started(self, operation: str) -> None:
        if not self._started:
            raise RuntimeError(
                f"StrategyRuntime не запущен. Операция {operation} недоступна до start()."
            )

    def _refresh_diagnostics(self, **updates: Any) -> None:
        current = asdict(self._diagnostics)
        current.update(updates)
        self._diagnostics = StrategyRuntimeDiagnostics(
            started=self._started,
            ready=bool(current["ready"]),
            lifecycle_state=StrategyRuntimeLifecycleState(current["lifecycle_state"]),
            tracked_context_keys=int(current["tracked_context_keys"]),
            tracked_candidate_keys=int(current["tracked_candidate_keys"]),
            actionable_candidate_keys=int(current["actionable_candidate_keys"]),
            invalidated_candidate_keys=int(current["invalidated_candidate_keys"]),
            expired_candidate_keys=int(current["expired_candidate_keys"]),
            last_signal_id=current["last_signal_id"],
            last_candidate_id=current["last_candidate_id"],
            last_event_type=current["last_event_type"],
            last_failure_reason=current["last_failure_reason"],
            readiness_reasons=list(current.get("readiness_reasons", [])),
            degraded_reasons=list(current.get("degraded_reasons", [])),
        )
        self._push_diagnostics()

    def _push_diagnostics(self) -> None:
        if self._diagnostics_sink is not None:
            self._diagnostics_sink(self.get_runtime_diagnostics())


def create_strategy_runtime(
    *,
    config: StrategyRuntimeConfig | None = None,
    diagnostics_sink: Callable[[dict[str, object]], None] | None = None,
) -> StrategyRuntime:
    """Собрать explicit strategy runtime foundation."""
    return StrategyRuntime(
        config=config or StrategyRuntimeConfig.from_settings(get_settings()),
        diagnostics_sink=diagnostics_sink,
    )


__all__ = [
    "StrategyRuntime",
    "StrategyRuntimeConfig",
    "StrategyRuntimeDiagnostics",
    "StrategyRuntimeLifecycleState",
    "StrategyRuntimeUpdate",
    "create_strategy_runtime",
]

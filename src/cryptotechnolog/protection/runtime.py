"""
Узкий explicit runtime foundation для Phase 15 Protection / Supervisor Foundation.

Этот runtime:
- стартует и останавливается явно;
- не делает hidden bootstrap;
- собирает typed protection context из portfolio-governor truth;
- поддерживает один минимальный deterministic protection contour;
- хранит query/state-first truth и operator-visible diagnostics.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from cryptotechnolog.config import get_settings
from cryptotechnolog.market_data import MarketDataTimeframe
from cryptotechnolog.portfolio_governor import GovernorStatus, PortfolioGovernorCandidate

from .events import ProtectionEventType, ProtectionPayload
from .models import (
    ProtectionContext,
    ProtectionDecision,
    ProtectionFreshness,
    ProtectionReasonCode,
    ProtectionSource,
    ProtectionStatus,
    ProtectionSupervisorCandidate,
    ProtectionValidity,
    ProtectionValidityStatus,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from cryptotechnolog.config.settings import Settings


type ProtectionStateKey = tuple[str, str, MarketDataTimeframe, str, str]


class ProtectionRuntimeLifecycleState(StrEnum):
    """Lifecycle-состояние protection runtime."""

    NOT_STARTED = "not_started"
    WARMING = "warming"
    READY = "ready"
    DEGRADED = "degraded"
    STOPPED = "stopped"


@dataclass(slots=True, frozen=True)
class ProtectionRuntimeConfig:
    """Typed runtime-конфигурация следующего шага P_15."""

    contour_name: str = "phase15_protection_contour"
    supervisor_name: str = "phase15_protection"
    max_candidate_age_seconds: int = 300
    halt_priority_threshold: Decimal = Decimal("0.9000")
    freeze_priority_threshold: Decimal = Decimal("0.9750")

    def __post_init__(self) -> None:
        if self.max_candidate_age_seconds <= 0:
            raise ValueError("max_candidate_age_seconds должен быть положительным")
        if not (Decimal("0") <= self.halt_priority_threshold <= Decimal("1")):
            raise ValueError("halt_priority_threshold должен находиться в диапазоне [0, 1]")
        if not (Decimal("0") <= self.freeze_priority_threshold <= Decimal("1")):
            raise ValueError("freeze_priority_threshold должен находиться в диапазоне [0, 1]")
        if self.freeze_priority_threshold < self.halt_priority_threshold:
            raise ValueError(
                "freeze_priority_threshold не должен быть меньше halt_priority_threshold"
            )

    @classmethod
    def from_settings(cls, settings: Settings) -> ProtectionRuntimeConfig:
        """Собрать protection runtime config из canonical project settings."""
        return cls(
            halt_priority_threshold=Decimal(str(settings.protection_halt_priority_threshold)),
            freeze_priority_threshold=Decimal(str(settings.protection_freeze_priority_threshold)),
        )


@dataclass(slots=True)
class ProtectionRuntimeDiagnostics:
    """Operator-visible diagnostics contract protection runtime."""

    started: bool = False
    ready: bool = False
    lifecycle_state: ProtectionRuntimeLifecycleState = ProtectionRuntimeLifecycleState.NOT_STARTED
    tracked_context_keys: int = 0
    tracked_protection_keys: int = 0
    protected_keys: int = 0
    halted_keys: int = 0
    frozen_keys: int = 0
    invalidated_protection_keys: int = 0
    expired_protection_keys: int = 0
    last_governor_id: str | None = None
    last_protection_id: str | None = None
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
            "tracked_protection_keys": self.tracked_protection_keys,
            "protected_keys": self.protected_keys,
            "halted_keys": self.halted_keys,
            "frozen_keys": self.frozen_keys,
            "invalidated_protection_keys": self.invalidated_protection_keys,
            "expired_protection_keys": self.expired_protection_keys,
            "last_governor_id": self.last_governor_id,
            "last_protection_id": self.last_protection_id,
            "last_event_type": self.last_event_type,
            "last_failure_reason": self.last_failure_reason,
            "readiness_reasons": list(self.readiness_reasons),
            "degraded_reasons": list(self.degraded_reasons),
        }


@dataclass(slots=True, frozen=True)
class ProtectionRuntimeUpdate:
    """Typed update contract protection runtime foundation."""

    context: ProtectionContext
    candidate: ProtectionSupervisorCandidate | None
    event_type: ProtectionEventType
    emitted_payload: ProtectionPayload | None = None


class ProtectionRuntime:
    """Explicit runtime foundation для protection layer Phase 15."""

    def __init__(
        self,
        config: ProtectionRuntimeConfig | None = None,
        *,
        diagnostics_sink: Callable[[dict[str, object]], None] | None = None,
    ) -> None:
        self.config = config or ProtectionRuntimeConfig()
        self._diagnostics_sink = diagnostics_sink
        self._diagnostics = ProtectionRuntimeDiagnostics()
        self._started = False
        self._contexts: dict[ProtectionStateKey, ProtectionContext] = {}
        self._candidates: dict[ProtectionStateKey, ProtectionSupervisorCandidate] = {}
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
            lifecycle_state=ProtectionRuntimeLifecycleState.WARMING,
            ready=False,
            last_failure_reason=None,
            readiness_reasons=("no_protection_context_processed",),
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
            lifecycle_state=ProtectionRuntimeLifecycleState.STOPPED,
            ready=False,
            tracked_context_keys=0,
            tracked_protection_keys=0,
            protected_keys=0,
            halted_keys=0,
            frozen_keys=0,
            invalidated_protection_keys=0,
            expired_protection_keys=0,
            last_governor_id=None,
            last_protection_id=None,
            last_event_type=None,
            last_failure_reason=None,
            readiness_reasons=("runtime_stopped",),
            degraded_reasons=(),
        )

    def ingest_governor(
        self,
        *,
        governor: PortfolioGovernorCandidate,
        reference_time: datetime,
        metadata: dict[str, object] | None = None,
    ) -> ProtectionRuntimeUpdate:
        """Принять portfolio-governor truth, собрать protection context и обновить state."""
        self._ensure_started("ingest_governor")
        context = self._assemble_protection_context(
            governor=governor,
            reference_time=reference_time,
            metadata=metadata,
        )
        return self._ingest_protection_context(context, reference_time=reference_time)

    def get_candidate(
        self,
        *,
        symbol: str,
        exchange: str,
        timeframe: MarketDataTimeframe,
    ) -> ProtectionSupervisorCandidate | None:
        """Вернуть текущее protection state по ключу."""
        return self._candidates.get(
            self._build_state_key(exchange=exchange, symbol=symbol, timeframe=timeframe)
        )

    def get_context(
        self,
        *,
        symbol: str,
        exchange: str,
        timeframe: MarketDataTimeframe,
    ) -> ProtectionContext | None:
        """Вернуть последний assembled protection context."""
        return self._contexts.get(
            self._build_state_key(exchange=exchange, symbol=symbol, timeframe=timeframe)
        )

    def expire_candidates(
        self,
        *,
        reference_time: datetime,
    ) -> tuple[ProtectionRuntimeUpdate, ...]:
        """Переоценить lifecycle truth относительно reference time."""
        self._ensure_started("expire_candidates")
        updates: list[ProtectionRuntimeUpdate] = []
        for key, candidate in tuple(self._candidates.items()):
            updated = self._expire_candidate_if_needed(candidate, reference_time=reference_time)
            if updated is not candidate:
                self._candidates[key] = updated
                context = self._contexts[key]
                payload = ProtectionPayload.from_candidate(updated)
                updates.append(
                    ProtectionRuntimeUpdate(
                        context=context,
                        candidate=updated,
                        event_type=ProtectionEventType.PROTECTION_INVALIDATED,
                        emitted_payload=payload,
                    )
                )
                self._update_diagnostics_for_candidate(
                    candidate=updated,
                    event_type=ProtectionEventType.PROTECTION_INVALIDATED,
                )
        return tuple(updates)

    def mark_degraded(self, reason: str) -> None:
        """Зафиксировать деградацию ingest/runtime path."""
        self._refresh_diagnostics(
            lifecycle_state=ProtectionRuntimeLifecycleState.DEGRADED,
            ready=False,
            last_failure_reason=reason,
            degraded_reasons=(reason,),
        )

    def get_runtime_diagnostics(self) -> dict[str, object]:
        """Вернуть operator-visible diagnostics."""
        return self._diagnostics.to_dict()

    def _assemble_protection_context(
        self,
        *,
        governor: PortfolioGovernorCandidate,
        reference_time: datetime,
        metadata: dict[str, object] | None,
    ) -> ProtectionContext:
        observed_inputs = 1
        required_inputs = 1
        missing_inputs: list[str] = []
        invalid_reason: str | None = None

        if (
            governor.freshness.is_expired_at(reference_time)
            or governor.status == GovernorStatus.EXPIRED
        ):
            invalid_reason = "portfolio_governor_expired"
        elif governor.status == GovernorStatus.INVALIDATED:
            invalid_reason = "portfolio_governor_invalidated"
        elif governor.status == GovernorStatus.CANDIDATE:
            missing_inputs.append("approved_governor")
        elif governor.is_approved:
            pass
        else:
            invalid_reason = "portfolio_governor_not_approved"

        if invalid_reason is not None:
            validity = ProtectionValidity(
                status=ProtectionValidityStatus.INVALID,
                observed_inputs=observed_inputs,
                required_inputs=required_inputs,
                invalid_reason=invalid_reason,
            )
        elif missing_inputs:
            validity = ProtectionValidity(
                status=ProtectionValidityStatus.WARMING,
                observed_inputs=observed_inputs - len(missing_inputs),
                required_inputs=required_inputs,
                missing_inputs=tuple(missing_inputs),
            )
        else:
            validity = ProtectionValidity(
                status=ProtectionValidityStatus.VALID,
                observed_inputs=observed_inputs,
                required_inputs=required_inputs,
            )

        context_metadata: dict[str, object] = {
            "governor_status": governor.status.value,
            "governor_decision": governor.decision.value,
        }
        if metadata:
            context_metadata.update(metadata)

        return ProtectionContext(
            supervisor_name=self.config.supervisor_name,
            contour_name=self.config.contour_name,
            symbol=governor.symbol,
            exchange=governor.exchange,
            timeframe=governor.timeframe,
            observed_at=reference_time,
            source=ProtectionSource.PORTFOLIO_GOVERNOR,
            governor=governor,
            validity=validity,
            metadata=context_metadata,
        )

    def _ingest_protection_context(
        self,
        context: ProtectionContext,
        *,
        reference_time: datetime,
    ) -> ProtectionRuntimeUpdate:
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

        payload = ProtectionPayload.from_candidate(candidate)
        event_type = self._resolve_event_type(candidate=candidate)
        self._update_diagnostics_for_candidate(candidate=candidate, event_type=event_type)

        return ProtectionRuntimeUpdate(
            context=context,
            candidate=candidate,
            event_type=event_type,
            emitted_payload=payload,
        )

    def _build_candidate_from_context(
        self,
        *,
        context: ProtectionContext,
        reference_time: datetime,
        previous_candidate: ProtectionSupervisorCandidate | None,
    ) -> ProtectionSupervisorCandidate:
        freshness = ProtectionFreshness(
            generated_at=reference_time,
            expires_at=reference_time + timedelta(seconds=self.config.max_candidate_age_seconds),
        )

        if context.validity.status == ProtectionValidityStatus.INVALID:
            if self._should_invalidate_previous_candidate(previous_candidate):
                assert previous_candidate is not None
                return self._build_invalidated_candidate(
                    freshness=freshness,
                    context=context,
                    previous_candidate=previous_candidate,
                )
            return ProtectionSupervisorCandidate(
                protection_id=self._resolve_protection_id(previous_candidate),
                contour_name=self.config.contour_name,
                supervisor_name=self.config.supervisor_name,
                symbol=context.symbol,
                exchange=context.exchange,
                timeframe=context.timeframe,
                source=context.source,
                freshness=freshness,
                validity=context.validity,
                status=ProtectionStatus.CANDIDATE,
                decision=ProtectionDecision.PROTECT,
                originating_governor_id=context.governor.governor_id,
                confidence=context.governor.confidence,
                priority_score=context.governor.priority_score,
                reason_code=ProtectionReasonCode.GOVERNOR_NOT_APPROVED,
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
            return ProtectionSupervisorCandidate.candidate(
                contour_name=self.config.contour_name,
                supervisor_name=self.config.supervisor_name,
                symbol=context.symbol,
                exchange=context.exchange,
                timeframe=context.timeframe,
                source=context.source,
                freshness=freshness,
                validity=context.validity,
                decision=ProtectionDecision.PROTECT,
                status=ProtectionStatus.CANDIDATE,
                originating_governor_id=context.governor.governor_id,
                confidence=context.governor.confidence,
                priority_score=context.governor.priority_score,
                reason_code=ProtectionReasonCode.CONTEXT_INCOMPLETE,
                metadata={"missing_inputs": context.validity.missing_inputs},
            )

        return self._evaluate_minimal_contour(
            context=context,
            freshness=freshness,
            previous_candidate=previous_candidate,
        )

    def _evaluate_minimal_contour(
        self,
        *,
        context: ProtectionContext,
        freshness: ProtectionFreshness,
        previous_candidate: ProtectionSupervisorCandidate | None,
    ) -> ProtectionSupervisorCandidate:
        governor = context.governor
        priority_score = governor.priority_score or governor.confidence or Decimal("0")
        confidence = governor.confidence

        if priority_score >= self.config.freeze_priority_threshold:
            return ProtectionSupervisorCandidate(
                protection_id=self._resolve_protection_id(previous_candidate),
                contour_name=self.config.contour_name,
                supervisor_name=self.config.supervisor_name,
                symbol=context.symbol,
                exchange=context.exchange,
                timeframe=context.timeframe,
                source=context.source,
                freshness=freshness,
                validity=context.validity,
                status=ProtectionStatus.FROZEN,
                decision=ProtectionDecision.FREEZE,
                originating_governor_id=governor.governor_id,
                confidence=confidence,
                priority_score=priority_score,
                reason_code=ProtectionReasonCode.PROTECTION_FROZEN,
                metadata={
                    "governor_status": governor.status.value,
                    "priority_score": str(priority_score),
                },
            )

        if priority_score >= self.config.halt_priority_threshold:
            return ProtectionSupervisorCandidate(
                protection_id=self._resolve_protection_id(previous_candidate),
                contour_name=self.config.contour_name,
                supervisor_name=self.config.supervisor_name,
                symbol=context.symbol,
                exchange=context.exchange,
                timeframe=context.timeframe,
                source=context.source,
                freshness=freshness,
                validity=context.validity,
                status=ProtectionStatus.HALTED,
                decision=ProtectionDecision.HALT,
                originating_governor_id=governor.governor_id,
                confidence=confidence,
                priority_score=priority_score,
                reason_code=ProtectionReasonCode.PROTECTION_HALTED,
                metadata={
                    "governor_status": governor.status.value,
                    "priority_score": str(priority_score),
                },
            )

        return ProtectionSupervisorCandidate(
            protection_id=self._resolve_protection_id(previous_candidate),
            contour_name=self.config.contour_name,
            supervisor_name=self.config.supervisor_name,
            symbol=context.symbol,
            exchange=context.exchange,
            timeframe=context.timeframe,
            source=context.source,
            freshness=freshness,
            validity=context.validity,
            status=ProtectionStatus.PROTECTED,
            decision=ProtectionDecision.PROTECT,
            originating_governor_id=governor.governor_id,
            confidence=confidence,
            priority_score=priority_score,
            reason_code=ProtectionReasonCode.PROTECTION_PROTECTED,
            metadata={
                "governor_status": governor.status.value,
                "priority_score": str(priority_score),
            },
        )

    def _build_invalidated_candidate(
        self,
        *,
        freshness: ProtectionFreshness,
        context: ProtectionContext,
        previous_candidate: ProtectionSupervisorCandidate,
    ) -> ProtectionSupervisorCandidate:
        metadata = previous_candidate.metadata.copy()
        metadata["invalid_reason"] = context.validity.invalid_reason or ",".join(
            context.validity.missing_inputs
        )
        invalid_validity = ProtectionValidity(
            status=ProtectionValidityStatus.INVALID,
            observed_inputs=context.validity.observed_inputs,
            required_inputs=context.validity.required_inputs,
            missing_inputs=context.validity.missing_inputs,
            invalid_reason=context.validity.invalid_reason or "protection_invalidated",
        )
        return ProtectionSupervisorCandidate(
            protection_id=previous_candidate.protection_id,
            contour_name=previous_candidate.contour_name,
            supervisor_name=previous_candidate.supervisor_name,
            symbol=previous_candidate.symbol,
            exchange=previous_candidate.exchange,
            timeframe=previous_candidate.timeframe,
            source=previous_candidate.source,
            freshness=freshness,
            validity=invalid_validity,
            status=ProtectionStatus.INVALIDATED,
            decision=ProtectionDecision.HALT,
            originating_governor_id=previous_candidate.originating_governor_id,
            confidence=previous_candidate.confidence,
            priority_score=previous_candidate.priority_score,
            reason_code=ProtectionReasonCode.PROTECTION_INVALIDATED,
            metadata=metadata,
        )

    def _expire_candidate_if_needed(
        self,
        candidate: ProtectionSupervisorCandidate,
        *,
        reference_time: datetime,
    ) -> ProtectionSupervisorCandidate:
        if candidate.status == ProtectionStatus.EXPIRED:
            return candidate
        if not candidate.freshness.is_expired_at(reference_time):
            return candidate
        expired_validity = candidate.validity
        if expired_validity.status == ProtectionValidityStatus.VALID:
            expired_validity = ProtectionValidity(
                status=ProtectionValidityStatus.INVALID,
                observed_inputs=expired_validity.observed_inputs,
                required_inputs=expired_validity.required_inputs,
                missing_inputs=expired_validity.missing_inputs,
                invalid_reason="protection_expired",
            )
        return replace(
            candidate,
            validity=expired_validity,
            status=ProtectionStatus.EXPIRED,
            reason_code=ProtectionReasonCode.PROTECTION_EXPIRED,
        )

    def _resolve_event_type(
        self,
        *,
        candidate: ProtectionSupervisorCandidate,
    ) -> ProtectionEventType:
        if candidate.status in {ProtectionStatus.INVALIDATED, ProtectionStatus.EXPIRED}:
            return ProtectionEventType.PROTECTION_INVALIDATED
        if candidate.status == ProtectionStatus.FROZEN:
            return ProtectionEventType.PROTECTION_FROZEN
        if candidate.status == ProtectionStatus.HALTED:
            return ProtectionEventType.PROTECTION_HALTED
        if candidate.status == ProtectionStatus.PROTECTED:
            return ProtectionEventType.PROTECTION_PROTECTED
        return ProtectionEventType.PROTECTION_CANDIDATE_UPDATED

    def _update_diagnostics_for_candidate(
        self,
        *,
        candidate: ProtectionSupervisorCandidate,
        event_type: ProtectionEventType,
    ) -> None:
        tracked_context_keys = len(self._contexts)
        tracked_protection_keys = len(self._candidates)
        protected_keys = sum(
            1
            for snapshot in self._candidates.values()
            if snapshot.status == ProtectionStatus.PROTECTED
        )
        halted_keys = sum(
            1
            for snapshot in self._candidates.values()
            if snapshot.status == ProtectionStatus.HALTED
        )
        frozen_keys = sum(
            1
            for snapshot in self._candidates.values()
            if snapshot.status == ProtectionStatus.FROZEN
        )
        invalidated_protection_keys = sum(
            1
            for snapshot in self._candidates.values()
            if snapshot.status == ProtectionStatus.INVALIDATED
        )
        expired_protection_keys = sum(
            1
            for snapshot in self._candidates.values()
            if snapshot.status == ProtectionStatus.EXPIRED
        )

        readiness_reasons: tuple[str, ...] = ()
        lifecycle_state = ProtectionRuntimeLifecycleState.READY
        ready = True

        if tracked_context_keys == 0:
            lifecycle_state = ProtectionRuntimeLifecycleState.WARMING
            ready = False
            readiness_reasons = ("no_protection_context_processed",)
        elif candidate.validity.is_warming:
            lifecycle_state = ProtectionRuntimeLifecycleState.WARMING
            ready = False
            readiness_reasons = tuple(candidate.validity.missing_inputs) or (
                "protection_context_warming",
            )
        elif self._diagnostics.degraded_reasons:
            lifecycle_state = ProtectionRuntimeLifecycleState.DEGRADED
            ready = False
            readiness_reasons = ("runtime_degraded",)

        self._refresh_diagnostics(
            lifecycle_state=lifecycle_state,
            ready=ready,
            tracked_context_keys=tracked_context_keys,
            tracked_protection_keys=tracked_protection_keys,
            protected_keys=protected_keys,
            halted_keys=halted_keys,
            frozen_keys=frozen_keys,
            invalidated_protection_keys=invalidated_protection_keys,
            expired_protection_keys=expired_protection_keys,
            last_governor_id=str(candidate.originating_governor_id)
            if candidate.originating_governor_id is not None
            else None,
            last_protection_id=str(candidate.protection_id),
            last_event_type=event_type.value,
            readiness_reasons=readiness_reasons,
        )

    def _build_state_key(
        self,
        *,
        exchange: str,
        symbol: str,
        timeframe: MarketDataTimeframe,
    ) -> ProtectionStateKey:
        return (
            exchange,
            symbol,
            timeframe,
            self.config.contour_name,
            self.config.supervisor_name,
        )

    @staticmethod
    def _should_invalidate_previous_candidate(
        previous_candidate: ProtectionSupervisorCandidate | None,
    ) -> bool:
        return (
            previous_candidate is not None
            and previous_candidate.validity.is_valid
            and previous_candidate.status
            not in {ProtectionStatus.EXPIRED, ProtectionStatus.INVALIDATED}
        )

    @staticmethod
    def _resolve_protection_id(
        previous_candidate: ProtectionSupervisorCandidate | None,
    ) -> UUID:
        if previous_candidate is not None:
            return previous_candidate.protection_id
        return uuid4()

    def _ensure_started(self, operation: str) -> None:
        if not self._started:
            raise RuntimeError(
                f"ProtectionRuntime не запущен. Операция {operation} недоступна до start()."
            )

    def _refresh_diagnostics(self, **updates: object) -> None:
        current = asdict(self._diagnostics)
        current.update(updates)
        self._diagnostics = ProtectionRuntimeDiagnostics(
            started=self._started,
            ready=bool(current["ready"]),
            lifecycle_state=ProtectionRuntimeLifecycleState(current["lifecycle_state"]),
            tracked_context_keys=int(current["tracked_context_keys"]),
            tracked_protection_keys=int(current["tracked_protection_keys"]),
            protected_keys=int(current["protected_keys"]),
            halted_keys=int(current["halted_keys"]),
            frozen_keys=int(current["frozen_keys"]),
            invalidated_protection_keys=int(current["invalidated_protection_keys"]),
            expired_protection_keys=int(current["expired_protection_keys"]),
            last_governor_id=current["last_governor_id"],
            last_protection_id=current["last_protection_id"],
            last_event_type=current["last_event_type"],
            last_failure_reason=current["last_failure_reason"],
            readiness_reasons=list(current["readiness_reasons"]),
            degraded_reasons=list(current["degraded_reasons"]),
        )
        self._push_diagnostics()

    def _push_diagnostics(self) -> None:
        if self._diagnostics_sink is not None:
            self._diagnostics_sink(self._diagnostics.to_dict())


def create_protection_runtime(
    config: ProtectionRuntimeConfig | None = None,
    *,
    diagnostics_sink: Callable[[dict[str, object]], None] | None = None,
) -> ProtectionRuntime:
    """Фабрика explicit runtime foundation protection layer."""
    return ProtectionRuntime(
        config=config or ProtectionRuntimeConfig.from_settings(get_settings()),
        diagnostics_sink=diagnostics_sink,
    )


__all__ = [
    "ProtectionRuntime",
    "ProtectionRuntimeConfig",
    "ProtectionRuntimeDiagnostics",
    "ProtectionRuntimeLifecycleState",
    "ProtectionRuntimeUpdate",
    "ProtectionStateKey",
    "create_protection_runtime",
]

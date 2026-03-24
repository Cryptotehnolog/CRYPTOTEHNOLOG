"""
Узкий explicit runtime foundation для Phase 19 Paper Trading Foundation.

Этот runtime:
- стартует и останавливается явно;
- не делает hidden bootstrap;
- собирает typed paper context из existing runtime truths;
- поддерживает один минимальный deterministic rehearsal contour;
- хранит query/state-first truth и operator-visible diagnostics.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, ClassVar

from cryptotechnolog.market_data import MarketDataTimeframe
from cryptotechnolog.oms import OmsLifecycleStatus

from .events import PaperEventType, PaperRehearsalPayload
from .models import (
    PaperContext,
    PaperDecision,
    PaperFreshness,
    PaperReasonCode,
    PaperRehearsalCandidate,
    PaperSource,
    PaperStatus,
    PaperValidity,
    PaperValidityStatus,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from uuid import UUID

    from cryptotechnolog.manager import ManagerWorkflowCandidate
    from cryptotechnolog.oms import OmsOrderRecord
    from cryptotechnolog.validation import ValidationReviewCandidate


type PaperStateKey = tuple[str, str, MarketDataTimeframe]


class PaperRuntimeLifecycleState(StrEnum):
    """Lifecycle-состояние paper runtime."""

    NOT_STARTED = "not_started"
    WARMING = "warming"
    READY = "ready"
    DEGRADED = "degraded"
    STOPPED = "stopped"


@dataclass(slots=True, frozen=True)
class PaperRuntimeConfig:
    """Typed runtime-конфигурация paper foundation."""

    contour_name: str = "phase19_paper_contour"
    paper_name: str = "phase19_paper"
    max_rehearsal_age_seconds: int = 3600

    def __post_init__(self) -> None:
        if self.max_rehearsal_age_seconds <= 0:
            raise ValueError("max_rehearsal_age_seconds должен быть положительным")


@dataclass(slots=True)
class PaperRuntimeDiagnostics:
    """Operator-visible diagnostics contract paper runtime."""

    started: bool = False
    ready: bool = False
    lifecycle_state: PaperRuntimeLifecycleState = PaperRuntimeLifecycleState.NOT_STARTED
    tracked_contexts: int = 0
    tracked_active_rehearsals: int = 0
    tracked_historical_rehearsals: int = 0
    last_rehearsal_id: str | None = None
    last_event_type: str | None = None
    last_failure_reason: str | None = None
    readiness_reasons: list[str] = field(default_factory=list)
    degraded_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        """Преобразовать diagnostics в operator-facing словарь."""
        result = asdict(self)
        result["lifecycle_state"] = self.lifecycle_state.value
        return result


@dataclass(slots=True, frozen=True)
class PaperRuntimeUpdate:
    """Typed update contract paper runtime foundation."""

    context: PaperContext | None
    rehearsal_candidate: PaperRehearsalCandidate | None
    event_type: PaperEventType | None
    emitted_payload: PaperRehearsalPayload | None = None


class PaperRuntime:
    """Explicit runtime foundation для paper layer Phase 19."""

    _TERMINAL_STATUSES: ClassVar[set[PaperStatus]] = {
        PaperStatus.INVALIDATED,
        PaperStatus.EXPIRED,
    }

    def __init__(
        self,
        config: PaperRuntimeConfig | None = None,
        *,
        diagnostics_sink: Callable[[dict[str, object]], None] | None = None,
    ) -> None:
        self.config = config or PaperRuntimeConfig()
        self._diagnostics_sink = diagnostics_sink
        self._diagnostics = PaperRuntimeDiagnostics()
        self._started = False
        self._contexts: dict[PaperStateKey, PaperContext] = {}
        self._active_rehearsals: dict[PaperStateKey, PaperRehearsalCandidate] = {}
        self._historical_rehearsals: dict[PaperStateKey, PaperRehearsalCandidate] = {}
        self._rehearsal_key_by_id: dict[UUID, PaperStateKey] = {}
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
            lifecycle_state=PaperRuntimeLifecycleState.WARMING,
            ready=False,
            last_failure_reason=None,
            readiness_reasons=("no_paper_rehearsal_processed",),
            degraded_reasons=(),
        )

    async def stop(self) -> None:
        """Остановить runtime и очистить operator-visible state."""
        if not self._started:
            return
        self._started = False
        self._contexts = {}
        self._active_rehearsals = {}
        self._historical_rehearsals = {}
        self._rehearsal_key_by_id = {}
        self._diagnostics.last_rehearsal_id = None
        self._diagnostics.last_event_type = None
        self._refresh_diagnostics(
            lifecycle_state=PaperRuntimeLifecycleState.STOPPED,
            ready=False,
            last_rehearsal_id=None,
            last_event_type=None,
            last_failure_reason=None,
            readiness_reasons=("runtime_stopped",),
            degraded_reasons=(),
        )

    def get_context(self, key: PaperStateKey) -> PaperContext | None:
        """Вернуть последний paper context по state key."""
        return self._contexts.get(key)

    def get_candidate(self, key: PaperStateKey) -> PaperRehearsalCandidate | None:
        """Вернуть active rehearsal candidate по state key."""
        return self._active_rehearsals.get(key)

    def get_historical_candidate(self, key: PaperStateKey) -> PaperRehearsalCandidate | None:
        """Вернуть terminal rehearsal candidate по state key."""
        return self._historical_rehearsals.get(key)

    def list_active_candidates(self) -> tuple[PaperRehearsalCandidate, ...]:
        """Вернуть все active paper rehearsal candidates."""
        return tuple(self._active_rehearsals.values())

    def list_historical_candidates(self) -> tuple[PaperRehearsalCandidate, ...]:
        """Вернуть все historical paper rehearsal candidates."""
        return tuple(self._historical_rehearsals.values())

    def get_runtime_diagnostics(self) -> dict[str, object]:
        """Вернуть текущую operator-visible diagnostics truth."""
        return self._diagnostics.to_dict()

    def mark_degraded(self, reason: str) -> None:
        """Явно пометить runtime как degraded без смешения с bootstrap truth."""
        reasons = tuple(dict.fromkeys((*self._diagnostics.degraded_reasons, reason)))
        self._refresh_diagnostics(
            lifecycle_state=PaperRuntimeLifecycleState.DEGRADED,
            ready=False,
            last_failure_reason=reason,
            degraded_reasons=reasons,
        )

    def ingest_truths(
        self,
        *,
        manager: ManagerWorkflowCandidate | None,
        validation: ValidationReviewCandidate | None,
        oms_order: OmsOrderRecord | None,
        reference_time: datetime,
    ) -> PaperRuntimeUpdate:
        """Собрать paper context и обновить rehearsal candidate из existing truths."""
        self._ensure_started()
        key = self._resolve_state_key(
            manager=manager,
            validation=validation,
            oms_order=oms_order,
        )
        if key is None:
            self.mark_degraded("paper_truths_missing_coordinates")
            return PaperRuntimeUpdate(context=None, rehearsal_candidate=None, event_type=None)

        validity, reason_code = self._build_validity(
            manager=manager,
            validation=validation,
            oms_order=oms_order,
            reference_time=reference_time,
        )

        if manager is None or validation is None:
            self._refresh_diagnostics(
                lifecycle_state=PaperRuntimeLifecycleState.WARMING,
                ready=False,
                readiness_reasons=tuple(validity.missing_inputs) or ("paper_context_incomplete",),
                last_failure_reason=None,
            )
            return PaperRuntimeUpdate(context=None, rehearsal_candidate=None, event_type=None)

        context = self._assemble_paper_context(
            symbol=key[0],
            exchange=key[1],
            timeframe=key[2],
            manager=manager,
            validation=validation,
            oms_order=oms_order,
            validity=validity,
            reference_time=reference_time,
        )
        self._contexts[key] = context

        update = self._build_update_for_context(
            key=key,
            context=context,
            reference_time=reference_time,
            reason_code=reason_code,
        )
        self._push_diagnostics()
        return update

    def expire_candidates(self, *, reference_time: datetime) -> tuple[PaperRehearsalCandidate, ...]:
        """Перевести устаревшие active rehearsal candidates в EXPIRED."""
        expired: list[PaperRehearsalCandidate] = []
        for key, candidate in tuple(self._active_rehearsals.items()):
            if not candidate.freshness.is_expired_at(reference_time):
                continue
            expired_candidate = replace(
                candidate,
                status=PaperStatus.EXPIRED,
                decision=PaperDecision.ABSTAIN,
                validity=PaperValidity(
                    status=PaperValidityStatus.INVALID,
                    observed_inputs=candidate.validity.observed_inputs,
                    required_inputs=candidate.validity.required_inputs,
                    missing_inputs=candidate.validity.missing_inputs,
                    invalid_reason="paper_candidate_expired",
                ),
                reason_code=PaperReasonCode.PAPER_EXPIRED,
            )
            self._move_to_historical(key=key, candidate=expired_candidate)
            expired.append(expired_candidate)
        if expired:
            self._refresh_diagnostics(
                lifecycle_state=PaperRuntimeLifecycleState.WARMING,
                ready=not self._diagnostics.degraded_reasons and bool(self._active_rehearsals),
                last_rehearsal_id=str(expired[-1].rehearsal_id),
                last_event_type=None,
                last_failure_reason="paper_candidate_expired",
                readiness_reasons=(
                    ("no_active_paper_rehearsal",) if not self._active_rehearsals else ()
                ),
            )
        return tuple(expired)

    def _build_update_for_context(
        self,
        *,
        key: PaperStateKey,
        context: PaperContext,
        reference_time: datetime,
        reason_code: PaperReasonCode,
    ) -> PaperRuntimeUpdate:
        existing = self._active_rehearsals.get(key)
        freshness = self._build_freshness(context=context, reference_time=reference_time)

        if context.validity.is_warming:
            candidate = PaperRehearsalCandidate.candidate(
                contour_name=self.config.contour_name,
                paper_name=self.config.paper_name,
                symbol=context.symbol,
                exchange=context.exchange,
                timeframe=context.timeframe,
                source=context.source,
                freshness=freshness,
                validity=context.validity,
                decision=PaperDecision.ABSTAIN,
                status=PaperStatus.CANDIDATE,
                originating_workflow_id=context.manager.workflow_id,
                originating_review_id=context.validation.review_id,
                originating_oms_order_id=(
                    context.oms_order.oms_order_id if context.oms_order is not None else None
                ),
                reason_code=reason_code,
            )
            self._active_rehearsals[key] = candidate
            self._rehearsal_key_by_id[candidate.rehearsal_id] = key
            payload = PaperRehearsalPayload.from_candidate(candidate)
            self._refresh_diagnostics(
                lifecycle_state=PaperRuntimeLifecycleState.WARMING,
                ready=False,
                last_rehearsal_id=str(candidate.rehearsal_id),
                last_event_type=PaperEventType.PAPER_CANDIDATE_UPDATED.value,
                last_failure_reason=None,
                readiness_reasons=tuple(context.validity.missing_inputs)
                or ("paper_context_incomplete",),
            )
            return PaperRuntimeUpdate(
                context=context,
                rehearsal_candidate=candidate,
                event_type=PaperEventType.PAPER_CANDIDATE_UPDATED,
                emitted_payload=payload,
            )

        if context.validity.is_valid:
            if self._should_rehearse(context):
                decision = PaperDecision.REHEARSE
                status = PaperStatus.REHEARSED
                event_type = PaperEventType.PAPER_REHEARSAL_REHEARSED
                reason = PaperReasonCode.PAPER_REHEARSED
            else:
                decision = PaperDecision.ABSTAIN
                status = PaperStatus.ABSTAINED
                event_type = PaperEventType.PAPER_REHEARSAL_ABSTAINED
                reason = PaperReasonCode.PAPER_ABSTAINED
            candidate = PaperRehearsalCandidate.candidate(
                contour_name=self.config.contour_name,
                paper_name=self.config.paper_name,
                symbol=context.symbol,
                exchange=context.exchange,
                timeframe=context.timeframe,
                source=context.source,
                freshness=freshness,
                validity=context.validity,
                decision=decision,
                status=status,
                originating_workflow_id=context.manager.workflow_id,
                originating_review_id=context.validation.review_id,
                originating_oms_order_id=(
                    context.oms_order.oms_order_id if context.oms_order is not None else None
                ),
                confidence=self._derive_confidence(context=context),
                rehearsal_score=self._derive_rehearsal_score(context=context),
                reason_code=reason,
            )
            self._active_rehearsals[key] = candidate
            self._rehearsal_key_by_id[candidate.rehearsal_id] = key
            payload = PaperRehearsalPayload.from_candidate(candidate)
            self._refresh_diagnostics(
                lifecycle_state=PaperRuntimeLifecycleState.READY,
                ready=True,
                last_rehearsal_id=str(candidate.rehearsal_id),
                last_event_type=event_type.value,
                last_failure_reason=None,
                readiness_reasons=(),
                degraded_reasons=(),
            )
            return PaperRuntimeUpdate(
                context=context,
                rehearsal_candidate=candidate,
                event_type=event_type,
                emitted_payload=payload,
            )

        if existing is not None:
            invalidated = replace(
                existing,
                status=PaperStatus.INVALIDATED,
                decision=PaperDecision.ABSTAIN,
                validity=context.validity,
                reason_code=PaperReasonCode.PAPER_INVALIDATED,
            )
            self._move_to_historical(key=key, candidate=invalidated)
            payload = PaperRehearsalPayload.from_candidate(invalidated)
            self._refresh_diagnostics(
                lifecycle_state=PaperRuntimeLifecycleState.DEGRADED,
                ready=False,
                last_rehearsal_id=str(invalidated.rehearsal_id),
                last_event_type=PaperEventType.PAPER_REHEARSAL_INVALIDATED.value,
                last_failure_reason=context.validity.invalid_reason,
                degraded_reasons=(context.validity.invalid_reason or "paper_context_invalid",),
                readiness_reasons=("paper_context_invalid",),
            )
            return PaperRuntimeUpdate(
                context=context,
                rehearsal_candidate=invalidated,
                event_type=PaperEventType.PAPER_REHEARSAL_INVALIDATED,
                emitted_payload=payload,
            )

        self._refresh_diagnostics(
            lifecycle_state=PaperRuntimeLifecycleState.DEGRADED,
            ready=False,
            last_failure_reason=context.validity.invalid_reason,
            degraded_reasons=(context.validity.invalid_reason or "paper_context_invalid",),
            readiness_reasons=("paper_context_invalid",),
        )
        return PaperRuntimeUpdate(context=context, rehearsal_candidate=None, event_type=None)

    def _build_validity(
        self,
        *,
        manager: ManagerWorkflowCandidate | None,
        validation: ValidationReviewCandidate | None,
        oms_order: OmsOrderRecord | None,
        reference_time: datetime,
    ) -> tuple[PaperValidity, PaperReasonCode]:
        missing_inputs = tuple(
            name
            for name, value in (
                ("manager", manager),
                ("validation", validation),
            )
            if value is None
        )
        observed_inputs = 3 - len(missing_inputs) - (1 if oms_order is None else 0)
        if missing_inputs:
            return (
                PaperValidity(
                    status=PaperValidityStatus.WARMING,
                    observed_inputs=max(observed_inputs, 0),
                    required_inputs=3,
                    missing_inputs=missing_inputs,
                ),
                PaperReasonCode.CONTEXT_INCOMPLETE,
            )

        assert manager is not None
        assert validation is not None

        invalid_upstreams = (
            manager.validity.status == manager.validity.status.INVALID
            or manager.status.value in {"invalidated", "expired"},
            validation.validity.status == validation.validity.status.INVALID
            or validation.status.value in {"invalidated", "expired"},
            oms_order is not None
            and (
                oms_order.validity.status == oms_order.validity.status.INVALID
                or oms_order.lifecycle_status == OmsLifecycleStatus.EXPIRED
            ),
        )
        if any(invalid_upstreams):
            return (
                PaperValidity(
                    status=PaperValidityStatus.INVALID,
                    observed_inputs=3 if oms_order is not None else 2,
                    required_inputs=3,
                    invalid_reason="upstream_paper_truth_invalidated",
                ),
                PaperReasonCode.PAPER_INVALIDATED,
            )

        checks: tuple[tuple[bool, PaperReasonCode, str], ...] = (
            (
                manager.is_coordinated,
                PaperReasonCode.MANAGER_NOT_COORDINATED,
                "manager_not_coordinated",
            ),
            (
                validation.is_validated,
                PaperReasonCode.VALIDATION_NOT_READY,
                "validation_not_ready",
            ),
        )
        first_nonready = next((item for item in checks if not item[0]), None)
        if first_nonready is not None:
            return (
                PaperValidity(
                    status=PaperValidityStatus.WARMING,
                    observed_inputs=3 if oms_order is not None else 2,
                    required_inputs=3,
                    missing_inputs=(first_nonready[2],),
                ),
                first_nonready[1],
            )

        freshness_values = (
            manager.freshness,
            validation.freshness,
            oms_order.freshness if oms_order is not None else None,
        )
        if any(
            item is not None and item.is_expired_at(reference_time) for item in freshness_values
        ):
            return (
                PaperValidity(
                    status=PaperValidityStatus.INVALID,
                    observed_inputs=3 if oms_order is not None else 2,
                    required_inputs=3,
                    invalid_reason="upstream_paper_truth_expired",
                ),
                PaperReasonCode.PAPER_EXPIRED,
            )

        return (
            PaperValidity(
                status=PaperValidityStatus.VALID,
                observed_inputs=3 if oms_order is not None else 2,
                required_inputs=3,
                missing_inputs=("oms",) if oms_order is None else (),
            ),
            PaperReasonCode.CONTEXT_READY
            if oms_order is not None
            else PaperReasonCode.OMS_STATE_MISSING,
        )

    def _build_freshness(
        self,
        *,
        context: PaperContext,
        reference_time: datetime,
    ) -> PaperFreshness:
        expires_at_candidates = (
            context.manager.freshness.expires_at,
            context.validation.freshness.expires_at,
            context.oms_order.freshness.expires_at if context.oms_order is not None else None,
        )
        non_null = tuple(item for item in expires_at_candidates if item is not None)
        return PaperFreshness(
            generated_at=reference_time,
            expires_at=min(non_null)
            if non_null
            else reference_time + timedelta(seconds=self.config.max_rehearsal_age_seconds),
        )

    def _assemble_paper_context(
        self,
        *,
        symbol: str,
        exchange: str,
        timeframe: MarketDataTimeframe,
        manager: ManagerWorkflowCandidate,
        validation: ValidationReviewCandidate,
        oms_order: OmsOrderRecord | None,
        validity: PaperValidity,
        reference_time: datetime,
    ) -> PaperContext:
        """Собрать typed PaperContext внутри paper layer."""
        return PaperContext(
            paper_name=self.config.paper_name,
            contour_name=self.config.contour_name,
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
            observed_at=reference_time,
            source=PaperSource.RUNTIME_FOUNDATIONS,
            manager=manager,
            validation=validation,
            oms_order=oms_order,
            validity=validity,
            metadata={},
        )

    @staticmethod
    def _derive_confidence(context: PaperContext) -> Decimal | None:
        values = tuple(
            value
            for value in (
                context.manager.confidence,
                context.validation.confidence,
            )
            if value is not None
        )
        if not values:
            return None
        return (sum(values, Decimal("0")) / Decimal(len(values))).quantize(Decimal("0.0001"))

    @staticmethod
    def _derive_rehearsal_score(context: PaperContext) -> Decimal | None:
        values = tuple(
            value
            for value in (
                context.manager.priority_score,
                context.validation.review_score,
            )
            if value is not None
        )
        if context.oms_order is not None and context.oms_order.is_active:
            values = (*values, Decimal("1.0000"))
        if not values:
            return None
        return max(values)

    @staticmethod
    def _resolve_state_key(
        *,
        manager: ManagerWorkflowCandidate | None,
        validation: ValidationReviewCandidate | None,
        oms_order: OmsOrderRecord | None,
    ) -> PaperStateKey | None:
        for value in (validation, manager):
            if value is not None:
                return (value.symbol, value.exchange, value.timeframe)
        if oms_order is not None:
            return (oms_order.symbol, oms_order.exchange, oms_order.timeframe)
        return None

    @staticmethod
    def _should_rehearse(context: PaperContext) -> bool:
        if context.oms_order is None:
            return True
        return context.oms_order.lifecycle_status in {
            OmsLifecycleStatus.REGISTERED,
            OmsLifecycleStatus.SUBMITTED,
            OmsLifecycleStatus.ACCEPTED,
            OmsLifecycleStatus.PARTIALLY_FILLED,
            OmsLifecycleStatus.FILLED,
        }

    def _move_to_historical(
        self,
        *,
        key: PaperStateKey,
        candidate: PaperRehearsalCandidate,
    ) -> None:
        self._historical_rehearsals[key] = candidate
        self._rehearsal_key_by_id[candidate.rehearsal_id] = key
        self._active_rehearsals.pop(key, None)

    def _ensure_started(self) -> None:
        if not self._started:
            raise RuntimeError("Paper runtime должен быть явно запущен перед ingest")

    def _refresh_diagnostics(
        self,
        *,
        lifecycle_state: PaperRuntimeLifecycleState | None = None,
        ready: bool | None = None,
        last_rehearsal_id: str | None = None,
        last_event_type: str | None = None,
        last_failure_reason: str | None = None,
        readiness_reasons: tuple[str, ...] | None = None,
        degraded_reasons: tuple[str, ...] | None = None,
    ) -> None:
        if lifecycle_state is not None:
            self._diagnostics.lifecycle_state = lifecycle_state
        self._diagnostics.started = self._started
        if ready is not None:
            self._diagnostics.ready = ready
        self._diagnostics.tracked_contexts = len(self._contexts)
        self._diagnostics.tracked_active_rehearsals = len(self._active_rehearsals)
        self._diagnostics.tracked_historical_rehearsals = len(self._historical_rehearsals)
        if last_rehearsal_id is not None:
            self._diagnostics.last_rehearsal_id = last_rehearsal_id
        if last_event_type is not None:
            self._diagnostics.last_event_type = last_event_type
        self._diagnostics.last_failure_reason = last_failure_reason
        if readiness_reasons is not None:
            self._diagnostics.readiness_reasons = list(readiness_reasons)
        if degraded_reasons is not None:
            self._diagnostics.degraded_reasons = list(degraded_reasons)
        self._push_diagnostics()

    def _push_diagnostics(self) -> None:
        if self._diagnostics_sink is not None:
            self._diagnostics_sink(self._diagnostics.to_dict())


def create_paper_runtime(
    config: PaperRuntimeConfig | None = None,
    *,
    diagnostics_sink: Callable[[dict[str, object]], None] | None = None,
) -> PaperRuntime:
    """Явный factory runtime entrypoint paper layer."""
    return PaperRuntime(config, diagnostics_sink=diagnostics_sink)


__all__ = [
    "PaperRuntime",
    "PaperRuntimeConfig",
    "PaperRuntimeDiagnostics",
    "PaperRuntimeLifecycleState",
    "PaperRuntimeUpdate",
    "PaperStateKey",
    "create_paper_runtime",
]

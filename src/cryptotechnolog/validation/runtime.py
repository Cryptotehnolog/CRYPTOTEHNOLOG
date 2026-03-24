"""
Узкий explicit runtime foundation для Phase 18 Validation Foundation.

Этот runtime:
- стартует и останавливается явно;
- не делает hidden bootstrap;
- собирает typed validation context из existing runtime truths;
- поддерживает один минимальный deterministic validation contour;
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

from .events import ValidationEventType, ValidationReviewPayload
from .models import (
    ValidationContext,
    ValidationDecision,
    ValidationFreshness,
    ValidationReasonCode,
    ValidationReviewCandidate,
    ValidationSource,
    ValidationStatus,
    ValidationValidity,
    ValidationValidityStatus,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from uuid import UUID

    from cryptotechnolog.manager import ManagerWorkflowCandidate
    from cryptotechnolog.oms import OmsOrderRecord
    from cryptotechnolog.portfolio_governor import PortfolioGovernorCandidate
    from cryptotechnolog.protection import ProtectionSupervisorCandidate


type ValidationStateKey = tuple[str, str, MarketDataTimeframe]


class ValidationRuntimeLifecycleState(StrEnum):
    """Lifecycle-состояние validation runtime."""

    NOT_STARTED = "not_started"
    WARMING = "warming"
    READY = "ready"
    DEGRADED = "degraded"
    STOPPED = "stopped"


@dataclass(slots=True, frozen=True)
class ValidationRuntimeConfig:
    """Typed runtime-конфигурация validation foundation."""

    contour_name: str = "phase18_validation_contour"
    validation_name: str = "phase18_validation"
    max_review_age_seconds: int = 3600

    def __post_init__(self) -> None:
        if self.max_review_age_seconds <= 0:
            raise ValueError("max_review_age_seconds должен быть положительным")


@dataclass(slots=True)
class ValidationRuntimeDiagnostics:
    """Operator-visible diagnostics contract validation runtime."""

    started: bool = False
    ready: bool = False
    lifecycle_state: ValidationRuntimeLifecycleState = ValidationRuntimeLifecycleState.NOT_STARTED
    tracked_contexts: int = 0
    tracked_active_reviews: int = 0
    tracked_historical_reviews: int = 0
    last_review_id: str | None = None
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
class ValidationRuntimeUpdate:
    """Typed update contract validation runtime foundation."""

    context: ValidationContext | None
    review_candidate: ValidationReviewCandidate | None
    event_type: ValidationEventType | None
    emitted_payload: ValidationReviewPayload | None = None


class ValidationRuntime:
    """Explicit runtime foundation для validation layer Phase 18."""

    _TERMINAL_STATUSES: ClassVar[set[ValidationStatus]] = {
        ValidationStatus.INVALIDATED,
        ValidationStatus.EXPIRED,
    }

    def __init__(
        self,
        config: ValidationRuntimeConfig | None = None,
        *,
        diagnostics_sink: Callable[[dict[str, object]], None] | None = None,
    ) -> None:
        self.config = config or ValidationRuntimeConfig()
        self._diagnostics_sink = diagnostics_sink
        self._diagnostics = ValidationRuntimeDiagnostics()
        self._started = False
        self._contexts: dict[ValidationStateKey, ValidationContext] = {}
        self._active_reviews: dict[ValidationStateKey, ValidationReviewCandidate] = {}
        self._historical_reviews: dict[ValidationStateKey, ValidationReviewCandidate] = {}
        self._review_key_by_id: dict[UUID, ValidationStateKey] = {}
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
            lifecycle_state=ValidationRuntimeLifecycleState.WARMING,
            ready=False,
            last_failure_reason=None,
            readiness_reasons=("no_validation_review_processed",),
            degraded_reasons=(),
        )

    async def stop(self) -> None:
        """Остановить runtime и очистить operator-visible state."""
        if not self._started:
            return
        self._started = False
        self._contexts = {}
        self._active_reviews = {}
        self._historical_reviews = {}
        self._review_key_by_id = {}
        self._diagnostics.last_review_id = None
        self._diagnostics.last_event_type = None
        self._refresh_diagnostics(
            lifecycle_state=ValidationRuntimeLifecycleState.STOPPED,
            ready=False,
            last_review_id=None,
            last_event_type=None,
            last_failure_reason=None,
            readiness_reasons=("runtime_stopped",),
            degraded_reasons=(),
        )

    def get_context(self, key: ValidationStateKey) -> ValidationContext | None:
        """Вернуть последний validation context по state key."""
        return self._contexts.get(key)

    def get_candidate(
        self,
        *,
        exchange: str,
        symbol: str,
        timeframe: MarketDataTimeframe,
    ) -> ValidationReviewCandidate | None:
        """Вернуть active review candidate по координатам."""
        return self._active_reviews.get((symbol, exchange, timeframe))

    def get_review_candidate(self, key: ValidationStateKey) -> ValidationReviewCandidate | None:
        """Вернуть текущий active review candidate по state key."""
        return self._active_reviews.get(key)

    def get_historical_candidate(
        self,
        key: ValidationStateKey,
    ) -> ValidationReviewCandidate | None:
        """Вернуть terminal review candidate по state key."""
        return self._historical_reviews.get(key)

    def list_active_candidates(self) -> tuple[ValidationReviewCandidate, ...]:
        """Вернуть все active validation review candidates."""
        return tuple(self._active_reviews.values())

    def list_historical_candidates(self) -> tuple[ValidationReviewCandidate, ...]:
        """Вернуть все terminal validation review candidates."""
        return tuple(self._historical_reviews.values())

    def get_runtime_diagnostics(self) -> dict[str, object]:
        """Вернуть текущую operator-visible diagnostics truth."""
        return self._diagnostics.to_dict()

    def mark_degraded(self, reason: str) -> None:
        """Явно пометить runtime как degraded без смешения с bootstrap truth."""
        reasons = tuple(dict.fromkeys((*self._diagnostics.degraded_reasons, reason)))
        self._refresh_diagnostics(
            lifecycle_state=ValidationRuntimeLifecycleState.DEGRADED,
            ready=False,
            last_failure_reason=reason,
            degraded_reasons=reasons,
        )

    def ingest_truths(
        self,
        *,
        manager: ManagerWorkflowCandidate | None,
        governor: PortfolioGovernorCandidate | None,
        protection: ProtectionSupervisorCandidate | None,
        oms_order: OmsOrderRecord | None,
        reference_time: datetime,
    ) -> ValidationRuntimeUpdate:
        """Собрать validation context и обновить review candidate из existing truths."""
        self._ensure_started()
        key = self._resolve_state_key(
            manager=manager,
            governor=governor,
            protection=protection,
            oms_order=oms_order,
        )
        if key is None:
            self.mark_degraded("validation_truths_missing_coordinates")
            return ValidationRuntimeUpdate(context=None, review_candidate=None, event_type=None)

        validity, reason_code = self._build_validity(
            manager=manager,
            governor=governor,
            protection=protection,
            oms_order=oms_order,
            reference_time=reference_time,
        )

        if any(value is None for value in (manager, governor, protection)):
            self._refresh_diagnostics(
                lifecycle_state=ValidationRuntimeLifecycleState.WARMING,
                ready=False,
                readiness_reasons=tuple(validity.missing_inputs)
                or ("validation_context_incomplete",),
                last_failure_reason=None,
            )
            return ValidationRuntimeUpdate(context=None, review_candidate=None, event_type=None)

        assert manager is not None
        assert governor is not None
        assert protection is not None

        context = self._assemble_validation_context(
            symbol=key[0],
            exchange=key[1],
            timeframe=key[2],
            manager=manager,
            governor=governor,
            protection=protection,
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

    def expire_candidates(
        self, *, reference_time: datetime
    ) -> tuple[ValidationReviewCandidate, ...]:
        """Перевести устаревшие active review candidates в EXPIRED."""
        expired: list[ValidationReviewCandidate] = []
        for key, candidate in tuple(self._active_reviews.items()):
            if not candidate.freshness.is_expired_at(reference_time):
                continue
            expired_candidate = replace(
                candidate,
                status=ValidationStatus.EXPIRED,
                decision=ValidationDecision.ABSTAIN,
                validity=ValidationValidity(
                    status=ValidationValidityStatus.INVALID,
                    observed_inputs=candidate.validity.observed_inputs,
                    required_inputs=candidate.validity.required_inputs,
                    missing_inputs=candidate.validity.missing_inputs,
                    invalid_reason="validation_candidate_expired",
                ),
                reason_code=ValidationReasonCode.VALIDATION_EXPIRED,
            )
            self._move_to_historical(key=key, candidate=expired_candidate)
            expired.append(expired_candidate)
        if expired:
            self._refresh_diagnostics(
                lifecycle_state=ValidationRuntimeLifecycleState.WARMING,
                ready=not self._diagnostics.degraded_reasons and bool(self._active_reviews),
                last_review_id=str(expired[-1].review_id),
                last_event_type=None,
                last_failure_reason="validation_candidate_expired",
                readiness_reasons=(
                    ("no_active_validation_review",) if not self._active_reviews else ()
                ),
            )
        return tuple(expired)

    def _build_update_for_context(
        self,
        *,
        key: ValidationStateKey,
        context: ValidationContext,
        reference_time: datetime,
        reason_code: ValidationReasonCode,
    ) -> ValidationRuntimeUpdate:
        existing = self._active_reviews.get(key)
        freshness = self._build_freshness(context=context, reference_time=reference_time)

        if context.validity.is_warming:
            candidate = ValidationReviewCandidate.candidate(
                contour_name=self.config.contour_name,
                validation_name=self.config.validation_name,
                symbol=context.symbol,
                exchange=context.exchange,
                timeframe=context.timeframe,
                source=context.source,
                freshness=freshness,
                validity=context.validity,
                decision=ValidationDecision.ABSTAIN,
                status=ValidationStatus.CANDIDATE,
                originating_workflow_id=context.manager.workflow_id,
                originating_governor_id=context.governor.governor_id,
                originating_protection_id=context.protection.protection_id,
                originating_oms_order_id=(
                    context.oms_order.oms_order_id if context.oms_order is not None else None
                ),
                reason_code=reason_code,
            )
            self._active_reviews[key] = candidate
            self._review_key_by_id[candidate.review_id] = key
            payload = ValidationReviewPayload.from_candidate(candidate)
            self._refresh_diagnostics(
                lifecycle_state=ValidationRuntimeLifecycleState.WARMING,
                ready=False,
                last_review_id=str(candidate.review_id),
                last_event_type=ValidationEventType.VALIDATION_CANDIDATE_UPDATED.value,
                last_failure_reason=None,
                readiness_reasons=tuple(context.validity.missing_inputs)
                or ("validation_context_incomplete",),
            )
            return ValidationRuntimeUpdate(
                context=context,
                review_candidate=candidate,
                event_type=ValidationEventType.VALIDATION_CANDIDATE_UPDATED,
                emitted_payload=payload,
            )

        if context.validity.is_valid:
            if self._should_validate(context):
                decision = ValidationDecision.VALIDATE
                status = ValidationStatus.VALIDATED
                event_type = ValidationEventType.VALIDATION_WORKFLOW_VALIDATED
                reason = ValidationReasonCode.VALIDATION_CONFIRMED
            else:
                decision = ValidationDecision.ABSTAIN
                status = ValidationStatus.ABSTAINED
                event_type = ValidationEventType.VALIDATION_WORKFLOW_ABSTAINED
                reason = ValidationReasonCode.VALIDATION_ABSTAINED
            candidate = ValidationReviewCandidate.candidate(
                contour_name=self.config.contour_name,
                validation_name=self.config.validation_name,
                symbol=context.symbol,
                exchange=context.exchange,
                timeframe=context.timeframe,
                source=context.source,
                freshness=freshness,
                validity=context.validity,
                decision=decision,
                status=status,
                originating_workflow_id=context.manager.workflow_id,
                originating_governor_id=context.governor.governor_id,
                originating_protection_id=context.protection.protection_id,
                originating_oms_order_id=(
                    context.oms_order.oms_order_id if context.oms_order is not None else None
                ),
                confidence=self._derive_confidence(context=context),
                review_score=self._derive_review_score(context=context),
                reason_code=reason,
            )
            self._active_reviews[key] = candidate
            self._review_key_by_id[candidate.review_id] = key
            payload = ValidationReviewPayload.from_candidate(candidate)
            self._refresh_diagnostics(
                lifecycle_state=ValidationRuntimeLifecycleState.READY,
                ready=True,
                last_review_id=str(candidate.review_id),
                last_event_type=event_type.value,
                last_failure_reason=None,
                readiness_reasons=(),
                degraded_reasons=(),
            )
            return ValidationRuntimeUpdate(
                context=context,
                review_candidate=candidate,
                event_type=event_type,
                emitted_payload=payload,
            )

        if existing is not None:
            invalidated = replace(
                existing,
                status=ValidationStatus.INVALIDATED,
                decision=ValidationDecision.ABSTAIN,
                validity=context.validity,
                reason_code=ValidationReasonCode.VALIDATION_INVALIDATED,
            )
            self._move_to_historical(key=key, candidate=invalidated)
            payload = ValidationReviewPayload.from_candidate(invalidated)
            self._refresh_diagnostics(
                lifecycle_state=ValidationRuntimeLifecycleState.DEGRADED,
                ready=False,
                last_review_id=str(invalidated.review_id),
                last_event_type=ValidationEventType.VALIDATION_WORKFLOW_INVALIDATED.value,
                last_failure_reason=context.validity.invalid_reason,
                degraded_reasons=(context.validity.invalid_reason or "validation_context_invalid",),
                readiness_reasons=("validation_context_invalid",),
            )
            return ValidationRuntimeUpdate(
                context=context,
                review_candidate=invalidated,
                event_type=ValidationEventType.VALIDATION_WORKFLOW_INVALIDATED,
                emitted_payload=payload,
            )

        self._refresh_diagnostics(
            lifecycle_state=ValidationRuntimeLifecycleState.DEGRADED,
            ready=False,
            last_failure_reason=context.validity.invalid_reason,
            degraded_reasons=(context.validity.invalid_reason or "validation_context_invalid",),
            readiness_reasons=("validation_context_invalid",),
        )
        return ValidationRuntimeUpdate(context=context, review_candidate=None, event_type=None)

    def _build_validity(
        self,
        *,
        manager: ManagerWorkflowCandidate | None,
        governor: PortfolioGovernorCandidate | None,
        protection: ProtectionSupervisorCandidate | None,
        oms_order: OmsOrderRecord | None,
        reference_time: datetime,
    ) -> tuple[ValidationValidity, ValidationReasonCode]:
        missing_inputs = tuple(
            name
            for name, value in (
                ("manager", manager),
                ("governor", governor),
                ("protection", protection),
            )
            if value is None
        )
        observed_inputs = 4 - len(missing_inputs) - (1 if oms_order is None else 0)
        if missing_inputs:
            return (
                ValidationValidity(
                    status=ValidationValidityStatus.WARMING,
                    observed_inputs=max(observed_inputs, 0),
                    required_inputs=4,
                    missing_inputs=missing_inputs,
                ),
                ValidationReasonCode.CONTEXT_INCOMPLETE,
            )

        assert manager is not None
        assert governor is not None
        assert protection is not None

        invalid_upstreams = (
            manager.validity.status == manager.validity.status.INVALID
            or manager.status.value in {"invalidated", "expired"},
            governor.validity.status == governor.validity.status.INVALID
            or governor.status.value in {"invalidated", "expired"},
            protection.validity.status == protection.validity.status.INVALID
            or protection.status.value in {"invalidated", "expired"},
            oms_order is not None
            and (
                oms_order.validity.status == oms_order.validity.status.INVALID
                or oms_order.lifecycle_status == OmsLifecycleStatus.EXPIRED
            ),
        )
        if any(invalid_upstreams):
            return (
                ValidationValidity(
                    status=ValidationValidityStatus.INVALID,
                    observed_inputs=4 if oms_order is not None else 3,
                    required_inputs=4,
                    invalid_reason="upstream_validation_truth_invalidated",
                ),
                ValidationReasonCode.VALIDATION_INVALIDATED,
            )

        checks: tuple[tuple[bool, ValidationReasonCode, str], ...] = (
            (
                manager.is_coordinated,
                ValidationReasonCode.MANAGER_NOT_COORDINATED,
                "manager_not_coordinated",
            ),
            (
                governor.is_approved,
                ValidationReasonCode.GOVERNOR_NOT_APPROVED,
                "governor_not_approved",
            ),
            (
                protection.is_protected,
                ValidationReasonCode.PROTECTION_NOT_PROTECTED,
                "protection_not_protected",
            ),
        )
        first_nonready = next((item for item in checks if not item[0]), None)
        if first_nonready is not None:
            return (
                ValidationValidity(
                    status=ValidationValidityStatus.WARMING,
                    observed_inputs=4 if oms_order is not None else 3,
                    required_inputs=4,
                    missing_inputs=(first_nonready[2],),
                ),
                first_nonready[1],
            )

        freshness_values = (
            manager.freshness,
            governor.freshness,
            protection.freshness,
            oms_order.freshness if oms_order is not None else None,
        )
        if any(
            item is not None and item.is_expired_at(reference_time) for item in freshness_values
        ):
            return (
                ValidationValidity(
                    status=ValidationValidityStatus.INVALID,
                    observed_inputs=4 if oms_order is not None else 3,
                    required_inputs=4,
                    invalid_reason="upstream_validation_truth_expired",
                ),
                ValidationReasonCode.VALIDATION_EXPIRED,
            )

        return (
            ValidationValidity(
                status=ValidationValidityStatus.VALID,
                observed_inputs=4 if oms_order is not None else 3,
                required_inputs=4,
                missing_inputs=("oms",) if oms_order is None else (),
            ),
            ValidationReasonCode.CONTEXT_READY
            if oms_order is not None
            else ValidationReasonCode.OMS_STATE_MISSING,
        )

    def _build_freshness(
        self,
        *,
        context: ValidationContext,
        reference_time: datetime,
    ) -> ValidationFreshness:
        expires_at_candidates = (
            context.manager.freshness.expires_at,
            context.governor.freshness.expires_at,
            context.protection.freshness.expires_at,
            context.oms_order.freshness.expires_at if context.oms_order is not None else None,
        )
        non_null = tuple(item for item in expires_at_candidates if item is not None)
        return ValidationFreshness(
            generated_at=reference_time,
            expires_at=min(non_null)
            if non_null
            else reference_time + timedelta(seconds=self.config.max_review_age_seconds),
        )

    def _assemble_validation_context(
        self,
        *,
        symbol: str,
        exchange: str,
        timeframe: MarketDataTimeframe,
        manager: ManagerWorkflowCandidate,
        governor: PortfolioGovernorCandidate,
        protection: ProtectionSupervisorCandidate,
        oms_order: OmsOrderRecord | None,
        validity: ValidationValidity,
        reference_time: datetime,
    ) -> ValidationContext:
        """Собрать typed ValidationContext внутри validation layer."""
        return ValidationContext(
            validation_name=self.config.validation_name,
            contour_name=self.config.contour_name,
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
            observed_at=reference_time,
            source=ValidationSource.RUNTIME_FOUNDATIONS,
            manager=manager,
            governor=governor,
            protection=protection,
            oms_order=oms_order,
            validity=validity,
            metadata={},
        )

    @staticmethod
    def _derive_confidence(context: ValidationContext) -> Decimal | None:
        values = tuple(
            value
            for value in (
                context.manager.confidence,
                context.governor.confidence,
                context.protection.confidence,
            )
            if value is not None
        )
        if not values:
            return None
        return (sum(values, Decimal("0")) / Decimal(len(values))).quantize(Decimal("0.0001"))

    @staticmethod
    def _derive_review_score(context: ValidationContext) -> Decimal | None:
        values = tuple(
            value
            for value in (
                context.manager.priority_score,
                context.governor.priority_score,
                context.protection.priority_score,
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
        governor: PortfolioGovernorCandidate | None,
        protection: ProtectionSupervisorCandidate | None,
        oms_order: OmsOrderRecord | None,
    ) -> ValidationStateKey | None:
        for value in (protection, governor, manager):
            if value is not None:
                return (value.symbol, value.exchange, value.timeframe)
        if oms_order is not None:
            return (
                oms_order.symbol,
                oms_order.exchange,
                oms_order.timeframe,
            )
        return None

    @staticmethod
    def _should_validate(context: ValidationContext) -> bool:
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
        key: ValidationStateKey,
        candidate: ValidationReviewCandidate,
    ) -> None:
        self._historical_reviews[key] = candidate
        self._review_key_by_id[candidate.review_id] = key
        self._active_reviews.pop(key, None)

    def _ensure_started(self) -> None:
        if not self._started:
            raise RuntimeError("Validation runtime должен быть явно запущен перед ingest")

    def _refresh_diagnostics(
        self,
        *,
        lifecycle_state: ValidationRuntimeLifecycleState | None = None,
        ready: bool | None = None,
        last_review_id: str | None = None,
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
        self._diagnostics.tracked_active_reviews = len(self._active_reviews)
        self._diagnostics.tracked_historical_reviews = len(self._historical_reviews)
        if last_review_id is not None:
            self._diagnostics.last_review_id = last_review_id
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


def create_validation_runtime(
    config: ValidationRuntimeConfig | None = None,
    *,
    diagnostics_sink: Callable[[dict[str, object]], None] | None = None,
) -> ValidationRuntime:
    """Явный factory runtime entrypoint validation layer."""
    return ValidationRuntime(config, diagnostics_sink=diagnostics_sink)


__all__ = [
    "ValidationRuntime",
    "ValidationRuntimeConfig",
    "ValidationRuntimeDiagnostics",
    "ValidationRuntimeLifecycleState",
    "ValidationRuntimeUpdate",
    "ValidationStateKey",
    "create_validation_runtime",
]

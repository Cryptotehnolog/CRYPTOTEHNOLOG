"""
Узкий explicit runtime foundation для Phase 17 Strategy Manager / Workflow Foundation.

Этот runtime:
- стартует и останавливается явно;
- не делает hidden bootstrap;
- собирает typed manager context из existing workflow truths;
- поддерживает один минимальный deterministic coordination contour;
- хранит query/state-first truth и operator-visible diagnostics.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, ClassVar

from cryptotechnolog.market_data import MarketDataTimeframe
from cryptotechnolog.protection import ProtectionStatus

from .events import ManagerEventType, ManagerWorkflowPayload
from .models import (
    ManagerContext,
    ManagerDecision,
    ManagerFreshness,
    ManagerReasonCode,
    ManagerSource,
    ManagerStatus,
    ManagerValidity,
    ManagerValidityStatus,
    ManagerWorkflowCandidate,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from uuid import UUID

    from cryptotechnolog.opportunity import OpportunitySelectionCandidate
    from cryptotechnolog.orchestration import OrchestrationDecisionCandidate
    from cryptotechnolog.portfolio_governor import PortfolioGovernorCandidate
    from cryptotechnolog.position_expansion import PositionExpansionCandidate
    from cryptotechnolog.protection import ProtectionSupervisorCandidate


type ManagerStateKey = tuple[str, str, MarketDataTimeframe]


class ManagerRuntimeLifecycleState(StrEnum):
    """Lifecycle-состояние manager runtime."""

    NOT_STARTED = "not_started"
    WARMING = "warming"
    READY = "ready"
    DEGRADED = "degraded"
    STOPPED = "stopped"


@dataclass(slots=True, frozen=True)
class ManagerRuntimeConfig:
    """Typed runtime-конфигурация manager foundation."""

    contour_name: str = "phase17_manager_contour"
    manager_name: str = "phase17_manager"
    max_workflow_age_seconds: int = 3600

    def __post_init__(self) -> None:
        if self.max_workflow_age_seconds <= 0:
            raise ValueError("max_workflow_age_seconds должен быть положительным")


@dataclass(slots=True)
class ManagerRuntimeDiagnostics:
    """Operator-visible diagnostics contract manager runtime."""

    started: bool = False
    ready: bool = False
    lifecycle_state: ManagerRuntimeLifecycleState = ManagerRuntimeLifecycleState.NOT_STARTED
    tracked_contexts: int = 0
    tracked_active_workflows: int = 0
    tracked_historical_workflows: int = 0
    last_workflow_id: str | None = None
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
class ManagerRuntimeUpdate:
    """Typed update contract manager runtime foundation."""

    context: ManagerContext | None
    workflow_candidate: ManagerWorkflowCandidate | None
    event_type: ManagerEventType | None
    emitted_payload: ManagerWorkflowPayload | None = None


class ManagerRuntime:
    """Explicit runtime foundation для manager layer Phase 17."""

    _TERMINAL_STATUSES: ClassVar[set[ManagerStatus]] = {
        ManagerStatus.INVALIDATED,
        ManagerStatus.EXPIRED,
    }

    def __init__(
        self,
        config: ManagerRuntimeConfig | None = None,
        *,
        diagnostics_sink: Callable[[dict[str, object]], None] | None = None,
    ) -> None:
        self.config = config or ManagerRuntimeConfig()
        self._diagnostics_sink = diagnostics_sink
        self._diagnostics = ManagerRuntimeDiagnostics()
        self._started = False
        self._contexts: dict[ManagerStateKey, ManagerContext] = {}
        self._active_workflows: dict[ManagerStateKey, ManagerWorkflowCandidate] = {}
        self._historical_workflows: dict[ManagerStateKey, ManagerWorkflowCandidate] = {}
        self._workflow_key_by_id: dict[UUID, ManagerStateKey] = {}
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
            lifecycle_state=ManagerRuntimeLifecycleState.WARMING,
            ready=False,
            last_failure_reason=None,
            readiness_reasons=("no_manager_workflow_processed",),
            degraded_reasons=(),
        )

    async def stop(self) -> None:
        """Остановить runtime и очистить operator-visible state."""
        if not self._started:
            return
        self._started = False
        self._contexts = {}
        self._active_workflows = {}
        self._historical_workflows = {}
        self._workflow_key_by_id = {}
        self._diagnostics.last_workflow_id = None
        self._diagnostics.last_event_type = None
        self._refresh_diagnostics(
            lifecycle_state=ManagerRuntimeLifecycleState.STOPPED,
            ready=False,
            last_workflow_id=None,
            last_event_type=None,
            last_failure_reason=None,
            readiness_reasons=("runtime_stopped",),
            degraded_reasons=(),
        )

    def get_context(self, key: ManagerStateKey) -> ManagerContext | None:
        """Вернуть последний manager context по state key."""
        return self._contexts.get(key)

    def get_candidate(
        self,
        *,
        exchange: str,
        symbol: str,
        timeframe: MarketDataTimeframe,
    ) -> ManagerWorkflowCandidate | None:
        """Вернуть active workflow candidate по координатам."""
        return self._active_workflows.get((symbol, exchange, timeframe))

    def get_workflow_candidate(self, key: ManagerStateKey) -> ManagerWorkflowCandidate | None:
        """Вернуть текущий active workflow candidate по state key."""
        return self._active_workflows.get(key)

    def get_historical_candidate(self, key: ManagerStateKey) -> ManagerWorkflowCandidate | None:
        """Вернуть terminal workflow candidate по state key."""
        return self._historical_workflows.get(key)

    def list_active_candidates(self) -> tuple[ManagerWorkflowCandidate, ...]:
        """Вернуть все active manager workflow candidates."""
        return tuple(self._active_workflows.values())

    def list_historical_candidates(self) -> tuple[ManagerWorkflowCandidate, ...]:
        """Вернуть все terminal manager workflow candidates."""
        return tuple(self._historical_workflows.values())

    def get_runtime_diagnostics(self) -> dict[str, object]:
        """Вернуть текущую operator-visible diagnostics truth."""
        return self._diagnostics.to_dict()

    def mark_degraded(self, reason: str) -> None:
        """Явно пометить runtime как degraded без смешения с bootstrap truth."""
        reasons = tuple(dict.fromkeys((*self._diagnostics.degraded_reasons, reason)))
        self._refresh_diagnostics(
            lifecycle_state=ManagerRuntimeLifecycleState.DEGRADED,
            ready=False,
            last_failure_reason=reason,
            degraded_reasons=reasons,
        )

    def ingest_truths(
        self,
        *,
        opportunity: OpportunitySelectionCandidate | None,
        orchestration: OrchestrationDecisionCandidate | None,
        expansion: PositionExpansionCandidate | None,
        governor: PortfolioGovernorCandidate | None,
        protection: ProtectionSupervisorCandidate | None,
        reference_time: datetime,
    ) -> ManagerRuntimeUpdate:
        """Собрать manager context и обновить workflow candidate из existing typed truths."""
        self._ensure_started()
        key = self._resolve_state_key(
            opportunity=opportunity,
            orchestration=orchestration,
            expansion=expansion,
            governor=governor,
            protection=protection,
        )
        if key is None:
            self.mark_degraded("manager_truths_missing_coordinates")
            return ManagerRuntimeUpdate(context=None, workflow_candidate=None, event_type=None)

        validity, reason_code = self._build_validity(
            opportunity=opportunity,
            orchestration=orchestration,
            expansion=expansion,
            governor=governor,
            protection=protection,
            reference_time=reference_time,
        )

        if any(
            value is None for value in (opportunity, orchestration, expansion, governor, protection)
        ):
            self._refresh_diagnostics(
                lifecycle_state=ManagerRuntimeLifecycleState.WARMING,
                ready=False,
                readiness_reasons=tuple(validity.missing_inputs) or ("manager_context_incomplete",),
                last_failure_reason=None,
            )
            return ManagerRuntimeUpdate(context=None, workflow_candidate=None, event_type=None)

        assert opportunity is not None
        assert orchestration is not None
        assert expansion is not None
        assert governor is not None
        assert protection is not None

        context = self._assemble_manager_context(
            symbol=key[0],
            exchange=key[1],
            timeframe=key[2],
            opportunity=opportunity,
            orchestration=orchestration,
            expansion=expansion,
            governor=governor,
            protection=protection,
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
    ) -> tuple[ManagerWorkflowCandidate, ...]:
        """Перевести устаревшие active workflow candidates в EXPIRED."""
        expired: list[ManagerWorkflowCandidate] = []
        for key, candidate in tuple(self._active_workflows.items()):
            if not candidate.freshness.is_expired_at(reference_time):
                continue
            expired_candidate = replace(
                candidate,
                status=ManagerStatus.EXPIRED,
                decision=ManagerDecision.ABSTAIN,
                validity=ManagerValidity(
                    status=ManagerValidityStatus.INVALID,
                    observed_inputs=candidate.validity.observed_inputs,
                    required_inputs=candidate.validity.required_inputs,
                    missing_inputs=candidate.validity.missing_inputs,
                    invalid_reason="manager_candidate_expired",
                ),
                reason_code=ManagerReasonCode.MANAGER_EXPIRED,
            )
            self._move_to_historical(key=key, candidate=expired_candidate)
            expired.append(expired_candidate)
        if expired:
            self._refresh_diagnostics(
                lifecycle_state=ManagerRuntimeLifecycleState.WARMING,
                ready=not self._diagnostics.degraded_reasons and bool(self._active_workflows),
                last_workflow_id=str(expired[-1].workflow_id),
                last_event_type=None,
                last_failure_reason="manager_candidate_expired",
                readiness_reasons=(
                    ("no_active_manager_workflow",) if not self._active_workflows else ()
                ),
            )
        return tuple(expired)

    def _build_update_for_context(
        self,
        *,
        key: ManagerStateKey,
        context: ManagerContext,
        reference_time: datetime,
        reason_code: ManagerReasonCode,
    ) -> ManagerRuntimeUpdate:
        existing = self._active_workflows.get(key)
        freshness = self._build_freshness(context=context, reference_time=reference_time)

        if context.validity.is_warming:
            candidate = ManagerWorkflowCandidate.candidate(
                contour_name=self.config.contour_name,
                manager_name=self.config.manager_name,
                symbol=context.symbol,
                exchange=context.exchange,
                timeframe=context.timeframe,
                source=context.source,
                freshness=freshness,
                validity=context.validity,
                decision=ManagerDecision.ABSTAIN,
                status=ManagerStatus.CANDIDATE,
                originating_selection_id=context.opportunity.selection_id,
                originating_decision_id=context.orchestration.decision_id,
                originating_expansion_id=context.expansion.expansion_id,
                originating_governor_id=context.governor.governor_id,
                originating_protection_id=context.protection.protection_id,
                reason_code=reason_code,
            )
            self._active_workflows[key] = candidate
            self._workflow_key_by_id[candidate.workflow_id] = key
            payload = ManagerWorkflowPayload.from_candidate(candidate)
            self._refresh_diagnostics(
                lifecycle_state=ManagerRuntimeLifecycleState.WARMING,
                ready=False,
                last_workflow_id=str(candidate.workflow_id),
                last_event_type=ManagerEventType.MANAGER_CANDIDATE_UPDATED.value,
                last_failure_reason=None,
                readiness_reasons=tuple(context.validity.missing_inputs)
                or ("manager_context_incomplete",),
            )
            return ManagerRuntimeUpdate(
                context=context,
                workflow_candidate=candidate,
                event_type=ManagerEventType.MANAGER_CANDIDATE_UPDATED,
                emitted_payload=payload,
            )

        if context.validity.is_valid:
            if context.protection.status == ProtectionStatus.PROTECTED:
                decision = ManagerDecision.COORDINATE
                status = ManagerStatus.COORDINATED
                event_type = ManagerEventType.MANAGER_WORKFLOW_COORDINATED
                reason = ManagerReasonCode.MANAGER_COORDINATED
            else:
                decision = ManagerDecision.ABSTAIN
                status = ManagerStatus.ABSTAINED
                event_type = ManagerEventType.MANAGER_WORKFLOW_ABSTAINED
                reason = ManagerReasonCode.MANAGER_ABSTAINED
            candidate = ManagerWorkflowCandidate.candidate(
                contour_name=self.config.contour_name,
                manager_name=self.config.manager_name,
                symbol=context.symbol,
                exchange=context.exchange,
                timeframe=context.timeframe,
                source=context.source,
                freshness=freshness,
                validity=context.validity,
                decision=decision,
                status=status,
                originating_selection_id=context.opportunity.selection_id,
                originating_decision_id=context.orchestration.decision_id,
                originating_expansion_id=context.expansion.expansion_id,
                originating_governor_id=context.governor.governor_id,
                originating_protection_id=context.protection.protection_id,
                confidence=self._derive_confidence(context=context),
                priority_score=self._derive_priority_score(context=context),
                reason_code=reason,
            )
            self._active_workflows[key] = candidate
            self._workflow_key_by_id[candidate.workflow_id] = key
            payload = ManagerWorkflowPayload.from_candidate(candidate)
            self._refresh_diagnostics(
                lifecycle_state=ManagerRuntimeLifecycleState.READY,
                ready=True,
                last_workflow_id=str(candidate.workflow_id),
                last_event_type=event_type.value,
                last_failure_reason=None,
                readiness_reasons=(),
                degraded_reasons=(),
            )
            return ManagerRuntimeUpdate(
                context=context,
                workflow_candidate=candidate,
                event_type=event_type,
                emitted_payload=payload,
            )

        if existing is not None:
            invalidated = replace(
                existing,
                status=ManagerStatus.INVALIDATED,
                decision=ManagerDecision.ABSTAIN,
                validity=context.validity,
                reason_code=ManagerReasonCode.MANAGER_INVALIDATED,
            )
            self._move_to_historical(key=key, candidate=invalidated)
            payload = ManagerWorkflowPayload.from_candidate(invalidated)
            self._refresh_diagnostics(
                lifecycle_state=ManagerRuntimeLifecycleState.DEGRADED,
                ready=False,
                last_workflow_id=str(invalidated.workflow_id),
                last_event_type=ManagerEventType.MANAGER_WORKFLOW_INVALIDATED.value,
                last_failure_reason=context.validity.invalid_reason,
                degraded_reasons=(context.validity.invalid_reason or "manager_context_invalid",),
                readiness_reasons=("manager_context_invalid",),
            )
            return ManagerRuntimeUpdate(
                context=context,
                workflow_candidate=invalidated,
                event_type=ManagerEventType.MANAGER_WORKFLOW_INVALIDATED,
                emitted_payload=payload,
            )

        self._refresh_diagnostics(
            lifecycle_state=ManagerRuntimeLifecycleState.DEGRADED,
            ready=False,
            last_failure_reason=context.validity.invalid_reason,
            degraded_reasons=(context.validity.invalid_reason or "manager_context_invalid",),
            readiness_reasons=("manager_context_invalid",),
        )
        return ManagerRuntimeUpdate(context=context, workflow_candidate=None, event_type=None)

    def _build_validity(
        self,
        *,
        opportunity: OpportunitySelectionCandidate | None,
        orchestration: OrchestrationDecisionCandidate | None,
        expansion: PositionExpansionCandidate | None,
        governor: PortfolioGovernorCandidate | None,
        protection: ProtectionSupervisorCandidate | None,
        reference_time: datetime,
    ) -> tuple[ManagerValidity, ManagerReasonCode]:
        missing_inputs = tuple(
            name
            for name, value in (
                ("opportunity", opportunity),
                ("orchestration", orchestration),
                ("expansion", expansion),
                ("governor", governor),
                ("protection", protection),
            )
            if value is None
        )
        observed_inputs = 5 - len(missing_inputs)
        if missing_inputs:
            return (
                ManagerValidity(
                    status=ManagerValidityStatus.WARMING,
                    observed_inputs=observed_inputs,
                    required_inputs=5,
                    missing_inputs=missing_inputs,
                ),
                ManagerReasonCode.CONTEXT_INCOMPLETE,
            )

        invalid_upstreams = (
            opportunity is not None
            and (
                opportunity.validity.status == opportunity.validity.status.INVALID
                or opportunity.status.value in {"invalidated", "expired"}
            ),
            orchestration is not None
            and (
                orchestration.validity.status == orchestration.validity.status.INVALID
                or orchestration.status.value in {"invalidated", "expired"}
            ),
            expansion is not None
            and (
                expansion.validity.status == expansion.validity.status.INVALID
                or expansion.status.value in {"invalidated", "expired"}
            ),
            governor is not None
            and (
                governor.validity.status == governor.validity.status.INVALID
                or governor.status.value in {"invalidated", "expired"}
            ),
            protection is not None
            and (
                protection.validity.status == protection.validity.status.INVALID
                or protection.status.value in {"invalidated", "expired"}
            ),
        )
        if any(invalid_upstreams):
            return (
                ManagerValidity(
                    status=ManagerValidityStatus.INVALID,
                    observed_inputs=5,
                    required_inputs=5,
                    invalid_reason="upstream_workflow_truth_invalidated",
                ),
                ManagerReasonCode.MANAGER_INVALIDATED,
            )

        checks: tuple[tuple[bool, ManagerReasonCode, str], ...] = (
            (
                opportunity is not None and opportunity.is_selected,
                ManagerReasonCode.OPPORTUNITY_NOT_SELECTED,
                "opportunity_not_selected",
            ),
            (
                orchestration is not None and orchestration.is_forwarded,
                ManagerReasonCode.ORCHESTRATION_NOT_FORWARDED,
                "orchestration_not_forwarded",
            ),
            (
                expansion is not None and expansion.is_expandable,
                ManagerReasonCode.EXPANSION_NOT_EXPANDABLE,
                "expansion_not_expandable",
            ),
            (
                governor is not None and governor.is_approved,
                ManagerReasonCode.GOVERNOR_NOT_APPROVED,
                "governor_not_approved",
            ),
            (
                protection is not None
                and (protection.is_protected or protection.is_halted or protection.is_frozen),
                ManagerReasonCode.PROTECTION_NOT_COORDINATABLE,
                "protection_not_coordinatable",
            ),
        )
        first_nonready = next((item for item in checks if not item[0]), None)
        if first_nonready is not None:
            return (
                ManagerValidity(
                    status=ManagerValidityStatus.WARMING,
                    observed_inputs=observed_inputs,
                    required_inputs=5,
                    missing_inputs=(first_nonready[2],),
                ),
                first_nonready[1],
            )

        freshness_values = (
            opportunity.freshness if opportunity is not None else None,
            orchestration.freshness if orchestration is not None else None,
            expansion.freshness if expansion is not None else None,
            governor.freshness if governor is not None else None,
            protection.freshness if protection is not None else None,
        )
        if any(
            item is not None and item.is_expired_at(reference_time) for item in freshness_values
        ):
            return (
                ManagerValidity(
                    status=ManagerValidityStatus.INVALID,
                    observed_inputs=5,
                    required_inputs=5,
                    invalid_reason="upstream_workflow_truth_expired",
                ),
                ManagerReasonCode.MANAGER_EXPIRED,
            )

        return (
            ManagerValidity(
                status=ManagerValidityStatus.VALID,
                observed_inputs=5,
                required_inputs=5,
            ),
            ManagerReasonCode.CONTEXT_READY,
        )

    def _build_freshness(
        self,
        *,
        context: ManagerContext,
        reference_time: datetime,
    ) -> ManagerFreshness:
        expires_at_candidates = (
            context.opportunity.freshness.expires_at,
            context.orchestration.freshness.expires_at,
            context.expansion.freshness.expires_at,
            context.governor.freshness.expires_at,
            context.protection.freshness.expires_at,
        )
        non_null = tuple(item for item in expires_at_candidates if item is not None)
        return ManagerFreshness(
            generated_at=reference_time,
            expires_at=min(non_null)
            if non_null
            else reference_time + timedelta(seconds=self.config.max_workflow_age_seconds),
        )

    def _assemble_manager_context(
        self,
        *,
        symbol: str,
        exchange: str,
        timeframe: MarketDataTimeframe,
        opportunity: OpportunitySelectionCandidate,
        orchestration: OrchestrationDecisionCandidate,
        expansion: PositionExpansionCandidate,
        governor: PortfolioGovernorCandidate,
        protection: ProtectionSupervisorCandidate,
        validity: ManagerValidity,
        reference_time: datetime,
    ) -> ManagerContext:
        """Собрать typed ManagerContext внутри manager layer."""
        return ManagerContext(
            manager_name=self.config.manager_name,
            contour_name=self.config.contour_name,
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
            observed_at=reference_time,
            source=ManagerSource.WORKFLOW_FOUNDATIONS,
            opportunity=opportunity,
            orchestration=orchestration,
            expansion=expansion,
            governor=governor,
            protection=protection,
            validity=validity,
            metadata={},
        )

    @staticmethod
    def _derive_confidence(context: ManagerContext) -> Decimal | None:
        values = tuple(
            value
            for value in (
                context.opportunity.confidence,
                context.orchestration.confidence,
                context.expansion.confidence,
                context.governor.confidence,
                context.protection.confidence,
            )
            if value is not None
        )
        if not values:
            return None
        return (sum(values, Decimal("0")) / Decimal(len(values))).quantize(Decimal("0.0001"))

    @staticmethod
    def _derive_priority_score(context: ManagerContext) -> Decimal | None:
        values = tuple(
            value
            for value in (
                context.opportunity.priority_score,
                context.orchestration.priority_score,
                context.expansion.priority_score,
                context.governor.priority_score,
                context.protection.priority_score,
            )
            if value is not None
        )
        if not values:
            return None
        return max(values)

    @staticmethod
    def _resolve_state_key(
        *,
        opportunity: OpportunitySelectionCandidate | None,
        orchestration: OrchestrationDecisionCandidate | None,
        expansion: PositionExpansionCandidate | None,
        governor: PortfolioGovernorCandidate | None,
        protection: ProtectionSupervisorCandidate | None,
    ) -> ManagerStateKey | None:
        for value in (protection, governor, expansion, orchestration, opportunity):
            if value is not None:
                return (value.symbol, value.exchange, value.timeframe)
        return None

    def _move_to_historical(
        self,
        *,
        key: ManagerStateKey,
        candidate: ManagerWorkflowCandidate,
    ) -> None:
        self._historical_workflows[key] = candidate
        self._workflow_key_by_id[candidate.workflow_id] = key
        self._active_workflows.pop(key, None)

    def _ensure_started(self) -> None:
        if not self._started:
            raise RuntimeError("Manager runtime должен быть явно запущен перед ingest")

    def _refresh_diagnostics(
        self,
        *,
        lifecycle_state: ManagerRuntimeLifecycleState | None = None,
        ready: bool | None = None,
        last_workflow_id: str | None = None,
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
        self._diagnostics.tracked_active_workflows = len(self._active_workflows)
        self._diagnostics.tracked_historical_workflows = len(self._historical_workflows)
        if last_workflow_id is not None:
            self._diagnostics.last_workflow_id = last_workflow_id
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


def create_manager_runtime(
    config: ManagerRuntimeConfig | None = None,
    *,
    diagnostics_sink: Callable[[dict[str, object]], None] | None = None,
) -> ManagerRuntime:
    """Явный factory runtime entrypoint manager layer."""
    return ManagerRuntime(config, diagnostics_sink=diagnostics_sink)


__all__ = [
    "ManagerRuntime",
    "ManagerRuntimeConfig",
    "ManagerRuntimeDiagnostics",
    "ManagerRuntimeLifecycleState",
    "ManagerRuntimeUpdate",
    "ManagerStateKey",
    "create_manager_runtime",
]

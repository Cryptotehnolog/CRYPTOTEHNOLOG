"""Source/provider abstractions для overview facade."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from cryptotechnolog.config import Settings, get_settings
from cryptotechnolog.core.state_machine_enums import get_state_policy
from cryptotechnolog.reporting import ReportingArtifactCatalog, ReportingSourceLayer
from cryptotechnolog.risk.portfolio_state import PortfolioState

from .contracts import (
    BacktestSummarySnapshot,
    CircuitBreakerSnapshot,
    EventSummarySnapshot,
    ExecutionSummarySnapshot,
    ManagerSummarySnapshot,
    OmsSummarySnapshot,
    OpenPositionSnapshot,
    OpenPositionsSnapshot,
    PositionHistoryRecordSnapshot,
    PositionHistorySnapshot,
    OpportunitySummarySnapshot,
    OrchestrationSummarySnapshot,
    PaperSummarySnapshot,
    PendingApprovalsSnapshot,
    PortfolioGovernorSummarySnapshot,
    PositionExpansionSummarySnapshot,
    ReportingCatalogCountsSnapshot,
    ReportingLastArtifactSnapshot,
    ReportingLastBundleSnapshot,
    ReportingSummarySnapshot,
    RiskConfigSnapshot,
    RiskRuntimeSnapshot,
    SignalSummarySnapshot,
    StrategySummarySnapshot,
    ValidationSummarySnapshot,
)

if TYPE_CHECKING:
    from cryptotechnolog.core.health import HealthChecker, SystemHealth
    from cryptotechnolog.core.operator_gate import OperatorGate
    from cryptotechnolog.core.system_controller import SystemController, SystemStatus
    from cryptotechnolog.risk.persistence_contracts import IRiskPersistenceRepository

    from ..registry.module_registry import ModuleAvailabilityRecord, ModuleAvailabilityRegistry


class SystemStatusSource(Protocol):
    """Источник системного статуса."""

    async def get_system_status(self) -> SystemStatus: ...


class HealthSnapshotSource(Protocol):
    """Источник health snapshot."""

    async def get_health_snapshot(self) -> SystemHealth | None: ...


class PendingApprovalsSource(Protocol):
    """Источник pending approvals summary."""

    async def get_pending_approvals_summary(self) -> PendingApprovalsSnapshot: ...


class EventSummarySource(Protocol):
    """Источник event summary."""

    async def get_event_summary(self) -> EventSummarySnapshot: ...


class ModuleAvailabilitySource(Protocol):
    """Источник snapshot доступности модулей панели."""

    async def get_module_availability(self) -> list[ModuleAvailabilityRecord]: ...


class RiskRuntimeSource(Protocol):
    """Источник runtime truth для risk summary."""

    async def get_risk_runtime_snapshot(self) -> RiskRuntimeSnapshot: ...


class RiskConfigSource(Protocol):
    """Источник settings/config truth для risk summary."""

    async def get_risk_config_snapshot(self) -> RiskConfigSnapshot: ...


class SignalSummarySource(Protocol):
    """Источник surfaced signal runtime diagnostics."""

    async def get_signal_summary_snapshot(self) -> SignalSummarySnapshot: ...


class StrategySummarySource(Protocol):
    """Источник surfaced strategy runtime diagnostics."""

    async def get_strategy_summary_snapshot(self) -> StrategySummarySnapshot: ...


class ExecutionSummarySource(Protocol):
    """Источник surfaced execution runtime diagnostics."""

    async def get_execution_summary_snapshot(self) -> ExecutionSummarySnapshot: ...


class OmsSummarySource(Protocol):
    """Источник surfaced OMS runtime diagnostics."""

    async def get_oms_summary_snapshot(self) -> OmsSummarySnapshot: ...


class OrchestrationSummarySource(Protocol):
    """Источник surfaced orchestration runtime diagnostics."""

    async def get_orchestration_summary_snapshot(self) -> OrchestrationSummarySnapshot: ...


class OpportunitySummarySource(Protocol):
    """Источник surfaced opportunity runtime diagnostics."""

    async def get_opportunity_summary_snapshot(self) -> OpportunitySummarySnapshot: ...


class PositionExpansionSummarySource(Protocol):
    """Источник surfaced position-expansion runtime diagnostics."""

    async def get_position_expansion_summary_snapshot(self) -> PositionExpansionSummarySnapshot: ...


class PortfolioGovernorSummarySource(Protocol):
    """Источник surfaced portfolio-governor runtime diagnostics."""

    async def get_portfolio_governor_summary_snapshot(self) -> PortfolioGovernorSummarySnapshot: ...


class ManagerSummarySource(Protocol):
    """Источник surfaced manager runtime diagnostics."""

    async def get_manager_summary_snapshot(self) -> ManagerSummarySnapshot: ...


class ValidationSummarySource(Protocol):
    """Источник surfaced validation runtime diagnostics."""

    async def get_validation_summary_snapshot(self) -> ValidationSummarySnapshot: ...


class PaperSummarySource(Protocol):
    """Источник surfaced paper runtime diagnostics."""

    async def get_paper_summary_snapshot(self) -> PaperSummarySnapshot: ...


class BacktestSummarySource(Protocol):
    """Источник surfaced backtest runtime diagnostics."""

    async def get_backtest_summary_snapshot(self) -> BacktestSummarySnapshot: ...


class ReportingSummarySource(Protocol):
    """Источник surfaced reporting artifact catalog summary."""

    async def get_reporting_summary_snapshot(self) -> ReportingSummarySnapshot: ...


class OpenPositionsSource(Protocol):
    """Источник surfaced open positions snapshot."""

    async def get_open_positions_snapshot(self) -> OpenPositionsSnapshot: ...


class PositionHistorySource(Protocol):
    """Источник surfaced closed position history snapshot."""

    async def get_position_history_snapshot(self) -> PositionHistorySnapshot: ...


def parse_circuit_breaker_snapshots(
    raw_snapshots: dict[str, dict[str, Any]],
) -> list[CircuitBreakerSnapshot]:
    """Преобразовать внутренние dict snapshots circuit breakers в typed contracts."""
    return [
        CircuitBreakerSnapshot(
            name=name,
            state=str(data.get("state", "unknown")),
            failure_count=int(data.get("failure_count", 0)),
            success_count=int(data.get("success_count", 0)),
            failure_threshold=int(data.get("failure_threshold", 0)),
            recovery_timeout=int(data.get("recovery_timeout", 0)),
        )
        for name, data in sorted(raw_snapshots.items())
    ]


@dataclass(slots=True)
class ControllerSystemStatusSource:
    """Адаптер SystemController для facade."""

    controller: SystemController

    async def get_system_status(self) -> SystemStatus:
        return await self.controller.get_status()


@dataclass(slots=True)
class HealthCheckerSource:
    """Адаптер HealthChecker для facade."""

    checker: HealthChecker
    prefer_cached: bool = True

    async def get_health_snapshot(self) -> SystemHealth | None:
        if self.prefer_cached:
            cached = self.checker.get_last_health()
            if cached is not None:
                return cached
        return await self.checker.check_system()


@dataclass(slots=True)
class OperatorGateSummarySource:
    """Адаптер OperatorGate для summary approvals."""

    gate: OperatorGate

    async def get_pending_approvals_summary(self) -> PendingApprovalsSnapshot:
        stats = self.gate.get_stats()
        return PendingApprovalsSnapshot(
            pending_count=len(self.gate.get_pending_requests()),
            total_requests=int(stats.get("total_requests", 0)),
            request_timeout_minutes=int(stats.get("request_timeout", 0)),
        )


@dataclass(slots=True)
class EventBusSummarySource:
    """Адаптер event bus metrics для summary events."""

    event_bus: Any

    async def get_event_summary(self) -> EventSummarySnapshot:
        metrics = self.event_bus.get_metrics()
        bus_metrics = metrics.get("bus_metrics", {})
        return EventSummarySnapshot(
            total_published=int(bus_metrics.get("published", 0)),
            total_delivered=int(bus_metrics.get("delivered", 0)),
            total_dropped=int(bus_metrics.get("dropped", 0)),
            total_rate_limited=int(bus_metrics.get("rate_limited", 0)),
            subscriber_count=int(metrics.get("subscriber_count", 0)),
            persistence_enabled=bool(metrics.get("enable_persistence", False)),
            backpressure_strategy=str(metrics.get("backpressure_strategy", "unknown")),
        )


@dataclass(slots=True)
class ModuleRegistrySource:
    """Адаптер системного module registry."""

    registry: ModuleAvailabilityRegistry

    async def get_module_availability(self) -> list[ModuleAvailabilityRecord]:
        return self.registry.list_modules()


@dataclass(slots=True)
class ControllerRiskRuntimeSource:
    """Адаптер runtime truth controller/state-machine для risk summary."""

    controller: SystemController
    event_bus: Any

    async def get_risk_runtime_snapshot(self) -> RiskRuntimeSnapshot:
        state_machine = self.controller.state_machine()
        current_state = state_machine.current_state
        policy = get_state_policy(current_state)

        return RiskRuntimeSnapshot(
            active_risk_path=getattr(self.event_bus, "active_risk_path", None),
            risk_multiplier=state_machine.get_risk_multiplier(),
            allow_new_positions=policy.allow_new_positions,
            allow_new_orders=policy.allow_new_orders,
            max_positions=policy.max_positions,
            max_order_size=policy.max_order_size,
            require_manual_approval=policy.require_manual_approval,
            policy_description=policy.description,
        )


@dataclass(slots=True)
class SettingsRiskConfigSource:
    """Адаптер settings в узкий risk config snapshot."""

    settings: Settings

    async def get_risk_config_snapshot(self) -> RiskConfigSnapshot:
        return RiskConfigSnapshot(
            base_r_percent=self.settings.base_r_percent,
            max_r_per_trade=self.settings.max_r_per_trade,
            max_portfolio_r=self.settings.max_portfolio_r,
            max_total_exposure_usd=self.settings.risk_max_total_exposure_usd,
            max_position_size_usd=self.settings.max_position_size,
            kill_switch_enabled=self.settings.kill_switch_enabled,
        )


def create_default_risk_config_source() -> SettingsRiskConfigSource:
    """Создать settings-backed источник risk config summary."""
    return SettingsRiskConfigSource(settings=get_settings())


@dataclass(slots=True)
class RuntimeSignalSummarySource:
    """Адаптер surfaced signal runtime diagnostics в narrow dashboard contract."""

    signal_runtime: Any

    async def get_signal_summary_snapshot(self) -> SignalSummarySnapshot:
        diagnostics = self.signal_runtime.get_runtime_diagnostics()
        contour_name = getattr(getattr(self.signal_runtime, "config", None), "contour_name", None)

        return SignalSummarySnapshot(
            started=bool(diagnostics.get("started", False)),
            ready=bool(diagnostics.get("ready", False)),
            lifecycle_state=str(diagnostics.get("lifecycle_state", "not_started")),
            tracked_signal_keys=int(diagnostics.get("tracked_signal_keys", 0)),
            active_signal_keys=int(diagnostics.get("active_signal_keys", 0)),
            invalidated_signal_keys=int(diagnostics.get("invalidated_signal_keys", 0)),
            expired_signal_keys=int(diagnostics.get("expired_signal_keys", 0)),
            last_context_at=(
                str(diagnostics["last_context_at"])
                if diagnostics.get("last_context_at") is not None
                else None
            ),
            last_signal_id=(
                str(diagnostics["last_signal_id"])
                if diagnostics.get("last_signal_id") is not None
                else None
            ),
            last_event_type=(
                str(diagnostics["last_event_type"])
                if diagnostics.get("last_event_type") is not None
                else None
            ),
            last_failure_reason=(
                str(diagnostics["last_failure_reason"])
                if diagnostics.get("last_failure_reason") is not None
                else None
            ),
            readiness_reasons=tuple(str(item) for item in diagnostics.get("readiness_reasons", [])),
            degraded_reasons=tuple(str(item) for item in diagnostics.get("degraded_reasons", [])),
            active_signal_path=str(contour_name) if contour_name is not None else "not_surfaced",
        )


@dataclass(slots=True)
class RuntimeStrategySummarySource:
    """Адаптер surfaced strategy runtime diagnostics в narrow dashboard contract."""

    strategy_runtime: Any

    async def get_strategy_summary_snapshot(self) -> StrategySummarySnapshot:
        diagnostics = self.strategy_runtime.get_runtime_diagnostics()
        config = getattr(self.strategy_runtime, "config", None)
        contour_name = getattr(config, "contour_name", None)
        strategy_name = getattr(config, "strategy_name", None)

        return StrategySummarySnapshot(
            started=bool(diagnostics.get("started", False)),
            ready=bool(diagnostics.get("ready", False)),
            lifecycle_state=str(diagnostics.get("lifecycle_state", "not_started")),
            tracked_context_keys=int(diagnostics.get("tracked_context_keys", 0)),
            tracked_candidate_keys=int(diagnostics.get("tracked_candidate_keys", 0)),
            actionable_candidate_keys=int(diagnostics.get("actionable_candidate_keys", 0)),
            invalidated_candidate_keys=int(diagnostics.get("invalidated_candidate_keys", 0)),
            expired_candidate_keys=int(diagnostics.get("expired_candidate_keys", 0)),
            last_signal_id=(
                str(diagnostics["last_signal_id"])
                if diagnostics.get("last_signal_id") is not None
                else None
            ),
            last_candidate_id=(
                str(diagnostics["last_candidate_id"])
                if diagnostics.get("last_candidate_id") is not None
                else None
            ),
            last_event_type=(
                str(diagnostics["last_event_type"])
                if diagnostics.get("last_event_type") is not None
                else None
            ),
            last_failure_reason=(
                str(diagnostics["last_failure_reason"])
                if diagnostics.get("last_failure_reason") is not None
                else None
            ),
            readiness_reasons=tuple(str(item) for item in diagnostics.get("readiness_reasons", [])),
            degraded_reasons=tuple(str(item) for item in diagnostics.get("degraded_reasons", [])),
            active_strategy_path=(
                str(contour_name) if contour_name is not None else "not_surfaced"
            ),
            strategy_source=(str(strategy_name) if strategy_name is not None else "not_surfaced"),
        )


@dataclass(slots=True)
class RuntimeExecutionSummarySource:
    """Адаптер surfaced execution runtime diagnostics в narrow dashboard contract."""

    execution_runtime: Any

    async def get_execution_summary_snapshot(self) -> ExecutionSummarySnapshot:
        diagnostics = self.execution_runtime.get_runtime_diagnostics()
        config = getattr(self.execution_runtime, "config", None)
        contour_name = getattr(config, "contour_name", None)
        execution_name = getattr(config, "execution_name", None)

        return ExecutionSummarySnapshot(
            started=bool(diagnostics.get("started", False)),
            ready=bool(diagnostics.get("ready", False)),
            lifecycle_state=str(diagnostics.get("lifecycle_state", "not_started")),
            tracked_context_keys=int(diagnostics.get("tracked_context_keys", 0)),
            tracked_intent_keys=int(diagnostics.get("tracked_intent_keys", 0)),
            executable_intent_keys=int(diagnostics.get("executable_intent_keys", 0)),
            invalidated_intent_keys=int(diagnostics.get("invalidated_intent_keys", 0)),
            expired_intent_keys=int(diagnostics.get("expired_intent_keys", 0)),
            last_candidate_id=(
                str(diagnostics["last_candidate_id"])
                if diagnostics.get("last_candidate_id") is not None
                else None
            ),
            last_intent_id=(
                str(diagnostics["last_intent_id"])
                if diagnostics.get("last_intent_id") is not None
                else None
            ),
            last_event_type=(
                str(diagnostics["last_event_type"])
                if diagnostics.get("last_event_type") is not None
                else None
            ),
            last_failure_reason=(
                str(diagnostics["last_failure_reason"])
                if diagnostics.get("last_failure_reason") is not None
                else None
            ),
            readiness_reasons=tuple(str(item) for item in diagnostics.get("readiness_reasons", [])),
            degraded_reasons=tuple(str(item) for item in diagnostics.get("degraded_reasons", [])),
            active_execution_path=(
                str(contour_name) if contour_name is not None else "not_surfaced"
            ),
            execution_source=(
                str(execution_name) if execution_name is not None else "not_surfaced"
            ),
        )


@dataclass(slots=True)
class RuntimeOmsSummarySource:
    """Адаптер surfaced OMS runtime diagnostics в narrow dashboard contract."""

    oms_runtime: Any

    async def get_oms_summary_snapshot(self) -> OmsSummarySnapshot:
        diagnostics = self.oms_runtime.get_runtime_diagnostics()
        config = getattr(self.oms_runtime, "config", None)
        contour_name = getattr(config, "contour_name", None)
        oms_name = getattr(config, "oms_name", None)

        return OmsSummarySnapshot(
            started=bool(diagnostics.get("started", False)),
            ready=bool(diagnostics.get("ready", False)),
            lifecycle_state=str(diagnostics.get("lifecycle_state", "not_started")),
            tracked_contexts=int(diagnostics.get("tracked_contexts", 0)),
            tracked_active_orders=int(diagnostics.get("tracked_active_orders", 0)),
            tracked_historical_orders=int(diagnostics.get("tracked_historical_orders", 0)),
            last_intent_id=(
                str(diagnostics["last_intent_id"])
                if diagnostics.get("last_intent_id") is not None
                else None
            ),
            last_order_id=(
                str(diagnostics["last_order_id"])
                if diagnostics.get("last_order_id") is not None
                else None
            ),
            last_event_type=(
                str(diagnostics["last_event_type"])
                if diagnostics.get("last_event_type") is not None
                else None
            ),
            last_failure_reason=(
                str(diagnostics["last_failure_reason"])
                if diagnostics.get("last_failure_reason") is not None
                else None
            ),
            readiness_reasons=tuple(str(item) for item in diagnostics.get("readiness_reasons", [])),
            degraded_reasons=tuple(str(item) for item in diagnostics.get("degraded_reasons", [])),
            active_oms_path=(str(contour_name) if contour_name is not None else "not_surfaced"),
            oms_source=(str(oms_name) if oms_name is not None else "not_surfaced"),
        )


@dataclass(slots=True)
class RuntimeOpportunitySummarySource:
    """Адаптер surfaced opportunity runtime diagnostics в narrow dashboard contract."""

    opportunity_runtime: Any

    async def get_opportunity_summary_snapshot(self) -> OpportunitySummarySnapshot:
        diagnostics = self.opportunity_runtime.get_runtime_diagnostics()
        config = getattr(self.opportunity_runtime, "config", None)
        contour_name = getattr(config, "contour_name", None)
        selection_name = getattr(config, "selection_name", None)

        return OpportunitySummarySnapshot(
            started=bool(diagnostics.get("started", False)),
            ready=bool(diagnostics.get("ready", False)),
            lifecycle_state=str(diagnostics.get("lifecycle_state", "not_started")),
            tracked_context_keys=int(diagnostics.get("tracked_context_keys", 0)),
            tracked_selection_keys=int(diagnostics.get("tracked_selection_keys", 0)),
            selected_keys=int(diagnostics.get("selected_keys", 0)),
            invalidated_selection_keys=int(diagnostics.get("invalidated_selection_keys", 0)),
            expired_selection_keys=int(diagnostics.get("expired_selection_keys", 0)),
            last_intent_id=(
                str(diagnostics["last_intent_id"])
                if diagnostics.get("last_intent_id") is not None
                else None
            ),
            last_selection_id=(
                str(diagnostics["last_selection_id"])
                if diagnostics.get("last_selection_id") is not None
                else None
            ),
            last_event_type=(
                str(diagnostics["last_event_type"])
                if diagnostics.get("last_event_type") is not None
                else None
            ),
            last_failure_reason=(
                str(diagnostics["last_failure_reason"])
                if diagnostics.get("last_failure_reason") is not None
                else None
            ),
            readiness_reasons=tuple(str(item) for item in diagnostics.get("readiness_reasons", [])),
            degraded_reasons=tuple(str(item) for item in diagnostics.get("degraded_reasons", [])),
            active_opportunity_path=(
                str(contour_name) if contour_name is not None else "not_surfaced"
            ),
            opportunity_source=(
                str(selection_name) if selection_name is not None else "not_surfaced"
            ),
        )


@dataclass(slots=True)
class RuntimeOrchestrationSummarySource:
    """Адаптер surfaced orchestration runtime diagnostics в narrow dashboard contract."""

    orchestration_runtime: Any

    async def get_orchestration_summary_snapshot(self) -> OrchestrationSummarySnapshot:
        diagnostics = self.orchestration_runtime.get_runtime_diagnostics()
        config = getattr(self.orchestration_runtime, "config", None)
        contour_name = getattr(config, "contour_name", None)
        orchestration_name = getattr(config, "orchestration_name", None)

        return OrchestrationSummarySnapshot(
            started=bool(diagnostics.get("started", False)),
            ready=bool(diagnostics.get("ready", False)),
            lifecycle_state=str(diagnostics.get("lifecycle_state", "not_started")),
            tracked_context_keys=int(diagnostics.get("tracked_context_keys", 0)),
            tracked_decision_keys=int(diagnostics.get("tracked_decision_keys", 0)),
            forwarded_keys=int(diagnostics.get("forwarded_keys", 0)),
            abstained_keys=int(diagnostics.get("abstained_keys", 0)),
            invalidated_decision_keys=int(diagnostics.get("invalidated_decision_keys", 0)),
            expired_decision_keys=int(diagnostics.get("expired_decision_keys", 0)),
            last_selection_id=(
                str(diagnostics["last_selection_id"])
                if diagnostics.get("last_selection_id") is not None
                else None
            ),
            last_decision_id=(
                str(diagnostics["last_decision_id"])
                if diagnostics.get("last_decision_id") is not None
                else None
            ),
            last_event_type=(
                str(diagnostics["last_event_type"])
                if diagnostics.get("last_event_type") is not None
                else None
            ),
            last_failure_reason=(
                str(diagnostics["last_failure_reason"])
                if diagnostics.get("last_failure_reason") is not None
                else None
            ),
            readiness_reasons=tuple(str(item) for item in diagnostics.get("readiness_reasons", [])),
            degraded_reasons=tuple(str(item) for item in diagnostics.get("degraded_reasons", [])),
            active_orchestration_path=(
                str(contour_name) if contour_name is not None else "not_surfaced"
            ),
            orchestration_source=(
                str(orchestration_name) if orchestration_name is not None else "not_surfaced"
            ),
        )


@dataclass(slots=True)
class RuntimePositionExpansionSummarySource:
    """Адаптер surfaced position-expansion runtime diagnostics в narrow dashboard contract."""

    position_expansion_runtime: Any

    async def get_position_expansion_summary_snapshot(self) -> PositionExpansionSummarySnapshot:
        diagnostics = self.position_expansion_runtime.get_runtime_diagnostics()
        config = getattr(self.position_expansion_runtime, "config", None)
        contour_name = getattr(config, "contour_name", None)
        expansion_name = getattr(config, "expansion_name", None)

        return PositionExpansionSummarySnapshot(
            started=bool(diagnostics.get("started", False)),
            ready=bool(diagnostics.get("ready", False)),
            lifecycle_state=str(diagnostics.get("lifecycle_state", "not_started")),
            tracked_context_keys=int(diagnostics.get("tracked_context_keys", 0)),
            tracked_expansion_keys=int(diagnostics.get("tracked_expansion_keys", 0)),
            expandable_keys=int(diagnostics.get("expandable_keys", 0)),
            abstained_keys=int(diagnostics.get("abstained_keys", 0)),
            rejected_keys=int(diagnostics.get("rejected_keys", 0)),
            invalidated_expansion_keys=int(diagnostics.get("invalidated_expansion_keys", 0)),
            expired_expansion_keys=int(diagnostics.get("expired_expansion_keys", 0)),
            last_decision_id=(
                str(diagnostics["last_decision_id"])
                if diagnostics.get("last_decision_id") is not None
                else None
            ),
            last_expansion_id=(
                str(diagnostics["last_expansion_id"])
                if diagnostics.get("last_expansion_id") is not None
                else None
            ),
            last_event_type=(
                str(diagnostics["last_event_type"])
                if diagnostics.get("last_event_type") is not None
                else None
            ),
            last_failure_reason=(
                str(diagnostics["last_failure_reason"])
                if diagnostics.get("last_failure_reason") is not None
                else None
            ),
            readiness_reasons=tuple(str(item) for item in diagnostics.get("readiness_reasons", [])),
            degraded_reasons=tuple(str(item) for item in diagnostics.get("degraded_reasons", [])),
            active_position_expansion_path=(
                str(contour_name) if contour_name is not None else "not_surfaced"
            ),
            position_expansion_source=(
                str(expansion_name) if expansion_name is not None else "not_surfaced"
            ),
        )


@dataclass(slots=True)
class RuntimePortfolioGovernorSummarySource:
    """Адаптер surfaced portfolio-governor runtime diagnostics в narrow dashboard contract."""

    portfolio_governor_runtime: Any

    async def get_portfolio_governor_summary_snapshot(self) -> PortfolioGovernorSummarySnapshot:
        diagnostics = self.portfolio_governor_runtime.get_runtime_diagnostics()
        config = getattr(self.portfolio_governor_runtime, "config", None)
        contour_name = getattr(config, "contour_name", None)
        governor_name = getattr(config, "governor_name", None)

        return PortfolioGovernorSummarySnapshot(
            started=bool(diagnostics.get("started", False)),
            ready=bool(diagnostics.get("ready", False)),
            lifecycle_state=str(diagnostics.get("lifecycle_state", "not_started")),
            tracked_context_keys=int(diagnostics.get("tracked_context_keys", 0)),
            tracked_governor_keys=int(diagnostics.get("tracked_governor_keys", 0)),
            approved_keys=int(diagnostics.get("approved_keys", 0)),
            abstained_keys=int(diagnostics.get("abstained_keys", 0)),
            rejected_keys=int(diagnostics.get("rejected_keys", 0)),
            invalidated_governor_keys=int(diagnostics.get("invalidated_governor_keys", 0)),
            expired_governor_keys=int(diagnostics.get("expired_governor_keys", 0)),
            last_expansion_id=(
                str(diagnostics["last_expansion_id"])
                if diagnostics.get("last_expansion_id") is not None
                else None
            ),
            last_governor_id=(
                str(diagnostics["last_governor_id"])
                if diagnostics.get("last_governor_id") is not None
                else None
            ),
            last_event_type=(
                str(diagnostics["last_event_type"])
                if diagnostics.get("last_event_type") is not None
                else None
            ),
            last_failure_reason=(
                str(diagnostics["last_failure_reason"])
                if diagnostics.get("last_failure_reason") is not None
                else None
            ),
            readiness_reasons=tuple(str(item) for item in diagnostics.get("readiness_reasons", [])),
            degraded_reasons=tuple(str(item) for item in diagnostics.get("degraded_reasons", [])),
            active_portfolio_governor_path=(
                str(contour_name) if contour_name is not None else "not_surfaced"
            ),
            portfolio_governor_source=(
                str(governor_name) if governor_name is not None else "not_surfaced"
            ),
        )


@dataclass(slots=True)
class RuntimeManagerSummarySource:
    """Адаптер surfaced manager runtime diagnostics в narrow dashboard contract."""

    manager_runtime: Any

    async def get_manager_summary_snapshot(self) -> ManagerSummarySnapshot:
        diagnostics = self.manager_runtime.get_runtime_diagnostics()
        config = getattr(self.manager_runtime, "config", None)
        contour_name = getattr(config, "contour_name", None)
        manager_name = getattr(config, "manager_name", None)

        return ManagerSummarySnapshot(
            started=bool(diagnostics.get("started", False)),
            ready=bool(diagnostics.get("ready", False)),
            lifecycle_state=str(diagnostics.get("lifecycle_state", "not_started")),
            tracked_contexts=int(diagnostics.get("tracked_contexts", 0)),
            tracked_active_workflows=int(diagnostics.get("tracked_active_workflows", 0)),
            tracked_historical_workflows=int(diagnostics.get("tracked_historical_workflows", 0)),
            last_workflow_id=(
                str(diagnostics["last_workflow_id"])
                if diagnostics.get("last_workflow_id") is not None
                else None
            ),
            last_event_type=(
                str(diagnostics["last_event_type"])
                if diagnostics.get("last_event_type") is not None
                else None
            ),
            last_failure_reason=(
                str(diagnostics["last_failure_reason"])
                if diagnostics.get("last_failure_reason") is not None
                else None
            ),
            readiness_reasons=tuple(str(item) for item in diagnostics.get("readiness_reasons", [])),
            degraded_reasons=tuple(str(item) for item in diagnostics.get("degraded_reasons", [])),
            active_manager_path=(str(contour_name) if contour_name is not None else "not_surfaced"),
            manager_source=(str(manager_name) if manager_name is not None else "not_surfaced"),
        )


@dataclass(slots=True)
class RuntimeValidationSummarySource:
    """Адаптер surfaced validation runtime diagnostics в narrow dashboard contract."""

    validation_runtime: Any

    async def get_validation_summary_snapshot(self) -> ValidationSummarySnapshot:
        diagnostics = self.validation_runtime.get_runtime_diagnostics()
        config = getattr(self.validation_runtime, "config", None)
        contour_name = getattr(config, "contour_name", None)
        validation_name = getattr(config, "validation_name", None)

        return ValidationSummarySnapshot(
            started=bool(diagnostics.get("started", False)),
            ready=bool(diagnostics.get("ready", False)),
            lifecycle_state=str(diagnostics.get("lifecycle_state", "not_started")),
            tracked_contexts=int(diagnostics.get("tracked_contexts", 0)),
            tracked_active_reviews=int(diagnostics.get("tracked_active_reviews", 0)),
            tracked_historical_reviews=int(diagnostics.get("tracked_historical_reviews", 0)),
            last_review_id=(
                str(diagnostics["last_review_id"])
                if diagnostics.get("last_review_id") is not None
                else None
            ),
            last_event_type=(
                str(diagnostics["last_event_type"])
                if diagnostics.get("last_event_type") is not None
                else None
            ),
            last_failure_reason=(
                str(diagnostics["last_failure_reason"])
                if diagnostics.get("last_failure_reason") is not None
                else None
            ),
            readiness_reasons=tuple(str(item) for item in diagnostics.get("readiness_reasons", [])),
            degraded_reasons=tuple(str(item) for item in diagnostics.get("degraded_reasons", [])),
            active_validation_path=(
                str(contour_name) if contour_name is not None else "not_surfaced"
            ),
            validation_source=(
                str(validation_name) if validation_name is not None else "not_surfaced"
            ),
        )


@dataclass(slots=True)
class RuntimePaperSummarySource:
    """Адаптер surfaced paper runtime diagnostics в narrow dashboard contract."""

    paper_runtime: Any

    async def get_paper_summary_snapshot(self) -> PaperSummarySnapshot:
        diagnostics = self.paper_runtime.get_runtime_diagnostics()
        config = getattr(self.paper_runtime, "config", None)
        contour_name = getattr(config, "contour_name", None)
        paper_name = getattr(config, "paper_name", None)

        return PaperSummarySnapshot(
            started=bool(diagnostics.get("started", False)),
            ready=bool(diagnostics.get("ready", False)),
            lifecycle_state=str(diagnostics.get("lifecycle_state", "not_started")),
            tracked_contexts=int(diagnostics.get("tracked_contexts", 0)),
            tracked_active_rehearsals=int(diagnostics.get("tracked_active_rehearsals", 0)),
            tracked_historical_rehearsals=int(diagnostics.get("tracked_historical_rehearsals", 0)),
            last_rehearsal_id=(
                str(diagnostics["last_rehearsal_id"])
                if diagnostics.get("last_rehearsal_id") is not None
                else None
            ),
            last_event_type=(
                str(diagnostics["last_event_type"])
                if diagnostics.get("last_event_type") is not None
                else None
            ),
            last_failure_reason=(
                str(diagnostics["last_failure_reason"])
                if diagnostics.get("last_failure_reason") is not None
                else None
            ),
            readiness_reasons=tuple(str(item) for item in diagnostics.get("readiness_reasons", [])),
            degraded_reasons=tuple(str(item) for item in diagnostics.get("degraded_reasons", [])),
            active_paper_path=(str(contour_name) if contour_name is not None else "not_surfaced"),
            paper_source=(str(paper_name) if paper_name is not None else "not_surfaced"),
        )


@dataclass(slots=True)
class RuntimeBacktestSummarySource:
    """Адаптер surfaced backtest runtime diagnostics в narrow dashboard contract."""

    backtest_runtime: Any

    async def get_backtest_summary_snapshot(self) -> BacktestSummarySnapshot:
        diagnostics = self.backtest_runtime.get_runtime_diagnostics()
        config = getattr(self.backtest_runtime, "config", None)
        contour_name = getattr(config, "contour_name", None)
        replay_name = getattr(config, "replay_name", None)

        return BacktestSummarySnapshot(
            started=bool(diagnostics.get("started", False)),
            ready=bool(diagnostics.get("ready", False)),
            lifecycle_state=str(diagnostics.get("lifecycle_state", "not_started")),
            tracked_inputs=int(diagnostics.get("tracked_inputs", 0)),
            tracked_contexts=int(diagnostics.get("tracked_contexts", 0)),
            tracked_active_replays=int(diagnostics.get("tracked_active_replays", 0)),
            tracked_historical_replays=int(diagnostics.get("tracked_historical_replays", 0)),
            last_replay_id=(
                str(diagnostics["last_replay_id"])
                if diagnostics.get("last_replay_id") is not None
                else None
            ),
            last_event_type=(
                str(diagnostics["last_event_type"])
                if diagnostics.get("last_event_type") is not None
                else None
            ),
            last_failure_reason=(
                str(diagnostics["last_failure_reason"])
                if diagnostics.get("last_failure_reason") is not None
                else None
            ),
            readiness_reasons=tuple(str(item) for item in diagnostics.get("readiness_reasons", [])),
            degraded_reasons=tuple(str(item) for item in diagnostics.get("degraded_reasons", [])),
            active_backtest_path=(
                str(contour_name) if contour_name is not None else "not_surfaced"
            ),
            backtest_source=(str(replay_name) if replay_name is not None else "not_surfaced"),
        )


@dataclass(slots=True)
class ReportingArtifactCatalogSummarySource:
    """Адаптер immutable reporting artifact catalog в dashboard summary contract."""

    catalog: ReportingArtifactCatalog

    async def get_reporting_summary_snapshot(self) -> ReportingSummarySnapshot:
        artifacts = self.catalog.artifacts
        bundles = self.catalog.bundles
        last_artifact = artifacts[-1] if artifacts else None
        last_bundle = bundles[-1] if bundles else None

        return ReportingSummarySnapshot(
            catalog_counts=ReportingCatalogCountsSnapshot(
                total_artifacts=len(artifacts),
                total_bundles=len(bundles),
                validation_artifacts=sum(
                    1
                    for artifact in artifacts
                    if artifact.source_layer == ReportingSourceLayer.VALIDATION
                ),
                paper_artifacts=sum(
                    1
                    for artifact in artifacts
                    if artifact.source_layer == ReportingSourceLayer.PAPER
                ),
                replay_artifacts=sum(
                    1
                    for artifact in artifacts
                    if artifact.source_layer == ReportingSourceLayer.REPLAY
                ),
            ),
            last_artifact_snapshot=(
                ReportingLastArtifactSnapshot(
                    kind=last_artifact.kind.value,
                    status=last_artifact.status.value,
                    source_layer=last_artifact.source_layer.value,
                    generated_at=last_artifact.generated_at,
                    source_reason_code=last_artifact.provenance.source_reason_code,
                )
                if last_artifact is not None
                else None
            ),
            last_bundle_snapshot=(
                ReportingLastBundleSnapshot(
                    reporting_name=last_bundle.reporting_name,
                    generated_at=last_bundle.generated_at,
                    artifact_count=len(last_bundle.artifacts),
                )
                if last_bundle is not None
                else None
            ),
        )


@dataclass(slots=True)
class PortfolioStateOpenPositionsSource:
    """Адаптер PortfolioState в узкий dashboard open positions contract."""

    portfolio_state: PortfolioState

    async def get_open_positions_snapshot(self) -> OpenPositionsSnapshot:
        positions = tuple(
            OpenPositionSnapshot(
                position_id=record.position_id,
                symbol=record.symbol,
                exchange=record.exchange_id,
                strategy=record.strategy_id,
                side=record.side.value,
                entry_price=record.entry_price,
                quantity=record.quantity,
                initial_stop=record.initial_stop,
                current_stop=record.current_stop,
                current_risk_usd=record.current_risk_usd,
                current_risk_r=record.current_risk_r,
                current_price=record.current_price,
                unrealized_pnl_usd=record.unrealized_pnl_usd,
                unrealized_pnl_percent=record.unrealized_pnl_percent,
                trailing_state=record.trailing_state.value,
                opened_at=record.opened_at,
                updated_at=record.updated_at,
            )
            for record in sorted(
                self.portfolio_state.list_positions(),
                key=lambda item: (item.opened_at, item.position_id),
            )
        )
        return OpenPositionsSnapshot(positions=positions)


@dataclass(slots=True)
class RiskPersistencePositionHistorySource:
    """Адаптер risk persistence history в узкий dashboard position history contract."""

    repository: IRiskPersistenceRepository | None

    async def get_position_history_snapshot(self) -> PositionHistorySnapshot:
        if self.repository is None:
            return PositionHistorySnapshot(positions=())

        records = await self.repository.list_closed_position_history()
        return PositionHistorySnapshot(
            positions=tuple(
                PositionHistoryRecordSnapshot(
                    position_id=record.position_id,
                    symbol=record.symbol,
                    exchange=record.exchange_id,
                    strategy=record.strategy_id,
                    side=record.side,
                    entry_price=record.entry_price,
                    quantity=record.quantity,
                    initial_stop=record.initial_stop,
                    current_stop=record.current_stop,
                    trailing_state=record.trailing_state,
                    opened_at=record.opened_at,
                    closed_at=record.closed_at,
                    realized_pnl_r=record.realized_pnl_r,
                    realized_pnl_usd=record.realized_pnl_usd,
                    realized_pnl_percent=record.realized_pnl_percent,
                )
                for record in records
            )
        )

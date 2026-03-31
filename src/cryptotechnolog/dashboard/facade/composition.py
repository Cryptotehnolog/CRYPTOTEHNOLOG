"""Composition root для overview facade."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from cryptotechnolog.config import get_settings

from .sources import (
    BacktestSummarySource,
    ControllerRiskRuntimeSource,
    ControllerSystemStatusSource,
    EventBusSummarySource,
    EventSummarySource,
    ExecutionSummarySource,
    HealthCheckerSource,
    HealthSnapshotSource,
    ManagerSummarySource,
    ModuleAvailabilitySource,
    ModuleRegistrySource,
    OmsSummarySource,
    OpenPositionsSource,
    OperatorGateSummarySource,
    OpportunitySummarySource,
    OrchestrationSummarySource,
    PaperSummarySource,
    PendingApprovalsSource,
    PortfolioGovernorSummarySource,
    PortfolioStateOpenPositionsSource,
    PositionExpansionSummarySource,
    PositionHistorySource,
    ReportingArtifactCatalogSummarySource,
    ReportingSummarySource,
    RiskConfigSource,
    RiskPersistencePositionHistorySource,
    RiskRuntimeSource,
    RuntimeBacktestSummarySource,
    RuntimeExecutionSummarySource,
    RuntimeManagerSummarySource,
    RuntimeOmsSummarySource,
    RuntimeOpportunitySummarySource,
    RuntimeOrchestrationSummarySource,
    RuntimePaperSummarySource,
    RuntimePortfolioGovernorSummarySource,
    RuntimePositionExpansionSummarySource,
    RuntimeSignalSummarySource,
    RuntimeStrategySummarySource,
    RuntimeValidationSummarySource,
    SettingsRiskConfigSource,
    SignalSummarySource,
    StrategySummarySource,
    SystemStatusSource,
    ValidationSummarySource,
)

if TYPE_CHECKING:
    from cryptotechnolog.core.health import HealthChecker
    from cryptotechnolog.core.operator_gate import OperatorGate
    from cryptotechnolog.core.system_controller import SystemController
    from cryptotechnolog.risk.persistence_contracts import IRiskPersistenceRepository
    from cryptotechnolog.risk.portfolio_state import PortfolioState

    from ..registry.module_registry import ModuleAvailabilityRegistry


@dataclass(slots=True)
class OverviewCompositionRoot:
    """Явный composition root overview facade."""

    system_status_source: SystemStatusSource
    health_snapshot_source: HealthSnapshotSource | None
    pending_approvals_source: PendingApprovalsSource
    event_summary_source: EventSummarySource
    module_availability_source: ModuleAvailabilitySource
    risk_runtime_source: RiskRuntimeSource
    risk_config_source: RiskConfigSource
    signal_summary_source: SignalSummarySource
    strategy_summary_source: StrategySummarySource
    execution_summary_source: ExecutionSummarySource
    opportunity_summary_source: OpportunitySummarySource
    oms_summary_source: OmsSummarySource
    manager_summary_source: ManagerSummarySource
    validation_summary_source: ValidationSummarySource
    paper_summary_source: PaperSummarySource
    open_positions_source: OpenPositionsSource
    position_history_source: PositionHistorySource | None = None
    backtest_summary_source: BacktestSummarySource | None = None
    reporting_summary_source: ReportingSummarySource | None = None
    orchestration_summary_source: OrchestrationSummarySource | None = None
    position_expansion_summary_source: PositionExpansionSummarySource | None = None
    portfolio_governor_summary_source: PortfolioGovernorSummarySource | None = None

    @classmethod
    def from_runtime(
        cls,
        *,
        controller: SystemController,
        operator_gate: OperatorGate,
        event_bus: Any,
        signal_runtime: Any,
        strategy_runtime: Any,
        execution_runtime: Any,
        opportunity_runtime: Any,
        orchestration_runtime: Any,
        position_expansion_runtime: Any,
        portfolio_governor_runtime: Any,
        oms_runtime: Any,
        manager_runtime: Any,
        validation_runtime: Any,
        paper_runtime: Any,
        backtest_runtime: Any,
        reporting_catalog: Any,
        portfolio_state: PortfolioState,
        risk_persistence_repository: IRiskPersistenceRepository | None,
        module_registry: ModuleAvailabilityRegistry,
        health_checker: HealthChecker | None = None,
    ) -> OverviewCompositionRoot:
        """Собрать composition root из runtime-компонентов backend."""
        return cls(
            system_status_source=ControllerSystemStatusSource(controller=controller),
            health_snapshot_source=(
                HealthCheckerSource(checker=health_checker) if health_checker is not None else None
            ),
            pending_approvals_source=OperatorGateSummarySource(gate=operator_gate),
            event_summary_source=EventBusSummarySource(event_bus=event_bus),
            module_availability_source=ModuleRegistrySource(registry=module_registry),
            risk_runtime_source=ControllerRiskRuntimeSource(
                controller=controller,
                event_bus=event_bus,
            ),
            risk_config_source=SettingsRiskConfigSource(settings=get_settings()),
            signal_summary_source=RuntimeSignalSummarySource(signal_runtime=signal_runtime),
            strategy_summary_source=RuntimeStrategySummarySource(strategy_runtime=strategy_runtime),
            execution_summary_source=RuntimeExecutionSummarySource(
                execution_runtime=execution_runtime
            ),
            opportunity_summary_source=RuntimeOpportunitySummarySource(
                opportunity_runtime=opportunity_runtime
            ),
            position_expansion_summary_source=RuntimePositionExpansionSummarySource(
                position_expansion_runtime=position_expansion_runtime
            ),
            portfolio_governor_summary_source=RuntimePortfolioGovernorSummarySource(
                portfolio_governor_runtime=portfolio_governor_runtime
            ),
            orchestration_summary_source=RuntimeOrchestrationSummarySource(
                orchestration_runtime=orchestration_runtime
            ),
            oms_summary_source=RuntimeOmsSummarySource(oms_runtime=oms_runtime),
            manager_summary_source=RuntimeManagerSummarySource(manager_runtime=manager_runtime),
            validation_summary_source=RuntimeValidationSummarySource(
                validation_runtime=validation_runtime
            ),
            paper_summary_source=RuntimePaperSummarySource(paper_runtime=paper_runtime),
            open_positions_source=PortfolioStateOpenPositionsSource(
                portfolio_state=portfolio_state
            ),
            position_history_source=RiskPersistencePositionHistorySource(
                repository=risk_persistence_repository
            ),
            backtest_summary_source=RuntimeBacktestSummarySource(backtest_runtime=backtest_runtime),
            reporting_summary_source=ReportingArtifactCatalogSummarySource(
                catalog=reporting_catalog
            ),
        )

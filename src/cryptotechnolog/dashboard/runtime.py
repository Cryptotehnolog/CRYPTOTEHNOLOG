"""Runtime wiring для backend-слоя панели управления."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from cryptotechnolog.backtest import ReplayRuntime, create_replay_runtime
from cryptotechnolog.config import get_logger
from cryptotechnolog.core.health import EventBusHealthCheck, HealthChecker, MetricsHealthCheck
from cryptotechnolog.core.metrics import MetricsCollector, get_metrics_collector
from cryptotechnolog.core.operator_gate import OperatorGate
from cryptotechnolog.core.system_controller import SystemController
from cryptotechnolog.execution import ExecutionRuntime, create_execution_runtime
from cryptotechnolog.manager import ManagerRuntime, create_manager_runtime
from cryptotechnolog.oms import OmsRuntime, create_oms_runtime
from cryptotechnolog.opportunity import OpportunityRuntime, create_opportunity_runtime
from cryptotechnolog.orchestration import OrchestrationRuntime, create_orchestration_runtime
from cryptotechnolog.paper import PaperRuntime, create_paper_runtime
from cryptotechnolog.portfolio_governor import (
    PortfolioGovernorRuntime,
    create_portfolio_governor_runtime,
)
from cryptotechnolog.position_expansion import (
    PositionExpansionRuntime,
    create_position_expansion_runtime,
)
from cryptotechnolog.reporting import ReportingArtifactCatalog, build_reporting_artifact_catalog
from cryptotechnolog.signals import SignalRuntime, create_signal_runtime
from cryptotechnolog.strategy import StrategyRuntime, create_strategy_runtime
from cryptotechnolog.validation import ValidationRuntime, create_validation_runtime

from .facade.composition import OverviewCompositionRoot
from .facade.overview_facade import OverviewFacade
from .registry.module_registry import ModuleAvailabilityRegistry, create_default_module_registry

if TYPE_CHECKING:
    from cryptotechnolog.core.enhanced_event_bus import EnhancedEventBus

logger = get_logger(__name__)


@dataclass(slots=True)
class DashboardRuntime:
    """Собранный runtime для read-only backend-слоя панели."""

    controller: SystemController
    health_checker: HealthChecker
    metrics_collector: MetricsCollector
    event_bus: EnhancedEventBus
    operator_gate: OperatorGate
    signal_runtime: SignalRuntime
    strategy_runtime: StrategyRuntime
    execution_runtime: ExecutionRuntime
    opportunity_runtime: OpportunityRuntime
    orchestration_runtime: OrchestrationRuntime
    position_expansion_runtime: PositionExpansionRuntime
    portfolio_governor_runtime: PortfolioGovernorRuntime
    oms_runtime: OmsRuntime
    manager_runtime: ManagerRuntime
    validation_runtime: ValidationRuntime
    paper_runtime: PaperRuntime
    backtest_runtime: ReplayRuntime
    reporting_catalog: ReportingArtifactCatalog
    module_registry: ModuleAvailabilityRegistry
    overview_facade: OverviewFacade

    async def start(self) -> None:
        """Запустить runtime-зависимости панели."""
        await self.event_bus.start()
        await self.operator_gate.start()
        await self.signal_runtime.start()
        await self.strategy_runtime.start()
        await self.execution_runtime.start()
        await self.opportunity_runtime.start()
        await self.orchestration_runtime.start()
        await self.position_expansion_runtime.start()
        await self.portfolio_governor_runtime.start()
        await self.oms_runtime.start()
        await self.manager_runtime.start()
        await self.validation_runtime.start()
        await self.paper_runtime.start()
        await self.backtest_runtime.start()
        await self.controller.state_machine().initialize()
        await self.health_checker.check_system()
        logger.info("Dashboard runtime запущен")

    async def stop(self) -> None:
        """Остановить runtime-зависимости панели."""
        await self.execution_runtime.stop()
        await self.opportunity_runtime.stop()
        await self.orchestration_runtime.stop()
        await self.portfolio_governor_runtime.stop()
        await self.position_expansion_runtime.stop()
        await self.oms_runtime.stop()
        await self.manager_runtime.stop()
        await self.validation_runtime.stop()
        await self.paper_runtime.stop()
        await self.backtest_runtime.stop()
        await self.strategy_runtime.stop()
        await self.signal_runtime.stop()
        await self.operator_gate.stop()
        await self.event_bus.shutdown()
        logger.info("Dashboard runtime остановлен")


def create_dashboard_runtime(
    *,
    event_bus: EnhancedEventBus,
    metrics_collector: MetricsCollector | None = None,
    module_registry: ModuleAvailabilityRegistry | None = None,
    health_checker: HealthChecker | None = None,
    operator_gate: OperatorGate | None = None,
    controller: SystemController | None = None,
    signal_runtime: SignalRuntime | None = None,
    strategy_runtime: StrategyRuntime | None = None,
    execution_runtime: ExecutionRuntime | None = None,
    opportunity_runtime: OpportunityRuntime | None = None,
    orchestration_runtime: OrchestrationRuntime | None = None,
    position_expansion_runtime: PositionExpansionRuntime | None = None,
    portfolio_governor_runtime: PortfolioGovernorRuntime | None = None,
    oms_runtime: OmsRuntime | None = None,
    manager_runtime: ManagerRuntime | None = None,
    validation_runtime: ValidationRuntime | None = None,
    paper_runtime: PaperRuntime | None = None,
    backtest_runtime: ReplayRuntime | None = None,
    reporting_catalog: ReportingArtifactCatalog | None = None,
) -> DashboardRuntime:
    """Собрать dashboard runtime поверх существующих backend-компонентов."""
    metrics = metrics_collector or get_metrics_collector()
    registry = module_registry or create_default_module_registry()

    checker = health_checker or HealthChecker()
    if not checker.get_registered_checks():
        checker.register_check(EventBusHealthCheck(event_bus))
        checker.register_check(MetricsHealthCheck(metrics))

    gate = operator_gate or OperatorGate(event_bus=event_bus)
    runtime_signal = signal_runtime or create_signal_runtime()
    runtime_strategy = strategy_runtime or create_strategy_runtime()
    runtime_execution = execution_runtime or create_execution_runtime()
    runtime_opportunity = opportunity_runtime or create_opportunity_runtime()
    runtime_orchestration = orchestration_runtime or create_orchestration_runtime()
    runtime_position_expansion = position_expansion_runtime or create_position_expansion_runtime()
    runtime_portfolio_governor = portfolio_governor_runtime or create_portfolio_governor_runtime()
    runtime_oms = oms_runtime or create_oms_runtime()
    runtime_manager = manager_runtime or create_manager_runtime()
    runtime_validation = validation_runtime or create_validation_runtime()
    runtime_paper = paper_runtime or create_paper_runtime()
    runtime_backtest = backtest_runtime or create_replay_runtime()
    artifact_catalog = reporting_catalog or build_reporting_artifact_catalog()
    runtime_controller = controller or SystemController(
        health_checker=checker,
        metrics_collector=metrics,
        event_bus=event_bus,
        test_mode=True,
    )

    runtime_controller.register_component(
        name="dashboard_operator_gate",
        component=gate,
        required=False,
        health_check_enabled=False,
    )
    runtime_controller.register_component(
        name="dashboard_event_bus",
        component=event_bus,
        required=False,
        health_check_enabled=False,
    )
    runtime_controller.register_component(
        name="dashboard_signal_runtime",
        component=runtime_signal,
        required=False,
        health_check_enabled=False,
    )
    runtime_controller.register_component(
        name="dashboard_strategy_runtime",
        component=runtime_strategy,
        required=False,
        health_check_enabled=False,
    )
    runtime_controller.register_component(
        name="dashboard_execution_runtime",
        component=runtime_execution,
        required=False,
        health_check_enabled=False,
    )
    runtime_controller.register_component(
        name="dashboard_opportunity_runtime",
        component=runtime_opportunity,
        required=False,
        health_check_enabled=False,
    )
    runtime_controller.register_component(
        name="dashboard_orchestration_runtime",
        component=runtime_orchestration,
        required=False,
        health_check_enabled=False,
    )
    runtime_controller.register_component(
        name="dashboard_position_expansion_runtime",
        component=runtime_position_expansion,
        required=False,
        health_check_enabled=False,
    )
    runtime_controller.register_component(
        name="dashboard_portfolio_governor_runtime",
        component=runtime_portfolio_governor,
        required=False,
        health_check_enabled=False,
    )
    runtime_controller.register_component(
        name="dashboard_oms_runtime",
        component=runtime_oms,
        required=False,
        health_check_enabled=False,
    )
    runtime_controller.register_component(
        name="dashboard_manager_runtime",
        component=runtime_manager,
        required=False,
        health_check_enabled=False,
    )
    runtime_controller.register_component(
        name="dashboard_validation_runtime",
        component=runtime_validation,
        required=False,
        health_check_enabled=False,
    )
    runtime_controller.register_component(
        name="dashboard_paper_runtime",
        component=runtime_paper,
        required=False,
        health_check_enabled=False,
    )
    runtime_controller.register_component(
        name="dashboard_backtest_runtime",
        component=runtime_backtest,
        required=False,
        health_check_enabled=False,
    )

    composition_root = OverviewCompositionRoot.from_runtime(
        controller=runtime_controller,
        operator_gate=gate,
        event_bus=event_bus,
        signal_runtime=runtime_signal,
        strategy_runtime=runtime_strategy,
        execution_runtime=runtime_execution,
        opportunity_runtime=runtime_opportunity,
        orchestration_runtime=runtime_orchestration,
        position_expansion_runtime=runtime_position_expansion,
        portfolio_governor_runtime=runtime_portfolio_governor,
        oms_runtime=runtime_oms,
        manager_runtime=runtime_manager,
        validation_runtime=runtime_validation,
        paper_runtime=runtime_paper,
        backtest_runtime=runtime_backtest,
        reporting_catalog=artifact_catalog,
        module_registry=registry,
        health_checker=checker,
    )

    return DashboardRuntime(
        controller=runtime_controller,
        health_checker=checker,
        metrics_collector=metrics,
        event_bus=event_bus,
        operator_gate=gate,
        signal_runtime=runtime_signal,
        strategy_runtime=runtime_strategy,
        execution_runtime=runtime_execution,
        opportunity_runtime=runtime_opportunity,
        orchestration_runtime=runtime_orchestration,
        position_expansion_runtime=runtime_position_expansion,
        portfolio_governor_runtime=runtime_portfolio_governor,
        oms_runtime=runtime_oms,
        manager_runtime=runtime_manager,
        validation_runtime=runtime_validation,
        paper_runtime=runtime_paper,
        backtest_runtime=runtime_backtest,
        reporting_catalog=artifact_catalog,
        module_registry=registry,
        overview_facade=OverviewFacade(composition_root=composition_root),
    )

"""Runtime wiring для backend-слоя панели управления."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from cryptotechnolog.config import get_logger
from cryptotechnolog.core.health import EventBusHealthCheck, HealthChecker, MetricsHealthCheck
from cryptotechnolog.core.metrics import MetricsCollector, get_metrics_collector
from cryptotechnolog.core.operator_gate import OperatorGate
from cryptotechnolog.core.system_controller import SystemController

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
    module_registry: ModuleAvailabilityRegistry
    overview_facade: OverviewFacade

    async def start(self) -> None:
        """Запустить runtime-зависимости панели."""
        await self.event_bus.start()
        await self.operator_gate.start()
        await self.controller.state_machine().initialize()
        await self.health_checker.check_system()
        logger.info("Dashboard runtime запущен")

    async def stop(self) -> None:
        """Остановить runtime-зависимости панели."""
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
) -> DashboardRuntime:
    """Собрать dashboard runtime поверх существующих backend-компонентов."""
    metrics = metrics_collector or get_metrics_collector()
    registry = module_registry or create_default_module_registry()

    checker = health_checker or HealthChecker()
    if not checker.get_registered_checks():
        checker.register_check(EventBusHealthCheck(event_bus))
        checker.register_check(MetricsHealthCheck(metrics))

    gate = operator_gate or OperatorGate(event_bus=event_bus)
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

    composition_root = OverviewCompositionRoot.from_runtime(
        controller=runtime_controller,
        operator_gate=gate,
        event_bus=event_bus,
        module_registry=registry,
        health_checker=checker,
    )

    return DashboardRuntime(
        controller=runtime_controller,
        health_checker=checker,
        metrics_collector=metrics,
        event_bus=event_bus,
        operator_gate=gate,
        module_registry=registry,
        overview_facade=OverviewFacade(composition_root=composition_root),
    )

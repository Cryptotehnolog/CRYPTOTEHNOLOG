"""Foundation для backend-слоя панели управления CRYPTOTEHNOLOG."""

from .api.router import create_dashboard_router
from .app import create_dashboard_app
from .dto.overview import OverviewSnapshotDTO
from .facade.composition import OverviewCompositionRoot
from .facade.overview_facade import OverviewFacade
from .registry.module_registry import (
    DashboardModuleDefinition,
    DashboardModuleStatus,
    ModuleAvailabilityRegistry,
    create_default_module_registry,
)
from .runtime import DashboardRuntime, create_dashboard_runtime

__all__ = [
    "DashboardModuleDefinition",
    "DashboardModuleStatus",
    "DashboardRuntime",
    "ModuleAvailabilityRegistry",
    "OverviewCompositionRoot",
    "OverviewFacade",
    "OverviewSnapshotDTO",
    "create_dashboard_app",
    "create_dashboard_router",
    "create_dashboard_runtime",
    "create_default_module_registry",
]

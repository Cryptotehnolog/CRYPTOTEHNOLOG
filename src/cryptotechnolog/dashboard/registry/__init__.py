"""Module registry панели управления."""

from .module_registry import (
    DashboardModuleDefinition,
    DashboardModuleStatus,
    ModuleAvailabilityRecord,
    ModuleAvailabilityRegistry,
    create_default_module_registry,
)

__all__ = [
    "DashboardModuleDefinition",
    "DashboardModuleStatus",
    "ModuleAvailabilityRecord",
    "ModuleAvailabilityRegistry",
    "create_default_module_registry",
]

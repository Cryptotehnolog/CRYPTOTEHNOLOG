"""Composition root для overview facade."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .sources import (
    ControllerSystemStatusSource,
    EventBusSummarySource,
    EventSummarySource,
    HealthCheckerSource,
    HealthSnapshotSource,
    ModuleAvailabilitySource,
    ModuleRegistrySource,
    OperatorGateSummarySource,
    PendingApprovalsSource,
    SystemStatusSource,
)

if TYPE_CHECKING:
    from cryptotechnolog.core.health import HealthChecker
    from cryptotechnolog.core.operator_gate import OperatorGate
    from cryptotechnolog.core.system_controller import SystemController

    from ..registry.module_registry import ModuleAvailabilityRegistry


@dataclass(slots=True)
class OverviewCompositionRoot:
    """Явный composition root overview facade."""

    system_status_source: SystemStatusSource
    health_snapshot_source: HealthSnapshotSource | None
    pending_approvals_source: PendingApprovalsSource
    event_summary_source: EventSummarySource
    module_availability_source: ModuleAvailabilitySource

    @classmethod
    def from_runtime(
        cls,
        *,
        controller: SystemController,
        operator_gate: OperatorGate,
        event_bus: Any,
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
        )

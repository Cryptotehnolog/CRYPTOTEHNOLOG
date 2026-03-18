"""Facade layer панели управления."""

from .composition import OverviewCompositionRoot
from .contracts import CircuitBreakerSnapshot, EventSummarySnapshot, PendingApprovalsSnapshot
from .overview_facade import OverviewFacade
from .sources import (
    ControllerSystemStatusSource,
    EventBusSummarySource,
    HealthCheckerSource,
    ModuleRegistrySource,
    OperatorGateSummarySource,
)

__all__ = [
    "CircuitBreakerSnapshot",
    "ControllerSystemStatusSource",
    "EventBusSummarySource",
    "EventSummarySnapshot",
    "HealthCheckerSource",
    "ModuleRegistrySource",
    "OperatorGateSummarySource",
    "OverviewCompositionRoot",
    "OverviewFacade",
    "PendingApprovalsSnapshot",
]

"""Foundation для backend-слоя панели управления CRYPTOTEHNOLOG."""

from .api.router import create_dashboard_router
from .app import create_dashboard_app
from .dto.backtest import BacktestSummaryDTO
from .dto.execution import ExecutionSummaryDTO
from .dto.manager import ManagerSummaryDTO
from .dto.oms import OmsSummaryDTO
from .dto.orchestration import OrchestrationSummaryDTO
from .dto.overview import OverviewSnapshotDTO
from .dto.paper import PaperSummaryDTO
from .dto.portfolio_governor import PortfolioGovernorSummaryDTO
from .dto.position_expansion import PositionExpansionSummaryDTO
from .dto.reporting import ReportingSummaryDTO
from .dto.risk import RiskSummaryDTO
from .dto.signals import SignalsSummaryDTO
from .dto.strategy import StrategySummaryDTO
from .dto.validation import ValidationSummaryDTO
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
    "BacktestSummaryDTO",
    "DashboardModuleDefinition",
    "DashboardModuleStatus",
    "DashboardRuntime",
    "ExecutionSummaryDTO",
    "ManagerSummaryDTO",
    "ModuleAvailabilityRegistry",
    "OmsSummaryDTO",
    "OrchestrationSummaryDTO",
    "OverviewCompositionRoot",
    "OverviewFacade",
    "OverviewSnapshotDTO",
    "PaperSummaryDTO",
    "PortfolioGovernorSummaryDTO",
    "PositionExpansionSummaryDTO",
    "ReportingSummaryDTO",
    "RiskSummaryDTO",
    "SignalsSummaryDTO",
    "StrategySummaryDTO",
    "ValidationSummaryDTO",
    "create_dashboard_app",
    "create_dashboard_router",
    "create_dashboard_runtime",
    "create_default_module_registry",
]

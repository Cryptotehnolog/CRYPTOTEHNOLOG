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
from .dto.positions import OpenPositionsDTO, PositionHistoryDTO
from .dto.reporting import ReportingSummaryDTO
from .dto.risk import RiskSummaryDTO
from .dto.settings import (
    CorrelationPolicySettingsDTO,
    DecisionChainSettingsDTO,
    EventBusPolicySettingsDTO,
    FundingPolicySettingsDTO,
    HealthPolicySettingsDTO,
    LiveFeedPolicySettingsDTO,
    ManualApprovalPolicySettingsDTO,
    ProtectionPolicySettingsDTO,
    ReliabilityPolicySettingsDTO,
    RiskLimitsSettingsDTO,
    SystemStatePolicySettingsDTO,
    SystemStateTimeoutSettingsDTO,
    TrailingPolicySettingsDTO,
    UniversePolicySettingsDTO,
    WorkflowTimeoutsSettingsDTO,
)
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
    "CorrelationPolicySettingsDTO",
    "DashboardModuleDefinition",
    "DashboardModuleStatus",
    "DashboardRuntime",
    "DecisionChainSettingsDTO",
    "EventBusPolicySettingsDTO",
    "ExecutionSummaryDTO",
    "FundingPolicySettingsDTO",
    "HealthPolicySettingsDTO",
    "LiveFeedPolicySettingsDTO",
    "ManualApprovalPolicySettingsDTO",
    "ManagerSummaryDTO",
    "ModuleAvailabilityRegistry",
    "OmsSummaryDTO",
    "OpenPositionsDTO",
    "OrchestrationSummaryDTO",
    "OverviewCompositionRoot",
    "OverviewFacade",
    "OverviewSnapshotDTO",
    "PaperSummaryDTO",
    "PortfolioGovernorSummaryDTO",
    "PositionExpansionSummaryDTO",
    "PositionHistoryDTO",
    "ProtectionPolicySettingsDTO",
    "ReliabilityPolicySettingsDTO",
    "ReportingSummaryDTO",
    "RiskLimitsSettingsDTO",
    "RiskSummaryDTO",
    "SignalsSummaryDTO",
    "StrategySummaryDTO",
    "SystemStatePolicySettingsDTO",
    "SystemStateTimeoutSettingsDTO",
    "TrailingPolicySettingsDTO",
    "UniversePolicySettingsDTO",
    "ValidationSummaryDTO",
    "WorkflowTimeoutsSettingsDTO",
    "create_dashboard_app",
    "create_dashboard_router",
    "create_dashboard_runtime",
    "create_default_module_registry",
]

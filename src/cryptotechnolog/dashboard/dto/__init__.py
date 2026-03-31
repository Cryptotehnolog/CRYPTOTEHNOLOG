"""DTO модели dashboard API."""

from .backtest import BacktestAvailabilityItemDTO, BacktestSummaryDTO
from .execution import ExecutionAvailabilityItemDTO, ExecutionSummaryDTO
from .manager import ManagerAvailabilityItemDTO, ManagerSummaryDTO
from .oms import OmsAvailabilityItemDTO, OmsSummaryDTO
from .opportunity import OpportunityAvailabilityItemDTO, OpportunitySummaryDTO
from .orchestration import OrchestrationAvailabilityItemDTO, OrchestrationSummaryDTO
from .overview import (
    AlertsPlaceholderDTO,
    CircuitBreakerSummaryDTO,
    EventSummaryDTO,
    HealthSummaryDTO,
    ModuleAvailabilityDTO,
    OverviewSnapshotDTO,
    PendingApprovalsSummaryDTO,
    SystemStateSummaryDTO,
)
from .paper import PaperAvailabilityItemDTO, PaperSummaryDTO
from .positions import (
    OpenPositionDTO,
    OpenPositionsDTO,
    PositionHistoryDTO,
    PositionHistoryRecordDTO,
)
from .portfolio_governor import (
    PortfolioGovernorAvailabilityItemDTO,
    PortfolioGovernorSummaryDTO,
)
from .position_expansion import (
    PositionExpansionAvailabilityItemDTO,
    PositionExpansionSummaryDTO,
)
from .reporting import (
    ReportingCatalogCountsDTO,
    ReportingLastArtifactDTO,
    ReportingLastBundleDTO,
    ReportingSummaryDTO,
)
from .risk import RiskConstraintDTO, RiskSummaryDTO
from .signals import SignalAvailabilityItemDTO, SignalsSummaryDTO
from .strategy import StrategyAvailabilityItemDTO, StrategySummaryDTO
from .validation import ValidationAvailabilityItemDTO, ValidationSummaryDTO

__all__ = [
    "AlertsPlaceholderDTO",
    "BacktestAvailabilityItemDTO",
    "BacktestSummaryDTO",
    "CircuitBreakerSummaryDTO",
    "EventSummaryDTO",
    "ExecutionAvailabilityItemDTO",
    "ExecutionSummaryDTO",
    "HealthSummaryDTO",
    "ManagerAvailabilityItemDTO",
    "ManagerSummaryDTO",
    "ModuleAvailabilityDTO",
    "OmsAvailabilityItemDTO",
    "OmsSummaryDTO",
    "OpenPositionDTO",
    "OpenPositionsDTO",
    "PositionHistoryDTO",
    "PositionHistoryRecordDTO",
    "OpportunityAvailabilityItemDTO",
    "OpportunitySummaryDTO",
    "OrchestrationAvailabilityItemDTO",
    "OrchestrationSummaryDTO",
    "OverviewSnapshotDTO",
    "PaperAvailabilityItemDTO",
    "PaperSummaryDTO",
    "PendingApprovalsSummaryDTO",
    "PortfolioGovernorAvailabilityItemDTO",
    "PortfolioGovernorSummaryDTO",
    "PositionExpansionAvailabilityItemDTO",
    "PositionExpansionSummaryDTO",
    "ReportingCatalogCountsDTO",
    "ReportingLastArtifactDTO",
    "ReportingLastBundleDTO",
    "ReportingSummaryDTO",
    "RiskConstraintDTO",
    "RiskSummaryDTO",
    "SignalAvailabilityItemDTO",
    "SignalsSummaryDTO",
    "StrategyAvailabilityItemDTO",
    "StrategySummaryDTO",
    "SystemStateSummaryDTO",
    "ValidationAvailabilityItemDTO",
    "ValidationSummaryDTO",
]

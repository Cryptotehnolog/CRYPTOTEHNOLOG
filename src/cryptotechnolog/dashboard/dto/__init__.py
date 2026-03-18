"""DTO модели dashboard API."""

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

__all__ = [
    "AlertsPlaceholderDTO",
    "CircuitBreakerSummaryDTO",
    "EventSummaryDTO",
    "HealthSummaryDTO",
    "ModuleAvailabilityDTO",
    "OverviewSnapshotDTO",
    "PendingApprovalsSummaryDTO",
    "SystemStateSummaryDTO",
]

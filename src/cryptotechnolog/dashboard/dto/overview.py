"""DTO модели для overview snapshot панели."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AlertsPlaceholderDTO(BaseModel):
    """Явное место под будущий alert-layer без фиктивных данных."""

    connected: bool = False
    note: str = "Отдельный alert-layer ещё не подключён"


class SystemStateSummaryDTO(BaseModel):
    """Сводка по системному состоянию."""

    is_running: bool
    is_shutting_down: bool
    current_state: str
    startup_phase: str
    shutdown_phase: str
    uptime_seconds: int
    trade_allowed: bool
    last_error: str | None = None


class HealthSummaryDTO(BaseModel):
    """Сводка по здоровью системы."""

    overall_status: str
    component_count: int
    unhealthy_components: list[str] = Field(default_factory=list)
    timestamp: float | None = None


class PendingApprovalsSummaryDTO(BaseModel):
    """Сводка по pending approvals."""

    pending_count: int
    total_requests: int
    request_timeout_minutes: int


class EventSummaryDTO(BaseModel):
    """Сводка по event bus без подмены полноценного event history."""

    total_published: int
    total_delivered: int
    total_dropped: int
    total_rate_limited: int
    subscriber_count: int
    persistence_enabled: bool
    backpressure_strategy: str


class CircuitBreakerSummaryDTO(BaseModel):
    """Сводка по circuit breaker."""

    name: str
    state: str
    failure_count: int
    success_count: int
    failure_threshold: int
    recovery_timeout: int


class ModuleAvailabilityDTO(BaseModel):
    """Стабильное представление доступности dashboard-модуля."""

    key: str
    title: str
    description: str
    route: str
    status: str
    phase: str
    status_reason: str | None = None


class OverviewSnapshotDTO(BaseModel):
    """Полный read-only snapshot overview панели."""

    system_state: SystemStateSummaryDTO
    health_summary: HealthSummaryDTO
    pending_approvals: PendingApprovalsSummaryDTO
    event_summary: EventSummaryDTO
    circuit_breaker_summary: list[CircuitBreakerSummaryDTO] = Field(default_factory=list)
    module_availability: list[ModuleAvailabilityDTO] = Field(default_factory=list)
    alerts_summary: AlertsPlaceholderDTO = Field(default_factory=AlertsPlaceholderDTO)

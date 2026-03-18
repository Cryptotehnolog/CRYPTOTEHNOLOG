"""Overview facade для read-only dashboard snapshot."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cryptotechnolog.config import get_logger
from cryptotechnolog.core.health import ComponentHealth, HealthStatus, SystemHealth

from ..dto.overview import (
    CircuitBreakerSummaryDTO,
    EventSummaryDTO,
    HealthSummaryDTO,
    ModuleAvailabilityDTO,
    OverviewSnapshotDTO,
    PendingApprovalsSummaryDTO,
    SystemStateSummaryDTO,
)

if TYPE_CHECKING:
    from .composition import OverviewCompositionRoot

from .sources import parse_circuit_breaker_snapshots

logger = get_logger(__name__)


class OverviewFacade:
    """Facade для агрегации overview snapshot панели."""

    def __init__(self, composition_root: OverviewCompositionRoot) -> None:
        self._composition_root = composition_root

    async def get_overview_snapshot(self) -> OverviewSnapshotDTO:
        """Получить полный overview snapshot."""
        system_status = await self._composition_root.system_status_source.get_system_status()
        health = await self._get_health_snapshot(system_status.components)
        approvals = await self._composition_root.pending_approvals_source.get_pending_approvals_summary()
        event_summary = await self._composition_root.event_summary_source.get_event_summary()
        module_availability = (
            await self._composition_root.module_availability_source.get_module_availability()
        )
        circuit_breakers = parse_circuit_breaker_snapshots(system_status.circuit_breakers)

        return OverviewSnapshotDTO(
            system_state=SystemStateSummaryDTO(
                is_running=system_status.is_running,
                is_shutting_down=system_status.is_shutting_down,
                current_state=system_status.current_state.value,
                startup_phase=system_status.startup_phase.value,
                shutdown_phase=system_status.shutdown_phase.value,
                uptime_seconds=system_status.uptime_seconds,
                trade_allowed=system_status.current_state.is_trading_allowed,
                last_error=system_status.last_error,
            ),
            health_summary=HealthSummaryDTO(
                overall_status=health.overall_status.value,
                component_count=len(health.components),
                unhealthy_components=health.get_unhealthy_components(),
                timestamp=health.timestamp,
            ),
            pending_approvals=PendingApprovalsSummaryDTO(
                pending_count=approvals.pending_count,
                total_requests=approvals.total_requests,
                request_timeout_minutes=approvals.request_timeout_minutes,
            ),
            event_summary=EventSummaryDTO(
                total_published=event_summary.total_published,
                total_delivered=event_summary.total_delivered,
                total_dropped=event_summary.total_dropped,
                total_rate_limited=event_summary.total_rate_limited,
                subscriber_count=event_summary.subscriber_count,
                persistence_enabled=event_summary.persistence_enabled,
                backpressure_strategy=event_summary.backpressure_strategy,
            ),
            circuit_breaker_summary=[
                CircuitBreakerSummaryDTO(
                    name=item.name,
                    state=item.state,
                    failure_count=item.failure_count,
                    success_count=item.success_count,
                    failure_threshold=item.failure_threshold,
                    recovery_timeout=item.recovery_timeout,
                )
                for item in circuit_breakers
            ],
            module_availability=[
                ModuleAvailabilityDTO(
                    key=module.key,
                    title=module.title,
                    description=module.description,
                    route=module.route,
                    status=module.status.value,
                    phase=module.phase,
                    status_reason=module.status_reason,
                )
                for module in module_availability
            ],
        )

    async def _get_health_snapshot(
        self,
        components: dict[str, ComponentHealth],
    ) -> SystemHealth:
        source = self._composition_root.health_snapshot_source
        if source is not None:
            health = await source.get_health_snapshot()
            if health is not None:
                return health

        return self._build_health_from_components(components)

    def _build_health_from_components(
        self,
        components: dict[str, ComponentHealth],
    ) -> SystemHealth:
        if not components:
            overall_status = HealthStatus.UNKNOWN
        else:
            statuses = {item.status for item in components.values()}
            if HealthStatus.UNHEALTHY in statuses:
                overall_status = HealthStatus.UNHEALTHY
            elif HealthStatus.DEGRADED in statuses or HealthStatus.UNKNOWN in statuses:
                overall_status = HealthStatus.DEGRADED
            else:
                overall_status = HealthStatus.HEALTHY

        logger.debug(
            "Построен fallback health snapshot для overview",
            components=len(components),
            overall_status=overall_status.value,
        )
        return SystemHealth(overall_status=overall_status, components=components)

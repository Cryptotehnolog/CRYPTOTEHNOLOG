from __future__ import annotations

from dataclasses import dataclass

import pytest

from cryptotechnolog.core.health import ComponentHealth, HealthStatus, SystemHealth
from cryptotechnolog.core.state_machine_enums import SystemState
from cryptotechnolog.core.system_controller import ShutdownPhase, StartupPhase, SystemStatus
from cryptotechnolog.dashboard.facade.composition import OverviewCompositionRoot
from cryptotechnolog.dashboard.facade.contracts import (
    EventSummarySnapshot,
    PendingApprovalsSnapshot,
)
from cryptotechnolog.dashboard.facade.overview_facade import OverviewFacade
from cryptotechnolog.dashboard.registry import create_default_module_registry


class _SystemStatusSource:
    async def get_system_status(self) -> SystemStatus:
        return SystemStatus(
            is_running=True,
            is_shutting_down=False,
            current_state=SystemState.READY,
            startup_phase=StartupPhase.READY,
            shutdown_phase=ShutdownPhase.NOT_SHUTTING_DOWN,
            uptime_seconds=42,
            components={
                "redis": ComponentHealth(component="redis", status=HealthStatus.HEALTHY),
                "postgresql": ComponentHealth(
                    component="postgresql",
                    status=HealthStatus.UNHEALTHY,
                    message="DB timeout",
                ),
            },
            circuit_breakers={
                "redis": {
                    "state": "closed",
                    "failure_count": 1,
                    "success_count": 2,
                    "failure_threshold": 5,
                    "recovery_timeout": 60,
                }
            },
            last_error="DB timeout",
        )


class _HealthSource:
    async def get_health_snapshot(self) -> SystemHealth:
        return SystemHealth(
            overall_status=HealthStatus.UNHEALTHY,
            components={
                "postgresql": ComponentHealth(
                    component="postgresql",
                    status=HealthStatus.UNHEALTHY,
                    message="DB timeout",
                )
            },
        )


class _ApprovalsSource:
    async def get_pending_approvals_summary(self) -> PendingApprovalsSnapshot:
        return PendingApprovalsSnapshot(
            pending_count=3,
            total_requests=9,
            request_timeout_minutes=5,
        )


class _EventSource:
    async def get_event_summary(self) -> EventSummarySnapshot:
        return EventSummarySnapshot(
            total_published=100,
            total_delivered=95,
            total_dropped=2,
            total_rate_limited=3,
            subscriber_count=4,
            persistence_enabled=True,
            backpressure_strategy="drop_low",
        )


@dataclass
class _ModuleSource:
    registry: object

    async def get_module_availability(self):
        return self.registry.list_modules()


@pytest.mark.asyncio
async def test_overview_facade_aggregates_snapshot() -> None:
    registry = create_default_module_registry()
    facade = OverviewFacade(
        OverviewCompositionRoot(
            system_status_source=_SystemStatusSource(),
            health_snapshot_source=_HealthSource(),
            pending_approvals_source=_ApprovalsSource(),
            event_summary_source=_EventSource(),
            module_availability_source=_ModuleSource(registry=registry),
        )
    )

    snapshot = await facade.get_overview_snapshot()

    assert snapshot.system_state.current_state == "ready"
    assert snapshot.health_summary.overall_status == "unhealthy"
    assert snapshot.pending_approvals.pending_count == 3
    assert snapshot.event_summary.total_published == 100
    assert snapshot.circuit_breaker_summary[0].name == "redis"
    assert any(module.key == "overview" for module in snapshot.module_availability)


@pytest.mark.asyncio
async def test_overview_facade_builds_fallback_health_when_source_absent() -> None:
    registry = create_default_module_registry()
    facade = OverviewFacade(
        OverviewCompositionRoot(
            system_status_source=_SystemStatusSource(),
            health_snapshot_source=None,
            pending_approvals_source=_ApprovalsSource(),
            event_summary_source=_EventSource(),
            module_availability_source=_ModuleSource(registry=registry),
        )
    )

    snapshot = await facade.get_overview_snapshot()

    assert snapshot.health_summary.overall_status == "unhealthy"
    assert "postgresql" in snapshot.health_summary.unhealthy_components

"""Source/provider abstractions для overview facade."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from .contracts import CircuitBreakerSnapshot, EventSummarySnapshot, PendingApprovalsSnapshot

if TYPE_CHECKING:
    from cryptotechnolog.core.health import HealthChecker, SystemHealth
    from cryptotechnolog.core.operator_gate import OperatorGate
    from cryptotechnolog.core.system_controller import SystemController, SystemStatus

    from ..registry.module_registry import ModuleAvailabilityRecord, ModuleAvailabilityRegistry


class SystemStatusSource(Protocol):
    """Источник системного статуса."""

    async def get_system_status(self) -> SystemStatus: ...


class HealthSnapshotSource(Protocol):
    """Источник health snapshot."""

    async def get_health_snapshot(self) -> SystemHealth | None: ...


class PendingApprovalsSource(Protocol):
    """Источник pending approvals summary."""

    async def get_pending_approvals_summary(self) -> PendingApprovalsSnapshot: ...


class EventSummarySource(Protocol):
    """Источник event summary."""

    async def get_event_summary(self) -> EventSummarySnapshot: ...


class ModuleAvailabilitySource(Protocol):
    """Источник snapshot доступности модулей панели."""

    async def get_module_availability(self) -> list[ModuleAvailabilityRecord]: ...


def parse_circuit_breaker_snapshots(
    raw_snapshots: dict[str, dict[str, Any]],
) -> list[CircuitBreakerSnapshot]:
    """Преобразовать внутренние dict snapshots circuit breakers в typed contracts."""
    return [
        CircuitBreakerSnapshot(
            name=name,
            state=str(data.get("state", "unknown")),
            failure_count=int(data.get("failure_count", 0)),
            success_count=int(data.get("success_count", 0)),
            failure_threshold=int(data.get("failure_threshold", 0)),
            recovery_timeout=int(data.get("recovery_timeout", 0)),
        )
        for name, data in sorted(raw_snapshots.items())
    ]


@dataclass(slots=True)
class ControllerSystemStatusSource:
    """Адаптер SystemController для facade."""

    controller: SystemController

    async def get_system_status(self) -> SystemStatus:
        return await self.controller.get_status()


@dataclass(slots=True)
class HealthCheckerSource:
    """Адаптер HealthChecker для facade."""

    checker: HealthChecker
    prefer_cached: bool = True

    async def get_health_snapshot(self) -> SystemHealth | None:
        if self.prefer_cached:
            cached = self.checker.get_last_health()
            if cached is not None:
                return cached
        return await self.checker.check_system()


@dataclass(slots=True)
class OperatorGateSummarySource:
    """Адаптер OperatorGate для summary approvals."""

    gate: OperatorGate

    async def get_pending_approvals_summary(self) -> PendingApprovalsSnapshot:
        stats = self.gate.get_stats()
        return PendingApprovalsSnapshot(
            pending_count=len(self.gate.get_pending_requests()),
            total_requests=int(stats.get("total_requests", 0)),
            request_timeout_minutes=int(stats.get("request_timeout", 0)),
        )


@dataclass(slots=True)
class EventBusSummarySource:
    """Адаптер event bus metrics для summary events."""

    event_bus: Any

    async def get_event_summary(self) -> EventSummarySnapshot:
        metrics = self.event_bus.get_metrics()
        bus_metrics = metrics.get("bus_metrics", {})
        return EventSummarySnapshot(
            total_published=int(bus_metrics.get("published", 0)),
            total_delivered=int(bus_metrics.get("delivered", 0)),
            total_dropped=int(bus_metrics.get("dropped", 0)),
            total_rate_limited=int(bus_metrics.get("rate_limited", 0)),
            subscriber_count=int(metrics.get("subscriber_count", 0)),
            persistence_enabled=bool(metrics.get("enable_persistence", False)),
            backpressure_strategy=str(metrics.get("backpressure_strategy", "unknown")),
        )


@dataclass(slots=True)
class ModuleRegistrySource:
    """Адаптер системного module registry."""

    registry: ModuleAvailabilityRegistry

    async def get_module_availability(self) -> list[ModuleAvailabilityRecord]:
        return self.registry.list_modules()

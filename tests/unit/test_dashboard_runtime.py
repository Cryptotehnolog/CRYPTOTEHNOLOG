from __future__ import annotations

from unittest.mock import AsyncMock, Mock

from fastapi import FastAPI

from cryptotechnolog.dashboard.app import create_dashboard_app
from cryptotechnolog.dashboard.dto.overview import (
    EventSummaryDTO,
    HealthSummaryDTO,
    OverviewSnapshotDTO,
    PendingApprovalsSummaryDTO,
    SystemStateSummaryDTO,
)


class _StubRuntime:
    def __init__(self) -> None:
        self.start = AsyncMock()
        self.stop = AsyncMock()
        self.overview_facade = Mock()
        self.overview_facade.get_overview_snapshot = AsyncMock(
            return_value=OverviewSnapshotDTO(
                system_state=SystemStateSummaryDTO(
                    is_running=False,
                    is_shutting_down=False,
                    current_state="boot",
                    startup_phase="not_started",
                    shutdown_phase="not_shutting_down",
                    uptime_seconds=0,
                    trade_allowed=False,
                ),
                health_summary=HealthSummaryDTO(
                    overall_status="unknown",
                    component_count=0,
                    unhealthy_components=[],
                    timestamp=None,
                ),
                pending_approvals=PendingApprovalsSummaryDTO(
                    pending_count=0,
                    total_requests=0,
                    request_timeout_minutes=5,
                ),
                event_summary=EventSummaryDTO(
                    total_published=0,
                    total_delivered=0,
                    total_dropped=0,
                    total_rate_limited=0,
                    subscriber_count=0,
                    persistence_enabled=False,
                    backpressure_strategy="drop_low",
                ),
            )
        )


def test_create_dashboard_app_registers_runtime_and_router() -> None:
    runtime = _StubRuntime()

    app = create_dashboard_app(runtime=runtime)

    assert isinstance(app, FastAPI)
    assert app.state.dashboard_runtime is runtime
    routes = {route.path for route in app.routes}
    assert "/dashboard/overview" in routes

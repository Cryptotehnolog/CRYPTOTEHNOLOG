from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from cryptotechnolog.dashboard.api import create_dashboard_router
from cryptotechnolog.dashboard.dto.overview import (
    EventSummaryDTO,
    HealthSummaryDTO,
    OverviewSnapshotDTO,
    PendingApprovalsSummaryDTO,
    SystemStateSummaryDTO,
)


class _StubFacade:
    async def get_overview_snapshot(self) -> OverviewSnapshotDTO:
        return OverviewSnapshotDTO(
            system_state=SystemStateSummaryDTO(
                is_running=True,
                is_shutting_down=False,
                current_state="ready",
                startup_phase="ready",
                shutdown_phase="not_shutting_down",
                uptime_seconds=7,
                trade_allowed=False,
            ),
            health_summary=HealthSummaryDTO(
                overall_status="healthy",
                component_count=2,
                unhealthy_components=[],
                timestamp=123.0,
            ),
            pending_approvals=PendingApprovalsSummaryDTO(
                pending_count=0,
                total_requests=1,
                request_timeout_minutes=5,
            ),
            event_summary=EventSummaryDTO(
                total_published=10,
                total_delivered=9,
                total_dropped=1,
                total_rate_limited=0,
                subscriber_count=2,
                persistence_enabled=True,
                backpressure_strategy="drop_low",
            ),
        )


def test_dashboard_overview_endpoint_returns_snapshot() -> None:
    app = FastAPI()
    app.include_router(create_dashboard_router(_StubFacade()))

    client = TestClient(app)
    response = client.get("/dashboard/overview")

    assert response.status_code == 200
    data = response.json()
    assert data["system_state"]["current_state"] == "ready"
    assert data["event_summary"]["total_published"] == 10
    assert data["alerts_summary"]["connected"] is False

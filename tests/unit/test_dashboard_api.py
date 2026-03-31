from __future__ import annotations

from typing import TYPE_CHECKING, cast

from fastapi import FastAPI
from fastapi.testclient import TestClient

from cryptotechnolog.dashboard.api import create_dashboard_router
from cryptotechnolog.dashboard.app import create_dashboard_app
from cryptotechnolog.dashboard.dto.backtest import (
    BacktestAvailabilityItemDTO,
    BacktestSummaryDTO,
)
from cryptotechnolog.dashboard.dto.execution import (
    ExecutionAvailabilityItemDTO,
    ExecutionSummaryDTO,
)
from cryptotechnolog.dashboard.dto.manager import (
    ManagerAvailabilityItemDTO,
    ManagerSummaryDTO,
)
from cryptotechnolog.dashboard.dto.oms import OmsAvailabilityItemDTO, OmsSummaryDTO
from cryptotechnolog.dashboard.dto.opportunity import (
    OpportunityAvailabilityItemDTO,
    OpportunitySummaryDTO,
)
from cryptotechnolog.dashboard.dto.orchestration import (
    OrchestrationAvailabilityItemDTO,
    OrchestrationSummaryDTO,
)
from cryptotechnolog.dashboard.dto.overview import (
    EventSummaryDTO,
    HealthSummaryDTO,
    OverviewSnapshotDTO,
    PendingApprovalsSummaryDTO,
    SystemStateSummaryDTO,
)
from cryptotechnolog.dashboard.dto.paper import PaperAvailabilityItemDTO, PaperSummaryDTO
from cryptotechnolog.dashboard.dto.portfolio_governor import (
    PortfolioGovernorAvailabilityItemDTO,
    PortfolioGovernorSummaryDTO,
)
from cryptotechnolog.dashboard.dto.position_expansion import (
    PositionExpansionAvailabilityItemDTO,
    PositionExpansionSummaryDTO,
)
from cryptotechnolog.dashboard.dto.positions import (
    OpenPositionDTO,
    OpenPositionsDTO,
    PositionHistoryDTO,
    PositionHistoryRecordDTO,
)
from cryptotechnolog.dashboard.dto.reporting import (
    ReportingCatalogCountsDTO,
    ReportingLastArtifactDTO,
    ReportingSummaryDTO,
)
from cryptotechnolog.dashboard.dto.risk import RiskConstraintDTO, RiskSummaryDTO
from cryptotechnolog.dashboard.dto.signals import SignalAvailabilityItemDTO, SignalsSummaryDTO
from cryptotechnolog.dashboard.dto.strategy import (
    StrategyAvailabilityItemDTO,
    StrategySummaryDTO,
)
from cryptotechnolog.dashboard.dto.validation import (
    ValidationAvailabilityItemDTO,
    ValidationSummaryDTO,
)

if TYPE_CHECKING:
    from cryptotechnolog.dashboard.facade.overview_facade import OverviewFacade


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

    async def get_risk_summary(self) -> RiskSummaryDTO:
        return RiskSummaryDTO(
            module_status="read-only",
            current_state="ready",
            global_status="limited",
            limiting_state="risk-limited",
            trading_blocked=False,
            active_risk_path="phase5_risk_engine",
            state_note="Система готова к торговле, ожидает сигнала оператора",
            summary_reason=None,
            constraints=[
                RiskConstraintDTO(
                    key="max_r_per_trade",
                    label="Макс. R на сделку",
                    value="1.00 R",
                    status="limited",
                    note="Глобальный settings-based лимит.",
                )
            ],
        )

    async def get_signals_summary(self) -> SignalsSummaryDTO:
        return SignalsSummaryDTO(
            module_status="read-only",
            global_status="warming",
            lifecycle_state="warming",
            started=True,
            ready=False,
            tracked_signal_keys=0,
            active_signal_keys=0,
            last_signal_id=None,
            last_event_type=None,
            last_context_at=None,
            active_signal_path="phase8_signal_contour",
            freshness_state="not_surfaced",
            summary_note="Signal runtime surfaced readiness reasons: no_signal_context_processed",
            summary_reason=None,
            availability=[
                SignalAvailabilityItemDTO(
                    key="runtime_ready",
                    label="Readiness",
                    value="not ready",
                    status="warning",
                    note="Readiness отражает только surfaced diagnostics signal runtime.",
                )
            ],
        )

    async def get_strategy_summary(self) -> StrategySummaryDTO:
        return StrategySummaryDTO(
            module_status="read-only",
            global_status="warming",
            lifecycle_state="warming",
            started=True,
            ready=False,
            tracked_context_keys=0,
            tracked_candidate_keys=0,
            actionable_candidate_keys=0,
            last_signal_id=None,
            last_candidate_id=None,
            last_event_type=None,
            active_strategy_path="phase9_strategy_contour",
            strategy_source="phase9_foundation_strategy",
            freshness_state="not_surfaced",
            summary_note="Strategy runtime surfaced readiness reasons: no_strategy_context_processed",
            summary_reason=None,
            availability=[
                StrategyAvailabilityItemDTO(
                    key="runtime_ready",
                    label="Readiness",
                    value="not ready",
                    status="warning",
                    note="Readiness отражает только surfaced diagnostics strategy runtime.",
                )
            ],
        )

    async def get_execution_summary(self) -> ExecutionSummaryDTO:
        return ExecutionSummaryDTO(
            module_status="read-only",
            global_status="warming",
            lifecycle_state="warming",
            started=True,
            ready=False,
            tracked_context_keys=0,
            tracked_intent_keys=0,
            executable_intent_keys=0,
            last_candidate_id=None,
            last_intent_id=None,
            last_event_type=None,
            active_execution_path="phase10_execution_contour",
            execution_source="phase10_foundation_execution",
            freshness_state="not_surfaced",
            summary_note="Execution runtime surfaced readiness reasons: no_execution_context_processed",
            summary_reason=None,
            availability=[
                ExecutionAvailabilityItemDTO(
                    key="runtime_ready",
                    label="Readiness",
                    value="not ready",
                    status="warning",
                    note="Readiness отражает только surfaced diagnostics execution runtime.",
                )
            ],
        )

    async def get_opportunity_summary(self) -> OpportunitySummaryDTO:
        return OpportunitySummaryDTO(
            module_status="read-only",
            global_status="warming",
            lifecycle_state="warming",
            started=True,
            ready=False,
            tracked_context_keys=0,
            tracked_selection_keys=0,
            selected_keys=0,
            last_intent_id=None,
            last_selection_id=None,
            last_event_type=None,
            active_opportunity_path="phase11_opportunity_contour",
            opportunity_source="phase11_foundation_selection",
            freshness_state="not_surfaced",
            summary_note="Opportunity runtime surfaced readiness reasons: no_selection_context_processed",
            summary_reason=None,
            availability=[
                OpportunityAvailabilityItemDTO(
                    key="runtime_ready",
                    label="Readiness",
                    value="not ready",
                    status="warning",
                    note="Readiness отражает только surfaced diagnostics opportunity runtime.",
                )
            ],
        )

    async def get_orchestration_summary(self) -> OrchestrationSummaryDTO:
        return OrchestrationSummaryDTO(
            module_status="read-only",
            global_status="warming",
            lifecycle_state="warming",
            started=True,
            ready=False,
            tracked_context_keys=0,
            tracked_decision_keys=0,
            forwarded_keys=0,
            abstained_keys=0,
            invalidated_decision_keys=0,
            expired_decision_keys=0,
            last_selection_id=None,
            last_decision_id=None,
            last_event_type=None,
            active_orchestration_path="phase12_orchestration_contour",
            orchestration_source="phase12_meta_orchestration",
            freshness_state="not_surfaced",
            summary_note="Orchestration runtime surfaced readiness reasons: no_orchestration_context_processed",
            summary_reason=None,
            availability=[
                OrchestrationAvailabilityItemDTO(
                    key="runtime_ready",
                    label="Readiness",
                    value="not ready",
                    status="warning",
                    note="Readiness отражает только surfaced diagnostics orchestration runtime.",
                )
            ],
        )

    async def get_position_expansion_summary(self) -> PositionExpansionSummaryDTO:
        return PositionExpansionSummaryDTO(
            module_status="read-only",
            global_status="warming",
            lifecycle_state="warming",
            started=True,
            ready=False,
            tracked_context_keys=0,
            tracked_expansion_keys=0,
            expandable_keys=0,
            abstained_keys=0,
            rejected_keys=0,
            invalidated_expansion_keys=0,
            expired_expansion_keys=0,
            last_decision_id=None,
            last_expansion_id=None,
            last_event_type=None,
            active_position_expansion_path="phase13_position_expansion_contour",
            position_expansion_source="phase13_position_expansion",
            freshness_state="not_surfaced",
            summary_note="Position expansion runtime surfaced readiness reasons: no_position_expansion_context_processed",
            summary_reason=None,
            availability=[
                PositionExpansionAvailabilityItemDTO(
                    key="runtime_ready",
                    label="Readiness",
                    value="not ready",
                    status="warning",
                    note="Readiness отражает только surfaced diagnostics position-expansion runtime.",
                )
            ],
        )

    async def get_portfolio_governor_summary(self) -> PortfolioGovernorSummaryDTO:
        return PortfolioGovernorSummaryDTO(
            module_status="read-only",
            global_status="warming",
            lifecycle_state="warming",
            started=True,
            ready=False,
            tracked_context_keys=0,
            tracked_governor_keys=0,
            approved_keys=0,
            abstained_keys=0,
            rejected_keys=0,
            invalidated_governor_keys=0,
            expired_governor_keys=0,
            last_expansion_id=None,
            last_governor_id=None,
            last_event_type=None,
            active_portfolio_governor_path="phase14_portfolio_governor_contour",
            portfolio_governor_source="phase14_portfolio_governor",
            freshness_state="not_surfaced",
            summary_note=(
                "Portfolio governor runtime surfaced readiness reasons: "
                "no_portfolio_governor_context_processed"
            ),
            summary_reason=None,
            availability=[
                PortfolioGovernorAvailabilityItemDTO(
                    key="runtime_ready",
                    label="Readiness",
                    value="not ready",
                    status="warning",
                    note="Readiness отражает только surfaced diagnostics portfolio governor runtime.",
                )
            ],
        )

    async def get_oms_summary(self) -> OmsSummaryDTO:
        return OmsSummaryDTO(
            module_status="read-only",
            global_status="warming",
            lifecycle_state="warming",
            started=True,
            ready=False,
            tracked_contexts=0,
            tracked_active_orders=0,
            tracked_historical_orders=0,
            last_intent_id=None,
            last_order_id=None,
            last_event_type=None,
            active_oms_path="phase16_oms_contour",
            oms_source="phase16_oms",
            freshness_state="not_surfaced",
            summary_note="OMS runtime surfaced readiness reasons: no_execution_intent_processed",
            summary_reason=None,
            availability=[
                OmsAvailabilityItemDTO(
                    key="runtime_ready",
                    label="Readiness",
                    value="not ready",
                    status="warning",
                    note="Readiness отражает только surfaced diagnostics OMS runtime.",
                )
            ],
        )

    async def get_manager_summary(self) -> ManagerSummaryDTO:
        return ManagerSummaryDTO(
            module_status="read-only",
            global_status="warming",
            lifecycle_state="warming",
            started=True,
            ready=False,
            tracked_contexts=0,
            tracked_active_workflows=0,
            tracked_historical_workflows=0,
            last_workflow_id=None,
            last_event_type=None,
            active_manager_path="phase17_manager_contour",
            manager_source="phase17_manager",
            freshness_state="not_surfaced",
            summary_note="Manager runtime surfaced readiness reasons: no_manager_workflow_processed",
            summary_reason=None,
            availability=[
                ManagerAvailabilityItemDTO(
                    key="runtime_ready",
                    label="Readiness",
                    value="not ready",
                    status="warning",
                    note="Readiness отражает только surfaced diagnostics manager runtime.",
                )
            ],
        )

    async def get_validation_summary(self) -> ValidationSummaryDTO:
        return ValidationSummaryDTO(
            module_status="read-only",
            global_status="warming",
            lifecycle_state="warming",
            started=True,
            ready=False,
            tracked_contexts=0,
            tracked_active_reviews=0,
            tracked_historical_reviews=0,
            last_review_id=None,
            last_event_type=None,
            active_validation_path="phase18_validation_contour",
            validation_source="phase18_validation",
            freshness_state="not_surfaced",
            summary_note="Validation runtime surfaced readiness reasons: no_validation_review_processed",
            summary_reason=None,
            availability=[
                ValidationAvailabilityItemDTO(
                    key="runtime_ready",
                    label="Readiness",
                    value="not ready",
                    status="warning",
                    note="Readiness отражает только surfaced diagnostics validation runtime.",
                )
            ],
        )

    async def get_paper_summary(self) -> PaperSummaryDTO:
        return PaperSummaryDTO(
            module_status="read-only",
            global_status="warming",
            lifecycle_state="warming",
            started=True,
            ready=False,
            tracked_contexts=0,
            tracked_active_rehearsals=0,
            tracked_historical_rehearsals=0,
            last_rehearsal_id=None,
            last_event_type=None,
            active_paper_path="phase19_paper_contour",
            paper_source="phase19_paper",
            freshness_state="not_surfaced",
            summary_note="Paper runtime surfaced readiness reasons: no_paper_rehearsal_processed",
            summary_reason=None,
            availability=[
                PaperAvailabilityItemDTO(
                    key="runtime_ready",
                    label="Readiness",
                    value="not ready",
                    status="warning",
                    note="Readiness отражает только surfaced diagnostics paper runtime.",
                )
            ],
        )

    async def get_backtest_summary(self) -> BacktestSummaryDTO:
        return BacktestSummaryDTO(
            module_status="read-only",
            global_status="warming",
            lifecycle_state="warming",
            started=True,
            ready=False,
            tracked_inputs=0,
            tracked_contexts=0,
            tracked_active_replays=0,
            tracked_historical_replays=0,
            last_replay_id=None,
            last_event_type=None,
            active_backtest_path="phase20_replay_contour",
            backtest_source="phase20_backtest",
            freshness_state="not_surfaced",
            summary_note="Backtest runtime surfaced readiness reasons: no_replay_processed",
            summary_reason=None,
            availability=[
                BacktestAvailabilityItemDTO(
                    key="runtime_ready",
                    label="Readiness",
                    value="not ready",
                    status="warning",
                    note="Readiness отражает только surfaced diagnostics backtest runtime.",
                )
            ],
        )

    async def get_reporting_summary(self) -> ReportingSummaryDTO:
        return ReportingSummaryDTO(
            module_status="read-only",
            global_status="warming",
            catalog_counts=ReportingCatalogCountsDTO(
                total_artifacts=1,
                total_bundles=0,
                validation_artifacts=1,
                paper_artifacts=0,
                replay_artifacts=0,
            ),
            last_artifact_snapshot=ReportingLastArtifactDTO(
                kind="validation_report",
                status="warming",
                source_layer="validation",
                generated_at="2026-03-25T10:00:00+00:00",
            ),
            last_bundle_snapshot=None,
            summary_note=(
                "Каталог reporting artifacts уже вывел отдельные artifacts по слоям "
                "validation, но bundle truth ещё не surfaced."
            ),
            summary_reason="review_warming",
        )

    async def get_open_positions(self) -> OpenPositionsDTO:
        return OpenPositionsDTO(
            positions=[
                OpenPositionDTO(
                    position_id="pos-1",
                    symbol="BTC/USDT",
                    exchange="okx",
                    strategy="breakout-trend",
                    side="long",
                    entry_price="62500",
                    quantity="0.15",
                    initial_stop="61000",
                    current_stop="61850",
                    current_risk_usd="97.50",
                    current_risk_r="0.65",
                    current_price="63125",
                    unrealized_pnl_usd="93.75",
                    unrealized_pnl_percent="1.00",
                    trailing_state="armed",
                    opened_at="2026-03-26T10:00:00+00:00",
                    updated_at="2026-03-26T12:15:00+00:00",
                )
            ]
        )

    async def get_position_history(self) -> PositionHistoryDTO:
        return PositionHistoryDTO(
            positions=[
                PositionHistoryRecordDTO(
                    position_id="closed-1",
                    symbol="ETH/USDT",
                    exchange="bybit",
                    strategy="mean-reversion-short",
                    side="short",
                    entry_price="3200",
                    quantity="1.25",
                    initial_stop="3340",
                    current_stop="3260",
                    trailing_state="locked",
                    opened_at="2026-03-20T08:00:00+00:00",
                    closed_at="2026-03-21T15:30:00+00:00",
                    realized_pnl_r="1.80",
                    realized_pnl_usd="72.50",
                    realized_pnl_percent="1.81",
                )
            ]
        )


def test_dashboard_overview_endpoint_returns_snapshot() -> None:
    app = FastAPI()
    app.include_router(create_dashboard_router(cast("OverviewFacade", _StubFacade())))

    client = TestClient(app)
    response = client.get("/dashboard/overview")

    assert response.status_code == 200
    data = response.json()
    assert data["system_state"]["current_state"] == "ready"
    assert data["event_summary"]["total_published"] == 10
    assert data["alerts_summary"]["connected"] is False


def test_dashboard_app_allows_local_cors_preflight() -> None:
    app = create_dashboard_app()

    with TestClient(app) as client:
        response = client.options(
            "/dashboard/overview",
            headers={
                "Origin": "http://127.0.0.1:5173",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"


def test_dashboard_risk_summary_endpoint_returns_snapshot() -> None:
    app = FastAPI()
    app.include_router(create_dashboard_router(cast("OverviewFacade", _StubFacade())))

    client = TestClient(app)
    response = client.get("/dashboard/risk-summary")

    assert response.status_code == 200
    data = response.json()
    assert data["module_status"] == "read-only"
    assert data["global_status"] == "limited"
    assert data["constraints"][0]["key"] == "max_r_per_trade"


def test_dashboard_signals_summary_endpoint_returns_snapshot() -> None:
    app = FastAPI()
    app.include_router(create_dashboard_router(cast("OverviewFacade", _StubFacade())))

    client = TestClient(app)
    response = client.get("/dashboard/signals-summary")

    assert response.status_code == 200
    data = response.json()
    assert data["module_status"] == "read-only"
    assert data["global_status"] == "warming"
    assert data["availability"][0]["key"] == "runtime_ready"


def test_dashboard_strategy_summary_endpoint_returns_snapshot() -> None:
    app = FastAPI()
    app.include_router(create_dashboard_router(cast("OverviewFacade", _StubFacade())))

    client = TestClient(app)
    response = client.get("/dashboard/strategy-summary")

    assert response.status_code == 200
    data = response.json()
    assert data["module_status"] == "read-only"
    assert data["global_status"] == "warming"
    assert data["availability"][0]["key"] == "runtime_ready"


def test_dashboard_execution_summary_endpoint_returns_snapshot() -> None:
    app = FastAPI()
    app.include_router(create_dashboard_router(cast("OverviewFacade", _StubFacade())))

    client = TestClient(app)
    response = client.get("/dashboard/execution-summary")

    assert response.status_code == 200
    data = response.json()
    assert data["module_status"] == "read-only"
    assert data["global_status"] == "warming"
    assert data["availability"][0]["key"] == "runtime_ready"


def test_dashboard_opportunity_summary_endpoint_returns_snapshot() -> None:
    app = FastAPI()
    app.include_router(create_dashboard_router(cast("OverviewFacade", _StubFacade())))

    client = TestClient(app)
    response = client.get("/dashboard/opportunity-summary")

    assert response.status_code == 200
    data = response.json()
    assert data["module_status"] == "read-only"
    assert data["global_status"] == "warming"
    assert data["availability"][0]["key"] == "runtime_ready"


def test_dashboard_orchestration_summary_endpoint_returns_snapshot() -> None:
    app = FastAPI()
    app.include_router(create_dashboard_router(cast("OverviewFacade", _StubFacade())))

    client = TestClient(app)
    response = client.get("/dashboard/orchestration-summary")

    assert response.status_code == 200
    data = response.json()
    assert data["module_status"] == "read-only"
    assert data["global_status"] == "warming"
    assert data["availability"][0]["key"] == "runtime_ready"


def test_dashboard_position_expansion_summary_endpoint_returns_snapshot() -> None:
    app = FastAPI()
    app.include_router(create_dashboard_router(cast("OverviewFacade", _StubFacade())))

    client = TestClient(app)
    response = client.get("/dashboard/position-expansion-summary")

    assert response.status_code == 200
    data = response.json()
    assert data["module_status"] == "read-only"
    assert data["global_status"] == "warming"
    assert data["availability"][0]["key"] == "runtime_ready"


def test_dashboard_portfolio_governor_summary_endpoint_returns_snapshot() -> None:
    app = FastAPI()
    app.include_router(create_dashboard_router(cast("OverviewFacade", _StubFacade())))

    client = TestClient(app)
    response = client.get("/dashboard/portfolio-governor-summary")

    assert response.status_code == 200
    data = response.json()
    assert data["module_status"] == "read-only"
    assert data["global_status"] == "warming"
    assert data["availability"][0]["key"] == "runtime_ready"


def test_dashboard_oms_summary_endpoint_returns_snapshot() -> None:
    app = FastAPI()
    app.include_router(create_dashboard_router(cast("OverviewFacade", _StubFacade())))

    client = TestClient(app)
    response = client.get("/dashboard/oms-summary")

    assert response.status_code == 200
    data = response.json()
    assert data["module_status"] == "read-only"
    assert data["global_status"] == "warming"
    assert data["availability"][0]["key"] == "runtime_ready"


def test_dashboard_manager_summary_endpoint_returns_snapshot() -> None:
    app = FastAPI()
    app.include_router(create_dashboard_router(cast("OverviewFacade", _StubFacade())))

    client = TestClient(app)
    response = client.get("/dashboard/manager-summary")

    assert response.status_code == 200
    data = response.json()
    assert data["module_status"] == "read-only"
    assert data["global_status"] == "warming"
    assert data["availability"][0]["key"] == "runtime_ready"


def test_dashboard_validation_summary_endpoint_returns_snapshot() -> None:
    app = FastAPI()
    app.include_router(create_dashboard_router(cast("OverviewFacade", _StubFacade())))

    client = TestClient(app)
    response = client.get("/dashboard/validation-summary")

    assert response.status_code == 200
    data = response.json()
    assert data["module_status"] == "read-only"
    assert data["global_status"] == "warming"
    assert data["availability"][0]["key"] == "runtime_ready"


def test_dashboard_paper_summary_endpoint_returns_snapshot() -> None:
    app = FastAPI()
    app.include_router(create_dashboard_router(cast("OverviewFacade", _StubFacade())))

    client = TestClient(app)
    response = client.get("/dashboard/paper-summary")

    assert response.status_code == 200
    data = response.json()
    assert data["module_status"] == "read-only"
    assert data["global_status"] == "warming"
    assert data["availability"][0]["key"] == "runtime_ready"


def test_dashboard_backtest_summary_endpoint_returns_snapshot() -> None:
    app = FastAPI()
    app.include_router(create_dashboard_router(cast("OverviewFacade", _StubFacade())))

    client = TestClient(app)
    response = client.get("/dashboard/backtest-summary")

    assert response.status_code == 200
    data = response.json()
    assert data["module_status"] == "read-only"
    assert data["global_status"] == "warming"
    assert data["availability"][0]["key"] == "runtime_ready"


def test_dashboard_reporting_summary_endpoint_returns_snapshot() -> None:
    app = FastAPI()
    app.include_router(create_dashboard_router(cast("OverviewFacade", _StubFacade())))

    client = TestClient(app)
    response = client.get("/dashboard/reporting-summary")

    assert response.status_code == 200
    data = response.json()
    assert data["module_status"] == "read-only"
    assert data["global_status"] == "warming"
    assert data["catalog_counts"]["validation_artifacts"] == 1
    assert data["last_artifact_snapshot"]["kind"] == "validation_report"


def test_dashboard_open_positions_endpoint_returns_snapshot() -> None:
    app = FastAPI()
    app.include_router(create_dashboard_router(cast("OverviewFacade", _StubFacade())))

    client = TestClient(app)
    response = client.get("/dashboard/open-positions")

    assert response.status_code == 200
    data = response.json()
    assert len(data["positions"]) == 1
    assert data["positions"][0]["position_id"] == "pos-1"
    assert data["positions"][0]["symbol"] == "BTC/USDT"
    assert data["positions"][0]["exchange"] == "okx"
    assert data["positions"][0]["strategy"] == "breakout-trend"
    assert data["positions"][0]["current_price"] == "63125"
    assert data["positions"][0]["unrealized_pnl_usd"] == "93.75"
    assert data["positions"][0]["unrealized_pnl_percent"] == "1.00"


def test_dashboard_position_history_endpoint_returns_snapshot() -> None:
    app = FastAPI()
    app.include_router(create_dashboard_router(cast("OverviewFacade", _StubFacade())))

    client = TestClient(app)
    response = client.get("/dashboard/position-history")

    assert response.status_code == 200
    data = response.json()
    assert len(data["positions"]) == 1
    assert data["positions"][0]["position_id"] == "closed-1"
    assert data["positions"][0]["symbol"] == "ETH/USDT"
    assert data["positions"][0]["exchange"] == "bybit"
    assert data["positions"][0]["strategy"] == "mean-reversion-short"
    assert data["positions"][0]["realized_pnl_usd"] == "72.50"
    assert data["positions"][0]["realized_pnl_percent"] == "1.81"


def test_dashboard_overview_endpoint_returns_snapshot_in_full_app_runtime() -> None:
    app = create_dashboard_app()

    with TestClient(app) as client:
        response = client.get("/dashboard/overview")

    assert response.status_code == 200
    data = response.json()
    assert data["health_summary"]["overall_status"] == "healthy"
    assert isinstance(data["module_availability"], list)
    assert any(module["key"] == "overview" for module in data["module_availability"])


def test_dashboard_risk_summary_endpoint_returns_snapshot_in_full_app_runtime() -> None:
    app = create_dashboard_app()

    with TestClient(app) as client:
        response = client.get("/dashboard/risk-summary")

    assert response.status_code == 200
    data = response.json()
    assert data["module_status"] == "read-only"
    assert isinstance(data["constraints"], list)
    assert any(item["key"] == "risk_multiplier" for item in data["constraints"])


def test_dashboard_signals_summary_endpoint_returns_snapshot_in_full_app_runtime() -> None:
    app = create_dashboard_app()

    with TestClient(app) as client:
        response = client.get("/dashboard/signals-summary")

    assert response.status_code == 200
    data = response.json()
    assert data["module_status"] == "read-only"
    assert data["global_status"] == "warming"
    assert isinstance(data["availability"], list)
    assert any(item["key"] == "tracked_signal_keys" for item in data["availability"])


def test_dashboard_strategy_summary_endpoint_returns_snapshot_in_full_app_runtime() -> None:
    app = create_dashboard_app()

    with TestClient(app) as client:
        response = client.get("/dashboard/strategy-summary")

    assert response.status_code == 200
    data = response.json()
    assert data["module_status"] == "read-only"
    assert data["global_status"] == "warming"
    assert isinstance(data["availability"], list)
    assert any(item["key"] == "tracked_context_keys" for item in data["availability"])


def test_dashboard_execution_summary_endpoint_returns_snapshot_in_full_app_runtime() -> None:
    app = create_dashboard_app()

    with TestClient(app) as client:
        response = client.get("/dashboard/execution-summary")

    assert response.status_code == 200
    data = response.json()
    assert data["module_status"] == "read-only"
    assert data["global_status"] == "warming"
    assert isinstance(data["availability"], list)
    assert any(item["key"] == "tracked_context_keys" for item in data["availability"])


def test_dashboard_opportunity_summary_endpoint_returns_snapshot_in_full_app_runtime() -> None:
    app = create_dashboard_app()

    with TestClient(app) as client:
        response = client.get("/dashboard/opportunity-summary")

    assert response.status_code == 200
    data = response.json()
    assert data["module_status"] == "read-only"
    assert data["global_status"] == "warming"
    assert isinstance(data["availability"], list)
    assert any(item["key"] == "tracked_context_keys" for item in data["availability"])


def test_dashboard_orchestration_summary_endpoint_returns_snapshot_in_full_app_runtime() -> None:
    app = create_dashboard_app()

    with TestClient(app) as client:
        response = client.get("/dashboard/orchestration-summary")

    assert response.status_code == 200
    data = response.json()
    assert data["module_status"] == "read-only"
    assert data["global_status"] == "warming"
    assert isinstance(data["availability"], list)
    assert any(item["key"] == "tracked_context_keys" for item in data["availability"])


def test_dashboard_position_expansion_summary_endpoint_returns_snapshot_in_full_app_runtime() -> (
    None
):
    app = create_dashboard_app()

    with TestClient(app) as client:
        response = client.get("/dashboard/position-expansion-summary")

    assert response.status_code == 200
    data = response.json()
    assert data["module_status"] == "read-only"
    assert data["global_status"] == "warming"
    assert isinstance(data["availability"], list)
    assert any(item["key"] == "tracked_context_keys" for item in data["availability"])


def test_dashboard_portfolio_governor_summary_endpoint_returns_snapshot_in_full_app_runtime() -> (
    None
):
    app = create_dashboard_app()

    with TestClient(app) as client:
        response = client.get("/dashboard/portfolio-governor-summary")

    assert response.status_code == 200
    data = response.json()
    assert data["module_status"] == "read-only"
    assert data["global_status"] == "warming"
    assert isinstance(data["availability"], list)
    assert any(item["key"] == "tracked_context_keys" for item in data["availability"])


def test_dashboard_oms_summary_endpoint_returns_snapshot_in_full_app_runtime() -> None:
    app = create_dashboard_app()

    with TestClient(app) as client:
        response = client.get("/dashboard/oms-summary")

    assert response.status_code == 200
    data = response.json()
    assert data["module_status"] == "read-only"
    assert data["global_status"] == "warming"
    assert isinstance(data["availability"], list)
    assert any(item["key"] == "tracked_contexts" for item in data["availability"])


def test_dashboard_manager_summary_endpoint_returns_snapshot_in_full_app_runtime() -> None:
    app = create_dashboard_app()

    with TestClient(app) as client:
        response = client.get("/dashboard/manager-summary")

    assert response.status_code == 200
    data = response.json()
    assert data["module_status"] == "read-only"
    assert data["global_status"] == "warming"
    assert isinstance(data["availability"], list)
    assert any(item["key"] == "tracked_contexts" for item in data["availability"])


def test_dashboard_validation_summary_endpoint_returns_snapshot_in_full_app_runtime() -> None:
    app = create_dashboard_app()

    with TestClient(app) as client:
        response = client.get("/dashboard/validation-summary")

    assert response.status_code == 200
    data = response.json()
    assert data["module_status"] == "read-only"
    assert data["global_status"] == "warming"
    assert isinstance(data["availability"], list)
    assert any(item["key"] == "tracked_contexts" for item in data["availability"])


def test_dashboard_paper_summary_endpoint_returns_snapshot_in_full_app_runtime() -> None:
    app = create_dashboard_app()

    with TestClient(app) as client:
        response = client.get("/dashboard/paper-summary")

    assert response.status_code == 200
    data = response.json()
    assert data["module_status"] == "read-only"
    assert data["global_status"] == "warming"
    assert isinstance(data["availability"], list)
    assert any(item["key"] == "tracked_contexts" for item in data["availability"])


def test_dashboard_backtest_summary_endpoint_returns_snapshot_in_full_app_runtime() -> None:
    app = create_dashboard_app()

    with TestClient(app) as client:
        response = client.get("/dashboard/backtest-summary")

    assert response.status_code == 200
    data = response.json()
    assert data["module_status"] == "read-only"
    assert data["global_status"] == "warming"
    assert isinstance(data["availability"], list)
    assert any(item["key"] == "tracked_inputs" for item in data["availability"])


def test_dashboard_reporting_summary_endpoint_returns_snapshot_in_full_app_runtime() -> None:
    app = create_dashboard_app()

    with TestClient(app) as client:
        response = client.get("/dashboard/reporting-summary")

    assert response.status_code == 200
    data = response.json()
    assert data["module_status"] == "read-only"
    assert data["global_status"] == "inactive"
    assert data["catalog_counts"]["total_artifacts"] == 0
    assert data["last_artifact_snapshot"] is None


def test_dashboard_open_positions_endpoint_returns_snapshot_in_full_app_runtime() -> None:
    app = create_dashboard_app()

    with TestClient(app) as client:
        response = client.get("/dashboard/open-positions")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["positions"], list)


def test_dashboard_position_history_endpoint_returns_snapshot_in_full_app_runtime() -> None:
    app = create_dashboard_app()

    with TestClient(app) as client:
        response = client.get("/dashboard/position-history")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["positions"], list)

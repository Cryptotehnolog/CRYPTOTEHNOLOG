from __future__ import annotations

from typing import TYPE_CHECKING, cast

from fastapi import FastAPI
from fastapi.testclient import TestClient

from cryptotechnolog.config import get_settings, reload_settings
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
from cryptotechnolog.dashboard.dto.settings import (
    BybitConnectorDiagnosticsDTO,
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
                    exit_price="3142",
                    exit_reason="trailing_stop",
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
    assert data["positions"][0]["exit_price"] == "3142"
    assert data["positions"][0]["exit_reason"] == "trailing_stop"
    assert data["positions"][0]["realized_pnl_usd"] == "72.50"
    assert data["positions"][0]["realized_pnl_percent"] == "1.81"


def test_dashboard_universe_policy_settings_endpoint_returns_current_values() -> None:
    app = FastAPI()
    app.include_router(create_dashboard_router(cast("OverviewFacade", _StubFacade())))

    client = TestClient(app)
    response = client.get("/dashboard/settings/universe-policy")

    assert response.status_code == 200
    data = UniversePolicySettingsDTO.model_validate(response.json())
    settings = get_settings()
    assert data.max_spread_bps == settings.universe_max_spread_bps
    assert data.min_top_depth_usd == settings.universe_min_top_depth_usd
    assert data.min_ready_confidence == settings.universe_min_ready_confidence


def test_dashboard_universe_policy_settings_endpoint_updates_current_values() -> None:
    app = FastAPI()
    app.include_router(create_dashboard_router(cast("OverviewFacade", _StubFacade())))

    client = TestClient(app)
    try:
        response = client.put(
            "/dashboard/settings/universe-policy",
            json={
                "max_spread_bps": 18.0,
                "min_top_depth_usd": 120000.0,
                "min_depth_5bps_usd": 280000.0,
                "max_latency_ms": 180.0,
                "min_coverage_ratio": 0.95,
                "max_data_age_ms": 1500,
                "min_quality_score": 0.8,
                "min_ready_instruments": 8,
                "min_degraded_instruments_ratio": 0.2,
                "min_ready_confidence": 0.82,
                "min_degraded_confidence": 0.55,
            },
        )

        assert response.status_code == 200
        data = UniversePolicySettingsDTO.model_validate(response.json())
        assert data.max_spread_bps == 18.0
        assert data.min_top_depth_usd == 120000.0
        assert data.min_ready_confidence == 0.82

        settings = get_settings()
        assert settings.universe_max_spread_bps == 18.0
        assert settings.universe_min_top_depth_usd == 120000.0
        assert settings.universe_min_ready_confidence == 0.82
    finally:
        reload_settings()


def test_dashboard_decision_chain_settings_endpoint_returns_current_values() -> None:
    app = FastAPI()
    app.include_router(create_dashboard_router(cast("OverviewFacade", _StubFacade())))

    client = TestClient(app)
    response = client.get("/dashboard/settings/decision-thresholds")

    assert response.status_code == 200
    data = DecisionChainSettingsDTO.model_validate(response.json())
    settings = get_settings()
    assert data.signal_min_trend_strength == settings.signal_min_trend_strength
    assert data.signal_min_regime_confidence == settings.signal_min_regime_confidence
    assert data.orchestration_max_decision_age_seconds == (
        settings.orchestration_max_decision_age_seconds
    )


def test_dashboard_decision_chain_settings_endpoint_updates_current_values() -> None:
    app = FastAPI()
    app.include_router(create_dashboard_router(cast("OverviewFacade", _StubFacade())))

    client = TestClient(app)
    try:
        response = client.put(
            "/dashboard/settings/decision-thresholds",
            json={
                "signal_min_trend_strength": 24.0,
                "signal_min_regime_confidence": 0.62,
                "signal_target_risk_reward": 2.5,
                "signal_max_age_seconds": 240,
                "strategy_min_signal_confidence": 0.61,
                "strategy_max_candidate_age_seconds": 260,
                "execution_min_strategy_confidence": 0.64,
                "execution_max_intent_age_seconds": 180,
                "opportunity_min_confidence": 0.67,
                "opportunity_min_priority": 0.71,
                "opportunity_max_age_seconds": 210,
                "orchestration_min_confidence": 0.69,
                "orchestration_min_priority": 0.74,
                "orchestration_max_decision_age_seconds": 150,
            },
        )

        assert response.status_code == 200
        data = DecisionChainSettingsDTO.model_validate(response.json())
        assert data.signal_min_trend_strength == 24.0
        assert data.strategy_min_signal_confidence == 0.61
        assert data.orchestration_max_decision_age_seconds == 150

        settings = get_settings()
        assert settings.signal_min_trend_strength == 24.0
        assert settings.strategy_min_signal_confidence == 0.61
        assert settings.orchestration_max_decision_age_seconds == 150
    finally:
        reload_settings()


def test_dashboard_risk_limits_settings_endpoint_returns_current_values() -> None:
    app = FastAPI()
    app.include_router(create_dashboard_router(cast("OverviewFacade", _StubFacade())))

    client = TestClient(app)
    response = client.get("/dashboard/settings/risk-limits")

    assert response.status_code == 200
    data = RiskLimitsSettingsDTO.model_validate(response.json())
    settings = get_settings()
    assert data.base_r_percent == settings.base_r_percent
    assert data.max_r_per_trade == settings.max_r_per_trade
    assert data.risk_starting_equity == settings.risk_starting_equity


def test_dashboard_risk_limits_settings_endpoint_updates_current_values() -> None:
    app = FastAPI()
    app.include_router(create_dashboard_router(cast("OverviewFacade", _StubFacade())))

    client = TestClient(app)
    try:
        response = client.put(
            "/dashboard/settings/risk-limits",
            json={
                "base_r_percent": 0.015,
                "max_r_per_trade": 1.2,
                "max_portfolio_r": 6.0,
                "risk_max_total_exposure_usd": 65000.0,
                "max_position_size": 12000.0,
                "risk_starting_equity": 15000.0,
            },
        )

        assert response.status_code == 200
        data = RiskLimitsSettingsDTO.model_validate(response.json())
        assert data.base_r_percent == 0.015
        assert data.max_r_per_trade == 1.2
        assert data.risk_starting_equity == 15000.0

        settings = get_settings()
        assert settings.base_r_percent == 0.015
        assert settings.max_r_per_trade == 1.2
        assert settings.risk_starting_equity == 15000.0
    finally:
        reload_settings()


def test_dashboard_trailing_policy_settings_endpoint_returns_current_values() -> None:
    app = FastAPI()
    app.include_router(create_dashboard_router(cast("OverviewFacade", _StubFacade())))

    client = TestClient(app)
    response = client.get("/dashboard/settings/trailing-policy")

    assert response.status_code == 200
    data = TrailingPolicySettingsDTO.model_validate(response.json())
    settings = get_settings()
    assert data.arm_at_pnl_r == settings.trailing_arm_at_pnl_r
    assert data.t1_atr_multiplier == settings.trailing_t1_atr_multiplier
    assert data.structural_confirmed_lows == settings.trailing_structural_confirmed_lows


def test_dashboard_trailing_policy_settings_endpoint_updates_current_values() -> None:
    app = FastAPI()
    app.include_router(create_dashboard_router(cast("OverviewFacade", _StubFacade())))

    client = TestClient(app)
    try:
        response = client.put(
            "/dashboard/settings/trailing-policy",
            json={
                "arm_at_pnl_r": 1.2,
                "t2_at_pnl_r": 2.4,
                "t3_at_pnl_r": 4.5,
                "t4_at_pnl_r": 6.8,
                "t1_atr_multiplier": 2.2,
                "t2_atr_multiplier": 1.7,
                "t3_atr_multiplier": 1.2,
                "t4_atr_multiplier": 0.9,
                "emergency_buffer_bps": 60.0,
                "structural_min_adx": 28.0,
                "structural_confirmed_highs": 3,
                "structural_confirmed_lows": 4,
            },
        )

        assert response.status_code == 200
        data = TrailingPolicySettingsDTO.model_validate(response.json())
        assert data.arm_at_pnl_r == 1.2
        assert data.t1_atr_multiplier == 2.2
        assert data.structural_confirmed_lows == 4

        settings = get_settings()
        assert settings.trailing_arm_at_pnl_r == 1.2
        assert settings.trailing_t1_atr_multiplier == 2.2
        assert settings.trailing_structural_confirmed_lows == 4
    finally:
        reload_settings()


def test_dashboard_correlation_policy_settings_endpoint_returns_current_values() -> None:
    app = FastAPI()
    app.include_router(create_dashboard_router(cast("OverviewFacade", _StubFacade())))

    client = TestClient(app)
    response = client.get("/dashboard/settings/correlation-policy")

    assert response.status_code == 200
    data = CorrelationPolicySettingsDTO.model_validate(response.json())
    settings = get_settings()
    assert data.correlation_limit == settings.correlation_limit
    assert data.same_group_correlation == settings.same_group_correlation
    assert data.cross_group_correlation == settings.cross_group_correlation


def test_dashboard_correlation_policy_settings_endpoint_updates_current_values() -> None:
    app = FastAPI()
    app.include_router(create_dashboard_router(cast("OverviewFacade", _StubFacade())))

    client = TestClient(app)
    try:
        response = client.put(
            "/dashboard/settings/correlation-policy",
            json={
                "correlation_limit": 0.75,
                "same_group_correlation": 0.6,
                "cross_group_correlation": 0.2,
            },
        )

        assert response.status_code == 200
        data = CorrelationPolicySettingsDTO.model_validate(response.json())
        assert data.correlation_limit == 0.75
        assert data.same_group_correlation == 0.6
        assert data.cross_group_correlation == 0.2

        settings = get_settings()
        assert settings.correlation_limit == 0.75
        assert settings.same_group_correlation == 0.6
        assert settings.cross_group_correlation == 0.2
    finally:
        reload_settings()


def test_dashboard_protection_policy_settings_endpoint_returns_current_values() -> None:
    app = FastAPI()
    app.include_router(create_dashboard_router(cast("OverviewFacade", _StubFacade())))

    client = TestClient(app)
    response = client.get("/dashboard/settings/protection-policy")

    assert response.status_code == 200
    data = ProtectionPolicySettingsDTO.model_validate(response.json())
    settings = get_settings()
    assert data.halt_priority_threshold == settings.protection_halt_priority_threshold
    assert data.freeze_priority_threshold == settings.protection_freeze_priority_threshold


def test_dashboard_protection_policy_settings_endpoint_updates_current_values() -> None:
    app = FastAPI()
    app.include_router(create_dashboard_router(cast("OverviewFacade", _StubFacade())))

    client = TestClient(app)
    try:
        response = client.put(
            "/dashboard/settings/protection-policy",
            json={
                "halt_priority_threshold": 0.88,
                "freeze_priority_threshold": 0.96,
            },
        )

        assert response.status_code == 200
        data = ProtectionPolicySettingsDTO.model_validate(response.json())
        assert data.halt_priority_threshold == 0.88
        assert data.freeze_priority_threshold == 0.96

        settings = get_settings()
        assert settings.protection_halt_priority_threshold == 0.88
        assert settings.protection_freeze_priority_threshold == 0.96
    finally:
        reload_settings()


def test_dashboard_funding_policy_settings_endpoint_returns_current_values() -> None:
    app = FastAPI()
    app.include_router(create_dashboard_router(cast("OverviewFacade", _StubFacade())))

    client = TestClient(app)
    response = client.get("/dashboard/settings/funding-policy")

    assert response.status_code == 200
    data = FundingPolicySettingsDTO.model_validate(response.json())
    settings = get_settings()
    assert data.min_arbitrage_spread == settings.funding_min_arbitrage_spread
    assert data.min_annualized_spread == settings.funding_min_annualized_spread
    assert data.max_acceptable_funding == settings.funding_max_acceptable_rate
    assert data.min_exchange_improvement == settings.funding_min_exchange_improvement
    assert data.min_quotes_for_opportunity == settings.funding_min_quotes_for_opportunity


def test_dashboard_funding_policy_settings_endpoint_updates_current_values() -> None:
    app = FastAPI()
    app.include_router(create_dashboard_router(cast("OverviewFacade", _StubFacade())))

    client = TestClient(app)
    try:
        response = client.put(
            "/dashboard/settings/funding-policy",
            json={
                "min_arbitrage_spread": 0.003,
                "min_annualized_spread": 0.08,
                "max_acceptable_funding": 0.0025,
                "min_exchange_improvement": 0.0008,
                "min_quotes_for_opportunity": 3,
            },
        )

        assert response.status_code == 200
        data = FundingPolicySettingsDTO.model_validate(response.json())
        assert data.min_arbitrage_spread == 0.003
        assert data.min_annualized_spread == 0.08
        assert data.max_acceptable_funding == 0.0025
        assert data.min_exchange_improvement == 0.0008
        assert data.min_quotes_for_opportunity == 3

        settings = get_settings()
        assert settings.funding_min_arbitrage_spread == 0.003
        assert settings.funding_min_annualized_spread == 0.08
        assert settings.funding_max_acceptable_rate == 0.0025
        assert settings.funding_min_exchange_improvement == 0.0008
        assert settings.funding_min_quotes_for_opportunity == 3
    finally:
        reload_settings()


def test_dashboard_system_state_policy_settings_endpoint_returns_current_values() -> None:
    app = FastAPI()
    app.include_router(create_dashboard_router(cast("OverviewFacade", _StubFacade())))

    client = TestClient(app)
    response = client.get("/dashboard/settings/system-state-policy")

    assert response.status_code == 200
    data = SystemStatePolicySettingsDTO.model_validate(response.json())
    settings = get_settings()
    assert data.trading_risk_multiplier == settings.system_trading_risk_multiplier
    assert data.degraded_max_positions == settings.system_degraded_max_positions
    assert data.survival_max_order_size == settings.system_survival_max_order_size


def test_dashboard_system_state_policy_settings_endpoint_updates_current_values() -> None:
    app = FastAPI()
    app.include_router(create_dashboard_router(cast("OverviewFacade", _StubFacade())))

    client = TestClient(app)
    try:
        response = client.put(
            "/dashboard/settings/system-state-policy",
            json={
                "trading_risk_multiplier": 0.9,
                "trading_max_positions": 80,
                "trading_max_order_size": 0.08,
                "degraded_risk_multiplier": 0.45,
                "degraded_max_positions": 40,
                "degraded_max_order_size": 0.04,
                "risk_reduction_risk_multiplier": 0.2,
                "risk_reduction_max_positions": 15,
                "risk_reduction_max_order_size": 0.015,
                "survival_risk_multiplier": 0.05,
                "survival_max_positions": 1,
                "survival_max_order_size": 0.005,
            },
        )

        assert response.status_code == 200
        data = SystemStatePolicySettingsDTO.model_validate(response.json())
        assert data.trading_risk_multiplier == 0.9
        assert data.degraded_max_positions == 40
        assert data.survival_max_order_size == 0.005

        settings = get_settings()
        assert settings.system_trading_risk_multiplier == 0.9
        assert settings.system_degraded_max_positions == 40
        assert settings.system_survival_max_order_size == 0.005
    finally:
        reload_settings()


def test_dashboard_system_state_timeouts_settings_endpoint_returns_current_values() -> None:
    app = FastAPI()
    app.include_router(create_dashboard_router(cast("OverviewFacade", _StubFacade())))

    client = TestClient(app)
    response = client.get("/dashboard/settings/system-state-timeouts")

    assert response.status_code == 200
    data = SystemStateTimeoutSettingsDTO.model_validate(response.json())
    settings = get_settings()
    assert data.boot_max_seconds == settings.system_boot_max_seconds
    assert data.ready_max_seconds == settings.system_ready_max_seconds
    assert data.recovery_max_seconds == settings.system_recovery_max_seconds


def test_dashboard_system_state_timeouts_settings_endpoint_updates_current_values() -> None:
    app = FastAPI()
    app.include_router(create_dashboard_router(cast("OverviewFacade", _StubFacade())))

    client = TestClient(app)
    try:
        response = client.put(
            "/dashboard/settings/system-state-timeouts",
            json={
                "boot_max_seconds": 75,
                "init_max_seconds": 150,
                "ready_max_seconds": 4200,
                "risk_reduction_max_seconds": 2100,
                "degraded_max_seconds": 3900,
                "survival_max_seconds": 1950,
                "error_max_seconds": 420,
                "recovery_max_seconds": 720,
            },
        )

        assert response.status_code == 200
        data = SystemStateTimeoutSettingsDTO.model_validate(response.json())
        assert data.boot_max_seconds == 75
        assert data.degraded_max_seconds == 3900
        assert data.recovery_max_seconds == 720

        settings = get_settings()
        assert settings.system_boot_max_seconds == 75
        assert settings.system_degraded_max_seconds == 3900
        assert settings.system_recovery_max_seconds == 720
    finally:
        reload_settings()


def test_dashboard_reliability_policy_settings_endpoint_returns_current_values() -> None:
    app = FastAPI()
    app.include_router(create_dashboard_router(cast("OverviewFacade", _StubFacade())))

    client = TestClient(app)
    response = client.get("/dashboard/settings/reliability-policy")

    assert response.status_code == 200
    data = ReliabilityPolicySettingsDTO.model_validate(response.json())
    settings = get_settings()
    assert data.circuit_breaker_failure_threshold == (
        settings.reliability_circuit_breaker_failure_threshold
    )
    assert data.watchdog_backoff_multiplier == settings.reliability_watchdog_backoff_multiplier
    assert data.watchdog_check_interval_seconds == (
        settings.reliability_watchdog_check_interval_seconds
    )


def test_dashboard_reliability_policy_settings_endpoint_updates_current_values() -> None:
    app = FastAPI()
    app.include_router(create_dashboard_router(cast("OverviewFacade", _StubFacade())))

    client = TestClient(app)
    try:
        response = client.put(
            "/dashboard/settings/reliability-policy",
            json={
                "circuit_breaker_failure_threshold": 6,
                "circuit_breaker_recovery_timeout_seconds": 75,
                "circuit_breaker_success_threshold": 4,
                "watchdog_failure_threshold": 4,
                "watchdog_backoff_base_seconds": 1.5,
                "watchdog_backoff_multiplier": 2.5,
                "watchdog_max_backoff_seconds": 90.0,
                "watchdog_jitter_factor": 0.35,
                "watchdog_check_interval_seconds": 20.0,
            },
        )

        assert response.status_code == 200
        data = ReliabilityPolicySettingsDTO.model_validate(response.json())
        assert data.circuit_breaker_failure_threshold == 6
        assert data.circuit_breaker_recovery_timeout_seconds == 75
        assert data.watchdog_check_interval_seconds == 20.0

        settings = get_settings()
        assert settings.reliability_circuit_breaker_failure_threshold == 6
        assert settings.reliability_circuit_breaker_recovery_timeout_seconds == 75
        assert settings.reliability_watchdog_check_interval_seconds == 20.0
    finally:
        reload_settings()


def test_dashboard_health_policy_settings_endpoint_returns_current_values() -> None:
    app = FastAPI()
    app.include_router(create_dashboard_router(cast("OverviewFacade", _StubFacade())))

    client = TestClient(app)
    response = client.get("/dashboard/settings/health-policy")

    assert response.status_code == 200
    data = HealthPolicySettingsDTO.model_validate(response.json())
    settings = get_settings()
    assert data.check_timeout_seconds == settings.health_check_timeout_seconds
    assert (
        data.background_check_interval_seconds == settings.health_background_check_interval_seconds
    )
    assert data.check_and_wait_timeout_seconds == settings.health_check_and_wait_timeout_seconds


def test_dashboard_health_policy_settings_endpoint_updates_current_values() -> None:
    app = FastAPI()
    app.include_router(create_dashboard_router(cast("OverviewFacade", _StubFacade())))

    client = TestClient(app)
    try:
        response = client.put(
            "/dashboard/settings/health-policy",
            json={
                "check_timeout_seconds": 6.5,
                "background_check_interval_seconds": 45.0,
                "check_and_wait_timeout_seconds": 20.0,
            },
        )

        assert response.status_code == 200
        data = HealthPolicySettingsDTO.model_validate(response.json())
        assert data.check_timeout_seconds == 6.5
        assert data.background_check_interval_seconds == 45.0
        assert data.check_and_wait_timeout_seconds == 20.0

        settings = get_settings()
        assert settings.health_check_timeout_seconds == 6.5
        assert settings.health_background_check_interval_seconds == 45.0
        assert settings.health_check_and_wait_timeout_seconds == 20.0
    finally:
        reload_settings()


def test_dashboard_event_bus_policy_settings_endpoint_returns_current_values() -> None:
    app = FastAPI()
    app.include_router(create_dashboard_router(cast("OverviewFacade", _StubFacade())))

    client = TestClient(app)
    response = client.get("/dashboard/settings/event-bus-policy")

    assert response.status_code == 200
    data = EventBusPolicySettingsDTO.model_validate(response.json())
    settings = get_settings()
    assert data.subscriber_capacity == settings.event_bus_subscriber_capacity
    assert data.fill_ratio_low == settings.event_bus_fill_ratio_low
    assert data.drain_timeout_seconds == settings.event_bus_drain_timeout_seconds


def test_dashboard_event_bus_policy_settings_endpoint_updates_current_values() -> None:
    app = FastAPI()
    app.include_router(create_dashboard_router(cast("OverviewFacade", _StubFacade())))

    client = TestClient(app)
    try:
        response = client.put(
            "/dashboard/settings/event-bus-policy",
            json={
                "subscriber_capacity": 2048,
                "fill_ratio_low": 0.6,
                "fill_ratio_normal": 0.75,
                "fill_ratio_high": 0.92,
                "push_wait_timeout_seconds": 6.5,
                "drain_timeout_seconds": 42.0,
            },
        )

        assert response.status_code == 200
        data = EventBusPolicySettingsDTO.model_validate(response.json())
        assert data.subscriber_capacity == 2048
        assert data.fill_ratio_low == 0.6
        assert data.drain_timeout_seconds == 42.0

        settings = get_settings()
        assert settings.event_bus_subscriber_capacity == 2048
        assert settings.event_bus_fill_ratio_low == 0.6
        assert settings.event_bus_fill_ratio_normal == 0.75
        assert settings.event_bus_fill_ratio_high == 0.92
        assert settings.event_bus_push_wait_timeout_seconds == 6.5
        assert settings.event_bus_drain_timeout_seconds == 42.0
    finally:
        reload_settings()


def test_dashboard_manual_approval_policy_settings_endpoint_returns_current_values() -> None:
    app = FastAPI()
    app.include_router(create_dashboard_router(cast("OverviewFacade", _StubFacade())))

    client = TestClient(app)
    response = client.get("/dashboard/settings/manual-approval-policy")

    assert response.status_code == 200
    data = ManualApprovalPolicySettingsDTO.model_validate(response.json())
    settings = get_settings()
    assert data.approval_timeout_minutes == settings.manual_approval_timeout_minutes


def test_dashboard_manual_approval_policy_settings_endpoint_updates_current_values() -> None:
    app = FastAPI()
    app.include_router(create_dashboard_router(cast("OverviewFacade", _StubFacade())))

    client = TestClient(app)
    try:
        response = client.put(
            "/dashboard/settings/manual-approval-policy",
            json={
                "approval_timeout_minutes": 9,
            },
        )

        assert response.status_code == 200
        data = ManualApprovalPolicySettingsDTO.model_validate(response.json())
        assert data.approval_timeout_minutes == 9

        settings = get_settings()
        assert settings.manual_approval_timeout_minutes == 9
    finally:
        reload_settings()


def test_dashboard_workflow_timeouts_settings_endpoint_returns_current_values() -> None:
    app = FastAPI()
    app.include_router(create_dashboard_router(cast("OverviewFacade", _StubFacade())))

    client = TestClient(app)
    response = client.get("/dashboard/settings/workflow-timeouts")

    assert response.status_code == 200
    data = WorkflowTimeoutsSettingsDTO.model_validate(response.json())
    settings = get_settings()
    assert data.manager_max_age_seconds == settings.workflow_manager_max_age_seconds
    assert data.validation_max_age_seconds == settings.workflow_validation_max_age_seconds
    assert data.paper_max_age_seconds == settings.workflow_paper_max_age_seconds
    assert data.replay_max_age_seconds == settings.workflow_replay_max_age_seconds


def test_dashboard_workflow_timeouts_settings_endpoint_updates_current_values() -> None:
    app = FastAPI()
    app.include_router(create_dashboard_router(cast("OverviewFacade", _StubFacade())))

    client = TestClient(app)
    try:
        response = client.put(
            "/dashboard/settings/workflow-timeouts",
            json={
                "manager_max_age_seconds": 4200,
                "validation_max_age_seconds": 3900,
                "paper_max_age_seconds": 4500,
                "replay_max_age_seconds": 4800,
            },
        )

        assert response.status_code == 200
        data = WorkflowTimeoutsSettingsDTO.model_validate(response.json())
        assert data.manager_max_age_seconds == 4200
        assert data.validation_max_age_seconds == 3900
        assert data.paper_max_age_seconds == 4500
        assert data.replay_max_age_seconds == 4800

        settings = get_settings()
        assert settings.workflow_manager_max_age_seconds == 4200
        assert settings.workflow_validation_max_age_seconds == 3900
        assert settings.workflow_paper_max_age_seconds == 4500
        assert settings.workflow_replay_max_age_seconds == 4800
    finally:
        reload_settings()


def test_dashboard_live_feed_policy_settings_endpoint_returns_current_values() -> None:
    app = FastAPI()
    app.include_router(create_dashboard_router(cast("OverviewFacade", _StubFacade())))

    client = TestClient(app)
    response = client.get("/dashboard/settings/live-feed-policy")

    assert response.status_code == 200
    data = LiveFeedPolicySettingsDTO.model_validate(response.json())
    settings = get_settings()
    assert data.retry_delay_seconds == settings.live_feed_retry_delay_seconds


def test_dashboard_live_feed_policy_settings_endpoint_updates_current_values() -> None:
    app = FastAPI()
    app.include_router(create_dashboard_router(cast("OverviewFacade", _StubFacade())))

    client = TestClient(app)
    try:
        response = client.put(
            "/dashboard/settings/live-feed-policy",
            json={
                "retry_delay_seconds": 9,
            },
        )

        assert response.status_code == 200
        data = LiveFeedPolicySettingsDTO.model_validate(response.json())
        assert data.retry_delay_seconds == 9

        settings = get_settings()
        assert settings.live_feed_retry_delay_seconds == 9
    finally:
        reload_settings()


def test_dashboard_bybit_connector_diagnostics_endpoint_returns_disabled_snapshot_by_default() -> (
    None
):
    app = FastAPI()
    app.include_router(create_dashboard_router(cast("OverviewFacade", _StubFacade())))

    client = TestClient(app)
    response = client.get("/dashboard/settings/bybit-connector-diagnostics")

    assert response.status_code == 200
    data = BybitConnectorDiagnosticsDTO.model_validate(response.json())
    assert data.enabled is False
    assert data.symbol is None
    assert data.transport_status == "unavailable"
    assert data.recovery_status == "idle"
    assert data.subscription_alive is False
    assert data.trade_seen is False
    assert data.orderbook_seen is False
    assert data.best_bid is None
    assert data.best_ask is None
    assert data.degraded_reason is None
    assert data.last_disconnect_reason is None


def test_dashboard_bybit_connector_diagnostics_endpoint_surfaces_runtime_snapshot() -> None:
    app = FastAPI()
    app.include_router(
        create_dashboard_router(
            cast("OverviewFacade", _StubFacade()),
            runtime_diagnostics_supplier=lambda: {
                "bybit_market_data_connector": {
                    "enabled": True,
                    "symbols": ("BTC/USDT",),
                    "transport_status": "connected",
                    "recovery_status": "recovered",
                    "subscription_alive": True,
                    "trade_seen": True,
                    "orderbook_seen": True,
                    "best_bid": "68499.90",
                    "best_ask": "68500.00",
                    "last_message_at": "2026-04-01T09:45:40.060548+00:00",
                    "degraded_reason": None,
                    "last_disconnect_reason": None,
                }
            },
        )
    )

    client = TestClient(app)
    response = client.get("/dashboard/settings/bybit-connector-diagnostics")

    assert response.status_code == 200
    data = BybitConnectorDiagnosticsDTO.model_validate(response.json())
    assert data.enabled is True
    assert data.symbol == "BTC/USDT"
    assert data.transport_status == "connected"
    assert data.recovery_status == "recovered"
    assert data.subscription_alive is True
    assert data.trade_seen is True
    assert data.orderbook_seen is True
    assert data.best_bid == "68499.90"
    assert data.best_ask == "68500.00"
    assert data.last_message_at == "2026-04-01T09:45:40.060548+00:00"


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

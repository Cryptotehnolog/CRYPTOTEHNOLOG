from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, Mock

from fastapi import FastAPI
import pytest

from cryptotechnolog.core import EnhancedEventBus
from cryptotechnolog.dashboard.app import create_dashboard_app
from cryptotechnolog.dashboard.dev_seed import DASHBOARD_DEV_SEED_ENV_VAR, POSITIONS_DEV_SEED_NAME
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
from cryptotechnolog.dashboard.dto.positions import OpenPositionsDTO, PositionHistoryDTO
from cryptotechnolog.dashboard.dto.reporting import (
    ReportingCatalogCountsDTO,
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
from cryptotechnolog.dashboard.runtime import create_dashboard_runtime
from cryptotechnolog.runtime_identity import get_runtime_version


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
        self.overview_facade.get_risk_summary = AsyncMock(
            return_value=RiskSummaryDTO(
                module_status="read-only",
                current_state="boot",
                global_status="blocked",
                limiting_state="trading-blocked",
                trading_blocked=True,
                active_risk_path=None,
                state_note="Система загружается, торговля запрещена",
                summary_reason=None,
                constraints=[
                    RiskConstraintDTO(
                        key="risk_multiplier",
                        label="Risk multiplier",
                        value="0.00x",
                        status="blocked",
                        note="Текущая state policy запрещает торговлю.",
                    )
                ],
            )
        )
        self.overview_facade.get_signals_summary = AsyncMock(
            return_value=SignalsSummaryDTO(
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
                        key="tracked_signal_keys",
                        label="Tracked signal keys",
                        value="0",
                        status="info",
                        note="Количество signal keys в текущем runtime snapshot.",
                    )
                ],
            )
        )
        self.overview_facade.get_strategy_summary = AsyncMock(
            return_value=StrategySummaryDTO(
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
                        key="tracked_context_keys",
                        label="Tracked context keys",
                        value="0",
                        status="info",
                        note="Количество strategy context keys в текущем runtime snapshot.",
                    )
                ],
            )
        )
        self.overview_facade.get_execution_summary = AsyncMock(
            return_value=ExecutionSummaryDTO(
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
                        key="tracked_context_keys",
                        label="Tracked context keys",
                        value="0",
                        status="info",
                        note="Количество execution context keys в текущем runtime snapshot.",
                    )
                ],
            )
        )
        self.overview_facade.get_opportunity_summary = AsyncMock(
            return_value=OpportunitySummaryDTO(
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
                        key="tracked_context_keys",
                        label="Tracked context keys",
                        value="0",
                        status="info",
                        note="Количество opportunity context keys в текущем runtime snapshot.",
                    )
                ],
            )
        )
        self.overview_facade.get_orchestration_summary = AsyncMock(
            return_value=OrchestrationSummaryDTO(
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
                        key="tracked_context_keys",
                        label="Tracked context keys",
                        value="0",
                        status="info",
                        note="Количество orchestration context keys в текущем runtime snapshot.",
                    )
                ],
            )
        )
        self.overview_facade.get_position_expansion_summary = AsyncMock(
            return_value=PositionExpansionSummaryDTO(
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
                        key="tracked_context_keys",
                        label="Tracked context keys",
                        value="0",
                        status="info",
                        note="Количество ключей контекста расширения позиции в текущем runtime snapshot.",
                    )
                ],
            )
        )
        self.overview_facade.get_portfolio_governor_summary = AsyncMock(
            return_value=PortfolioGovernorSummaryDTO(
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
                        key="tracked_context_keys",
                        label="Tracked context keys",
                        value="0",
                        status="info",
                        note="Количество governor context keys в текущем runtime snapshot.",
                    )
                ],
            )
        )
        self.overview_facade.get_oms_summary = AsyncMock(
            return_value=OmsSummaryDTO(
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
                        key="tracked_contexts",
                        label="Tracked contexts",
                        value="0",
                        status="info",
                        note="Количество OMS context entries в текущем runtime snapshot.",
                    )
                ],
            )
        )
        self.overview_facade.get_manager_summary = AsyncMock(
            return_value=ManagerSummaryDTO(
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
                        key="tracked_contexts",
                        label="Tracked contexts",
                        value="0",
                        status="info",
                        note="Количество manager context entries в текущем runtime snapshot.",
                    )
                ],
            )
        )
        self.overview_facade.get_validation_summary = AsyncMock(
            return_value=ValidationSummaryDTO(
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
                        key="tracked_contexts",
                        label="Tracked contexts",
                        value="0",
                        status="info",
                        note="Количество validation context entries в текущем runtime snapshot.",
                    )
                ],
            )
        )
        self.overview_facade.get_paper_summary = AsyncMock(
            return_value=PaperSummaryDTO(
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
                        key="tracked_contexts",
                        label="Tracked contexts",
                        value="0",
                        status="info",
                        note="Количество paper context entries в текущем runtime snapshot.",
                    )
                ],
            )
        )
        self.overview_facade.get_backtest_summary = AsyncMock(
            return_value=BacktestSummaryDTO(
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
                        key="tracked_inputs",
                        label="Tracked inputs",
                        value="0",
                        status="info",
                        note="Количество historical inputs в текущем runtime snapshot.",
                    )
                ],
            )
        )
        self.overview_facade.get_reporting_summary = AsyncMock(
            return_value=ReportingSummaryDTO(
                module_status="read-only",
                global_status="inactive",
                catalog_counts=ReportingCatalogCountsDTO(
                    total_artifacts=0,
                    total_bundles=0,
                    validation_artifacts=0,
                    paper_artifacts=0,
                    replay_artifacts=0,
                ),
                summary_note=(
                    "Каталог reporting artifacts пока не вывел ни одного surfaced artifact "
                    "или bundle."
                ),
                summary_reason=None,
            )
        )
        self.overview_facade.get_open_positions = AsyncMock(
            return_value=OpenPositionsDTO(positions=[])
        )
        self.overview_facade.get_position_history = AsyncMock(
            return_value=PositionHistoryDTO(positions=[])
        )


def test_create_dashboard_app_registers_runtime_and_router() -> None:
    runtime = _StubRuntime()

    app = create_dashboard_app(runtime=runtime)

    assert isinstance(app, FastAPI)
    assert app.version == get_runtime_version()
    assert app.state.dashboard_runtime is runtime
    routes = {route.path for route in app.routes}
    assert "/dashboard/overview" in routes
    assert "/dashboard/risk-summary" in routes
    assert "/dashboard/signals-summary" in routes
    assert "/dashboard/strategy-summary" in routes
    assert "/dashboard/execution-summary" in routes
    assert "/dashboard/opportunity-summary" in routes
    assert "/dashboard/orchestration-summary" in routes
    assert "/dashboard/position-expansion-summary" in routes
    assert "/dashboard/portfolio-governor-summary" in routes
    assert "/dashboard/oms-summary" in routes
    assert "/dashboard/manager-summary" in routes
    assert "/dashboard/validation-summary" in routes
    assert "/dashboard/paper-summary" in routes
    assert "/dashboard/backtest-summary" in routes
    assert "/dashboard/reporting-summary" in routes
    assert "/dashboard/open-positions" in routes
    assert "/dashboard/position-history" in routes


def test_create_dashboard_app_builds_local_runtime_without_global_event_bus() -> None:
    app = create_dashboard_app()

    assert isinstance(app, FastAPI)
    assert app.version == get_runtime_version()
    assert app.state.dashboard_runtime.event_bus is not None
    assert app.state.dashboard_runtime.event_bus.enable_persistence is False
    routes = {route.path for route in app.routes}
    assert "/dashboard/overview" in routes
    assert "/dashboard/risk-summary" in routes
    assert "/dashboard/signals-summary" in routes
    assert "/dashboard/strategy-summary" in routes
    assert "/dashboard/execution-summary" in routes
    assert "/dashboard/opportunity-summary" in routes
    assert "/dashboard/orchestration-summary" in routes
    assert "/dashboard/position-expansion-summary" in routes
    assert "/dashboard/portfolio-governor-summary" in routes
    assert "/dashboard/oms-summary" in routes
    assert "/dashboard/manager-summary" in routes
    assert "/dashboard/validation-summary" in routes
    assert "/dashboard/paper-summary" in routes
    assert "/dashboard/backtest-summary" in routes
    assert "/dashboard/reporting-summary" in routes
    assert "/dashboard/open-positions" in routes
    assert "/dashboard/position-history" in routes


@pytest.mark.asyncio
async def test_create_dashboard_app_local_runtime_lifecycle_starts_and_stops() -> None:
    app = create_dashboard_app()
    runtime = app.state.dashboard_runtime

    await runtime.start()
    assert runtime.operator_gate._running is True
    assert runtime.signal_runtime.is_started is True
    assert runtime.strategy_runtime.is_started is True
    assert runtime.execution_runtime.is_started is True
    assert runtime.opportunity_runtime.is_started is True
    assert runtime.orchestration_runtime.is_started is True
    assert runtime.position_expansion_runtime.is_started is True
    assert runtime.portfolio_governor_runtime.is_started is True
    assert runtime.oms_runtime.is_started is True
    assert runtime.manager_runtime.is_started is True
    assert runtime.validation_runtime.is_started is True
    assert runtime.paper_runtime.is_started is True
    assert runtime.backtest_runtime.is_started is True

    await runtime.stop()
    assert runtime.operator_gate._running is False
    assert runtime.signal_runtime.is_started is False
    assert runtime.strategy_runtime.is_started is False
    assert runtime.execution_runtime.is_started is False
    assert runtime.opportunity_runtime.is_started is False
    assert runtime.orchestration_runtime.is_started is False
    assert runtime.position_expansion_runtime.is_started is False
    assert runtime.portfolio_governor_runtime.is_started is False
    assert runtime.oms_runtime.is_started is False
    assert runtime.manager_runtime.is_started is False
    assert runtime.validation_runtime.is_started is False
    assert runtime.paper_runtime.is_started is False
    assert runtime.backtest_runtime.is_started is False


@pytest.mark.asyncio
async def test_create_dashboard_runtime_uses_controlled_positions_dev_seed_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(DASHBOARD_DEV_SEED_ENV_VAR, POSITIONS_DEV_SEED_NAME)
    runtime = create_dashboard_runtime(
        event_bus=EnhancedEventBus(
            enable_persistence=False,
            redis_url=None,
            rate_limit=1000,
        )
    )

    open_positions = await runtime.overview_facade.get_open_positions()
    position_history = await runtime.overview_facade.get_position_history()

    assert len(open_positions.positions) == 3
    assert {item.exchange for item in open_positions.positions} == {
        "OKX",
        "Bybit",
        "Binance",
    }
    assert {item.strategy for item in open_positions.positions} == {
        "breakout-trend",
        "mean-reversion-short",
        "range-continuation",
    }
    assert {item.current_price for item in open_positions.positions} == {
        Decimal("68125"),
        Decimal("3462"),
        Decimal("175.9"),
    }
    assert {item.unrealized_pnl_usd for item in open_positions.positions} == {
        Decimal("246.75"),
        Decimal("351.00"),
        Decimal("-300.00"),
    }
    assert len(position_history.positions) == 4
    assert {item.exchange for item in position_history.positions} == {
        "OKX",
        "Bybit",
        "Binance",
    }
    assert {item.strategy for item in position_history.positions} == {
        "breakout-trend",
        "mean-reversion-short",
        "range-continuation",
        "funding-rotation",
    }

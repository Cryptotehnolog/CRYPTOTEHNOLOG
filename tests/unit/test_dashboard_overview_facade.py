from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from cryptotechnolog.core.health import ComponentHealth, HealthStatus, SystemHealth
from cryptotechnolog.core.state_machine_enums import SystemState
from cryptotechnolog.core.system_controller import ShutdownPhase, StartupPhase, SystemStatus
from cryptotechnolog.dashboard.facade.composition import OverviewCompositionRoot
from cryptotechnolog.dashboard.facade.contracts import (
    BacktestSummarySnapshot,
    EventSummarySnapshot,
    ExecutionSummarySnapshot,
    ManagerSummarySnapshot,
    OmsSummarySnapshot,
    OpportunitySummarySnapshot,
    OrchestrationSummarySnapshot,
    PaperSummarySnapshot,
    PendingApprovalsSnapshot,
    PortfolioGovernorSummarySnapshot,
    PositionExpansionSummarySnapshot,
    ReportingCatalogCountsSnapshot,
    ReportingLastArtifactSnapshot,
    ReportingSummarySnapshot,
    RiskConfigSnapshot,
    RiskRuntimeSnapshot,
    SignalSummarySnapshot,
    StrategySummarySnapshot,
    ValidationSummarySnapshot,
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


class _RiskRuntimeSource:
    async def get_risk_runtime_snapshot(self) -> RiskRuntimeSnapshot:
        return RiskRuntimeSnapshot(
            active_risk_path="phase5_risk_engine",
            risk_multiplier=0.5,
            allow_new_positions=False,
            allow_new_orders=True,
            max_positions=50,
            max_order_size=0.05,
            require_manual_approval=True,
            policy_description="Деградированный режим, ограниченная торговля",
        )


class _RiskConfigSource:
    async def get_risk_config_snapshot(self) -> RiskConfigSnapshot:
        return RiskConfigSnapshot(
            base_r_percent=0.01,
            max_r_per_trade=1.0,
            max_portfolio_r=5.0,
            max_total_exposure_usd=50000.0,
            max_position_size_usd=10000.0,
            kill_switch_enabled=True,
        )


class _SignalSummarySource:
    async def get_signal_summary_snapshot(self) -> SignalSummarySnapshot:
        return SignalSummarySnapshot(
            started=True,
            ready=False,
            lifecycle_state="warming",
            tracked_signal_keys=0,
            active_signal_keys=0,
            invalidated_signal_keys=0,
            expired_signal_keys=0,
            last_context_at=None,
            last_signal_id=None,
            last_event_type=None,
            last_failure_reason=None,
            readiness_reasons=("no_signal_context_processed",),
            degraded_reasons=(),
            active_signal_path="phase8_signal_contour",
        )


class _StrategySummarySource:
    async def get_strategy_summary_snapshot(self) -> StrategySummarySnapshot:
        return StrategySummarySnapshot(
            started=True,
            ready=False,
            lifecycle_state="warming",
            tracked_context_keys=0,
            tracked_candidate_keys=0,
            actionable_candidate_keys=0,
            invalidated_candidate_keys=0,
            expired_candidate_keys=0,
            last_signal_id=None,
            last_candidate_id=None,
            last_event_type=None,
            last_failure_reason=None,
            readiness_reasons=("no_strategy_context_processed",),
            degraded_reasons=(),
            active_strategy_path="phase9_strategy_contour",
            strategy_source="phase9_foundation_strategy",
        )


class _ExecutionSummarySource:
    async def get_execution_summary_snapshot(self) -> ExecutionSummarySnapshot:
        return ExecutionSummarySnapshot(
            started=True,
            ready=False,
            lifecycle_state="warming",
            tracked_context_keys=0,
            tracked_intent_keys=0,
            executable_intent_keys=0,
            invalidated_intent_keys=0,
            expired_intent_keys=0,
            last_candidate_id=None,
            last_intent_id=None,
            last_event_type=None,
            last_failure_reason=None,
            readiness_reasons=("no_execution_context_processed",),
            degraded_reasons=(),
            active_execution_path="phase10_execution_contour",
            execution_source="phase10_foundation_execution",
        )


class _OpportunitySummarySource:
    async def get_opportunity_summary_snapshot(self) -> OpportunitySummarySnapshot:
        return OpportunitySummarySnapshot(
            started=True,
            ready=False,
            lifecycle_state="warming",
            tracked_context_keys=0,
            tracked_selection_keys=0,
            selected_keys=0,
            invalidated_selection_keys=0,
            expired_selection_keys=0,
            last_intent_id=None,
            last_selection_id=None,
            last_event_type=None,
            last_failure_reason=None,
            readiness_reasons=("no_selection_context_processed",),
            degraded_reasons=(),
            active_opportunity_path="phase11_opportunity_contour",
            opportunity_source="phase11_foundation_selection",
        )


class _OrchestrationSummarySource:
    async def get_orchestration_summary_snapshot(self) -> OrchestrationSummarySnapshot:
        return OrchestrationSummarySnapshot(
            started=True,
            ready=False,
            lifecycle_state="warming",
            tracked_context_keys=0,
            tracked_decision_keys=0,
            forwarded_keys=0,
            abstained_keys=0,
            invalidated_decision_keys=0,
            expired_decision_keys=0,
            last_selection_id=None,
            last_decision_id=None,
            last_event_type=None,
            last_failure_reason=None,
            readiness_reasons=("no_orchestration_context_processed",),
            degraded_reasons=(),
            active_orchestration_path="phase12_orchestration_contour",
            orchestration_source="phase12_meta_orchestration",
        )


class _OmsSummarySource:
    async def get_oms_summary_snapshot(self) -> OmsSummarySnapshot:
        return OmsSummarySnapshot(
            started=True,
            ready=False,
            lifecycle_state="warming",
            tracked_contexts=0,
            tracked_active_orders=0,
            tracked_historical_orders=0,
            last_intent_id=None,
            last_order_id=None,
            last_event_type=None,
            last_failure_reason=None,
            readiness_reasons=("no_execution_intent_processed",),
            degraded_reasons=(),
            active_oms_path="phase16_oms_contour",
            oms_source="phase16_oms",
        )


class _PositionExpansionSummarySource:
    async def get_position_expansion_summary_snapshot(
        self,
    ) -> PositionExpansionSummarySnapshot:
        return PositionExpansionSummarySnapshot(
            started=True,
            ready=False,
            lifecycle_state="warming",
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
            last_failure_reason=None,
            readiness_reasons=("no_position_expansion_context_processed",),
            degraded_reasons=(),
            active_position_expansion_path="phase13_position_expansion_contour",
            position_expansion_source="phase13_position_expansion",
        )


class _PortfolioGovernorSummarySource:
    async def get_portfolio_governor_summary_snapshot(
        self,
    ) -> PortfolioGovernorSummarySnapshot:
        return PortfolioGovernorSummarySnapshot(
            started=True,
            ready=False,
            lifecycle_state="warming",
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
            last_failure_reason=None,
            readiness_reasons=("no_portfolio_governor_context_processed",),
            degraded_reasons=(),
            active_portfolio_governor_path="phase14_portfolio_governor_contour",
            portfolio_governor_source="phase14_portfolio_governor",
        )


class _ManagerSummarySource:
    async def get_manager_summary_snapshot(self) -> ManagerSummarySnapshot:
        return ManagerSummarySnapshot(
            started=True,
            ready=False,
            lifecycle_state="warming",
            tracked_contexts=0,
            tracked_active_workflows=0,
            tracked_historical_workflows=0,
            last_workflow_id=None,
            last_event_type=None,
            last_failure_reason=None,
            readiness_reasons=("no_manager_workflow_processed",),
            degraded_reasons=(),
            active_manager_path="phase17_manager_contour",
            manager_source="phase17_manager",
        )


class _ValidationSummarySource:
    async def get_validation_summary_snapshot(self) -> ValidationSummarySnapshot:
        return ValidationSummarySnapshot(
            started=True,
            ready=False,
            lifecycle_state="warming",
            tracked_contexts=0,
            tracked_active_reviews=0,
            tracked_historical_reviews=0,
            last_review_id=None,
            last_event_type=None,
            last_failure_reason=None,
            readiness_reasons=("no_validation_review_processed",),
            degraded_reasons=(),
            active_validation_path="phase18_validation_contour",
            validation_source="phase18_validation",
        )


class _PaperSummarySource:
    async def get_paper_summary_snapshot(self) -> PaperSummarySnapshot:
        return PaperSummarySnapshot(
            started=True,
            ready=False,
            lifecycle_state="warming",
            tracked_contexts=0,
            tracked_active_rehearsals=0,
            tracked_historical_rehearsals=0,
            last_rehearsal_id=None,
            last_event_type=None,
            last_failure_reason=None,
            readiness_reasons=("no_paper_rehearsal_processed",),
            degraded_reasons=(),
            active_paper_path="phase19_paper_contour",
            paper_source="phase19_paper",
        )


class _BacktestSummarySource:
    async def get_backtest_summary_snapshot(self) -> BacktestSummarySnapshot:
        return BacktestSummarySnapshot(
            started=True,
            ready=False,
            lifecycle_state="warming",
            tracked_inputs=0,
            tracked_contexts=0,
            tracked_active_replays=0,
            tracked_historical_replays=0,
            last_replay_id=None,
            last_event_type=None,
            last_failure_reason=None,
            readiness_reasons=("no_replay_processed",),
            degraded_reasons=(),
            active_backtest_path="phase20_replay_contour",
            backtest_source="phase20_backtest",
        )


class _ReportingSummarySource:
    async def get_reporting_summary_snapshot(self) -> ReportingSummarySnapshot:
        return ReportingSummarySnapshot(
            catalog_counts=ReportingCatalogCountsSnapshot(
                total_artifacts=2,
                total_bundles=0,
                validation_artifacts=1,
                paper_artifacts=1,
                replay_artifacts=0,
            ),
            last_artifact_snapshot=ReportingLastArtifactSnapshot(
                kind="paper_report",
                status="warming",
                source_layer="paper",
                generated_at=datetime(2026, 3, 25, 10, 0, tzinfo=UTC),
                source_reason_code="paper_warming",
            ),
            last_bundle_snapshot=None,
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
            risk_runtime_source=_RiskRuntimeSource(),
            risk_config_source=_RiskConfigSource(),
            signal_summary_source=_SignalSummarySource(),
            strategy_summary_source=_StrategySummarySource(),
            execution_summary_source=_ExecutionSummarySource(),
            opportunity_summary_source=_OpportunitySummarySource(),
            oms_summary_source=_OmsSummarySource(),
            manager_summary_source=_ManagerSummarySource(),
            validation_summary_source=_ValidationSummarySource(),
            paper_summary_source=_PaperSummarySource(),
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
            risk_runtime_source=_RiskRuntimeSource(),
            risk_config_source=_RiskConfigSource(),
            signal_summary_source=_SignalSummarySource(),
            strategy_summary_source=_StrategySummarySource(),
            execution_summary_source=_ExecutionSummarySource(),
            opportunity_summary_source=_OpportunitySummarySource(),
            oms_summary_source=_OmsSummarySource(),
            manager_summary_source=_ManagerSummarySource(),
            validation_summary_source=_ValidationSummarySource(),
            paper_summary_source=_PaperSummarySource(),
        )
    )

    snapshot = await facade.get_overview_snapshot()

    assert snapshot.health_summary.overall_status == "unhealthy"
    assert "postgresql" in snapshot.health_summary.unhealthy_components


@pytest.mark.asyncio
async def test_overview_facade_builds_risk_summary_snapshot() -> None:
    registry = create_default_module_registry()
    facade = OverviewFacade(
        OverviewCompositionRoot(
            system_status_source=_SystemStatusSource(),
            health_snapshot_source=_HealthSource(),
            pending_approvals_source=_ApprovalsSource(),
            event_summary_source=_EventSource(),
            module_availability_source=_ModuleSource(registry=registry),
            risk_runtime_source=_RiskRuntimeSource(),
            risk_config_source=_RiskConfigSource(),
            signal_summary_source=_SignalSummarySource(),
            strategy_summary_source=_StrategySummarySource(),
            execution_summary_source=_ExecutionSummarySource(),
            opportunity_summary_source=_OpportunitySummarySource(),
            oms_summary_source=_OmsSummarySource(),
            manager_summary_source=_ManagerSummarySource(),
            validation_summary_source=_ValidationSummarySource(),
            paper_summary_source=_PaperSummarySource(),
        )
    )

    snapshot = await facade.get_risk_summary()

    assert snapshot.module_status == "read-only"
    assert snapshot.global_status == "blocked"
    assert snapshot.active_risk_path == "phase5_risk_engine"
    assert snapshot.state_note == "Деградированный режим, ограниченная торговля"
    assert any(item.key == "max_portfolio_r" for item in snapshot.constraints)


@pytest.mark.asyncio
async def test_overview_facade_builds_signals_summary_snapshot() -> None:
    registry = create_default_module_registry()
    facade = OverviewFacade(
        OverviewCompositionRoot(
            system_status_source=_SystemStatusSource(),
            health_snapshot_source=_HealthSource(),
            pending_approvals_source=_ApprovalsSource(),
            event_summary_source=_EventSource(),
            module_availability_source=_ModuleSource(registry=registry),
            risk_runtime_source=_RiskRuntimeSource(),
            risk_config_source=_RiskConfigSource(),
            signal_summary_source=_SignalSummarySource(),
            strategy_summary_source=_StrategySummarySource(),
            execution_summary_source=_ExecutionSummarySource(),
            opportunity_summary_source=_OpportunitySummarySource(),
            oms_summary_source=_OmsSummarySource(),
            manager_summary_source=_ManagerSummarySource(),
            validation_summary_source=_ValidationSummarySource(),
            paper_summary_source=_PaperSummarySource(),
        )
    )

    snapshot = await facade.get_signals_summary()

    assert snapshot.module_status == "read-only"
    assert snapshot.global_status == "warming"
    assert snapshot.active_signal_path == "phase8_signal_contour"
    assert snapshot.freshness_state == "not_surfaced"
    assert any(item.key == "runtime_ready" for item in snapshot.availability)


@pytest.mark.asyncio
async def test_overview_facade_builds_strategy_summary_snapshot() -> None:
    registry = create_default_module_registry()
    facade = OverviewFacade(
        OverviewCompositionRoot(
            system_status_source=_SystemStatusSource(),
            health_snapshot_source=_HealthSource(),
            pending_approvals_source=_ApprovalsSource(),
            event_summary_source=_EventSource(),
            module_availability_source=_ModuleSource(registry=registry),
            risk_runtime_source=_RiskRuntimeSource(),
            risk_config_source=_RiskConfigSource(),
            signal_summary_source=_SignalSummarySource(),
            strategy_summary_source=_StrategySummarySource(),
            execution_summary_source=_ExecutionSummarySource(),
            opportunity_summary_source=_OpportunitySummarySource(),
            oms_summary_source=_OmsSummarySource(),
            manager_summary_source=_ManagerSummarySource(),
            validation_summary_source=_ValidationSummarySource(),
            paper_summary_source=_PaperSummarySource(),
        )
    )

    snapshot = await facade.get_strategy_summary()

    assert snapshot.module_status == "read-only"
    assert snapshot.global_status == "warming"
    assert snapshot.active_strategy_path == "phase9_strategy_contour"
    assert snapshot.strategy_source == "phase9_foundation_strategy"
    assert snapshot.freshness_state == "not_surfaced"
    assert any(item.key == "tracked_context_keys" for item in snapshot.availability)


@pytest.mark.asyncio
async def test_overview_facade_builds_execution_summary_snapshot() -> None:
    registry = create_default_module_registry()
    facade = OverviewFacade(
        OverviewCompositionRoot(
            system_status_source=_SystemStatusSource(),
            health_snapshot_source=_HealthSource(),
            pending_approvals_source=_ApprovalsSource(),
            event_summary_source=_EventSource(),
            module_availability_source=_ModuleSource(registry=registry),
            risk_runtime_source=_RiskRuntimeSource(),
            risk_config_source=_RiskConfigSource(),
            signal_summary_source=_SignalSummarySource(),
            strategy_summary_source=_StrategySummarySource(),
            execution_summary_source=_ExecutionSummarySource(),
            opportunity_summary_source=_OpportunitySummarySource(),
            oms_summary_source=_OmsSummarySource(),
            manager_summary_source=_ManagerSummarySource(),
            validation_summary_source=_ValidationSummarySource(),
            paper_summary_source=_PaperSummarySource(),
        )
    )

    snapshot = await facade.get_execution_summary()

    assert snapshot.module_status == "read-only"
    assert snapshot.global_status == "warming"
    assert snapshot.active_execution_path == "phase10_execution_contour"
    assert snapshot.execution_source == "phase10_foundation_execution"
    assert snapshot.freshness_state == "not_surfaced"
    assert any(item.key == "tracked_context_keys" for item in snapshot.availability)


@pytest.mark.asyncio
async def test_overview_facade_builds_opportunity_summary_snapshot() -> None:
    registry = create_default_module_registry()
    facade = OverviewFacade(
        OverviewCompositionRoot(
            system_status_source=_SystemStatusSource(),
            health_snapshot_source=_HealthSource(),
            pending_approvals_source=_ApprovalsSource(),
            event_summary_source=_EventSource(),
            module_availability_source=_ModuleSource(registry=registry),
            risk_runtime_source=_RiskRuntimeSource(),
            risk_config_source=_RiskConfigSource(),
            signal_summary_source=_SignalSummarySource(),
            strategy_summary_source=_StrategySummarySource(),
            execution_summary_source=_ExecutionSummarySource(),
            opportunity_summary_source=_OpportunitySummarySource(),
            oms_summary_source=_OmsSummarySource(),
            manager_summary_source=_ManagerSummarySource(),
            validation_summary_source=_ValidationSummarySource(),
            paper_summary_source=_PaperSummarySource(),
        )
    )

    snapshot = await facade.get_opportunity_summary()

    assert snapshot.module_status == "read-only"
    assert snapshot.global_status == "warming"
    assert snapshot.active_opportunity_path == "phase11_opportunity_contour"
    assert snapshot.opportunity_source == "phase11_foundation_selection"
    assert snapshot.freshness_state == "not_surfaced"
    assert any(item.key == "tracked_context_keys" for item in snapshot.availability)


@pytest.mark.asyncio
async def test_overview_facade_builds_orchestration_summary_snapshot() -> None:
    registry = create_default_module_registry()
    facade = OverviewFacade(
        OverviewCompositionRoot(
            system_status_source=_SystemStatusSource(),
            health_snapshot_source=_HealthSource(),
            pending_approvals_source=_ApprovalsSource(),
            event_summary_source=_EventSource(),
            module_availability_source=_ModuleSource(registry=registry),
            risk_runtime_source=_RiskRuntimeSource(),
            risk_config_source=_RiskConfigSource(),
            signal_summary_source=_SignalSummarySource(),
            strategy_summary_source=_StrategySummarySource(),
            execution_summary_source=_ExecutionSummarySource(),
            opportunity_summary_source=_OpportunitySummarySource(),
            oms_summary_source=_OmsSummarySource(),
            manager_summary_source=_ManagerSummarySource(),
            validation_summary_source=_ValidationSummarySource(),
            paper_summary_source=_PaperSummarySource(),
            orchestration_summary_source=_OrchestrationSummarySource(),
        )
    )

    snapshot = await facade.get_orchestration_summary()

    assert snapshot.module_status == "read-only"
    assert snapshot.global_status == "warming"
    assert snapshot.active_orchestration_path == "phase12_orchestration_contour"
    assert snapshot.orchestration_source == "phase12_meta_orchestration"
    assert snapshot.freshness_state == "not_surfaced"
    assert any(item.key == "tracked_context_keys" for item in snapshot.availability)


@pytest.mark.asyncio
async def test_overview_facade_builds_position_expansion_summary_snapshot() -> None:
    registry = create_default_module_registry()
    facade = OverviewFacade(
        OverviewCompositionRoot(
            system_status_source=_SystemStatusSource(),
            health_snapshot_source=_HealthSource(),
            pending_approvals_source=_ApprovalsSource(),
            event_summary_source=_EventSource(),
            module_availability_source=_ModuleSource(registry=registry),
            risk_runtime_source=_RiskRuntimeSource(),
            risk_config_source=_RiskConfigSource(),
            signal_summary_source=_SignalSummarySource(),
            strategy_summary_source=_StrategySummarySource(),
            execution_summary_source=_ExecutionSummarySource(),
            opportunity_summary_source=_OpportunitySummarySource(),
            position_expansion_summary_source=_PositionExpansionSummarySource(),
            oms_summary_source=_OmsSummarySource(),
            manager_summary_source=_ManagerSummarySource(),
            validation_summary_source=_ValidationSummarySource(),
            paper_summary_source=_PaperSummarySource(),
        )
    )

    snapshot = await facade.get_position_expansion_summary()

    assert snapshot.module_status == "read-only"
    assert snapshot.global_status == "warming"
    assert snapshot.active_position_expansion_path == "phase13_position_expansion_contour"
    assert snapshot.position_expansion_source == "phase13_position_expansion"
    assert snapshot.freshness_state == "not_surfaced"
    assert any(item.key == "tracked_context_keys" for item in snapshot.availability)


@pytest.mark.asyncio
async def test_overview_facade_builds_portfolio_governor_summary_snapshot() -> None:
    registry = create_default_module_registry()
    facade = OverviewFacade(
        OverviewCompositionRoot(
            system_status_source=_SystemStatusSource(),
            health_snapshot_source=_HealthSource(),
            pending_approvals_source=_ApprovalsSource(),
            event_summary_source=_EventSource(),
            module_availability_source=_ModuleSource(registry=registry),
            risk_runtime_source=_RiskRuntimeSource(),
            risk_config_source=_RiskConfigSource(),
            signal_summary_source=_SignalSummarySource(),
            strategy_summary_source=_StrategySummarySource(),
            execution_summary_source=_ExecutionSummarySource(),
            opportunity_summary_source=_OpportunitySummarySource(),
            oms_summary_source=_OmsSummarySource(),
            manager_summary_source=_ManagerSummarySource(),
            validation_summary_source=_ValidationSummarySource(),
            paper_summary_source=_PaperSummarySource(),
            portfolio_governor_summary_source=_PortfolioGovernorSummarySource(),
        )
    )

    snapshot = await facade.get_portfolio_governor_summary()

    assert snapshot.module_status == "read-only"
    assert snapshot.global_status == "warming"
    assert snapshot.active_portfolio_governor_path == "phase14_portfolio_governor_contour"
    assert snapshot.portfolio_governor_source == "phase14_portfolio_governor"
    assert snapshot.freshness_state == "not_surfaced"
    assert any(item.key == "tracked_context_keys" for item in snapshot.availability)


@pytest.mark.asyncio
async def test_overview_facade_builds_oms_summary_snapshot() -> None:
    registry = create_default_module_registry()
    facade = OverviewFacade(
        OverviewCompositionRoot(
            system_status_source=_SystemStatusSource(),
            health_snapshot_source=_HealthSource(),
            pending_approvals_source=_ApprovalsSource(),
            event_summary_source=_EventSource(),
            module_availability_source=_ModuleSource(registry=registry),
            risk_runtime_source=_RiskRuntimeSource(),
            risk_config_source=_RiskConfigSource(),
            signal_summary_source=_SignalSummarySource(),
            strategy_summary_source=_StrategySummarySource(),
            execution_summary_source=_ExecutionSummarySource(),
            opportunity_summary_source=_OpportunitySummarySource(),
            oms_summary_source=_OmsSummarySource(),
            manager_summary_source=_ManagerSummarySource(),
            validation_summary_source=_ValidationSummarySource(),
            paper_summary_source=_PaperSummarySource(),
        )
    )

    snapshot = await facade.get_oms_summary()

    assert snapshot.module_status == "read-only"
    assert snapshot.global_status == "warming"
    assert snapshot.active_oms_path == "phase16_oms_contour"
    assert snapshot.oms_source == "phase16_oms"
    assert snapshot.freshness_state == "not_surfaced"
    assert any(item.key == "tracked_contexts" for item in snapshot.availability)


@pytest.mark.asyncio
async def test_overview_facade_builds_manager_summary_snapshot() -> None:
    registry = create_default_module_registry()
    facade = OverviewFacade(
        OverviewCompositionRoot(
            system_status_source=_SystemStatusSource(),
            health_snapshot_source=_HealthSource(),
            pending_approvals_source=_ApprovalsSource(),
            event_summary_source=_EventSource(),
            module_availability_source=_ModuleSource(registry=registry),
            risk_runtime_source=_RiskRuntimeSource(),
            risk_config_source=_RiskConfigSource(),
            signal_summary_source=_SignalSummarySource(),
            strategy_summary_source=_StrategySummarySource(),
            execution_summary_source=_ExecutionSummarySource(),
            opportunity_summary_source=_OpportunitySummarySource(),
            oms_summary_source=_OmsSummarySource(),
            manager_summary_source=_ManagerSummarySource(),
            validation_summary_source=_ValidationSummarySource(),
            paper_summary_source=_PaperSummarySource(),
        )
    )

    snapshot = await facade.get_manager_summary()

    assert snapshot.module_status == "read-only"
    assert snapshot.global_status == "warming"
    assert snapshot.active_manager_path == "phase17_manager_contour"
    assert snapshot.manager_source == "phase17_manager"
    assert snapshot.freshness_state == "not_surfaced"
    assert any(item.key == "tracked_contexts" for item in snapshot.availability)


@pytest.mark.asyncio
async def test_overview_facade_builds_validation_summary_snapshot() -> None:
    registry = create_default_module_registry()
    facade = OverviewFacade(
        OverviewCompositionRoot(
            system_status_source=_SystemStatusSource(),
            health_snapshot_source=_HealthSource(),
            pending_approvals_source=_ApprovalsSource(),
            event_summary_source=_EventSource(),
            module_availability_source=_ModuleSource(registry=registry),
            risk_runtime_source=_RiskRuntimeSource(),
            risk_config_source=_RiskConfigSource(),
            signal_summary_source=_SignalSummarySource(),
            strategy_summary_source=_StrategySummarySource(),
            execution_summary_source=_ExecutionSummarySource(),
            opportunity_summary_source=_OpportunitySummarySource(),
            oms_summary_source=_OmsSummarySource(),
            manager_summary_source=_ManagerSummarySource(),
            validation_summary_source=_ValidationSummarySource(),
            paper_summary_source=_PaperSummarySource(),
        )
    )

    snapshot = await facade.get_validation_summary()

    assert snapshot.module_status == "read-only"
    assert snapshot.global_status == "warming"
    assert snapshot.active_validation_path == "phase18_validation_contour"
    assert snapshot.validation_source == "phase18_validation"
    assert snapshot.freshness_state == "not_surfaced"
    assert any(item.key == "tracked_contexts" for item in snapshot.availability)


@pytest.mark.asyncio
async def test_overview_facade_builds_paper_summary_snapshot() -> None:
    registry = create_default_module_registry()
    facade = OverviewFacade(
        OverviewCompositionRoot(
            system_status_source=_SystemStatusSource(),
            health_snapshot_source=_HealthSource(),
            pending_approvals_source=_ApprovalsSource(),
            event_summary_source=_EventSource(),
            module_availability_source=_ModuleSource(registry=registry),
            risk_runtime_source=_RiskRuntimeSource(),
            risk_config_source=_RiskConfigSource(),
            signal_summary_source=_SignalSummarySource(),
            strategy_summary_source=_StrategySummarySource(),
            execution_summary_source=_ExecutionSummarySource(),
            opportunity_summary_source=_OpportunitySummarySource(),
            oms_summary_source=_OmsSummarySource(),
            manager_summary_source=_ManagerSummarySource(),
            validation_summary_source=_ValidationSummarySource(),
            paper_summary_source=_PaperSummarySource(),
        )
    )

    snapshot = await facade.get_paper_summary()

    assert snapshot.module_status == "read-only"
    assert snapshot.global_status == "warming"
    assert snapshot.active_paper_path == "phase19_paper_contour"
    assert snapshot.paper_source == "phase19_paper"
    assert snapshot.freshness_state == "not_surfaced"
    assert any(item.key == "tracked_contexts" for item in snapshot.availability)


@pytest.mark.asyncio
async def test_overview_facade_builds_backtest_summary_snapshot() -> None:
    registry = create_default_module_registry()
    facade = OverviewFacade(
        OverviewCompositionRoot(
            system_status_source=_SystemStatusSource(),
            health_snapshot_source=_HealthSource(),
            pending_approvals_source=_ApprovalsSource(),
            event_summary_source=_EventSource(),
            module_availability_source=_ModuleSource(registry=registry),
            risk_runtime_source=_RiskRuntimeSource(),
            risk_config_source=_RiskConfigSource(),
            signal_summary_source=_SignalSummarySource(),
            strategy_summary_source=_StrategySummarySource(),
            execution_summary_source=_ExecutionSummarySource(),
            opportunity_summary_source=_OpportunitySummarySource(),
            oms_summary_source=_OmsSummarySource(),
            manager_summary_source=_ManagerSummarySource(),
            validation_summary_source=_ValidationSummarySource(),
            paper_summary_source=_PaperSummarySource(),
            backtest_summary_source=_BacktestSummarySource(),
        )
    )

    snapshot = await facade.get_backtest_summary()

    assert snapshot.module_status == "read-only"
    assert snapshot.global_status == "warming"
    assert snapshot.active_backtest_path == "phase20_replay_contour"
    assert snapshot.backtest_source == "phase20_backtest"
    assert snapshot.freshness_state == "not_surfaced"
    assert any(item.key == "tracked_inputs" for item in snapshot.availability)


@pytest.mark.asyncio
async def test_overview_facade_builds_reporting_summary_snapshot() -> None:
    registry = create_default_module_registry()
    facade = OverviewFacade(
        OverviewCompositionRoot(
            system_status_source=_SystemStatusSource(),
            health_snapshot_source=_HealthSource(),
            pending_approvals_source=_ApprovalsSource(),
            event_summary_source=_EventSource(),
            module_availability_source=_ModuleSource(registry=registry),
            risk_runtime_source=_RiskRuntimeSource(),
            risk_config_source=_RiskConfigSource(),
            signal_summary_source=_SignalSummarySource(),
            strategy_summary_source=_StrategySummarySource(),
            execution_summary_source=_ExecutionSummarySource(),
            opportunity_summary_source=_OpportunitySummarySource(),
            oms_summary_source=_OmsSummarySource(),
            manager_summary_source=_ManagerSummarySource(),
            validation_summary_source=_ValidationSummarySource(),
            paper_summary_source=_PaperSummarySource(),
            backtest_summary_source=_BacktestSummarySource(),
            reporting_summary_source=_ReportingSummarySource(),
        )
    )

    snapshot = await facade.get_reporting_summary()

    assert snapshot.module_status == "read-only"
    assert snapshot.global_status == "warming"
    assert snapshot.catalog_counts.total_artifacts == 2
    assert snapshot.catalog_counts.paper_artifacts == 1
    assert snapshot.last_artifact_snapshot is not None
    assert snapshot.last_artifact_snapshot.kind == "paper_report"
    assert snapshot.summary_reason == "paper_warming"

"""
Production composition root для CRYPTOTEHNOLOG.

Этот модуль является официальной точкой сборки production runtime
в рамках Шага 2 фазы P_5_1.
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
import os
from typing import TYPE_CHECKING, Any, cast
from urllib.error import URLError


def _spot_snapshot_trade_count(snapshot: object, attr: str) -> int:
    value = getattr(snapshot, attr, 0)
    return int(value) if isinstance(value, int) else 0


def _spot_snapshot_datetime(snapshot: object, attr: str) -> datetime | None:
    value = getattr(snapshot, attr, None)
    return value if isinstance(value, datetime) else None


def _spot_snapshot_persisted_total(snapshot: object) -> int:
    value = getattr(snapshot, "persisted_trade_count_24h", 0)
    return int(value) if isinstance(value, int) else 0

from cryptotechnolog.analysis.runtime import SharedAnalysisRuntime, create_shared_analysis_runtime
from cryptotechnolog.config.logging import configure_logging, get_logger
from cryptotechnolog.config.settings import (
    Settings,
    get_settings,
    validate_settings,
)
from cryptotechnolog.config.settings import (
    persist_settings_updates as update_settings,
)
from cryptotechnolog.core.database import DatabaseManager, set_database
from cryptotechnolog.core.enhanced_event_bus import EnhancedEventBus
from cryptotechnolog.core.event import Event, SystemEventType
from cryptotechnolog.core.global_instances import set_event_bus
from cryptotechnolog.core.health import (
    HealthChecker,
    HealthStatus,
    SystemHealth,
    init_health_checker,
)
from cryptotechnolog.core.listeners import (
    PHASE5_RISK_PATH,
    build_listener_registry,
    get_risk_path_for_listener_name,
)
from cryptotechnolog.core.listeners.base import ListenerRegistry
from cryptotechnolog.core.metrics import MetricsCollector, init_metrics
from cryptotechnolog.core.redis_manager import RedisManager, set_redis_manager
from cryptotechnolog.core.system_controller import ShutdownResult, StartupResult, SystemController
from cryptotechnolog.execution import (
    ExecutionEventSource,
    ExecutionEventType,
    ExecutionRuntime,
    build_execution_event,
    create_execution_runtime,
)
from cryptotechnolog.intelligence.runtime import IntelligenceRuntime, create_intelligence_runtime
from cryptotechnolog.live_feed import (
    BybitAdmissionSnapshot,
    BybitDiscoverySnapshot,
    BybitLinearV2Transport,
    BybitLinearV2TransportConfig,
    BybitMarketDataConnector,
    BybitMarketDataConnectorConfig,
    BybitProjectionSnapshot,
    BybitSpotMarketDataConnector,
    BybitSpotMarketDataConnectorConfig,
    BybitSpotV2Transport,
    BybitSpotV2LiveTradeLedgerRepository,
    BybitSpotV2DiagnosticsService,
    BybitSpotV2RecoveryCoordinator,
    BybitSpotV2TransportConfig,
    BybitSpotV2PersistedQueryService,
    BybitSpotV2ReconciliationService,
    BybitTradeTruthSymbolSnapshot,
    BybitTradeTruthSnapshot,
    BybitTransportSnapshot,
    BybitUniverseDiscoveryConfig,
    create_bybit_linear_v2_transport,
    create_bybit_market_data_connector,
    create_bybit_spot_market_data_connector,
    create_bybit_spot_v2_transport,
    discover_bybit_universe,
    run_bybit_spot_v2_archive_loader,
)
import cryptotechnolog.live_feed.bybit_spot_module as bybit_spot_module_lib
from cryptotechnolog.live_feed.bybit_spot_module import (
    BybitSpotModule,
    BybitSpotModuleDeps,
)
from cryptotechnolog.live_feed.bybit_trade_count_truth_model import (
    FINAL_BYBIT_TRADE_COUNT_TRUTH_OWNERSHIP,
)
from cryptotechnolog.live_feed.bybit_trade_ledger_persistence import BybitTradeLedgerRepository
from cryptotechnolog.live_feed.bybit_trade_ledger_query import (
    BybitTradeLedgerTradeCountQueryService,
)
from cryptotechnolog.live_feed.bybit_spot_v2_persisted_query import (
    _max_datetime,
    _min_datetime,
)
from cryptotechnolog.manager import (
    ManagerEventSource,
    ManagerEventType,
    ManagerRuntime,
    build_manager_event,
    create_manager_runtime,
)
from cryptotechnolog.market_data import MarketDataTimeframe
from cryptotechnolog.market_data.events import BarCompletedPayload
from cryptotechnolog.market_data.runtime import MarketDataRuntime, create_market_data_runtime
from cryptotechnolog.oms import (
    OmsEventSource,
    OmsRuntime,
    build_oms_event,
    create_oms_runtime,
)
from cryptotechnolog.opportunity import (
    OpportunityEventSource,
    OpportunityEventType,
    OpportunityRuntime,
    build_opportunity_event,
    create_opportunity_runtime,
)
from cryptotechnolog.orchestration import (
    OrchestrationEventSource,
    OrchestrationEventType,
    OrchestrationRuntime,
    build_orchestration_event,
    create_orchestration_runtime,
)
from cryptotechnolog.paper import (
    PaperEventSource,
    PaperRuntime,
    build_paper_event,
    create_paper_runtime,
)
from cryptotechnolog.portfolio_governor import (
    PortfolioGovernorEventSource,
    PortfolioGovernorEventType,
    PortfolioGovernorRuntime,
    build_portfolio_governor_event,
    create_portfolio_governor_runtime,
)
from cryptotechnolog.position_expansion import (
    PositionExpansionEventSource,
    PositionExpansionEventType,
    PositionExpansionRuntime,
    build_position_expansion_event,
    create_position_expansion_runtime,
)
from cryptotechnolog.protection import (
    ProtectionEventSource,
    ProtectionEventType,
    ProtectionRuntime,
    build_protection_event,
    create_protection_runtime,
)
from cryptotechnolog.risk.runtime import RiskRuntime, create_risk_runtime
from cryptotechnolog.runtime_identity import RuntimeIdentity, build_runtime_identity
from cryptotechnolog.signals import (
    SignalEventSource,
    SignalEventType,
    SignalRuntime,
    build_signal_event,
    create_signal_runtime,
)
from cryptotechnolog.strategy import (
    StrategyEventSource,
    StrategyEventType,
    StrategyRuntime,
    build_strategy_event,
    create_strategy_runtime,
)
from cryptotechnolog.validation import (
    ValidationEventSource,
    ValidationEventType,
    ValidationRuntime,
    build_validation_event,
    create_validation_runtime,
)

if TYPE_CHECKING:
    from cryptotechnolog.analysis import RiskDerivedInputsSnapshot
    from cryptotechnolog.market_data import OrderBookSnapshotContract
    from cryptotechnolog.oms import OmsOrderRecord


class ProductionBootstrapError(RuntimeError):
    """Ошибка production bootstrap path."""


_BYBIT_CONNECTOR_JOIN_TIMEOUT_SECONDS = 1.0
@dataclass(slots=True, frozen=True)
class _ResolvedBybitConnectorScope:
    symbols: tuple[str, ...]
    truth: _BybitConnectorScopeTruth


@dataclass(slots=True, frozen=True)
class _BybitConnectorScopeTruth:
    scope_mode: str
    trade_count_filter_minimum: int
    discovery_status: str
    total_instruments_discovered: int | None = None
    instruments_passed_coarse_filter: int | None = None
    instruments_passed_final_filter: int | None = None
    discovery_error: str | None = None
    discovery_signature: tuple[object, ...] | None = None
    coarse_selected_symbols: tuple[str, ...] = ()
    coarse_selected_quote_volume_24h_usd_by_symbol: tuple[tuple[str, str], ...] = ()
    selected_symbols: tuple[str, ...] = ()
    selected_quote_volume_24h_usd_by_symbol: tuple[tuple[str, str], ...] = ()
    selected_trade_count_24h_by_symbol: tuple[tuple[str, int], ...] = ()
    selected_trade_count_24h_is_final: bool | None = None
    selected_trade_count_24h_empty_scope_confirmed: bool | None = None

    def as_diagnostics(self) -> dict[str, object]:
        return {
            "scope_mode": self.scope_mode,
            "trade_count_filter_minimum": self.trade_count_filter_minimum,
            "discovery_status": self.discovery_status,
            "discovery_error": self.discovery_error,
            "total_instruments_discovered": self.total_instruments_discovered,
            "instruments_passed_coarse_filter": self.instruments_passed_coarse_filter,
            "instruments_passed_final_filter": self.instruments_passed_final_filter,
        }


@dataclass(slots=True, frozen=True)
class _BybitRuntimeApplyTruth:
    desired_scope_mode: str
    desired_trade_count_filter_minimum: int
    applied_scope_mode: str | None
    applied_trade_count_filter_minimum: int | None
    policy_apply_status: str
    policy_apply_reason: str | None = None


def _resolve_spot_primary_lifecycle_state(
    *,
    desired_running: bool,
    transport_status: str,
    trade_seen: bool,
    orderbook_seen: bool,
    trade_ingest_count: int,
    orderbook_ingest_count: int,
) -> str:
    if not desired_running:
        return "stopped"
    if transport_status in {"idle", "connecting"}:
        return "starting"
    if transport_status != "connected":
        return "degraded"
    if trade_seen and trade_ingest_count > 0:
        return "connected_live"
    if orderbook_seen and orderbook_ingest_count > 0:
        return "connected_live"
    return "connected_no_flow"


@dataclass(slots=True, frozen=True)
class ProductionBootstrapPolicy:
    """Политика сборки production composition root."""

    test_mode: bool = False
    enable_event_bus_persistence: bool = True
    enable_risk_persistence: bool = True
    active_risk_path: str = PHASE5_RISK_PATH
    include_legacy_risk_listener: bool = False


@dataclass(slots=True)
class ProductionRuntime:
    """Собранный production runtime платформы."""

    settings: Settings
    policy: ProductionBootstrapPolicy
    identity: RuntimeIdentity
    db_manager: DatabaseManager
    redis_manager: RedisManager
    metrics_collector: MetricsCollector
    health_checker: HealthChecker
    event_bus: EnhancedEventBus
    listener_registry: ListenerRegistry
    controller: SystemController
    risk_runtime: RiskRuntime
    market_data_runtime: MarketDataRuntime
    shared_analysis_runtime: SharedAnalysisRuntime
    intelligence_runtime: IntelligenceRuntime
    signal_runtime: SignalRuntime
    strategy_runtime: StrategyRuntime
    execution_runtime: ExecutionRuntime
    oms_runtime: OmsRuntime
    opportunity_runtime: OpportunityRuntime
    orchestration_runtime: OrchestrationRuntime
    position_expansion_runtime: PositionExpansionRuntime
    portfolio_governor_runtime: PortfolioGovernorRuntime
    protection_runtime: ProtectionRuntime
    manager_runtime: ManagerRuntime
    validation_runtime: ValidationRuntime
    paper_runtime: PaperRuntime
    bybit_market_data_connector: BybitMarketDataConnector | None = None
    bybit_market_data_connector_task: asyncio.Task[None] | None = None
    bybit_market_data_scope_summary: _BybitConnectorScopeTruth | None = None
    bybit_market_data_apply_truth: _BybitRuntimeApplyTruth | None = None
    bybit_spot_market_data_connector: BybitSpotMarketDataConnector | None = None
    bybit_spot_market_data_connector_task: asyncio.Task[None] | None = None
    bybit_spot_market_data_scope_summary: _BybitConnectorScopeTruth | None = None
    bybit_spot_market_data_apply_truth: _BybitRuntimeApplyTruth | None = None
    bybit_linear_v2_transport: BybitLinearV2Transport | None = None
    bybit_linear_v2_transport_task: asyncio.Task[None] | None = None
    bybit_spot_v2_transport: BybitSpotV2Transport | None = None
    bybit_spot_v2_transport_task: asyncio.Task[None] | None = None
    bybit_spot_v2_recovery: BybitSpotV2RecoveryCoordinator | None = None
    bybit_spot_v2_recovery_task: asyncio.Task[None] | None = None
    bybit_spot_module: BybitSpotModule | None = None
    _runtime_health_refresh_task: asyncio.Task[None] | None = None
    _background_connector_shutdown_tasks: set[asyncio.Task[None]] = field(default_factory=set)
    startup_result: StartupResult | None = None
    shutdown_result: ShutdownResult | None = None
    last_health: SystemHealth | None = None
    _started: bool = False
    _post_start_bringup_task: asyncio.Task[None] | None = None

    @property
    def is_started(self) -> bool:
        """Проверить, поднят ли runtime."""
        return self._started

    async def await_post_start_bringup(self, *, timeout_seconds: float | None = None) -> None:
        task = self._post_start_bringup_task
        if task is None or task.done():
            return
        awaitable = asyncio.shield(task)
        if timeout_seconds is None:
            await awaitable
            return
        await asyncio.wait_for(awaitable, timeout=timeout_seconds)

    def get_bybit_connector_screen_projection(self) -> dict[str, object]:
        return _build_bybit_connector_screen_projection(
            connector=self.bybit_market_data_connector,
            exchange="bybit",
            enabled=bool(getattr(self.settings, "bybit_market_data_connector_enabled", False)),
            scope_truth=self.bybit_market_data_scope_summary,
            apply_truth=self.bybit_market_data_apply_truth,
        )

    def get_bybit_spot_connector_screen_projection(self) -> dict[str, object]:
        return self.bybit_spot_module.get_connector_screen_projection()

    async def _run_bybit_spot_v2_finalized_startup(self) -> None:
        await self.bybit_spot_module.run_finalized_startup()

    def _schedule_bybit_spot_v2_finalized_startup(self) -> None:
        self.bybit_spot_module.schedule_finalized_startup()

    def _is_bybit_spot_trade_truth_coverage_incomplete(self) -> bool:
        return self.bybit_spot_module.is_trade_truth_coverage_incomplete()

    def _is_bybit_spot_snapshot_coverage_incomplete(
        self,
        *,
        coverage_status: str,
    ) -> bool:
        return self.bybit_spot_module.is_snapshot_coverage_incomplete(
            coverage_status=coverage_status,
        )

    def _resolve_bybit_spot_persistence_coverage_status(
        self,
        *,
        live_trade_count_24h: int,
        archive_trade_count_24h: int,
    ) -> str:
        return self.bybit_spot_module.resolve_persistence_coverage_status(
            live_trade_count_24h=live_trade_count_24h,
            archive_trade_count_24h=archive_trade_count_24h,
        )

    def _should_retain_spot_symbol_during_incomplete_coverage(
        self,
        *,
        symbol: str,
        coverage_status: str,
    ) -> bool:
        return self.bybit_spot_module.should_retain_symbol_during_incomplete_coverage(
            symbol=symbol,
            coverage_status=coverage_status,
        )

    def _tick_bybit_spot_final_scope_refresh(self) -> None:
        self.bybit_spot_module.tick_final_scope_refresh()

    async def _run_bybit_spot_v2_scope_refresh_loop(self) -> None:
        await self.bybit_spot_module.run_scope_refresh_loop()

    def _ensure_bybit_spot_v2_scope_refresh_loop(self) -> None:
        self.bybit_spot_module.ensure_scope_refresh_loop()

    def get_runtime_diagnostics(self) -> dict[str, Any]:
        """Вернуть operator-facing runtime diagnostics."""
        diagnostics = dict(self.health_checker.get_runtime_diagnostics())
        diagnostics["bybit_market_data_connector"] = self.get_bybit_connector_screen_projection()
        diagnostics["bybit_spot_market_data_connector"] = (
            self.get_bybit_spot_connector_screen_projection()
        )
        diagnostics["bybit_linear_v2_transport"] = self.get_bybit_linear_v2_transport_diagnostics()
        diagnostics["bybit_spot_v2_transport"] = self.get_bybit_spot_v2_transport_diagnostics()
        diagnostics["bybit_spot_v2_recovery"] = self.get_bybit_spot_v2_recovery_diagnostics()
        return diagnostics

    def get_bybit_linear_v2_transport_diagnostics(self) -> dict[str, object]:
        enabled = _is_bybit_linear_v2_transport_enabled()
        if self.bybit_linear_v2_transport is None:
            return _build_disabled_bybit_linear_v2_transport_diagnostics(enabled=enabled)
        return self.bybit_linear_v2_transport.get_transport_diagnostics()

    def get_bybit_spot_v2_transport_diagnostics(self) -> dict[str, object]:
        enabled = _is_bybit_spot_v2_transport_enabled(settings=self.settings)
        if self.bybit_spot_v2_transport is None:
            return _build_disabled_bybit_spot_v2_transport_diagnostics(enabled=enabled)
        return self.bybit_spot_v2_transport.get_transport_diagnostics()

    def get_bybit_spot_v2_recovery_diagnostics(self) -> dict[str, object]:
        enabled = _is_bybit_spot_v2_recovery_enabled(settings=self.settings)
        if self.bybit_spot_v2_recovery is None:
            return _build_disabled_bybit_spot_v2_recovery_diagnostics(enabled=enabled)
        return self.bybit_spot_v2_recovery.get_recovery_diagnostics()

    def get_bybit_spot_runtime_status(self) -> dict[str, object]:
        return self.bybit_spot_module.get_runtime_status()

    async def get_bybit_spot_product_snapshot(self) -> dict[str, object]:
        return await self.bybit_spot_module.get_product_snapshot()

    async def get_bybit_spot_v2_recovery_diagnostics_async(self) -> dict[str, object]:
        enabled = _is_bybit_spot_v2_recovery_enabled(settings=self.settings)
        if self.bybit_spot_v2_recovery is None:
            return _build_disabled_bybit_spot_v2_recovery_diagnostics(enabled=enabled)
        return await self.bybit_spot_v2_recovery.get_recovery_diagnostics_async()

    async def get_bybit_spot_v2_compact_diagnostics(
        self,
        *,
        symbols: tuple[str, ...] | None = None,
        observed_at: datetime | None = None,
        window_hours: int = 24,
    ) -> dict[str, object]:
        resolved_symbols = symbols or _resolve_bybit_spot_v2_compact_diagnostics_symbols(
            settings=self.settings,
            transport=self.bybit_spot_v2_transport,
        )
        service = BybitSpotV2DiagnosticsService(
            persisted_query_service=BybitSpotV2PersistedQueryService(self.db_manager),
            reconciliation_service=BybitSpotV2ReconciliationService(
                persisted_query_service=BybitSpotV2PersistedQueryService(self.db_manager),
            ),
            transport_diagnostics_provider=self.get_bybit_spot_v2_transport_diagnostics,
            recovery_diagnostics_provider=self.get_bybit_spot_v2_recovery_diagnostics_async,
            symbol_volume_24h_provider=self._get_bybit_spot_v2_symbol_volume_24h_by_symbol,
        )
        snapshot = await service.build_snapshot(
            symbols=resolved_symbols,
            observed_at=observed_at,
            window_hours=window_hours,
        )
        return snapshot.as_dict()

    def _get_bybit_spot_v2_symbol_volume_24h_by_symbol(
        self,
        symbols: Sequence[str],
    ) -> dict[str, str | None]:
        scope_truth = self.bybit_spot_market_data_scope_summary
        if scope_truth is None:
            return {}
        volume_by_symbol = dict(scope_truth.selected_quote_volume_24h_usd_by_symbol)
        return {
            str(symbol): (str(volume_by_symbol[str(symbol)]) if str(symbol) in volume_by_symbol else None)
            for symbol in symbols
        }

    async def startup(self, *, defer_post_start_bringup: bool = False) -> StartupResult:
        """Поднять production runtime через единый composition root."""
        logger = get_logger(__name__)
        logger.info(
            "Старт production composition root",
            bootstrap_module=self.identity.bootstrap_module,
            bootstrap_mode=self.identity.bootstrap_mode,
            version=self.identity.version,
            config_identity=self.identity.config_identity,
            config_revision=self.identity.config_revision,
            active_risk_path=self.identity.active_risk_path,
            legacy_risk_listener_enabled=self.policy.include_legacy_risk_listener,
        )
        self._update_runtime_diagnostics(
            runtime_started=False,
            runtime_ready=False,
            startup_state="starting",
            shutdown_state="not_shutting_down",
            failure_reason=None,
            degraded_reasons=[],
        )

        try:
            startup_stage_timings: dict[str, int] = {}
            controller_started_at = datetime.now(UTC)
            result = await self.controller.startup()
            startup_stage_timings["controller_startup_ms"] = int(
                (datetime.now(UTC) - controller_started_at).total_seconds() * 1000
            )
            self.startup_result = result
            if not result.success:
                reason = result.error or "Startup завершился неуспешно"
                self._update_runtime_diagnostics(
                    runtime_started=False,
                    runtime_ready=False,
                    startup_state="failed",
                    failure_reason=reason,
                )
                logger.error(
                    "Production runtime startup заблокирован",
                    bootstrap_module=self.identity.bootstrap_module,
                    startup_phase=result.phase_reached.value,
                    failure_reason=reason,
                    config_identity=self.identity.config_identity,
                    config_revision=self.identity.config_revision,
                    active_risk_path=self.identity.active_risk_path,
                )
                raise ProductionBootstrapError(reason)

            if self.redis_manager.redis is not None:
                self.metrics_collector.set_redis(self.redis_manager.redis)

            self._started = True
            if defer_post_start_bringup:
                self._update_runtime_diagnostics(
                    runtime_started=True,
                    runtime_ready=False,
                    startup_state="post_start_bringup",
                    shutdown_state="not_shutting_down",
                    failure_reason=None,
                    degraded_reasons=[],
                    startup_stage_timings=startup_stage_timings,
                )
                self._schedule_post_start_bringup(
                    startup_result=result,
                    startup_stage_timings=startup_stage_timings,
                )
                logger.info(
                    "Production runtime переведён в background post-start bring-up",
                    startup_phase=result.phase_reached.value,
                    controller_startup_ms=startup_stage_timings.get("controller_startup_ms"),
                )
                return result

            connector_started_at = datetime.now(UTC)
            await self._start_opt_in_market_data_connectors()
            startup_stage_timings["opt_in_connector_startup_ms"] = int(
                (datetime.now(UTC) - connector_started_at).total_seconds() * 1000
            )

            validation_started_at = datetime.now(UTC)
            await self._validate_started_runtime()
            self.event_bus.seal_risk_path_policy()
            startup_stage_timings["post_start_validation_ms"] = int(
                (datetime.now(UTC) - validation_started_at).total_seconds() * 1000
            )
            health_started_at = datetime.now(UTC)
            self.last_health = await self.health_checker.check_system()
            startup_stage_timings["health_check_ms"] = int(
                (datetime.now(UTC) - health_started_at).total_seconds() * 1000
            )
            degraded_reasons = self._collect_degraded_reasons(self.last_health)

            self._update_runtime_diagnostics(
                runtime_started=True,
                runtime_ready=not degraded_reasons,
                startup_state="ready" if not degraded_reasons else "degraded",
                shutdown_state="not_shutting_down",
                failure_reason=None,
                degraded_reasons=degraded_reasons,
                startup_stage_timings=startup_stage_timings,
            )

            logger_method = logger.info if not degraded_reasons else logger.warning
            logger_method(
                "Production runtime успешно поднят",
                startup_phase=result.phase_reached.value,
                duration_ms=result.duration_ms,
                initialized_components=result.components_initialized,
                readiness_status="ready" if not degraded_reasons else "not_ready",
                degraded_reasons=degraded_reasons,
                active_risk_path=self.identity.active_risk_path,
                bootstrap_mode=self.identity.bootstrap_mode,
                version=self.identity.version,
                config_identity=self.identity.config_identity,
                config_revision=self.identity.config_revision,
            )
            return result
        except Exception as exc:
            if self.startup_result is None or self.startup_result.success:
                self._update_runtime_diagnostics(
                    runtime_started=False,
                    runtime_ready=False,
                    startup_state="failed",
                    failure_reason=str(exc),
                )
            logger.error(
                "Production runtime startup завершился ошибкой",
                bootstrap_module=self.identity.bootstrap_module,
                active_risk_path=self.identity.active_risk_path,
                config_identity=self.identity.config_identity,
                config_revision=self.identity.config_revision,
                failure_reason=str(exc),
            )
            raise

    async def shutdown(
        self,
        force: bool = False,
        *,
        preserve_startup_failure: bool = False,
    ) -> ShutdownResult:
        """Корректно остановить production runtime."""
        logger = get_logger(__name__)
        diagnostics_before_shutdown = self.get_runtime_diagnostics()
        failure_reason = diagnostics_before_shutdown.get("failure_reason")
        startup_failed = (
            diagnostics_before_shutdown.get("startup_state") == "failed"
            and failure_reason is not None
        )

        logger.info(
            "Остановка production runtime",
            bootstrap_module=self.identity.bootstrap_module,
            force=force,
            active_risk_path=self.identity.active_risk_path,
            config_identity=self.identity.config_identity,
            config_revision=self.identity.config_revision,
            preserve_startup_failure=preserve_startup_failure,
        )
        self._update_runtime_diagnostics(
            shutdown_state="stopping",
            runtime_ready=False,
        )

        await self._stop_opt_in_market_data_connectors()
        if self._post_start_bringup_task is not None:
            self._post_start_bringup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._post_start_bringup_task
            self._post_start_bringup_task = None
        if self._runtime_health_refresh_task is not None:
            self._runtime_health_refresh_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._runtime_health_refresh_task
            self._runtime_health_refresh_task = None
        await self._cancel_background_connector_shutdown_tasks()
        shutdown_result = await self.controller.shutdown(force=force)
        self.shutdown_result = shutdown_result

        await self._ensure_component_cleanup()
        self._started = False
        self.last_health = await self.health_checker.check_system()
        if preserve_startup_failure and startup_failed:
            self._update_runtime_diagnostics(
                runtime_started=False,
                runtime_ready=False,
                startup_state="failed",
                shutdown_state=shutdown_result.phase_reached.value,
                failure_reason=failure_reason,
                degraded_reasons=["startup_failed_cleanup"],
            )
        else:
            self._update_runtime_diagnostics(
                runtime_started=False,
                runtime_ready=False,
                startup_state="stopped",
                shutdown_state=shutdown_result.phase_reached.value,
                degraded_reasons=["runtime_stopped"],
                failure_reason=None,
            )

        logger.info(
            "Production runtime остановлен",
            success=shutdown_result.success,
            duration_ms=shutdown_result.duration_ms,
            shutdown_phase=shutdown_result.phase_reached.value,
            readiness_status="not_ready",
            active_risk_path=self.identity.active_risk_path,
            version=self.identity.version,
            config_identity=self.identity.config_identity,
            config_revision=self.identity.config_revision,
            startup_state=self.get_runtime_diagnostics()["startup_state"],
        )
        return shutdown_result

    async def _validate_started_runtime(self) -> None:  # noqa: PLR0912
        """Проверить обязательные зависимости после startup."""
        if not self.db_manager.is_connected:
            raise ProductionBootstrapError("Production bootstrap не поднял подключение к БД")
        if not self.redis_manager.is_connected:
            raise ProductionBootstrapError("Production bootstrap не поднял подключение к Redis")
        if self.event_bus.listener_registry is not self.listener_registry:
            raise ProductionBootstrapError("Production bootstrap потерял явный ListenerRegistry")
        if not self.risk_runtime.is_started:
            raise ProductionBootstrapError("Phase 5 risk runtime не подключён к Event Bus")
        if self.policy.enable_event_bus_persistence and not self.event_bus.enable_persistence:
            raise ProductionBootstrapError("Event Bus persistence выключилась во время startup")
        if self.policy.enable_risk_persistence and self.risk_runtime.persistence_repository is None:
            raise ProductionBootstrapError(
                "Risk runtime persistence не была подключена в production bootstrap"
            )
        # Upstream truth providers Phase 6-8 остаются startup-degradable:
        # operator truth видит их как not_ready/degraded, но startup не
        # проваливается только из-за их warming/missing state.
        if not self.strategy_runtime.is_started:
            raise ProductionBootstrapError("Phase 9 strategy runtime не подключён к Event Bus")
        if not self.execution_runtime.is_started:
            raise ProductionBootstrapError("Phase 10 execution runtime не подключён к Event Bus")
        if not self.oms_runtime.is_started:
            raise ProductionBootstrapError("Phase 16 OMS runtime не подключён к Event Bus")
        if not self.opportunity_runtime.is_started:
            raise ProductionBootstrapError("Phase 11 opportunity runtime не подключён к Event Bus")
        if not self.orchestration_runtime.is_started:
            raise ProductionBootstrapError(
                "Phase 12 orchestration runtime не подключён к Event Bus"
            )
        if not self.position_expansion_runtime.is_started:
            raise ProductionBootstrapError(
                "Phase 13 position-expansion runtime не подключён к Event Bus"
            )
        if not self.portfolio_governor_runtime.is_started:
            raise ProductionBootstrapError(
                "Phase 14 portfolio-governor runtime не подключён к Event Bus"
            )
        if not self.protection_runtime.is_started:
            raise ProductionBootstrapError("Phase 15 protection runtime не подключён к Event Bus")
        if not self.manager_runtime.is_started:
            raise ProductionBootstrapError("Phase 17 manager runtime не подключён к Event Bus")
        if not self.validation_runtime.is_started:
            raise ProductionBootstrapError("Phase 18 validation runtime не подключён к Event Bus")
        if not self.paper_runtime.is_started:
            raise ProductionBootstrapError("Phase 19 paper runtime не подключён к Event Bus")
        registered_risk_paths = {
            resolved_path
            for listener in self.listener_registry.all_listeners
            if (resolved_path := get_risk_path_for_listener_name(listener.name)) is not None
        }
        if registered_risk_paths != {self.identity.active_risk_path}:
            raise ProductionBootstrapError(
                "Production runtime содержит недопустимый набор risk path: "
                f"{sorted(registered_risk_paths)}"
            )
        if self.event_bus.active_risk_path != self.identity.active_risk_path:
            raise ProductionBootstrapError("Event Bus настроен на неверный active risk path")
        if not self.event_bus.enforce_single_risk_path:
            raise ProductionBootstrapError(
                "Production Event Bus не форсирует single-risk-path policy"
            )

    async def _ensure_component_cleanup(self) -> None:  # noqa: PLR0912,PLR0915
        """Дочистить компоненты, если контроллер не остановил их сам."""
        if self.risk_runtime.is_started:
            with contextlib.suppress(Exception):
                await self.risk_runtime.stop()
        if self.shared_analysis_runtime.is_started:
            with contextlib.suppress(Exception):
                await self.shared_analysis_runtime.stop()
        if self.signal_runtime.is_started:
            with contextlib.suppress(Exception):
                await self.signal_runtime.stop()
        if self.strategy_runtime.is_started:
            with contextlib.suppress(Exception):
                await self.strategy_runtime.stop()
        if self.execution_runtime.is_started:
            with contextlib.suppress(Exception):
                await self.execution_runtime.stop()
        if self.oms_runtime.is_started:
            with contextlib.suppress(Exception):
                await self.oms_runtime.stop()
        if self.opportunity_runtime.is_started:
            with contextlib.suppress(Exception):
                await self.opportunity_runtime.stop()
        if self.orchestration_runtime.is_started:
            with contextlib.suppress(Exception):
                await self.orchestration_runtime.stop()
        if self.position_expansion_runtime.is_started:
            with contextlib.suppress(Exception):
                await self.position_expansion_runtime.stop()
        if self.portfolio_governor_runtime.is_started:
            with contextlib.suppress(Exception):
                await self.portfolio_governor_runtime.stop()
        if self.protection_runtime.is_started:
            with contextlib.suppress(Exception):
                await self.protection_runtime.stop()
        if self.manager_runtime.is_started:
            with contextlib.suppress(Exception):
                await self.manager_runtime.stop()
        if self.validation_runtime.is_started:
            with contextlib.suppress(Exception):
                await self.validation_runtime.stop()
        if self.paper_runtime.is_started:
            with contextlib.suppress(Exception):
                await self.paper_runtime.stop()
        await self._stop_opt_in_market_data_connectors()
        if getattr(self.event_bus, "pending_tasks", None):
            with contextlib.suppress(Exception):
                await self.event_bus.shutdown()
        if self.redis_manager.is_connected:
            with contextlib.suppress(Exception):
                await self.redis_manager.disconnect()
        if self.db_manager.is_connected:
            with contextlib.suppress(Exception):
                await self.db_manager.disconnect()

    def _update_runtime_diagnostics(self, **updates: Any) -> dict[str, Any]:
        """Синхронизировать runtime diagnostics с composition root."""
        return self.health_checker.set_runtime_diagnostics(**updates)

    async def _start_opt_in_market_data_connectors(self) -> None:
        """Поднять узкий canonical live-feed connector path после старта runtime components."""
        await self.bybit_spot_module.start_runtime()
        await self._start_bybit_linear_v2_transport()

    async def _start_bybit_market_data_connector(self) -> None:
        """Поднять только Bybit perpetual contour без вмешательства в другие connectors."""
        if (
            self.bybit_market_data_connector_task is not None
            and self.bybit_market_data_connector_task.done()
        ):
            self.bybit_market_data_connector_task = None
        if (
            self.bybit_market_data_connector is not None
            and self.bybit_market_data_connector_task is None
        ):
            self.bybit_market_data_connector.set_ledger_trade_count_query_service(
                _build_canonical_bybit_trade_ledger_query_service(db_manager=self.db_manager)
            )
            self.bybit_market_data_connector_task = asyncio.create_task(
                self.bybit_market_data_connector.run(),
                name="production_bybit_market_data_connector",
            )

    async def _start_bybit_spot_market_data_connector(self) -> None:
        await self.bybit_spot_module.start_market_data_connector()

    async def _start_bybit_linear_v2_transport(self) -> None:
        """Поднять отдельный transport-only Bybit linear v2 path."""
        if (
            self.bybit_linear_v2_transport_task is not None
            and self.bybit_linear_v2_transport_task.done()
        ):
            self.bybit_linear_v2_transport_task = None
        if self.bybit_linear_v2_transport is not None and self.bybit_linear_v2_transport_task is None:
            get_logger(__name__).info(
                "Bybit linear v2 transport task scheduling",
                exchange="bybit_linear_v2",
            )
            self.bybit_linear_v2_transport_task = asyncio.create_task(
                self.bybit_linear_v2_transport.run(),
                name="production_bybit_linear_v2_transport",
            )

    async def _start_bybit_spot_v2_transport(
        self,
        *,
        resolved_scope: _ResolvedBybitConnectorScope | None = None,
    ) -> None:
        await self.bybit_spot_module.start_v2_transport(resolved_scope=resolved_scope)

    async def _start_bybit_spot_v2_recovery(self) -> None:
        await self.bybit_spot_module.start_v2_recovery()

    async def _stop_opt_in_market_data_connectors(self) -> None:
        """Остановить canonical live-feed connector path без вмешательства в core runtime."""
        await self._stop_bybit_market_data_connector()
        await self.bybit_spot_module.stop_runtime()
        await self._stop_bybit_linear_v2_transport()

    async def _stop_bybit_market_data_connector(self) -> None:
        """Остановить только Bybit perpetual contour."""
        if self.bybit_market_data_connector is not None:
            with contextlib.suppress(Exception):
                await self.bybit_market_data_connector.stop()
        if self.bybit_market_data_connector_task is not None:
            task = self.bybit_market_data_connector_task
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception, TimeoutError):
                await asyncio.wait_for(
                    asyncio.shield(task),
                    timeout=_BYBIT_CONNECTOR_JOIN_TIMEOUT_SECONDS,
                )
            if task.done():
                self.bybit_market_data_connector_task = None
            else:
                self._track_background_connector_shutdown(
                    task=task,
                    attr_name="bybit_market_data_connector_task",
                )

    async def _stop_bybit_spot_market_data_connector(self) -> None:
        await self.bybit_spot_module.stop_market_data_connector()

    async def _stop_bybit_linear_v2_transport(self) -> None:
        """Остановить только отдельный transport-only Bybit linear v2 path."""
        if self.bybit_linear_v2_transport is not None:
            with contextlib.suppress(Exception):
                await self.bybit_linear_v2_transport.stop()
        if self.bybit_linear_v2_transport_task is not None:
            task = self.bybit_linear_v2_transport_task
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception, TimeoutError):
                await asyncio.wait_for(
                    asyncio.shield(task),
                    timeout=_BYBIT_CONNECTOR_JOIN_TIMEOUT_SECONDS,
                )
            if task.done():
                self.bybit_linear_v2_transport_task = None
            else:
                self._track_background_connector_shutdown(
                    task=task,
                    attr_name="bybit_linear_v2_transport_task",
                )

    async def _stop_bybit_spot_v2_transport(self) -> None:
        await self.bybit_spot_module.stop_v2_transport()

    async def _stop_bybit_spot_v2_recovery(self) -> None:
        await self.bybit_spot_module.stop_v2_recovery()

    def _track_background_connector_shutdown(
        self,
        *,
        task: asyncio.Task[None],
        attr_name: str,
    ) -> None:
        if getattr(task, "_background_shutdown_tracked", False):
            return

        async def _wait_for_shutdown() -> None:
            try:
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await task
            finally:
                if getattr(self, attr_name) is task:
                    setattr(self, attr_name, None)
                self._background_connector_shutdown_tasks.discard(waiter)

        waiter = asyncio.create_task(
            _wait_for_shutdown(),
            name=f"{attr_name}_background_shutdown",
        )
        task._background_shutdown_tracked = True  # type: ignore[attr-defined]
        self._background_connector_shutdown_tasks.add(waiter)

    async def _cancel_background_connector_shutdown_tasks(self) -> None:
        if not self._background_connector_shutdown_tasks:
            return
        tasks = tuple(self._background_connector_shutdown_tasks)
        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task

    async def _refresh_runtime_health_after_bybit_toggle(self) -> None:
        """Refresh shared runtime diagnostics after a narrow Bybit toggle."""
        if not self._started:
            return
        if (
            self.bybit_market_data_connector is None
            and self.bybit_spot_market_data_connector is None
            and self.bybit_spot_v2_transport is None
        ):
            return
        self._schedule_runtime_health_refresh()

    def _schedule_runtime_health_refresh(self) -> None:
        """Schedule shared health refresh outside the critical HTTP control path."""
        if not self._started:
            return
        if (
            self._runtime_health_refresh_task is not None
            and not self._runtime_health_refresh_task.done()
        ):
            return
        self._runtime_health_refresh_task = asyncio.create_task(
            self._run_runtime_health_refresh(),
            name="production_runtime_health_refresh",
        )

    async def _run_runtime_health_refresh(self) -> None:
        """Recompute shared runtime health asynchronously after control-path changes."""
        runtime_logger = get_logger(__name__)
        try:
            self.last_health = await self.health_checker.check_system()
            degraded_reasons = self._collect_degraded_reasons(self.last_health)
            self.bybit_spot_module.schedule_product_snapshot_refresh()
            self._update_runtime_diagnostics(
                runtime_started=True,
                runtime_ready=not degraded_reasons,
                startup_state="ready" if not degraded_reasons else "degraded",
                degraded_reasons=degraded_reasons,
                failure_reason=None,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            runtime_logger.exception(
                "Не удалось обновить shared runtime health после Bybit control path"
            )
        finally:
            self._runtime_health_refresh_task = None

    def _schedule_post_start_bringup(
        self,
        *,
        startup_result: StartupResult,
        startup_stage_timings: dict[str, int],
    ) -> None:
        if self._post_start_bringup_task is not None and not self._post_start_bringup_task.done():
            return
        self._post_start_bringup_task = asyncio.create_task(
            self._run_post_start_bringup(
                startup_result=startup_result,
                startup_stage_timings=dict(startup_stage_timings),
            ),
            name="production_runtime_post_start_bringup",
        )

    async def _run_post_start_bringup(
        self,
        *,
        startup_result: StartupResult,
        startup_stage_timings: dict[str, int],
    ) -> None:
        logger = get_logger(__name__)
        try:
            connector_started_at = datetime.now(UTC)
            await self._start_opt_in_market_data_connectors()
            startup_stage_timings["opt_in_connector_startup_ms"] = int(
                (datetime.now(UTC) - connector_started_at).total_seconds() * 1000
            )
            validation_started_at = datetime.now(UTC)
            await self._validate_started_runtime()
            self.event_bus.seal_risk_path_policy()
            startup_stage_timings["post_start_validation_ms"] = int(
                (datetime.now(UTC) - validation_started_at).total_seconds() * 1000
            )
            health_started_at = datetime.now(UTC)
            self.last_health = await self.health_checker.check_system()
            startup_stage_timings["health_check_ms"] = int(
                (datetime.now(UTC) - health_started_at).total_seconds() * 1000
            )
            degraded_reasons = self._collect_degraded_reasons(self.last_health)
            self._update_runtime_diagnostics(
                runtime_started=True,
                runtime_ready=not degraded_reasons,
                startup_state="ready" if not degraded_reasons else "degraded",
                shutdown_state="not_shutting_down",
                failure_reason=None,
                degraded_reasons=degraded_reasons,
                startup_stage_timings=startup_stage_timings,
            )
            logger_method = logger.info if not degraded_reasons else logger.warning
            logger_method(
                "Production runtime post-start bring-up завершён",
                startup_phase=startup_result.phase_reached.value,
                controller_startup_ms=startup_stage_timings.get("controller_startup_ms"),
                opt_in_connector_startup_ms=startup_stage_timings.get(
                    "opt_in_connector_startup_ms"
                ),
                post_start_validation_ms=startup_stage_timings.get("post_start_validation_ms"),
                health_check_ms=startup_stage_timings.get("health_check_ms"),
                degraded_reasons=degraded_reasons,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._update_runtime_diagnostics(
                runtime_started=True,
                runtime_ready=False,
                startup_state="failed",
                shutdown_state="not_shutting_down",
                failure_reason=str(exc),
                degraded_reasons=[],
                startup_stage_timings=startup_stage_timings,
            )
            logger.exception(
                "Production runtime post-start bring-up завершился ошибкой",
                failure_reason=str(exc),
            )
        finally:
            self._post_start_bringup_task = None

    def _bybit_linear_runtime_signature(self) -> tuple[object, ...]:
        return _build_bybit_runtime_signature(
            settings=self.settings,
            contour="linear",
        )

    def _bybit_spot_runtime_signature(self) -> tuple[object, ...]:
        return _build_bybit_runtime_signature(
            settings=self.settings,
            contour="spot",
        )

    async def _apply_linear_bybit_runtime_plan(
        self,
        *,
        settings: Settings,
        resolved_scope: _ResolvedBybitConnectorScope,
        restart_required: bool,
    ) -> None:
        candidate_connector = _build_selected_bybit_market_data_connector(
            settings=settings,
            db_manager=self.db_manager,
            market_data_runtime=self.market_data_runtime,
            resolved_scope=resolved_scope,
        )
        if restart_required:
            await self._stop_bybit_market_data_connector()
            self.bybit_market_data_connector = candidate_connector
            self.bybit_market_data_scope_summary = resolved_scope.truth
            self.bybit_market_data_apply_truth = _build_bybit_runtime_apply_truth(
                settings=settings,
                contour="linear",
                resolved_scope=resolved_scope,
                connector=candidate_connector,
            )
            if self._started and self.bybit_market_data_connector is not None:
                await self._start_bybit_market_data_connector()
            return
        apply_status = "applied"
        apply_reason: str | None = None
        if self.bybit_market_data_connector is not None:
            apply_status = (
                await self.bybit_market_data_connector.update_universe_trade_count_threshold(
                    resolved_scope.truth.trade_count_filter_minimum
                )
            )
            if not isinstance(apply_status, str) or not apply_status:
                apply_status = "applied"
            if apply_status == "deferred":
                apply_reason = "transport_reconnect_pending"
        self.bybit_market_data_scope_summary = resolved_scope.truth
        self.bybit_market_data_apply_truth = _build_bybit_runtime_apply_truth(
            settings=settings,
            contour="linear",
            resolved_scope=resolved_scope,
            connector=self.bybit_market_data_connector,
            apply_status=apply_status,
            apply_reason=apply_reason,
        )

    async def _apply_spot_bybit_runtime_plan(
        self,
        *,
        settings: Settings,
        resolved_scope: _ResolvedBybitConnectorScope,
        restart_required: bool,
    ) -> None:
        await self.bybit_spot_module.apply_runtime_plan(
            settings=settings,
            resolved_scope=resolved_scope,
            restart_required=restart_required,
        )

    async def _resolve_spot_v2_final_scope(
        self,
        *,
        settings: Settings,
        resolved_scope: _ResolvedBybitConnectorScope,
    ) -> _ResolvedBybitConnectorScope:
        return await self.bybit_spot_module.resolve_final_scope(
            settings=settings,
            resolved_scope=resolved_scope,
        )

    async def set_bybit_market_data_connector_enabled(self, enabled: bool) -> dict[str, Any]:
        """Narrow runtime control path for Bybit connector widget in terminal settings."""
        candidate_payload = get_settings().model_dump(mode="python")
        candidate_payload["bybit_market_data_connector_enabled"] = enabled
        candidate_settings = Settings.model_validate(candidate_payload)
        previous_signature = self._bybit_linear_runtime_signature()
        candidate_signature = _build_bybit_runtime_signature(
            settings=candidate_settings,
            contour="linear",
        )
        if enabled:
            resolved_scope = _reuse_bybit_universe_scope_if_possible(
                settings=candidate_settings,
                contour="linear",
                existing_truth=self.bybit_market_data_scope_summary,
            ) or _resolve_canonical_bybit_market_data_scope(
                settings=candidate_settings,
                capture_discovery_errors=True,
            )
        else:
            resolved_scope = _resolve_disabled_bybit_toggle_scope(
                settings=candidate_settings,
                contour="linear",
                existing_truth=self.bybit_market_data_scope_summary,
            )

        await self._apply_linear_bybit_runtime_plan(
            settings=candidate_settings,
            resolved_scope=resolved_scope,
            restart_required=previous_signature != candidate_signature,
        )
        updated_settings = update_settings({"bybit_market_data_connector_enabled": enabled})
        self.settings = updated_settings
        await self._refresh_runtime_health_after_bybit_toggle()

        return self.get_runtime_diagnostics()

    async def set_bybit_spot_market_data_connector_enabled(self, enabled: bool) -> dict[str, Any]:
        return await self.bybit_spot_module.set_enabled(enabled)

    async def set_bybit_spot_runtime_desired_running(
        self,
        desired_running: bool,
    ) -> dict[str, object]:
        return await self.bybit_spot_module.set_runtime_desired_running(desired_running)

    async def update_live_feed_policy_settings(
        self,
        updates: dict[str, Any],
    ) -> Settings:
        """Синхронизировать live-feed policy settings и canonical runtime truth."""
        candidate_payload = get_settings().model_dump(mode="python")
        candidate_payload.update(updates)
        candidate_settings = Settings.model_validate(candidate_payload)
        previous_settings = self.settings

        previous_linear_signature = self._bybit_linear_runtime_signature()
        previous_spot_signature = self._bybit_spot_runtime_signature()
        candidate_linear_signature = _build_bybit_runtime_signature(
            settings=candidate_settings,
            contour="linear",
        )
        candidate_spot_signature = _build_bybit_runtime_signature(
            settings=candidate_settings,
            contour="spot",
        )
        resolved_linear_scope = _reuse_bybit_universe_scope_if_possible(
            settings=candidate_settings,
            contour="linear",
            existing_truth=self.bybit_market_data_scope_summary,
        ) or _resolve_canonical_bybit_market_data_scope(
            settings=candidate_settings,
            capture_discovery_errors=True,
        )
        resolved_spot_scope = _reuse_bybit_universe_scope_if_possible(
            settings=candidate_settings,
            contour="spot",
            existing_truth=self.bybit_spot_market_data_scope_summary,
        ) or await _resolve_canonical_bybit_spot_market_data_scope_async(
            settings=candidate_settings,
            capture_discovery_errors=True,
        )

        self.settings = candidate_settings
        try:
            await self._apply_linear_bybit_runtime_plan(
                settings=candidate_settings,
                resolved_scope=resolved_linear_scope,
                restart_required=previous_linear_signature != candidate_linear_signature,
            )
            await self._apply_spot_bybit_runtime_plan(
                settings=candidate_settings,
                resolved_scope=resolved_spot_scope,
                restart_required=previous_spot_signature != candidate_spot_signature,
            )
            updated_settings = update_settings(updates)
        except Exception:
            self.settings = previous_settings
            raise
        self.settings = updated_settings
        self.bybit_spot_module.mark_product_snapshot_stale()
        self.bybit_spot_module.schedule_product_snapshot_refresh()
        if self._started and (
            previous_linear_signature != candidate_linear_signature
            or previous_spot_signature != candidate_spot_signature
        ):
            self._schedule_runtime_health_refresh()

        return updated_settings

    def _collect_degraded_reasons(self, health: SystemHealth) -> list[str]:  # noqa: PLR0912,PLR0915
        """Собрать operator-facing причины деградации из health truth."""
        reasons = [
            f"{name}:{component.status.value}"
            for name, component in health.components.items()
            if component.status != HealthStatus.HEALTHY
        ]
        if self.bybit_market_data_connector is not None:
            connector = self.bybit_market_data_connector.get_operator_diagnostics()
            if connector.get("enabled", False):
                transport_status = str(connector.get("transport_status", "unknown"))
                if transport_status != "connected":
                    reasons.append(f"live_feed_bybit:{transport_status}")
                degraded_reason = connector.get("degraded_reason")
                if isinstance(degraded_reason, str) and degraded_reason:
                    reasons.append(f"live_feed_bybit:{degraded_reason}")
        if self.bybit_spot_market_data_connector is not None:
            connector = self.bybit_spot_market_data_connector.get_operator_diagnostics()
            if connector.get("enabled", False):
                transport_status = str(connector.get("transport_status", "unknown"))
                if transport_status != "connected":
                    reasons.append(f"live_feed_bybit_spot:{transport_status}")
                degraded_reason = connector.get("degraded_reason")
                if isinstance(degraded_reason, str) and degraded_reason:
                    reasons.append(f"live_feed_bybit_spot:{degraded_reason}")
                last_disconnect_reason = connector.get("last_disconnect_reason")
                if isinstance(last_disconnect_reason, str) and last_disconnect_reason:
                    reasons.append(f"live_feed_bybit_disconnect:{last_disconnect_reason}")
        market_data_runtime = self.market_data_runtime.get_runtime_diagnostics()
        if not market_data_runtime.get("ready", False):
            reasons.append("phase6_market_data:not_ready")
        readiness_reason_values = cast(
            "list[str] | tuple[str, ...]",
            market_data_runtime.get("readiness_reasons", []),
        )
        reasons.extend(f"phase6_market_data:{reason}" for reason in readiness_reason_values)
        degraded_reason_values = cast(
            "list[str] | tuple[str, ...]",
            market_data_runtime.get("degraded_reasons", []),
        )
        reasons.extend(f"phase6_market_data:{reason}" for reason in degraded_reason_values)
        shared_analysis_runtime = self.shared_analysis_runtime.get_runtime_diagnostics()
        if not shared_analysis_runtime.get("ready", False):
            reasons.append("c7r_shared_analysis:not_ready")
        readiness_reason_values = cast(
            "list[str] | tuple[str, ...]",
            shared_analysis_runtime.get("readiness_reasons", []),
        )
        reasons.extend(f"c7r_shared_analysis:{reason}" for reason in readiness_reason_values)
        degraded_reason_values = cast(
            "list[str] | tuple[str, ...]",
            shared_analysis_runtime.get("degraded_reasons", []),
        )
        reasons.extend(f"c7r_shared_analysis:{reason}" for reason in degraded_reason_values)
        intelligence_runtime = self.intelligence_runtime.get_runtime_diagnostics()
        if not intelligence_runtime.get("ready", False):
            reasons.append("phase7_intelligence:not_ready")
        readiness_reason_values = cast(
            "list[str] | tuple[str, ...]",
            intelligence_runtime.get("readiness_reasons", []),
        )
        reasons.extend(f"phase7_intelligence:{reason}" for reason in readiness_reason_values)
        degraded_reason_values = cast(
            "list[str] | tuple[str, ...]",
            intelligence_runtime.get("degraded_reasons", []),
        )
        reasons.extend(f"phase7_intelligence:{reason}" for reason in degraded_reason_values)
        signal_runtime = self.signal_runtime.get_runtime_diagnostics()
        if not signal_runtime.get("ready", False):
            reasons.append("phase8_signal:not_ready")
        readiness_reason_values = cast(
            "list[str] | tuple[str, ...]",
            signal_runtime.get("readiness_reasons", []),
        )
        reasons.extend(f"phase8_signal:{reason}" for reason in readiness_reason_values)
        degraded_reason_values = cast(
            "list[str] | tuple[str, ...]",
            signal_runtime.get("degraded_reasons", []),
        )
        reasons.extend(f"phase8_signal:{reason}" for reason in degraded_reason_values)
        strategy_runtime = self.strategy_runtime.get_runtime_diagnostics()
        if not strategy_runtime.get("started", False):
            reasons.append("phase9_strategy:not_started")
        if not strategy_runtime.get("ready", False):
            reasons.append("phase9_strategy:not_ready")
        readiness_reason_values = cast(
            "list[str] | tuple[str, ...]",
            strategy_runtime.get("readiness_reasons", []),
        )
        reasons.extend(f"phase9_strategy:{reason}" for reason in readiness_reason_values)
        degraded_reason_values = cast(
            "list[str] | tuple[str, ...]",
            strategy_runtime.get("degraded_reasons", []),
        )
        reasons.extend(f"phase9_strategy:{reason}" for reason in degraded_reason_values)
        execution_runtime = self.execution_runtime.get_runtime_diagnostics()
        if not execution_runtime.get("started", False):
            reasons.append("phase10_execution:not_started")
        if not execution_runtime.get("ready", False):
            reasons.append("phase10_execution:not_ready")
        readiness_reason_values = cast(
            "list[str] | tuple[str, ...]",
            execution_runtime.get("readiness_reasons", []),
        )
        reasons.extend(f"phase10_execution:{reason}" for reason in readiness_reason_values)
        degraded_reason_values = cast(
            "list[str] | tuple[str, ...]",
            execution_runtime.get("degraded_reasons", []),
        )
        reasons.extend(f"phase10_execution:{reason}" for reason in degraded_reason_values)
        oms_runtime = self.oms_runtime.get_runtime_diagnostics()
        if not oms_runtime.get("started", False):
            reasons.append("phase16_oms:not_started")
        if not oms_runtime.get("ready", False):
            reasons.append("phase16_oms:not_ready")
        readiness_reason_values = cast(
            "list[str] | tuple[str, ...]",
            oms_runtime.get("readiness_reasons", []),
        )
        reasons.extend(f"phase16_oms:{reason}" for reason in readiness_reason_values)
        degraded_reason_values = cast(
            "list[str] | tuple[str, ...]",
            oms_runtime.get("degraded_reasons", []),
        )
        reasons.extend(f"phase16_oms:{reason}" for reason in degraded_reason_values)
        opportunity_runtime = self.opportunity_runtime.get_runtime_diagnostics()
        if not opportunity_runtime.get("started", False):
            reasons.append("phase11_opportunity:not_started")
        if not opportunity_runtime.get("ready", False):
            reasons.append("phase11_opportunity:not_ready")
        readiness_reason_values = cast(
            "list[str] | tuple[str, ...]",
            opportunity_runtime.get("readiness_reasons", []),
        )
        reasons.extend(f"phase11_opportunity:{reason}" for reason in readiness_reason_values)
        degraded_reason_values = cast(
            "list[str] | tuple[str, ...]",
            opportunity_runtime.get("degraded_reasons", []),
        )
        reasons.extend(f"phase11_opportunity:{reason}" for reason in degraded_reason_values)
        orchestration_runtime = self.orchestration_runtime.get_runtime_diagnostics()
        if not orchestration_runtime.get("started", False):
            reasons.append("phase12_orchestration:not_started")
        if not orchestration_runtime.get("ready", False):
            reasons.append("phase12_orchestration:not_ready")
        readiness_reason_values = cast(
            "list[str] | tuple[str, ...]",
            orchestration_runtime.get("readiness_reasons", []),
        )
        reasons.extend(f"phase12_orchestration:{reason}" for reason in readiness_reason_values)
        degraded_reason_values = cast(
            "list[str] | tuple[str, ...]",
            orchestration_runtime.get("degraded_reasons", []),
        )
        reasons.extend(f"phase12_orchestration:{reason}" for reason in degraded_reason_values)
        position_expansion_runtime = self.position_expansion_runtime.get_runtime_diagnostics()
        if not position_expansion_runtime.get("started", False):
            reasons.append("phase13_position_expansion:not_started")
        if not position_expansion_runtime.get("ready", False):
            reasons.append("phase13_position_expansion:not_ready")
        readiness_reason_values = cast(
            "list[str] | tuple[str, ...]",
            position_expansion_runtime.get("readiness_reasons", []),
        )
        reasons.extend(f"phase13_position_expansion:{reason}" for reason in readiness_reason_values)
        degraded_reason_values = cast(
            "list[str] | tuple[str, ...]",
            position_expansion_runtime.get("degraded_reasons", []),
        )
        reasons.extend(f"phase13_position_expansion:{reason}" for reason in degraded_reason_values)
        portfolio_governor_runtime = self.portfolio_governor_runtime.get_runtime_diagnostics()
        if not portfolio_governor_runtime.get("started", False):
            reasons.append("phase14_portfolio_governor:not_started")
        if not portfolio_governor_runtime.get("ready", False):
            reasons.append("phase14_portfolio_governor:not_ready")
        readiness_reason_values = cast(
            "list[str] | tuple[str, ...]",
            portfolio_governor_runtime.get("readiness_reasons", []),
        )
        reasons.extend(f"phase14_portfolio_governor:{reason}" for reason in readiness_reason_values)
        degraded_reason_values = cast(
            "list[str] | tuple[str, ...]",
            portfolio_governor_runtime.get("degraded_reasons", []),
        )
        reasons.extend(f"phase14_portfolio_governor:{reason}" for reason in degraded_reason_values)
        protection_runtime = self.protection_runtime.get_runtime_diagnostics()
        if not protection_runtime.get("started", False):
            reasons.append("phase15_protection:not_started")
        if not protection_runtime.get("ready", False):
            reasons.append("phase15_protection:not_ready")
        readiness_reason_values = cast(
            "list[str] | tuple[str, ...]",
            protection_runtime.get("readiness_reasons", []),
        )
        reasons.extend(f"phase15_protection:{reason}" for reason in readiness_reason_values)
        degraded_reason_values = cast(
            "list[str] | tuple[str, ...]",
            protection_runtime.get("degraded_reasons", []),
        )
        reasons.extend(f"phase15_protection:{reason}" for reason in degraded_reason_values)
        manager_runtime = self.manager_runtime.get_runtime_diagnostics()
        if not manager_runtime.get("started", False):
            reasons.append("phase17_manager:not_started")
        if not manager_runtime.get("ready", False):
            reasons.append("phase17_manager:not_ready")
        readiness_reason_values = cast(
            "list[str] | tuple[str, ...]",
            manager_runtime.get("readiness_reasons", []),
        )
        reasons.extend(f"phase17_manager:{reason}" for reason in readiness_reason_values)
        degraded_reason_values = cast(
            "list[str] | tuple[str, ...]",
            manager_runtime.get("degraded_reasons", []),
        )
        reasons.extend(f"phase17_manager:{reason}" for reason in degraded_reason_values)
        validation_runtime = self.validation_runtime.get_runtime_diagnostics()
        if not validation_runtime.get("started", False):
            reasons.append("phase18_validation:not_started")
        if not validation_runtime.get("ready", False):
            reasons.append("phase18_validation:not_ready")
        readiness_reason_values = cast(
            "list[str] | tuple[str, ...]",
            validation_runtime.get("readiness_reasons", []),
        )
        reasons.extend(f"phase18_validation:{reason}" for reason in readiness_reason_values)
        degraded_reason_values = cast(
            "list[str] | tuple[str, ...]",
            validation_runtime.get("degraded_reasons", []),
        )
        reasons.extend(f"phase18_validation:{reason}" for reason in degraded_reason_values)
        paper_runtime = self.paper_runtime.get_runtime_diagnostics()
        if not paper_runtime.get("started", False):
            reasons.append("phase19_paper:not_started")
        if not paper_runtime.get("ready", False):
            reasons.append("phase19_paper:not_ready")
        readiness_reason_values = cast(
            "list[str] | tuple[str, ...]",
            paper_runtime.get("readiness_reasons", []),
        )
        reasons.extend(f"phase19_paper:{reason}" for reason in readiness_reason_values)
        degraded_reason_values = cast(
            "list[str] | tuple[str, ...]",
            paper_runtime.get("degraded_reasons", []),
        )
        reasons.extend(f"phase19_paper:{reason}" for reason in degraded_reason_values)
        return reasons


async def build_production_runtime(  # noqa: PLR0915
    *,
    settings: Settings | None = None,
    policy: ProductionBootstrapPolicy | None = None,
) -> ProductionRuntime:
    """
    Собрать production runtime без запуска бизнес-цикла.

    Возвращает:
        Полностью собранный, но ещё не стартованный runtime.
    """
    runtime_settings = settings or get_settings()
    runtime_policy = policy or ProductionBootstrapPolicy()

    if runtime_policy.active_risk_path != PHASE5_RISK_PATH:
        raise ProductionBootstrapError(
            "Production composition root поддерживает только новый Phase 5 Risk Engine path"
        )
    if runtime_policy.include_legacy_risk_listener:
        raise ProductionBootstrapError(
            "Legacy RiskListener не может быть включён в production bootstrap"
        )

    if not validate_settings(runtime_settings, create_dirs=True):
        raise ProductionBootstrapError("Валидация settings не пройдена")

    configure_logging()
    logger = get_logger(__name__)

    db_manager = DatabaseManager()
    set_database(db_manager)

    redis_manager = RedisManager()
    set_redis_manager(redis_manager)

    metrics_collector = init_metrics()

    event_bus = EnhancedEventBus(
        enable_persistence=runtime_policy.enable_event_bus_persistence,
        redis_url=(
            runtime_settings.event_bus_redis_url
            if runtime_policy.enable_event_bus_persistence
            else None
        ),
        rate_limit=runtime_settings.event_bus_rate_limit,
        backpressure_strategy=runtime_settings.event_bus_backpressure_strategy,
    )
    event_bus.configure_risk_path_policy(
        active_risk_path=runtime_policy.active_risk_path,
        enforce_single=True,
    )
    set_event_bus(event_bus)

    listener_registry = build_listener_registry(
        registry=ListenerRegistry(),
        include_legacy_risk=runtime_policy.include_legacy_risk_listener,
    )
    event_bus.listener_registry = listener_registry

    health_checker = init_health_checker(
        db_manager=db_manager,
        redis_manager=redis_manager,
        event_bus=event_bus,
        metrics_collector=metrics_collector,
        runtime_identity=build_runtime_identity(
            bootstrap_module="cryptotechnolog.bootstrap",
            bootstrap_mode="production",
            active_risk_path=runtime_policy.active_risk_path,
            config_identity=runtime_settings.get_config_identity(),
            config_revision=runtime_settings.get_config_revision(),
        ),
    )

    controller = SystemController(
        db_manager=db_manager,
        redis_manager=redis_manager,
        health_checker=health_checker,
        metrics_collector=metrics_collector,
        event_bus=event_bus,
        test_mode=runtime_policy.test_mode,
    )
    controller.register_component(
        name="event_bus",
        component=event_bus,
        required=True,
        health_check_enabled=False,
    )

    risk_runtime = await create_risk_runtime(
        event_bus=event_bus,
        controller=controller,
        settings=runtime_settings,
        enable_persistence=runtime_policy.enable_risk_persistence,
    )
    controller.register_component(
        name="phase5_risk_runtime",
        component=risk_runtime,
        required=True,
        health_check_enabled=False,
        shutdown_timeout=15.0,
    )

    def update_market_data_runtime_diagnostics(diagnostics: dict[str, object]) -> None:
        health_checker.set_runtime_diagnostics(market_data_runtime=diagnostics)

    market_data_runtime = create_market_data_runtime(
        event_bus=event_bus,
        controller=controller,
        diagnostics_sink=update_market_data_runtime_diagnostics,
    )
    controller.register_component(
        name="phase6_market_data_runtime",
        component=market_data_runtime,
        required=False,
        health_check_enabled=False,
        shutdown_timeout=15.0,
    )

    def update_intelligence_runtime_diagnostics(diagnostics: dict[str, object]) -> None:
        health_checker.set_runtime_diagnostics(intelligence_runtime=diagnostics)

    def update_shared_analysis_runtime_diagnostics(diagnostics: dict[str, object]) -> None:
        health_checker.set_runtime_diagnostics(shared_analysis_runtime=diagnostics)

    def update_signal_runtime_diagnostics(diagnostics: dict[str, object]) -> None:
        health_checker.set_runtime_diagnostics(signal_runtime=diagnostics)

    def update_strategy_runtime_diagnostics(diagnostics: dict[str, object]) -> None:
        health_checker.set_runtime_diagnostics(strategy_runtime=diagnostics)

    def update_execution_runtime_diagnostics(diagnostics: dict[str, object]) -> None:
        health_checker.set_runtime_diagnostics(execution_runtime=diagnostics)

    def update_oms_runtime_diagnostics(diagnostics: dict[str, object]) -> None:
        health_checker.set_runtime_diagnostics(oms_runtime=diagnostics)

    def update_opportunity_runtime_diagnostics(diagnostics: dict[str, object]) -> None:
        health_checker.set_runtime_diagnostics(opportunity_runtime=diagnostics)

    def update_orchestration_runtime_diagnostics(diagnostics: dict[str, object]) -> None:
        health_checker.set_runtime_diagnostics(orchestration_runtime=diagnostics)

    def update_position_expansion_runtime_diagnostics(diagnostics: dict[str, object]) -> None:
        health_checker.set_runtime_diagnostics(position_expansion_runtime=diagnostics)

    def update_portfolio_governor_runtime_diagnostics(diagnostics: dict[str, object]) -> None:
        health_checker.set_runtime_diagnostics(portfolio_governor_runtime=diagnostics)

    def update_protection_runtime_diagnostics(diagnostics: dict[str, object]) -> None:
        health_checker.set_runtime_diagnostics(protection_runtime=diagnostics)

    def update_manager_runtime_diagnostics(diagnostics: dict[str, object]) -> None:
        health_checker.set_runtime_diagnostics(manager_runtime=diagnostics)

    def update_validation_runtime_diagnostics(diagnostics: dict[str, object]) -> None:
        health_checker.set_runtime_diagnostics(validation_runtime=diagnostics)

    def update_paper_runtime_diagnostics(diagnostics: dict[str, object]) -> None:
        health_checker.set_runtime_diagnostics(paper_runtime=diagnostics)

    # Legacy Bybit connector wiring: keep the current contour stable as a support
    # path, but stop treating it as the default place for new feature work.
    bybit_market_data_scope = _resolve_canonical_bybit_market_data_scope(settings=runtime_settings)
    bybit_market_data_connector = _build_selected_bybit_market_data_connector(
        settings=runtime_settings,
        db_manager=db_manager,
        market_data_runtime=market_data_runtime,
        resolved_scope=bybit_market_data_scope,
    )
    bybit_spot_market_data_scope = _resolve_canonical_bybit_spot_market_data_scope(
        settings=runtime_settings
    )
    bybit_spot_market_data_connector = _build_selected_bybit_spot_market_data_connector(
        settings=runtime_settings,
        db_manager=db_manager,
        market_data_runtime=market_data_runtime,
        resolved_scope=bybit_spot_market_data_scope,
    )
    bybit_linear_v2_transport = _build_bybit_linear_v2_transport_connector(
        settings=runtime_settings,
        market_data_runtime=market_data_runtime,
    )
    bybit_spot_v2_transport = _build_bybit_spot_v2_transport_connector(
        settings=runtime_settings,
        db_manager=db_manager,
        market_data_runtime=market_data_runtime,
        resolved_scope=bybit_spot_market_data_scope,
    )
    bybit_spot_v2_recovery = _build_bybit_spot_v2_recovery_orchestrator(
        settings=runtime_settings,
        db_manager=db_manager,
        resolved_scope=bybit_spot_market_data_scope,
    )

    intelligence_runtime = create_intelligence_runtime(
        diagnostics_sink=update_intelligence_runtime_diagnostics,
    )
    controller.register_component(
        name="phase7_intelligence_runtime",
        component=intelligence_runtime,
        required=False,
        health_check_enabled=False,
        shutdown_timeout=15.0,
    )

    shared_analysis_runtime = create_shared_analysis_runtime(
        diagnostics_sink=update_shared_analysis_runtime_diagnostics,
    )
    controller.register_component(
        name="c7r_shared_analysis_runtime",
        component=shared_analysis_runtime,
        required=False,
        health_check_enabled=False,
        shutdown_timeout=15.0,
    )

    signal_runtime = create_signal_runtime(
        diagnostics_sink=update_signal_runtime_diagnostics,
    )
    controller.register_component(
        name="phase8_signal_runtime",
        component=signal_runtime,
        required=False,
        health_check_enabled=False,
        shutdown_timeout=15.0,
    )

    strategy_runtime = create_strategy_runtime(
        diagnostics_sink=update_strategy_runtime_diagnostics,
    )
    controller.register_component(
        name="phase9_strategy_runtime",
        component=strategy_runtime,
        required=False,
        health_check_enabled=False,
        shutdown_timeout=15.0,
    )

    execution_runtime = create_execution_runtime(
        diagnostics_sink=update_execution_runtime_diagnostics,
    )
    controller.register_component(
        name="phase10_execution_runtime",
        component=execution_runtime,
        required=False,
        health_check_enabled=False,
        shutdown_timeout=15.0,
    )

    oms_runtime = create_oms_runtime(
        diagnostics_sink=update_oms_runtime_diagnostics,
    )
    controller.register_component(
        name="phase16_oms_runtime",
        component=oms_runtime,
        required=False,
        health_check_enabled=False,
        shutdown_timeout=15.0,
    )

    opportunity_runtime = create_opportunity_runtime(
        diagnostics_sink=update_opportunity_runtime_diagnostics,
    )
    controller.register_component(
        name="phase11_opportunity_runtime",
        component=opportunity_runtime,
        required=False,
        health_check_enabled=False,
        shutdown_timeout=15.0,
    )

    orchestration_runtime = create_orchestration_runtime(
        diagnostics_sink=update_orchestration_runtime_diagnostics,
    )
    controller.register_component(
        name="phase12_orchestration_runtime",
        component=orchestration_runtime,
        required=False,
        health_check_enabled=False,
        shutdown_timeout=15.0,
    )

    position_expansion_runtime = create_position_expansion_runtime(
        diagnostics_sink=update_position_expansion_runtime_diagnostics,
    )
    controller.register_component(
        name="phase13_position_expansion_runtime",
        component=position_expansion_runtime,
        required=False,
        health_check_enabled=False,
        shutdown_timeout=15.0,
    )

    portfolio_governor_runtime = create_portfolio_governor_runtime(
        diagnostics_sink=update_portfolio_governor_runtime_diagnostics,
    )
    controller.register_component(
        name="phase14_portfolio_governor_runtime",
        component=portfolio_governor_runtime,
        required=False,
        health_check_enabled=False,
        shutdown_timeout=15.0,
    )

    protection_runtime = create_protection_runtime(
        diagnostics_sink=update_protection_runtime_diagnostics,
    )
    controller.register_component(
        name="phase15_protection_runtime",
        component=protection_runtime,
        required=False,
        health_check_enabled=False,
        shutdown_timeout=15.0,
    )

    manager_runtime = create_manager_runtime(
        diagnostics_sink=update_manager_runtime_diagnostics,
    )
    controller.register_component(
        name="phase17_manager_runtime",
        component=manager_runtime,
        required=False,
        health_check_enabled=False,
        shutdown_timeout=15.0,
    )
    validation_runtime = create_validation_runtime(
        diagnostics_sink=update_validation_runtime_diagnostics,
    )
    controller.register_component(
        name="phase18_validation_runtime",
        component=validation_runtime,
        required=False,
        health_check_enabled=False,
        shutdown_timeout=15.0,
    )
    paper_runtime = create_paper_runtime(
        diagnostics_sink=update_paper_runtime_diagnostics,
    )
    controller.register_component(
        name="phase19_paper_runtime",
        component=paper_runtime,
        required=False,
        health_check_enabled=False,
        shutdown_timeout=15.0,
    )

    async def handle_market_data_bar_completed_for_intelligence(event: Event) -> None:
        try:
            payload = BarCompletedPayload(**event.payload)
            update = intelligence_runtime.ingest_bar_completed_payload(payload)
            if update.regime_changed_event is not None:
                await event_bus.publish(update.regime_changed_event)
        except Exception as exc:
            intelligence_runtime.mark_degraded(f"bar_ingest_failed:{exc}")
            raise

    async def handle_market_data_bar_completed_for_shared_analysis(event: Event) -> None:
        try:
            payload = BarCompletedPayload(**event.payload)
            update = shared_analysis_runtime.ingest_bar_completed_payload(payload)
            risk_event = _build_risk_bar_completed_event(
                payload=payload,
                derived_inputs=update.snapshot,
                orderbook_snapshot=market_data_runtime.orderbook_manager.get_snapshot(
                    payload.symbol,
                    payload.exchange,
                ),
            )
            if risk_event is not None:
                await event_bus.publish(risk_event)
        except Exception as exc:
            shared_analysis_runtime.mark_degraded(f"bar_ingest_failed:{exc}")
            raise RuntimeError(f"shared_analysis_bar_ingest_failed:{exc}") from exc

    async def handle_market_data_bar_completed_for_signal(event: Event) -> None:
        try:
            payload = BarCompletedPayload(**event.payload)
            timeframe = MarketDataTimeframe(payload.timeframe)
            orderbook_snapshot = market_data_runtime.orderbook_manager.get_snapshot(
                payload.symbol,
                payload.exchange,
            )
            derived_inputs = shared_analysis_runtime.get_risk_derived_inputs(
                exchange=payload.exchange,
                symbol=payload.symbol,
                timeframe=timeframe,
            )
            derya = intelligence_runtime.get_derya_assessment(
                exchange=payload.exchange,
                symbol=payload.symbol,
                timeframe=timeframe,
            )
            update = signal_runtime.ingest_bar_completed_payload(
                payload,
                orderbook=orderbook_snapshot,
                derived_inputs=derived_inputs,
                derya=derya,
            )
            if update.event_type is not None and update.emitted_payload is not None:
                await event_bus.publish(
                    build_signal_event(
                        event_type=update.event_type,
                        payload=update.emitted_payload,
                        source=SignalEventSource.SIGNAL_RUNTIME.value,
                    )
                )
        except Exception as exc:
            signal_runtime.mark_degraded(f"bar_ingest_failed:{exc}")
            raise RuntimeError(f"signal_bar_ingest_failed:{exc}") from exc

    async def handle_signal_event_for_strategy(event: Event) -> None:
        try:
            payload = cast("dict[str, object]", event.payload)
            symbol = cast("str", payload["symbol"])
            exchange = cast("str", payload["exchange"])
            timeframe = MarketDataTimeframe(cast("str", payload["timeframe"]))
            generated_at = datetime.fromisoformat(cast("str", payload["generated_at"]))
            signal = signal_runtime.get_signal(
                exchange=exchange,
                symbol=symbol,
                timeframe=timeframe,
                reference_time=generated_at,
            )
            if signal is None:
                raise RuntimeError("strategy_signal_truth_missing_for_event")
            update = strategy_runtime.ingest_signal(
                signal=signal,
                reference_time=generated_at,
            )
            if update.event_type is not None and update.emitted_payload is not None:
                await event_bus.publish(
                    build_strategy_event(
                        event_type=update.event_type,
                        payload=update.emitted_payload,
                        source=StrategyEventSource.STRATEGY_RUNTIME.value,
                    )
                )
        except Exception as exc:
            strategy_runtime.mark_degraded(f"signal_ingest_failed:{exc}")
            raise RuntimeError(f"strategy_signal_ingest_failed:{exc}") from exc

    async def handle_strategy_event_for_execution(event: Event) -> None:
        try:
            payload = cast("dict[str, object]", event.payload)
            symbol = cast("str", payload["symbol"])
            exchange = cast("str", payload["exchange"])
            timeframe = MarketDataTimeframe(cast("str", payload["timeframe"]))
            generated_at = datetime.fromisoformat(cast("str", payload["generated_at"]))
            candidate = strategy_runtime.get_candidate(
                exchange=exchange,
                symbol=symbol,
                timeframe=timeframe,
            )
            if candidate is None:
                raise RuntimeError("execution_strategy_truth_missing_for_event")
            update = execution_runtime.ingest_candidate(
                candidate=candidate,
                reference_time=generated_at,
            )
            if update.event_type is not None and update.emitted_payload is not None:
                await event_bus.publish(
                    build_execution_event(
                        event_type=update.event_type,
                        payload=update.emitted_payload,
                        source=ExecutionEventSource.EXECUTION_RUNTIME.value,
                    )
                )
        except Exception as exc:
            execution_runtime.mark_degraded(f"candidate_ingest_failed:{exc}")
            raise RuntimeError(f"execution_candidate_ingest_failed:{exc}") from exc

    async def handle_execution_event_for_opportunity(event: Event) -> None:
        try:
            payload = cast("dict[str, object]", event.payload)
            symbol = cast("str", payload["symbol"])
            exchange = cast("str", payload["exchange"])
            timeframe = MarketDataTimeframe(cast("str", payload["timeframe"]))
            generated_at = datetime.fromisoformat(cast("str", payload["generated_at"]))
            intent = execution_runtime.get_intent(
                exchange=exchange,
                symbol=symbol,
                timeframe=timeframe,
            )
            if intent is None:
                raise RuntimeError("opportunity_execution_truth_missing_for_event")
            update = opportunity_runtime.ingest_intent(
                intent=intent,
                reference_time=generated_at,
            )
            if update.event_type is not None and update.emitted_payload is not None:
                await event_bus.publish(
                    build_opportunity_event(
                        event_type=update.event_type,
                        payload=update.emitted_payload,
                        source=OpportunityEventSource.OPPORTUNITY_RUNTIME.value,
                    )
                )
        except Exception as exc:
            opportunity_runtime.mark_degraded(f"intent_ingest_failed:{exc}")
            raise RuntimeError(f"opportunity_intent_ingest_failed:{exc}") from exc

    async def handle_execution_event_for_oms(event: Event) -> None:
        try:
            payload = cast("dict[str, object]", event.payload)
            symbol = cast("str", payload["symbol"])
            exchange = cast("str", payload["exchange"])
            timeframe = MarketDataTimeframe(cast("str", payload["timeframe"]))
            generated_at = datetime.fromisoformat(cast("str", payload["generated_at"]))
            intent = execution_runtime.get_intent(
                exchange=exchange,
                symbol=symbol,
                timeframe=timeframe,
            )
            if intent is None:
                raise RuntimeError("oms_execution_truth_missing_for_event")
            update = oms_runtime.ingest_intent(
                intent=intent,
                reference_time=generated_at,
            )
            if update.event_type is not None and update.emitted_payload is not None:
                await event_bus.publish(
                    build_oms_event(
                        event_type=update.event_type,
                        payload=update.emitted_payload,
                        source=OmsEventSource.OMS_RUNTIME.value,
                    )
                )
        except Exception as exc:
            oms_runtime.mark_degraded(f"intent_ingest_failed:{exc}")
            raise RuntimeError(f"oms_intent_ingest_failed:{exc}") from exc

    async def handle_opportunity_event_for_orchestration(event: Event) -> None:
        try:
            payload = cast("dict[str, object]", event.payload)
            symbol = cast("str", payload["symbol"])
            exchange = cast("str", payload["exchange"])
            timeframe = MarketDataTimeframe(cast("str", payload["timeframe"]))
            generated_at = datetime.fromisoformat(cast("str", payload["generated_at"]))
            selection = opportunity_runtime.get_selection(
                exchange=exchange,
                symbol=symbol,
                timeframe=timeframe,
            )
            if selection is None:
                raise RuntimeError("orchestration_opportunity_truth_missing_for_event")
            update = orchestration_runtime.ingest_selection(
                selection=selection,
                reference_time=generated_at,
            )
            if update.event_type is not None and update.emitted_payload is not None:
                await event_bus.publish(
                    build_orchestration_event(
                        event_type=update.event_type,
                        payload=update.emitted_payload,
                        source=OrchestrationEventSource.ORCHESTRATION_RUNTIME.value,
                    )
                )
        except Exception as exc:
            orchestration_runtime.mark_degraded(f"selection_ingest_failed:{exc}")
            raise RuntimeError(f"orchestration_selection_ingest_failed:{exc}") from exc

    async def handle_orchestration_event_for_position_expansion(event: Event) -> None:
        try:
            payload = cast("dict[str, object]", event.payload)
            symbol = cast("str", payload["symbol"])
            exchange = cast("str", payload["exchange"])
            timeframe = MarketDataTimeframe(cast("str", payload["timeframe"]))
            generated_at = datetime.fromisoformat(cast("str", payload["generated_at"]))
            decision = orchestration_runtime.get_decision(
                exchange=exchange,
                symbol=symbol,
                timeframe=timeframe,
            )
            if decision is None:
                raise RuntimeError("position_expansion_orchestration_truth_missing_for_event")
            update = position_expansion_runtime.ingest_decision(
                decision=decision,
                reference_time=generated_at,
            )
            if update.event_type is not None and update.emitted_payload is not None:
                await event_bus.publish(
                    build_position_expansion_event(
                        event_type=update.event_type,
                        payload=update.emitted_payload,
                        source=PositionExpansionEventSource.POSITION_EXPANSION_RUNTIME.value,
                    )
                )
        except Exception as exc:
            position_expansion_runtime.mark_degraded(f"decision_ingest_failed:{exc}")
            raise RuntimeError(f"position_expansion_decision_ingest_failed:{exc}") from exc

    async def handle_position_expansion_event_for_portfolio_governor(event: Event) -> None:
        try:
            payload = cast("dict[str, object]", event.payload)
            symbol = cast("str", payload["symbol"])
            exchange = cast("str", payload["exchange"])
            timeframe = MarketDataTimeframe(cast("str", payload["timeframe"]))
            generated_at = datetime.fromisoformat(cast("str", payload["generated_at"]))
            expansion = position_expansion_runtime.get_candidate(
                exchange=exchange,
                symbol=symbol,
                timeframe=timeframe,
            )
            if expansion is None:
                raise RuntimeError("portfolio_governor_expansion_truth_missing_for_event")
            update = portfolio_governor_runtime.ingest_expansion(
                expansion=expansion,
                reference_time=generated_at,
            )
            if update.event_type is not None and update.emitted_payload is not None:
                await event_bus.publish(
                    build_portfolio_governor_event(
                        event_type=update.event_type,
                        payload=update.emitted_payload,
                        source=PortfolioGovernorEventSource.PORTFOLIO_GOVERNOR_RUNTIME.value,
                    )
                )
        except Exception as exc:
            portfolio_governor_runtime.mark_degraded(f"expansion_ingest_failed:{exc}")
            raise RuntimeError(f"portfolio_governor_expansion_ingest_failed:{exc}") from exc

    async def handle_portfolio_governor_event_for_protection(event: Event) -> None:
        try:
            payload = cast("dict[str, object]", event.payload)
            symbol = cast("str", payload["symbol"])
            exchange = cast("str", payload["exchange"])
            timeframe = MarketDataTimeframe(cast("str", payload["timeframe"]))
            generated_at = datetime.fromisoformat(cast("str", payload["generated_at"]))
            governor = portfolio_governor_runtime.get_candidate(
                exchange=exchange,
                symbol=symbol,
                timeframe=timeframe,
            )
            if governor is None:
                raise RuntimeError("protection_governor_truth_missing_for_event")
            update = protection_runtime.ingest_governor(
                governor=governor,
                reference_time=generated_at,
            )
            if update.emitted_payload is not None:
                await event_bus.publish(
                    build_protection_event(
                        event_type=update.event_type,
                        payload=update.emitted_payload,
                        source=ProtectionEventSource.PROTECTION_RUNTIME.value,
                    )
                )
        except Exception as exc:
            protection_runtime.mark_degraded(f"governor_ingest_failed:{exc}")
            raise RuntimeError(f"protection_governor_ingest_failed:{exc}") from exc

    async def handle_protection_event_for_manager(event: Event) -> None:
        try:
            payload = cast("dict[str, object]", event.payload)
            symbol = cast("str", payload["symbol"])
            exchange = cast("str", payload["exchange"])
            timeframe = MarketDataTimeframe(cast("str", payload["timeframe"]))
            generated_at = datetime.fromisoformat(cast("str", payload["generated_at"]))
            opportunity = opportunity_runtime.get_selection(
                exchange=exchange,
                symbol=symbol,
                timeframe=timeframe,
            )
            orchestration = orchestration_runtime.get_decision(
                exchange=exchange,
                symbol=symbol,
                timeframe=timeframe,
            )
            expansion = position_expansion_runtime.get_candidate(
                exchange=exchange,
                symbol=symbol,
                timeframe=timeframe,
            )
            governor = portfolio_governor_runtime.get_candidate(
                exchange=exchange,
                symbol=symbol,
                timeframe=timeframe,
            )
            protection = protection_runtime.get_candidate(
                exchange=exchange,
                symbol=symbol,
                timeframe=timeframe,
            )
            update = manager_runtime.ingest_truths(
                opportunity=opportunity,
                orchestration=orchestration,
                expansion=expansion,
                governor=governor,
                protection=protection,
                reference_time=generated_at,
            )
            if update.event_type is not None and update.emitted_payload is not None:
                await event_bus.publish(
                    build_manager_event(
                        event_type=update.event_type,
                        payload=update.emitted_payload,
                        source=ManagerEventSource.MANAGER_RUNTIME.value,
                    )
                )
        except Exception as exc:
            manager_runtime.mark_degraded(f"workflow_ingest_failed:{exc}")
            raise RuntimeError(f"manager_workflow_ingest_failed:{exc}") from exc

    def get_adjacent_oms_order_for_validation(
        *,
        exchange: str,
        symbol: str,
        timeframe: MarketDataTimeframe,
    ) -> OmsOrderRecord | None:
        for order in oms_runtime.list_active_orders():
            if (
                order.exchange == exchange
                and order.symbol == symbol
                and order.timeframe == timeframe
            ):
                return order
        for order in oms_runtime.list_historical_orders():
            if (
                order.exchange == exchange
                and order.symbol == symbol
                and order.timeframe == timeframe
            ):
                return order
        return None

    def get_adjacent_oms_order_for_paper(
        *,
        exchange: str,
        symbol: str,
        timeframe: MarketDataTimeframe,
    ) -> OmsOrderRecord | None:
        return get_adjacent_oms_order_for_validation(
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
        )

    async def handle_manager_event_for_validation(event: Event) -> None:
        try:
            payload = cast("dict[str, object]", event.payload)
            symbol = cast("str", payload["symbol"])
            exchange = cast("str", payload["exchange"])
            timeframe = MarketDataTimeframe(cast("str", payload["timeframe"]))
            generated_at = datetime.fromisoformat(cast("str", payload["generated_at"]))
            key = (symbol, exchange, timeframe)
            manager = manager_runtime.get_candidate(
                exchange=exchange,
                symbol=symbol,
                timeframe=timeframe,
            ) or manager_runtime.get_historical_candidate(key)
            governor = portfolio_governor_runtime.get_candidate(
                exchange=exchange,
                symbol=symbol,
                timeframe=timeframe,
            )
            protection = protection_runtime.get_candidate(
                exchange=exchange,
                symbol=symbol,
                timeframe=timeframe,
            )
            oms_order = get_adjacent_oms_order_for_validation(
                exchange=exchange,
                symbol=symbol,
                timeframe=timeframe,
            )
            update = validation_runtime.ingest_truths(
                manager=manager,
                governor=governor,
                protection=protection,
                oms_order=oms_order,
                reference_time=generated_at,
            )
            if update.event_type is not None and update.emitted_payload is not None:
                await event_bus.publish(
                    build_validation_event(
                        event_type=update.event_type,
                        payload=update.emitted_payload,
                        source=ValidationEventSource.VALIDATION_RUNTIME.value,
                    )
                )
        except Exception as exc:
            validation_runtime.mark_degraded(f"review_ingest_failed:{exc}")
            raise RuntimeError(f"validation_review_ingest_failed:{exc}") from exc

    async def handle_validation_event_for_paper(event: Event) -> None:
        try:
            payload = cast("dict[str, object]", event.payload)
            symbol = cast("str", payload["symbol"])
            exchange = cast("str", payload["exchange"])
            timeframe = MarketDataTimeframe(cast("str", payload["timeframe"]))
            generated_at = datetime.fromisoformat(cast("str", payload["generated_at"]))
            key = (symbol, exchange, timeframe)
            validation = validation_runtime.get_candidate(
                exchange=exchange,
                symbol=symbol,
                timeframe=timeframe,
            ) or validation_runtime.get_historical_candidate(key)
            manager = manager_runtime.get_candidate(
                exchange=exchange,
                symbol=symbol,
                timeframe=timeframe,
            ) or manager_runtime.get_historical_candidate(key)
            oms_order = get_adjacent_oms_order_for_paper(
                exchange=exchange,
                symbol=symbol,
                timeframe=timeframe,
            )
            update = paper_runtime.ingest_truths(
                manager=manager,
                validation=validation,
                oms_order=oms_order,
                reference_time=generated_at,
            )
            if update.event_type is not None and update.emitted_payload is not None:
                await event_bus.publish(
                    build_paper_event(
                        event_type=update.event_type,
                        payload=update.emitted_payload,
                        source=PaperEventSource.PAPER_RUNTIME.value,
                    )
                )
        except Exception as exc:
            paper_runtime.mark_degraded(f"rehearsal_ingest_failed:{exc}")
            raise RuntimeError(f"paper_rehearsal_ingest_failed:{exc}") from exc

    event_bus.on(SystemEventType.BAR_COMPLETED, handle_market_data_bar_completed_for_intelligence)
    event_bus.on(
        SystemEventType.BAR_COMPLETED,
        handle_market_data_bar_completed_for_shared_analysis,
    )
    event_bus.on(SystemEventType.BAR_COMPLETED, handle_market_data_bar_completed_for_signal)
    event_bus.on(SignalEventType.SIGNAL_SNAPSHOT_UPDATED.value, handle_signal_event_for_strategy)
    event_bus.on(SignalEventType.SIGNAL_EMITTED.value, handle_signal_event_for_strategy)
    event_bus.on(SignalEventType.SIGNAL_INVALIDATED.value, handle_signal_event_for_strategy)
    event_bus.on(
        StrategyEventType.STRATEGY_CANDIDATE_UPDATED.value,
        handle_strategy_event_for_execution,
    )
    event_bus.on(
        StrategyEventType.STRATEGY_ACTIONABLE.value,
        handle_strategy_event_for_execution,
    )
    event_bus.on(
        StrategyEventType.STRATEGY_INVALIDATED.value,
        handle_strategy_event_for_execution,
    )
    event_bus.on(
        ExecutionEventType.EXECUTION_INTENT_UPDATED.value,
        handle_execution_event_for_opportunity,
    )
    event_bus.on(
        ExecutionEventType.EXECUTION_INTENT_UPDATED.value,
        handle_execution_event_for_oms,
    )
    event_bus.on(
        ExecutionEventType.EXECUTION_REQUESTED.value,
        handle_execution_event_for_opportunity,
    )
    event_bus.on(
        ExecutionEventType.EXECUTION_REQUESTED.value,
        handle_execution_event_for_oms,
    )
    event_bus.on(
        ExecutionEventType.EXECUTION_INVALIDATED.value,
        handle_execution_event_for_opportunity,
    )
    event_bus.on(
        ExecutionEventType.EXECUTION_INVALIDATED.value,
        handle_execution_event_for_oms,
    )
    event_bus.on(
        OpportunityEventType.OPPORTUNITY_CANDIDATE_UPDATED.value,
        handle_opportunity_event_for_orchestration,
    )
    event_bus.on(
        OpportunityEventType.OPPORTUNITY_SELECTED.value,
        handle_opportunity_event_for_orchestration,
    )
    event_bus.on(
        OpportunityEventType.OPPORTUNITY_INVALIDATED.value,
        handle_opportunity_event_for_orchestration,
    )
    event_bus.on(
        OrchestrationEventType.ORCHESTRATION_CANDIDATE_UPDATED.value,
        handle_orchestration_event_for_position_expansion,
    )
    event_bus.on(
        OrchestrationEventType.ORCHESTRATION_DECIDED.value,
        handle_orchestration_event_for_position_expansion,
    )
    event_bus.on(
        OrchestrationEventType.ORCHESTRATION_INVALIDATED.value,
        handle_orchestration_event_for_position_expansion,
    )
    event_bus.on(
        PositionExpansionEventType.POSITION_EXPANSION_CANDIDATE_UPDATED.value,
        handle_position_expansion_event_for_portfolio_governor,
    )
    event_bus.on(
        PositionExpansionEventType.POSITION_EXPANSION_APPROVED.value,
        handle_position_expansion_event_for_portfolio_governor,
    )
    event_bus.on(
        PositionExpansionEventType.POSITION_EXPANSION_INVALIDATED.value,
        handle_position_expansion_event_for_portfolio_governor,
    )
    event_bus.on(
        PortfolioGovernorEventType.PORTFOLIO_GOVERNOR_CANDIDATE_UPDATED.value,
        handle_portfolio_governor_event_for_protection,
    )
    event_bus.on(
        PortfolioGovernorEventType.PORTFOLIO_GOVERNOR_APPROVED.value,
        handle_portfolio_governor_event_for_protection,
    )
    event_bus.on(
        PortfolioGovernorEventType.PORTFOLIO_GOVERNOR_INVALIDATED.value,
        handle_portfolio_governor_event_for_protection,
    )
    event_bus.on(
        ProtectionEventType.PROTECTION_CANDIDATE_UPDATED.value,
        handle_protection_event_for_manager,
    )
    event_bus.on(
        ProtectionEventType.PROTECTION_PROTECTED.value,
        handle_protection_event_for_manager,
    )
    event_bus.on(
        ProtectionEventType.PROTECTION_HALTED.value,
        handle_protection_event_for_manager,
    )
    event_bus.on(
        ProtectionEventType.PROTECTION_FROZEN.value,
        handle_protection_event_for_manager,
    )
    event_bus.on(
        ProtectionEventType.PROTECTION_INVALIDATED.value,
        handle_protection_event_for_manager,
    )
    event_bus.on(
        ManagerEventType.MANAGER_CANDIDATE_UPDATED.value,
        handle_manager_event_for_validation,
    )
    event_bus.on(
        ManagerEventType.MANAGER_WORKFLOW_COORDINATED.value,
        handle_manager_event_for_validation,
    )
    event_bus.on(
        ManagerEventType.MANAGER_WORKFLOW_ABSTAINED.value,
        handle_manager_event_for_validation,
    )
    event_bus.on(
        ManagerEventType.MANAGER_WORKFLOW_INVALIDATED.value,
        handle_manager_event_for_validation,
    )
    event_bus.on(
        ValidationEventType.VALIDATION_CANDIDATE_UPDATED.value,
        handle_validation_event_for_paper,
    )
    event_bus.on(
        ValidationEventType.VALIDATION_WORKFLOW_VALIDATED.value,
        handle_validation_event_for_paper,
    )
    event_bus.on(
        ValidationEventType.VALIDATION_WORKFLOW_ABSTAINED.value,
        handle_validation_event_for_paper,
    )
    event_bus.on(
        ValidationEventType.VALIDATION_WORKFLOW_INVALIDATED.value,
        handle_validation_event_for_paper,
    )

    runtime = ProductionRuntime(
        settings=runtime_settings,
        policy=runtime_policy,
        identity=build_runtime_identity(
            bootstrap_module="cryptotechnolog.bootstrap",
            bootstrap_mode="production",
            active_risk_path=runtime_policy.active_risk_path,
            config_identity=runtime_settings.get_config_identity(),
            config_revision=runtime_settings.get_config_revision(),
        ),
        db_manager=db_manager,
        redis_manager=redis_manager,
        metrics_collector=metrics_collector,
        health_checker=health_checker,
        event_bus=event_bus,
        listener_registry=listener_registry,
        controller=controller,
        risk_runtime=risk_runtime,
        market_data_runtime=market_data_runtime,
        shared_analysis_runtime=shared_analysis_runtime,
        intelligence_runtime=intelligence_runtime,
        signal_runtime=signal_runtime,
        strategy_runtime=strategy_runtime,
        execution_runtime=execution_runtime,
        oms_runtime=oms_runtime,
        opportunity_runtime=opportunity_runtime,
        orchestration_runtime=orchestration_runtime,
        position_expansion_runtime=position_expansion_runtime,
        portfolio_governor_runtime=portfolio_governor_runtime,
        protection_runtime=protection_runtime,
        manager_runtime=manager_runtime,
        validation_runtime=validation_runtime,
        paper_runtime=paper_runtime,
        bybit_market_data_connector=bybit_market_data_connector,
        bybit_market_data_scope_summary=bybit_market_data_scope.truth,
        bybit_market_data_apply_truth=_build_bybit_runtime_apply_truth(
            settings=runtime_settings,
            contour="linear",
            resolved_scope=bybit_market_data_scope,
            connector=bybit_market_data_connector,
        ),
        bybit_spot_market_data_connector=bybit_spot_market_data_connector,
        bybit_spot_market_data_scope_summary=bybit_spot_market_data_scope.truth,
        bybit_spot_market_data_apply_truth=_build_bybit_runtime_apply_truth(
            settings=runtime_settings,
            contour="spot",
            resolved_scope=bybit_spot_market_data_scope,
            connector=bybit_spot_market_data_connector,
        ),
        bybit_linear_v2_transport=bybit_linear_v2_transport,
        bybit_spot_v2_transport=bybit_spot_v2_transport,
        bybit_spot_v2_recovery=bybit_spot_v2_recovery,
    )
    runtime._update_runtime_diagnostics(
        composition_root_built=True,
        runtime_started=False,
        runtime_ready=False,
        startup_state="built",
        shutdown_state="not_shutting_down",
        bootstrap_module=runtime.identity.bootstrap_module,
        bootstrap_mode=runtime.identity.bootstrap_mode,
        active_risk_path=runtime.identity.active_risk_path,
        config_identity=runtime.identity.config_identity,
        config_revision=runtime.identity.config_revision,
        failure_reason=None,
        degraded_reasons=[],
    )
    runtime.bybit_spot_module = _build_bybit_spot_module(runtime)

    logger.info(
        "Production composition root собран",
        bootstrap_module=runtime.identity.bootstrap_module,
        version=runtime.identity.version,
        config_identity=runtime.identity.config_identity,
        config_revision=runtime.identity.config_revision,
        active_risk_path=runtime.identity.active_risk_path,
        legacy_risk_listener_enabled=runtime.policy.include_legacy_risk_listener,
        readiness_status="not_ready",
    )
    return runtime


def _build_bybit_spot_module(runtime: ProductionRuntime) -> BybitSpotModule:
    return BybitSpotModule(
        runtime=runtime,
        deps=BybitSpotModuleDeps(
            build_connector_screen_projection=_build_bybit_connector_screen_projection,
            resolve_runtime_generation=_resolve_bybit_connector_runtime_generation,
            build_runtime_signature=_build_bybit_runtime_signature,
            build_trade_ledger_query_service=_build_canonical_bybit_trade_ledger_query_service,
            reuse_scope_if_possible=_reuse_bybit_universe_scope_if_possible,
            resolve_canonical_scope_async=_resolve_canonical_bybit_spot_market_data_scope_async,
            build_runtime_apply_truth=_build_bybit_runtime_apply_truth,
            build_selected_connector=_build_selected_bybit_spot_market_data_connector,
            build_transport_connector=_build_bybit_spot_v2_transport_connector,
            build_recovery_orchestrator=_build_bybit_spot_v2_recovery_orchestrator,
            resolve_disabled_toggle_scope=_resolve_disabled_bybit_toggle_scope,
            resolve_monitoring_symbols=_resolve_bybit_spot_v2_monitoring_symbols,
            resolve_min_trade_count_24h=_resolve_bybit_min_trade_count_24h,
            resolve_spot_primary_lifecycle_state=_resolve_spot_primary_lifecycle_state,
            join_timeout_seconds=_BYBIT_CONNECTOR_JOIN_TIMEOUT_SECONDS,
            query_exact_trade_counts_uncached=bybit_spot_module_lib.query_exact_trade_counts_by_symbol_uncached,
            query_exact_trade_count_snapshots_uncached=bybit_spot_module_lib.query_exact_trade_count_snapshots_by_symbol_uncached,
            update_settings=update_settings,
        ),
    )


def _build_legacy_canonical_bybit_market_data_connector(
    *,
    settings: Settings,
    db_manager: DatabaseManager,
    market_data_runtime: MarketDataRuntime,
    resolved_scope: _ResolvedBybitConnectorScope,
) -> BybitMarketDataConnector | None:
    """Build the current legacy Bybit linear connector support path.

    This wiring remains the active production path today, but it is now treated as
    the legacy/support contour. New feature work should land in a dedicated v2 path
    instead of expanding this constructor further.
    """
    enabled = bool(getattr(settings, "bybit_market_data_connector_enabled", False))
    if not enabled:
        return None
    symbols = resolved_scope.symbols
    if not symbols:
        return None
    return create_bybit_market_data_connector(
        symbols=symbols,
        market_data_runtime=market_data_runtime,
        config=BybitMarketDataConnectorConfig.from_settings(settings),
        universe_scope_mode=True,
        universe_min_trade_count_24h=resolved_scope.truth.trade_count_filter_minimum,
        ledger_trade_count_query_service=_build_canonical_bybit_trade_ledger_query_service(
            db_manager=db_manager
        ),
        ledger_repository=_build_canonical_bybit_trade_ledger_repository(db_manager=db_manager),
    )


def _build_v2_canonical_bybit_market_data_connector(
    *,
    settings: Settings,
    db_manager: DatabaseManager,
    market_data_runtime: MarketDataRuntime,
    resolved_scope: _ResolvedBybitConnectorScope,
) -> BybitMarketDataConnector | None:
    """Reserve a separate v2 wiring boundary for the future Bybit linear path.

    This entrypoint is intentionally disabled for now. It exists only to stop
    new feature work from extending the legacy constructor by default.
    """
    _ = (settings, db_manager, market_data_runtime, resolved_scope)
    return None


def _build_legacy_canonical_bybit_spot_market_data_connector(
    *,
    settings: Settings,
    db_manager: DatabaseManager,
    market_data_runtime: MarketDataRuntime,
    resolved_scope: _ResolvedBybitConnectorScope,
) -> BybitSpotMarketDataConnector | None:
    """Build the current legacy Bybit spot connector support path.

    This wiring remains the active production path today, but it is now treated as
    the legacy/support contour. New feature work should land in a dedicated v2 path
    instead of expanding this constructor further.
    """
    enabled = bool(getattr(settings, "bybit_spot_market_data_connector_enabled", False))
    if not enabled:
        return None
    symbols = resolved_scope.symbols
    if not symbols:
        return None
    return create_bybit_spot_market_data_connector(
        symbols=symbols,
        market_data_runtime=market_data_runtime,
        config=BybitSpotMarketDataConnectorConfig.from_settings(settings),
        universe_scope_mode=True,
        universe_min_trade_count_24h=resolved_scope.truth.trade_count_filter_minimum,
        ledger_trade_count_query_service=_build_canonical_bybit_trade_ledger_query_service(
            db_manager=db_manager
        ),
        ledger_repository=_build_canonical_bybit_trade_ledger_repository(db_manager=db_manager),
    )


def _build_v2_canonical_bybit_spot_market_data_connector(
    *,
    settings: Settings,
    db_manager: DatabaseManager,
    market_data_runtime: MarketDataRuntime,
    resolved_scope: _ResolvedBybitConnectorScope,
) -> BybitSpotMarketDataConnector | None:
    """Reserve a separate v2 wiring boundary for the future Bybit spot path.

    This entrypoint is intentionally disabled for now. It exists only to stop
    new feature work from extending the legacy constructor by default.
    """
    _ = (settings, db_manager, market_data_runtime, resolved_scope)
    return None


def _build_bybit_spot_v2_transport_connector(
    *,
    settings: Settings,
    db_manager: DatabaseManager,
    market_data_runtime: MarketDataRuntime,
    resolved_scope: _ResolvedBybitConnectorScope | None = None,
) -> BybitSpotV2Transport | None:
    """Build the separate spot v2 transport path as the primary spot runtime by default."""
    orderbook_symbol_cap = 64
    if not _is_bybit_spot_v2_transport_enabled(settings=settings):
        return None
    trade_symbols = (
        _resolve_bybit_spot_v2_monitoring_symbols(resolved_scope=resolved_scope)
        if resolved_scope is not None
        else _resolve_bybit_spot_v2_transport_symbols(settings=settings)
    )
    if not trade_symbols:
        return None
    orderbook_symbols = (
        tuple(
            str(symbol)
            for symbol in (
                resolved_scope.truth.selected_symbols
                or resolved_scope.symbols
            )
            if isinstance(symbol, str)
        )[:orderbook_symbol_cap]
        if resolved_scope is not None
        else trade_symbols[:orderbook_symbol_cap]
    )
    return create_bybit_spot_v2_transport(
        symbols=trade_symbols,
        orderbook_symbols=orderbook_symbols,
        config=BybitSpotV2TransportConfig.from_settings(settings),
        market_data_runtime=market_data_runtime,
        live_trade_ledger_repository=BybitSpotV2LiveTradeLedgerRepository(db_manager),
    )


def _build_bybit_linear_v2_transport_connector(
    *,
    settings: Settings,
    market_data_runtime: MarketDataRuntime,
) -> BybitLinearV2Transport | None:
    """Build the separate linear v2 transport path, disabled by default."""
    if not _is_bybit_linear_v2_transport_enabled():
        return None
    symbols = _resolve_bybit_linear_v2_transport_symbols(settings=settings)
    if not symbols:
        return None
    return create_bybit_linear_v2_transport(
        symbols=symbols,
        config=BybitLinearV2TransportConfig.from_settings(settings),
        market_data_runtime=market_data_runtime,
    )


def _build_bybit_spot_v2_recovery_orchestrator(
    *,
    settings: Settings,
    db_manager: DatabaseManager,
    resolved_scope: _ResolvedBybitConnectorScope | None = None,
) -> BybitSpotV2RecoveryCoordinator | None:
    """Build separate non-blocking recovery orchestration for the primary spot v2 path."""
    if not _is_bybit_spot_v2_recovery_enabled(settings=settings):
        return None
    symbols = (
        _resolve_bybit_spot_v2_monitoring_symbols(resolved_scope=resolved_scope)
        if resolved_scope is not None
        else _resolve_bybit_spot_v2_recovery_symbols(settings=settings)
    )
    if not symbols:
        return None
    window_hours = _resolve_bybit_spot_v2_recovery_window_hours()
    return BybitSpotV2RecoveryCoordinator(
        symbols=symbols,
        window_hours=window_hours,
        db_manager=db_manager,
        persisted_query_service=BybitSpotV2PersistedQueryService(db_manager),
        archive_loader_runner=lambda **kwargs: run_bybit_spot_v2_archive_loader(
            db_manager=db_manager,
            **kwargs,
        ),
        observed_at_factory=lambda: datetime.now(tz=UTC),
    )


def _resolve_bybit_connector_runtime_generation(
    *,
    contour: str,
) -> str:
    """Resolve explicit runtime generation while keeping spot on v2 by default."""
    if contour == "spot":
        raw_value = os.getenv("CRYPTOTEHNOLOG_BYBIT_SPOT_RUNTIME_MODE", "")
        normalized = raw_value.strip().lower()
        if normalized in {"legacy", "v2"}:
            return normalized
        return "v2"
    return "legacy"


def _resolve_bybit_spot_v2_monitoring_symbols(
    *,
    resolved_scope: _ResolvedBybitConnectorScope,
) -> tuple[str, ...]:
    coarse_symbols = (
        resolved_scope.truth.coarse_selected_symbols
        or resolved_scope.truth.selected_symbols
        or resolved_scope.symbols
    )
    return tuple(str(symbol) for symbol in coarse_symbols if str(symbol))


def _is_bybit_spot_v2_transport_enabled(*, settings: Settings | None = None) -> bool:
    raw_value = os.getenv("CRYPTOTEHNOLOG_BYBIT_SPOT_V2_TRANSPORT_ENABLED", "")
    normalized = raw_value.strip().lower()
    if normalized:
        if normalized not in {"1", "true", "yes", "on"}:
            return False
        if settings is None:
            return True
        return bool(getattr(settings, "bybit_spot_market_data_connector_enabled", False))
    if _resolve_bybit_connector_runtime_generation(contour="spot") != "v2":
        return False
    if settings is None:
        return True
    return bool(getattr(settings, "bybit_spot_market_data_connector_enabled", False))


def _is_bybit_linear_v2_transport_enabled() -> bool:
    raw_value = os.getenv("CRYPTOTEHNOLOG_BYBIT_LINEAR_V2_TRANSPORT_ENABLED", "")
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _is_bybit_spot_v2_recovery_enabled(*, settings: Settings | None = None) -> bool:
    raw_value = os.getenv("CRYPTOTEHNOLOG_BYBIT_SPOT_V2_RECOVERY_ENABLED", "")
    normalized = raw_value.strip().lower()
    if normalized:
        return normalized in {"1", "true", "yes", "on"}
    return _is_bybit_spot_v2_transport_enabled(settings=settings)


def _resolve_bybit_spot_v2_transport_symbols(
    *,
    settings: Settings,
) -> tuple[str, ...]:
    raw_override = os.getenv("CRYPTOTEHNOLOG_BYBIT_SPOT_V2_TRANSPORT_SYMBOLS", "")
    if raw_override.strip():
        return tuple(
            symbol.strip()
            for symbol in raw_override.split(",")
            if symbol.strip()
        )
    resolved_scope = _resolve_bybit_connector_scope(
        settings=settings,
        enabled=True,
        contour="spot",
        capture_discovery_errors=True,
    )
    return resolved_scope.symbols


def _resolve_bybit_linear_v2_transport_symbols(
    *,
    settings: Settings,
) -> tuple[str, ...]:
    raw_override = os.getenv("CRYPTOTEHNOLOG_BYBIT_LINEAR_V2_TRANSPORT_SYMBOLS", "")
    if raw_override.strip():
        return tuple(
            symbol.strip()
            for symbol in raw_override.split(",")
            if symbol.strip()
        )
    resolved_scope = _resolve_bybit_connector_scope(
        settings=settings,
        enabled=True,
        contour="linear",
        capture_discovery_errors=True,
    )
    return resolved_scope.symbols


def _resolve_bybit_spot_v2_recovery_symbols(
    *,
    settings: Settings,
) -> tuple[str, ...]:
    raw_override = os.getenv("CRYPTOTEHNOLOG_BYBIT_SPOT_V2_RECOVERY_SYMBOLS", "")
    if raw_override.strip():
        return tuple(
            symbol.strip()
            for symbol in raw_override.split(",")
            if symbol.strip()
        )
    return _resolve_bybit_spot_v2_transport_symbols(settings=settings)


def _resolve_bybit_spot_v2_recovery_window_hours() -> int:
    raw_value = os.getenv("CRYPTOTEHNOLOG_BYBIT_SPOT_V2_RECOVERY_WINDOW_HOURS", "")
    if not raw_value.strip():
        return 24
    with contextlib.suppress(ValueError):
        parsed = int(raw_value)
        if parsed > 0:
            return parsed
    return 24


def _resolve_bybit_spot_v2_compact_diagnostics_symbols(
    *,
    settings: Settings,
    transport: BybitSpotV2Transport | None,
) -> tuple[str, ...]:
    raw_override = os.getenv("CRYPTOTEHNOLOG_BYBIT_SPOT_V2_DIAGNOSTICS_SYMBOLS", "")
    if raw_override.strip():
        return tuple(
            symbol.strip()
            for symbol in raw_override.split(",")
            if symbol.strip()
        )
    if transport is not None and transport.symbols:
        return tuple(transport.symbols)
    _ = settings
    return ("BTC/USDT", "ETH/USDT")


def _build_selected_bybit_market_data_connector(
    *,
    settings: Settings,
    db_manager: DatabaseManager,
    market_data_runtime: MarketDataRuntime,
    resolved_scope: _ResolvedBybitConnectorScope,
) -> BybitMarketDataConnector | None:
    generation = _resolve_bybit_connector_runtime_generation(contour="linear")
    if generation == "v2":
        return _build_v2_canonical_bybit_market_data_connector(
            settings=settings,
            db_manager=db_manager,
            market_data_runtime=market_data_runtime,
            resolved_scope=resolved_scope,
        )
    return _build_legacy_canonical_bybit_market_data_connector(
        settings=settings,
        db_manager=db_manager,
        market_data_runtime=market_data_runtime,
        resolved_scope=resolved_scope,
    )


def _build_selected_bybit_spot_market_data_connector(
    *,
    settings: Settings,
    db_manager: DatabaseManager,
    market_data_runtime: MarketDataRuntime,
    resolved_scope: _ResolvedBybitConnectorScope,
) -> BybitSpotMarketDataConnector | None:
    generation = _resolve_bybit_connector_runtime_generation(contour="spot")
    if generation == "v2":
        return _build_v2_canonical_bybit_spot_market_data_connector(
            settings=settings,
            db_manager=db_manager,
            market_data_runtime=market_data_runtime,
            resolved_scope=resolved_scope,
        )
    return _build_legacy_canonical_bybit_spot_market_data_connector(
        settings=settings,
        db_manager=db_manager,
        market_data_runtime=market_data_runtime,
        resolved_scope=resolved_scope,
    )


def _build_canonical_bybit_trade_ledger_query_service(
    *,
    db_manager: DatabaseManager,
) -> BybitTradeLedgerTradeCountQueryService | None:
    pool = db_manager.pool
    if pool is None:
        return None
    repository = BybitTradeLedgerRepository(pool)
    return BybitTradeLedgerTradeCountQueryService(repository)


def _build_canonical_bybit_trade_ledger_repository(
    *,
    db_manager: DatabaseManager,
) -> BybitTradeLedgerRepository | None:
    pool = db_manager.pool
    if pool is None:
        return None
    return BybitTradeLedgerRepository(pool)


def _resolve_canonical_bybit_market_data_scope(
    *,
    settings: Settings,
    capture_discovery_errors: bool = True,
) -> _ResolvedBybitConnectorScope:
    return _resolve_bybit_connector_scope(
        settings=settings,
        enabled=bool(getattr(settings, "bybit_market_data_connector_enabled", False)),
        contour="linear",
        capture_discovery_errors=capture_discovery_errors,
    )


def _resolve_canonical_bybit_spot_market_data_scope(
    *,
    settings: Settings,
    capture_discovery_errors: bool = True,
) -> _ResolvedBybitConnectorScope:
    return _resolve_bybit_connector_scope(
        settings=settings,
        enabled=bool(getattr(settings, "bybit_spot_market_data_connector_enabled", False)),
        contour="spot",
        capture_discovery_errors=capture_discovery_errors,
    )


async def _resolve_canonical_bybit_spot_market_data_scope_async(
    *,
    settings: Settings,
    capture_discovery_errors: bool = True,
) -> _ResolvedBybitConnectorScope:
    return await asyncio.to_thread(
        _resolve_canonical_bybit_spot_market_data_scope,
        settings=settings,
        capture_discovery_errors=capture_discovery_errors,
    )


def _resolve_bybit_connector_scope(
    *,
    settings: Settings,
    enabled: bool,
    contour: str,
    capture_discovery_errors: bool = False,
) -> _ResolvedBybitConnectorScope:
    discovery_signature = _build_bybit_discovery_signature(
        settings=settings,
        contour=contour,
    )
    try:
        selection = discover_bybit_universe(
            BybitUniverseDiscoveryConfig(
                contour=cast("Any", contour),
                rest_base_url=(
                    "https://api-testnet.bybit.com"
                    if settings.bybit_testnet
                    else "https://api.bybit.com"
                ),
                min_quote_volume_24h_usd=_resolve_bybit_min_quote_volume_24h_usd(
                    settings=settings,
                    contour=contour,
                ),
                min_trade_count_24h=_resolve_bybit_min_trade_count_24h(
                    settings=settings,
                    contour=contour,
                ),
                spot_quote_asset_filter=(
                    _resolve_bybit_spot_quote_asset_filter(settings=settings)
                    if contour == "spot"
                    else None
                ),
                max_symbols_per_scope=(
                    _resolve_bybit_max_symbols_per_scope(settings=settings)
                    if contour == "linear"
                    else None
                ),
            )
        )
    except (OSError, TimeoutError, URLError) as exc:
        if enabled and not capture_discovery_errors:
            raise RuntimeError(f"Bybit {contour} universe discovery is unavailable: {exc}") from exc
        return _ResolvedBybitConnectorScope(
            symbols=(),
            truth=_BybitConnectorScopeTruth(
                scope_mode="universe",
                trade_count_filter_minimum=_resolve_bybit_min_trade_count_24h(
                    settings=settings,
                    contour=contour,
                ),
                discovery_status="unavailable",
                discovery_error=str(exc),
                discovery_signature=discovery_signature,
            ),
        )
    return _ResolvedBybitConnectorScope(
        symbols=selection.selected_symbols,
        truth=_BybitConnectorScopeTruth(
            scope_mode=selection.scope_mode,
            trade_count_filter_minimum=_resolve_bybit_min_trade_count_24h(
                settings=settings,
                contour=contour,
            ),
            discovery_status="ready",
            total_instruments_discovered=selection.total_instruments_discovered,
            instruments_passed_coarse_filter=selection.instruments_passed_coarse_filter,
            instruments_passed_final_filter=selection.instruments_passed_coarse_filter,
            discovery_signature=discovery_signature,
            coarse_selected_symbols=selection.selected_symbols,
            coarse_selected_quote_volume_24h_usd_by_symbol=(
                selection.selected_quote_volume_24h_usd_by_symbol
            ),
            selected_symbols=selection.selected_symbols,
            selected_quote_volume_24h_usd_by_symbol=(
                selection.selected_quote_volume_24h_usd_by_symbol
            ),
        ),
    )


def _resolve_disabled_bybit_toggle_scope(
    *,
    settings: Settings,
    contour: str,
    existing_truth: _BybitConnectorScopeTruth | None,
) -> _ResolvedBybitConnectorScope:
    if existing_truth is not None and existing_truth.scope_mode == "universe":
        return _ResolvedBybitConnectorScope(symbols=(), truth=existing_truth)
    return _ResolvedBybitConnectorScope(
        symbols=(),
        truth=_BybitConnectorScopeTruth(
            scope_mode="universe",
            trade_count_filter_minimum=_resolve_bybit_min_trade_count_24h(
                settings=settings,
                contour=contour,
            ),
            discovery_status="not_applicable",
        ),
    )


def _reuse_bybit_universe_scope_if_possible(
    *,
    settings: Settings,
    contour: str,
    existing_truth: _BybitConnectorScopeTruth | None,
) -> _ResolvedBybitConnectorScope | None:
    if existing_truth is None or existing_truth.scope_mode != "universe":
        return None
    discovery_signature = _build_bybit_discovery_signature(
        settings=settings,
        contour=contour,
    )
    if existing_truth.discovery_signature != discovery_signature:
        return None
    next_trade_count_minimum = _resolve_bybit_min_trade_count_24h(
        settings=settings,
        contour=contour,
    )
    if contour == "spot" and int(existing_truth.trade_count_filter_minimum) != next_trade_count_minimum:
        return None
    truth = replace(
        existing_truth,
        trade_count_filter_minimum=next_trade_count_minimum,
        discovery_signature=discovery_signature,
    )
    coarse_symbols = truth.coarse_selected_symbols or truth.selected_symbols
    return _ResolvedBybitConnectorScope(
        symbols=coarse_symbols,
        truth=truth,
    )


def _disabled_bybit_connector_diagnostics(*, enabled: bool = False) -> dict[str, object]:
    return _build_bybit_connector_screen_projection(
        connector=None,
        exchange="bybit",
        enabled=enabled,
        scope_truth=None,
        apply_truth=None,
    )


def _disabled_bybit_spot_connector_diagnostics(*, enabled: bool = False) -> dict[str, object]:
    return _build_bybit_connector_screen_projection(
        connector=None,
        exchange="bybit_spot",
        enabled=enabled,
        scope_truth=None,
        apply_truth=None,
    )


def _build_disabled_bybit_spot_v2_transport_diagnostics(
    *,
    enabled: bool,
) -> dict[str, object]:
    transport_status = "idle" if enabled else "disabled"
    return {
        "enabled": enabled,
        "generation": "v2",
        "exchange": "bybit_spot_v2_transport",
        "symbols": (),
        "topics": (),
        "public_stream_url": (
            BybitSpotV2TransportConfig.from_settings(get_settings()).public_stream_url
        ),
        "messages_received_count": 0,
        "trade_ingest_count": 0,
        "orderbook_ingest_count": 0,
        "trade_seen": False,
        "orderbook_seen": False,
        "trade_seen_symbols": (),
        "orderbook_seen_symbols": (),
        "best_bid": None,
        "best_ask": None,
        "persisted_trade_count": 0,
        "last_persisted_trade_at": None,
        "last_persisted_trade_symbol": None,
        "last_error": None,
        "transport_status": transport_status,
        "recovery_status": "idle" if enabled else "disabled",
        "subscription_alive": False,
        "last_message_at": None,
        "message_age_ms": None,
        "transport_rtt_ms": None,
        "last_ping_sent_at": None,
        "last_pong_at": None,
        "application_ping_sent_at": None,
        "application_pong_at": None,
        "application_heartbeat_latency_ms": None,
        "last_ping_timeout_at": None,
        "last_ping_timeout_message_age_ms": None,
        "last_ping_timeout_loop_lag_ms": None,
        "last_ping_timeout_backfill_status": None,
        "last_ping_timeout_processed_archives": None,
        "last_ping_timeout_total_archives": None,
        "last_ping_timeout_cache_source": None,
        "last_ping_timeout_ignored_due_to_recent_messages": False,
        "degraded_reason": None,
        "last_disconnect_reason": None,
        "retry_count": None,
        "ready": False,
        "started": False,
        "lifecycle_state": transport_status,
        "reset_required": False,
    }


def _build_disabled_bybit_linear_v2_transport_diagnostics(
    *,
    enabled: bool,
) -> dict[str, object]:
    transport_status = "idle" if enabled else "disabled"
    return {
        "enabled": enabled,
        "generation": "v2",
        "exchange": "bybit_linear_v2_transport",
        "symbols": (),
        "topics": (),
        "public_stream_url": (
            BybitLinearV2TransportConfig.from_settings(get_settings()).public_stream_url
        ),
        "messages_received_count": 0,
        "trade_ingest_count": 0,
        "orderbook_ingest_count": 0,
        "trade_seen": False,
        "orderbook_seen": False,
        "trade_seen_symbols": (),
        "orderbook_seen_symbols": (),
        "best_bid": None,
        "best_ask": None,
        "last_error": None,
        "transport_status": transport_status,
        "recovery_status": "idle" if enabled else "disabled",
        "subscription_alive": False,
        "last_message_at": None,
        "message_age_ms": None,
        "transport_rtt_ms": None,
        "last_ping_sent_at": None,
        "last_pong_at": None,
        "application_ping_sent_at": None,
        "application_pong_at": None,
        "application_heartbeat_latency_ms": None,
        "last_ping_timeout_at": None,
        "last_ping_timeout_message_age_ms": None,
        "last_ping_timeout_loop_lag_ms": None,
        "last_ping_timeout_backfill_status": None,
        "last_ping_timeout_processed_archives": None,
        "last_ping_timeout_total_archives": None,
        "last_ping_timeout_cache_source": None,
        "last_ping_timeout_ignored_due_to_recent_messages": False,
        "degraded_reason": None,
        "last_disconnect_reason": None,
        "retry_count": None,
        "ready": False,
        "started": False,
        "lifecycle_state": transport_status,
        "reset_required": False,
    }


def _build_disabled_bybit_spot_v2_recovery_diagnostics(
    *,
    enabled: bool,
) -> dict[str, object]:
    lifecycle_state = "idle" if enabled else "disabled"
    return {
        "component": "bybit_spot_v2_recovery",
        "exchange": "bybit_spot_v2_recovery",
        "generation": "v2",
        "status": lifecycle_state,
        "stage": lifecycle_state,
        "target_symbols": (),
        "observed_at": None,
        "window_started_at": None,
        "window_hours": _resolve_bybit_spot_v2_recovery_window_hours(),
        "started_at": None,
        "finished_at": None,
        "last_error": None,
        "reason": None,
        "processed_archives": 0,
        "written_archive_records": 0,
        "skipped_archive_records": 0,
        "archive_dates": (),
        "last_progress_checkpoint": None,
        "ready": False,
    }


def _project_bybit_connector_diagnostics(  # noqa: PLR0912, PLR0915
    connector_diagnostics: dict[str, object],
    scope_truth: _BybitConnectorScopeTruth | None,
    apply_truth: _BybitRuntimeApplyTruth | None,
) -> dict[str, object]:
    from cryptotechnolog.dashboard.projections.bybit_connector_diagnostics import (
        DiagnosticsProjection,
    )

    projection_snapshot = _projection_snapshot_from_operator_payload(
        connector_diagnostics=connector_diagnostics,
        scope_truth=scope_truth,
    )
    projection = DiagnosticsProjection.from_snapshot(
        projection_snapshot,
        apply_truth=_projection_apply_truth(apply_truth),
    )
    return projection.to_dict()


def _build_bybit_connector_screen_projection(
    *,
    connector: BybitMarketDataConnector | BybitSpotMarketDataConnector | None,
    exchange: str,
    enabled: bool,
    scope_truth: _BybitConnectorScopeTruth | None,
    apply_truth: _BybitRuntimeApplyTruth | None,
) -> dict[str, object]:
    from cryptotechnolog.dashboard.projections.bybit_connector_diagnostics import (
        DiagnosticsProjection,
        build_disabled_bybit_projection_snapshot,
    )

    if connector is not None:
        snapshot = connector.build_projection_snapshot(
            compact_cutover_payload=(exchange == "bybit_spot")
        )
        snapshot = replace(snapshot, discovery=_enrich_discovery_snapshot(snapshot.discovery, scope_truth))
    else:
        snapshot = build_disabled_bybit_projection_snapshot(
            exchange=exchange,
            enabled=enabled,
            discovery=_bootstrap_discovery_snapshot(exchange=exchange, scope_truth=scope_truth),
            admission=_bootstrap_admission_snapshot(scope_truth=scope_truth),
        )
    projection = DiagnosticsProjection.from_snapshot(
        snapshot,
        apply_truth=_projection_apply_truth(apply_truth),
    )
    return projection.to_dict()


def _projection_apply_truth(
    apply_truth: _BybitRuntimeApplyTruth | None,
) -> object | None:
    if apply_truth is None:
        return None
    from cryptotechnolog.dashboard.projections.bybit_connector_diagnostics import (
        _BybitProjectionApplyTruth,
    )

    return _BybitProjectionApplyTruth(
        desired_scope_mode=apply_truth.desired_scope_mode,
        desired_trade_count_filter_minimum=apply_truth.desired_trade_count_filter_minimum,
        applied_scope_mode=apply_truth.applied_scope_mode,
        applied_trade_count_filter_minimum=apply_truth.applied_trade_count_filter_minimum,
        policy_apply_status=apply_truth.policy_apply_status,
        policy_apply_reason=apply_truth.policy_apply_reason,
    )


def _bootstrap_discovery_snapshot(
    *,
    exchange: str,
    scope_truth: _BybitConnectorScopeTruth | None,
) -> BybitDiscoverySnapshot:
    if scope_truth is None:
        return BybitDiscoverySnapshot(
            exchange=exchange,
            scope_mode="universe",
            discovery_status="not_applicable",
            coarse_candidate_symbols=(),
        )
    return BybitDiscoverySnapshot(
        exchange=exchange,
        scope_mode=scope_truth.scope_mode,
        coarse_candidate_symbols=scope_truth.selected_symbols,
        discovery_status=scope_truth.discovery_status,
        total_instruments_discovered=scope_truth.total_instruments_discovered,
        instruments_passed_coarse_filter=scope_truth.instruments_passed_coarse_filter,
        quote_turnover_24h_by_symbol=scope_truth.selected_quote_volume_24h_usd_by_symbol,
        quote_turnover_last_error=scope_truth.discovery_error,
    )


def _bootstrap_admission_snapshot(
    *,
    scope_truth: _BybitConnectorScopeTruth | None,
) -> BybitAdmissionSnapshot:
    return BybitAdmissionSnapshot(
        scope_mode=scope_truth.scope_mode if scope_truth is not None else "universe",
        trade_count_filter_minimum=(
            scope_truth.trade_count_filter_minimum if scope_truth is not None else 0
        ),
        trade_count_admission_basis="derived_operational_truth",
        trade_count_admission_truth_owner=(
            FINAL_BYBIT_TRADE_COUNT_TRUTH_OWNERSHIP.admission_truth_owner
        ),
        trade_count_admission_truth_source=(
            FINAL_BYBIT_TRADE_COUNT_TRUTH_OWNERSHIP.admission_truth_source
        ),
        trade_count_admission_candidate_symbols=(
            scope_truth.selected_symbols if scope_truth is not None else ()
        ),
        active_subscribed_symbols=(),
        trade_count_qualifying_symbols=(),
        trade_count_excluded_symbols=(),
        selected_symbols=scope_truth.selected_symbols if scope_truth is not None else (),
        readiness_state=None,
    )


def _enrich_discovery_snapshot(
    discovery: BybitDiscoverySnapshot,
    scope_truth: _BybitConnectorScopeTruth | None,
) -> BybitDiscoverySnapshot:
    if scope_truth is None:
        return discovery
    quote_turnover_24h_by_symbol = (
        discovery.quote_turnover_24h_by_symbol
        if discovery.quote_turnover_24h_by_symbol
        else scope_truth.selected_quote_volume_24h_usd_by_symbol
    )
    quote_turnover_last_error = discovery.quote_turnover_last_error or scope_truth.discovery_error
    return replace(
        discovery,
        scope_mode=scope_truth.scope_mode,
        discovery_status=scope_truth.discovery_status,
        total_instruments_discovered=scope_truth.total_instruments_discovered,
        instruments_passed_coarse_filter=scope_truth.instruments_passed_coarse_filter,
        quote_turnover_24h_by_symbol=quote_turnover_24h_by_symbol,
        quote_turnover_last_error=quote_turnover_last_error,
    )


def _projection_snapshot_from_operator_payload(
    *,
    connector_diagnostics: dict[str, object],
    scope_truth: _BybitConnectorScopeTruth | None,
) -> BybitProjectionSnapshot:
    from cryptotechnolog.dashboard.projections.bybit_connector_diagnostics import (
        build_disabled_bybit_projection_snapshot,
    )

    exchange = str(connector_diagnostics.get("exchange", "bybit"))
    symbols = tuple(
        symbol
        for symbol in connector_diagnostics.get("symbols", ())
        if isinstance(symbol, str)
    )
    primary_symbol = (
        str(connector_diagnostics.get("symbol"))
        if isinstance(connector_diagnostics.get("symbol"), str)
        else None
    )
    discovery = _enrich_discovery_snapshot(
        BybitDiscoverySnapshot(
            exchange=exchange,
            scope_mode=str(connector_diagnostics.get("scope_mode", "universe")),
            coarse_candidate_symbols=symbols,
            discovery_status=str(connector_diagnostics.get("discovery_status", "not_applicable")),
            total_instruments_discovered=connector_diagnostics.get("total_instruments_discovered")
            if isinstance(connector_diagnostics.get("total_instruments_discovered"), int)
            else None,
            instruments_passed_coarse_filter=connector_diagnostics.get(
                "instruments_passed_coarse_filter"
            )
            if isinstance(connector_diagnostics.get("instruments_passed_coarse_filter"), int)
            else None,
            quote_turnover_last_error=connector_diagnostics.get("discovery_error")
            if isinstance(connector_diagnostics.get("discovery_error"), str)
            else None,
        ),
        scope_truth,
    )
    transport = build_disabled_bybit_projection_snapshot(
        exchange=exchange,
        enabled=bool(connector_diagnostics.get("enabled", False)),
        discovery=discovery,
        admission=_bootstrap_admission_snapshot(scope_truth=scope_truth),
    ).transport
    base_snapshot = build_disabled_bybit_projection_snapshot(
        exchange=exchange,
        enabled=bool(connector_diagnostics.get("enabled", False)),
        discovery=discovery,
        admission=_bootstrap_admission_snapshot(scope_truth=scope_truth),
    )
    raw_symbol_snapshots = connector_diagnostics.get("symbol_snapshots", ())
    symbol_snapshots = tuple(
        BybitTradeTruthSymbolSnapshot(
            symbol=str(snapshot.get("symbol", "")),
            trade_seen=bool(snapshot.get("trade_seen", False)),
            orderbook_seen=bool(snapshot.get("orderbook_seen", False)),
            best_bid=snapshot.get("best_bid") if isinstance(snapshot.get("best_bid"), str) else None,
            best_ask=snapshot.get("best_ask") if isinstance(snapshot.get("best_ask"), str) else None,
            volume_24h_usd=(
                snapshot.get("volume_24h_usd")
                if isinstance(snapshot.get("volume_24h_usd"), str)
                else None
            ),
            derived_trade_count_24h=(
                snapshot.get("derived_trade_count_24h")
                if isinstance(snapshot.get("derived_trade_count_24h"), int)
                else None
            ),
            bucket_trade_count_24h=(
                snapshot.get("bucket_trade_count_24h")
                if isinstance(snapshot.get("bucket_trade_count_24h"), int)
                else None
            ),
            ledger_trade_count_24h=(
                snapshot.get("ledger_trade_count_24h")
                if isinstance(snapshot.get("ledger_trade_count_24h"), int)
                else None
            ),
            ledger_trade_count_status="unavailable",
            ledger_trade_count_symbol_last_error=None,
            ledger_trade_count_symbol_last_synced_at=None,
            trade_count_reconciliation_verdict=str(
                snapshot.get("trade_count_reconciliation_verdict", "not_comparable")
            ),
            trade_count_reconciliation_reason=str(
                snapshot.get("trade_count_reconciliation_reason", "not_comparable")
            ),
            trade_count_reconciliation_absolute_diff=(
                snapshot.get("trade_count_reconciliation_absolute_diff")
                if isinstance(snapshot.get("trade_count_reconciliation_absolute_diff"), int)
                else None
            ),
            trade_count_reconciliation_tolerance=(
                snapshot.get("trade_count_reconciliation_tolerance")
                if isinstance(snapshot.get("trade_count_reconciliation_tolerance"), int)
                else None
            ),
            trade_count_cutover_readiness_state=str(
                snapshot.get("trade_count_cutover_readiness_state", "not_ready")
            ),
            trade_count_cutover_readiness_reason=str(
                snapshot.get("trade_count_cutover_readiness_reason", "not_comparable")
            ),
            observed_trade_count_since_reset=int(
                snapshot.get("observed_trade_count_since_reset", 0)
            ),
            product_trade_count_24h=(
                snapshot.get("product_trade_count_24h")
                if isinstance(snapshot.get("product_trade_count_24h"), int)
                else None
            ),
            product_trade_count_state=str(
                snapshot.get("product_trade_count_state", "pending_validation")
            ),
            product_trade_count_reason=str(
                snapshot.get("product_trade_count_reason", "pending_validation_present")
            ),
        )
        for snapshot in raw_symbol_snapshots
        if isinstance(snapshot, dict) and isinstance(snapshot.get("symbol"), str)
    )
    trade_truth = base_snapshot.trade_truth
    admission = replace(
        base_snapshot.admission,
        active_subscribed_symbols=symbols,
        selected_symbols=scope_truth.selected_symbols if scope_truth is not None else symbols,
    )
    return BybitProjectionSnapshot(
        exchange=exchange,
        enabled=bool(connector_diagnostics.get("enabled", False)),
        primary_symbol=primary_symbol,
        symbols=symbols,
        discovery=discovery,
        transport=replace(
            transport,
            transport_status=str(connector_diagnostics.get("transport_status", transport.transport_status)),
            recovery_status=str(connector_diagnostics.get("recovery_status", transport.recovery_status)),
            subscription_alive=bool(connector_diagnostics.get("subscription_alive", False)),
            last_message_at=connector_diagnostics.get("last_message_at")
            if isinstance(connector_diagnostics.get("last_message_at"), str)
            else None,
            message_age_ms=connector_diagnostics.get("message_age_ms")
            if isinstance(connector_diagnostics.get("message_age_ms"), int)
            else None,
            transport_rtt_ms=connector_diagnostics.get("transport_rtt_ms")
            if isinstance(connector_diagnostics.get("transport_rtt_ms"), int)
            else None,
            degraded_reason=connector_diagnostics.get("degraded_reason")
            if isinstance(connector_diagnostics.get("degraded_reason"), str)
            else None,
            last_disconnect_reason=connector_diagnostics.get("last_disconnect_reason")
            if isinstance(connector_diagnostics.get("last_disconnect_reason"), str)
            else None,
            retry_count=connector_diagnostics.get("retry_count")
            if isinstance(connector_diagnostics.get("retry_count"), int)
            else None,
            ready=bool(connector_diagnostics.get("ready", False)),
            started=bool(connector_diagnostics.get("started", False)),
            lifecycle_state=connector_diagnostics.get("lifecycle_state")
            if isinstance(connector_diagnostics.get("lifecycle_state"), str)
            else None,
            reset_required=bool(connector_diagnostics.get("reset_required", False)),
        ),
        trade_truth=replace(
            trade_truth,
            symbol_snapshots=symbol_snapshots,
            trade_seen=bool(connector_diagnostics.get("trade_seen", False)),
            orderbook_seen=bool(connector_diagnostics.get("orderbook_seen", False)),
            best_bid=connector_diagnostics.get("best_bid")
            if isinstance(connector_diagnostics.get("best_bid"), str)
            else None,
            best_ask=connector_diagnostics.get("best_ask")
            if isinstance(connector_diagnostics.get("best_ask"), str)
            else None,
            derived_trade_count_state=connector_diagnostics.get("derived_trade_count_state")
            if isinstance(connector_diagnostics.get("derived_trade_count_state"), str)
            else None,
            derived_trade_count_ready=bool(connector_diagnostics.get("derived_trade_count_ready", False)),
            derived_trade_count_backfill_status=connector_diagnostics.get("derived_trade_count_backfill_status")
            if isinstance(connector_diagnostics.get("derived_trade_count_backfill_status"), str)
            else None,
            derived_trade_count_backfill_needed=connector_diagnostics.get("derived_trade_count_backfill_needed")
            if isinstance(connector_diagnostics.get("derived_trade_count_backfill_needed"), bool)
            else None,
        ),
        admission=admission,
    )


def _build_bybit_runtime_apply_truth(
    *,
    settings: Settings,
    contour: str,
    resolved_scope: _ResolvedBybitConnectorScope,
    connector: BybitMarketDataConnector | BybitSpotMarketDataConnector | None,
    apply_status: str = "applied",
    apply_reason: str | None = None,
) -> _BybitRuntimeApplyTruth:
    if contour == "linear":
        enabled = bool(getattr(settings, "bybit_market_data_connector_enabled", False))
    else:
        enabled = bool(getattr(settings, "bybit_spot_market_data_connector_enabled", False))

    if connector is not None:
        connector_scope_mode = getattr(connector, "_universe_scope_mode", None)
        if isinstance(connector_scope_mode, bool):
            applied_scope_mode = "universe"
        else:
            applied_scope_mode = resolved_scope.truth.scope_mode
        connector_threshold = getattr(connector, "_universe_min_trade_count_24h", None)
        if isinstance(connector_threshold, int):
            applied_trade_count_filter_minimum = connector_threshold
        else:
            applied_trade_count_filter_minimum = resolved_scope.truth.trade_count_filter_minimum
    else:
        applied_scope_mode = None
        applied_trade_count_filter_minimum = None
        if not enabled:
            apply_status = "not_running"
        elif resolved_scope.symbols:
            apply_status = "applied"
        else:
            apply_status = "waiting_for_scope"

    return _BybitRuntimeApplyTruth(
        desired_scope_mode=resolved_scope.truth.scope_mode,
        desired_trade_count_filter_minimum=resolved_scope.truth.trade_count_filter_minimum,
        applied_scope_mode=applied_scope_mode,
        applied_trade_count_filter_minimum=applied_trade_count_filter_minimum,
        policy_apply_status=apply_status,
        policy_apply_reason=apply_reason,
    )


def _build_bybit_discovery_signature(*, settings: Settings, contour: str) -> tuple[object, ...]:
    base_signature: tuple[object, ...] = (
        contour,
        "https://api-testnet.bybit.com" if settings.bybit_testnet else "https://api.bybit.com",
        _resolve_bybit_min_quote_volume_24h_usd(settings=settings, contour=contour),
    )
    if contour == "spot":
        return (
            *base_signature,
            _resolve_bybit_spot_quote_asset_filter(settings=settings),
        )
    return (
        *base_signature,
        _resolve_bybit_max_symbols_per_scope(settings=settings),
    )


def _build_bybit_runtime_signature(*, settings: Settings, contour: str) -> tuple[object, ...]:
    if contour == "linear":
        enabled = bool(getattr(settings, "bybit_market_data_connector_enabled", False))
        config = BybitMarketDataConnectorConfig.from_settings(settings)
    else:
        enabled = bool(getattr(settings, "bybit_spot_market_data_connector_enabled", False))
        config = BybitSpotMarketDataConnectorConfig.from_settings(settings)

    base_signature: tuple[object, ...] = (
        contour,
        enabled,
        "universe",
        config,
    )
    trade_count_signature: object = (
        _resolve_bybit_min_trade_count_24h(settings=settings, contour=contour)
        if contour == "spot"
        else _resolve_bybit_min_trade_count_24h(settings=settings, contour=contour) > 0
    )
    return (
        *base_signature,
        trade_count_signature,
        _build_bybit_discovery_signature(settings=settings, contour=contour),
    )


def _resolve_bybit_min_quote_volume_24h_usd(*, settings: Settings, contour: str) -> float:
    if contour == "spot":
        return float(settings.bybit_spot_universe_min_quote_volume_24h_usd)
    return float(settings.bybit_universe_min_quote_volume_24h_usd)


def _resolve_bybit_min_trade_count_24h(*, settings: Settings, contour: str) -> int:
    if contour == "spot":
        return int(settings.bybit_spot_universe_min_trade_count_24h)
    return int(settings.bybit_universe_min_trade_count_24h)


def _resolve_bybit_spot_quote_asset_filter(*, settings: Settings) -> str:
    return str(settings.bybit_spot_quote_asset_filter)


def _resolve_bybit_max_symbols_per_scope(*, settings: Settings) -> int:
    return int(settings.bybit_universe_max_symbols_per_scope)


def _build_risk_bar_completed_event(
    *,
    payload: BarCompletedPayload,
    derived_inputs: RiskDerivedInputsSnapshot,
    orderbook_snapshot: OrderBookSnapshotContract | None,
) -> Event | None:
    """Собрать честный RISK_BAR_COMPLETED только при наличии полного набора truth sources."""
    if orderbook_snapshot is None or not orderbook_snapshot.bids or not orderbook_snapshot.asks:
        return None
    if not derived_inputs.is_fully_ready:
        return None
    if derived_inputs.atr.value is None or derived_inputs.adx.value is None:
        return None

    return Event.new(
        SystemEventType.RISK_BAR_COMPLETED,
        "SHARED_ANALYSIS_RUNTIME",
        {
            "symbol": payload.symbol,
            "exchange": payload.exchange,
            "timeframe": payload.timeframe,
            "open_time": payload.open_time,
            "close_time": payload.close_time,
            "mark_price": payload.close,
            "close": payload.close,
            "atr": str(derived_inputs.atr.value),
            "adx": str(derived_inputs.adx.value),
            "best_bid": str(orderbook_snapshot.bids[0].price),
            "best_ask": str(orderbook_snapshot.asks[0].price),
            "is_stale": bool(payload.is_gap_affected or orderbook_snapshot.is_gap_affected),
        },
    )


async def start_production_runtime(
    *,
    settings: Settings | None = None,
    policy: ProductionBootstrapPolicy | None = None,
) -> ProductionRuntime:
    """Собрать и поднять production runtime."""
    runtime = await build_production_runtime(settings=settings, policy=policy)
    try:
        await runtime.startup()
    except Exception:
        with contextlib.suppress(Exception):
            await runtime.shutdown(force=True, preserve_startup_failure=True)
        raise
    return runtime


async def run_production_runtime(
    *,
    settings: Settings | None = None,
    policy: ProductionBootstrapPolicy | None = None,
) -> None:
    """Запустить production runtime и держать процесс активным до остановки."""
    runtime = await start_production_runtime(settings=settings, policy=policy)
    logger = get_logger(__name__)

    try:
        logger.info(
            "Production runtime перешёл в serve_forever режим",
            bootstrap_module=runtime.identity.bootstrap_module,
            active_risk_path=runtime.identity.active_risk_path,
        )
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        logger.info("Получен сигнал остановки production runtime")
        raise
    finally:
        await runtime.shutdown()

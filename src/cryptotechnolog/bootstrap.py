"""
Production composition root для CRYPTOTEHNOLOG.

Этот модуль является официальной точкой сборки production runtime
в рамках Шага 2 фазы P_5_1.
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import TYPE_CHECKING, Any, cast
from urllib.error import URLError

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
    BybitMarketDataConnector,
    BybitMarketDataConnectorConfig,
    BybitSpotMarketDataConnector,
    BybitSpotMarketDataConnectorConfig,
    BybitUniverseDiscoveryConfig,
    create_bybit_market_data_connector,
    create_bybit_spot_market_data_connector,
    discover_bybit_universe,
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
    discovery_error: str | None = None
    discovery_signature: tuple[object, ...] | None = None
    selected_symbols: tuple[str, ...] = ()
    selected_quote_volume_24h_usd_by_symbol: tuple[tuple[str, str], ...] = ()

    def as_diagnostics(self) -> dict[str, object]:
        return {
            "scope_mode": self.scope_mode,
            "trade_count_filter_minimum": self.trade_count_filter_minimum,
            "discovery_status": self.discovery_status,
            "discovery_error": self.discovery_error,
            "total_instruments_discovered": self.total_instruments_discovered,
            "instruments_passed_coarse_filter": self.instruments_passed_coarse_filter,
        }


@dataclass(slots=True, frozen=True)
class _BybitRuntimeApplyTruth:
    desired_scope_mode: str
    desired_trade_count_filter_minimum: int
    applied_scope_mode: str | None
    applied_trade_count_filter_minimum: int | None
    policy_apply_status: str
    policy_apply_reason: str | None = None


@dataclass(slots=True, frozen=True)
class _BybitOperatorRuntimeTruth:
    operator_runtime_state: str
    operator_runtime_reason: str | None = None


@dataclass(slots=True, frozen=True)
class _BybitOperatorConfidenceTruth:
    operator_confidence_state: str
    operator_confidence_reason: str | None = None


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
    _runtime_health_refresh_task: asyncio.Task[None] | None = None
    _background_connector_shutdown_tasks: set[asyncio.Task[None]] = field(default_factory=set)
    startup_result: StartupResult | None = None
    shutdown_result: ShutdownResult | None = None
    last_health: SystemHealth | None = None
    _started: bool = False

    @property
    def is_started(self) -> bool:
        """Проверить, поднят ли runtime."""
        return self._started

    def get_runtime_diagnostics(self) -> dict[str, Any]:
        """Вернуть operator-facing runtime diagnostics."""
        diagnostics = dict(self.health_checker.get_runtime_diagnostics())
        if self.bybit_market_data_connector is not None:
            diagnostics["bybit_market_data_connector"] = _project_bybit_connector_diagnostics(
                self.bybit_market_data_connector.get_operator_diagnostics(),
                self.bybit_market_data_scope_summary,
                self.bybit_market_data_apply_truth,
            )
        else:
            linear_enabled = bool(
                getattr(self.settings, "bybit_market_data_connector_enabled", False)
            )
            diagnostics.setdefault(
                "bybit_market_data_connector",
                _project_bybit_connector_diagnostics(
                    _disabled_bybit_connector_diagnostics(enabled=linear_enabled),
                    self.bybit_market_data_scope_summary if linear_enabled else None,
                    self.bybit_market_data_apply_truth,
                ),
            )
        if self.bybit_spot_market_data_connector is not None:
            diagnostics["bybit_spot_market_data_connector"] = _project_bybit_connector_diagnostics(
                self.bybit_spot_market_data_connector.get_operator_diagnostics(),
                self.bybit_spot_market_data_scope_summary,
                self.bybit_spot_market_data_apply_truth,
            )
        else:
            spot_enabled = bool(
                getattr(self.settings, "bybit_spot_market_data_connector_enabled", False)
            )
            diagnostics.setdefault(
                "bybit_spot_market_data_connector",
                _project_bybit_connector_diagnostics(
                    _disabled_bybit_spot_connector_diagnostics(enabled=spot_enabled),
                    self.bybit_spot_market_data_scope_summary if spot_enabled else None,
                    self.bybit_spot_market_data_apply_truth,
                ),
            )
        return diagnostics

    async def startup(self) -> StartupResult:
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
            result = await self.controller.startup()
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

            await self._start_opt_in_market_data_connectors()
            await self._validate_started_runtime()
            self.event_bus.seal_risk_path_policy()
            self.last_health = await self.health_checker.check_system()
            degraded_reasons = self._collect_degraded_reasons(self.last_health)

            self._started = True
            self._update_runtime_diagnostics(
                runtime_started=True,
                runtime_ready=not degraded_reasons,
                startup_state="ready" if not degraded_reasons else "degraded",
                shutdown_state="not_shutting_down",
                failure_reason=None,
                degraded_reasons=degraded_reasons,
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
        await self._start_bybit_market_data_connector()
        await self._start_bybit_spot_market_data_connector()

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
            self.bybit_market_data_connector_task = asyncio.create_task(
                self.bybit_market_data_connector.run(),
                name="production_bybit_market_data_connector",
            )

    async def _start_bybit_spot_market_data_connector(self) -> None:
        """Поднять только Bybit spot contour без вмешательства в другие connectors."""
        if (
            self.bybit_spot_market_data_connector_task is not None
            and self.bybit_spot_market_data_connector_task.done()
        ):
            self.bybit_spot_market_data_connector_task = None
        if (
            self.bybit_spot_market_data_connector is not None
            and self.bybit_spot_market_data_connector_task is None
        ):
            self.bybit_spot_market_data_connector_task = asyncio.create_task(
                self.bybit_spot_market_data_connector.run(),
                name="production_bybit_spot_market_data_connector",
            )

    async def _stop_opt_in_market_data_connectors(self) -> None:
        """Остановить canonical live-feed connector path без вмешательства в core runtime."""
        await self._stop_bybit_market_data_connector()
        await self._stop_bybit_spot_market_data_connector()

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
        """Остановить только Bybit spot contour."""
        if self.bybit_spot_market_data_connector is not None:
            with contextlib.suppress(Exception):
                await self.bybit_spot_market_data_connector.stop()
        if self.bybit_spot_market_data_connector_task is not None:
            task = self.bybit_spot_market_data_connector_task
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception, TimeoutError):
                await asyncio.wait_for(
                    asyncio.shield(task),
                    timeout=_BYBIT_CONNECTOR_JOIN_TIMEOUT_SECONDS,
                )
            if task.done():
                self.bybit_spot_market_data_connector_task = None
            else:
                self._track_background_connector_shutdown(
                    task=task,
                    attr_name="bybit_spot_market_data_connector_task",
                )

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
        candidate_connector = _build_canonical_bybit_market_data_connector(
            settings=settings,
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
        candidate_connector = _build_canonical_bybit_spot_market_data_connector(
            settings=settings,
            market_data_runtime=self.market_data_runtime,
            resolved_scope=resolved_scope,
        )
        if restart_required:
            await self._stop_bybit_spot_market_data_connector()
            self.bybit_spot_market_data_connector = candidate_connector
            self.bybit_spot_market_data_scope_summary = resolved_scope.truth
            self.bybit_spot_market_data_apply_truth = _build_bybit_runtime_apply_truth(
                settings=settings,
                contour="spot",
                resolved_scope=resolved_scope,
                connector=candidate_connector,
            )
            if self._started and self.bybit_spot_market_data_connector is not None:
                await self._start_bybit_spot_market_data_connector()
            return
        apply_status = "applied"
        apply_reason: str | None = None
        if self.bybit_spot_market_data_connector is not None:
            apply_status = (
                await self.bybit_spot_market_data_connector.update_universe_trade_count_threshold(
                    resolved_scope.truth.trade_count_filter_minimum
                )
            )
            if not isinstance(apply_status, str) or not apply_status:
                apply_status = "applied"
            if apply_status == "deferred":
                apply_reason = "transport_reconnect_pending"
        self.bybit_spot_market_data_scope_summary = resolved_scope.truth
        self.bybit_spot_market_data_apply_truth = _build_bybit_runtime_apply_truth(
            settings=settings,
            contour="spot",
            resolved_scope=resolved_scope,
            connector=self.bybit_spot_market_data_connector,
            apply_status=apply_status,
            apply_reason=apply_reason,
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
        """Narrow runtime control path for Bybit spot connector widget in terminal settings."""
        candidate_payload = get_settings().model_dump(mode="python")
        candidate_payload["bybit_spot_market_data_connector_enabled"] = enabled
        candidate_settings = Settings.model_validate(candidate_payload)
        previous_signature = self._bybit_spot_runtime_signature()
        candidate_signature = _build_bybit_runtime_signature(
            settings=candidate_settings,
            contour="spot",
        )
        if enabled:
            resolved_scope = _reuse_bybit_universe_scope_if_possible(
                settings=candidate_settings,
                contour="spot",
                existing_truth=self.bybit_spot_market_data_scope_summary,
            ) or _resolve_canonical_bybit_spot_market_data_scope(
                settings=candidate_settings,
                capture_discovery_errors=True,
            )
        else:
            resolved_scope = _resolve_disabled_bybit_toggle_scope(
                settings=candidate_settings,
                contour="spot",
                existing_truth=self.bybit_spot_market_data_scope_summary,
            )

        await self._apply_spot_bybit_runtime_plan(
            settings=candidate_settings,
            resolved_scope=resolved_scope,
            restart_required=previous_signature != candidate_signature,
        )
        updated_settings = update_settings({"bybit_spot_market_data_connector_enabled": enabled})
        self.settings = updated_settings
        await self._refresh_runtime_health_after_bybit_toggle()

        return self.get_runtime_diagnostics()

    async def update_live_feed_policy_settings(
        self,
        updates: dict[str, Any],
    ) -> Settings:
        """Синхронизировать live-feed policy settings и canonical runtime truth."""
        candidate_payload = get_settings().model_dump(mode="python")
        candidate_payload.update(updates)
        candidate_settings = Settings.model_validate(candidate_payload)

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
        ) or _resolve_canonical_bybit_spot_market_data_scope(
            settings=candidate_settings,
            capture_discovery_errors=True,
        )

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
        self.settings = updated_settings

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

    bybit_market_data_scope = _resolve_canonical_bybit_market_data_scope(settings=runtime_settings)
    bybit_market_data_connector = _build_canonical_bybit_market_data_connector(
        settings=runtime_settings,
        market_data_runtime=market_data_runtime,
        resolved_scope=bybit_market_data_scope,
    )
    bybit_spot_market_data_scope = _resolve_canonical_bybit_spot_market_data_scope(
        settings=runtime_settings
    )
    bybit_spot_market_data_connector = _build_canonical_bybit_spot_market_data_connector(
        settings=runtime_settings,
        market_data_runtime=market_data_runtime,
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


def _build_canonical_bybit_market_data_connector(
    *,
    settings: Settings,
    market_data_runtime: MarketDataRuntime,
    resolved_scope: _ResolvedBybitConnectorScope,
) -> BybitMarketDataConnector | None:
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
    )


def _build_canonical_bybit_spot_market_data_connector(
    *,
    settings: Settings,
    market_data_runtime: MarketDataRuntime,
    resolved_scope: _ResolvedBybitConnectorScope,
) -> BybitSpotMarketDataConnector | None:
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
    )


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
                min_quote_volume_24h_usd=settings.bybit_universe_min_quote_volume_24h_usd,
                min_trade_count_24h=settings.bybit_universe_min_trade_count_24h,
                max_symbols_per_scope=settings.bybit_universe_max_symbols_per_scope,
            )
        )
    except (OSError, TimeoutError, URLError) as exc:
        if enabled and not capture_discovery_errors:
            raise RuntimeError(
                f"Bybit {contour} universe discovery is unavailable: {exc}"
            ) from exc
        return _ResolvedBybitConnectorScope(
            symbols=(),
            truth=_BybitConnectorScopeTruth(
                scope_mode="universe",
                trade_count_filter_minimum=settings.bybit_universe_min_trade_count_24h,
                discovery_status="unavailable",
                discovery_error=str(exc),
                discovery_signature=discovery_signature,
            ),
        )
    return _ResolvedBybitConnectorScope(
        symbols=selection.selected_symbols,
        truth=_BybitConnectorScopeTruth(
            scope_mode=selection.scope_mode,
            trade_count_filter_minimum=settings.bybit_universe_min_trade_count_24h,
            discovery_status="ready",
            total_instruments_discovered=selection.total_instruments_discovered,
            instruments_passed_coarse_filter=selection.instruments_passed_coarse_filter,
            discovery_signature=discovery_signature,
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
            trade_count_filter_minimum=settings.bybit_universe_min_trade_count_24h,
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
    truth = replace(
        existing_truth,
        trade_count_filter_minimum=settings.bybit_universe_min_trade_count_24h,
        discovery_signature=discovery_signature,
    )
    return _ResolvedBybitConnectorScope(
        symbols=truth.selected_symbols,
        truth=truth,
    )


def _disabled_bybit_connector_diagnostics(*, enabled: bool = False) -> dict[str, object]:
    return {
        "enabled": enabled,
        "exchange": "bybit",
        "symbol": None,
        "symbols": (),
        "symbol_snapshots": (),
        "transport_status": "idle" if enabled else "disabled",
        "recovery_status": "waiting_for_scope" if enabled else "idle",
        "subscription_alive": False,
        "last_message_at": None,
        "trade_seen": False,
        "orderbook_seen": False,
        "best_bid": None,
        "best_ask": None,
        "degraded_reason": None,
        "last_disconnect_reason": None,
        "retry_count": None,
        "ready": False,
        "started": False,
        "lifecycle_state": "waiting_for_scope" if enabled else "disabled",
        "reset_required": False,
        "derived_trade_count_state": None,
        "derived_trade_count_ready": False,
        "derived_trade_count_observation_started_at": None,
        "derived_trade_count_reliable_after": None,
        "derived_trade_count_last_gap_at": None,
        "derived_trade_count_last_gap_reason": None,
        "derived_trade_count_backfill_status": None,
        "derived_trade_count_backfill_needed": None,
        "derived_trade_count_backfill_processed_archives": None,
        "derived_trade_count_backfill_total_archives": None,
        "derived_trade_count_backfill_progress_percent": None,
        "derived_trade_count_last_backfill_at": None,
        "derived_trade_count_last_backfill_source": None,
        "derived_trade_count_last_backfill_reason": None,
        "scope_mode": "universe",
        "trade_count_filter_minimum": 0,
        "discovery_status": "not_applicable",
        "discovery_error": None,
        "total_instruments_discovered": None,
        "instruments_passed_coarse_filter": None,
        "quote_volume_filter_ready": False,
        "trade_count_filter_ready": False,
        "instruments_passed_trade_count_filter": None,
        "universe_admission_state": None,
        "active_subscribed_scope_count": 0,
        "live_trade_streams_count": 0,
        "live_orderbook_count": 0,
        "degraded_or_stale_count": 0,
    }


def _disabled_bybit_spot_connector_diagnostics(*, enabled: bool = False) -> dict[str, object]:
    return {
        "enabled": enabled,
        "exchange": "bybit_spot",
        "symbol": None,
        "symbols": (),
        "symbol_snapshots": (),
        "transport_status": "idle" if enabled else "disabled",
        "recovery_status": "waiting_for_scope" if enabled else "idle",
        "subscription_alive": False,
        "last_message_at": None,
        "trade_seen": False,
        "orderbook_seen": False,
        "best_bid": None,
        "best_ask": None,
        "degraded_reason": None,
        "last_disconnect_reason": None,
        "retry_count": None,
        "ready": False,
        "started": False,
        "lifecycle_state": "waiting_for_scope" if enabled else "disabled",
        "reset_required": False,
        "derived_trade_count_state": None,
        "derived_trade_count_ready": False,
        "derived_trade_count_observation_started_at": None,
        "derived_trade_count_reliable_after": None,
        "derived_trade_count_last_gap_at": None,
        "derived_trade_count_last_gap_reason": None,
        "derived_trade_count_backfill_status": None,
        "derived_trade_count_backfill_needed": None,
        "derived_trade_count_backfill_processed_archives": None,
        "derived_trade_count_backfill_total_archives": None,
        "derived_trade_count_backfill_progress_percent": None,
        "derived_trade_count_last_backfill_at": None,
        "derived_trade_count_last_backfill_source": None,
        "derived_trade_count_last_backfill_reason": None,
        "scope_mode": "universe",
        "trade_count_filter_minimum": 0,
        "discovery_status": "not_applicable",
        "discovery_error": None,
        "total_instruments_discovered": None,
        "instruments_passed_coarse_filter": None,
        "quote_volume_filter_ready": False,
        "trade_count_filter_ready": False,
        "instruments_passed_trade_count_filter": None,
        "universe_admission_state": None,
        "active_subscribed_scope_count": 0,
        "live_trade_streams_count": 0,
        "live_orderbook_count": 0,
        "degraded_or_stale_count": 0,
    }


def _project_bybit_connector_diagnostics(  # noqa: PLR0912, PLR0915
    connector_diagnostics: dict[str, object],
    scope_truth: _BybitConnectorScopeTruth | None,
    apply_truth: _BybitRuntimeApplyTruth | None,
) -> dict[str, object]:
    merged = dict(connector_diagnostics)
    if scope_truth is not None:
        merged.update(scope_truth.as_diagnostics())
    if apply_truth is not None:
        merged["desired_scope_mode"] = apply_truth.desired_scope_mode
        merged["desired_trade_count_filter_minimum"] = (
            apply_truth.desired_trade_count_filter_minimum
        )
        merged["applied_scope_mode"] = apply_truth.applied_scope_mode
        merged["applied_trade_count_filter_minimum"] = (
            apply_truth.applied_trade_count_filter_minimum
        )
        merged["policy_apply_status"] = apply_truth.policy_apply_status
        merged["policy_apply_reason"] = apply_truth.policy_apply_reason
    raw_symbol_snapshots = merged.get("symbol_snapshots")
    symbol_snapshots = (
        raw_symbol_snapshots if isinstance(raw_symbol_snapshots, (list, tuple)) else ()
    )
    selected_quote_volume_24h_usd_by_symbol = (
        dict(scope_truth.selected_quote_volume_24h_usd_by_symbol)
        if scope_truth is not None
        else {}
    )
    if selected_quote_volume_24h_usd_by_symbol and symbol_snapshots:
        enriched_symbol_snapshots: list[dict[str, object]] = []
        for snapshot in symbol_snapshots:
            if not isinstance(snapshot, dict):
                continue
            enriched_snapshot = dict(snapshot)
            if (
                not isinstance(enriched_snapshot.get("volume_24h_usd"), str)
                or not str(enriched_snapshot.get("volume_24h_usd")).strip()
            ):
                symbol = enriched_snapshot.get("symbol")
                if isinstance(symbol, str):
                    fallback_volume = selected_quote_volume_24h_usd_by_symbol.get(symbol)
                    if fallback_volume is not None:
                        enriched_snapshot["volume_24h_usd"] = fallback_volume
            enriched_symbol_snapshots.append(enriched_snapshot)
        symbol_snapshots = tuple(enriched_symbol_snapshots)
        merged["symbol_snapshots"] = symbol_snapshots
    transport_status = str(merged.get("transport_status", "")).strip().lower()
    has_live_transport_messages = transport_status in {"connected", "degraded"} and isinstance(
        merged.get("last_message_at"), str
    )
    if has_live_transport_messages:
        live_trade_streams_count = sum(
            1
            for snapshot in symbol_snapshots
            if isinstance(snapshot, dict) and bool(snapshot.get("trade_seen", False))
        )
        live_orderbook_count = sum(
            1
            for snapshot in symbol_snapshots
            if isinstance(snapshot, dict) and bool(snapshot.get("orderbook_seen", False))
        )
    else:
        live_trade_streams_count = 0
        live_orderbook_count = 0
        merged["trade_seen"] = False
        merged["orderbook_seen"] = False
        merged["best_bid"] = None
        merged["best_ask"] = None
    active_subscribed_scope_count = len(
        [snapshot for snapshot in symbol_snapshots if isinstance(snapshot, dict)]
    )
    if active_subscribed_scope_count == 0 and isinstance(merged.get("symbols"), (list, tuple)):
        active_subscribed_scope_count = len(cast("list[str] | tuple[str, ...]", merged["symbols"]))
    merged.setdefault("scope_mode", "universe")
    merged["active_subscribed_scope_count"] = active_subscribed_scope_count
    merged["live_trade_streams_count"] = live_trade_streams_count
    merged["live_orderbook_count"] = live_orderbook_count
    merged["degraded_or_stale_count"] = max(
        0,
        active_subscribed_scope_count - min(live_trade_streams_count, live_orderbook_count),
    )
    if scope_truth is not None and scope_truth.scope_mode == "universe":
        trade_count_threshold = scope_truth.trade_count_filter_minimum
        quote_volume_filter_ready = scope_truth.discovery_status == "ready"
        empty_selected_scope = quote_volume_filter_ready and not scope_truth.selected_symbols
        trade_count_filter_required = trade_count_threshold > 0
        if empty_selected_scope:
            trade_count_filter_ready = True
        else:
            trade_count_filter_ready = (
                bool(merged.get("derived_trade_count_ready", False))
                if trade_count_filter_required
                else True
            )
        instruments_passed_trade_count_filter: int | None
        if empty_selected_scope:
            instruments_passed_trade_count_filter = 0
            if merged.get("derived_trade_count_backfill_status") is None:
                merged["derived_trade_count_backfill_status"] = "not_needed"
            if merged.get("derived_trade_count_backfill_needed") is None:
                merged["derived_trade_count_backfill_needed"] = False
        elif trade_count_filter_required and not trade_count_filter_ready:
            instruments_passed_trade_count_filter = None
        elif trade_count_filter_required:
            instruments_passed_trade_count_filter = sum(
                1
                for snapshot in symbol_snapshots
                if isinstance(snapshot, dict)
                and isinstance(snapshot.get("derived_trade_count_24h"), int)
                and int(cast("int", snapshot.get("derived_trade_count_24h")))
                >= trade_count_threshold
            )
        else:
            instruments_passed_trade_count_filter = active_subscribed_scope_count

        if not quote_volume_filter_ready:
            universe_admission_state = "waiting_for_filter_readiness"
        elif not trade_count_filter_ready and merged.get("derived_trade_count_state") == (
            "live_tail_pending_after_gap"
        ):
            universe_admission_state = "waiting_for_live_tail"
        elif not trade_count_filter_ready:
            universe_admission_state = "waiting_for_filter_readiness"
        elif instruments_passed_trade_count_filter == 0:
            universe_admission_state = "waiting_for_qualifying_instruments"
        else:
            universe_admission_state = "ready_for_selection"

        merged["quote_volume_filter_ready"] = quote_volume_filter_ready
        merged["trade_count_filter_ready"] = trade_count_filter_ready
        merged["instruments_passed_trade_count_filter"] = instruments_passed_trade_count_filter
        merged["universe_admission_state"] = universe_admission_state
        if scope_truth.discovery_status == "unavailable":
            merged["degraded_reason"] = merged.get("degraded_reason") or "discovery_unavailable"
        elif (
            bool(merged.get("enabled", False))
            and not merged.get("degraded_reason")
            and not active_subscribed_scope_count
        ):
            merged["degraded_reason"] = universe_admission_state
    else:
        merged["quote_volume_filter_ready"] = None
        merged["trade_count_filter_ready"] = None
        merged["instruments_passed_trade_count_filter"] = None
        merged["universe_admission_state"] = None
    runtime_truth = _build_bybit_operator_runtime_truth(merged)
    merged["operator_runtime_state"] = runtime_truth.operator_runtime_state
    merged["operator_runtime_reason"] = runtime_truth.operator_runtime_reason
    confidence_truth = _build_bybit_operator_confidence_truth(merged)
    merged["operator_confidence_state"] = confidence_truth.operator_confidence_state
    merged["operator_confidence_reason"] = confidence_truth.operator_confidence_reason
    return merged


def _build_bybit_operator_runtime_truth(
    diagnostics: dict[str, object],
) -> _BybitOperatorRuntimeTruth:
    state = "live"
    reason: str | None = None
    if not bool(diagnostics.get("enabled", False)):
        state = "disabled"
    else:
        policy_apply_status = diagnostics.get("policy_apply_status")
        policy_apply_reason = diagnostics.get("policy_apply_reason")
        transport_status = str(diagnostics.get("transport_status", "idle"))
        universe_admission_state = diagnostics.get("universe_admission_state")
        if policy_apply_status == "deferred":
            state = "apply_deferred"
            reason = policy_apply_reason if isinstance(policy_apply_reason, str) else None
        elif transport_status in {"connecting", "idle"}:
            state = "connecting"
        elif transport_status != "connected":
            state = "transport_unavailable"
            degraded_reason = diagnostics.get("degraded_reason")
            disconnect_reason = diagnostics.get("last_disconnect_reason")
            reason = degraded_reason if isinstance(degraded_reason, str) else None
            if reason is None and isinstance(disconnect_reason, str):
                reason = disconnect_reason
        elif universe_admission_state == "ready_for_selection":
            state = "ready"
        elif universe_admission_state == "waiting_for_live_tail":
            state = "waiting_for_live_tail"
            reason = "Historical window restored, waiting for post-gap live tail."
        elif universe_admission_state == "waiting_for_filter_readiness":
            state = "warming_up"
            reason = "Trade-count layer is still warming up."
        elif universe_admission_state == "waiting_for_qualifying_instruments":
            state = "no_qualifying_instruments"
            reason = "Filters are ready, but no instruments currently qualify."

    return _BybitOperatorRuntimeTruth(state, reason)


def _build_bybit_operator_confidence_truth(
    diagnostics: dict[str, object],
) -> _BybitOperatorConfidenceTruth:
    runtime_state = str(diagnostics.get("operator_runtime_state", "live"))
    live_trade_streams_count = int(diagnostics.get("live_trade_streams_count", 0))
    live_orderbook_count = int(diagnostics.get("live_orderbook_count", 0))
    active_scope = int(diagnostics.get("active_subscribed_scope_count", 0))
    state = "steady"
    reason: str | None = None
    if runtime_state == "disabled":
        state = "disabled"
    elif runtime_state == "apply_deferred":
        state = "deferred"
        reason = "Saved policy truth is ahead of the currently applied runtime."
    elif runtime_state == "waiting_for_live_tail":
        state = "preserved_after_gap"
        reason = "Historical window is preserved; only post-gap live tail confidence is pending."
    elif active_scope > 0 and (live_trade_streams_count == 0 or live_orderbook_count == 0):
        state = "streams_recovering"
        reason = "Transport is back, but not all live streams have resumed yet."
    elif runtime_state == "warming_up":
        state = "cold_recovery"
        reason = "Trade-count layer is rebuilding confidence from a wider recovery boundary."
    elif runtime_state == "no_qualifying_instruments":
        state = "steady_but_empty"
        reason = "Runtime is stable, but final admission currently has no qualifying instruments."
    elif runtime_state == "transport_unavailable":
        state = "transport_unavailable"
        runtime_reason = diagnostics.get("operator_runtime_reason")
        reason = runtime_reason if isinstance(runtime_reason, str) else None
    return _BybitOperatorConfidenceTruth(state, reason)


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
    return (
        contour,
        "https://api-testnet.bybit.com" if settings.bybit_testnet else "https://api.bybit.com",
        settings.bybit_universe_min_quote_volume_24h_usd,
        settings.bybit_universe_max_symbols_per_scope,
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
    return (
        *base_signature,
        settings.bybit_universe_min_trade_count_24h > 0,
        _build_bybit_discovery_signature(settings=settings, contour=contour),
    )


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

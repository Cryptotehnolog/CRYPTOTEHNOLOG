"""
Production composition root для CRYPTOTEHNOLOG.

Этот модуль является официальной точкой сборки production runtime
в рамках Шага 2 фазы P_5_1.
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from cryptotechnolog.analysis.runtime import SharedAnalysisRuntime, create_shared_analysis_runtime
from cryptotechnolog.config.logging import configure_logging, get_logger
from cryptotechnolog.config.settings import Settings, get_settings, validate_settings
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
from cryptotechnolog.intelligence.runtime import IntelligenceRuntime, create_intelligence_runtime
from cryptotechnolog.market_data import MarketDataTimeframe
from cryptotechnolog.market_data.events import BarCompletedPayload
from cryptotechnolog.market_data.runtime import MarketDataRuntime, create_market_data_runtime
from cryptotechnolog.risk.runtime import RiskRuntime, create_risk_runtime
from cryptotechnolog.runtime_identity import RuntimeIdentity, build_runtime_identity
from cryptotechnolog.signals import (
    SignalEventSource,
    SignalRuntime,
    build_signal_event,
    create_signal_runtime,
)

if TYPE_CHECKING:
    from cryptotechnolog.analysis import RiskDerivedInputsSnapshot
    from cryptotechnolog.market_data import OrderBookSnapshotContract


class ProductionBootstrapError(RuntimeError):
    """Ошибка production bootstrap path."""


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
        return self.health_checker.get_runtime_diagnostics()

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

    async def _validate_started_runtime(self) -> None:
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

    async def _ensure_component_cleanup(self) -> None:
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

    def _collect_degraded_reasons(self, health: SystemHealth) -> list[str]:
        """Собрать operator-facing причины деградации из health truth."""
        reasons = [
            f"{name}:{component.status.value}"
            for name, component in health.components.items()
            if component.status != HealthStatus.HEALTHY
        ]
        market_data_runtime = self.market_data_runtime.get_runtime_diagnostics()
        if not market_data_runtime.get("started", False):
            reasons.append("phase6_market_data:not_started")
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
        if not shared_analysis_runtime.get("started", False):
            reasons.append("c7r_shared_analysis:not_started")
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
        if not intelligence_runtime.get("started", False):
            reasons.append("phase7_intelligence:not_started")
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
        if not signal_runtime.get("started", False):
            reasons.append("phase8_signal:not_started")
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

    event_bus.on(SystemEventType.BAR_COMPLETED, handle_market_data_bar_completed_for_intelligence)
    event_bus.on(
        SystemEventType.BAR_COMPLETED,
        handle_market_data_bar_completed_for_shared_analysis,
    )
    event_bus.on(SystemEventType.BAR_COMPLETED, handle_market_data_bar_completed_for_signal)

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

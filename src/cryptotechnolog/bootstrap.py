"""
Production composition root для CRYPTOTEHNOLOG.

Этот модуль является официальной точкой сборки production runtime
в рамках Шага 2 фазы P_5_1.
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass
from typing import Any

from cryptotechnolog.config.logging import configure_logging, get_logger
from cryptotechnolog.config.settings import Settings, get_settings, validate_settings
from cryptotechnolog.core.database import DatabaseManager, set_database
from cryptotechnolog.core.enhanced_event_bus import EnhancedEventBus
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
from cryptotechnolog.risk.runtime import RiskRuntime, create_risk_runtime
from cryptotechnolog.runtime_identity import RuntimeIdentity, build_runtime_identity


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
            raise ProductionBootstrapError(
                "Production bootstrap потерял явный ListenerRegistry"
            )
        if not self.risk_runtime.is_started:
            raise ProductionBootstrapError("Phase 5 risk runtime не подключён к Event Bus")
        if self.policy.enable_event_bus_persistence and not self.event_bus.enable_persistence:
            raise ProductionBootstrapError(
                "Event Bus persistence выключилась во время startup"
            )
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
            raise ProductionBootstrapError(
                "Event Bus настроен на неверный active risk path"
            )
        if not self.event_bus.enforce_single_risk_path:
            raise ProductionBootstrapError(
                "Production Event Bus не форсирует single-risk-path policy"
            )

    async def _ensure_component_cleanup(self) -> None:
        """Дочистить компоненты, если контроллер не остановил их сам."""
        if self.risk_runtime.is_started:
            with contextlib.suppress(Exception):
                await self.risk_runtime.stop()
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
        return reasons


async def build_production_runtime(
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

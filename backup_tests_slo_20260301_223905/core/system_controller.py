"""
System Controller - Root Orchestrator для управления жизненным циклом системы.

Особенности:
- Startup/Shutdown процедуры с гарантией порядка
- Интеграция с State Machine для контроля состояний
- Health checks для всех компонентов
- Circuit Breaker для внешних зависимостей
- Graceful shutdown с cleanup
- Telemetry и метрики

Это ядро системы - если оно падает, падает вся система.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from cryptotechnolog.config import get_logger
from src.core.circuit_breaker import CircuitBreaker, CircuitState
from src.core.event import Event, SystemEventSource, SystemEventType
from src.core.health import ComponentHealth, HealthCheck, HealthChecker, HealthStatus
from src.core.state_machine import StateMachine
from src.core.state_machine_enums import SystemState, TriggerType

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from src.core.metrics import MetricsCollector

logger = get_logger(__name__)


class StartupPhase(Enum):
    """Фазы startup процедуры."""

    NOT_STARTED = "not_started"
    INITIALIZING = "initializing"
    LOADING_CONFIG = "loading_config"
    CONNECTING_DATABASE = "connecting_database"
    CONNECTING_REDIS = "connecting_redis"
    INITIALIZING_STATE_MACHINE = "initializing_state_machine"
    INITIALIZING_CIRCUIT_BREAKERS = "initializing_circuit_breakers"
    INITIALIZING_HEALTH_CHECKS = "initializing_health_checks"
    INITIALIZING_COMPONENTS = "initializing_components"
    READY = "ready"
    FAILED = "failed"


class ShutdownPhase(Enum):
    """Фазы shutdown процедуры."""

    NOT_SHUTTING_DOWN = "not_shutting_down"
    INITIATED = "initiated"
    STOPPING_COMPONENTS = "stopping_components"
    CLOSING_CONNECTIONS = "closing_connections"
    SAVING_STATE = "saving_state"
    COMPLETED = "completed"


class SystemControllerError(Exception):
    """Ошибка при работе System Controller."""

    pass


class StartupError(SystemControllerError):
    """Ошибка при startup."""

    pass


class ShutdownError(SystemControllerError):
    """Ошибка при shutdown."""

    pass


class ComponentInitError(StartupError):
    """Ошибка инициализации компонента."""

    pass


@dataclass
class ComponentInfo:
    """Информация о компоненте системы."""

    name: str
    component: Any  # Компонент (или stub)
    required: bool = True  # Обязательный ли компонент
    shutdown_timeout: float = 30.0  # Таймаут shutdown в секундах
    health_check_enabled: bool = True
    circuit_breaker_name: str | None = None  # Имя circuit breaker


@dataclass
class StartupResult:
    """Результат startup процедуры."""

    success: bool
    duration_ms: int
    phase_reached: StartupPhase
    error: str | None = None
    components_initialized: list[str] = field(default_factory=list)
    components_failed: list[str] = field(default_factory=list)


@dataclass
class ShutdownResult:
    """Результат shutdown процедуры."""

    success: bool
    duration_ms: int
    phase_reached: ShutdownPhase
    error: str | None = None
    components_stopped: list[str] = field(default_factory=list)


@dataclass
class SystemStatus:
    """Общий статус системы."""

    is_running: bool
    is_shutting_down: bool
    current_state: SystemState
    startup_phase: StartupPhase
    shutdown_phase: ShutdownPhase
    uptime_seconds: int
    components: dict[str, ComponentHealth]
    circuit_breakers: dict[str, dict[str, Any]]
    last_error: str | None = None


class SystemController:
    """
    Root Orchestrator для управления жизненным циклом системы.

    Отвечает за:
    - Startup всех компонентов в правильном порядке
    - Graceful shutdown с cleanup
    - Интеграцию с State Machine
    - Health monitoring всех компонентов
    - Circuit Breaker для внешних зависимостей

    Пример использования:
        >>> controller = SystemController()
        >>> await controller.startup()
        >>> # система работает
        >>> await controller.shutdown()

    Важно:
        - Все операции idempotent
        - Startup нельзя вызвать дважды без shutdown
        - Shutdown можно вызвать в любой момент
    """

    def __init__(
        self,
        db_manager: Any | None = None,
        redis_manager: Any | None = None,
        state_machine: StateMachine | None = None,
        health_checker: HealthChecker | None = None,
        metrics_collector: MetricsCollector | None = None,
        event_bus: Any | None = None,
        test_mode: bool = False,
    ) -> None:
        """
        Инициализировать System Controller.

        Аргументы:
            db_manager: Менеджер БД (опционально)
            redis_manager: Менеджер Redis (опционально)
            state_machine: State Machine (опционально, будет создана если не передана)
            health_checker: Health Checker (опционально)
            metrics_collector: Коллектор метрик (опционально)
            event_bus: Event Bus для shutdown notification (опционально)
            test_mode: Если True - не запускает background tasks (health monitor)
        """
        # Внешние зависимости
        self._db = db_manager
        self._redis = redis_manager
        self._health_checker = health_checker
        self._metrics = metrics_collector
        self._event_bus = event_bus
        self._test_mode = test_mode

        # State Machine - создаём или используем переданную
        self._state_machine = state_machine or StateMachine(
            db_manager=db_manager,
            metrics_collector=metrics_collector,
        )

        # Компоненты системы
        self._components: dict[str, ComponentInfo] = {}

        # Circuit Breakers для внешних зависимостей
        self._circuit_breakers: dict[str, CircuitBreaker] = {}

        # Фазы lifecycle
        self._startup_phase: StartupPhase = StartupPhase.NOT_STARTED
        self._shutdown_phase: ShutdownPhase = ShutdownPhase.NOT_SHUTTING_DOWN

        # Состояние
        self._is_running: bool = False
        self._is_shutting_down: bool = False

        # Время
        self._started_at: datetime | None = None
        self._startup_duration_ms: int = 0

        # Мониторинг
        self._last_error: str | None = None

        # Компоненты которые не удалось инициализировать
        self._failed_components: list[str] = []

        # Lock для предотвращения concurrent startup/shutdown
        self._lifecycle_lock = asyncio.Lock()

        # Background tasks
        self._health_monitor_task: asyncio.Task | None = None
        self._shutdown_event = asyncio.Event()

        logger.info("System Controller инициализирован")

    # ==================== Свойства ====================
    def state_machine(self) -> StateMachine:
        """Получить State Machine."""
        return self._state_machine

    @property
    def is_running(self) -> bool:
        """Проверить запущена ли система."""
        return self._is_running

    @property
    def is_shutting_down(self) -> bool:
        """Проверить идёт ли shutdown."""
        return self._is_shutting_down

    @property
    def current_state(self) -> SystemState:
        """Получить текущее состояние State Machine."""
        return self._state_machine.current_state

    @property
    def startup_phase(self) -> StartupPhase:
        """Получить текущую фазу startup."""
        return self._startup_phase

    @property
    def shutdown_phase(self) -> ShutdownPhase:
        """Получить текущую фазу shutdown."""
        return self._shutdown_phase

    @property
    def uptime_seconds(self) -> int:
        """Получить uptime в секундах."""
        if not self._started_at:
            return 0
        return int((datetime.now(UTC) - self._started_at).total_seconds())

    # ==================== Регистрация компонентов ====================

    def register_component(
        self,
        name: str,
        component: Any,
        required: bool = True,
        shutdown_timeout: float = 30.0,
        health_check_enabled: bool = True,
        circuit_breaker_name: str | None = None,
    ) -> None:
        """
        Зарегистрировать компонент системы.

        Аргументы:
            name: Имя компонента
            component: Экземпляр компонента
            required: Обязательный ли компонент
            shutdown_timeout: Таймаут shutdown
            health_check_enabled: Включить health checks
            circuit_breaker_name: Имя circuit breaker
        """
        if name in self._components:
            logger.warning("Компонент уже зарегистрирован, перезапись", name=name)

        self._components[name] = ComponentInfo(
            name=name,
            component=component,
            required=required,
            shutdown_timeout=shutdown_timeout,
            health_check_enabled=health_check_enabled,
            circuit_breaker_name=circuit_breaker_name,
        )

        logger.debug(
            "Зарегистрирован компонент",
            name=name,
            required=required,
            circuit_breaker=circuit_breaker_name,
        )

    def unregister_component(self, name: str) -> bool:
        """
        Удалить компонент.

        Аргументы:
            name: Имя компонента

        Возвращает:
            True если компонент был удалён
        """
        if name in self._components:
            del self._components[name]
            logger.info("Компонент удалён", name=name)
            return True
        return False

    def get_component(self, name: str) -> Any:
        """
        Получить компонент по имени.

        Аргументы:
            name: Имя компонента

        Возвращает:
            Компонент или None
        """
        info = self._components.get(name)
        return info.component if info else None

    # ==================== Circuit Breakers ====================

    def register_circuit_breaker(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        success_threshold: int = 3,
    ) -> CircuitBreaker:
        """
        Зарегистрировать circuit breaker.

        Аргументы:
            name: Имя circuit breaker
            failure_threshold: Порог ошибок для открытия
            recovery_timeout: Время ожидания перед retry
            success_threshold: Успехи для закрытия

        Возвращает:
            CircuitBreaker
        """
        if name in self._circuit_breakers:
            logger.warning("Circuit breaker уже зарегистрирован", name=name)
            return self._circuit_breakers[name]

        # Создаём circuit breaker с callback на переход в ERROR
        def on_state_change(old: CircuitState, new: CircuitState) -> None:
            logger.warning(
                "Circuit breaker изменил состояние",
                name=name,
                old_state=old.value,
                new_state=new.value,
            )
            # Можно добавить автоматический переход в ERROR

        breaker = CircuitBreaker(
            name=name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            success_threshold=success_threshold,
            on_state_change=on_state_change,
        )

        self._circuit_breakers[name] = breaker
        logger.info("Зарегистрирован circuit breaker", name=name)

        return breaker

    def get_circuit_breaker(self, name: str) -> CircuitBreaker | None:
        """
        Получить circuit breaker по имени.

        Аргументы:
            name: Имя circuit breaker

        Возвращает:
            CircuitBreaker или None
        """
        return self._circuit_breakers.get(name)

    # ==================== Startup ====================

    async def startup(self) -> StartupResult:  # noqa: PLR0915
        """
        Запустить систему.

        Выполняет startup всех компонентов в правильном порядке:
        1. Конфигурация
        2. База данных
        3. Redis
        4. State Machine
        5. Circuit Breakers
        6. Health Checks
        7. Компоненты

        Returns:
            StartupResult с результатом

        Raises:
            StartupError: Если startup неуспешен и required компонент не инициализирован
        """
        async with self._lifecycle_lock:
            if self._is_running:
                logger.warning("Система уже запущена")
                return StartupResult(
                    success=True,
                    duration_ms=0,
                    phase_reached=self._startup_phase,
                )

            start_time = datetime.now(UTC)
            components_initialized: list[str] = []
            components_failed: list[str] = []

            logger.info("=" * 60)
            logger.info("STARTUP НАЧАТ")
            logger.info("=" * 60)

            try:
                # Фаза 1: Инициализация
                self._startup_phase = StartupPhase.INITIALIZING
                logger.info("Фаза 1: Инициализация")

                # Фаза 2: Конфигурация (всегда успешна, конфиг уже загружен)
                self._startup_phase = StartupPhase.LOADING_CONFIG
                logger.info("Фаза 2: Конфигурация загружена")

                # Фаза 3: Подключение к БД
                self._startup_phase = StartupPhase.CONNECTING_DATABASE
                await self._connect_database()
                components_initialized.append("database")

                # Фаза 4: Подключение к Redis
                self._startup_phase = StartupPhase.CONNECTING_REDIS
                await self._connect_redis()
                components_initialized.append("redis")

                # Фаза 5: Инициализация State Machine
                self._startup_phase = StartupPhase.INITIALIZING_STATE_MACHINE
                await self._initialize_state_machine()
                components_initialized.append("state_machine")

                # Фаза 6: Инициализация Circuit Breakers
                self._startup_phase = StartupPhase.INITIALIZING_CIRCUIT_BREAKERS
                await self._initialize_circuit_breakers()
                components_initialized.append("circuit_breakers")

                # Фаза 7: Инициализация Health Checks
                self._startup_phase = StartupPhase.INITIALIZING_HEALTH_CHECKS
                await self._initialize_health_checks()
                components_initialized.append("health_checks")

                # Фаза 8: Инициализация компонентов
                self._startup_phase = StartupPhase.INITIALIZING_COMPONENTS
                failed = await self._initialize_components()
                components_initialized.extend(failed[0])
                components_failed.extend(failed[1])

                # Переход в состояние READY через State Machine
                logger.info("Переход в состояние READY")
                result = await self._state_machine.transition(
                    to_state=SystemState.READY,
                    trigger=TriggerType.INITIALIZATION_COMPLETE,
                    metadata={"components_initialized": len(components_initialized)},
                )

                if not result.success:
                    raise StartupError(f"Не удалось перейти в READY: {result.error}")

                # Startup завершён
                self._startup_phase = StartupPhase.READY
                self._is_running = True
                self._started_at = datetime.now(UTC)

                duration_ms = int((datetime.now(UTC) - start_time).total_seconds() * 1000)
                self._startup_duration_ms = duration_ms

                # Запускаем мониторинг health (только не в test_mode)
                if not self._test_mode:
                    self._start_health_monitor()

                logger.info("=" * 60)
                logger.info(f"STARTUP ЗАВЕРШЁН УСПЕШНО за {duration_ms}ms")
                logger.info(f"Инициализировано компонентов: {len(components_initialized)}")
                logger.info("=" * 60)

                return StartupResult(
                    success=True,
                    duration_ms=duration_ms,
                    phase_reached=StartupPhase.READY,
                    components_initialized=components_initialized,
                    components_failed=components_failed,
                )

            except Exception as e:
                duration_ms = int((datetime.now(UTC) - start_time).total_seconds() * 1000)
                error_msg = f"Startup неуспешен: {e!s}"

                logger.critical(
                    "КРИТИЧЕСКАЯ ОШИБКА STARTUP",
                    phase=self._startup_phase.value,
                    error=str(e),
                    duration_ms=duration_ms,
                )

                self._startup_phase = StartupPhase.FAILED
                self._last_error = error_msg

                # Пытаемся откатить startup
                await self._rollback_startup(components_initialized)

                # Используем сохранённый список неудачных компонентов
                all_failed = list(set(components_failed + self._failed_components))

                return StartupResult(
                    success=False,
                    duration_ms=duration_ms,
                    phase_reached=self._startup_phase,
                    error=error_msg,
                    components_initialized=components_initialized,
                    components_failed=all_failed,
                )

    async def _connect_database(self) -> None:
        """Подключиться к базе данных."""
        if not self._db:
            logger.info("DB Manager не передан, пропуск подключения к БД")
            return

        try:
            # Проверяем есть ли метод connect
            if hasattr(self._db, "connect"):
                await self._db.connect()
                logger.info("Подключение к БД установлено")
            elif hasattr(self._db, "pool"):
                # Пул уже инициализирован
                logger.info("Пул БД уже инициализирован")
            else:
                logger.info("DB Manager не требует явного подключения")
        except Exception as e:
            logger.warning("Не удалось подключиться к БД", error=str(e))
            # Не критично, продолжаем

    async def _connect_redis(self) -> None:
        """Подключиться к Redis."""
        if not self._redis:
            logger.info("Redis Manager не передан, пропуск подключения к Redis")
            return

        try:
            # Проверяем есть ли метод ping
            if hasattr(self._redis, "ping"):
                await self._redis.ping()
                logger.info("Подключение к Redis установлено")
            else:
                logger.info("Redis Manager не требует явного подключения")
        except Exception as e:
            logger.warning("Не удалось подключиться к Redis", error=str(e))
            # Не критично, продолжаем

    async def _initialize_state_machine(self) -> None:
        """Инициализировать State Machine."""
        try:
            await self._state_machine.initialize()
            logger.info("State Machine инициализирована")

            # Регистрируем callback для логирования переходов
            self._state_machine.register_on_enter(
                SystemState.ERROR,
                self._on_error_state_enter,
                name="system_controller_error_handler",
            )
        except Exception as e:
            raise StartupError(f"Не удалось инициализировать State Machine: {e!s}") from e

    async def _initialize_circuit_breakers(self) -> None:
        """Инициализировать circuit breakers для компонентов."""
        # Создаём circuit breakers для каждого компонента с указанием имени
        for _name, info in self._components.items():
            if info.circuit_breaker_name:
                self.register_circuit_breaker(
                    name=info.circuit_breaker_name,
                    failure_threshold=5,
                    recovery_timeout=60,
                    success_threshold=3,
                )

        # Всегда создаём circuit breakers для внешних зависимостей
        if self._db:
            self.register_circuit_breaker(
                name="database",
                failure_threshold=3,
                recovery_timeout=30,
                success_threshold=2,
            )

        if self._redis:
            self.register_circuit_breaker(
                name="redis",
                failure_threshold=3,
                recovery_timeout=30,
                success_threshold=2,
            )

        logger.info(
            "Circuit breakers инициализированы",
            count=len(self._circuit_breakers),
        )

    async def _initialize_health_checks(self) -> None:
        """Инициализировать health checks."""
        if not self._health_checker:
            logger.info("Health Checker не передан, пропуск")
            return

        # Регистрируем компоненты для health checks
        for name, info in self._components.items():
            if info.health_check_enabled:
                check = self._create_health_check(name, info)
                self._health_checker.register_check(check)

        logger.info("Health checks инициализированы")

    def _create_health_check(self, name: str, info: ComponentInfo) -> HealthCheck:
        """Создать health check для компонента."""

        class ComponentHealthCheck(HealthCheck):
            """Health check для компонента системы."""

            def __init__(self, component_name: str, component: Any) -> None:
                super().__init__(component_name)
                self._component = component

            async def check(self) -> ComponentHealth:
                """Выполнить проверку здоровья компонента."""
                try:
                    # Проверяем разные способы проверки здоровья
                    if hasattr(self._component, "health_check"):
                        result: ComponentHealth = await self._component.health_check()
                        return result
                    elif hasattr(self._component, "ping"):
                        await self._component.ping()
                        return ComponentHealth(
                            component=self.name,
                            status=HealthStatus.HEALTHY,
                            message="OK",
                        )
                    elif hasattr(self._component, "is_healthy"):
                        is_healthy = self._component.is_healthy()
                        return ComponentHealth(
                            component=self.name,
                            status=HealthStatus.HEALTHY if is_healthy else HealthStatus.UNHEALTHY,
                            message="OK" if is_healthy else "Unhealthy",
                        )
                    else:
                        # Компонент без явного health check - считаем здоровым
                        return ComponentHealth(
                            component=self.name,
                            status=HealthStatus.HEALTHY,
                            message="No health check defined",
                        )
                except Exception as e:
                    return ComponentHealth(
                        component=self.name,
                        status=HealthStatus.UNHEALTHY,
                        message=f"Error: {e!s}",
                    )

        return ComponentHealthCheck(name, info.component)

    async def _initialize_components(self) -> tuple[list[str], list[str]]:
        """
        Инициализировать все компоненты.

        Returns:
            (список инициализированных, список неудачных)
        """
        initialized = []
        failed = []

        for name, info in self._components.items():
            try:
                # Проверяем circuit breaker если есть
                if (
                    info.circuit_breaker_name
                    and info.circuit_breaker_name in self._circuit_breakers
                ):
                    breaker = self._circuit_breakers[info.circuit_breaker_name]
                    async with breaker:
                        await self._init_component(name, info)
                else:
                    await self._init_component(name, info)

                initialized.append(name)
                logger.info("Компонент инициализирован", name=name)

            except Exception as e:
                logger.error("Ошибка инициализации компонента", name=name, error=str(e))
                failed.append(name)
                self._failed_components.append(name)  # Сохраняем для результата

                if info.required:
                    raise ComponentInitError(
                        f"Обязательный компонент {name} не инициализирован: {e!s}"
                    ) from e

        return (initialized, failed)

    async def _init_component(self, name: str, info: ComponentInfo) -> None:
        """Инициализировать один компонент."""
        component = info.component

        # Пробуем разные методы инициализации
        if hasattr(component, "start"):
            await component.start()
        elif hasattr(component, "connect"):
            await component.connect()
        elif hasattr(component, "initialize"):
            await component.initialize()
        # Если ничего нет - компонент пассивный, не требует инициализации

    async def _rollback_startup(self, initialized_components: list[str]) -> None:
        """Откатить изменения после неудачного startup."""
        logger.warning("Откат startup", components=initialized_components)

        # Останавливаем компоненты в обратном порядке
        for name in reversed(initialized_components):
            try:
                info = self._components.get(name)
                if info:
                    await self._shutdown_component(info, timeout=5.0)
            except Exception as e:
                logger.error("Ошибка при откате компонента", name=name, error=str(e))

        self._is_running = False

    # ==================== Shutdown ====================

    async def shutdown(self, force: bool = False) -> ShutdownResult:
        """
        Остановить систему (graceful shutdown).

        Args:
            force: Принудительный shutdown без graceful cleanup

        Returns:
            ShutdownResult с результатом
        """
        async with self._lifecycle_lock:
            if not self._is_running and not self._is_shutting_down:
                logger.warning("Система не запущена")
                return ShutdownResult(
                    success=True,
                    duration_ms=0,
                    phase_reached=ShutdownPhase.COMPLETED,
                )

            if self._is_shutting_down:
                logger.warning("Shutdown уже выполняется")
                return ShutdownResult(
                    success=False,
                    duration_ms=0,
                    phase_reached=self._shutdown_phase,
                    error="Shutdown уже выполняется",
                )

            self._is_shutting_down = True
            start_time = datetime.now(UTC)
            components_stopped: list[str] = []

            logger.info("=" * 60)
            logger.info("SHUTDOWN НАЧАТ")
            logger.info("=" * 60)

            try:
                # Переходим в состояние HALT
                self._shutdown_phase = ShutdownPhase.INITIATED
                logger.info("Фаза 1: Переход в HALT")

                if not force:
                    await self._state_machine.transition(
                        to_state=SystemState.HALT,
                        trigger=TriggerType.EMERGENCY_SHUTDOWN,
                    )

                # Останавливаем мониторинг
                self._shutdown_phase = ShutdownPhase.STOPPING_COMPONENTS
                logger.info("Фаза 2: Остановка компонентов")

                stopped = await self._stop_components(force=force)
                components_stopped = stopped

                # Закрываем соединения
                self._shutdown_phase = ShutdownPhase.CLOSING_CONNECTIONS
                logger.info("Фаза 3: Закрытие соединений")

                await self._close_connections()

                # Сохраняем состояние
                if not force:
                    self._shutdown_phase = ShutdownPhase.SAVING_STATE
                    logger.info("Фаза 4: Сохранение состояния")
                    await self._save_state()

                # Завершаем
                self._shutdown_phase = ShutdownPhase.COMPLETED
                self._is_running = False

                duration_ms = int((datetime.now(UTC) - start_time).total_seconds() * 1000)

                logger.info("=" * 60)
                logger.info(f"SHUTDOWN ЗАВЕРШЁН за {duration_ms}ms")
                logger.info("=" * 60)

                return ShutdownResult(
                    success=True,
                    duration_ms=duration_ms,
                    phase_reached=ShutdownPhase.COMPLETED,
                    components_stopped=components_stopped,
                )

            except Exception as e:
                duration_ms = int((datetime.now(UTC) - start_time).total_seconds() * 1000)
                error_msg = f"Shutdown неуспешен: {e!s}"

                logger.critical(
                    "КРИТИЧЕСКАЯ ОШИБКА SHUTDOWN",
                    phase=self._shutdown_phase.value,
                    error=str(e),
                )

                self._is_running = False

                return ShutdownResult(
                    success=False,
                    duration_ms=duration_ms,
                    phase_reached=self._shutdown_phase,
                    error=error_msg,
                    components_stopped=components_stopped,
                )
            finally:
                self._is_shutting_down = False

    async def _stop_components(self, force: bool = False) -> list[str]:
        """Остановить все компоненты."""
        stopped = []

        # Останавливаем в обратном порядке регистрации
        for name in reversed(list(self._components.keys())):
            info = self._components.get(name)
            if not info:
                continue

            try:
                await self._shutdown_component(
                    info, timeout=5.0 if force else info.shutdown_timeout
                )
                stopped.append(name)
                logger.info("Компонент остановлен", name=name)
            except Exception as e:
                logger.error("Ошибка остановки компонента", name=name, error=str(e))
                if info.required and not force:
                    # Для обязательных компонентов - предупреждение, но продолжаем
                    logger.warning("Не удалось остановить обязательный компонент", name=name)

        return stopped

    async def _shutdown_component(self, info: ComponentInfo, timeout: float) -> None:
        """Остановить один компонент."""
        component = info.component

        try:
            # Пробуем разные методы shutdown
            if hasattr(component, "stop"):
                await asyncio.wait_for(component.stop(), timeout=timeout)
            elif hasattr(component, "disconnect"):
                await asyncio.wait_for(component.disconnect(), timeout=timeout)
            elif hasattr(component, "close"):
                await asyncio.wait_for(component.close(), timeout=timeout)
            # Если ничего нет - компонент пассивный
        except TimeoutError:
            logger.warning("Таймаут при остановке компонента", name=info.name)
        except Exception as e:
            logger.warning("Ошибка при остановке компонента", name=info.name, error=str(e))

    async def _close_connections(self) -> None:
        """Закрыть внешние соединения."""
        # Останавливаем health monitor
        await self._stop_health_monitor()

        # Закрываем Redis
        if self._redis and hasattr(self._redis, "close"):
            try:
                await self._redis.close()
                logger.info("Redis соединение закрыто")
            except Exception as e:
                logger.warning("Ошибка закрытия Redis", error=str(e))

        # Закрываем БД
        if self._db and hasattr(self._db, "close"):
            try:
                await self._db.close()
                logger.info("DB соединение закрыто")
            except Exception as e:
                logger.warning("Ошибка закрытия БД", error=str(e))

    async def _save_state(self) -> None:
        """Сохранить состояние системы с checkpoint."""
        # 1. Создаём checkpoint State Machine
        try:
            # Получаем Redis клиент если есть
            redis_client = None
            if self._redis and hasattr(self._redis, "_pool"):
                # Пробуем получить async клиент
                redis_client = self._redis

            await self._state_machine.checkpoint(redis_client)
            logger.info("State machine checkpoint создан")
        except Exception as e:
            logger.error("Ошибка создания checkpoint", error=str(e))

        # 2. Отправляем событие SHUTDOWN всем компонентам
        if self._event_bus:
            try:
                shutdown_event = Event.new(
                    event_type=SystemEventType.SYSTEM_SHUTDOWN,
                    source=SystemEventSource.SYSTEM_CONTROLLER,
                    payload={
                        "reason": "graceful_shutdown",
                        "timestamp": datetime.now(UTC).isoformat(),
                    },
                )
                self._event_bus.publish(shutdown_event)
                logger.info("Shutdown event опубликован")
            except Exception as e:
                logger.warning("Не удалось опубликовать shutdown event", error=str(e))

        logger.info("Состояние сохранено")

    # ==================== Health Monitor ====================

    def _start_health_monitor(self) -> None:
        """Запустить фоновый мониторинг health."""
        if self._health_monitor_task:
            return

        async def monitor() -> None:
            """Health monitor с гарантированной обработкой отмены."""
            check_interval = 5  # Проверяем каждые 5 секунд
            try:
                while self._is_running and not self._is_shutting_down:
                    # Защита #1: отмена во время sleep
                    try:
                        await asyncio.sleep(check_interval)
                    except asyncio.CancelledError:
                        break

                    # Проверка флагов после сна (могли измениться во время сна)
                    if not (self._is_running and not self._is_shutting_down):
                        break

                    # Защита #2: отмена во время health check
                    try:
                        if self._health_checker:
                            system_health = await self._health_checker.check_system()

                            # Проверяем есть ли проблемы
                            unhealthy = system_health.get_unhealthy_components()
                            if unhealthy:
                                logger.warning(
                                    "Обнаружены нездоровые компоненты",
                                    components=unhealthy,
                                )
                    except asyncio.CancelledError:
                        break
                    except Exception as e:
                        logger.error("Ошибка в health monitor", error=str(e))

            except asyncio.CancelledError:
                # Защита #3: отмена на уровне всего цикла
                pass
            finally:
                logger.debug("Health monitor task завершена")

        self._health_monitor_task = asyncio.create_task(monitor())
        logger.info("Health monitor запущен")

    async def _stop_health_monitor(self) -> None:
        """Остановить health monitor."""
        if self._health_monitor_task:
            self._health_monitor_task.cancel()
            try:
                await asyncio.wait_for(self._health_monitor_task, timeout=5.0)
            except asyncio.CancelledError:
                pass
            except TimeoutError:
                logger.warning("Health monitor не завершился за 5 секунд, принудительная остановка")
            self._health_monitor_task = None
            logger.info("Health monitor остановлен")

    # ==================== Callbacks ====================

    async def _on_error_state_enter(
        self,
        from_state: SystemState,
        to_state: SystemState,
    ) -> None:
        """Callback при входе в состояние ERROR."""
        logger.critical(
            "Система перешла в состояние ERROR",
            from_state=from_state.value,
            to_state=to_state.value,
        )
        self._last_error = "System entered ERROR state"

        # Можно добавить автоматический recovery или уведомления

    # ==================== Status ====================

    async def get_status(self) -> SystemStatus:
        """
        Получить полный статус системы.

        Returns:
            SystemStatus с текущим состоянием
        """
        # Получаем health компонентов
        components_health = {}
        if self._health_checker:
            try:
                system_health = await self._health_checker.check_system()
                components_health = system_health.components
            except Exception as e:
                logger.warning("Ошибка получения health status", error=str(e))

        # Получаем статус circuit breakers
        breakers_status = {}
        for name, breaker in self._circuit_breakers.items():
            breakers_status[name] = breaker.get_stats()

        return SystemStatus(
            is_running=self._is_running,
            is_shutting_down=self._is_shutting_down,
            current_state=self._state_machine.current_state,
            startup_phase=self._startup_phase,
            shutdown_phase=self._shutdown_phase,
            uptime_seconds=self.uptime_seconds,
            components=components_health,
            circuit_breakers=breakers_status,
            last_error=self._last_error,
        )

    # ==================== Context Manager ====================

    @asynccontextmanager
    async def lifecycle(self) -> AsyncIterator[None]:
        """
        Контекстный менеджер для автоматического startup/shutdown.

        Пример:
            >>> async with controller.lifecycle():
            ...     # система работает
            ...     pass
            # автоматический shutdown при выходе
        """
        try:
            result = await self.startup()
            if not result.success:
                raise StartupError(f"Startup failed: {result.error}")
            yield
        finally:
            await self.shutdown()

    # ====================repr ====================

    def __repr__(self) -> str:
        """Строковое представление."""
        return (
            f"SystemController("
            f"running={self._is_running}, "
            f"state={self._state_machine.current_state.value}, "
            f"components={len(self._components)})"
        )

    def __str__(self) -> str:
        """Строковое представление для пользователя."""
        state = self._state_machine.current_state.value
        return f"System: {state} | Components: {len(self._components)}"

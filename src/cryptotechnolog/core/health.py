"""
Health Check System — система проверки здоровья компонентов.

Обеспечивает:
- Проверку PostgreSQL
- Проверку Redis
- Проверку Event Bus
- Проверку системы метрик
- Агрегированный статус системы
- Уведомления при изменении статуса
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass, field
from enum import Enum
import time
from typing import TYPE_CHECKING, Any

from cryptotechnolog.config import get_logger

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

logger = get_logger(__name__)


class HealthStatus(Enum):
    """Статусы здоровья компонента."""

    HEALTHY = "healthy"  # Все работает
    UNHEALTHY = "unhealthy"  # Критическая проблема
    DEGRADED = "degraded"  # Частичная деградация
    UNKNOWN = "unknown"  # Статус неизвестен


@dataclass
class ComponentHealth:
    """Состояние здоровья компонента."""

    component: str
    status: HealthStatus
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    latency_ms: float = 0.0

    def is_healthy(self) -> bool:
        """Проверить является ли компонент здоровым."""
        return self.status == HealthStatus.HEALTHY

    def to_dict(self) -> dict[str, Any]:
        """Преобразовать в словарь."""
        return {
            "component": self.component,
            "status": self.status.value,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp,
            "latency_ms": self.latency_ms,
        }


@dataclass
class SystemHealth:
    """Общее состояние системы."""

    overall_status: HealthStatus
    components: dict[str, ComponentHealth]
    timestamp: float = field(default_factory=time.time)
    version: str = "1.4.0"

    def is_healthy(self) -> bool:
        """Проверить здорова ли вся система."""
        return self.overall_status == HealthStatus.HEALTHY

    def get_unhealthy_components(self) -> list[str]:
        """Получить список нездоровых компонентов."""
        return [
            name
            for name, health in self.components.items()
            if health.status != HealthStatus.HEALTHY
        ]

    def to_dict(self) -> dict[str, Any]:
        """Преобразовать в словарь."""
        return {
            "overall_status": self.overall_status.value,
            "components": {k: v.to_dict() for k, v in self.components.items()},
            "timestamp": self.timestamp,
            "version": self.version,
        }


class HealthCheck:
    """Базовый класс для проверки здоровья компонента."""

    def __init__(self, name: str, timeout: float = 5.0) -> None:
        """
        Инициализировать проверку.

        Аргументы:
            name: Имя компонента
            timeout: Таймаут проверки в секундах
        """
        self.name = name
        self.timeout = timeout

    async def check(self) -> ComponentHealth:
        """
        Выполнить проверку.

        Returns:
            Результат проверки здоровья
        """
        raise NotImplementedError("Метод check() должен быть переопределен")


class DatabaseHealthCheck(HealthCheck):
    """Проверка здоровья PostgreSQL."""

    def __init__(self, db_manager: Any | None = None, timeout: float = 5.0) -> None:
        """
        Инициализировать проверку БД.

        Аргументы:
            db_manager: Экземпляр DatabaseManager
            timeout: Таймаут проверки
        """
        super().__init__("postgresql", timeout)
        self._db_manager = db_manager

    def set_db_manager(self, db_manager: Any) -> None:
        """Установить менеджер БД."""
        self._db_manager = db_manager

    async def check(self) -> ComponentHealth:
        """Проверить здоровье PostgreSQL."""
        start_time = time.time()

        # Проверяем отмену перед началом
        current_task = asyncio.current_task()
        if current_task and current_task.cancelled():
            raise asyncio.CancelledError()

        if self._db_manager is None:
            return ComponentHealth(
                component=self.name,
                status=HealthStatus.UNKNOWN,
                message="DatabaseManager не настроен",
                latency_ms=(time.time() - start_time) * 1000,
            )

        try:
            health_result = await asyncio.wait_for(
                self._db_manager.health_check(),
                timeout=self.timeout,
            )

            # Проверяем отмену после await
            if current_task and current_task.cancelled():
                raise asyncio.CancelledError()

            latency_ms = (time.time() - start_time) * 1000

            if health_result.get("status") == "healthy":
                return ComponentHealth(
                    component=self.name,
                    status=HealthStatus.HEALTHY,
                    message="Подключение к PostgreSQL активно",
                    details={
                        "connected": health_result.get("connected"),
                        "pool_size": health_result.get("pool_size"),
                        "pool_max_size": health_result.get("pool_max_size"),
                    },
                    latency_ms=latency_ms,
                )
            else:
                return ComponentHealth(
                    component=self.name,
                    status=HealthStatus.UNHEALTHY,
                    message=health_result.get("error", "Неизвестная ошибка"),
                    details=health_result,
                    latency_ms=latency_ms,
                )

        except asyncio.CancelledError:
            # Пробрасываем отмену дальше
            raise
        except TimeoutError:
            latency_ms = (time.time() - start_time) * 1000
            logger.error("Таймаут проверки PostgreSQL", component=self.name)
            return ComponentHealth(
                component=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Таймаут проверки ({self.timeout}с)",
                latency_ms=latency_ms,
            )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.error("Ошибка проверки PostgreSQL", error=str(e))
            return ComponentHealth(
                component=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Ошибка: {e!s}",
                latency_ms=latency_ms,
            )


class RedisHealthCheck(HealthCheck):
    """Проверка здоровья Redis."""

    def __init__(self, redis_manager: Any | None = None, timeout: float = 5.0) -> None:
        """
        Инициализировать проверку Redis.

        Аргументы:
            redis_manager: Экземпляр RedisManager
            timeout: Таймаут проверки
        """
        super().__init__("redis", timeout)
        self._redis_manager = redis_manager

    def set_redis_manager(self, redis_manager: Any) -> None:
        """Установить менеджер Redis."""
        self._redis_manager = redis_manager

    async def check(self) -> ComponentHealth:
        """Проверить здоровье Redis."""
        start_time = time.time()

        # Проверяем отмену перед началом
        current_task = asyncio.current_task()
        if current_task and current_task.cancelled():
            raise asyncio.CancelledError()

        if self._redis_manager is None:
            return ComponentHealth(
                component=self.name,
                status=HealthStatus.UNKNOWN,
                message="RedisManager не настроен",
                latency_ms=(time.time() - start_time) * 1000,
            )

        try:
            health_result = await asyncio.wait_for(
                self._redis_manager.health_check(),
                timeout=self.timeout,
            )

            # Проверяем отмену после await
            if current_task and current_task.cancelled():
                raise asyncio.CancelledError()

            latency_ms = (time.time() - start_time) * 1000

            if health_result.get("status") == "healthy":
                return ComponentHealth(
                    component=self.name,
                    status=HealthStatus.HEALTHY,
                    message="Подключение к Redis активно",
                    details={
                        "connected": health_result.get("connected"),
                        "max_connections": health_result.get("max_connections"),
                    },
                    latency_ms=latency_ms,
                )
            else:
                return ComponentHealth(
                    component=self.name,
                    status=HealthStatus.UNHEALTHY,
                    message=health_result.get("error", "Неизвестная ошибка"),
                    details=health_result,
                    latency_ms=latency_ms,
                )

        except asyncio.CancelledError:
            raise
        except TimeoutError:
            latency_ms = (time.time() - start_time) * 1000
            logger.error("Таймаут проверки Redis", component=self.name)
            return ComponentHealth(
                component=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Таймаут проверки ({self.timeout}с)",
                latency_ms=latency_ms,
            )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.error("Ошибка проверки Redis", error=str(e))
            return ComponentHealth(
                component=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Ошибка: {e!s}",
                latency_ms=latency_ms,
            )


class EventBusHealthCheck(HealthCheck):
    """Проверка здоровья Event Bus."""

    def __init__(self, event_bus: Any | None = None, timeout: float = 5.0) -> None:
        """
        Инициализировать проверку Event Bus.

        Аргументы:
            event_bus: Экземпляр Event Bus
            timeout: Таймаут проверки
        """
        super().__init__("event_bus", timeout)
        self._event_bus = event_bus

    def set_event_bus(self, event_bus: Any) -> None:
        """Установить Event Bus."""
        self._event_bus = event_bus

    async def check(self) -> ComponentHealth:
        """Проверить здоровье Event Bus."""
        start_time = time.time()

        # Проверяем отмену перед началом
        current_task = asyncio.current_task()
        if current_task and current_task.cancelled():
            raise asyncio.CancelledError()

        if self._event_bus is None:
            return ComponentHealth(
                component=self.name,
                status=HealthStatus.UNKNOWN,
                message="EventBus не настроен",
                latency_ms=(time.time() - start_time) * 1000,
            )

        try:
            # Пробуем получить метрики Event Bus
            if hasattr(self._event_bus, "get_metrics"):
                metrics = await asyncio.wait_for(
                    self._event_bus.get_metrics(),
                    timeout=self.timeout,
                )

                # Проверяем отмену после await
                if current_task and current_task.cancelled():
                    raise asyncio.CancelledError()

                latency_ms = (time.time() - start_time) * 1000

                return ComponentHealth(
                    component=self.name,
                    status=HealthStatus.HEALTHY,
                    message="Event Bus функционирует",
                    details={"metrics": metrics},
                    latency_ms=latency_ms,
                )

            # Если метод get_metrics не существует, проверяем через publish
            if hasattr(self._event_bus, "publish"):
                # Проверяем отмену перед возвратом
                if current_task and current_task.cancelled():
                    raise asyncio.CancelledError()

                latency_ms = (time.time() - start_time) * 1000
                return ComponentHealth(
                    component=self.name,
                    status=HealthStatus.HEALTHY,
                    message="Event Bus доступен",
                    latency_ms=latency_ms,
                )

            return ComponentHealth(
                component=self.name,
                status=HealthStatus.UNKNOWN,
                message="Event Bus не имеет метода проверки",
                latency_ms=(time.time() - start_time) * 1000,
            )

        except asyncio.CancelledError:
            raise
        except TimeoutError:
            latency_ms = (time.time() - start_time) * 1000
            logger.error("Таймаут проверки Event Bus", component=self.name)
            return ComponentHealth(
                component=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Таймаут проверки ({self.timeout}с)",
                latency_ms=latency_ms,
            )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.error("Ошибка проверки Event Bus", error=str(e))
            return ComponentHealth(
                component=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Ошибка: {e!s}",
                latency_ms=latency_ms,
            )


class MetricsHealthCheck(HealthCheck):
    """Проверка здоровья системы метрик."""

    def __init__(self, metrics_collector: Any | None = None, timeout: float = 5.0) -> None:
        """
        Инициализировать проверку метрик.

        Аргументы:
            metrics_collector: Экземпляр MetricsCollector
            timeout: Таймаут проверки
        """
        super().__init__("metrics", timeout)
        self._metrics_collector = metrics_collector

    def set_metrics_collector(self, metrics_collector: Any) -> None:
        """Установить коллектор метрик."""
        self._metrics_collector = metrics_collector

    async def check(self) -> ComponentHealth:
        """Проверить здоровье системы метрик."""
        start_time = time.time()

        # Проверяем отмену перед началом
        current_task = asyncio.current_task()
        if current_task and current_task.cancelled():
            raise asyncio.CancelledError()

        if self._metrics_collector is None:
            return ComponentHealth(
                component=self.name,
                status=HealthStatus.UNKNOWN,
                message="MetricsCollector не настроен",
                latency_ms=(time.time() - start_time) * 1000,
            )

        try:
            # Проверяем что метрики включены и работают
            enabled = self._metrics_collector.enabled
            metric_names = self._metrics_collector.get_metric_names()

            # Проверяем отмену после операций
            if current_task and current_task.cancelled():
                raise asyncio.CancelledError()

            latency_ms = (time.time() - start_time) * 1000

            if enabled:
                return ComponentHealth(
                    component=self.name,
                    status=HealthStatus.HEALTHY,
                    message="Система метрик активна",
                    details={
                        "enabled": enabled,
                        "metrics_count": len(metric_names),
                    },
                    latency_ms=latency_ms,
                )
            else:
                return ComponentHealth(
                    component=self.name,
                    status=HealthStatus.DEGRADED,
                    message="Система метрик отключена",
                    details={"enabled": enabled},
                    latency_ms=latency_ms,
                )

        except asyncio.CancelledError:
            raise
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.error("Ошибка проверки метрик", error=str(e))
            return ComponentHealth(
                component=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Ошибка: {e!s}",
                latency_ms=latency_ms,
            )


class HealthChecker:
    """
    Центральный компонент для проверки здоровья всей системы.

    Обеспечивает:
    - Регистрацию проверок компонентов
    - Параллельное выполнение проверок
    - Агрегацию результатов
    - Уведомления при изменении статуса

    Пример:
        >>> checker = HealthChecker()
        >>> checker.register_check(DatabaseHealthCheck(db_manager))
        >>> checker.register_check(RedisHealthCheck(redis_manager))
        >>> system_health = await checker.check_system()
        >>> print(system_health.overall_status)
    """

    def __init__(self) -> None:
        """Инициализировать проверяльщик."""
        self._checks: dict[str, HealthCheck] = {}
        self._last_health: SystemHealth | None = None
        self._status_callbacks: list[Callable[[SystemHealth], Awaitable[None]]] = []
        self._check_interval: float = 60.0  # Интервал автоматической проверки
        self._running: bool = False
        self._monitor_task: asyncio.Task | None = None

        logger.info(
            "Инициализирован HealthChecker",
            checks_registered=0,
        )

    def register_check(self, check: HealthCheck) -> None:
        """
        Зарегистрировать проверку компонента.

        Аргументы:
            check: Экземпляр проверки здоровья
        """
        self._checks[check.name] = check
        logger.info(
            "Зарегистрирована проверка здоровья",
            component=check.name,
            total_checks=len(self._checks),
        )

    def unregister_check(self, component_name: str) -> bool:
        """
        Удалить проверку компонента.

        Аргументы:
            component_name: Имя компонента

        Returns:
            True если проверка была удалена
        """
        if component_name in self._checks:
            del self._checks[component_name]
            logger.info(
                "Удалена проверка здоровья",
                component=component_name,
                total_checks=len(self._checks),
            )
            return True
        return False

    def get_registered_checks(self) -> list[str]:
        """Получить список зарегистрированных компонентов."""
        return list(self._checks.keys())

    def on_status_change(
        self,
        callback: Callable[[SystemHealth], Awaitable[None]],
    ) -> None:
        """
        Зарегистрировать callback для уведомлений об изменении статуса.

        Аргументы:
            callback: Async функция, которая вызывается при изменении статуса
        """
        self._status_callbacks.append(callback)
        logger.debug("Зарегистрирован callback статуса", total=len(self._status_callbacks))

    async def _notify_status_change(self, health: SystemHealth) -> None:
        """Уведомить об изменении статуса."""
        # При первом запуске вызываем callbacks с начальным статусом
        if self._last_health is None:
            logger.info(
                "Первая проверка здоровья",
                status=health.overall_status.value,
            )
            # Вызываем все callbacks при первой проверке
            for callback in self._status_callbacks:
                try:
                    await callback(health)
                except Exception as e:
                    logger.error(
                        "Ошибка в callback статуса",
                        callback=callback.__name__,
                        error=str(e),
                    )
            self._last_health = health
            return

        # Проверяем изменился ли общий статус
        if self._last_health.overall_status != health.overall_status:
            logger.warning(
                "Изменился статус системы",
                old_status=self._last_health.overall_status.value,
                new_status=health.overall_status.value,
                unhealthy_components=health.get_unhealthy_components(),
            )

            # Вызываем все callbacks
            for callback in self._status_callbacks:
                try:
                    await callback(health)
                except Exception as e:
                    logger.error(
                        "Ошибка в callback статуса",
                        callback=callback.__name__,
                        error=str(e),
                    )

        self._last_health = health

    async def check_component(self, component_name: str) -> ComponentHealth:
        """
        Проверить здоровье конкретного компонента.

        Аргументы:
            component_name: Имя компонента

        Returns:
            Результат проверки

        Raises:
            ValueError: Если компонент не зарегистрирован
        """
        if component_name not in self._checks:
            raise ValueError(f"Компонент {component_name} не зарегистрирован")

        check = self._checks[component_name]
        return await check.check()

    async def check_system(self) -> SystemHealth:
        """
        Проверить здоровье всей системы.

        Returns:
            Общее состояние системы
        """
        # Проверяем отмену перед началом проверки
        current_task = asyncio.current_task()
        if current_task and current_task.cancelled():
            raise asyncio.CancelledError()

        logger.debug("Начало проверки системы", total_checks=len(self._checks))

        # Параллельно выполняем все проверки
        tasks = [check.check() for check in self._checks.values()]

        # Проверяем отмену перед gather
        if current_task and current_task.cancelled():
            raise asyncio.CancelledError()

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Проверяем отмену после gather
        if current_task and current_task.cancelled():
            raise asyncio.CancelledError()

        # Собираем результаты
        components: dict[str, ComponentHealth] = {}

        for result in results:
            if isinstance(result, Exception):
                logger.error("Ошибка при проверке компонента", error=str(result))
                continue

            if isinstance(result, ComponentHealth):
                components[result.component] = result

        # Определяем общий статус
        overall_status = self._determine_overall_status(components)

        system_health = SystemHealth(
            overall_status=overall_status,
            components=components,
            version="1.4.0",
        )

        # Уведомляем об изменении статуса
        await self._notify_status_change(system_health)

        logger.debug(
            "Проверка завершена",
            overall_status=overall_status.value,
            components_checked=len(components),
        )

        return system_health

    def _determine_overall_status(
        self,
        components: dict[str, ComponentHealth],
    ) -> HealthStatus:
        """Определить общий статус системы."""
        if not components:
            return HealthStatus.UNKNOWN

        statuses = [h.status for h in components.values()]

        # Если есть UNHEALTHY — система нездорова
        if HealthStatus.UNHEALTHY in statuses:
            return HealthStatus.UNHEALTHY

        # Если есть DEGRADED или UNKNOWN — деградировала
        if HealthStatus.DEGRADED in statuses or HealthStatus.UNKNOWN in statuses:
            return HealthStatus.DEGRADED

        # Все HEALTHY
        return HealthStatus.HEALTHY

    async def start_monitoring(self, interval: float | None = None) -> None:
        """
        Запустить автоматический мониторинг.

        Аргументы:
            interval: Интервал проверки в секундах
        """
        if self._running:
            logger.warning("Мониторинг уже запущен")
            return

        self._running = True
        self._check_interval = interval or self._check_interval

        logger.info(
            "Запуск мониторинга здоровья",
            interval=self._check_interval,
        )

        async def monitor_loop() -> None:
            while self._running:
                try:
                    await self.check_system()
                except Exception as e:
                    logger.error("Ошибка в цикле мониторинга", error=str(e))

                await asyncio.sleep(self._check_interval)

        self._monitor_task = asyncio.create_task(monitor_loop())

    async def stop_monitoring(self) -> None:
        """Остановить автоматический мониторинг."""
        if not self._running:
            return

        self._running = False

        if self._monitor_task:
            self._monitor_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._monitor_task

        logger.info("Мониторинг остановлен")

    async def check_and_wait(self, timeout: float = 30.0) -> SystemHealth:
        """
        Проверить систему и ждать готовности.

        Ждет пока все компоненты не станут здоровыми или не истечет таймаут.

        Аргументы:
            timeout: Максимальное время ожидания в секундах

        Returns:
            Состояние системы
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            health = await self.check_system()

            if health.is_healthy():
                return health

            await asyncio.sleep(1.0)

        # Вернуть последний результат
        return await self.check_system()

    def get_last_health(self) -> SystemHealth | None:
        """Получить последнее известное состояние системы."""
        return self._last_health


# Глобальный экземпляр
_health_checker: HealthChecker | None = None


def get_health_checker() -> HealthChecker:
    """
    Получить глобальный экземпляр HealthChecker.

    Returns:
        Экземпляр проверяльщика
    """
    global _health_checker  # noqa: PLW0603
    if _health_checker is None:
        _health_checker = HealthChecker()
    return _health_checker


def init_health_checker(
    db_manager: Any | None = None,
    redis_manager: Any | None = None,
    event_bus: Any | None = None,
    metrics_collector: Any | None = None,
) -> HealthChecker:
    """
    Инициализировать HealthChecker с компонентами.

    Аргументы:
        db_manager: Менеджер БД
        redis_manager: Менеджер Redis
        event_bus: Event Bus
        metrics_collector: Коллектор метрик

    Returns:
        Инициализированный экземпляр
    """
    global _health_checker  # noqa: PLW0603
    checker = HealthChecker()

    # Регистрируем проверки
    if db_manager is not None:
        checker.register_check(DatabaseHealthCheck(db_manager))

    if redis_manager is not None:
        checker.register_check(RedisHealthCheck(redis_manager))

    if event_bus is not None:
        checker.register_check(EventBusHealthCheck(event_bus))

    if metrics_collector is not None:
        checker.register_check(MetricsHealthCheck(metrics_collector))

    _health_checker = checker
    return checker

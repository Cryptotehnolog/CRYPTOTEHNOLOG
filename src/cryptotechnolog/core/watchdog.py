"""
Watchdog Implementation.

Система мониторинга здоровья компонентов с auto-recovery
для торговой платформы CRYPTOTEHNOLOG.

Особенности:
- Периодические health checks
- Auto-recovery логика
- Circuit breaker для защиты от бесконечных рестартов
- Эскалация к оператору при критических проблемах
- Интеграция с Event Bus
- Все на РУССКОМ языке
"""

from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import dataclass, field
from enum import Enum
import time
from typing import TYPE_CHECKING, Any

from cryptotechnolog.config import get_logger

# Верхнеуровневый импорт EnhancedEventBus
from .enhanced_event_bus import EnhancedEventBus

if TYPE_CHECKING:
    from collections.abc import Callable

from .circuit_breaker import CircuitBreaker, CircuitBreakerError, CircuitState
from .event import Event, SystemEventSource, SystemEventType
from .enhanced_event_bus import EnhancedEventBus
from .metrics import get_metrics_collector, get_slo_registry

logger = get_logger(__name__)


class WatchdogAlertLevel(Enum):
    """Уровни alert в Watchdog."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ComponentStatus(Enum):
    """Статус компонента."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    RECOVERING = "recovering"
    FAILED = "failed"


@dataclass
class WatchdogAlert:
    """Alert от Watchdog."""

    level: WatchdogAlertLevel
    component: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ComponentHealth:
    """Состояние здоровья компонента."""

    name: str
    status: ComponentStatus
    last_check: float
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    error_message: str | None = None
    recovery_attempts: int = 0


# ==================== Recovery Strategy ====================


class RecoveryStrategy:
    """Стратегия восстановления компонента."""

    def __init__(
        self,
        max_retries: int = 3,
        backoff_base: float = 1.0,
        backoff_multiplier: float = 2.0,
        max_backoff: float = 60.0,
    ) -> None:
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.backoff_multiplier = backoff_multiplier
        self.max_backoff = max_backoff
        self._attempt = 0

    def get_backoff_delay(self) -> float:
        """Получить задержку перед следующей попыткой."""
        delay = self.backoff_base * (self.backoff_multiplier**self._attempt)
        return min(delay, self.max_backoff)

    def increment_attempt(self) -> None:
        """Увеличить счётчик попыток."""
        self._attempt += 1

    def reset(self) -> None:
        """Сбросить счётчик попыток."""
        self._attempt = 0

    def should_retry(self) -> bool:
        """Проверить, нужно ли продолжать попытки."""
        return self._attempt < self.max_retries


# ==================== Component Checker ====================


class ComponentChecker:
    """Проверка здоровья отдельного компонента."""

    def __init__(
        self,
        name: str,
        check_func: Callable[[], Any],
        recovery_func: Callable[[], Any] | None = None,
        strategy: RecoveryStrategy | None = None,
        circuit_breaker: CircuitBreaker | None = None,
    ) -> None:
        self.name = name
        self.check_func = check_func
        self.recovery_func = recovery_func
        self.strategy = strategy or RecoveryStrategy()
        self.circuit_breaker = circuit_breaker

        self._health = ComponentHealth(
            name=name,
            status=ComponentStatus.HEALTHY,
            last_check=0.0,
        )

    @property
    def health(self) -> ComponentHealth:
        """Получить текущее состояние здоровья."""
        return self._health

    async def check(self) -> ComponentHealth:
        """
        Выполнить проверку компонента.

        Возвращает:
            ComponentHealth с результатами проверки
        """
        self._health.last_check = time.time()

        try:
            # Check circuit breaker
            if self.circuit_breaker and self.circuit_breaker.is_open:
                self._health.status = ComponentStatus.FAILED
                self._health.error_message = "Circuit breaker is OPEN"
                self._health.consecutive_failures += 1
                self._health.consecutive_successes = 0
                return self._health

            # Execute health check
            result = self.check_func()

            # Handle async results
            if asyncio.iscoroutine(result):
                result = await result

            # Check result
            if result is True or result is None:
                self._health.status = ComponentStatus.HEALTHY
                self._health.consecutive_successes += 1
                self._health.consecutive_failures = 0
                self._health.error_message = None
                self.strategy.reset()
            elif isinstance(result, dict):
                # Handle dict result with status
                status = result.get("status", "healthy")
                if status == "healthy":
                    self._health.status = ComponentStatus.HEALTHY
                    self._health.consecutive_successes += 1
                    self._health.consecutive_failures = 0
                else:
                    self._health.status = ComponentStatus.UNHEALTHY
                    self._health.consecutive_failures += 1
                    self._health.consecutive_successes = 0
                    self._health.error_message = result.get("message", "Unknown error")
            else:
                self._health.status = ComponentStatus.UNHEALTHY
                self._health.consecutive_failures += 1
                self._health.consecutive_successes = 0

        except CircuitBreakerError as e:
            self._health.status = ComponentStatus.FAILED
            self._health.error_message = str(e)
            self._health.consecutive_failures += 1

        except Exception as e:
            self._health.status = ComponentStatus.UNHEALTHY
            self._health.error_message = str(e)
            self._health.consecutive_failures += 1
            self._health.consecutive_successes = 0

            logger.warning(
                "Health check failed",
                component=self.name,
                error=str(e),
            )

        return self._health

    async def recover(self) -> bool:
        """
        Попытаться восстановить компонент.

        Возвращает:
            True если восстановление успешно
        """
        if not self.recovery_func:
            logger.info(
                "Нет функции восстановления для компонента",
                component=self.name,
            )
            return False

        if not self.strategy.should_retry():
            logger.warning(
                "Превышено максимальное количество попыток восстановления",
                component=self.name,
                max_retries=self.strategy.max_retries,
            )
            return False

        self.strategy.increment_attempt()
        self._health.recovery_attempts += 1
        self._health.status = ComponentStatus.RECOVERING

        try:
            logger.info(
                "Попытка восстановления компонента",
                component=self.name,
                attempt=self.strategy._attempt,
                max_retries=self.strategy.max_retries,
            )

            result = self.recovery_func()

            if asyncio.iscoroutine(result):
                result = await result

            if result is True:
                self._health.status = ComponentStatus.HEALTHY
                self._health.consecutive_successes = 0
                self.strategy.reset()
                logger.info(
                    "Компонент успешно восстановлен",
                    component=self.name,
                )
                return True
            else:
                delay = self.strategy.get_backoff_delay()
                logger.warning(
                    "Восстановление не удалось",
                    component=self.name,
                    attempt=self.strategy._attempt,
                    next_retry_delay=delay,
                )
                return False

        except Exception as e:
            logger.error(
                "Ошибка восстановления компонента",
                component=self.name,
                error=str(e),
            )
            return False


# ==================== Watchdog ====================


class Watchdog:
    """
    Watchdog для мониторинга и восстановления компонентов.

    Обеспечивает:
    - Периодические health checks всех зарегистрированных компонентов
    - Auto-recovery при сбоях
    - Circuit breaker для защиты от бесконечных рестартов
    - Эскалацию при критических проблемах
    - Интеграцию с Event Bus

    Аргументы:
        event_bus: Опциональный Event Bus для публикации событий
        check_interval: Интервал проверки в секундах
        failure_threshold: Количество последовательных сбоев для trigger recovery
        max_recovery_attempts: Максимальное количество попыток восстановления

    Пример:
        >>> watchdog = Watchdog(check_interval=30)
        >>> watchdog.register_component("redis", check_redis, recover_redis)
        >>> await watchdog.start()
    """

    def __init__(
        self,
        event_bus: EnhancedEventBus | None = None,
        check_interval: float = 30.0,
        failure_threshold: int = 3,
        max_recovery_attempts: int = 3,
    ) -> None:
        # Получить глобальный экземпляр Event Bus
        from . import get_event_bus
        self._event_bus = event_bus or get_event_bus()
        # asyncio уже импортирован на уровне модуля
        self._check_interval = check_interval
        self._failure_threshold = failure_threshold
        self._max_recovery_attempts = max_recovery_attempts

        self._components: dict[str, ComponentChecker] = {}
        self._running = False
        self._task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

        # Callbacks
        self._on_alert: list[Callable[[WatchdogAlert], Any]] = []
        self._on_recovery: list[Callable[[str], Any]] = []
        self._on_failure: list[Callable[[str], Any]] = []

        # Statistics
        self._total_checks = 0
        self._total_recoveries = 0
        self._total_failures = 0

        logger.info(
            "Watchdog инициализирован",
            check_interval=check_interval,
            failure_threshold=failure_threshold,
        )

    @property
    def is_running(self) -> bool:
        """Проверить, запущен ли Watchdog."""
        return self._running

    @property
    def component_count(self) -> int:
        """Получить количество зарегистрированных компонентов."""
        return len(self._components)

    def register_component(
        self,
        name: str,
        check_func: Callable[[], Any],
        recovery_func: Callable[[], Any] | None = None,
        max_retries: int = 3,
        use_circuit_breaker: bool = True,
    ) -> None:
        """
        Зарегистрировать компонент для мониторинга.

        Аргументы:
            name: Имя компонента
            check_func: Функция проверки здоровья (должна возвращать True/False или dict)
            recovery_func: Опциональная функция восстановления
            max_retries: Максимальное количество попыток восстановления
            use_circuit_breaker: Использовать ли circuit breaker
        """
        if name in self._components:
            logger.warning(
                "Компонент уже зарегистрирован, перезапись",
                component=name,
            )

        # Create circuit breaker
        circuit_breaker = None
        if use_circuit_breaker:
            circuit_breaker = CircuitBreaker(
                name=f"watchdog_{name}",
                failure_threshold=self._failure_threshold,
                recovery_timeout=60,
                success_threshold=2,
                on_state_change=self._create_circuit_callback(name),
            )

        strategy = RecoveryStrategy(max_retries=max_retries)

        checker = ComponentChecker(
            name=name,
            check_func=check_func,
            recovery_func=recovery_func,
            strategy=strategy,
            circuit_breaker=circuit_breaker,
        )

        self._components[name] = checker

        logger.info(
            "Компонент зарегистрирован в Watchdog",
            component=name,
            has_recovery=recovery_func is not None,
            use_circuit_breaker=use_circuit_breaker,
        )

    def unregister_component(self, name: str) -> None:
        """
        Удалить компонент из мониторинга.

        Аргументы:
            name: Имя компонента
        """
        if name in self._components:
            del self._components[name]
            logger.info("Компонент удалён из Watchdog", component=name)

    def _create_circuit_callback(self, component_name: str) -> Callable:
        """Создать callback для circuit breaker."""
        from . import publish_event  # noqa: PLC0415
        from .event import Priority  # noqa: PLC0415

        def callback(old_state: CircuitState, new_state: CircuitState) -> None:
            if new_state == CircuitState.OPEN:
                # Используем publish_event для безопасного fire-and-forget
                try:
                    publish_event(
                        event_type="WATCHDOG_ALERT",
                        source="WATCHDOG",
                        payload={
                            "level": "error",
                            "component": component_name,
                            "message": f"Circuit breaker OPEN для {component_name}",
                            "details": {"old_state": old_state.value, "new_state": new_state.value},
                        },
                        priority=Priority.HIGH,
                    )
                except Exception as e:
                    logger.warning("Не удалось опубликовать событие", error=str(e))
            elif new_state == CircuitState.CLOSED:
                logger.info(
                    "Circuit breaker CLOSED",
                    component=component_name,
                )

        return callback

    async def _check_component(self, checker: ComponentChecker) -> None:
        """Проверить отдельный компонент."""
        health = await checker.check()
        self._total_checks += 1

        if health.status == ComponentStatus.UNHEALTHY:
            self._total_failures += 1

            await self._publish_alert(
                WatchdogAlertLevel.WARNING,
                health.name,
                f"Компонент {health.name} нездоров: {health.error_message}",
                {
                    "status": health.status.value,
                    "consecutive_failures": health.consecutive_failures,
                    "error": health.error_message,
                },
            )

            # Try recovery
            if checker.recovery_func and health.consecutive_failures >= self._failure_threshold:
                success = await checker.recover()
                if success:
                    self._total_recoveries += 1
                    await self._publish_alert(
                        WatchdogAlertLevel.INFO,
                        health.name,
                        f"Компонент {health.name} восстановлен",
                        {"recovery_attempts": health.recovery_attempts},
                    )
                    for callback in self._on_recovery:
                        try:
                            callback(health.name)
                        except Exception as e:
                            logger.error("Ошибка в callback восстановления", error=str(e))

        elif health.status == ComponentStatus.FAILED:
            await self._publish_alert(
                WatchdogAlertLevel.CRITICAL,
                health.name,
                f"Компонент {health.name} в состоянии FAILURE: {health.error_message}",
                {
                    "status": health.status.value,
                    "error": health.error_message,
                    "recovery_attempts": health.recovery_attempts,
                },
            )
            self._total_failures += 1

            for callback in self._on_failure:
                try:
                    callback(health.name)
                except Exception as e:
                    logger.error("Ошибка в callback failure", error=str(e))

    async def _monitor_loop(self) -> None:
        """Основной цикл мониторинга."""
        logger.info("Watchdog мониторинг запущен")

        # Get metrics collector for SLO checks
        metrics_collector = None
        try:
            metrics_collector = get_metrics_collector()
        except Exception:
            logger.debug("MetricsCollector не доступен для SLO мониторинга")

        while self._running:
            try:
                async with self._lock:
                    # Check all components
                    for checker in self._components.values():
                        await self._check_component(checker)

                # SLO violations check (every 60 seconds)
                # Делаем SLO check реже чем component check
                if metrics_collector and self._total_checks % 2 == 0:
                    await self.check_slo_violations(metrics_collector)

                # Publish system health event
                await self._publish_system_health()

                # Wait for next check
                await asyncio.sleep(self._check_interval)

            except asyncio.CancelledError:
                logger.info("Watchdog мониторинг остановлен")
                break
            except Exception as e:
                logger.error("Ошибка в мониторинге", error=str(e))
                await asyncio.sleep(5)  # Brief pause before retry

        logger.info("Watchdog мониторинг завершён")

    async def _publish_system_health(self) -> None:
        """Опубликовать событие системного здоровья."""
        components_data: dict[str, dict[str, Any]] = {}

        for name, checker in self._components.items():
            health = checker.health
            components_data[name] = {
                "status": health.status.value,
                "consecutive_failures": health.consecutive_failures,
                "recovery_attempts": health.recovery_attempts,
            }

        health_data: dict[str, Any] = {
            "component_count": self.component_count,
            "total_checks": self._total_checks,
            "total_recoveries": self._total_recoveries,
            "total_failures": self._total_failures,
            "components": components_data,
        }

        event = Event.new(
            SystemEventType.HEALTH_CHECK_FAILED,  # Reusing for periodic health
            SystemEventSource.WATCHDOG,
            health_data,
        )

        await self._event_bus.publish(event)

    async def _publish_alert(
        self,
        level: WatchdogAlertLevel,
        component: str,
        message: str,
        details: dict[str, Any],
    ) -> None:
        """Опубликовать alert."""
        alert = WatchdogAlert(
            level=level,
            component=component,
            message=message,
            details=details,
        )

        # Call local callbacks
        for callback in self._on_alert:
            try:
                callback(alert)
            except Exception as e:
                logger.error("Ошибка в callback alert", error=str(e))

        # Publish to event bus
        event = Event.new(
            SystemEventType.WATCHDOG_ALERT,
            SystemEventSource.WATCHDOG,
            {
                "level": level.value,
                "component": component,
                "message": message,
                "details": details,
            },
        )

        await self._event_bus.publish(event)

    async def check_all(self) -> dict[str, ComponentHealth]:
        """
        Выполнить проверку всех компонентов.

        Возвращает:
            Словарь с результатами проверки компонентов
        """
        async with self._lock:
            results = {}
            for checker in self._components.values():
                await self._check_component(checker)
                results[checker.name] = checker.health

        return results

    async def check_component(self, name: str) -> ComponentHealth | None:
        """
        Проверить конкретный компонент.

        Аргументы:
            name: Имя компонента

        Возвращает:
            ComponentHealth или None если компонент не найден
        """
        checker = self._components.get(name)
        if not checker:
            return None

        await self._check_component(checker)
        return checker.health

    def get_component_health(self, name: str) -> ComponentHealth | None:
        """
        Получить состояние компонента без выполнения проверки.

        Аргументы:
            name: Имя компонента

        Возвращает:
            ComponentHealth или None
        """
        checker = self._components.get(name)
        return checker.health if checker else None

    def get_all_health(self) -> dict[str, ComponentHealth]:
        """
        Получить состояние всех компонентов.

        Возвращает:
            Словарь с состоянием всех компонентов
        """
        return {name: checker.health for name, checker in self._components.items()}

    def on_alert(self, callback: Callable[[WatchdogAlert], Any]) -> None:
        """Зарегистрировать callback для alerts."""
        self._on_alert.append(callback)

    def on_recovery(self, callback: Callable[[str], Any]) -> None:
        """Зарегистрировать callback для восстановлений."""
        self._on_recovery.append(callback)

    def on_failure(self, callback: Callable[[str], Any]) -> None:
        """Зарегистрировать callback для failures."""
        self._on_failure.append(callback)

    async def start(self) -> None:
        """Запустить Watchdog."""
        if self._running:
            logger.warning("Watchdog уже запущен")
            return

        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())

        logger.info("Watchdog запущен")

        # Publish startup event
        event = Event.new(
            SystemEventType.SYSTEM_BOOT,
            SystemEventSource.WATCHDOG,
            {"component_count": self.component_count},
        )
        await self._event_bus.publish(event)

    async def stop(self) -> None:
        """Остановить Watchdog."""
        if not self._running:
            return

        self._running = False

        if self._task:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task

        logger.info("Watchdog остановлен")

        # Publish shutdown event
        event = Event.new(
            SystemEventType.SYSTEM_SHUTDOWN,
            SystemEventSource.WATCHDOG,
            {
                "total_checks": self._total_checks,
                "total_recoveries": self._total_recoveries,
                "total_failures": self._total_failures,
            },
        )
        await self._event_bus.publish(event)

    def get_stats(self) -> dict[str, Any]:
        """Получить статистику Watchdog."""
        return {
            "running": self._running,
            "component_count": self.component_count,
            "total_checks": self._total_checks,
            "total_recoveries": self._total_recoveries,
            "total_failures": self._total_failures,
            "check_interval": self._check_interval,
            "failure_threshold": self._failure_threshold,
        }

    async def check_slo_violations(self, metrics_collector: Any) -> list[dict[str, Any]]:
        """
        Проверить SLO на нарушения.

        Вызывается периодически для мониторинга производительности.
        При обнаружении нарушений - публикует alert.

        Аргументы:
            metrics_collector: Экземпляр MetricsCollector

        Returns:
            Список нарушений SLO
        """
        try:
            registry = get_slo_registry()
            violations = registry.check_slo_violations(metrics_collector)

            if violations:
                logger.warning(
                    "Обнаружены нарушения SLO",
                    count=len(violations),
                    violations=[v["slo_name"] for v in violations],
                )

                # Публикуем alert для каждого нарушения
                for violation in violations:
                    await self._publish_alert(
                        WatchdogAlertLevel.WARNING,
                        "SLO",
                        f"SLO нарушен: {violation['slo_name']}",
                        {
                            "slo_name": violation["slo_name"],
                            "actual_ms": violation["actual_ms"],
                            "threshold_ms": violation["threshold_ms"],
                            "compliance_percent": violation["compliance_percent"],
                        },
                    )

            return violations

        except Exception as e:
            logger.error("Ошибка проверки SLO", error=str(e))
            return []

    def __repr__(self) -> str:
        return (
            f"Watchdog(running={self._running}, "
            f"components={self.component_count}, "
            f"checks={self._total_checks})"
        )

"""
Core components of CRYPTOTEHNOLOG trading platform.

Этот модуль содержит основные компоненты ядра торговой платформы:
- Event Bus (шина событий)
- State Machine (машина состояний)
- Watchdog (система мониторинга)
- Health Checks (проверки здоровья)
- Circuit Breaker (автоматический выключатель)
- И другие компоненты инфраструктуры
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, TypeAlias

# ==================== ИМПОРТЫ КОМПОНЕНТОВ ====================

from .circuit_breaker import CircuitBreaker
from .database import DatabaseManager
from .dual_control import DualControlManager
from .event import Event, Priority, SystemEventSource, SystemEventType
from .health import (
    HealthCheck,
    HealthChecker,
    ComponentHealth,
    HealthStatus,
    get_health_checker,
    init_health_checker,
)
from .listeners import (
    AuditListener,
    BaseListener,
    MetricsListener,
    RiskListener,
    StateMachineListener,
    get_listener_registry,
)
from .metrics import MetricsCollector, get_metrics_collector
from .operator_gate import OperatorGate
from .redis_manager import RedisManager
from .ring_buffer import RingBuffer
from .state_machine import StateMachine
from .state_machine_enums import SystemState
from .state_transition import (
    StateTransition,
    TransitionResult,
    StateHistory,
)
from .state_transition import StateTransition
from .stubs import (
    ExecutionLayerStub,
    PortfolioGovernorStub,
    RiskEngineStub,
    StrategyManagerStub,
)
from .system_controller import SystemController
from .watchdog import Watchdog

# ==================== ENHANCED EVENT BUS ИМПОРТЫ ====================

from .enhanced_event_bus import EnhancedEventBus

# TypeAlias для чистой обратной совместимости
EventBus: TypeAlias = EnhancedEventBus  # Type alias для статического анализа и runtime

# Экспорты Enhanced Event Bus для удобства пользователей
from .enhanced_event_bus import (
    BackpressureStrategy,
    RateLimitError,
    PersistenceError,
    BackpressureError,
    PublishError,
    AsyncEventReceiver,
    PriorityQueue,
    RateLimiter,
    PersistenceLayer,
)


# ==================== Enhanced Event Bus Global Instance ====================

# Верхнеуровневый импорт для избежания циклических зависимостей
# Импортируем на верхнем уровне, но создаём экземпляр лениво
from .enhanced_event_bus import EnhancedEventBus
from ..config import get_settings


class _GlobalEventBusInstance:
    """Class-based singleton для глобального Event Bus (Enhanced версия)."""

    _instance: EnhancedEventBus | None = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> EnhancedEventBus:
        """Получить глобальный экземпляр Enhanced Event Bus."""
        with cls._lock:
            if cls._instance is None:
                settings = get_settings()
                try:
                    cls._instance = EnhancedEventBus(
                        enable_persistence=True,
                        redis_url=settings.event_bus_redis_url,
                        rate_limit=settings.event_bus_rate_limit,
                        backpressure_strategy=settings.event_bus_backpressure_strategy,
                    )
                except Exception as e:
                    # Fallback к базовой конфигурации при ошибке
                    from ..config import get_logger
                    logger = get_logger(__name__)
                    logger.error(
                        "Ошибка создания EnhancedEventBus, используется fallback конфигурация",
                        error=str(e)
                    )
                    cls._instance = EnhancedEventBus(
                        enable_persistence=False,
                        redis_url=None,
                        rate_limit=10000,
                        backpressure_strategy="drop_low"
                    )
            return cls._instance
                
    @classmethod
    def set_instance(cls, bus: EnhancedEventBus) -> None:
        """Установить глобальный экземпляр Enhanced Event Bus."""
        with cls._lock:
            cls._instance = bus

    @classmethod
    def reset(cls) -> None:
        """Сбросить глобальный экземпляр (для тестов)."""
        with cls._lock:
            if cls._instance:
                cls._instance.clear()
            cls._instance = None


def get_enhanced_event_bus() -> EnhancedEventBus:
    """
    Получить глобальный экземпляр Enhanced Event Bus.

    Используется для упрощённого доступа к расширенной шине событий
    из любого места в приложении.

    Возвращает:
        Глобальный экземпляр EnhancedEventBus
    """
    return _GlobalEventBusInstance.get_instance()


def set_enhanced_event_bus(bus: EnhancedEventBus) -> None:
    """
    Установить глобальный экземпляр Enhanced Event Bus.

    Аргументы:
        bus: Экземпляр EnhancedEventBus для установки
    """
    _GlobalEventBusInstance.set_instance(bus)


def reset_enhanced_event_bus() -> None:
    """Сбросить глобальный Enhanced Event Bus (для тестов)."""
    _GlobalEventBusInstance.reset()


# ==================== Legacy Event Bus (для обратной совместимости) ====================


def get_event_bus() -> EventBus:
    """
    Получить глобальный экземпляр Event Bus (legacy).

    Используется для обратной совместимости.

    Возвращает:
        Глобальный экземпляр EventBus (на самом деле EnhancedEventBus)
    """
    return _GlobalEventBusInstance.get_instance()


def set_event_bus(bus: EventBus) -> None:
    """
    Установить глобальный экземпляр Event Bus (legacy).

    Аргументы:
        bus: Экземпляр EventBus (на самом деле EnhancedEventBus) для установки
    """
    _GlobalEventBusInstance.set_instance(bus)


def reset_event_bus() -> None:
    """Сбросить глобальный Event Bus (для тестов)."""
    _GlobalEventBusInstance.reset()


# ==================== Convenience Functions ====================


def publish_event(
    event_type: str,
    source: str,
    payload: dict[str, object],
    priority: Priority = Priority.NORMAL,
    correlation_id: str | None = None,
    timeout: float = 5.0,
) -> bool:
    """
    Опубликовать событие через глобальный Enhanced Event Bus.

    ГАРАНТИИ:
    - Синхронный вызов (не требует async контекста)
    - Timeout для предотвращения блокировки
    - Логирование ошибок
    - Возвращает True только если событие успешно поставлено в очередь

    Аргументы:
        event_type: Тип события
        source: Источник события
        payload: Данные события
        priority: Приоритет события
        correlation_id: Опциональный correlation ID
        timeout: Таймаут в секундах для асинхронной публикации

    Возвращает:
        True если событие успешно поставлено в очередь, False в случае ошибки или таймаута
    """
    import uuid
    import asyncio
    from .event import Event
    from ..config import get_logger
    
    logger = get_logger(__name__)
    
    # Создать событие
    event = Event.new(event_type, source, payload)
    event.priority = priority
    
    if correlation_id:
        event.correlation_id = uuid.UUID(correlation_id)

    # Получить глобальный Event Bus
    bus = get_enhanced_event_bus()
    
    try:
        # Попробовать найти running loop
        loop = asyncio.get_running_loop()
        
        # Создать Future для публикации
        future = loop.create_task(bus.publish(event))
        
        # Ждать с таймаутом
        try:
            loop.call_later(timeout, future.cancel)
            success = asyncio.run_coroutine_threadsafe(
                future,
                loop
            ).result(timeout=timeout)
            
            if success:
                logger.debug(
                    "Событие опубликовано успешно",
                    event_type=event_type,
                    priority=priority.value,
                    source=source,
                )
            else:
                logger.warning(
                    "Событие не опубликовано (backpressure или отсутствие подписчиков)",
                    event_type=event_type,
                    priority=priority.value,
                    source=source,
                )
            
            return success
            
        except asyncio.TimeoutError:
            logger.error(
                "Таймаут публикации события",
                event_type=event_type,
                priority=priority.value,
                timeout=timeout,
            )
            future.cancel()
            return False
        except Exception as e:
            logger.error(
                "Ошибка публикации события",
                event_type=event_type,
                priority=priority.value,
                error=str(e),
            )
            return False
            
    except RuntimeError:
        # Нет running loop - это критическая ошибка для production
        # Для CRITICAL/HIGH событий нужно как-то сохранить
        logger.critical(
            "Нет running event loop для публикации события",
            event_type=event_type,
            priority=priority.value,
            source=source,
        )
        
        # Для CRITICAL событий можно попробовать синхронную публикацию
        if priority in (Priority.CRITICAL, Priority.HIGH):
            # Пытаемся создать новый event loop
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                success = loop.run_until_complete(
                    asyncio.wait_for(bus.publish(event), timeout=timeout)
                )
                loop.close()
                
                if success:
                    logger.info(
                        "CRITICAL/HIGH событие опубликовано в emergency loop",
                        event_type=event_type,
                        priority=priority.value,
                    )
                else:
                    logger.error(
                        "Не удалось опубликовать CRITICAL/HIGH событие в emergency loop",
                        event_type=event_type,
                        priority=priority.value,
                    )
                
                return success
            except Exception as e:
                logger.critical(
                    "Критическая ошибка публикации события (нет event loop)",
                    event_type=event_type,
                    priority=priority.value,
                    error=str(e),
                )
        
        return False


async def publish_alert(
    message: str,
    severity: str = "warning",
    component: str = "SYSTEM",
    priority: Priority = Priority.HIGH,
) -> bool:
    """
    Опубликовать alert через глобальный Enhanced Event Bus.

    Аргументы:
        message: Сообщение alert
        severity: Уровень серьёзности (info, warning, error, critical)
        component: Компонент-источник
        priority: Приоритет события

    Возвращает:
        True если alert опубликован
    """
    from .event import Event, SystemEventType, SystemEventSource
    
    event = Event.new(
        SystemEventType.WATCHDOG_ALERT,
        SystemEventSource.WATCHDOG,
        {
            "message": message,
            "severity": severity,
            "component": component,
        },
    )
    event.priority = priority
    
    bus = get_enhanced_event_bus()
    return await bus.publish(event)


# ==================== Module Exports ====================


__all__ = [
    # Event system
    "Event",
    "Priority",
    "SystemEventSource",
    "SystemEventType",
    
    # Event buses
    "EnhancedEventBus",
    "get_enhanced_event_bus",
    "set_enhanced_event_bus",
    "reset_enhanced_event_bus",
    "EventBus",  # Legacy
    "get_event_bus",  # Legacy
    "set_event_bus",  # Legacy
    "reset_event_bus",  # Legacy
    
    # Convenience functions
    "publish_event",
    "publish_alert",
    
    # State machine
    "SystemState",
    "StateMachine",
    "StateTransition",
    "TransitionResult",
    "StateHistory",
    
    # Watchdog & Health
    "Watchdog",
    "HealthCheck",
    "HealthChecker",
    "get_health_checker",
    "init_health_checker",
    
    # Circuit breaker
    "CircuitBreaker",
    
    # Database
    "DatabaseManager",
    
    # Redis
    "RedisManager",
    
    # Dual control
    "DualControlManager",
    
    # Operator gate
    "OperatorGate",
    
    # Metrics
    "MetricsCollector",
    "get_metrics_collector",
    
    # Ring buffer
    "RingBuffer",
    
    # Stubs
    "ExecutionLayerStub",
    "PortfolioGovernorStub",
    "RiskEngineStub",
    "StrategyManagerStub",
    
    # System controller
    "SystemController",
    
    # Listeners
    "BaseListener",
    "StateMachineListener",
    "AuditListener",
    "MetricsListener",
    "RiskListener",
    "get_listener_registry",
]

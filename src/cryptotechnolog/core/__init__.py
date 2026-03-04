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


# ==================== Global Instance - Re-export from global_instances ====================

# Re-export из global_instances для обратной совместимости
from .global_instances import (
    get_enhanced_event_bus,
    set_enhanced_event_bus,
    reset_enhanced_event_bus,
    get_event_bus,
    set_event_bus,
    reset_event_bus,
)


# ==================== Convenience Functions ====================


# Re-export из event_publisher для обратной совместимости
from .event_publisher import publish_event, publish_alert


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

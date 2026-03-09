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

from typing import TYPE_CHECKING

# ==================== ИНТЕРФЕЙСЫ И АДАПТЕРЫ ====================
from .adapters import (
    PostgresOrderRepository,
    PostgresPositionRepository,
    PostgresRiskLimitRepository,
    StructlogAdapter,
)

# ==================== ИМПОРТЫ КОМПОНЕНТОВ ====================
from .circuit_breaker import CircuitBreaker
from .database import DatabaseManager
from .dual_control import DualControlManager

# ==================== ENHANCED EVENT BUS ИМПОРТЫ ====================
from .enhanced_event_bus import (
    AsyncEventReceiver,
    BackpressureError,
    BackpressureStrategy,
    EnhancedEventBus,
    PersistenceError,
    PersistenceLayer,
    PriorityQueue,
    PublishError,
    RateLimiter,
    RateLimitError,
)
from .event import Event, Priority, SystemEventSource, SystemEventType
from .event_publisher import publish_alert, publish_event
from .global_instances import (
    get_enhanced_event_bus,
    get_event_bus,
    reset_enhanced_event_bus,
    reset_event_bus,
    set_enhanced_event_bus,
    set_event_bus,
)
from .health import (
    ComponentHealth,
    HealthCheck,
    HealthChecker,
    HealthStatus,
    get_health_checker,
    init_health_checker,
)
from .interfaces import (
    Logger,
    OrderRepository,
    PositionRepository,
    RiskLimitRepository,
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
    StateHistory,
    StateTransition,
    TransitionResult,
)
from .stubs import (
    ExecutionLayerStub,
    PortfolioGovernorStub,
    RiskEngineStub,
    StrategyManagerStub,
)
from .system_controller import SystemController
from .watchdog import Watchdog

# ==================== Type Aliases ====================
# For backward compatibility - using type keyword (Python 3.12+)
if TYPE_CHECKING:
    type EventBus = EnhancedEventBus


# ==================== Module Exports ====================


__all__ = [
    "AuditListener",
    "BaseListener",
    "CircuitBreaker",
    "DatabaseManager",
    "DualControlManager",
    "EnhancedEventBus",
    "Event",
    "EventBus",
    "ExecutionLayerStub",
    "HealthCheck",
    "HealthChecker",
    "Logger",
    "MetricsCollector",
    "MetricsListener",
    "OperatorGate",
    "OrderRepository",
    "PlannedState",
    "PortfolioGovernorStub",
    "PositionRepository",
    "Priority",
    "RedisManager",
    "RingBuffer",
    "RiskEngineStub",
    "RiskLimitRepository",
    "RiskListener",
    "StateHistory",
    "StateMachine",
    "StateMachineListener",
    "StateTransition",
    "StrategyManagerStub",
    "StructlogAdapter",
    "SystemController",
    "SystemEventSource",
    "SystemEventType",
    "SystemState",
    "TransitionResult",
    "Watchdog",
    "get_enhanced_event_bus",
    "get_event_bus",
    "get_health_checker",
    "get_listener_registry",
    "get_metrics_collector",
    "init_health_checker",
    "publish_alert",
    "publish_event",
    "reset_enhanced_event_bus",
    "reset_event_bus",
    "set_enhanced_event_bus",
    "set_event_bus",
]

"""
Event Bus Listeners for CRYPTOTEHNOLOG.

Экспортирует все listeners и функции для регистрации.
"""

from src.core.listeners.audit import AuditListener
from src.core.listeners.base import (
    BaseListener,
    ListenerConfig,
    ListenerRegistry,
    get_listener_registry,
)
from src.core.listeners.metrics import MetricsListener
from src.core.listeners.risk import RiskListener
from src.core.listeners.state_machine import StateMachineListener

__all__ = [
    "AuditListener",
    "BaseListener",
    "ListenerConfig",
    "ListenerRegistry",
    "MetricsListener",
    "RiskListener",
    "StateMachineListener",
    "get_listener_registry",
    "register_all_listeners",
]


def register_all_listeners() -> ListenerRegistry:
    """
    Зарегистрировать все listeners в Event Bus.

    Возвращает:
        Заполненный ListenerRegistry
    """
    registry = get_listener_registry()

    # Регистрация listeners (порядок важен - приоритет)
    listeners = [
        StateMachineListener(),  # priority=100
        RiskListener(),          # priority=90
        AuditListener(),         # priority=50
        MetricsListener(),       # priority=10
    ]

    for listener in listeners:
        registry.register(listener)

    return registry

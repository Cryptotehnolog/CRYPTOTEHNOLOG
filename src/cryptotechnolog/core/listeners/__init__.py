"""
Event Bus Listeners for CRYPTOTEHNOLOG.

Экспортирует все listeners и функции для регистрации.
"""

from .audit import AuditListener
from .base import (
    BaseListener,
    ListenerConfig,
    ListenerRegistry,
    get_listener_registry,
)
from .metrics import MetricsListener
from .risk import RiskListener
from .state_machine import StateMachineListener

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
        RiskListener(),  # priority=90
        AuditListener(),  # priority=50
        MetricsListener(),  # priority=10
    ]

    for listener in listeners:
        registry.register(listener)

    return registry

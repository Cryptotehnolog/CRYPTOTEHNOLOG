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

LEGACY_RISK_PATH = "legacy_risk_listener"
PHASE5_RISK_PATH = "phase5_risk_engine"

RISK_PATH_LISTENER_NAMES: dict[str, str] = {
    "risk_check_listener": LEGACY_RISK_PATH,
    "risk_engine_listener": PHASE5_RISK_PATH,
}

__all__ = [
    "LEGACY_RISK_PATH",
    "PHASE5_RISK_PATH",
    "RISK_PATH_LISTENER_NAMES",
    "AuditListener",
    "BaseListener",
    "ListenerConfig",
    "ListenerRegistry",
    "MetricsListener",
    "RiskListener",
    "StateMachineListener",
    "build_listener_registry",
    "get_listener_registry",
    "get_risk_path_for_listener_name",
    "register_all_listeners",
]


def get_risk_path_for_listener_name(listener_name: str) -> str | None:
    """Определить risk path по имени listener."""
    return RISK_PATH_LISTENER_NAMES.get(listener_name)


def build_listener_registry(
    *,
    registry: ListenerRegistry | None = None,
    include_legacy_risk: bool = True,
) -> ListenerRegistry:
    """
    Собрать ListenerRegistry для конкретного runtime path.

    Аргументы:
        registry: Реестр для заполнения. Если не передан, используется глобальный.
        include_legacy_risk: Регистрировать ли legacy RiskListener.

    Возвращает:
        Заполненный ListenerRegistry
    """
    target_registry = registry or get_listener_registry()

    listeners: list[BaseListener] = [
        StateMachineListener(),  # priority=100
        AuditListener(),  # priority=50
        MetricsListener(),  # priority=10
    ]
    if include_legacy_risk:
        listeners.insert(1, RiskListener())  # priority=90

    for listener in listeners:
        target_registry.register(listener)

    return target_registry


def register_all_listeners() -> ListenerRegistry:
    """
    Зарегистрировать все listeners в Event Bus.

    Возвращает:
        Заполненный ListenerRegistry
    """
    return build_listener_registry(registry=get_listener_registry(), include_legacy_risk=True)

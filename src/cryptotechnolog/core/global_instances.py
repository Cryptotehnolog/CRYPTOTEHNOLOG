"""
Global instances for CRYPTOTEHNOLOG core components.

Вынесено в отдельный модуль для избежания циклических зависимостей.
Содержит compatibility-accessors для уже явно собранных runtime-компонентов,
но не должен выполнять скрытый bootstrap на import-time или при обычном getter-access.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from cryptotechnolog.config import get_logger

if TYPE_CHECKING:
    from .enhanced_event_bus import EnhancedEventBus


logger = get_logger(__name__)


class _GlobalEventBusInstance:
    """Class-based singleton for global Event Bus."""

    _instance: EnhancedEventBus | None = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> EnhancedEventBus | None:
        """Get already configured global EnhancedEventBus instance."""
        with cls._lock:
            return cls._instance

    @classmethod
    def set_instance(cls, bus: EnhancedEventBus | None) -> None:
        """Set global EnhancedEventBus instance."""
        with cls._lock:
            cls._instance = bus

    @classmethod
    def reset(cls) -> None:
        """Reset global instance (for tests)."""
        with cls._lock:
            if cls._instance:
                cls._instance.clear()
            cls._instance = None


# Convenience functions
def get_event_bus() -> EnhancedEventBus:
    """Get explicitly configured global EventBus instance."""
    bus = _GlobalEventBusInstance.get_instance()
    if bus is None:
        raise RuntimeError(
            "Global EventBus is not configured. "
            "Соберите runtime через composition root или явно вызовите set_event_bus()."
        )
    return bus


def set_event_bus(bus: EnhancedEventBus | None) -> None:
    """Set global EventBus instance."""
    _GlobalEventBusInstance.set_instance(bus)


def reset_event_bus() -> None:
    """Reset global EventBus (for tests)."""
    _GlobalEventBusInstance.reset()


# Aliases for compatibility
def get_enhanced_event_bus() -> EnhancedEventBus:
    """Get explicitly configured global EnhancedEventBus instance."""
    return get_event_bus()


def set_enhanced_event_bus(bus: EnhancedEventBus | None) -> None:
    """Set global EnhancedEventBus instance."""
    _GlobalEventBusInstance.set_instance(bus)


def reset_enhanced_event_bus() -> None:
    """Reset global EnhancedEventBus (for tests)."""
    _GlobalEventBusInstance.reset()

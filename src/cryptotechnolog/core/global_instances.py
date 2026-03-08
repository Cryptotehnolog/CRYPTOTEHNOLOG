"""
Global instances for CRYPTOTEHNOLOG core components.

Вынесено в отдельный модуль для избежания циклических зависимостей.
Содержит синглтоны для Event Bus и других глобальных компонентов.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from cryptotechnolog.config import get_logger, get_settings

if TYPE_CHECKING:
    from .enhanced_event_bus import EnhancedEventBus


logger = get_logger(__name__)


class _GlobalEventBusInstance:
    """Class-based singleton for global Event Bus."""

    _instance: EnhancedEventBus | None = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> EnhancedEventBus | None:
        """Get global EnhancedEventBus instance."""
        # Import here to avoid circular dependency
        EnhancedEventBus = __import__(
            "cryptotechnolog.core.enhanced_event_bus", fromlist=["EnhancedEventBus"]
        ).EnhancedEventBus

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
                    logger.error(
                        "Error creating EnhancedEventBus, using fallback config",
                        error=str(e),
                    )
                    cls._instance = EnhancedEventBus(
                        enable_persistence=False,
                        redis_url=None,
                        rate_limit=10000,
                        backpressure_strategy="drop_low",
                    )
            return cls._instance

    @classmethod
    def set_instance(cls, bus: EnhancedEventBus) -> None:
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
    """Get global EventBus instance."""
    bus = _GlobalEventBusInstance.get_instance()
    assert bus is not None, "EventBus instance should always be initialized"
    return bus


def set_event_bus(bus: EnhancedEventBus) -> None:
    """Set global EventBus instance."""
    _GlobalEventBusInstance.set_instance(bus)


def reset_event_bus() -> None:
    """Reset global EventBus (for tests)."""
    _GlobalEventBusInstance.reset()


# Aliases for compatibility
def get_enhanced_event_bus() -> EnhancedEventBus:
    """Get global EnhancedEventBus instance."""
    bus = _GlobalEventBusInstance.get_instance()
    assert bus is not None, "EventBus instance should always be initialized"
    return bus


def set_enhanced_event_bus(bus: EnhancedEventBus) -> None:
    """Set global EnhancedEventBus instance."""
    _GlobalEventBusInstance.set_instance(bus)


def reset_enhanced_event_bus() -> None:
    """Reset global EnhancedEventBus (for tests)."""
    _GlobalEventBusInstance.reset()

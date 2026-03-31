# ==================== CRYPTOTEHNOLOG Config Module ====================
# Configuration management for the trading platform

from .logging import (
    LogContext,
    LoggerMixin,
    bind_context,
    clear_context,
    configure_logging,
    get_context,
    get_logger,
    log_exception,
    log_performance,
)
from .manager import ConfigManager, ConfigManagerError
from .providers import InfisicalConfigProvider
from .settings import Settings, get_settings, reload_settings, update_settings, validate_settings

__all__ = [
    "ConfigManager",
    "ConfigManagerError",
    "LogContext",
    "LoggerMixin",
    "Settings",
    "bind_context",
    "clear_context",
    "configure_logging",
    "get_context",
    "get_logger",
    "get_settings",
    "log_exception",
    "log_performance",
    "reload_settings",
    "update_settings",
    "validate_settings",
]


def __getattr__(name: str) -> Settings:
    """Ленивая compatibility-точка для старого `config.settings` API."""
    if name == "settings":
        return get_settings()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

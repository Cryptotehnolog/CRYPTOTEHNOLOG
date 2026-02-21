# ==================== CRYPTOTEHNOLOG Logging Type Stubs ====================
# Type stubs for logging configuration module

from __future__ import annotations

from typing import Any

import structlog

def configure_logging() -> None:
    """Configure structlog for structured logging."""
    ...

def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a configured structlog logger."""
    ...


class LogContext:
    """Context manager for adding temporary log context."""

    def __init__(self, **context: Any) -> None:
        """Initialize the log context."""
        ...

    def __enter__(self) -> structlog.stdlib.BoundLogger:
        """Enter the context and bind the context to the logger."""
        ...

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit the context and unbind the context."""
        ...


def log_exception(
    logger: structlog.stdlib.BoundLogger,
    exc: Exception,
    **extra: Any,
) -> None:
    """Log an exception with full traceback."""
    ...

def log_performance(
    logger: structlog.stdlib.BoundLogger,
    operation: str,
    duration_ms: float,
    **extra: Any,
) -> None:
    """Log performance metrics."""
    ...

# ==================== CRYPTOTEHNOLOG Logging Configuration ====================
# Structured logging with structlog and pydantic-settings

import logging
import sys
from typing import TYPE_CHECKING, Any

import structlog

from cryptotechnolog.config.settings import get_settings

if TYPE_CHECKING:
    from collections.abc import Callable


def configure_logging() -> None:
    """
    Configure structlog for structured logging.

    This function sets up structlog with processors for:
    - Filtering by log level
    - Adding logger name and log level
    - Timestamp formatting
    - Stack info rendering
    - Exception info formatting
    - JSON or text output based on settings

    The configuration is loaded from the global settings instance.
    """
    settings = get_settings()

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level),
    )

    # Define shared processors with explicit type
    shared_processors: list[Callable[..., Any]] = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    # Add format-specific processor
    if settings.log_format == "JSON":
        shared_processors.append(structlog.processors.JSONRenderer())
    else:  # TEXT
        shared_processors.append(
            structlog.dev.ConsoleRenderer(
                colors=settings.environment != "production",
                exception_formatter=structlog.dev.plain_traceback,
            )
        )

    # Configure structlog
    structlog.configure(
        processors=shared_processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
        wrapper_class=structlog.stdlib.BoundLogger,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """
    Get a configured structlog logger.

    Args:
        name: Logger name. If None, uses the calling module's name.

    Returns:
        structlog.stdlib.BoundLogger: Configured logger instance.
    """
    if name is None:
        # Get the calling module's name
        name = "cryptotechnolog"
    # Cast to BoundLogger to satisfy mypy (structlog.get_logger() returns Any)
    return structlog.get_logger(name)  # type: ignore[no-any-return]


class LogContext:
    """
    Context manager for adding temporary log context.

    This is useful for adding context to a block of code, such as
    request IDs, user IDs, or other contextual information.

    Example:
        with LogContext(request_id="12345"):
            log.info("Processing request")
    """

    def __init__(self, **context: Any) -> None:
        """
        Initialize the log context.

        Args:
            **context: Key-value pairs to add to the log context.
        """
        self.context = context
        self.bound_logger: structlog.stdlib.BoundLogger | None = None
        self.logger = get_logger()

    def __enter__(self) -> structlog.stdlib.BoundLogger:
        """
        Enter the context and bind the context to the logger.

        Returns:
            structlog.stdlib.BoundLogger: Logger with bound context.
        """
        self.bound_logger = self.logger.bind(**self.context)
        return self.bound_logger

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """
        Exit the context and unbind the context.

        Args:
            exc_type: Exception type if an exception was raised.
            exc_val: Exception value if an exception was raised.
            exc_tb: Exception traceback if an exception was raised.
        """
        if self.bound_logger is not None:
            self.bound_logger = None


# ==================== Convenience Functions ====================
def log_exception(logger: structlog.stdlib.BoundLogger, exc: Exception, **extra: Any) -> None:
    """
    Log an exception with full traceback.

    Args:
        logger: Logger instance.
        exc: Exception to log.
        **extra: Additional context to log.
    """
    logger.exception(
        "Exception occurred",
        exc_type=type(exc).__name__,
        exc_message=str(exc),
        **extra,
    )


def log_performance(
    logger: structlog.stdlib.BoundLogger,
    operation: str,
    duration_ms: float,
    **extra: Any,
) -> None:
    """
    Log performance metrics.

    Args:
        logger: Logger instance.
        operation: Operation name.
        duration_ms: Duration in milliseconds.
        **extra: Additional context to log.
    """
    logger.info(
        "Performance metric",
        operation=operation,
        duration_ms=duration_ms,
        **extra,
    )


# ==================== Main ====================
if __name__ == "__main__":
    # Configure logging
    configure_logging()

    # Get logger
    log = get_logger("test")

    # Test logging
    log.info("Test info message", key="value")
    log.warning("Test warning message")
    log.error("Test error message", error_code=500)

    # Test log context
    with LogContext(request_id="test-123", user_id="user-456"):
        log.info("Message with context")

    # Test exception logging
    try:
        raise ValueError("Test exception")
    except Exception as e:
        log_exception(log, e)

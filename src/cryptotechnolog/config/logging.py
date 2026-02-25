# ==================== CRYPTOTEHNOLOG Logging Configuration ====================
# Structured logging with structlog and pydantic-settings

from contextvars import ContextVar
from datetime import datetime
import logging
import logging.handlers
from pathlib import Path
import sys
from typing import TYPE_CHECKING, Any

import structlog

from cryptotechnolog.config.settings import get_settings

if TYPE_CHECKING:
    from collections.abc import Callable


# Контекст для трейсинга (доступен во всех логах)
_context: ContextVar[dict[str, Any] | None] = ContextVar("log_context", default=None)


def _init_context() -> dict[str, Any]:
    """Инициализация пустого контекста."""
    return {}


class FileLoggingManager:
    """Менеджер для управления файловыми обработчиками логирования."""

    def __init__(self) -> None:
        self._logs_dir: Path | None = None
        self._handlers: dict[str, logging.handlers.TimedRotatingFileHandler] = {}

    def get_logs_dir(self, settings: Any) -> Path:
        """Получить директорию для логов."""
        if self._logs_dir is None:
            self._logs_dir = settings.logs_dir
            self._logs_dir.mkdir(parents=True, exist_ok=True)
        assert self._logs_dir is not None
        return self._logs_dir

    def setup(self, settings: Any) -> None:
        """Настроить файловые обработчики."""
        logs_dir = self.get_logs_dir(settings)
        today = datetime.now().strftime("%Y-%m-%d")

        # Основной файл - ротация по времени (каждый день, 30 дней)
        app_handler = logging.handlers.TimedRotatingFileHandler(
            filename=logs_dir / f"app-{today}.log",
            when="midnight",
            interval=1,
            backupCount=30,
            encoding="utf-8",
        )
        app_handler.suffix = "%Y-%m-%d"
        self._handlers["app"] = app_handler

        # Файл для ошибок - только ERROR и выше
        error_handler = logging.handlers.TimedRotatingFileHandler(
            filename=logs_dir / f"error-{today}.log",
            when="midnight",
            interval=1,
            backupCount=30,
            encoding="utf-8",
        )
        error_handler.suffix = "%Y-%m-%d"
        self._handlers["error"] = error_handler

    @property
    def handlers(self) -> dict[str, logging.handlers.TimedRotatingFileHandler]:
        """Получить обработчики."""
        return self._handlers


# Глобальный экземпляр менеджера файлового логирования
_file_logging_manager = FileLoggingManager()


def _write_to_file_processor(
    logger: logging.Logger, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Процессор для записи логов в файл."""
    handlers = _file_logging_manager.handlers
    if not handlers:
        return event_dict

    try:
        # Форматируем сообщение
        message = event_dict.get("event", "")
        level = method_name.upper()
        logger_name = event_dict.get("logger", "unknown")

        # Формируем строку
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"{timestamp} | {level:8} | {logger_name} | {message}\n"

        # Записываем в основной файл
        if "app" in handlers:
            handler = handlers["app"]
            handler.acquire()
            try:
                handler.emit(
                    logging.LogRecord(
                        name=logger_name,
                        level=getattr(logging, level, logging.INFO),
                        pathname="",
                        lineno=0,
                        msg=log_line,
                        args=(),
                        exc_info=None,
                    )
                )
            finally:
                handler.release()

        # Записываем в файл ошибок (объединённый if)
        if level in ("ERROR", "CRITICAL") and "error" in handlers:
            func_name = event_dict.get("func", "unknown")
            lineno = event_dict.get("lineno", 0)
            error_line = (
                f"{timestamp} | {level:8} | {logger_name} | " f"{func_name}:{lineno} | {message}\n"
            )
            handler = handlers["error"]
            handler.acquire()
            try:
                handler.emit(
                    logging.LogRecord(
                        name=logger_name,
                        level=getattr(logging, level, logging.ERROR),
                        pathname="",
                        lineno=0,
                        msg=error_line,
                        args=(),
                        exc_info=None,
                    )
                )
            finally:
                handler.release()
    except Exception:
        # Игнорируем ошибки записи в файл
        pass

    return event_dict


def configure_logging() -> None:
    """
    Настроить structlog для структурированного логирования.

    Настраивает:
    - Вывод в консоль (stdout)
    - Запись в файл (каждый день, 30 дней)
    - Отдельный файл для ошибок
    - Фильтрация по уровню
    - JSON или TEXT формат (настраивается в .env)

    Конфигурация загружается из глобальных настроек.
    """
    settings = get_settings()

    # Настраиваем файловые обработчики
    _file_logging_manager.setup(settings)

    # Configure console logging (stdout) через стандартный logging
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level))
    root_logger.handlers.clear()
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    root_logger.addHandler(console_handler)

    # Define shared processors with explicit type
    shared_processors: list[Callable[..., Any]] = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    # Add format-specific processor
    # Добавляем процессор для записи в файл ДО ConsoleRenderer
    shared_processors.append(_write_to_file_processor)

    # ConsoleRenderer для вывода в консоль
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
        wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG),
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


# ==================== Context Variables Functions ====================


def bind_context(**context: Any) -> None:
    """
    Привязать контекстные данные ко всем последующим логам в текущем контексте.

    Аргументы:
        **context: Пары ключ-значение для контекста

    Пример:
        >>> bind_context(request_id="req-123", strategy_id="strategy-1")
        >>> logger.info("Ордер отправлен")  # автоматически включает request_id
    """
    current = _context.get()
    if current is None:
        current = _init_context()
    current.update(context)
    _context.set(current)


def clear_context() -> None:
    """Очистить контекстные данные."""
    _context.set({})


def get_context() -> dict[str, Any]:
    """
    Получить текущий контекст.

    Возвращает:
        Словарь с текущим контекстом
    """
    current = _context.get()
    if current is None:
        current = _init_context()
    return current


class LoggerMixin:
    """
    Миксин для классов, которым нужен логгер.

    Пример:
        >>> class MyClass(LoggerMixin):
        ...     def do_something(self):
        ...         self.logger.info("Выполняю действие", value=42)
    """

    @property
    def logger(self) -> structlog.stdlib.BoundLogger:
        """Получить логгер для текущего класса.

        Returns:
            Логгер с именем класса
        """
        if not hasattr(self, "_logger"):
            self._logger = get_logger(self.__class__.__name__)
        return self._logger


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

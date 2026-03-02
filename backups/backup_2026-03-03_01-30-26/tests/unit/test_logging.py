# ==================== Tests: Logging Configuration ====================

import logging

from cryptotechnolog.config import (
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


class TestConfigureLogging:
    """Test logging configuration."""

    def test_configure_logging(self) -> None:
        """Test that logging can be configured."""
        configure_logging()

        # Check that log level is set
        logger = logging.getLogger()
        assert logger.level > 0  # Should be set, NOTSET (0) means not configured

    def test_get_logger_returns_logger(self) -> None:
        """Test that get_logger returns a valid logger."""
        configure_logging()
        logger = get_logger("test")

        # Should be a structlog BoundLogger
        assert logger is not None
        assert hasattr(logger, "info")
        assert hasattr(logger, "warning")
        assert hasattr(logger, "error")

    def test_get_logger_default_name(self) -> None:
        """Test that get_logger uses default name when None is provided."""
        configure_logging()
        logger = get_logger(None)

        assert logger is not None

    def test_get_logger_custom_name(self) -> None:
        """Test that get_logger uses custom name."""
        configure_logging()
        logger = get_logger("custom_logger")

        assert logger is not None


class TestLogContext:
    """Test log context manager."""

    def test_log_context_binds_values(self) -> None:
        """Test that LogContext binds values to logger."""
        configure_logging()

        with LogContext(request_id="test-123", user_id="user-456") as logger:
            assert logger is not None
            # Context should be bound to logger

    def test_log_context_cleanup(self) -> None:
        """Test that LogContext cleans up after exit."""
        configure_logging()

        with LogContext(request_id="test-123"):
            pass  # Context manager should work

        # After context exit, should not raise
        assert True


class TestLogConvenienceFunctions:
    """Test convenience logging functions."""

    def test_log_exception(self) -> None:
        """Test log_exception function."""
        configure_logging()
        logger = get_logger("test")

        try:
            raise ValueError("Test exception")
        except Exception as e:
            # Should not raise
            log_exception(logger, e, context="test")

        assert True

    def test_log_performance(self) -> None:
        """Test log_performance function."""
        configure_logging()
        logger = get_logger("test")

        # Should not raise
        log_performance(logger, "test_operation", 123.45)

        assert True


class TestBindContext:
    """Тесты для bind_context и clear_context."""

    def setup_method(self):
        """Очистка контекста перед каждым тестом."""
        clear_context()

    def teardown_method(self):
        """Очистка контекста после каждого теста."""
        clear_context()

    def test_bind_context_single_value(self):
        """Добавление одного значения в контекст."""
        bind_context(request_id="req-123")
        ctx = get_context()
        assert ctx.get("request_id") == "req-123"

    def test_bind_context_multiple_values(self):
        """Добавление нескольких значений в контекст."""
        bind_context(request_id="req-123", strategy_id="strat-1", order_id="ord-456")
        ctx = get_context()
        assert ctx.get("request_id") == "req-123"
        assert ctx.get("strategy_id") == "strat-1"
        assert ctx.get("order_id") == "ord-456"

    def test_bind_context_preserves_previous(self):
        """Сохранение предыдущих значений контекста."""
        bind_context(first_key="first_value")
        bind_context(second_key="second_value")
        ctx = get_context()
        assert ctx.get("first_key") == "first_value"
        assert ctx.get("second_key") == "second_value"

    def test_clear_context_removes_all(self):
        """Очистка всего контекста."""
        bind_context(key1="value1", key2="value2")
        clear_context()
        ctx = get_context()
        assert len(ctx) == 0

    def test_context_available_in_logger(self):
        """Контекст доступен в логах."""
        bind_context(strategy_id="strategy-1", order_id="order-123")
        logger = get_logger("ContextTest")

        # Должно работать без исключений
        logger.info("Ордер создан", symbol="BTCUSDT")


class TestLoggerMixin:
    """Тесты для LoggerMixin."""

    def test_logger_mixin_provides_logger(self):
        """Миксин предоставляет доступ к логгеру."""

        class TestClass(LoggerMixin):
            pass

        obj = TestClass()
        assert hasattr(obj, "logger")
        assert obj.logger is not None

    def test_logger_mixin_uses_class_name(self):
        """Логгер использует имя класса."""

        class MyCustomClass(LoggerMixin):
            pass

        obj = MyCustomClass()
        # Имя логгера должно содержать имя класса
        assert "MyCustomClass" in str(obj.logger)

    def test_logger_mixin_cached(self):
        """Логгер кешируется для экземпляра."""

        class TestClass(LoggerMixin):
            pass

        obj = TestClass()
        logger1 = obj.logger
        logger2 = obj.logger
        assert logger1 is logger2


class TestGetContext:
    """Тесты для get_context()."""

    def setup_method(self):
        clear_context()

    def teardown_method(self):
        clear_context()

    def test_get_context_empty_initially(self):
        """Контекст пустой при старте."""
        ctx = get_context()
        assert isinstance(ctx, dict)

    def test_get_context_after_bind(self):
        """Контекст содержит данные после bind_context."""
        bind_context(test_key="test_value")
        ctx = get_context()
        assert ctx["test_key"] == "test_value"

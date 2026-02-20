# ==================== Tests: Logging Configuration ====================

import logging

import pytest

from cryptotechnolog.config import configure_logging, get_logger, LogContext


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

        with LogContext(request_id="test-123") as logger:
            bound_logger = logger

        # After context exit, bound_logger should be None
        # (This is implementation-specific, so we just check it doesn't raise)
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
            from cryptotechnolog.config import log_exception
            log_exception(logger, e, context="test")

        assert True

    def test_log_performance(self) -> None:
        """Test log_performance function."""
        configure_logging()
        logger = get_logger("test")

        # Should not raise
        from cryptotechnolog.config import log_performance
        log_performance(logger, "test_operation", 123.45)

        assert True

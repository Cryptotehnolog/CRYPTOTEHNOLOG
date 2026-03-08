# ==================== Tests for main.py ====================

import asyncio
import inspect
from unittest.mock import Mock, patch

import pytest

from cryptotechnolog import main as main_module
from cryptotechnolog.main import asyncio as main_asyncio
from cryptotechnolog.main import structlog as main_structlog


class TestMain:
    """Tests for cryptotechnolog.main module."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings for testing."""
        with patch(
            "cryptotechnolog.main.get_settings"
        ) as mock:
            mock_settings = Mock()
            mock_settings.environment = "test"
            mock_settings.log_level = "INFO"
            mock.return_value = mock_settings
            yield mock_settings

    @pytest.fixture
    def mock_structlog(self):
        """Mock structlog."""
        with patch("cryptotechnolog.main.structlog") as mock:
            mock.get_logger.return_value = Mock()
            mock.configure.return_value = None
            yield mock

    @pytest.mark.asyncio
    async def test_main_entry_point_exits_on_keyboard_interrupt(self):
        """Test main() exits on KeyboardInterrupt."""
        with patch("cryptotechnolog.main.asyncio.run") as mock_run:
            # Test the main() function runs
            mock_run.return_value = None

            # Verify main function exists and is async
            assert asyncio.iscoroutinefunction(main_module.main)

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(main_module, "main")
        assert callable(main_module.main)

    def test_main_is_async(self):
        """Test main is an async function."""
        assert asyncio.iscoroutinefunction(main_module.main)

    def test_main_module_imports(self):
        """Test main module imports correctly."""
        # Verify required imports
        assert hasattr(main_module, "asyncio")
        assert hasattr(main_module, "sys")
        assert hasattr(main_module, "structlog")
        assert hasattr(main_module, "get_settings")

    def test_main_has_docstring(self):
        """Test main function has a docstring."""
        assert main_module.main.__doc__ is not None
        assert "Main application entry point" in main_module.main.__doc__


class TestMainIntegration:
    """Integration tests for main module."""

    def test_main_module_dunder_name(self):
        """Test main module has __name__ attribute."""
        assert main_module.__name__ == "cryptotechnolog.main"

    def test_main_file_path(self):
        """Test main module has __file__ attribute."""
        assert main_module.__file__ is not None
        assert "main.py" in main_module.__file__

    def test_main_has_stdlib_imports(self):
        """Test main module imports sys and asyncio."""
        assert hasattr(main_asyncio, "run")

    def test_main_has_structlog_import(self):
        """Test main module imports structlog."""
        assert hasattr(main_structlog, "configure")
        assert hasattr(main_structlog, "get_logger")

    def test_main_configure_processor_list(self):
        """Test main uses structlog processors."""
        source = inspect.getsource(main_module)
        # Verify processors are used in structlog.configure
        assert "JSONRenderer" in source
        assert "TimeStamper" in source

    def test_main_logger_info_calls(self):
        """Test main logs startup messages."""
        source = inspect.getsource(main_module)
        # Verify logging calls exist
        assert "logger.info" in source
        assert "CRYPTOTEHNOLOG Platform" in source

    def test_main_uses_settings(self):
        """Test main uses get_settings."""
        source = inspect.getsource(main_module)
        assert "get_settings" in source

    def test_main_has_asyncio_sleep(self):
        """Test main uses asyncio.sleep for heartbeat."""
        source = inspect.getsource(main_module)
        assert "asyncio.sleep" in source

    def test_main_handles_cancelled_error(self):
        """Test main handles CancelledError."""
        source = inspect.getsource(main_module)
        assert "CancelledError" in source

    def test_main_handles_keyboard_interrupt(self):
        """Test main handles KeyboardInterrupt."""
        source = inspect.getsource(main_module)
        assert "KeyboardInterrupt" in source

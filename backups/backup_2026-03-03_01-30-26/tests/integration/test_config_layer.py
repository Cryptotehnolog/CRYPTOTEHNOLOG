# ==================== CRYPTOTEHNOLOG Config Layer Integration Tests ====================
# Integration tests for configuration layer
#
# These tests verify that:
# 1. Settings are loaded correctly
# 2. Logging configuration works
# 3. Environment variables are handled properly

import os

import pytest

from cryptotechnolog.config.logging import configure_logging
from cryptotechnolog.config.settings import Settings


class TestSettingsIntegration:
    """Test suite for settings integration."""

    def test_default_settings(self):
        """Test that default settings are loaded correctly."""
        settings = Settings()

        # Check default values (may be overridden by ENVIRONMENT env var)
        assert settings.environment in ["development", "test", "production"]
        assert settings.debug is True
        assert settings.log_level == "INFO"

    def test_environment_override(self):
        """Test that environment variables override defaults."""
        # Set environment variable
        os.environ["ENVIRONMENT"] = "production"
        os.environ["DEBUG"] = "false"

        settings = Settings()

        # Check overrides
        assert settings.environment == "production"
        assert settings.debug is False

        # Clean up
        del os.environ["ENVIRONMENT"]
        del os.environ["DEBUG"]

    def test_database_settings(self):
        """Test database settings."""
        settings = Settings()

        # Check database configuration
        assert hasattr(settings, "postgres_host")
        assert hasattr(settings, "postgres_port")
        assert hasattr(settings, "postgres_db")
        assert hasattr(settings, "postgres_user")

    def test_redis_settings(self):
        """Test Redis settings."""
        settings = Settings()

        # Check Redis configuration
        assert hasattr(settings, "redis_host")
        assert hasattr(settings, "redis_port")
        assert hasattr(settings, "redis_db")

    def test_api_settings(self):
        """Test Dashboard settings (web UI)."""
        settings = Settings()

        # Check Dashboard configuration
        assert hasattr(settings, "dashboard_host")
        assert hasattr(settings, "dashboard_port")
        assert settings.dashboard_enabled is True


class TestLoggingIntegration:
    """Test suite for logging integration."""

    def test_configure_logging(self):
        """Test that logging can be configured."""
        # This should not raise an exception
        configure_logging()

    def test_logging_with_environment(self):
        """Test logging with different environments."""
        os.environ["ENVIRONMENT"] = "production"

        # Configure logging for production
        configure_logging()

        # Clean up
        del os.environ["ENVIRONMENT"]


class TestConfigIntegration:
    """Test suite for configuration integration."""

    def test_settings_and_logging_integration(self):
        """Test that settings and logging work together."""
        # Create settings
        settings = Settings()

        # Configure logging based on settings
        configure_logging()

        # Verify settings are accessible
        assert settings.environment in ["development", "production", "test"]

    def test_config_validation(self):
        """Test that configuration is validated."""
        settings = Settings()

        # Settings should validate required fields
        assert settings.postgres_host is not None
        assert settings.postgres_port is not None
        assert settings.redis_host is not None
        assert settings.redis_port is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

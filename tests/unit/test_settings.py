# ==================== CRYPTOTEHNOLOG Settings Tests ====================
# Unit tests for configuration settings

import os
from pathlib import Path

import pytest

from src.config.settings import Settings, get_settings, reload_settings, validate_settings


class TestSettings:
    """Test cases for Settings class."""

    def test_settings_load_default_values(self):
        """Test that settings load with correct default values."""
        settings = Settings()

        # Check project settings
        assert settings.project_name == "CRYPTOTEHNOLOG"
        assert settings.project_version == "1.0.0"
        assert settings.environment == "development"
        assert settings.debug is True

        # Check database settings
        assert settings.postgres_host == "localhost"
        assert settings.postgres_port == 5432
        assert settings.postgres_user == "bot_user"
        assert settings.postgres_db == "trading_dev"

        # Check risk parameters
        assert settings.base_r_percent == 0.01
        assert settings.max_r_per_trade == 1.0
        assert settings.max_portfolio_r == 5.0

    def test_settings_load_from_environment(self):
        """Test that settings can be loaded from environment variables."""
        # Set environment variables
        os.environ["PROJECT_NAME"] = "TEST_CRYPTO"
        os.environ["ENVIRONMENT"] = "production"
        os.environ["DEBUG"] = "false"
        os.environ["BASE_R_PERCENT"] = "0.02"

        try:
            # Reload settings
            settings = reload_settings()

            # Check that environment variables are loaded
            assert settings.project_name == "TEST_CRYPTO"
            assert settings.environment == "production"
            assert settings.debug is False
            assert settings.base_r_percent == 0.02
        finally:
            # Clean up environment variables
            os.environ.pop("PROJECT_NAME", None)
            os.environ.pop("ENVIRONMENT", None)
            os.environ.pop("DEBUG", None)
            os.environ.pop("BASE_R_PERCENT", None)

    def test_settings_postgres_url_construction(self):
        """Test that PostgreSQL URL is constructed correctly."""
        settings = Settings()

        expected_url = (
            f"postgresql://{settings.postgres_user}:{settings.postgres_password}"
            f"@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
        )

        assert settings.postgres_url == expected_url

    def test_settings_postgres_async_url_construction(self):
        """Test that async PostgreSQL URL is constructed correctly."""
        settings = Settings()

        expected_url = (
            f"postgresql+asyncpg://{settings.postgres_user}:{settings.postgres_password}"
            f"@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
        )

        assert settings.postgres_async_url == expected_url

    def test_settings_redis_url_construction(self):
        """Test that Redis URL is constructed correctly."""
        settings = Settings()

        expected_url = f"redis://{settings.redis_host}:{settings.redis_port}/{settings.redis_db}"

        assert settings.redis_url == expected_url

    def test_settings_redis_url_with_password(self):
        """Test that Redis URL includes password when set."""
        # Set environment variable
        os.environ["REDIS_PASSWORD"] = "test_password"

        try:
            settings = Settings()
            expected_url = (
                f"redis://:{settings.redis_password}@"
                f"{settings.redis_host}:{settings.redis_port}/{settings.redis_db}"
            )

            assert settings.redis_url == expected_url
        finally:
            # Clean up
            os.environ.pop("REDIS_PASSWORD", None)

    def test_settings_log_level_validation(self):
        """Test that log level is validated correctly."""
        # Valid log levels
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            os.environ["LOG_LEVEL"] = level
            settings = Settings()
            assert settings.log_level == level

        # Invalid log level should raise error
        with pytest.raises(ValueError):
            os.environ["LOG_LEVEL"] = "INVALID"
            Settings()

        # Clean up
        os.environ.pop("LOG_LEVEL", None)

    def test_settings_log_format_validation(self):
        """Test that log format is validated correctly."""
        # Valid formats
        for fmt in ["JSON", "TEXT"]:
            os.environ["LOG_FORMAT"] = fmt
            settings = Settings()
            assert settings.log_format == fmt

        # Invalid format should raise error
        with pytest.raises(ValueError):
            os.environ["LOG_FORMAT"] = "INVALID"
            Settings()

        # Clean up
        os.environ.pop("LOG_FORMAT", None)

    def test_settings_event_bus_type_validation(self):
        """Test that event bus type is validated correctly."""
        # Valid types
        for bus_type in ["REDIS", "ZEROMQ"]:
            os.environ["EVENT_BUS_TYPE"] = bus_type
            settings = Settings()
            assert settings.event_bus_type == bus_type

        # Invalid type should raise error
        with pytest.raises(ValueError):
            os.environ["EVENT_BUS_TYPE"] = "INVALID"
            Settings()

        # Clean up
        os.environ.pop("EVENT_BUS_TYPE", None)


class TestSettingsValidation:
    """Test cases for settings validation."""

    def test_validate_settings_success(self, test_settings, tmp_path):
        """Test that valid settings pass validation."""
        # Override paths to use temp directory
        test_settings.data_dir = tmp_path / "data"
        test_settings.logs_dir = tmp_path / "logs"
        test_settings.config_dir = tmp_path / "config"

        # Validate should succeed
        assert validate_settings() is True

    def test_validate_settings_invalid_base_r_percent(self, test_settings, tmp_path):
        """Test that invalid base_r_percent fails validation."""
        test_settings.base_r_percent = -0.01

        result = validate_settings()
        assert result is False

    def test_validate_settings_invalid_max_r_per_trade(self, test_settings, tmp_path):
        """Test that invalid max_r_per_trade fails validation."""
        test_settings.max_r_per_trade = -1.0

        result = validate_settings()
        assert result is False

    def test_validate_settings_invalid_leverage(self, test_settings, tmp_path):
        """Test that invalid leverage fails validation."""
        test_settings.default_leverage = 0.5

        result = validate_settings()
        assert result is False


class TestSettingsFactory:
    """Test cases for settings factory functions."""

    def test_get_settings_returns_global_instance(self):
        """Test that get_settings returns the global settings instance."""
        settings1 = get_settings()
        settings2 = get_settings()

        # Should be the same instance
        assert settings1 is settings2

    def test_reload_settings_creates_new_instance(self):
        """Test that reload_settings creates a new settings instance."""
        settings1 = get_settings()

        # Reload settings
        settings2 = reload_settings()

        # Should be a new instance (not the same object)
        assert settings1 is not settings2

    def test_reload_settings_preserves_environment(self):
        """Test that reload_settings preserves environment variables."""
        # Set environment variable
        os.environ["PROJECT_NAME"] = "RELOAD_TEST"

        try:
            settings1 = get_settings()
            assert settings1.project_name == "RELOAD_TEST"

            # Reload should preserve the environment variable
            settings2 = reload_settings()
            assert settings2.project_name == "RELOAD_TEST"
        finally:
            # Clean up
            os.environ.pop("PROJECT_NAME", None)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

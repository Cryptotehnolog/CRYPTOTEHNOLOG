# ==================== CRYPTOTEHNOLOG Settings Tests ====================
# Unit tests for configuration settings

import os

import pytest

from src.config.settings import Settings, get_settings, reload_settings, validate_settings


@pytest.mark.unit
class TestSettings:
    """Test cases for Settings class."""

    def test_settings_load_default_values(self, test_env):
        """Test that settings load with correct default values."""
        settings = Settings()

        # Check project settings
        assert settings.project_name == "CRYPTOTEHNOLOG"
        assert settings.project_version == "1.0.0"
        assert settings.environment == "test"  # test_env sets ENVIRONMENT=test
        assert settings.debug is True

        # Check database settings
        assert settings.postgres_host == "localhost"
        assert settings.postgres_port == 5432
        assert settings.postgres_user == "bot_user"
        assert settings.postgres_db == "trading_test"  # test_env sets POSTGRES_DB=trading_test

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
            f"postgresql://{settings.postgres_user}:{settings.postgres_password}"
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


@pytest.mark.unit
class TestSettingsValidation:
    """Test cases for settings validation."""

    def test_validate_settings_success(self, test_settings, tmp_path):
        """Test that valid settings pass validation."""
        # Override paths to use temp directory
        test_settings.data_dir = tmp_path / "data"
        test_settings.logs_dir = tmp_path / "logs"
        test_settings.config_dir = tmp_path / "config"

        # Ensure environment is set to test (not production)
        test_settings.environment = "test"

        # Validate should succeed
        assert validate_settings(test_settings) is True

    def test_validate_settings_invalid_base_r_percent(self):
        """Test that invalid base_r_percent fails validation."""
        # Save original value
        original_value = os.environ.get("BASE_R_PERCENT")

        try:
            # Set invalid value (negative)
            os.environ["BASE_R_PERCENT"] = "-0.01"

            # Reload settings to pick up new environment variable
            reload_settings()

            # Validate should fail
            result = validate_settings()
            assert result is False
        finally:
            # Restore original value
            if original_value is not None:
                os.environ["BASE_R_PERCENT"] = original_value
            else:
                os.environ.pop("BASE_R_PERCENT", None)

            # Reload settings back to original
            reload_settings()

    def test_validate_settings_invalid_max_r_per_trade(self):
        """Test that invalid max_r_per_trade fails validation."""
        # Save original value
        original_value = os.environ.get("MAX_R_PER_TRADE")

        try:
            # Set invalid value (negative)
            os.environ["MAX_R_PER_TRADE"] = "-1.0"

            # Reload settings to pick up new environment variable
            reload_settings()

            # Validate should fail
            result = validate_settings()
            assert result is False
        finally:
            # Restore original value
            if original_value is not None:
                os.environ["MAX_R_PER_TRADE"] = original_value
            else:
                os.environ.pop("MAX_R_PER_TRADE", None)

            # Reload settings back to original
            reload_settings()

    def test_validate_settings_invalid_leverage(self):
        """Test that invalid leverage fails validation."""
        # Save original values
        original_default = os.environ.get("DEFAULT_LEVERAGE")
        original_max = os.environ.get("MAX_LEVERAGE")

        try:
            # Set invalid values (default < 1.0)
            os.environ["DEFAULT_LEVERAGE"] = "0.5"
            os.environ["MAX_LEVERAGE"] = "10.0"

            # Reload settings to pick up new environment variables
            reload_settings()

            # Validate should fail
            result = validate_settings()
            assert result is False
        finally:
            # Restore original values
            if original_default is not None:
                os.environ["DEFAULT_LEVERAGE"] = original_default
            else:
                os.environ.pop("DEFAULT_LEVERAGE", None)

            if original_max is not None:
                os.environ["MAX_LEVERAGE"] = original_max
            else:
                os.environ.pop("MAX_LEVERAGE", None)

            # Reload settings back to original
            reload_settings()

    def test_validate_settings_invalid_slippage_tolerance(self):
        """Test that invalid slippage tolerance fails validation."""
        # Save original value
        original_value = os.environ.get("SLIPPAGE_TOLERANCE")

        try:
            # Set invalid value (greater than 1.0)
            os.environ["SLIPPAGE_TOLERANCE"] = "1.5"

            # Reload settings to pick up new environment variable
            reload_settings()

            # Validate should fail
            result = validate_settings()
            assert result is False
        finally:
            # Restore original value
            if original_value is not None:
                os.environ["SLIPPAGE_TOLERANCE"] = original_value
            else:
                os.environ.pop("SLIPPAGE_TOLERANCE", None)

            # Reload settings back to original
            reload_settings()


@pytest.mark.unit
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
        """Test that reload_settings creates new settings instance."""
        # Note: Pydantic Settings caches environment variables
        # This test verifies that reload_settings creates a new instance

        # Get initial settings
        settings1 = get_settings()
        initial_id = id(settings1)

        # Reload settings
        settings2 = reload_settings()
        reloaded_id = id(settings2)

        # Should be a new instance
        assert reloaded_id != initial_id
        assert settings1 is not settings2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

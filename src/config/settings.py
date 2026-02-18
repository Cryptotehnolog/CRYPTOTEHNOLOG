# ==================== CRYPTOTEHNOLOG Configuration Settings ====================
# Centralized configuration management using Pydantic Settings

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    CRYPTOTEHNOLOG Configuration Settings

    Loads configuration from environment variables and .env file.
    Uses Pydantic for validation and type safety.
    """

    # ==================== Project Settings ====================
    project_name: str = "CRYPTOTEHNOLOG"
    project_version: str = "1.0.0"
    environment: str = "development"
    debug: bool = True

    # ==================== Paths ====================
    # Base directory (project root)
    base_dir: Path = Field(default_factory=lambda: Path(__file__).parent.parent.parent)

    # Data directory
    data_dir: Path = Field(default_factory=lambda: Path(__file__).parent.parent.parent / "data")

    # Logs directory
    logs_dir: Path = Field(default_factory=lambda: Path(__file__).parent.parent.parent / "logs")

    # Config directory
    config_dir: Path = Field(default_factory=lambda: Path(__file__).parent.parent.parent / "config")

    # ==================== Database Settings ====================
    # PostgreSQL + TimescaleDB
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "bot_user"
    postgres_password: str = "bot_password_dev"
    postgres_db: str = "trading_dev"

    @property
    def postgres_url(self) -> str:
        """Construct PostgreSQL connection URL."""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def postgres_async_url(self) -> str:
        """Construct async PostgreSQL connection URL."""
        # Note: asyncpg uses 'postgresql' scheme, not 'postgresql+asyncpg'
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str | None = None

    @property
    def redis_url(self) -> str:
        """Construct Redis connection URL."""
        password_part = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{password_part}{self.redis_host}:{self.redis_port}/{self.redis_db}"

    # ==================== Secrets Management ====================
    # Infisical
    infisical_token: str | None = None
    infisical_address: str = "https://vault.infisical.com"
    infisical_project_id: str | None = None
    infisical_environment: str = "dev"

    # Legacy Vault (if using)
    vault_addr: str = "http://localhost:8200"
    vault_token: str = "dev-only-token"

    # ==================== Exchange API Keys ====================
    # Bybit
    bybit_api_key: str | None = None
    bybit_api_secret: str | None = None
    bybit_testnet: bool = True

    # OKX
    okx_api_key: str | None = None
    okx_api_secret: str | None = None
    okx_passphrase: str | None = None
    okx_testnet: bool = True

    # Binance
    binance_api_key: str | None = None
    binance_api_secret: str | None = None
    binance_testnet: bool = True

    # ==================== Risk Parameters ====================
    # Base Risk Percentage (e.g., 0.01 for 1%)
    base_r_percent: float = 0.01

    # Maximum R per trade
    max_r_per_trade: float = 1.0

    # Maximum portfolio R exposure
    max_portfolio_r: float = 5.0

    # Maximum position size (USD)
    max_position_size: float = 10000.0

    # ==================== Trading Settings ====================
    # Default leverage
    default_leverage: float = 1.0

    # Maximum leverage
    max_leverage: float = 10.0

    # Order timeout (seconds)
    order_timeout: int = 30

    # Slippage tolerance (percentage)
    slippage_tolerance: float = 0.001

    # ==================== Observability ====================
    # Logging Level
    log_level: str = "INFO"

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"log_level must be one of {valid_levels}")
        return v.upper()

    # Log format
    log_format: str = "JSON"

    @field_validator("log_format")
    @classmethod
    def validate_log_format(cls, v: str) -> str:
        """Validate log format."""
        valid_formats = ["JSON", "TEXT"]
        if v.upper() not in valid_formats:
            raise ValueError(f"log_format must be one of {valid_formats}")
        return v.upper()

    # Metrics enabled
    metrics_enabled: bool = True

    # Prometheus port
    prometheus_port: int = 9090

    # ==================== Web Dashboard ====================
    # Dashboard enabled
    dashboard_enabled: bool = True

    # Dashboard host
    dashboard_host: str = "0.0.0.0"

    # Dashboard port
    dashboard_port: int = 8000

    # ==================== Event Bus ====================
    # Event bus type
    event_bus_type: str = "REDIS"

    @field_validator("event_bus_type")
    @classmethod
    def validate_event_bus_type(cls, v: str) -> str:
        """Validate event bus type."""
        valid_types = ["REDIS", "ZEROMQ"]
        if v.upper() not in valid_types:
            raise ValueError(f"event_bus_type must be one of {valid_types}")
        return v.upper()

    # ZeroMQ ports (if using)
    zeromq_pub_port: int = 5555
    zeromq_sub_port: int = 5556

    # ==================== Rate Limiting ====================
    # Exchange API rate limit (requests per second)
    exchange_rate_limit: int = 10

    # WebSocket rate limit
    ws_rate_limit: int = 100

    # ==================== Circuit Breaker ====================
    # Circuit breaker enabled
    circuit_breaker_enabled: bool = True

    # Failure threshold
    failure_threshold: int = 5

    # Recovery timeout (seconds)
    recovery_timeout: int = 60

    # ==================== Kill Switch ====================
    # Kill switch enabled
    kill_switch_enabled: bool = True

    # Emergency stop on critical error
    emergency_stop_on_critical: bool = True

    # ==================== Feature Flags ====================
    # Feature flags for experimental features
    feature_exchange_monitoring: bool = True
    feature_funding_rate_arbitrage: bool = False
    feature_shadow_mode: bool = False
    feature_stress_testing: bool = False

    # ==================== Advanced Settings ====================
    # Thread pool size
    thread_pool_size: int = 4

    # Async task queue size
    async_queue_size: int = 1000

    # Connection pool size
    connection_pool_size: int = 10

    # Request timeout (seconds)
    request_timeout: int = 30

    # ==================== Pydantic Settings Config ====================
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore extra environment variables
    )

    def __repr__(self) -> str:
        """String representation of settings."""
        return (
            f"Settings(project_name={self.project_name}, "
            f"version={self.project_version}, "
            f"environment={self.environment}, "
            f"debug={self.debug})"
        )


# Global settings instance
settings = Settings()


# ==================== Settings Validation ====================
def validate_settings(settings_to_validate: Settings | None = None) -> bool:
    """
    Validate that all required settings are properly configured.

    Args:
        settings_to_validate: Settings instance to validate. If None, uses global settings.

    Returns:
        bool: True if settings are valid, False otherwise.
    """
    validation_errors = []

    # Use provided settings or global settings
    s = settings_to_validate if settings_to_validate is not None else settings

    # Validate paths exist or can be created
    required_paths = [
        ("data_dir", s.data_dir),
        ("logs_dir", s.logs_dir),
        ("config_dir", s.config_dir),
    ]

    for path_name, path in required_paths:
        try:
            path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            validation_errors.append(f"Failed to create {path_name} at {path}: {e}")

    # Validate database settings
    if s.environment == "production" and s.infisical_token is None:
        validation_errors.append("infisical_token is required in production")

    # Validate risk parameters
    if s.base_r_percent <= 0 or s.base_r_percent > 1:
        validation_errors.append("base_r_percent must be between 0 and 1")

    if s.max_r_per_trade <= 0:
        validation_errors.append("max_r_per_trade must be positive")

    if s.max_portfolio_r <= 0:
        validation_errors.append("max_portfolio_r must be positive")

    # Validate trading settings
    if s.default_leverage < 1 or s.default_leverage > s.max_leverage:
        validation_errors.append(
            f"default_leverage must be between 1 and max_leverage ({s.max_leverage})"
        )

    if s.slippage_tolerance < 0 or s.slippage_tolerance > 1:
        validation_errors.append("slippage_tolerance must be between 0 and 1")

    # Report validation results
    if validation_errors:
        print("Settings validation failed:")
        for error in validation_errors:
            print(f"  ❌ {error}")
        return False
    else:
        print("✅ Settings validation passed")
        return True


# ==================== Settings Factory ====================
def get_settings() -> Settings:
    """
    Get the global settings instance.

    Returns:
        Settings: The global settings instance.
    """
    return settings


def reload_settings() -> Settings:
    """
    Reload settings from environment variables.

    Returns:
        Settings: The reloaded settings instance.
    """
    global settings  # noqa: PLW0603 - Required for singleton pattern
    settings = Settings()
    validate_settings()
    return settings


# ==================== Main ====================
if __name__ == "__main__":
    # Print current settings (excluding secrets)
    print("CRYPTOTEHNOLOG Settings")
    print("=" * 50)
    print(f"Project Name: {settings.project_name}")
    print(f"Version: {settings.project_version}")
    print(f"Environment: {settings.environment}")
    print(f"Debug: {settings.debug}")
    print(f"PostgreSQL URL: {settings.postgres_url}")
    print(f"Redis URL: {settings.redis_url}")
    print(f"Log Level: {settings.log_level}")
    print(f"Base R%: {settings.base_r_percent}")
    print(f"Max R per Trade: {settings.max_r_per_trade}")
    print(f"Max Portfolio R: {settings.max_portfolio_r}")
    print(f"Default Leverage: {settings.default_leverage}")
    print("=" * 50)

    # Validate settings
    validate_settings()

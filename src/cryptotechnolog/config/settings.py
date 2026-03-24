# ==================== CRYPTOTEHNOLOG Configuration Settings ====================
# Centralized configuration management using Pydantic Settings

import hashlib
import json
from pathlib import Path
import threading
from typing import Any

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from cryptotechnolog.runtime_identity import get_project_name, get_runtime_version

_LOCAL_ENVIRONMENTS = frozenset({"development", "dev", "local", "test"})
_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


class Settings(BaseSettings):
    """
    CRYPTOTEHNOLOG Configuration Settings

    Loads configuration from environment variables and .env file.
    Uses Pydantic for validation and type safety.
    """

    # ==================== Project Settings ====================
    project_name: str = Field(default_factory=get_project_name)
    project_version: str = Field(default_factory=get_runtime_version)
    environment: str = "development"
    debug: bool = False

    # ==================== Paths ====================
    # Base directory (project root)
    base_dir: Path = Field(default_factory=lambda: Path(__file__).parent.parent.parent.parent)

    # Data directory
    data_dir: Path = Field(
        default_factory=lambda: Path(__file__).parent.parent.parent.parent / "data"
    )

    # Logs directory
    logs_dir: Path = Field(
        default_factory=lambda: Path(__file__).parent.parent.parent.parent / "logs"
    )

    # Config directory
    config_dir: Path = Field(
        default_factory=lambda: Path(__file__).parent.parent.parent.parent / "config"
    )

    # ==================== Database Settings ====================
    # PostgreSQL + TimescaleDB
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "bot_user"
    postgres_password: SecretStr = SecretStr("")
    postgres_db: str = "trading_dev"

    # Test database (отдельная БД для интеграционных тестов)
    postgres_test_db: str = "trading_test"

    @property
    def normalized_environment(self) -> str:
        """Return a normalized environment marker for fail-closed decisions."""
        return self.environment.strip().lower()

    @property
    def is_explicit_local_mode(self) -> bool:
        """Return True when settings are explicitly running in local/dev-like mode."""
        return self.normalized_environment in _LOCAL_ENVIRONMENTS

    @property
    def has_postgres_password(self) -> bool:
        """Return True when PostgreSQL password is explicitly configured."""
        return bool(self.postgres_password.get_secret_value().strip())

    @property
    def is_local_postgres_target(self) -> bool:
        """Return True when PostgreSQL target is clearly local-only."""
        return self.postgres_host.strip().lower() in _LOCAL_HOSTS

    @property
    def uses_default_event_bus_redis_url(self) -> bool:
        """Return True when event bus still points to the permissive local default."""
        return self.event_bus_redis_url.strip() == "redis://localhost:6379"

    def _build_postgres_url(self, database_name: str) -> str:
        """Construct PostgreSQL URL with fail-closed semantics for non-local paths."""
        if self.has_postgres_password:
            auth_part = f"{self.postgres_user}:{self.postgres_password.get_secret_value()}"
        elif self.is_explicit_local_mode and self.is_local_postgres_target:
            auth_part = f"{self.postgres_user}:"
        else:
            raise ValueError(
                "POSTGRES_PASSWORD must be explicitly configured for non-local PostgreSQL usage"
            )

        return f"postgresql://{auth_part}@{self.postgres_host}:{self.postgres_port}/{database_name}"

    @property
    def postgres_url(self) -> str:
        """Construct PostgreSQL connection URL."""
        return self._build_postgres_url(self.postgres_db)

    @property
    def postgres_async_url(self) -> str:
        """Construct async PostgreSQL connection URL."""
        # Note: asyncpg uses 'postgresql' scheme, not 'postgresql+asyncpg'
        return self._build_postgres_url(self.postgres_db)

    @property
    def postgres_test_url(self) -> str:
        """Construct test PostgreSQL connection URL."""
        return self._build_postgres_url(self.postgres_test_db)

    @property
    def postgres_test_async_url(self) -> str:
        """Construct test async PostgreSQL connection URL."""
        return self._build_postgres_url(self.postgres_test_db)

    # ==================== Connection Pooling ====================
    # PostgreSQL Connection Pool Settings
    postgres_pool_min_size: int = 2
    postgres_pool_max_size: int = 10
    postgres_pool_max_idle: int = 300  # seconds
    postgres_pool_max_inactive_connection_lifetime: int = 300  # seconds

    # Redis Connection Pool Settings
    redis_pool_max_connections: int = 50
    redis_pool_timeout: int = 5  # seconds
    redis_pool_socket_timeout: int = 5  # seconds
    redis_pool_socket_connect_timeout: int = 5  # seconds
    redis_pool_retry_on_timeout: bool = True

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: SecretStr | None = None

    @property
    def redis_url(self) -> str:
        """Construct Redis connection URL."""
        password_part = f":{self.redis_password.get_secret_value()}@" if self.redis_password else ""
        return f"redis://{password_part}{self.redis_host}:{self.redis_port}/{self.redis_db}"

    # ==================== Secrets Management ====================
    infisical_token: SecretStr | None = None
    infisical_project_id: str | None = None

    # ==================== Exchange API Keys ====================
    # Bybit
    bybit_api_key: SecretStr | None = None
    bybit_api_secret: SecretStr | None = None
    bybit_testnet: bool = True

    # OKX
    okx_api_key: SecretStr | None = None
    okx_api_secret: SecretStr | None = None
    okx_passphrase: SecretStr | None = None
    okx_testnet: bool = True

    # Binance
    binance_api_key: SecretStr | None = None
    binance_api_secret: SecretStr | None = None
    binance_testnet: bool = True

    # ==================== Risk Parameters ====================
    # Base Risk Percentage (e.g., 0.01 for 1%)
    base_r_percent: float = 0.01

    # Maximum R per trade
    max_r_per_trade: float = 1.0

    # Maximum portfolio R exposure
    max_portfolio_r: float = 5.0

    # Maximum aggregate exposure for Risk Engine portfolio checks (USD)
    risk_max_total_exposure_usd: float = 50000.0

    # Maximum position size (USD)
    max_position_size: float = 10000.0

    # Starting equity baseline for DrawdownMonitor runtime
    risk_starting_equity: float = 10000.0

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

    # Dashboard host (localhost by default for security)
    # For production, use DASHBOARD_HOST environment variable
    dashboard_host: str = "127.0.0.1"

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

    # ==================== Enhanced Event Bus Settings ====================
    # Redis URL for event persistence
    event_bus_redis_url: str = "redis://localhost:6379"

    # Queue capacities for each priority
    event_bus_capacity_critical: int = 100
    event_bus_capacity_high: int = 500
    event_bus_capacity_normal: int = 10000
    event_bus_capacity_low: int = 50000

    # Rate limiting (events per second)
    event_bus_rate_limit: int = 10000

    # Backpressure strategy
    event_bus_backpressure_strategy: str = "drop_low"

    @field_validator("event_bus_backpressure_strategy")
    @classmethod
    def validate_backpressure_strategy(cls, v: str) -> str:
        """Validate backpressure strategy."""
        valid_strategies = ["drop_low", "overflow_normal", "drop_normal", "block_critical"]
        if v.lower() not in valid_strategies:
            raise ValueError(f"event_bus_backpressure_strategy must be one of {valid_strategies}")
        return v.lower()

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
        """String representation of settings (secrets are hidden)."""
        return (
            f"Settings(project_name={self.project_name}, "
            f"version={self.project_version}, "
            f"environment={self.environment}, "
            f"debug={self.debug}, "
            f"secrets=***)"
        )

    def get_config_identity(self) -> str:
        """Вернуть operator-facing identity текущего settings-based config path."""
        return f"settings:{self.environment}:{self.config_dir.resolve()}"

    def get_config_revision(self) -> str:
        """Вернуть стабильный revision marker для текущего runtime config."""
        normalized = _normalize_config_value(self.model_dump(mode="python"))
        payload = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


_settings: Settings | None = None
_settings_lock = threading.Lock()


def _normalize_config_value(value: Any) -> Any:
    """Подготовить settings value к безопасному детерминированному hashing."""
    normalized_value = value
    if isinstance(value, SecretStr):
        normalized_value = {
            "secret_configured": bool(value.get_secret_value()),
        }
    elif isinstance(value, Path):
        normalized_value = str(value.resolve())
    elif isinstance(value, dict):
        normalized_value = {
            str(key): _normalize_config_value(nested_value)
            for key, nested_value in sorted(value.items(), key=lambda item: str(item[0]))
        }
    elif isinstance(value, (list, tuple)):
        normalized_value = [_normalize_config_value(item) for item in value]
    elif isinstance(value, set):
        normalized_value = sorted(str(_normalize_config_value(item)) for item in value)
    return normalized_value


def _collect_runtime_secret_validation_errors(settings_to_validate: Settings) -> list[str]:
    """Collect fail-closed validation errors for secrets and local defaults."""
    validation_errors: list[str] = []

    if not settings_to_validate.is_explicit_local_mode and settings_to_validate.debug:
        validation_errors.append("debug must be disabled outside explicit local/test environments")

    if not settings_to_validate.has_postgres_password and not (
        settings_to_validate.is_explicit_local_mode
        and settings_to_validate.is_local_postgres_target
    ):
        validation_errors.append(
            "postgres_password must be explicitly configured outside local/test PostgreSQL usage"
        )

    if (
        not settings_to_validate.is_explicit_local_mode
        and settings_to_validate.uses_default_event_bus_redis_url
    ):
        validation_errors.append(
            "event_bus_redis_url must be explicitly configured outside local/test environments"
        )

    return validation_errors


def _collect_domain_validation_errors(settings_to_validate: Settings) -> list[str]:
    """Collect domain validation errors for risk and trading settings."""
    validation_errors: list[str] = []

    if settings_to_validate.base_r_percent <= 0 or settings_to_validate.base_r_percent > 1:
        validation_errors.append("base_r_percent must be between 0 and 1")

    if settings_to_validate.max_r_per_trade <= 0:
        validation_errors.append("max_r_per_trade must be positive")

    if settings_to_validate.max_portfolio_r <= 0:
        validation_errors.append("max_portfolio_r must be positive")

    if (
        settings_to_validate.default_leverage < 1
        or settings_to_validate.default_leverage > settings_to_validate.max_leverage
    ):
        validation_errors.append(
            "default_leverage must be between 1 and "
            f"max_leverage ({settings_to_validate.max_leverage})"
        )

    if settings_to_validate.slippage_tolerance < 0 or settings_to_validate.slippage_tolerance > 1:
        validation_errors.append("slippage_tolerance must be between 0 and 1")

    return validation_errors


# ==================== Settings Validation ====================
def validate_settings(
    settings_to_validate: Settings | None = None,
    create_dirs: bool = False,
) -> bool:
    """
    Validate that all required settings are properly configured.

    Args:
        settings_to_validate: Settings instance to validate. If None, uses global settings.
        create_dirs: If True, create required directories. Default: False for performance.

    Returns:
        bool: True if settings are valid, False otherwise.
    """
    validation_errors: list[str] = []

    # Use provided settings or lazily initialized cached settings
    s = settings_to_validate if settings_to_validate is not None else get_settings()

    # Validate paths exist or can be created
    if create_dirs:
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

    validation_errors.extend(_collect_runtime_secret_validation_errors(s))
    validation_errors.extend(_collect_domain_validation_errors(s))

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
    global _settings  # noqa: PLW0603 - Required for cached singleton access
    with _settings_lock:
        if _settings is None:
            _settings = Settings()
        return _settings


def reload_settings() -> Settings:
    """
    Reload settings from environment variables.

    Returns:
        Settings: The reloaded settings instance.
    """
    global _settings  # noqa: PLW0603 - Required for singleton pattern
    with _settings_lock:
        _settings = Settings()
    # Note: validate_settings() is NOT called here to avoid expensive directory creation
    # during tests. Call validate_settings() explicitly when needed.
    return _settings


def __getattr__(name: str) -> Settings:
    """Ленивая compatibility-точка для старого `settings` API."""
    if name == "settings":
        return get_settings()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# ==================== Main ====================
if __name__ == "__main__":
    current_settings = get_settings()

    # Print current settings (excluding secrets)
    print("CRYPTOTEHNOLOG Settings")
    print("=" * 50)
    print(f"Project Name: {current_settings.project_name}")
    print(f"Version: {current_settings.project_version}")
    print(f"Environment: {current_settings.environment}")
    print(f"Debug: {current_settings.debug}")
    print(f"PostgreSQL URL: {current_settings.postgres_url}")
    print(f"Redis URL: {current_settings.redis_url}")
    print(f"Log Level: {current_settings.log_level}")
    print(f"Base R%: {current_settings.base_r_percent}")
    print(f"Max R per Trade: {current_settings.max_r_per_trade}")
    print(f"Max Portfolio R: {current_settings.max_portfolio_r}")
    print(f"Default Leverage: {current_settings.default_leverage}")
    print("=" * 50)

    # Validate settings
    validate_settings()

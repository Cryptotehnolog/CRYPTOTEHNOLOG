# ==================== CRYPTOTEHNOLOG Settings Type Stubs ====================
# Type stubs for configuration settings module

from __future__ import annotations

from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """CRYPTOTEHNOLOG Configuration Settings."""

    # ==================== Project Settings ====================
    project_name: str
    project_version: str
    environment: str
    debug: bool

    # ==================== Paths ====================
    base_dir: Path
    data_dir: Path
    logs_dir: Path
    config_dir: Path

    # ==================== Database Settings ====================
    postgres_host: str
    postgres_port: int
    postgres_user: str
    postgres_password: SecretStr
    postgres_db: str

    @property
    def postgres_url(self) -> str:
        """Construct PostgreSQL connection URL."""
        ...

    @property
    def postgres_async_url(self) -> str:
        """Construct async PostgreSQL connection URL."""
        ...

    # ==================== Connection Pooling ====================
    postgres_pool_min_size: int
    postgres_pool_max_size: int
    postgres_pool_max_idle: int
    postgres_pool_max_inactive_connection_lifetime: int

    redis_pool_max_connections: int
    redis_pool_timeout: int
    redis_pool_socket_timeout: int
    redis_pool_socket_connect_timeout: int
    redis_pool_retry_on_timeout: bool

    # ==================== Redis Settings ====================
    redis_host: str
    redis_port: int
    redis_db: int
    redis_password: SecretStr | None

    @property
    def redis_url(self) -> str:
        """Construct Redis connection URL."""
        ...

    # ==================== Secrets Management ====================
    vault_addr: str
    vault_token: SecretStr

    # ==================== Exchange API Keys ====================
    bybit_api_key: SecretStr | None
    bybit_api_secret: SecretStr | None
    bybit_testnet: bool

    okx_api_key: SecretStr | None
    okx_api_secret: SecretStr | None
    okx_passphrase: SecretStr | None
    okx_testnet: bool

    binance_api_key: SecretStr | None
    binance_api_secret: SecretStr | None
    binance_testnet: bool

    # ==================== Risk Parameters ====================
    base_r_percent: float
    max_r_per_trade: float
    max_portfolio_r: float
    max_position_size: float

    # ==================== Trading Settings ====================
    default_leverage: float
    max_leverage: float
    order_timeout: int
    slippage_tolerance: float

    # ==================== Observability ====================
    log_level: str
    log_format: str
    metrics_enabled: bool
    prometheus_port: int

    # ==================== Web Dashboard ====================
    dashboard_enabled: bool
    dashboard_host: str
    dashboard_port: int

    # ==================== Event Bus ====================
    event_bus_type: str
    zeromq_pub_port: int
    zeromq_sub_port: int

    # ==================== Rate Limiting ====================
    exchange_rate_limit: int
    ws_rate_limit: int

    # ==================== Circuit Breaker ====================
    circuit_breaker_enabled: bool
    failure_threshold: int
    recovery_timeout: int

    # ==================== Kill Switch ====================
    kill_switch_enabled: bool
    emergency_stop_on_critical: bool

    # ==================== Feature Flags ====================
    feature_exchange_monitoring: bool
    feature_funding_rate_arbitrage: bool
    feature_shadow_mode: bool
    feature_stress_testing: bool

    # ==================== Advanced Settings ====================
    thread_pool_size: int
    async_queue_size: int
    connection_pool_size: int
    request_timeout: int

    def __repr__(self) -> str:
        """String representation of settings."""
        ...


# ==================== Global Settings Instance ====================
settings: Settings


# ==================== Functions ====================
def validate_settings(
    settings_to_validate: Settings | None = None,
    create_dirs: bool = False,
) -> bool:
    """Validate that all required settings are properly configured."""
    ...

def get_settings() -> Settings:
    """Get the global settings instance."""
    ...

def reload_settings() -> Settings:
    """Reload settings from environment variables."""
    ...

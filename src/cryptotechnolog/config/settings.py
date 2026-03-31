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

    # ==================== Trailing Policy Settings ====================
    trailing_arm_at_pnl_r: float = Field(
        default=1.0,
        description=(
            "Recommended baseline: 1.0 R. Profit threshold at which trailing becomes armed."
        ),
    )
    trailing_t2_at_pnl_r: float = Field(
        default=2.0,
        description=("Recommended baseline: 2.0 R. Profit threshold for trailing tier 2."),
    )
    trailing_t3_at_pnl_r: float = Field(
        default=4.0,
        description=("Recommended baseline: 4.0 R. Profit threshold for trailing tier 3."),
    )
    trailing_t4_at_pnl_r: float = Field(
        default=6.0,
        description=("Recommended baseline: 6.0 R. Profit threshold for trailing tier 4."),
    )
    trailing_t1_atr_multiplier: float = Field(
        default=2.0,
        description=("Recommended baseline: 2.0. ATR multiplier used for trailing tier 1."),
    )
    trailing_t2_atr_multiplier: float = Field(
        default=1.5,
        description=("Recommended baseline: 1.5. ATR multiplier used for trailing tier 2."),
    )
    trailing_t3_atr_multiplier: float = Field(
        default=1.1,
        description=("Recommended baseline: 1.1. ATR multiplier used for trailing tier 3."),
    )
    trailing_t4_atr_multiplier: float = Field(
        default=0.8,
        description=("Recommended baseline: 0.8. ATR multiplier used for trailing tier 4."),
    )
    trailing_emergency_buffer_bps: float = Field(
        default=50.0,
        description=(
            "Recommended baseline: 50 bps. Emergency protective buffer for forced stop movement."
        ),
    )
    trailing_structural_min_adx: float = Field(
        default=25.0,
        description=(
            "Recommended baseline: 25.0. Minimum trend strength required for structural trailing."
        ),
    )
    trailing_structural_confirmed_highs: int = Field(
        default=2,
        description=(
            "Recommended baseline: 2. Minimum confirmed highs required for structural trailing."
        ),
    )
    trailing_structural_confirmed_lows: int = Field(
        default=2,
        description=(
            "Recommended baseline: 2. Minimum confirmed lows required for structural trailing."
        ),
    )

    # ==================== Correlation Policy Settings ====================
    correlation_limit: float = Field(
        default=0.80,
        description=("Recommended baseline: 0.80. Maximum allowed correlation between positions."),
    )
    same_group_correlation: float = Field(
        default=0.65,
        description=(
            "Recommended baseline: 0.65. Allowed correlation inside the same instrument group."
        ),
    )
    cross_group_correlation: float = Field(
        default=0.25,
        description=(
            "Recommended baseline: 0.25. Allowed correlation between different instrument groups."
        ),
    )

    # ==================== Protection Policy Settings ====================
    protection_halt_priority_threshold: float = Field(
        default=0.90,
        description=(
            "Recommended baseline: 0.90. Priority threshold after which the system enters "
            "hard protection mode."
        ),
    )
    protection_freeze_priority_threshold: float = Field(
        default=0.975,
        description=(
            "Recommended baseline: 0.975. Priority threshold after which the system freezes "
            "new actions."
        ),
    )

    # ==================== Funding Policy Settings ====================
    funding_min_arbitrage_spread: float = Field(
        default=0.002,
        description=(
            "Recommended baseline: 0.002. Minimum funding spread per period for arbitrage "
            "opportunity detection."
        ),
    )
    funding_min_annualized_spread: float = Field(
        default=0.05,
        description=(
            "Recommended baseline: 0.05. Minimum annualized funding spread for arbitrage "
            "opportunity detection."
        ),
    )
    funding_max_acceptable_rate: float = Field(
        default=0.003,
        description=(
            "Recommended baseline: 0.003. Maximum acceptable funding rate for opening a new "
            "position."
        ),
    )
    funding_min_exchange_improvement: float = Field(
        default=0.0005,
        description=(
            "Recommended baseline: 0.0005. Minimum rate improvement required to justify an "
            "exchange switch."
        ),
    )
    funding_min_quotes_for_opportunity: int = Field(
        default=2,
        description=(
            "Recommended baseline: 2. Minimum number of exchange quotes required to detect a "
            "funding opportunity."
        ),
    )

    # ==================== System State Policy Settings ====================
    system_trading_risk_multiplier: float = Field(
        default=1.0,
        description="Recommended baseline: 1.0. Risk multiplier for normal trading mode.",
    )
    system_trading_max_positions: int = Field(
        default=100,
        description="Recommended baseline: 100. Maximum open positions in normal trading mode.",
    )
    system_trading_max_order_size: float = Field(
        default=0.1,
        description="Recommended baseline: 0.10. Maximum new position size in trading mode.",
    )
    system_degraded_risk_multiplier: float = Field(
        default=0.5,
        description="Recommended baseline: 0.50. Risk multiplier for degraded mode.",
    )
    system_degraded_max_positions: int = Field(
        default=50,
        description="Recommended baseline: 50. Maximum open positions in degraded mode.",
    )
    system_degraded_max_order_size: float = Field(
        default=0.05,
        description="Recommended baseline: 0.05. Maximum new position size in degraded mode.",
    )
    system_risk_reduction_risk_multiplier: float = Field(
        default=0.25,
        description="Recommended baseline: 0.25. Risk multiplier for risk-reduction mode.",
    )
    system_risk_reduction_max_positions: int = Field(
        default=20,
        description="Recommended baseline: 20. Maximum open positions in risk-reduction mode.",
    )
    system_risk_reduction_max_order_size: float = Field(
        default=0.02,
        description="Recommended baseline: 0.02. Maximum new position size in risk-reduction mode.",
    )
    system_survival_risk_multiplier: float = Field(
        default=0.1,
        description="Recommended baseline: 0.10. Risk multiplier for survival mode.",
    )
    system_survival_max_positions: int = Field(
        default=0,
        description="Recommended baseline: 0. Maximum open positions in survival mode.",
    )
    system_survival_max_order_size: float = Field(
        default=0.01,
        description="Recommended baseline: 0.01. Maximum new position size in survival mode.",
    )

    # ==================== System State Timeout Settings ====================
    system_boot_max_seconds: int = Field(
        default=60,
        description="Recommended baseline: 60 seconds. Maximum time allowed in BOOT state.",
    )
    system_init_max_seconds: int = Field(
        default=120,
        description="Recommended baseline: 120 seconds. Maximum time allowed in INIT state.",
    )
    system_ready_max_seconds: int = Field(
        default=3600,
        description="Recommended baseline: 3600 seconds. Maximum time allowed in READY state.",
    )
    system_risk_reduction_max_seconds: int = Field(
        default=1800,
        description=(
            "Recommended baseline: 1800 seconds. Maximum time allowed in RISK_REDUCTION state."
        ),
    )
    system_degraded_max_seconds: int = Field(
        default=3600,
        description="Recommended baseline: 3600 seconds. Maximum time allowed in DEGRADED state.",
    )
    system_survival_max_seconds: int = Field(
        default=1800,
        description="Recommended baseline: 1800 seconds. Maximum time allowed in SURVIVAL state.",
    )
    system_error_max_seconds: int = Field(
        default=300,
        description="Recommended baseline: 300 seconds. Maximum time allowed in ERROR state.",
    )
    system_recovery_max_seconds: int = Field(
        default=600,
        description="Recommended baseline: 600 seconds. Maximum time allowed in RECOVERY state.",
    )

    # ==================== Reliability Policy Settings ====================
    reliability_circuit_breaker_failure_threshold: int = Field(
        default=5,
        description=(
            "Recommended baseline: 5. Consecutive failures allowed before circuit breaker opens."
        ),
    )
    reliability_circuit_breaker_recovery_timeout_seconds: int = Field(
        default=60,
        description=(
            "Recommended baseline: 60 seconds. Delay before circuit breaker attempts recovery."
        ),
    )
    reliability_circuit_breaker_success_threshold: int = Field(
        default=3,
        description=(
            "Recommended baseline: 3. Successful attempts needed to close circuit breaker."
        ),
    )
    reliability_watchdog_failure_threshold: int = Field(
        default=3,
        description=(
            "Recommended baseline: 3. Consecutive watchdog failures treated as a problem."
        ),
    )
    reliability_watchdog_backoff_base_seconds: float = Field(
        default=1.0,
        description=("Recommended baseline: 1.0 seconds. Base retry delay for watchdog recovery."),
    )
    reliability_watchdog_backoff_multiplier: float = Field(
        default=2.0,
        description=("Recommended baseline: 2.0. Multiplier for watchdog exponential backoff."),
    )
    reliability_watchdog_max_backoff_seconds: float = Field(
        default=60.0,
        description=("Recommended baseline: 60.0 seconds. Maximum watchdog retry delay."),
    )
    reliability_watchdog_jitter_factor: float = Field(
        default=0.5,
        description=("Recommended baseline: 0.5. Jitter factor for spreading watchdog retries."),
    )
    reliability_watchdog_check_interval_seconds: float = Field(
        default=30.0,
        description=(
            "Recommended baseline: 30.0 seconds. Interval between watchdog health checks."
        ),
    )

    # ==================== Health Policy Settings ====================
    health_check_timeout_seconds: float = Field(
        default=5.0,
        description=("Recommended baseline: 5.0 seconds. Timeout for a single health check."),
    )
    health_background_check_interval_seconds: float = Field(
        default=60.0,
        description=(
            "Recommended baseline: 60.0 seconds. Interval between background health checks."
        ),
    )
    health_check_and_wait_timeout_seconds: float = Field(
        default=30.0,
        description=(
            "Recommended baseline: 30.0 seconds. Maximum wait for overall readiness check."
        ),
    )

    # ==================== Manual Approval Policy Settings ====================
    manual_approval_timeout_minutes: int = Field(
        default=5,
        description=(
            "Recommended baseline: 5 minutes. How long a manual approval request stays active "
            "before it expires."
        ),
    )

    # ==================== Workflow Timeout Settings ====================
    workflow_manager_max_age_seconds: int = Field(
        default=3600,
        description=(
            "Recommended baseline: 3600 seconds. Maximum lifetime of a manager workflow "
            "before it expires."
        ),
    )
    workflow_validation_max_age_seconds: int = Field(
        default=3600,
        description=(
            "Recommended baseline: 3600 seconds. Maximum lifetime of a validation review "
            "before it expires."
        ),
    )
    workflow_paper_max_age_seconds: int = Field(
        default=3600,
        description=(
            "Recommended baseline: 3600 seconds. Maximum lifetime of a paper rehearsal "
            "before it expires."
        ),
    )
    workflow_replay_max_age_seconds: int = Field(
        default=3600,
        description=(
            "Recommended baseline: 3600 seconds. Maximum lifetime of a replay/backtest "
            "session before it expires."
        ),
    )
    live_feed_retry_delay_seconds: int = Field(
        default=5,
        description=(
            "Recommended baseline: 5 seconds. Base delay before reconnecting to the live feed."
        ),
    )

    # ==================== Trading Settings ====================
    # Default leverage
    default_leverage: float = 1.0

    # Maximum leverage
    max_leverage: float = 10.0

    # Order timeout (seconds)
    order_timeout: int = 30

    # Slippage tolerance (percentage)
    slippage_tolerance: float = 0.001

    # ==================== Market Data Universe Policy ====================
    universe_max_spread_bps: float = Field(
        default=25.0,
        description=(
            "Recommended baseline: 25 bps. Maximum allowed bid/ask spread for an instrument "
            "to remain admissible in the market-data universe."
        ),
    )
    universe_min_top_depth_usd: float = Field(
        default=75000.0,
        description=(
            "Recommended baseline: 75,000 USD. Minimum top-of-book depth required for an "
            "instrument to be considered liquid enough for admission."
        ),
    )
    universe_min_depth_5bps_usd: float = Field(
        default=200000.0,
        description=(
            "Recommended baseline: 200,000 USD. Minimum cumulative depth inside the 5 bps "
            "range required for stable admissibility."
        ),
    )
    universe_max_latency_ms: float = Field(
        default=250.0,
        description=(
            "Recommended baseline: 250 ms. Maximum tolerated market-data latency before the "
            "instrument is treated as low-confidence."
        ),
    )
    universe_min_coverage_ratio: float = Field(
        default=0.90,
        description=(
            "Recommended baseline: 0.90. Minimum required data coverage ratio for an "
            "instrument to remain admissible."
        ),
    )
    universe_max_data_age_ms: int = Field(
        default=3000,
        description=(
            "Recommended baseline: 3000 ms. Maximum allowed market-data staleness before the "
            "instrument is excluded as stale."
        ),
    )
    universe_min_quality_score: float = Field(
        default=0.60,
        description=(
            "Recommended baseline: 0.60. Minimum quality score required for an instrument to "
            "be admitted into the active universe."
        ),
    )
    universe_min_ready_instruments: int = Field(
        default=5,
        description=(
            "Recommended baseline: 5 instruments. Minimum admissible instrument count required "
            "for universe state READY."
        ),
    )
    universe_min_degraded_instruments_ratio: float = Field(
        default=0.10,
        description=(
            "Recommended baseline: 0.10. Minimum admissible share of the raw universe required "
            "to stay in DEGRADED instead of BLOCKED."
        ),
    )
    universe_min_ready_confidence: float = Field(
        default=0.70,
        description=(
            "Recommended baseline: 0.70. Minimum universe confidence required for state READY."
        ),
    )
    universe_min_degraded_confidence: float = Field(
        default=0.45,
        description=(
            "Recommended baseline: 0.45. Minimum universe confidence required to stay in "
            "DEGRADED instead of BLOCKED."
        ),
    )

    # ==================== Decision Chain Thresholds ====================
    signal_min_trend_strength: float = Field(
        default=20.0,
        description=(
            "Recommended baseline: 20.0. Minimum trend strength required before a signal can "
            "activate."
        ),
    )
    signal_min_regime_confidence: float = Field(
        default=0.50,
        description=(
            "Recommended baseline: 0.50. Minimum regime confidence required for signal activation."
        ),
    )
    signal_target_risk_reward: float = Field(
        default=2.0,
        description=(
            "Recommended baseline: 2.0. Target risk/reward multiple used by the signal layer."
        ),
    )
    signal_max_age_seconds: int = Field(
        default=300,
        description=(
            "Recommended baseline: 300 seconds. Maximum age of a signal before it expires."
        ),
    )
    strategy_min_signal_confidence: float = Field(
        default=0.50,
        description=(
            "Recommended baseline: 0.50. Minimum signal confidence required for a strategy "
            "candidate to become actionable."
        ),
    )
    strategy_max_candidate_age_seconds: int = Field(
        default=300,
        description=(
            "Recommended baseline: 300 seconds. Maximum lifetime of a strategy candidate."
        ),
    )
    execution_min_strategy_confidence: float = Field(
        default=0.50,
        description=(
            "Recommended baseline: 0.50. Minimum strategy confidence required to form an "
            "execution intent."
        ),
    )
    execution_max_intent_age_seconds: int = Field(
        default=300,
        description=("Recommended baseline: 300 seconds. Maximum lifetime of an execution intent."),
    )
    opportunity_min_confidence: float = Field(
        default=0.50,
        description=(
            "Recommended baseline: 0.50. Minimum intent confidence required for opportunity "
            "selection."
        ),
    )
    opportunity_min_priority: float = Field(
        default=0.50,
        description=(
            "Recommended baseline: 0.50. Minimum priority score required for opportunity selection."
        ),
    )
    opportunity_max_age_seconds: int = Field(
        default=300,
        description=(
            "Recommended baseline: 300 seconds. Maximum lifetime of a selected opportunity."
        ),
    )
    orchestration_min_confidence: float = Field(
        default=0.50,
        description=(
            "Recommended baseline: 0.50. Minimum selection confidence required for orchestration "
            "forwarding."
        ),
    )
    orchestration_min_priority: float = Field(
        default=0.50,
        description=(
            "Recommended baseline: 0.50. Minimum priority score required for orchestration "
            "forwarding."
        ),
    )
    orchestration_max_decision_age_seconds: int = Field(
        default=300,
        description=(
            "Recommended baseline: 300 seconds. Maximum lifetime of an orchestration decision."
        ),
    )

    # ==================== Observability ====================
    # Logging Level
    log_level: str = "INFO"

    @field_validator("debug", mode="before")
    @classmethod
    def validate_debug(cls, v: Any) -> bool | Any:
        """Нормализовать legacy debug/env truth к boolean."""
        if isinstance(v, str):
            normalized = v.strip().lower()
            if normalized in {"release", "production", "prod", "off"}:
                return False
            if normalized in {"debug", "development", "dev", "on"}:
                return True
        return v

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

    event_bus_subscriber_capacity: int = Field(
        default=1024,
        description=(
            "Recommended baseline: 1024 events. Default capacity of a subscriber queue before "
            "backpressure starts to matter."
        ),
    )
    event_bus_fill_ratio_low: float = Field(
        default=0.7,
        description=(
            "Recommended baseline: 0.70. Lower queue fill threshold where the bus starts "
            "treating low-priority pressure as noticeable."
        ),
    )
    event_bus_fill_ratio_normal: float = Field(
        default=0.8,
        description=(
            "Recommended baseline: 0.80. Normal queue fill threshold used for medium "
            "backpressure escalation."
        ),
    )
    event_bus_fill_ratio_high: float = Field(
        default=0.9,
        description=(
            "Recommended baseline: 0.90. High queue fill threshold where strong backpressure "
            "actions are allowed."
        ),
    )
    event_bus_push_wait_timeout_seconds: float = Field(
        default=5.0,
        description=(
            "Recommended baseline: 5.0 seconds. Maximum wait when publishing into a pressured "
            "queue before the bus gives up."
        ),
    )
    event_bus_drain_timeout_seconds: float = Field(
        default=30.0,
        description=(
            "Recommended baseline: 30.0 seconds. Maximum wait for draining remaining events "
            "before shutdown or controlled stop reports timeout."
        ),
    )

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

    def append_positive_error(field_name: str, value: int | float) -> None:
        if value <= 0:
            validation_errors.append(f"{field_name} must be positive")

    def append_unit_interval_error(field_name: str, value: int | float) -> None:
        if value < 0 or value > 1:
            validation_errors.append(f"{field_name} must be between 0 and 1")

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

    append_unit_interval_error("slippage_tolerance", settings_to_validate.slippage_tolerance)
    append_positive_error("universe_max_spread_bps", settings_to_validate.universe_max_spread_bps)
    append_positive_error(
        "universe_min_top_depth_usd",
        settings_to_validate.universe_min_top_depth_usd,
    )
    append_positive_error(
        "universe_min_depth_5bps_usd",
        settings_to_validate.universe_min_depth_5bps_usd,
    )
    append_positive_error("universe_max_latency_ms", settings_to_validate.universe_max_latency_ms)
    append_unit_interval_error(
        "universe_min_coverage_ratio",
        settings_to_validate.universe_min_coverage_ratio,
    )
    append_positive_error("universe_max_data_age_ms", settings_to_validate.universe_max_data_age_ms)
    append_unit_interval_error(
        "universe_min_quality_score",
        settings_to_validate.universe_min_quality_score,
    )
    append_positive_error(
        "universe_min_ready_instruments",
        settings_to_validate.universe_min_ready_instruments,
    )
    append_unit_interval_error(
        "universe_min_degraded_instruments_ratio",
        settings_to_validate.universe_min_degraded_instruments_ratio,
    )
    append_unit_interval_error(
        "universe_min_ready_confidence",
        settings_to_validate.universe_min_ready_confidence,
    )
    append_unit_interval_error(
        "universe_min_degraded_confidence",
        settings_to_validate.universe_min_degraded_confidence,
    )
    append_positive_error(
        "signal_min_trend_strength", settings_to_validate.signal_min_trend_strength
    )
    append_unit_interval_error(
        "signal_min_regime_confidence",
        settings_to_validate.signal_min_regime_confidence,
    )
    append_positive_error(
        "signal_target_risk_reward", settings_to_validate.signal_target_risk_reward
    )
    append_positive_error("signal_max_age_seconds", settings_to_validate.signal_max_age_seconds)
    append_unit_interval_error(
        "strategy_min_signal_confidence",
        settings_to_validate.strategy_min_signal_confidence,
    )
    append_positive_error(
        "strategy_max_candidate_age_seconds",
        settings_to_validate.strategy_max_candidate_age_seconds,
    )
    append_unit_interval_error(
        "execution_min_strategy_confidence",
        settings_to_validate.execution_min_strategy_confidence,
    )
    append_positive_error(
        "execution_max_intent_age_seconds",
        settings_to_validate.execution_max_intent_age_seconds,
    )
    append_unit_interval_error(
        "opportunity_min_confidence",
        settings_to_validate.opportunity_min_confidence,
    )
    append_unit_interval_error(
        "opportunity_min_priority", settings_to_validate.opportunity_min_priority
    )
    append_positive_error(
        "opportunity_max_age_seconds",
        settings_to_validate.opportunity_max_age_seconds,
    )
    append_unit_interval_error(
        "orchestration_min_confidence",
        settings_to_validate.orchestration_min_confidence,
    )
    append_unit_interval_error(
        "orchestration_min_priority",
        settings_to_validate.orchestration_min_priority,
    )
    append_positive_error(
        "orchestration_max_decision_age_seconds",
        settings_to_validate.orchestration_max_decision_age_seconds,
    )
    append_positive_error("trailing_arm_at_pnl_r", settings_to_validate.trailing_arm_at_pnl_r)
    append_positive_error("trailing_t2_at_pnl_r", settings_to_validate.trailing_t2_at_pnl_r)
    append_positive_error("trailing_t3_at_pnl_r", settings_to_validate.trailing_t3_at_pnl_r)
    append_positive_error("trailing_t4_at_pnl_r", settings_to_validate.trailing_t4_at_pnl_r)
    append_positive_error(
        "trailing_t1_atr_multiplier",
        settings_to_validate.trailing_t1_atr_multiplier,
    )
    append_positive_error(
        "trailing_t2_atr_multiplier",
        settings_to_validate.trailing_t2_atr_multiplier,
    )
    append_positive_error(
        "trailing_t3_atr_multiplier",
        settings_to_validate.trailing_t3_atr_multiplier,
    )
    append_positive_error(
        "trailing_t4_atr_multiplier",
        settings_to_validate.trailing_t4_atr_multiplier,
    )
    append_positive_error(
        "trailing_emergency_buffer_bps",
        settings_to_validate.trailing_emergency_buffer_bps,
    )
    append_positive_error(
        "trailing_structural_min_adx",
        settings_to_validate.trailing_structural_min_adx,
    )
    append_positive_error(
        "trailing_structural_confirmed_highs",
        settings_to_validate.trailing_structural_confirmed_highs,
    )
    append_positive_error(
        "trailing_structural_confirmed_lows",
        settings_to_validate.trailing_structural_confirmed_lows,
    )
    append_unit_interval_error("correlation_limit", settings_to_validate.correlation_limit)
    append_unit_interval_error(
        "same_group_correlation",
        settings_to_validate.same_group_correlation,
    )
    append_unit_interval_error(
        "cross_group_correlation",
        settings_to_validate.cross_group_correlation,
    )
    append_unit_interval_error(
        "protection_halt_priority_threshold",
        settings_to_validate.protection_halt_priority_threshold,
    )
    append_unit_interval_error(
        "protection_freeze_priority_threshold",
        settings_to_validate.protection_freeze_priority_threshold,
    )
    if (
        settings_to_validate.protection_freeze_priority_threshold
        < settings_to_validate.protection_halt_priority_threshold
    ):
        validation_errors.append(
            "protection_freeze_priority_threshold must be greater than or equal to "
            "protection_halt_priority_threshold"
        )
    append_positive_error(
        "funding_min_arbitrage_spread",
        settings_to_validate.funding_min_arbitrage_spread,
    )
    append_positive_error(
        "funding_min_annualized_spread",
        settings_to_validate.funding_min_annualized_spread,
    )
    append_positive_error(
        "funding_max_acceptable_rate",
        settings_to_validate.funding_max_acceptable_rate,
    )
    append_positive_error(
        "funding_min_exchange_improvement",
        settings_to_validate.funding_min_exchange_improvement,
    )
    append_positive_error(
        "funding_min_quotes_for_opportunity",
        settings_to_validate.funding_min_quotes_for_opportunity,
    )
    append_positive_error(
        "system_trading_risk_multiplier",
        settings_to_validate.system_trading_risk_multiplier,
    )
    append_positive_error(
        "system_trading_max_positions",
        settings_to_validate.system_trading_max_positions,
    )
    append_positive_error(
        "system_trading_max_order_size",
        settings_to_validate.system_trading_max_order_size,
    )
    append_positive_error(
        "system_degraded_risk_multiplier",
        settings_to_validate.system_degraded_risk_multiplier,
    )
    append_positive_error(
        "system_degraded_max_positions",
        settings_to_validate.system_degraded_max_positions,
    )
    append_positive_error(
        "system_degraded_max_order_size",
        settings_to_validate.system_degraded_max_order_size,
    )
    append_positive_error(
        "system_risk_reduction_risk_multiplier",
        settings_to_validate.system_risk_reduction_risk_multiplier,
    )
    append_positive_error(
        "system_risk_reduction_max_positions",
        settings_to_validate.system_risk_reduction_max_positions,
    )
    append_positive_error(
        "system_risk_reduction_max_order_size",
        settings_to_validate.system_risk_reduction_max_order_size,
    )
    append_positive_error(
        "system_survival_risk_multiplier",
        settings_to_validate.system_survival_risk_multiplier,
    )
    if settings_to_validate.system_survival_max_positions < 0:
        validation_errors.append("system_survival_max_positions must be non-negative")
    append_positive_error(
        "system_survival_max_order_size",
        settings_to_validate.system_survival_max_order_size,
    )
    append_positive_error("system_boot_max_seconds", settings_to_validate.system_boot_max_seconds)
    append_positive_error("system_init_max_seconds", settings_to_validate.system_init_max_seconds)
    append_positive_error("system_ready_max_seconds", settings_to_validate.system_ready_max_seconds)
    append_positive_error(
        "system_risk_reduction_max_seconds",
        settings_to_validate.system_risk_reduction_max_seconds,
    )
    append_positive_error(
        "system_degraded_max_seconds",
        settings_to_validate.system_degraded_max_seconds,
    )
    append_positive_error(
        "system_survival_max_seconds",
        settings_to_validate.system_survival_max_seconds,
    )
    append_positive_error("system_error_max_seconds", settings_to_validate.system_error_max_seconds)
    append_positive_error(
        "system_recovery_max_seconds",
        settings_to_validate.system_recovery_max_seconds,
    )
    append_positive_error(
        "reliability_circuit_breaker_failure_threshold",
        settings_to_validate.reliability_circuit_breaker_failure_threshold,
    )
    append_positive_error(
        "reliability_circuit_breaker_recovery_timeout_seconds",
        settings_to_validate.reliability_circuit_breaker_recovery_timeout_seconds,
    )
    append_positive_error(
        "reliability_circuit_breaker_success_threshold",
        settings_to_validate.reliability_circuit_breaker_success_threshold,
    )
    append_positive_error(
        "reliability_watchdog_failure_threshold",
        settings_to_validate.reliability_watchdog_failure_threshold,
    )
    append_positive_error(
        "reliability_watchdog_backoff_base_seconds",
        settings_to_validate.reliability_watchdog_backoff_base_seconds,
    )
    append_positive_error(
        "reliability_watchdog_backoff_multiplier",
        settings_to_validate.reliability_watchdog_backoff_multiplier,
    )
    append_positive_error(
        "reliability_watchdog_max_backoff_seconds",
        settings_to_validate.reliability_watchdog_max_backoff_seconds,
    )
    append_unit_interval_error(
        "reliability_watchdog_jitter_factor",
        settings_to_validate.reliability_watchdog_jitter_factor,
    )
    append_positive_error(
        "reliability_watchdog_check_interval_seconds",
        settings_to_validate.reliability_watchdog_check_interval_seconds,
    )
    append_positive_error(
        "health_check_timeout_seconds",
        settings_to_validate.health_check_timeout_seconds,
    )
    append_positive_error(
        "health_background_check_interval_seconds",
        settings_to_validate.health_background_check_interval_seconds,
    )
    append_positive_error(
        "health_check_and_wait_timeout_seconds",
        settings_to_validate.health_check_and_wait_timeout_seconds,
    )
    append_positive_error(
        "manual_approval_timeout_minutes",
        settings_to_validate.manual_approval_timeout_minutes,
    )
    append_positive_error(
        "workflow_manager_max_age_seconds",
        settings_to_validate.workflow_manager_max_age_seconds,
    )
    append_positive_error(
        "workflow_validation_max_age_seconds",
        settings_to_validate.workflow_validation_max_age_seconds,
    )
    append_positive_error(
        "workflow_paper_max_age_seconds",
        settings_to_validate.workflow_paper_max_age_seconds,
    )
    append_positive_error(
        "workflow_replay_max_age_seconds",
        settings_to_validate.workflow_replay_max_age_seconds,
    )
    append_positive_error(
        "live_feed_retry_delay_seconds",
        settings_to_validate.live_feed_retry_delay_seconds,
    )
    append_positive_error(
        "event_bus_subscriber_capacity",
        settings_to_validate.event_bus_subscriber_capacity,
    )
    append_unit_interval_error(
        "event_bus_fill_ratio_low",
        settings_to_validate.event_bus_fill_ratio_low,
    )
    append_unit_interval_error(
        "event_bus_fill_ratio_normal",
        settings_to_validate.event_bus_fill_ratio_normal,
    )
    append_unit_interval_error(
        "event_bus_fill_ratio_high",
        settings_to_validate.event_bus_fill_ratio_high,
    )
    append_positive_error(
        "event_bus_push_wait_timeout_seconds",
        settings_to_validate.event_bus_push_wait_timeout_seconds,
    )
    append_positive_error(
        "event_bus_drain_timeout_seconds",
        settings_to_validate.event_bus_drain_timeout_seconds,
    )
    if not (
        settings_to_validate.event_bus_fill_ratio_low
        < settings_to_validate.event_bus_fill_ratio_normal
        < settings_to_validate.event_bus_fill_ratio_high
    ):
        validation_errors.append("event_bus fill ratios must satisfy low < normal < high")

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


def update_settings(updates: dict[str, Any]) -> Settings:
    """
    Update the cached settings instance with validated values.

    This is a process-backed write path for product settings APIs.
    It updates the canonical in-memory Settings singleton used by the current backend runtime.
    """
    global _settings  # noqa: PLW0603 - Required for cached singleton mutation
    with _settings_lock:
        current = _settings or Settings()
        candidate_payload = current.model_dump(mode="python")
        candidate_payload.update(updates)
        candidate = Settings.model_validate(candidate_payload)

        validation_errors: list[str] = []
        validation_errors.extend(_collect_runtime_secret_validation_errors(candidate))
        validation_errors.extend(_collect_domain_validation_errors(candidate))
        if validation_errors:
            raise ValueError("; ".join(validation_errors))

        _settings = candidate
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

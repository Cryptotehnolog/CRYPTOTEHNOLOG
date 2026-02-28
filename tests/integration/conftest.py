# ==================== CRYPTOTEHNOLOG Integration Test Configuration ====================
# Pytest configuration for integration tests (requires real DB)

import asyncio
import os
import sys
from typing import TYPE_CHECKING

import asyncpg
import pytest
import pytest_asyncio
import redis.asyncio as redis

from cryptotechnolog.config.settings import Settings

# Windows asyncio fix
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

if TYPE_CHECKING:
    from collections.abc import Generator

# Set test environment
os.environ["ENVIRONMENT"] = "test"
os.environ["DEBUG"] = "true"

# Unique lock ID for test DB initialization
_TEST_DB_INIT_LOCK_ID = 1234567890


# ==================== Event Loop Fixture ====================


@pytest.fixture(scope="session")
def event_loop() -> "Generator[asyncio.AbstractEventLoop, None, None]":
    """One event loop for entire test session."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


# ==================== Database Fixtures ====================


@pytest.fixture(scope="session", autouse=True)
async def test_db_setup() -> None:
    """Initialize test DB before all integration tests.

    Uses PostgreSQL Advisory Lock to prevent concurrent initialization
    from multiple pytest-xdist workers.
    """
    settings = Settings()

    # Connect to TEST DB
    conn = await asyncpg.connect(
        settings.postgres_test_async_url,
        command_timeout=60,
    )
    try:
        # Acquire advisory lock to serialize DB initialization across workers
        # This prevents race condition when multiple xdist workers try to create tables
        lock_acquired = await conn.fetchval(
            "SELECT pg_try_advisory_lock($1)",
            _TEST_DB_INIT_LOCK_ID,
        )

        if not lock_acquired:
            # Another worker is initializing - wait for it
            await conn.execute(
                "SELECT pg_advisory_lock($1)",
                _TEST_DB_INIT_LOCK_ID,
            )

        try:
            # Check if tables already exist
            tables_exist = await conn.fetch(
                "SELECT COUNT(*) as cnt FROM pg_tables WHERE schemaname = 'public'"
            )
            tables_count = tables_exist[0]["cnt"] if tables_exist else 0

            if tables_count == 0:
                # Create tables only if they don't exist
                init_db_sql = """
                -- State Machine States (current state)
                CREATE TABLE IF NOT EXISTS state_machine_states (
                    id SERIAL PRIMARY KEY,
                    current_state VARCHAR(50) NOT NULL,
                    version INTEGER NOT NULL DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT NOW()
                );

                -- State Transitions (transition history)
                CREATE TABLE IF NOT EXISTS state_transitions (
                    id SERIAL PRIMARY KEY,
                    from_state VARCHAR(50) NOT NULL,
                    to_state VARCHAR(50) NOT NULL,
                    trigger VARCHAR(100) NOT NULL,
                    metadata JSONB,
                    operator VARCHAR(100),
                    timestamp TIMESTAMP DEFAULT NOW(),
                    duration_ms INTEGER
                );

                -- Audit Events (audit trail)
                CREATE TABLE IF NOT EXISTS audit_events (
                    id SERIAL PRIMARY KEY,
                    event_type VARCHAR(100) NOT NULL,
                    entity_type VARCHAR(100),
                    entity_id VARCHAR(100),
                    old_state JSONB,
                    new_state JSONB,
                    operator VARCHAR(100),
                    metadata JSONB,
                    timestamp TIMESTAMP DEFAULT NOW()
                );

                -- Market Data (OHLCV data)
                CREATE TABLE IF NOT EXISTS market_data (
                    id SERIAL PRIMARY KEY,
                    symbol VARCHAR(50) NOT NULL,
                    timeframe VARCHAR(10) NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    volume REAL NOT NULL,
                    timestamp TIMESTAMP NOT NULL
                );

                -- Orders
                CREATE TABLE IF NOT EXISTS orders (
                    id SERIAL PRIMARY KEY,
                    order_id VARCHAR(100) UNIQUE NOT NULL,
                    symbol VARCHAR(50) NOT NULL,
                    side VARCHAR(10) NOT NULL,
                    order_type VARCHAR(20) NOT NULL,
                    size REAL NOT NULL,
                    price REAL,
                    status VARCHAR(20) NOT NULL,
                    filled_size REAL DEFAULT 0,
                    average_price REAL,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                );

                -- Positions
                CREATE TABLE IF NOT EXISTS positions (
                    id SERIAL PRIMARY KEY,
                    symbol VARCHAR(50) UNIQUE NOT NULL,
                    side VARCHAR(10) NOT NULL,
                    size REAL NOT NULL,
                    entry_price REAL NOT NULL,
                    current_price REAL,
                    unrealized_pnl REAL,
                    realized_pnl REAL DEFAULT 0,
                    opened_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                );

                -- Risk Events
                CREATE TABLE IF NOT EXISTS risk_events (
                    id SERIAL PRIMARY KEY,
                    event_type VARCHAR(100) NOT NULL,
                    symbol VARCHAR(50),
                    size REAL,
                    price REAL,
                    risk_amount REAL,
                    allowed BOOLEAN NOT NULL,
                    reason TEXT,
                    timestamp TIMESTAMP DEFAULT NOW()
                );

                -- Risk Ledger
                CREATE TABLE IF NOT EXISTS risk_ledger (
                    id SERIAL PRIMARY KEY,
                    limit_type VARCHAR(50) NOT NULL,
                    limit_value REAL NOT NULL,
                    current_value REAL NOT NULL,
                    period_seconds INTEGER,
                    reset_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT NOW()
                );

                -- Risk Limits
                CREATE TABLE IF NOT EXISTS risk_limits (
                    id SERIAL PRIMARY KEY,
                    limit_name VARCHAR(100) UNIQUE NOT NULL,
                    limit_type VARCHAR(50) NOT NULL,
                    max_value REAL NOT NULL,
                    current_value REAL DEFAULT 0,
                    enabled BOOLEAN DEFAULT TRUE,
                    updated_at TIMESTAMP DEFAULT NOW()
                );

                -- System Metrics
                CREATE TABLE IF NOT EXISTS system_metrics (
                    id SERIAL PRIMARY KEY,
                    metric_name VARCHAR(100) NOT NULL,
                    metric_type VARCHAR(50) NOT NULL,
                    value REAL NOT NULL,
                    labels JSONB,
                    timestamp TIMESTAMP DEFAULT NOW()
                );

                -- Indexes
                CREATE INDEX IF NOT EXISTS idx_market_data_symbol_timeframe_timestamp
                    ON market_data(symbol, timeframe, timestamp);
                CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
                CREATE INDEX IF NOT EXISTS idx_positions_symbol ON positions(symbol);
                CREATE INDEX IF NOT EXISTS idx_risk_events_timestamp ON risk_events(timestamp);
                CREATE INDEX IF NOT EXISTS idx_state_transitions_timestamp ON state_transitions(timestamp);
                CREATE INDEX IF NOT EXISTS idx_audit_events_timestamp ON audit_events(timestamp);
                """

                await conn.execute(init_db_sql)

                # Insert initial state for State Machine
                await conn.execute("""
                    INSERT INTO state_machine_states (current_state, version)
                    VALUES ('boot', 0)
                    ON CONFLICT (id) DO NOTHING
                """)
            else:
                # Tables exist - just clean data
                await conn.execute("""
                    TRUNCATE TABLE state_machine_states, state_transitions, audit_events,
                    market_data, orders, positions, risk_events, risk_ledger,
                    risk_limits, system_metrics RESTART IDENTITY CASCADE
                """)

                # Insert initial state
                await conn.execute("""
                    INSERT INTO state_machine_states (current_state, version)
                    VALUES ('boot', 0)
                    ON CONFLICT (id) DO NOTHING
                """)
        finally:
            # Release advisory lock
            await conn.execute(
                "SELECT pg_advisory_unlock($1)",
                _TEST_DB_INIT_LOCK_ID,
            )
    finally:
        await conn.close()


@pytest.fixture
def db_connection_factory():
    """Factory for creating test DB connection."""

    class DBConnectionFactory:
        @staticmethod
        async def create() -> asyncpg.Connection:
            settings = Settings()
            conn = await asyncpg.connect(
                settings.postgres_test_async_url,
                command_timeout=60,
            )
            return conn

    return DBConnectionFactory


# ==================== Pool Fixture for Integration Tests ====================


@pytest_asyncio.fixture(scope="function")
async def db_pool():
    """
    Function-scoped database pool for integration tests.
    
    Использует существующий DatabaseManager из проекта.
    """
    from src.core.database import get_database, close_database
    
    db = get_database()
    await db.connect()
    
    yield db.pool
    
    await close_database()


# ==================== Settings Fixtures ====================


@pytest.fixture
def test_env(monkeypatch: pytest.MonkeyPatch) -> "Generator[dict[str, str], None, None]":
    """Set test environment."""
    env_vars = {
        "ENVIRONMENT": "test",
        "DEBUG": "true",
    }
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)
    yield env_vars


@pytest.fixture
def test_settings(test_env: dict[str, str]) -> "Settings":
    """Return test settings instance."""
    return Settings()


# ==================== Markers ====================


def pytest_configure(config: pytest.Config) -> None:
    """Register markers."""
    config.addinivalue_line("markers", "integration: integration tests with external dependencies")
    config.addinivalue_line("markers", "db: tests requiring DB connection")
    config.addinivalue_line("markers", "redis: tests requiring Redis connection")


# ==================== Redis Fixtures ====================


@pytest.fixture(scope="session", autouse=True)
async def redis_clean_state() -> None:
    """Clean Redis before all tests."""
    settings = Settings()
    client = redis.from_url(
        settings.redis_url,
        socket_timeout=10,
        socket_connect_timeout=10,
    )
    try:
        await client.flushdb()
    finally:
        await client.close()


@pytest.fixture
def redis_client_factory():
    """Factory for creating Redis client."""

    class RedisClientFactory:
        @staticmethod
        async def create() -> redis.Redis:
            settings = Settings()
            client = redis.from_url(
                settings.redis_url,
                max_connections=settings.redis_pool_max_connections,
                socket_timeout=settings.redis_pool_socket_timeout,
                socket_connect_timeout=10,
                decode_responses=True,
            )
            await asyncio.wait_for(client.ping(), timeout=10.0)
            return client

    return RedisClientFactory

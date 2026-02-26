# ==================== CRYPTOTEHNOLOG Test Configuration ====================
# Pytest configuration and fixtures

import asyncio
import os
import sys
from typing import TYPE_CHECKING

import asyncpg
import pytest
import redis.asyncio as redis

from cryptotechnolog.config.settings import Settings

# Windows asyncio fix: use SelectorEventLoop for Redis/socket operations
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

if TYPE_CHECKING:
    from collections.abc import Generator

# Set test environment
os.environ["ENVIRONMENT"] = "test"
os.environ["DEBUG"] = "true"


# ==================== Event Loop Fixture ====================


@pytest.fixture(scope="session")
def event_loop() -> "Generator[asyncio.AbstractEventLoop, None, None]":
    """Один event loop на всю тестовую сессию."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


# ==================== Database Fixtures ====================


@pytest.fixture(scope="session", autouse=True)
async def test_db_setup() -> None:
    """Инициализирует тестовую БД перед началом всех тестов.

    Использует отдельную тестовую БД (trading_test) для изоляции от production.
    Выполняется один раз перед всеми тестами сессии.
    """
    settings = Settings()
    
    # Подключаемся к ТЕСТОВОЙ БД
    conn = await asyncpg.connect(
        settings.postgres_test_async_url,
        command_timeout=60,
    )
    try:
        # Удаляем все таблицы и пересоздаём схему в тестовой БД
        tables = await conn.fetch("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        for table in tables:
            await conn.execute(f"DROP TABLE IF EXISTS {table['tablename']} CASCADE")
        
        # Создаём таблицы
        init_db_sql = """
        -- State Machine States (текущее состояние)
        CREATE TABLE IF NOT EXISTS state_machine_states (
            id SERIAL PRIMARY KEY,
            current_state VARCHAR(50) NOT NULL,
            version INTEGER NOT NULL DEFAULT 0,
            updated_at TIMESTAMP DEFAULT NOW()
        );

        -- State Transitions (история переходов)
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

        -- Audit Events (аудит всех событий)
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

        -- Market Data (OHLCV данные)
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

        -- Orders (ордера)
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

        -- Positions (позиции)
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

        -- Risk Events (события риск-менеджмента)
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

        -- Risk Ledger (журнал риск-лимитов)
        CREATE TABLE IF NOT EXISTS risk_ledger (
            id SERIAL PRIMARY KEY,
            limit_type VARCHAR(50) NOT NULL,
            limit_value REAL NOT NULL,
            current_value REAL NOT NULL,
            period_seconds INTEGER,
            reset_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT NOW()
        );

        -- Risk Limits (лимиты риска)
        CREATE TABLE IF NOT EXISTS risk_limits (
            id SERIAL PRIMARY KEY,
            limit_name VARCHAR(100) UNIQUE NOT NULL,
            limit_type VARCHAR(50) NOT NULL,
            max_value REAL NOT NULL,
            current_value REAL DEFAULT 0,
            enabled BOOLEAN DEFAULT TRUE,
            updated_at TIMESTAMP DEFAULT NOW()
        );

        -- System Metrics (метрики системы)
        CREATE TABLE IF NOT EXISTS system_metrics (
            id SERIAL PRIMARY KEY,
            metric_name VARCHAR(100) NOT NULL,
            metric_type VARCHAR(50) NOT NULL,
            value REAL NOT NULL,
            labels JSONB,
            timestamp TIMESTAMP DEFAULT NOW()
        );

        -- Индексы для оптимизации
        CREATE INDEX IF NOT EXISTS idx_market_data_symbol_timeframe_timestamp 
            ON market_data(symbol, timeframe, timestamp);
        CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
        CREATE INDEX IF NOT EXISTS idx_positions_symbol ON positions(symbol);
        CREATE INDEX IF NOT EXISTS idx_risk_events_timestamp ON risk_events(timestamp);
        CREATE INDEX IF NOT EXISTS idx_state_transitions_timestamp ON state_transitions(timestamp);
        CREATE INDEX IF NOT EXISTS idx_audit_events_timestamp ON audit_events(timestamp);

        -- Вставляем начальное состояние для State Machine
        INSERT INTO state_machine_states (current_state, version) 
        VALUES ('boot', 0)
        ON CONFLICT (id) DO NOTHING;
        """
        
        await conn.execute(init_db_sql)
    finally:
        await conn.close()


@pytest.fixture
def db_connection_factory():
    """Фабрика для создания соединения с ТЕСТОВОЙ БД внутри теста.

    Создаёт соединение в том же event loop, где выполняется тест.
    Использует тестовую БД (trading_test) для изоляции.
    """

    class DBConnectionFactory:
        """Фабрика создания соединения с тестовой БД."""

        @staticmethod
        async def create() -> asyncpg.Connection:
            """Создать новое соединение с тестовой БД."""
            settings = Settings()

            conn = await asyncpg.connect(
                settings.postgres_test_async_url,  # Используем тестовую БД
                command_timeout=60,
            )

            return conn

    return DBConnectionFactory


# ==================== Settings Fixtures ====================


@pytest.fixture
def test_env(monkeypatch: pytest.MonkeyPatch) -> "Generator[dict[str, str], None, None]":
    """Устанавливает тестовое окружение."""
    env_vars = {
        "ENVIRONMENT": "test",
        "DEBUG": "true",
    }
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)
    yield env_vars


@pytest.fixture
def test_settings(test_env: dict[str, str]) -> "Settings":
    """Возвращает экземпляр настроек для тестов."""
    from cryptotechnolog.config.settings import Settings  # noqa: PLC0415

    return Settings()


# ==================== Markers ====================


def pytest_configure(config: pytest.Config) -> None:
    """Регистрирует маркеры."""
    config.addinivalue_line("markers", "integration: интеграционные тесты с внешними зависимостями")
    config.addinivalue_line("markers", "db: тесты, требующие подключения к БД")
    config.addinivalue_line("markers", "redis: тесты, требующие подключения к Redis")


# ==================== Redis Fixtures ====================


@pytest.fixture(scope="session", autouse=True)
async def redis_clean_state() -> None:
    """Очищает Redis перед началом всех тестов.

    Выполняется один раз перед всеми тестами сессии.
    """
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
    """Фабрика для создания Redis клиента внутри теста.

    Создаёт клиент в том же event loop, где выполняется тест.
    Гарантирует отсутствие конфликтов event loops.
    """

    class RedisClientFactory:
        """Фабрика создания Redis клиента."""

        @staticmethod
        async def create() -> redis.Redis:
            """Создать новый Redis клиент."""
            settings = Settings()

            client = redis.from_url(
                settings.redis_url,
                max_connections=settings.redis_pool_max_connections,
                socket_timeout=settings.redis_pool_socket_timeout,
                socket_connect_timeout=10,
                decode_responses=True,
            )

            # Проверить подключение
            await asyncio.wait_for(client.ping(), timeout=10.0)

            return client

    return RedisClientFactory

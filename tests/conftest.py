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
async def db_clean_state() -> None:
    """Очищает PostgreSQL перед началом всех тестов.

    Выполняется один раз перед всеми тестами сессии.
    """
    settings = Settings()
    conn = await asyncpg.connect(
        settings.postgres_async_url,
        command_timeout=60,
    )
    try:
        # Удаляем все таблицы и пересоздаём схему
        tables = await conn.fetch("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        for table in tables:
            await conn.execute(f"DROP TABLE IF EXISTS {table['tablename']} CASCADE")
    finally:
        await conn.close()


@pytest.fixture
def db_connection_factory():
    """Фабрика для создания соединения с БД внутри теста.

    Создаёт соединение в том же event loop, где выполняется тест.
    Гарантирует отсутствие конфликтов event loops.
    """

    class DBConnectionFactory:
        """Фабрика создания соединения с БД."""

        @staticmethod
        async def create() -> asyncpg.Connection:
            """Создать новое соединение с БД."""
            settings = Settings()

            conn = await asyncpg.connect(
                settings.postgres_async_url,
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

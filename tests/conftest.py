# ==================== CRYPTOTEHNOLOG Test Configuration ====================
# Pytest configuration and fixtures

import asyncio
from collections.abc import AsyncGenerator, Generator
import os
from typing import TYPE_CHECKING

import asyncpg
import pytest
import redis.asyncio as redis

from cryptotechnolog.config.settings import Settings

if TYPE_CHECKING:
    from asyncpg import Pool

    from src.core.database import DatabaseManager
    from src.core.redis_manager import RedisManager

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


@pytest.fixture(scope="session")
async def db_pool(event_loop: asyncio.AbstractEventLoop) -> AsyncGenerator["Pool", None]:
    """Один пул соединений на всю тестовую сессию.

    Создаётся один раз и переиспользуется всеми тестами.
    """
    settings = Settings()

    pool = await asyncpg.create_pool(
        settings.postgres_async_url,
        min_size=2,
        max_size=10,
        command_timeout=60,
    )

    yield pool

    await pool.close()


@pytest.fixture(scope="session")
async def db_manager(db_pool: "Pool") -> AsyncGenerator["DatabaseManager", None]:
    """DatabaseManager с переданным пулом."""
    from src.core.database import DatabaseManager  # noqa: PLC0415

    db = DatabaseManager(min_size=2, max_size=10)
    # Используем переданный пул
    db._pool = db_pool
    db._connected = True

    # Прогрев пула - выполняем простой запрос чтобы убедиться что всё работает
    async with db_pool.acquire() as conn:
        await conn.fetchval("SELECT 1")

    yield db


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


@pytest.fixture(scope="session")
async def redis_client(event_loop: asyncio.AbstractEventLoop) -> AsyncGenerator[redis.Redis, None]:
    """Один клиент Redis на всю тестовую сессию.

    Создаётся один раз и переиспользуется всеми тестами.
    """
    settings = Settings()

    client = redis.from_url(
        settings.redis_url,
        max_connections=settings.redis_pool_max_connections,
        socket_timeout=settings.redis_pool_socket_timeout,
        decode_responses=True,
    )

    # Проверить подключение
    await client.ping()

    yield client

    await client.close()


@pytest.fixture(scope="session")
async def redis_manager(redis_client: redis.Redis) -> AsyncGenerator["RedisManager", None]:
    """RedisManager с переданным клиентом."""
    from src.core.redis_manager import RedisManager  # noqa: PLC0415

    mgr = RedisManager()
    # Используем переданный клиент
    mgr._redis = redis_client
    mgr._connected = True

    yield mgr

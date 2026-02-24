# ==================== CRYPTOTEHNOLOG Test Configuration ====================
# Pytest configuration and fixtures

import asyncio
from collections.abc import AsyncGenerator, Generator
import os
from typing import TYPE_CHECKING, cast

import asyncpg
import pytest

from cryptotechnolog.config.settings import Settings

if TYPE_CHECKING:
    from asyncpg import Connection, Pool

    from src.core.database import DatabaseManager

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
    db._pool = db_pool
    db._connected = True

    yield db


@pytest.fixture
async def db_connection(db_pool: "Pool") -> AsyncGenerator["Connection", None]:
    """Соединение с транзакцией. После теста - ROLLBACK.

    Каждый тест получает чистое соединение:
    - BEGIN в начале
    - ROLLBACK в конце (даже при ошибке)

    Это гарантирует 100% изоляцию тестов.
    """
    async with db_pool.acquire() as conn:
        await conn.execute("BEGIN")

        try:
            yield cast("Connection", conn)
        finally:
            await conn.execute("ROLLBACK")

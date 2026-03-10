# ==================== E2E Test Configuration ====================
"""E2E тесты используют fixtures из integration для работы с БД и Redis."""

import asyncio
import os
import sys
from collections.abc import AsyncGenerator, Generator
from pathlib import Path

from typing import TYPE_CHECKING

import asyncpg
import pytest
import pytest_asyncio

if TYPE_CHECKING:
    from cryptotechnolog.core.enhanced_event_bus import EnhancedEventBus

# Windows asyncio fix
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Set test environment
os.environ["ENVIRONMENT"] = "test"
os.environ["DEBUG"] = "true"


# Session-scoped event loop для всех E2E тестов
@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Один event loop для всех E2E тестов."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


# Function-scoped db_pool - создаём новый пул для каждого теста
@pytest_asyncio.fixture(scope="function")
async def db_pool() -> AsyncGenerator[asyncpg.Pool, None]:
    """Function-scoped пул БД для E2E тестов."""
    from cryptotechnolog.config.settings import Settings
    from tests.integration.conftest import apply_migrations

    settings = Settings()

    # Создаём новый пул для каждого теста
    pool = await asyncpg.create_pool(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.postgres_user,
        password=settings.postgres_password.get_secret_value(),
        database=settings.postgres_test_db,
        min_size=2,
        max_size=5,
    )

    try:
        # Проверяем, существуют ли уже таблицы
        async with pool.acquire() as conn:
            tables = await conn.fetch(
                "SELECT table_name FROM information_schema.tables " "WHERE table_schema = 'public'"
            )
            table_names = {row["table_name"] for row in tables}

            # Применяем миграции только если таблиц нет
            if "schema_migrations" not in table_names:
                await apply_migrations(conn)

            # Применяем миграцию config_versions если её нет
            if "config_versions" not in table_names:
                config_versions_migration = (
                    Path(__file__).parent.parent.parent
                    / "scripts"
                    / "migrations"
                    / "010_config_versions.sql"
                )
                if config_versions_migration.exists():
                    sql = config_versions_migration.read_text(encoding="utf-8")
                    await conn.execute(sql)

        yield pool
    finally:
        # Cleanup
        await pool.close()


# Clean Redis state для каждого теста
@pytest_asyncio.fixture(autouse=True)
async def redis_clean_state() -> AsyncGenerator[None, None]:
    """Очистка Redis перед каждым тестом."""
    import redis.asyncio as redis

    from cryptotechnolog.config.settings import Settings

    settings = Settings()
    client = redis.Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        decode_responses=False,
    )
    try:
        await client.flushdb()
    finally:
        await client.close()

    yield


# Event bus fixture для E2E тестов
@pytest.fixture
def event_bus() -> "EnhancedEventBus":
    """Создать event bus для E2E тестов."""
    from cryptotechnolog.core.enhanced_event_bus import EnhancedEventBus

    return EnhancedEventBus(
        enable_persistence=False,
        rate_limit=1000,
    )

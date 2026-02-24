"""
Фикстуры для тестирования PostgreSQL.

Один пул на всю сессию + транзакционная изоляция каждого теста.
"""

from collections.abc import AsyncGenerator

import asyncpg
import pytest

from cryptotechnolog.config import get_settings
from src.core.database import DatabaseManager

# ==================== Session-scoped Pool ====================


@pytest.fixture(scope="session")
async def db_pool() -> AsyncGenerator[asyncpg.Pool, None]:
    """
    Создать один пул соединений на всю тестовую сессию.

    Использует настройки из Settings, но с ограниченным размером пула.
    """
    settings = get_settings()

    pool = await asyncpg.create_pool(
        settings.postgres_async_url,
        min_size=2,
        max_size=10,
        command_timeout=60,
    )

    yield pool

    await pool.close()


@pytest.fixture(scope="session")
async def db_manager(db_pool: asyncpg.Pool) -> AsyncGenerator[DatabaseManager, None]:
    """
    Создать DatabaseManager с переданным пулом.

    Это позволяет тестам использовать высокоуровневые методы
    DatabaseManager, но с единым пулом.
    """
    db = DatabaseManager(min_size=2, max_size=10)
    db._pool = db_pool
    db._connected = True

    yield db

    # Пул закрывается в db_pool fixture


# ==================== Function-scoped Connection with Transaction ====================


@pytest.fixture
async def db_connection(
    db_pool: asyncpg.Pool,
) -> AsyncGenerator[asyncpg.PoolConnectionProxy, None]:
    """
    Предоставить соединение с авто-ROLLBACK после каждого теста.

    Каждый тест получает чистое соединение:
    - BEGIN в начале
    - ROLLBACK в конце (даже при ошибке)

    Это гарантирует 100% изоляцию тестов.
    """
    async with db_pool.acquire() as conn:
        # Начать транзакцию
        await conn.execute("BEGIN")

        try:
            yield conn
        finally:
            # Всегда откатывать - тест не должен мусорить в БД
            await conn.execute("ROLLBACK")


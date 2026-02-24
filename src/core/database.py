"""
Database Layer — PostgreSQL Manager с асинхронным подключением.

Использует asyncpg для высокопроизводительного асинхронного доступа к PostgreSQL.
Поддерживает:
- Connection pooling
- Транзакции
- Prepared statements
- Контекстные менеджеры
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, cast

import asyncpg

from cryptotechnolog.config import get_logger, get_settings

logger = get_logger(__name__)


class DatabaseManager:
    """
    Менеджер подключения к PostgreSQL.

    Обеспечивает:
    - Пул соединений с настраиваемыми параметрами
    - Асинхронные операции
    - Транзакции с автоматическим rollback
    - Graceful shutdown

    Пример:
        >>> db = DatabaseManager()
        >>> await db.connect()
        >>> result = await db.fetch("SELECT * FROM orders WHERE status = $1", "pending")
        >>> await db.disconnect()
    """

    def __init__(
        self,
        min_size: int | None = None,
        max_size: int | None = None,
    ) -> None:
        """
        Инициализировать менеджер базы данных.

        Аргументы:
            min_size: Минимальный размер пула (по умолчанию из настроек)
            max_size: Максимальный размер пула (по умолчанию из настроек)
        """
        settings = get_settings()

        self._min_size = min_size or settings.postgres_pool_min_size
        self._max_size = max_size or settings.postgres_pool_max_size
        self._url = settings.postgres_async_url

        self._pool: asyncpg.Pool | None = None
        self._connected = False

        logger.info(
            "Инициализирован менеджер БД",
            min_size=self._min_size,
            max_size=self._max_size,
        )

    @property
    def is_connected(self) -> bool:
        """Проверить подключение к БД."""
        return self._connected and self._pool is not None

    @property
    def pool(self) -> asyncpg.Pool | None:
        """Получить пул соединений."""
        return self._pool

    async def connect(self) -> None:
        """
        Подключиться к PostgreSQL и создать пул соединений.

        Raises:
            RuntimeError: Если подключение уже установлено
            asyncpg.InvalidCatalogNameError: Если БД не существует
            asyncpg.InvalidPasswordError: Если неверный пароль
        """
        if self._connected and self._pool is not None:
            raise RuntimeError("Уже подключено к БД")

        logger.info("Подключение к PostgreSQL", url=self._url.split("@")[1])

        try:
            self._pool = await asyncpg.create_pool(
                self._url,
                min_size=self._min_size,
                max_size=self._max_size,
                command_timeout=60,
            )
            self._connected = True

            # Проверить подключение
            async with self._pool.acquire() as conn:
                version = await conn.fetchval("SELECT version()")
                logger.info("Подключение к PostgreSQL установлено", version=version[:50])

        except Exception as e:
            logger.error("Ошибка подключения к PostgreSQL", error=str(e))
            self._pool = None
            self._connected = False
            raise

    async def disconnect(self) -> None:
        """Отключиться от PostgreSQL и закрыть пул."""
        if self._pool is not None:
            logger.info("Закрытие пула соединений PostgreSQL")
            await self._pool.close()
            self._pool = None
            self._connected = False
            logger.info("Отключение от PostgreSQL выполнено")

    @asynccontextmanager
    async def connection(self) -> AsyncIterator[asyncpg.Connection]:
        """
        Контекстный менеджер для получения соединения из пула.

        Yields:
            asyncpg.Connection: Соединение с БД

        Пример:
            >>> async with db.connection() as conn:
            ...     await conn.fetch("SELECT 1")
        """
        if self._pool is None:
            raise RuntimeError("Нет подключения к БД. Вызовите connect()")

        async with self._pool.acquire() as conn:
            yield cast(asyncpg.Connection, conn)

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[asyncpg.Connection]:
        """
        Контекстный менеджер для транзакции.

        Автоматически commit при успехе, rollback при ошибке.

        Yields:
            asyncpg.Connection: Соединение внутри транзакции

        Пример:
            >>> async with db.transaction() as tx:
            ...     await tx.execute("INSERT INTO orders ...")
            ...     # автоматический commit
        """
        async with self.connection() as conn, conn.transaction():
            yield conn

    # ==================== Convenience Methods ====================

    async def fetch(
        self,
        query: str,
        *args: Any,
    ) -> list[dict[str, Any]]:
        """
        Выполнить SELECT запрос и вернуть результаты.

        Аргументы:
            query: SQL запрос
            *args: Позиционные аргументы для запроса

        Returns:
            Список словарей с результатами

        Пример:
            >>> rows = await db.fetch("SELECT * FROM orders WHERE status = $1", "pending")
        """
        async with self.connection() as conn:
            rows = await conn.fetch(query, *args)
            return [dict(row) for row in rows]

    async def fetchrow(
        self,
        query: str,
        *args: Any,
    ) -> dict[str, Any] | None:
        """
        Выполнить SELECT запрос и вернуть одну строку.

        Аргументы:
            query: SQL запрос
            *args: Позиционные аргументы для запроса

        Returns:
            Словарь с результатом или None

        Пример:
            >>> row = await db.fetchrow("SELECT * FROM orders WHERE id = $1", order_id)
        """
        async with self.connection() as conn:
            row = await conn.fetchrow(query, *args)
            return dict(row) if row else None

    async def fetchval(
        self,
        query: str,
        *args: Any,
    ) -> Any:
        """
        Выполнить SELECT запрос и вернуть одно значение.

        Аргументы:
            query: SQL запрос
            *args: Позиционные аргументы для запроса

        Returns:
            Значение первой колонки первой строки

        Пример:
            >>> count = await db.fetchval("SELECT COUNT(*) FROM orders")
        """
        async with self.connection() as conn:
            return await conn.fetchval(query, *args)

    async def execute(
        self,
        query: str,
        *args: Any,
    ) -> str | None:
        """
        Выполнить INSERT/UPDATE/DELETE запрос.

        Аргументы:
            query: SQL запрос
            *args: Позиционные аргументы для запроса

        Returns:
            Результат выполнения

        Пример:
            >>> await db.execute("INSERT INTO orders (id, status) VALUES ($1, $2)", order_id, "new")
        """
        async with self.connection() as conn:
            result = await conn.execute(query, *args)
            return cast("str | None", result)

    async def execute_many(
        self,
        query: str,
        args_list: list[tuple[Any, ...]],
    ) -> None:
        """
        Выполнить запрос для множества наборов аргументов.

        Аргументы:
            query: SQL запрос
            args_list: Список кортежей с аргументами

        Пример:
            >>> await db.execute_many(
            ...     "INSERT INTO orders (id, status) VALUES ($1, $2)",
            ...     [(1, "new"), (2, "pending"), (3, "filled")]
            ... )
        """
        async with self.connection() as conn:
            await conn.executemany(query, args_list)

    async def health_check(self) -> dict[str, Any]:
        """
        Проверить здоровье подключения к БД.

        Returns:
            Словарь с статусом проверки
        """
        if not self.is_connected:
            return {
                "status": "unhealthy",
                "connected": False,
                "error": "Нет подключения к БД",
            }

        try:
            async with self.connection() as conn:
                # Простой запрос для проверки
                await conn.fetchval("SELECT 1")

                # Получить статистику пула
                pool_stats = self._pool.get_stats()  # type: ignore[union-attr]

                return {
                    "status": "healthy",
                    "connected": True,
                    "pool_size": self._min_size,
                    "pool_max_size": self._max_size,
                    "idle_connections": pool_stats.idle_count,
                    "busy_connections": pool_stats.busy_count,
                    "max_concurrent_requests": pool_stats.max_concurrent_requests,
                }
        except Exception as e:
            return {
                "status": "unhealthy",
                "connected": False,
                "error": str(e),
            }

    async def get_table_names(self) -> list[str]:
        """
        Получить список всех таблиц в БД.

        Returns:
            Список имён таблиц
        """
        query = """
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
AND table_type = 'BASE TABLE'
ORDER BY table_name
"""
        rows = await self.fetch(query)
        return [row["table_name"] for row in rows]

    async def table_exists(self, table_name: str) -> bool:
        """
        Проверить существование таблицы.

        Аргументы:
            table_name: Имя таблицы

        Returns:
            True если таблица существует
        """
        query = """
SELECT EXISTS (
    SELECT FROM information_schema.tables
    WHERE table_schema = 'public'
    AND table_name = $1
) AS exists
"""
        result = await self.fetchval(query, table_name)
        return result is True


# Глобальный экземпляр
_db_manager: DatabaseManager | None = None


def get_database() -> DatabaseManager:
    """
    Получить глобальный экземпляр DatabaseManager.

    Returns:
        Экземпляр менеджера БД
    """
    global _db_manager  # noqa: PLW0603
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


async def init_database() -> DatabaseManager:
    """
    Инициализировать подключение к БД.

    Returns:
        Подключённый экземпляр DatabaseManager
    """
    db = get_database()
    await db.connect()
    return db


async def close_database() -> None:
    """Закрыть подключение к БД."""
    global _db_manager  # noqa: PLW0603
    if _db_manager is not None:
        await _db_manager.disconnect()
        _db_manager = None

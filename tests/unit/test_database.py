"""
Тесты для Database Manager (src/core/database.py).

Используют паттерн "один пул + транзакционная изоляция":
- Один пул на всю сессию
- Каждый тест работает в своей транзакции с авто-ROLLBACK
"""

import asyncpg
import pytest

from src.core.database import DatabaseManager, get_database


class TestDatabaseManagerInit:
    """Тесты инициализации DatabaseManager."""

    def test_default_init(self) -> None:
        """Инициализация с параметрами по умолчанию."""
        db = DatabaseManager()
        assert db is not None
        assert not db.is_connected
        assert db._min_size == 2
        assert db._max_size == 10

    def test_custom_pool_size(self) -> None:
        """Инициализация с кастомным размером пула."""
        db = DatabaseManager(min_size=1, max_size=3)
        assert db._min_size == 1
        assert db._max_size == 3

    def test_get_database_singleton(self) -> None:
        """Получение глобального экземпляра."""
        db1 = get_database()
        db2 = get_database()
        assert db1 is db2


class TestDatabaseManagerConnection:
    """Тесты подключения к БД."""

    @pytest.mark.asyncio
    async def test_disconnect_when_not_connected(self) -> None:
        """Отключение без подключения не должно вызывать ошибку."""
        db = DatabaseManager()
        await db.disconnect()
        assert not db.is_connected


class TestDatabaseManagerOperations:
    """Тесты операций с БД (с транзакционной изоляцией)."""

    @pytest.mark.asyncio
    async def test_connection_context_manager(
        self, db_connection: asyncpg.Connection
    ) -> None:
        """Контекстный менеджер connection работает."""
        result = await db_connection.fetchval("SELECT 1")
        assert result == 1

    @pytest.mark.asyncio
    async def test_transaction_isolation(self, db_connection: asyncpg.Connection) -> None:
        """Транзакция изолирует изменения."""
        # Создать таблицу в транзакции
        await db_connection.execute("""
            CREATE TEMP TABLE test_isolation (
                id SERIAL PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        # Вставить данные
        await db_connection.execute("INSERT INTO test_isolation (value) VALUES ($1)", "test_value")

        # Данные есть в транзакции
        row = await db_connection.fetchrow("SELECT value FROM test_isolation")
        assert row is not None
        assert row["value"] == "test_value"

        # После ROLLBACK (в fixture) таблица будет удалена

    @pytest.mark.asyncio
    async def test_fetch_returns_list_of_dicts(
        self, db_connection: asyncpg.Connection
    ) -> None:
        """Метод fetch возвращает список словарей."""
        rows = await db_connection.fetch("SELECT 1 as col1, 'test' as col2")

        assert isinstance(rows, list)
        assert len(rows) == 1
        assert rows[0]["col1"] == 1
        assert rows[0]["col2"] == "test"

    @pytest.mark.asyncio
    async def test_fetchrow_returns_single_dict(
        self, db_connection: asyncpg.Connection
    ) -> None:
        """Метод fetchrow возвращает один словарь."""
        row = await db_connection.fetchrow("SELECT 1 as id, 'test' as name")

        assert row is not None
        assert row["id"] == 1
        assert row["name"] == "test"

    @pytest.mark.asyncio
    async def test_fetchrow_returns_none_when_no_rows(
        self, db_connection: asyncpg.Connection
    ) -> None:
        """Метод fetchrow возвращает None если нет строк."""
        row = await db_connection.fetchrow("SELECT 1 WHERE 1=0")
        assert row is None

    @pytest.mark.asyncio
    async def test_fetchval_returns_single_value(
        self, db_connection: asyncpg.Connection
    ) -> None:
        """Метод fetchval возвращает одно значение."""
        result = await db_connection.fetchval("SELECT COUNT(*)")
        assert isinstance(result, int)

    @pytest.mark.asyncio
    async def test_execute_insert(self, db_connection: asyncpg.Connection) -> None:
        """Метод execute для INSERT."""
        # Создать временную таблицу (удаляется при rollback)
        await db_connection.execute("""
            CREATE TEMP TABLE test_execute (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL
            )
        """)

        # Вставить данные
        result = await db_connection.execute(
            "INSERT INTO test_execute (name) VALUES ($1)", "test_name"
        )

        assert result == "INSERT 0 1"

        # Проверить данные (внутри транзакции)
        row = await db_connection.fetchrow("SELECT name FROM test_execute")
        assert row is not None
        assert row["name"] == "test_name"

    @pytest.mark.asyncio
    async def test_execute_many(self, db_connection: asyncpg.Connection) -> None:
        """Метод execute_many для массовой вставки."""
        # Создать таблицу
        await db_connection.execute("""
            CREATE TEMP TABLE test_bulk (
                id SERIAL PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        # Вставить много записей
        args_list = [
            ("value1",),
            ("value2",),
            ("value3",),
        ]

        await db_connection.executemany("INSERT INTO test_bulk (value) VALUES ($1)", args_list)

        # Проверить
        count = await db_connection.fetchval("SELECT COUNT(*) FROM test_bulk")
        assert count == 3


class TestDatabaseManagerHighLevel:
    """Тесты высокоуровневых методов DatabaseManager."""

    @pytest.mark.asyncio
    async def test_fetch_with_db_manager(self, db_manager: DatabaseManager) -> None:
        """Тест высокоуровневого fetch через DatabaseManager."""
        rows = await db_manager.fetch("SELECT 1 as num, 'hello' as text")

        assert len(rows) == 1
        assert rows[0]["num"] == 1
        assert rows[0]["text"] == "hello"

    @pytest.mark.asyncio
    async def test_fetchrow_with_db_manager(self, db_manager: DatabaseManager) -> None:
        """Тест высокоуровневого fetchrow через DatabaseManager."""
        row = await db_manager.fetchrow("SELECT 1 as id, 'test' as name")

        assert row is not None
        assert row["id"] == 1
        assert row["name"] == "test"

    @pytest.mark.asyncio
    async def test_fetchval_with_db_manager(self, db_manager: DatabaseManager) -> None:
        """Тест высокоуровневого fetchval через DatabaseManager."""
        result = await db_manager.fetchval("SELECT 42 as answer")
        assert result == 42


class TestDatabaseManagerHealthCheck:
    """Тесты health check."""

    @pytest.mark.asyncio
    async def test_health_check_when_not_connected(self) -> None:
        """Health check без подключения."""
        db = DatabaseManager()

        health = await db.health_check()

        assert health["status"] == "unhealthy"
        assert not health["connected"]
        assert "Нет подключения" in health["error"]

    @pytest.mark.asyncio
    async def test_health_check_with_pool(self, db_manager: DatabaseManager) -> None:
        """Health check с подключённым пулом."""
        health = await db_manager.health_check()

        assert health["status"] == "healthy"
        assert health["connected"]
        assert "pool_size" in health


class TestDatabaseManagerTableInfo:
    """Тесты получения информации о таблицах."""

    @pytest.mark.asyncio
    async def test_get_table_names(self, db_manager: DatabaseManager) -> None:
        """Получение списка таблиц."""
        tables = await db_manager.get_table_names()

        assert isinstance(tables, list)

    @pytest.mark.asyncio
    async def test_table_exists(self, db_manager: DatabaseManager) -> None:
        """Проверка существования таблицы."""
        # Системная таблица
        assert await db_manager.table_exists("pg_class")

        # Несуществующая таблица
        assert not await db_manager.table_exists("nonexistent_table_xyz")


pytest.mark.unit(__name__)

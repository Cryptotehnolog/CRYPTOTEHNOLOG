"""
Тесты для Database Manager (src/core/database.py).

Используют паттерн "фабрика создаёт соединение внутри теста":
- Каждое соединение создаётся в том же event loop, где выполняется тест
- Гарантирует отсутствие конфликтов event loops
"""

import pytest

from cryptotechnolog.core.database import DatabaseManager, get_database


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


@pytest.mark.db
class TestDatabaseManagerOperations:
    """Тесты операций с БД (используют db_connection_factory)."""

    @pytest.mark.asyncio
    async def test_connection_works(self, db_connection_factory) -> None:
        """Проверка что соединение работает."""
        conn = await db_connection_factory.create()
        try:
            result = await conn.fetchval("SELECT 1")
            assert result == 1
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_transaction_isolation(self, db_connection_factory) -> None:
        """Транзакция изолирует изменения."""
        conn = await db_connection_factory.create()
        try:
            async with conn.transaction():
                await conn.execute(
                    "CREATE TEMP TABLE test_isolation (id SERIAL PRIMARY KEY, value TEXT NOT NULL)"
                )
                await conn.execute("INSERT INTO test_isolation (value) VALUES ($1)", "test_value")
                row = await conn.fetchrow("SELECT value FROM test_isolation")
                assert row["value"] == "test_value"
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_fetch_returns_list(self, db_connection_factory) -> None:
        """Fetch возвращает список словарей."""
        conn = await db_connection_factory.create()
        try:
            rows = await conn.fetch("SELECT 1 as col1, 'test' as col2")
            assert len(rows) == 1
            assert rows[0]["col1"] == 1
            assert rows[0]["col2"] == "test"
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_fetchrow_returns_dict(self, db_connection_factory) -> None:
        """Fetchrow возвращает один словарь."""
        conn = await db_connection_factory.create()
        try:
            row = await conn.fetchrow("SELECT 1 as id, 'test' as name")
            assert row is not None
            assert row["id"] == 1
            assert row["name"] == "test"
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_fetchrow_returns_none(self, db_connection_factory) -> None:
        """Fetchrow возвращает None если нет строк."""
        conn = await db_connection_factory.create()
        try:
            row = await conn.fetchrow("SELECT 1 WHERE 1=0")
            assert row is None
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_fetchval(self, db_connection_factory) -> None:
        """Fetchval возвращает одно значение."""
        conn = await db_connection_factory.create()
        try:
            result = await conn.fetchval("SELECT COUNT(*)")
            assert isinstance(result, int)
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_execute_insert(self, db_connection_factory) -> None:
        """Execute для INSERT."""
        conn = await db_connection_factory.create()
        try:
            await conn.execute("CREATE TEMP TABLE test_execute (id SERIAL PRIMARY KEY, name TEXT)")
            result = await conn.execute("INSERT INTO test_execute (name) VALUES ($1)", "test_name")
            assert result == "INSERT 0 1"
            row = await conn.fetchrow("SELECT name FROM test_execute")
            assert row["name"] == "test_name"
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_execute_many(self, db_connection_factory) -> None:
        """Execute_many для массовой вставки."""
        conn = await db_connection_factory.create()
        try:
            await conn.execute("CREATE TEMP TABLE test_bulk (id SERIAL PRIMARY KEY, value TEXT)")
            args_list = [("value1",), ("value2",), ("value3",)]
            await conn.executemany("INSERT INTO test_bulk (value) VALUES ($1)", args_list)
            count = await conn.fetchval("SELECT COUNT(*) FROM test_bulk")
            assert count == 3
        finally:
            await conn.close()


@pytest.mark.db
class TestDatabaseManagerHighLevel:
    """Тесты высокоуровневых методов DatabaseManager."""

    @pytest.mark.asyncio
    async def test_fetch_with_db_manager(self, db_connection_factory) -> None:
        """Тест высокоуровневого fetch через DatabaseManager."""
        conn = await db_connection_factory.create()
        try:
            db = DatabaseManager()
            db._connection = conn
            db._connected = True

            rows = await db.fetch("SELECT 1 as num, 'hello' as text")

            assert len(rows) == 1
            assert rows[0]["num"] == 1
            assert rows[0]["text"] == "hello"
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_fetchrow_with_db_manager(self, db_connection_factory) -> None:
        """Тест высокоуровневого fetchrow через DatabaseManager."""
        conn = await db_connection_factory.create()
        try:
            db = DatabaseManager()
            db._connection = conn
            db._connected = True

            row = await db.fetchrow("SELECT 1 as id, 'test' as name")

            assert row is not None
            assert row["id"] == 1
            assert row["name"] == "test"
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_fetchval_with_db_manager(self, db_connection_factory) -> None:
        """Тест высокоуровневого fetchval через DatabaseManager."""
        conn = await db_connection_factory.create()
        try:
            db = DatabaseManager()
            db._connection = conn
            db._connected = True

            result = await db.fetchval("SELECT 42 as answer")
            assert result == 42
        finally:
            await conn.close()


@pytest.mark.db
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
    async def test_health_check_with_connection(self, db_connection_factory) -> None:
        """Health check с подключённым соединением."""
        conn = await db_connection_factory.create()
        try:
            db = DatabaseManager()
            db._connection = conn
            db._connected = True

            # Проверить что менеджер работает
            result = await db.fetchval("SELECT 1")
            assert result == 1

            health = await db.health_check()

            assert health["status"] == "healthy", f"Expected healthy, got {health}"
            assert health["connected"]
        finally:
            await conn.close()


@pytest.mark.db
class TestDatabaseManagerTableInfo:
    """Тесты получения информации о таблицах."""

    @pytest.mark.asyncio
    async def test_get_table_names(self, db_connection_factory) -> None:
        """Получение списка таблиц."""
        conn = await db_connection_factory.create()
        try:
            db = DatabaseManager()
            db._connection = conn
            db._connected = True

            tables = await db.get_table_names()

            assert isinstance(tables, list)
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_table_exists(self, db_connection_factory) -> None:
        """Проверка существования таблицы."""
        conn = await db_connection_factory.create()
        try:
            db = DatabaseManager()
            db._connection = conn
            db._connected = True

            # Проверить что менеджер работает
            result = await db.fetchval("SELECT 1")
            assert result == 1

            # Системная таблица pg_class - проверяем через pg_catalog
            exists = await db.table_exists("pg_class")
            assert exists is True, f"Expected True, got {exists}"

            # Несуществующая таблица
            assert not await db.table_exists("nonexistent_table_xyz")
        finally:
            await conn.close()


pytest.mark.unit(__name__)


class TestDatabaseManagerRedisAndCache:
    """Тесты для Redis кэша и методов без подключения к БД."""

    def test_set_redis(self) -> None:
        """Тест установки Redis клиента."""
        db = DatabaseManager()

        # Redis не установлен
        assert db.has_redis() is False

        # Устанавливаем мок Redis
        mock_redis = object()
        db.set_redis(mock_redis)

        # Теперь Redis установлен
        assert db.has_redis() is True

    @pytest.mark.asyncio
    async def test_is_healthy_without_connection(self) -> None:
        """Тест is_healthy без подключения."""
        db = DatabaseManager()

        # Без подключения - нездоров
        assert db.is_healthy() is False

    def test_is_healthy_with_connected_redis(self) -> None:
        """Тест is_healthy с подключённым Redis."""
        db = DatabaseManager()

        # Устанавливаем мок Redis
        mock_redis = object()
        db.set_redis(mock_redis)

        # Без подключения к БД всё ещё нездоров
        assert db.is_healthy() is False

    @pytest.mark.asyncio
    async def test_cache_operations(self) -> None:
        """Тест кэш операций без реального Redis."""
        db = DatabaseManager()

        # Кэш не работает без Redis - должен выбросить исключение
        with pytest.raises(RuntimeError, match="Redis"):
            await db.cache_get("test_key")

    def test_pool_property_not_connected(self) -> None:
        """Тест свойства pool без подключения."""
        db = DatabaseManager()

        # Пул не доступен без подключения
        assert db.pool is None

    def test_circuit_breaker_property(self) -> None:
        """Тест свойства circuit_breaker."""
        db = DatabaseManager()

        # Circuit breaker должен быть доступен
        cb = db.circuit_breaker
        assert cb is not None
        assert cb.name == "postgresql"


class TestDatabaseManagerCache:
    """Тесты для методов кэширования."""

    @pytest.mark.asyncio
    async def test_cache_set_and_get(self) -> None:
        """Тест установки и получения из кэша."""
        db = DatabaseManager()

        # Мок Redis с простым хранилищем
        class MockRedis:
            def __init__(self):
                self._data = {}

            async def get(self, key):
                return self._data.get(key)

            async def set(self, key, value, ttl=None):
                self._data[key] = value

            async def delete(self, key):
                if key in self._data:
                    del self._data[key]
                    return 1
                return 0

        mock_redis = MockRedis()
        db.set_redis(mock_redis)

        # Устанавливаем значение
        await db.cache_set("test_key", "test_value")

        # Получаем значение
        result = await db.cache_get("test_key")
        assert result == "test_value"

    @pytest.mark.asyncio
    async def test_cache_delete(self) -> None:
        """Тест удаления из кэша."""
        db = DatabaseManager()

        # Мок Redis
        class MockRedis:
            def __init__(self):
                self._data = {"key1": "value1"}

            async def get(self, key):
                return self._data.get(key)

            async def set(self, key, value, ex=None):
                self._data[key] = value

            async def delete(self, key):
                if key in self._data:
                    del self._data[key]
                    return 1
                return 0

        mock_redis = MockRedis()
        db.set_redis(mock_redis)

        # Удаляем значение
        result = await db.cache_delete("key1")
        assert result == 1

        # Значение удалено
        assert await db.cache_get("key1") is None

"""
Database Layer — PostgreSQL Manager с асинхронным подключением.

Использует asyncpg для высокопроизводительного асинхронного доступа к PostgreSQL.
Поддерживает:
- Connection pooling
- Динамическое создание пула под каждый event loop
- Prepared statements
- Контекстные менеджеры
- Redis кэширование
- Pub/Sub уведомления
- Circuit breaker для отказоустойчивости
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import hashlib
import json
from typing import Any, cast

import asyncpg

from cryptotechnolog.config import get_logger, get_settings
from cryptotechnolog.core.circuit_breaker import CircuitBreaker, CircuitBreakerError

logger = get_logger(__name__)

# Тип для Redis клиента
RedisClientType = Any  # redis.asyncio.Redis


# Глобальное хранилище пулов по event loop id
# Key: id(event_loop), Value: asyncpg.Pool
_pool_registry: dict[int, asyncpg.Pool] = {}
_registry_lock = asyncio.Lock()


class DatabaseManager:
    """
    Менеджер подключения к PostgreSQL.

    Обеспечивает:
    - Пул соединений с настраиваемыми параметрами
    - Динамическое создание пула под каждый event loop
    - Асинхронные операции
    - Транзакции с автоматическим rollback
    - Graceful shutdown
    - Circuit breaker для fault tolerance

    Особенности:
    - Пул создаётся лениво при первом обращении
    - Автоматическое пересоздание пула при смене event loop

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
        circuit_breaker_enabled: bool = True,
    ) -> None:
        """
        Инициализировать менеджер базы данных.

        Аргументы:
            min_size: Минимальный размер пула (по умолчанию из настроек)
            max_size: Максимальный размер пула (по умолчанию из настроек)
            circuit_breaker_enabled: Включить circuit breaker
        """
        settings = get_settings()

        self._min_size = min_size or settings.postgres_pool_min_size
        self._max_size = max_size or settings.postgres_pool_max_size
        self._url = settings.postgres_async_url

        self._pool: asyncpg.Pool | None = None
        self._connection: asyncpg.Connection | None = None
        self._connected = False
        self._redis: RedisClientType | None = None

        # ID event loop для отслеживания смены
        self._loop_id: int | None = None

        # Circuit breaker for fault tolerance
        self._circuit_breaker_enabled = circuit_breaker_enabled
        self._circuit_breaker = CircuitBreaker(
            name="postgresql",
            failure_threshold=5,
            recovery_timeout=30,
            success_threshold=2,
            excluded_exceptions=(asyncpg.InvalidCatalogNameError, asyncpg.InvalidPasswordError),
        )

        logger.info(
            "Инициализирован менеджер БД",
            min_size=self._min_size,
            max_size=self._max_size,
            circuit_breaker_enabled=circuit_breaker_enabled,
        )

    @property
    def is_connected(self) -> bool:
        """Проверить подключение к БД."""
        return self._connected and (self._pool is not None or self._connection is not None)

    @property
    def pool(self) -> asyncpg.Pool | None:
        """Получить пул соединений."""
        return self._pool

    @property
    def circuit_breaker(self) -> CircuitBreaker:
        """Получить circuit breaker."""
        return self._circuit_breaker

    def is_healthy(self) -> bool:
        """Проверить здоровье подключения (учитывая circuit breaker)."""
        if self._circuit_breaker_enabled and self._circuit_breaker.is_open:
            return False
        return self.is_connected

    def _get_current_loop_id(self) -> int:
        """
        Получить ID текущего event loop.

        Returns:
            ID текущего event loop.
        """
        try:
            loop = asyncio.get_running_loop()
            return id(loop)
        except RuntimeError:
            # Нет запущенного loop - используем 0 как идентификатор
            return 0

    async def _ensure_pool(self) -> asyncpg.Pool:
        """
        Обеспечить наличие пула для текущего event loop.

        Если пул не существует или создан в другом event loop,
        создаёт новый пул.

        Returns:
            Пул соединений для текущего event loop.

        Raises:
            CircuitBreakerError: Если circuit breaker открыт
        """
        current_loop_id = self._get_current_loop_id()

        # Проверяем circuit breaker
        if self._circuit_breaker_enabled and self._circuit_breaker.is_open:
            raise CircuitBreakerError(
                "Cannot get pool: circuit breaker is OPEN. Service is currently unavailable."
            )

        # Проверяем: нужен ли новый пул
        needs_new_pool = (
            self._pool is None or self._loop_id != current_loop_id or not self._connected
        )

        if needs_new_pool:
            # Закрываем старый пул если есть
            if self._pool is not None and self._loop_id != current_loop_id:
                logger.info(
                    "Закрытие пула БД из-за смены event loop",
                    old_loop=self._loop_id,
                    new_loop=current_loop_id,
                )
                try:
                    await self._pool.close()
                except Exception as e:
                    logger.warning("Ошибка закрытия пула", error=str(e))

            # Создаём новый пул
            logger.info(
                "Создание пула PostgreSQL",
                loop_id=current_loop_id,
                min_size=self._min_size,
                max_size=self._max_size,
            )

            self._pool = await asyncpg.create_pool(
                self._url,
                min_size=self._min_size,
                max_size=self._max_size,
                command_timeout=60,
            )
            self._loop_id = current_loop_id
            self._connected = True

            # Проверяем подключение
            async with self._pool.acquire() as conn:
                version = await conn.fetchval("SELECT version()")
                logger.info(
                    "Подключение к PostgreSQL установлено",
                    version=version[:50],
                    loop_id=current_loop_id,
                )

        return self._pool

    async def connect(self) -> None:
        """
        Подключиться к PostgreSQL и создать пул соединений.

        При вызове автоматически создаёт пул для текущего event loop.
        Если пул уже существует и loop не изменился - ничего не делает.

        Raises:
            RuntimeError: Если подключение уже установлено
            asyncpg.InvalidCatalogNameError: Если БД не существует
            asyncpg.InvalidPasswordError: Если неверный пароль
            CircuitBreakerError: Если circuit breaker открыт
        """
        current_loop_id = self._get_current_loop_id()

        # Если уже подключены в текущем loop - не делаем ничего
        if self._connected and self._pool is not None and self._loop_id == current_loop_id:
            logger.debug("Уже подключено к БД в текущем event loop", loop_id=current_loop_id)
            return

        # Создаём пул (метод сам обработает смену loop)
        await self._ensure_pool()
        logger.info("Подключение к PostgreSQL выполнено", loop_id=current_loop_id)

    async def disconnect(self) -> None:
        """Отключиться от PostgreSQL и закрыть пул."""
        if self._pool is not None:
            logger.info("Закрытие пула соединений PostgreSQL")
            await self._pool.close()
            self._pool = None
            self._connected = False
            self._loop_id = None
            logger.info("Отключение от PostgreSQL выполнено")

    async def close(self) -> None:
        """Совместимый alias для graceful shutdown orchestration."""
        await self.disconnect()

    @asynccontextmanager
    async def connection(self) -> AsyncIterator[asyncpg.Connection]:
        """
        Контекстный менеджер для получения соединения.

        Yields:
            asyncpg.Connection: Соединение с БД

        Пример:
            >>> async with db.connection() as conn:
            ...     await conn.fetch("SELECT 1")
        """
        # Автоматически создаём пул если его нет
        if self._pool is None:
            await self._ensure_pool()

        if self._connection is not None:
            # Одиночное соединение
            yield self._connection
        elif self._pool is not None:
            # Пул соединений
            async with self._pool.acquire() as conn:
                yield cast("asyncpg.Connection", conn)
        else:
            raise RuntimeError("Нет подключения к БД. Вызовите connect()")

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
        # Check circuit breaker state
        cb_state = (
            self._circuit_breaker.state.value if self._circuit_breaker_enabled else "disabled"
        )

        if not self.is_connected:
            return {
                "status": "unhealthy",
                "connected": False,
                "circuit_breaker": cb_state,
                "error": "Нет подключения к БД",
            }

        # If circuit is open, report degraded
        if self._circuit_breaker_enabled and self._circuit_breaker.is_open:
            return {
                "status": "degraded",
                "connected": True,
                "circuit_breaker": cb_state,
                "error": "Circuit breaker is OPEN - service degraded",
            }

        try:
            async with self.connection() as conn:
                # Простой запрос для проверки
                result = await conn.fetchval("SELECT 1")

                return {
                    "status": "healthy",
                    "connected": True,
                    "circuit_breaker": cb_state,
                    "pool_size": self._min_size if self._pool else 1,
                    "pool_max_size": self._max_size if self._pool else 1,
                    "test_query_result": result,
                }
        except Exception as e:
            return {
                "status": "unhealthy",
                "connected": False,
                "circuit_breaker": cb_state,
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
    SELECT 1 FROM pg_catalog.pg_class
    WHERE relname = $1
    AND relkind IN ('r', 'v', 'm', 'f')
) AS exists
"""
        result = await self.fetchval(query, table_name)
        return result is True

    # ==================== Redis Integration ====================

    def set_redis(self, redis_client: RedisClientType) -> None:
        """
        Установить Redis клиент для кэширования.

        Аргументы:
            redis_client: Redis клиент (redis.asyncio.Redis)
        """
        self._redis = redis_client
        logger.info("Redis клиент установлен для DatabaseManager")

    def has_redis(self) -> bool:
        """Проверить подключён ли Redis."""
        return self._redis is not None

    async def cache_get(self, key: str) -> str | None:
        """
        Получить значение из кэша.

        Аргументы:
            key: Ключ кэша

        Returns:
            Значение или None если не найдено
        """
        if self._redis is None:
            raise RuntimeError("Redis не подключён. Вызовите set_redis()")

        return cast("str | None", await self._redis.get(key))

    async def cache_set(
        self,
        key: str,
        value: str | int | float | bool,
        ttl: int | None = None,
    ) -> bool:
        """
        Установить значение в кэш.

        Аргументы:
            key: Ключ кэша
            value: Значение
            ttl: TTL в секундах (опционально)

        Returns:
            True если установлено
        """
        if self._redis is None:
            raise RuntimeError("Redis не подключён. Вызовите set_redis()")

        return cast("bool", await self._redis.set(key, str(value), ttl=ttl))

    async def cache_delete(self, key: str) -> int:
        """
        Удалить ключ из кэша.

        Аргументы:
            key: Ключ для удаления

        Returns:
            Количество удалённых ключей
        """
        if self._redis is None:
            raise RuntimeError("Redis не подключён. Вызовите set_redis()")

        return cast("int", await self._redis.delete(key))

    async def fetch_cached(
        self,
        query: str,
        *args: Any,
        ttl: int = 60,
        cache_key: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Выполнить запрос с кэшированием результата.

        Сначала проверяет кэш, если есть — возвращает из кэша.
        Если нет — выполняет запрос и сохраняет результат в кэш.

        Аргументы:
            query: SQL запрос
            *args: Аргументы запроса
            ttl: TTL кэша в секундах (по умолчанию 60)
            cache_key: Кастомный ключ кэша (по умолчанию хэш запроса)

        Returns:
            Список словарей с результатами

        Пример:
            >>> # Кэшировать результат на 5 минут
            >>> rows = await db.fetch_cached("SELECT * FROM symbols", ttl=300)
            >>> # С кастомным ключом
            >>> rows = await db.fetch_cached(
            ...     "SELECT * FROM symbols", ttl=60, cache_key="all_symbols"
            ... )
        """
        if self._redis is None:
            # Без Redis — просто выполняем запрос
            return await self.fetch(query, *args)

        # Генерируем ключ кэша
        if cache_key is None:
            # Хэшируем запрос + аргументы
            key_data = json.dumps({"query": query, "args": args}, sort_keys=True)
            cache_key = f"db_cache:{hashlib.md5(key_data.encode()).hexdigest()}"

        # Пробуем получить из кэша
        cached = await self._redis.get(cache_key)
        if cached is not None:
            logger.debug("Кэш найден", key=cache_key)
            return cast("list[dict[str, Any]]", json.loads(cached))

        # Выполняем запрос
        rows = await self.fetch(query, *args)

        # Сохраняем в кэш
        if rows:
            await self._redis.set(cache_key, json.dumps(rows), ttl=ttl)
            logger.debug("Результат сохранён в кэш", key=cache_key, ttl=ttl)

        return rows

    async def invalidate_cache(self, pattern: str | None = None) -> int:
        """
        Инвалидировать кэш по шаблону.

        Аргументы:
            pattern: Шаблон ключей для удаления (например "db_cache:*").
                    Если None — удаляет все ключи с префиксом "db_cache:"

        Returns:
            Количество удалённых ключей
        """
        if self._redis is None:
            raise RuntimeError("Redis не подключён. Вызовите set_redis()")

        pattern = pattern or "db_cache:*"
        keys = await self._redis.keys(pattern)

        if keys:
            count = cast("int", await self._redis.delete(*keys))
            logger.info("Кэш инвалидирован", pattern=pattern, deleted=count)
            return count

        return 0

    async def publish(self, channel: str, message: str | int | float | bool) -> int:
        """
        Опубликовать сообщение в Redis канал.

        Используется для межкомпонентной коммуникации.

        Аргументы:
            channel: Имя канала
            message: Сообщение

        Returns:
            Количество подписчиков

        Пример:
            >>> # Уведомить о новом ордере
            >>> await db.publish("orders", '{"event": "new", "order_id": 123}')
        """
        if self._redis is None:
            raise RuntimeError("Redis не подключён. Вызовите set_redis()")

        return cast("int", await self._redis.publish(channel, str(message)))


# Глобальный экземпляр
_db_manager: DatabaseManager | None = None


async def get_db_pool() -> asyncpg.Pool:
    """
    Получить пул соединений с БД (для совместимости).

    Returns:
        Пул соединений asyncpg

    Raises:
        RuntimeError: Если не удалось подключиться к БД
    """
    db = get_database()
    if db.pool is None:
        await db.connect()
    if db.pool is None:
        raise RuntimeError("Не удалось получить пул соединений с БД")
    return db.pool


async def init_db_pool() -> asyncpg.Pool:
    """
    Инициализировать пул соединений (для совместимости).

    Returns:
        Пул соединений asyncpg

    Raises:
        RuntimeError: Если не удалось подключиться к БД
    """
    db = get_database()
    if not db.is_connected:
        await db.connect()
    if db.pool is None:
        raise RuntimeError("Не удалось инициализировать пул соединений")
    return db.pool


async def close_db_pool() -> None:
    """Закрыть пул соединений (для совместимости)."""
    await close_database()


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


def set_database(db_manager: DatabaseManager) -> None:
    """Явно установить глобальный экземпляр DatabaseManager."""
    global _db_manager  # noqa: PLW0603
    _db_manager = db_manager


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

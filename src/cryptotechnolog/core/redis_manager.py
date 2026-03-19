"""
Redis Manager — асинхронный менеджер подключения к Redis.

Использует redis-py (async) для высокопроизводительного асинхронного доступа к Redis.
Поддерживает:
- Connection pooling
- Основные операции (get, set, delete, exists)
- TTL (time-to-live)
- Pub/Sub
- Streams
- Circuit breaker для отказоустойчивости
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, cast

import redis.asyncio as redis

from cryptotechnolog.config import get_logger, get_settings
from cryptotechnolog.core.circuit_breaker import CircuitBreaker

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from redis.asyncio import Redis
    from redis.asyncio.client import Pipeline, PubSub

logger = get_logger(__name__)


class TypedRedisClient:
    """
    Типобезопасная обёртка над redis.asyncio.Redis.

    Скрывает проблемы с типами библиотеки redis-py, которая возвращает
    Union[Awaitable[T], T] вместо Awaitable[T]. Использует cast() для
    корректного сужения типов.

    Это внутренняя обёртка, используемая RedisManager.
    """

    def __init__(self, client: Redis) -> None:
        """Инициализировать обёртку с клиентом Redis."""
        self._client = client

    # ==================== Основные операции ====================

    async def set_value(
        self,
        key: str,
        value: str,
        ex: int | None = None,
        nx: bool = False,
        xx: bool = False,
    ) -> bool | None:
        """Установить значение ключа."""
        options: dict[str, Any] = {}
        if nx:
            options["nx"] = True
        if xx:
            options["xx"] = True
        if ex is not None:
            options["ex"] = ex

        result = cast("bool | None", await self._client.set(key, value, **options))
        return result

    async def get(self, key: str) -> str | None:
        """Получить значение по ключу."""
        result = cast("str | None", await self._client.get(key))
        return result

    async def delete(self, *keys: str) -> int:
        """Удалить ключи."""
        result = cast("int", await self._client.delete(*keys))
        return result

    async def exists(self, *keys: str) -> int:
        """Проверить существование ключей."""
        result = cast("int", await self._client.exists(*keys))
        return result

    async def expire(self, key: str, time: int) -> bool:
        """Установить TTL для ключа."""
        result = cast("bool", await self._client.expire(key, time))
        return result

    async def ttl(self, key: str) -> int:
        """Получить TTL ключа."""
        result = cast("int", await self._client.ttl(key))
        return result

    async def incrby(self, key: str, amount: int) -> int:
        """Увеличить значение ключа."""
        result = cast("int", await self._client.incrby(key, amount))
        return result

    async def decrby(self, key: str, amount: int) -> int:
        """Уменьшить значение ключа."""
        result = cast("int", await self._client.decrby(key, amount))
        return result

    # ==================== Хеш-операции ====================

    async def hset(self, key: str, field: str, value: str) -> int:
        """Установить значение поля в хеше."""
        result = cast("int", await self._client.hset(key, field, value))
        return result

    async def hget(self, key: str, field: str) -> str | None:
        """Получить значение поля из хеша."""
        result = cast("str | None", await self._client.hget(key, field))
        return result

    async def hgetall(self, key: str) -> dict[str, str]:
        """Получить все поля и значения хеша."""
        result = cast("dict[str, str]", await self._client.hgetall(key))
        return result

    async def hdel(self, key: str, *fields: str) -> int:
        """Удалить поля из хеша."""
        result = cast("int", await self._client.hdel(key, *fields))
        return result

    # ==================== Списки (List) ====================

    async def lpush(self, key: str, *values: str) -> int:
        """Добавить значения в начало списка."""
        result = cast("int", await self._client.lpush(key, *values))
        return result

    async def rpush(self, key: str, *values: str) -> int:
        """Добавить значения в конец списка."""
        result = cast("int", await self._client.rpush(key, *values))
        return result

    async def lpop(self, key: str) -> str | None:
        """Получить и удалить первый элемент списка."""
        result = cast("str | None", await self._client.lpop(key))
        return result

    async def rpop(self, key: str) -> str | None:
        """Получить и удалить последний элемент списка."""
        result = cast("str | None", await self._client.rpop(key))
        return result

    async def lrange(self, key: str, start: int, end: int) -> list[str]:
        """Получить диапазон элементов списка."""
        result = cast("list[str]", await self._client.lrange(key, start, end))
        return result

    async def llen(self, key: str) -> int:
        """Получить длину списка."""
        result = cast("int", await self._client.llen(key))
        return result

    # ==================== Множества (Set) ====================

    async def sadd(self, key: str, *members: str) -> int:
        """Добавить элементы в множество."""
        result = cast("int", await self._client.sadd(key, *members))
        return result

    async def smembers(self, key: str) -> set[str]:
        """Получить все элементы множества."""
        result = cast("set[str]", await self._client.smembers(key))
        return result

    async def sismember(self, key: str, member: str) -> int:
        """Проверить членство в множестве."""
        result = cast("int", await self._client.sismember(key, member))
        return result

    async def srem(self, key: str, *members: str) -> int:
        """Удалить элементы из множества."""
        result = cast("int", await self._client.srem(key, *members))
        return result

    # ==================== Pub/Sub ====================

    async def publish(self, channel: str, message: str) -> int:
        """Опубликовать сообщение в канал."""
        result = cast("int", await self._client.publish(channel, message))
        return result

    def pubsub(self) -> PubSub:
        """Создать PubSub объект."""
        return self._client.pubsub()

    # ==================== Streams ====================

    async def xadd(
        self,
        stream: str,
        fields: dict[str, str],
        maxlen: int | None = None,
        approximate: bool = True,
    ) -> str:
        """Добавить сообщение в stream."""
        options: dict[str, Any] = {}
        if maxlen is not None:
            options["maxlen"] = maxlen
            if approximate:
                options["~"] = "*"

        result = cast("str", await self._client.xadd(stream, fields, **options))
        return result

    async def xread(
        self,
        streams: dict[str, str],
        count: int | None = None,
        block: int | None = None,
    ) -> list[list[tuple[str, dict[str, str]]]]:
        """Прочитать сообщения из stream."""
        result = cast(
            "list[list[tuple[str, dict[str, str]]]]",
            await self._client.xread(streams, count=count, block=block),
        )
        return result

    async def xrange(
        self,
        stream: str,
        min: str,
        max: str,
        count: int | None = None,
    ) -> list[tuple[str, dict[str, str]]]:
        """Прочитать диапазон сообщений из stream."""
        result = cast(
            "list[tuple[str, dict[str, str]]]",
            await self._client.xrange(stream, min=min, max=max, count=count),
        )
        return result

    async def xlen(self, stream: str) -> int:
        """Получить длину stream."""
        result = cast("int", await self._client.xlen(stream))
        return result

    async def xdel(self, stream: str, *ids: str) -> int:
        """Удалить сообщения из stream."""
        result = cast("int", await self._client.xdel(stream, *ids))
        return result

    # ==================== Pipeline ====================

    def pipeline(self) -> Pipeline:
        """Создать pipeline."""
        return self._client.pipeline()

    # ==================== Утилиты ====================

    async def keys(self, pattern: str) -> list[str]:
        """Найти ключи по шаблону."""
        result = cast("list[str]", await self._client.keys(pattern))
        return result

    async def flushdb(self) -> bool:
        """Очистить базу данных."""
        result = cast("bool", await self._client.flushdb())
        return result

    async def info(self, section: str | None = None) -> dict[str, Any]:
        """Получить информацию о Redis."""
        result = cast("dict[str, Any]", await self._client.info(section))
        return result

    async def ping(self) -> bool:
        """Проверить подключение."""
        result = cast("bool", await self._client.ping())
        return result


class RedisManager:
    """
    Менеджер подключения к Redis.

    Обеспечивает:
    - Пул соединений с настраиваемыми параметрами
    - Асинхронные операции
    - Pub/Sub для межкомпонентной коммуникации
    - Streams для очередей сообщений
    - Graceful shutdown

    Пример:
        >>> redis_mgr = RedisManager()
        >>> await redis_mgr.connect()
        >>> await redis_mgr.set("key", "value", ttl=60)
        >>> value = await redis_mgr.get("key")
        >>> await redis_mgr.disconnect()
    """

    def __init__(
        self,
        max_connections: int | None = None,
        socket_timeout: int | None = None,
        circuit_breaker_enabled: bool = True,
    ) -> None:
        """
        Инициализировать менеджер Redis.

        Аргументы:
            max_connections: Максимальное количество соединений в пуле
            socket_timeout: Таймаут сокета в секундах
            circuit_breaker_enabled: Включить circuit breaker
        """
        settings = get_settings()

        self._max_connections = max_connections or settings.redis_pool_max_connections
        self._socket_timeout = socket_timeout or settings.redis_pool_socket_timeout
        self._url = settings.redis_url

        self._redis: Redis | None = None
        self._typed_client: TypedRedisClient | None = None
        self._connected = False

        # Circuit breaker for fault tolerance
        self._circuit_breaker_enabled = circuit_breaker_enabled
        self._circuit_breaker = CircuitBreaker(
            name="redis",
            failure_threshold=5,
            recovery_timeout=30,
            success_threshold=2,
            excluded_exceptions=(redis.AuthenticationError,),
        )

        logger.info(
            "Инициализирован менеджер Redis",
            max_connections=self._max_connections,
            url=self._url.split("@")[-1] if "@" in self._url else self._url,
            circuit_breaker_enabled=circuit_breaker_enabled,
        )

    @property
    def is_connected(self) -> bool:
        """Проверить подключение к Redis."""
        return self._connected and self._redis is not None

    @property
    def redis(self) -> Redis | None:
        """Получить экземпляр Redis."""
        return self._redis

    @property
    def circuit_breaker(self) -> CircuitBreaker:
        """Получить circuit breaker."""
        return self._circuit_breaker

    def is_healthy(self) -> bool:
        """Проверить здоровье подключения (учитывая circuit breaker)."""
        if self._circuit_breaker_enabled and self._circuit_breaker.is_open:
            return False
        return self.is_connected

    def _require_typed_client(self) -> TypedRedisClient:
        """Получить типизированный клиент."""
        if self._typed_client is None:
            msg = "Нет подключения к Redis. Вызовите connect()"
            raise RuntimeError(msg)
        return self._typed_client

    async def connect(self) -> None:
        """
        Подключиться к Redis.

        Raises:
            RuntimeError: Если подключение уже установлено
            redis.ConnectionError: Если не удалось подключиться
        """
        if self._connected and self._redis is not None:
            msg = "Уже подключено к Redis"
            raise RuntimeError(msg)

        logger.info(
            "Подключение к Redis", url=self._url.split("@")[-1] if "@" in self._url else self._url
        )

        try:
            client = redis.from_url(
                self._url,
                max_connections=self._max_connections,
                socket_timeout=self._socket_timeout,
                socket_connect_timeout=self._socket_timeout,
                decode_responses=True,
            )

            # Проверить подключение
            await client.ping()
            self._redis = client
            self._typed_client = TypedRedisClient(client)
            self._connected = True

            info = await client.info("server")
            redis_version = info.get("redis_version", "unknown")
            logger.info("Подключение к Redis установлено", version=redis_version)

        except Exception as e:
            logger.error("Ошибка подключения к Redis", error=str(e))
            self._redis = None
            self._typed_client = None
            self._connected = False
            raise

    async def disconnect(self) -> None:
        """Отключиться от Redis и закрыть пул."""
        if self._redis is not None:
            logger.info("Закрытие соединений Redis")
            await self._redis.close()
            self._redis = None
            self._typed_client = None
            self._connected = False
            logger.info("Отключение от Redis выполнено")

    async def close(self) -> None:
        """Совместимый alias для graceful shutdown orchestration."""
        await self.disconnect()

    async def health_check(self) -> dict[str, Any]:
        """
        Проверить здоровье подключения к Redis.

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
                "error": "Нет подключения к Redis",
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
            client = self._require_typed_client()
            await client.ping()

            info = await client.info("stats")
            return {
                "status": "healthy",
                "connected": True,
                "circuit_breaker": cb_state,
                "max_connections": self._max_connections,
                "total_commands_processed": info.get("total_commands_processed", 0),
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "connected": False,
                "circuit_breaker": cb_state,
                "error": str(e),
            }

    # ==================== Основные операции ====================

    async def set_value(
        self,
        key: str,
        value: str | int | float | bool,
        ttl: int | None = None,
        nx: bool = False,
        xx: bool = False,
    ) -> bool:
        """
        Установить значение ключа.

        Аргументы:
            key: Имя ключа
            value: Значение для установки
            ttl: Time-to-live в секундах (опционально)
            nx: Установить только если ключ не существует
            xx: Установить только если ключ существует

        Returns:
            True если значение установлено, иначе False
        """
        client = self._require_typed_client()
        result = await client.set_value(key, str(value), ex=ttl, nx=nx, xx=xx)
        return result is True

    async def get(self, key: str) -> str | None:
        """Получить значение по ключу."""
        client = self._require_typed_client()
        return await client.get(key)

    async def delete(self, *keys: str) -> int:
        """Удалить ключи."""
        client = self._require_typed_client()
        if not keys:
            return 0
        return await client.delete(*keys)

    async def exists(self, *keys: str) -> int:
        """Проверить существование ключей."""
        client = self._require_typed_client()
        if not keys:
            return 0
        return await client.exists(*keys)

    async def expire(self, key: str, ttl: int) -> bool:
        """Установить TTL для ключа."""
        client = self._require_typed_client()
        return await client.expire(key, ttl)

    async def ttl(self, key: str) -> int:
        """Получить TTL ключа."""
        client = self._require_typed_client()
        return await client.ttl(key)

    async def incr(self, key: str, amount: int = 1) -> int:
        """Увеличить значение ключа."""
        client = self._require_typed_client()
        return await client.incrby(key, amount)

    async def decr(self, key: str, amount: int = 1) -> int:
        """Уменьшить значение ключа."""
        client = self._require_typed_client()
        return await client.decrby(key, amount)

    # ==================== Хеш-операции ====================

    async def hset(
        self,
        key: str,
        field: str,
        value: str | int | float | bool,
    ) -> int:
        """Установить значение поля в хеше."""
        client = self._require_typed_client()
        return await client.hset(key, field, str(value))

    async def hget(self, key: str, field: str) -> str | None:
        """Получить значение поля из хеша."""
        client = self._require_typed_client()
        return await client.hget(key, field)

    async def hgetall(self, key: str) -> dict[str, str]:
        """Получить все поля и значения хеша."""
        client = self._require_typed_client()
        return await client.hgetall(key)

    async def hdel(self, key: str, *fields: str) -> int:
        """Удалить поля из хеша."""
        client = self._require_typed_client()
        if not fields:
            return 0
        return await client.hdel(key, *fields)

    # ==================== Списки (List) ====================

    async def lpush(self, key: str, *values: str) -> int:
        """Добавить значения в начало списка."""
        client = self._require_typed_client()
        return await client.lpush(key, *values)

    async def rpush(self, key: str, *values: str) -> int:
        """Добавить значения в конец списка."""
        client = self._require_typed_client()
        return await client.rpush(key, *values)

    async def lpop(self, key: str) -> str | None:
        """Получить и удалить первый элемент списка."""
        client = self._require_typed_client()
        return await client.lpop(key)

    async def rpop(self, key: str) -> str | None:
        """Получить и удалить последний элемент списка."""
        client = self._require_typed_client()
        return await client.rpop(key)

    async def lrange(self, key: str, start: int = 0, end: int = -1) -> list[str]:
        """Получить диапазон элементов списка."""
        client = self._require_typed_client()
        return await client.lrange(key, start, end)

    async def llen(self, key: str) -> int:
        """Получить длину списка."""
        client = self._require_typed_client()
        return await client.llen(key)

    # ==================== Множества (Set) ====================

    async def sadd(self, key: str, *members: str) -> int:
        """Добавить элементы в множество."""
        client = self._require_typed_client()
        return await client.sadd(key, *members)

    async def smembers(self, key: str) -> set[str]:
        """Получить все элементы множества."""
        client = self._require_typed_client()
        return await client.smembers(key)

    async def sismember(self, key: str, member: str) -> bool:
        """Проверить членство в множестве."""
        client = self._require_typed_client()
        result = await client.sismember(key, member)
        return result == 1

    async def srem(self, key: str, *members: str) -> int:
        """Удалить элементы из множества."""
        client = self._require_typed_client()
        if not members:
            return 0
        return await client.srem(key, *members)

    # ==================== Pub/Sub ====================

    @asynccontextmanager
    async def pubsub(self) -> AsyncIterator[PubSub]:
        """Контекстный менеджер для Pub/Sub."""
        client = self._require_typed_client()
        pubsub = client.pubsub()
        try:
            yield pubsub
        finally:
            await pubsub.close()

    async def publish(self, channel: str, message: str | int | float | bool) -> int:
        """Опубликовать сообщение в канал."""
        client = self._require_typed_client()
        return await client.publish(channel, str(message))

    async def subscribe(self, *channels: str) -> PubSub:
        """Подписаться на каналы."""
        client = self._require_typed_client()
        pubsub = client.pubsub()
        await pubsub.subscribe(*channels)
        return pubsub

    # ==================== Streams ====================

    async def xadd(
        self,
        stream: str,
        fields: dict[str, str],
        maxlen: int | None = None,
        approximate: bool = True,
    ) -> str:
        """Добавить сообщение в stream."""
        client = self._require_typed_client()
        return await client.xadd(stream, fields, maxlen=maxlen, approximate=approximate)

    async def xread(
        self,
        streams: dict[str, str],
        count: int | None = None,
        block: int | None = None,
    ) -> list[list[tuple[str, dict[str, str]]]]:
        """Прочитать сообщения из stream."""
        client = self._require_typed_client()
        return await client.xread(streams, count=count, block=block)

    async def xrange(
        self,
        stream: str,
        start: str = "-",
        end: str = "+",
        count: int | None = None,
    ) -> list[tuple[str, dict[str, str]]]:
        """Прочитать диапазон сообщений из stream."""
        client = self._require_typed_client()
        return await client.xrange(stream, start, end, count=count)

    async def xlen(self, stream: str) -> int:
        """Получить длину stream."""
        client = self._require_typed_client()
        return await client.xlen(stream)

    async def xdel(self, stream: str, *ids: str) -> int:
        """Удалить сообщения из stream."""
        client = self._require_typed_client()
        if not ids:
            return 0
        return await client.xdel(stream, *ids)

    # ==================== Pipeline ====================

    async def pipeline(self) -> Pipeline:
        """Создать pipeline."""
        client = self._require_typed_client()
        return client.pipeline()

    # ==================== Утилиты ====================

    async def keys(self, pattern: str) -> list[str]:
        """Найти ключи по шаблону."""
        client = self._require_typed_client()
        return await client.keys(pattern)

    async def flushdb(self) -> bool:
        """Очистить базу данных."""
        client = self._require_typed_client()
        logger.warning("Очистка базы данных Redis")
        return await client.flushdb()

    async def info(self, section: str | None = None) -> dict[str, Any]:
        """Получить информацию о Redis."""
        client = self._require_typed_client()
        return await client.info(section)


# Глобальный экземпляр
_redis_manager: RedisManager | None = None


def get_redis() -> RedisManager:
    """Получить глобальный экземпляр RedisManager."""
    global _redis_manager  # noqa: PLW0603
    if _redis_manager is None:
        _redis_manager = RedisManager()
    return _redis_manager


def set_redis_manager(redis_manager: RedisManager) -> None:
    """Явно установить глобальный экземпляр RedisManager."""
    global _redis_manager  # noqa: PLW0603
    _redis_manager = redis_manager


async def init_redis() -> RedisManager:
    """Инициализировать подключение к Redis."""
    redis_mgr = get_redis()
    await redis_mgr.connect()
    return redis_mgr


async def close_redis() -> None:
    """Закрыть подключение к Redis."""
    global _redis_manager  # noqa: PLW0603
    if _redis_manager is not None:
        await _redis_manager.disconnect()
        _redis_manager = None

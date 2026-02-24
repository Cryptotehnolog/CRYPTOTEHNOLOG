"""
Redis Manager — асинхронный менеджер подключения к Redis.

Использует redis-py (async) для высокопроизводительного асинхронного доступа к Redis.
Поддерживает:
- Connection pooling
- Основные операции (get, set, delete, exists)
- TTL (time-to-live)
- Pub/Sub
- Streams
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Set, cast

import redis.asyncio as redis
from redis.asyncio import Redis
from redis.asyncio.client import PubSub, Pipeline

from cryptotechnolog.config import get_logger, get_settings

logger = get_logger(__name__)


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
    ) -> None:
        """
        Инициализировать менеджер Redis.

        Аргументы:
            max_connections: Максимальное количество соединений в пуле
            socket_timeout: Таймаут сокета в секундах
        """
        settings = get_settings()

        self._max_connections = max_connections or settings.redis_pool_max_connections
        self._socket_timeout = socket_timeout or settings.redis_pool_socket_timeout
        self._url = settings.redis_url

        self._redis: Redis | None = None
        self._connected = False

        logger.info(
            "Инициализирован менеджер Redis",
            max_connections=self._max_connections,
            url=self._url.split("@")[-1] if "@" in self._url else self._url,
        )

    @property
    def is_connected(self) -> bool:
        """Проверить подключение к Redis."""
        return self._connected and self._redis is not None

    @property
    def redis(self) -> Redis | None:
        """Получить экземпляр Redis."""
        return self._redis

    async def connect(self) -> None:
        """
        Подключиться к Redis.

        Raises:
            RuntimeError: Если подключение уже установлено
            redis.ConnectionError: Если не удалось подключиться
        """
        if self._connected and self._redis is not None:
            raise RuntimeError("Уже подключено к Redis")

        logger.info("Подключение к Redis", url=self._url.split("@")[-1] if "@" in self._url else self._url)

        try:
            self._redis = redis.from_url(
                self._url,
                max_connections=self._max_connections,
                socket_timeout=self._socket_timeout,
                socket_connect_timeout=self._socket_timeout,
                decode_responses=True,
            )

            # Проверить подключение
            await self._redis.ping()
            self._connected = True

            info = await self._redis.info("server")
            redis_version = info.get("redis_version", "unknown")
            logger.info("Подключение к Redis установлено", version=redis_version)

        except Exception as e:
            logger.error("Ошибка подключения к Redis", error=str(e))
            self._redis = None
            self._connected = False
            raise

    async def disconnect(self) -> None:
        """Отключиться от Redis и закрыть пул."""
        if self._redis is not None:
            logger.info("Закрытие соединений Redis")
            await self._redis.close()
            self._redis = None
            self._connected = False
            logger.info("Отключение от Redis выполнено")

    async def health_check(self) -> dict[str, Any]:
        """
        Проверить здоровье подключения к Redis.

        Returns:
            Словарь с статусом проверки
        """
        if not self.is_connected:
            return {
                "status": "unhealthy",
                "connected": False,
                "error": "Нет подключения к Redis",
            }

        try:
            # Простой запрос для проверки
            await self._redis.ping()

            info = await self._redis.info("stats")
            return {
                "status": "healthy",
                "connected": True,
                "max_connections": self._max_connections,
                "total_commands_processed": info.get("total_commands_processed", 0),
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "connected": False,
                "error": str(e),
            }

    # ==================== Основные операции ====================

    async def set(
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
            nx: Установить только если ключ не существует (nx = "only if not exists")
            xx: Установить только если ключ существует (xx = "only if exists")

        Returns:
            True если значение установлено, иначе False

        Пример:
            >>> await redis_mgr.set("user:1", "Alice", ttl=3600)
            >>> await redis_mgr.set("lock", "1", nx=True)  # только если не существует
        """
        if self._redis is None:
            raise RuntimeError("Нет подключения к Redis. Вызовите connect()")

        options: dict[str, Any] = {}
        if nx:
            options["nx"] = True
        if xx:
            options["xx"] = True
        if ttl is not None:
            options["ex"] = ttl

        result = await self._redis.set(key, str(value), **options)
        return result is True

    async def get(self, key: str) -> str | None:
        """
        Получить значение по ключу.

        Аргументы:
            key: Имя ключа

        Returns:
            Значение ключа или None если ключ не существует

        Пример:
            >>> value = await redis_mgr.get("user:1")
        """
        if self._redis is None:
            raise RuntimeError("Нет подключения к Redis. Вызовите connect()")

        return await self._redis.get(key)

    async def delete(self, *keys: str) -> int:
        """
        Удалить один или несколько ключей.

        Аргументы:
            *keys: Имена ключей для удаления

        Returns:
            Количество удалённых ключей

        Пример:
            >>> deleted = await redis_mgr.delete("key1", "key2", "key3")
        """
        if self._redis is None:
            raise RuntimeError("Нет подключения к Redis. Вызовите connect()")

        if not keys:
            return 0

        return await self._redis.delete(*keys)

    async def exists(self, *keys: str) -> int:
        """
        Проверить существование ключей.

        Аргументы:
            *keys: Имена ключей для проверки

        Returns:
            Количество существующих ключей

        Пример:
            >>> count = await redis_mgr.exists("key1", "key2")
        """
        if self._redis is None:
            raise RuntimeError("Нет подключения к Redis. Вызовите connect()")

        if not keys:
            return 0

        return await self._redis.exists(*keys)

    async def expire(self, key: str, ttl: int) -> bool:
        """
        Установить TTL для ключа.

        Аргументы:
            key: Имя ключа
            ttl: TTL в секундах

        Returns:
            True если TTL установлен, иначе False

        Пример:
            >>> await redis_mgr.expire("key", 60)  # истечёт через 60 секунд
        """
        if self._redis is None:
            raise RuntimeError("Нет подключения к Redis. Вызовите connect()")

        return await self._redis.expire(key, ttl)

    async def ttl(self, key: str) -> int:
        """
        Получить TTL ключа.

        Аргументы:
            key: Имя ключа

        Returns:
            TTL в секундах (-1 если нет TTL, -2 если ключ не существует)

        Пример:
            >>> ttl = await redis_mgr.ttl("key")
        """
        if self._redis is None:
            raise RuntimeError("Нет подключения к Redis. Вызовите connect()")

        return await self._redis.ttl(key)

    async def incr(self, key: str, amount: int = 1) -> int:
        """
        Увеличить значение ключа на amount.

        Аргументы:
            key: Имя ключа
            amount: Значение для увеличения (по умолчанию 1)

        Returns:
            Новое значение ключа

        Пример:
            >>> new_value = await redis_mgr.incr("counter")
            >>> new_value = await redis_mgr.incr("counter", 10)
        """
        if self._redis is None:
            raise RuntimeError("Нет подключения к Redis. Вызовите connect()")

        return await self._redis.incrby(key, amount)

    async def decr(self, key: str, amount: int = 1) -> int:
        """
        Уменьшить значение ключа на amount.

        Аргументы:
            key: Имя ключа
            amount: Значение для уменьшения (по умолчанию 1)

        Returns:
            Новое значение ключа

        Пример:
            >>> new_value = await redis_mgr.decr("counter")
        """
        if self._redis is None:
            raise RuntimeError("Нет подключения к Redis. Вызовите connect()")

        return await self._redis.decrby(key, amount)

    # ==================== Хеш-операции ====================

    async def hset(
        self,
        key: str,
        field: str,
        value: str | int | float | bool,
    ) -> int:
        """
        Установить значение поля в хеше.

        Аргументы:
            key: Имя ключа
            field: Имя поля
            value: Значение поля

        Returns:
            1 если установлено новое поле, 0 если поле обновлено

        Пример:
            >>> await redis_mgr.hset("user:1", "name", "Alice")
        """
        if self._redis is None:
            raise RuntimeError("Нет подключения к Redis. Вызовите connect()")

        return await self._redis.hset(key, field, str(value))

    async def hget(self, key: str, field: str) -> str | None:
        """
        Получить значение поля из хеша.

        Аргументы:
            key: Имя ключа
            field: Имя поля

        Returns:
            Значение поля или None

        Пример:
            >>> name = await redis_mgr.hget("user:1", "name")
        """
        if self._redis is None:
            raise RuntimeError("Нет подключения к Redis. Вызовите connect()")

        return await self._redis.hget(key, field)

    async def hgetall(self, key: str) -> dict[str, str]:
        """
        Получить все поля и значения хеша.

        Аргументы:
            key: Имя ключа

        Returns:
            Словарь всех полей и значений

        Пример:
            >>> user_data = await redis_mgr.hgetall("user:1")
        """
        if self._redis is None:
            raise RuntimeError("Нет подключения к Redis. Вызовите connect()")

        return await self._redis.hgetall(key)

    async def hdel(self, key: str, *fields: str) -> int:
        """
        Удалить поля из хеша.

        Аргументы:
            key: Имя ключа
            *fields: Имена полей для удаления

        Returns:
            Количество удалённых полей

        Пример:
            >>> await redis_mgr.hdel("user:1", "name", "email")
        """
        if self._redis is None:
            raise RuntimeError("Нет подключения к Redis. Вызовите connect()")

        if not fields:
            return 0

        return await self._redis.hdel(key, *fields)

    # ==================== Списки (List) ====================

    async def lpush(self, key: str, *values: str) -> int:
        """
        Добавить значения в начало списка.

        Аргументы:
            key: Имя ключа
            *values: Значения для добавления

        Returns:
            Длина списка после добавления

        Пример:
            >>> await redis_mgr.lpush("queue", "item1", "item2")
        """
        if self._redis is None:
            raise RuntimeError("Нет подключения к Redis. Вызовите connect()")

        return await self._redis.lpush(key, *values)

    async def rpush(self, key: str, *values: str) -> int:
        """
        Добавить значения в конец списка.

        Аргументы:
            key: Имя ключа
            *values: Значения для добавления

        Returns:
            Длина списка после добавления

        Пример:
            >>> await redis_mgr.rpush("queue", "item1", "item2")
        """
        if self._redis is None:
            raise RuntimeError("Нет подключения к Redis. Вызовите connect()")

        return await self._redis.rpush(key, *values)

    async def lpop(self, key: str) -> str | None:
        """
        Получить и удалить первый элемент списка.

        Аргументы:
            key: Имя ключа

        Returns:
            Значение первого элемента или None

        Пример:
            >>> item = await redis_mgr.lpop("queue")
        """
        if self._redis is None:
            raise RuntimeError("Нет подключения к Redis. Вызовите connect()")

        result = await self._redis.lpop(key)
        return cast(str | None, result)

    async def rpop(self, key: str) -> str | None:
        """
        Получить и удалить последний элемент списка.

        Аргументы:
            key: Имя ключа

        Returns:
            Значение последнего элемента или None

        Пример:
            >>> item = await redis_mgr.rpop("queue")
        """
        if self._redis is None:
            raise RuntimeError("Нет подключения к Redis. Вызовите connect()")

        result = await self._redis.rpop(key)
        return cast(str | None, result)

    async def lrange(self, key: str, start: int = 0, end: int = -1) -> list[str]:
        """
        Получить диапазон элементов списка.

        Аргументы:
            key: Имя ключа
            start: Начальный индекс
            end: Конечный индекс (-1 для всех)

        Returns:
            Список элементов

        Пример:
            >>> items = await redis_mgr.lrange("queue", 0, 9)
        """
        if self._redis is None:
            raise RuntimeError("Нет подключения к Redis. Вызовите connect()")

        return await self._redis.lrange(key, start, end)

    async def llen(self, key: str) -> int:
        """
        Получить длину списка.

        Аргументы:
            key: Имя ключа

        Returns:
            Длина списка

        Пример:
            >>> length = await redis_mgr.llen("queue")
        """
        if self._redis is None:
            raise RuntimeError("Нет подключения к Redis. Вызовите connect()")

        return await self._redis.llen(key)

    # ==================== Множества (Set) ====================

    async def sadd(self, key: str, *members: str) -> int:
        """
        Добавить элементы в множество.

        Аргументы:
            key: Имя ключа
            *members: Элементы для добавления

        Returns:
            Количество добавленных элементов

        Пример:
            >>> await redis_mgr.sadd("tags", "python", "redis", "async")
        """
        if self._redis is None:
            raise RuntimeError("Нет подключения к Redis. Вызовите connect()")

        return await self._redis.sadd(key, *members)

    async def smembers(self, key: str) -> Set[str]:
        """
        Получить все элементы множества.

        Аргументы:
            key: Имя ключа

        Returns:
            Множество элементов

        Пример:
            >>> tags = await redis_mgr.smembers("tags")
        """
        if self._redis is None:
            raise RuntimeError("Нет подключения к Redis. Вызовите connect()")

        return await self._redis.smembers(key)

    async def sismember(self, key: str, member: str) -> bool:
        """
        Проверить является ли элемент членом множества.

        Аргументы:
            key: Имя ключа
            member: Элемент для проверки

        Returns:
            True если элемент в множестве

        Пример:
            >>> is_member = await redis_mgr.sismember("tags", "python")
        """
        if self._redis is None:
            raise RuntimeError("Нет подключения к Redis. Вызовите connect()")

        result = await self._redis.sismember(key, member)
        return bool(result)

    async def srem(self, key: str, *members: str) -> int:
        """
        Удалить элементы из множества.

        Аргументы:
            key: Имя ключа
            *members: Элементы для удаления

        Returns:
            Количество удалённых элементов

        Пример:
            >>> await redis_mgr.srem("tags", "python")
        """
        if self._redis is None:
            raise RuntimeError("Нет подключения к Redis. Вызовите connect()")

        if not members:
            return 0

        return await self._redis.srem(key, *members)

    # ==================== Pub/Sub ====================

    @asynccontextmanager
    async def pubsub(self) -> AsyncIterator[PubSub]:
        """
        Контекстный менеджер для Pub/Sub.

        Yields:
            PubSub: Объект PubSub для подписки на каналы

        Пример:
            >>> async with redis_mgr.pubsub() as pub:
            ...     await pub.subscribe("channel1")
            ...     async for msg in pub.listen():
            ...         print(msg)
        """
        if self._redis is None:
            raise RuntimeError("Нет подключения к Redis. Вызовите connect()")

        pubsub = self._redis.pubsub()
        try:
            yield pubsub
        finally:
            await pubsub.close()

    async def publish(self, channel: str, message: str | int | float | bool) -> int:
        """
        Опубликовать сообщение в канал.

        Аргументы:
            channel: Имя канала
            message: Сообщение для публикации

        Returns:
            Количество подписчиков, получивших сообщение

        Пример:
            >>> await redis_mgr.publish("trades", "BTC/USDT bought: 0.5")
        """
        if self._redis is None:
            raise RuntimeError("Нет подключения к Redis. Вызовите connect()")

        return await self._redis.publish(channel, str(message))

    async def subscribe(self, *channels: str) -> PubSub:
        """
        Подписаться на каналы.

        Аргументы:
            *channels: Имена каналов для подписки

        Returns:
            Объект PubSub

        Пример:
            >>> pubsub = await redis_mgr.subscribe("trades", "orders")
            >>> async for msg in pubsub.listen():
            ...     print(msg)
        """
        if self._redis is None:
            raise RuntimeError("Нет подключения к Redis. Вызовите connect()")

        pubsub = self._redis.pubsub()
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
        """
        Добавить сообщение в stream.

        Аргументы:
            stream: Имя stream
            fields: Поля сообщения
            maxlen: Максимальная длина stream (опционально)
            approximate: Использовать приблизительный maxlen (быстрее)

        Returns:
            ID добавленного сообщения

        Пример:
            >>> msg_id = await redis_mgr.xadd("events", {"type": "trade", "symbol": "BTC"})
        """
        if self._redis is None:
            raise RuntimeError("Нет подключения к Redis. Вызовите connect()")

        options: dict[str, Any] = {}
        if maxlen is not None:
            options["maxlen"] = maxlen
            if approximate:
                options["~"] = "*"  # Приблизительное количество

        return await self._redis.xadd(stream, fields, **options)

    async def xread(
        self,
        streams: dict[str, str],
        count: int | None = None,
        block: int | None = None,
    ) -> list[list[tuple[str, dict[str, str]]]]:
        """
        Прочитать сообщения из stream.

        Аргументы:
            streams: Словарь {stream_name: last_id} для каждого stream
            count: Максимум сообщений на stream
            block: Блокировать milliseconds если нет сообщений

        Returns:
            Список сообщений

        Пример:
            >>> msgs = await redis_mgr.xread({"events": "0"}, block=5000)
        """
        if self._redis is None:
            raise RuntimeError("Нет подключения к Redis. Вызовите connect()")

        return await self._redis.xread(streams, count=count, block=block)

    async def xrange(
        self,
        stream: str,
        start: str = "-",
        end: str = "+",
        count: int | None = None,
    ) -> list[tuple[str, dict[str, str]]]:
        """
        Прочитать диапазон сообщений из stream.

        Аргументы:
            stream: Имя stream
            start: Начальный ID (по умолчанию "-")
            end: Конечный ID (по умолчанию "+")
            count: Максимум сообщений

        Returns:
            Список сообщений (id, fields)

        Пример:
            >>> msgs = await redis_mgr.xrange("events", count=10)
        """
        if self._redis is None:
            raise RuntimeError("Нет подключения к Redis. Вызовите connect()")

        return await self._redis.xrange(stream, start=start, end=end, count=count)

    async def xlen(self, stream: str) -> int:
        """
        Получить длину stream.

        Аргументы:
            stream: Имя stream

        Returns:
            Количество сообщений в stream

        Пример:
            >>> length = await redis_mgr.xlen("events")
        """
        if self._redis is None:
            raise RuntimeError("Нет подключения к Redis. Вызовите connect()")

        return await self._redis.xlen(stream)

    async def xdel(self, stream: str, *ids: str) -> int:
        """
        Удалить сообщения из stream.

        Аргументы:
            stream: Имя stream
            *ids: ID сообщений для удаления

        Returns:
            Количество удалённых сообщений

        Пример:
            >>> await redis_mgr.xdel("events", "1234567890-0")
        """
        if self._redis is None:
            raise RuntimeError("Нет подключения к Redis. Вызовите connect()")

        if not ids:
            return 0

        return await self._redis.xdel(stream, *ids)

    # ==================== Pipeline ====================

    async def pipeline(self) -> Pipeline:
        """
        Создать pipeline для пакетного выполнения команд.

        Returns:
            Pipeline объект

        Пример:
            >>> pipe = await redis_mgr.pipeline()
            >>> pipe.set("key1", "value1")
            >>> pipe.get("key2")
            >>> results = await pipe.execute()
        """
        if self._redis is None:
            raise RuntimeError("Нет подключения к Redis. Вызовите connect()")

        return self._redis.pipeline()

    # ==================== Утилиты ====================

    async def keys(self, pattern: str) -> list[str]:
        """
        Найти ключи по шаблону.

        ⚠️  Внимание: Не использовать в production на больших数据集.

        Аргументы:
            pattern: Шаблон (например, "user:*")

        Returns:
            Список найденных ключей

        Пример:
            >>> keys = await redis_mgr.keys("user:*")
        """
        if self._redis is None:
            raise RuntimeError("Нет подключения к Redis. Вызовите connect()")

        return await self._redis.keys(pattern)

    async def flushdb(self) -> bool:
        """
        Очистить текущую базу данных Redis.

        ⚠️  Внимание: Удаляет все ключи в текущей базе данных!

        Returns:
            True при успехе

        Пример:
            >>> await redis_mgr.flushdb()
        """
        if self._redis is None:
            raise RuntimeError("Нет подключения к Redis. Вызовите connect()")

        logger.warning("Очистка базы данных Redis")
        return await self._redis.flushdb()

    async def info(self, section: str | None = None) -> dict[str, Any]:
        """
        Получить информацию о Redis.

        Аргументы:
            section: Секция информации (опционально)

        Returns:
            Словарь с информацией

        Пример:
            >>> info = await redis_mgr.info("stats")
        """
        if self._redis is None:
            raise RuntimeError("Нет подключения к Redis. Вызовите connect()")

        return await self._redis.info(section)


# Глобальный экземпляр
_redis_manager: RedisManager | None = None


def get_redis() -> RedisManager:
    """
    Получить глобальный экземпляр RedisManager.

    Returns:
        Экземпляр менеджера Redis
    """
    global _redis_manager  # noqa: PLW0603
    if _redis_manager is None:
        _redis_manager = RedisManager()
    return _redis_manager


async def init_redis() -> RedisManager:
    """
    Инициализировать подключение к Redis.

    Returns:
        Подключённый экземпляр RedisManager
    """
    redis_mgr = get_redis()
    await redis_mgr.connect()
    return redis_mgr


async def close_redis() -> None:
    """Закрыть подключение к Redis."""
    global _redis_manager  # noqa: PLW0603
    if _redis_manager is not None:
        await _redis_manager.disconnect()
        _redis_manager = None

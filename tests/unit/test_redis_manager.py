"""
Тесты для Redis Manager (src/core/redis_manager.py).

Используют паттерн "фабрика создаёт клиент внутри теста":
- Каждый тест создаёт свой клиент через redis_client_factory()
- Клиент создаётся в том же event loop, где выполняется тест
- Гарантирует отсутствие конфликтов event loops на Windows
"""

import pytest

from src.core.redis_manager import RedisManager, TypedRedisClient, get_redis


class TestRedisManagerInit:
    """Тесты инициализации RedisManager."""

    def test_default_init(self) -> None:
        """Инициализация с параметрами по умолчанию."""
        redis_mgr = RedisManager()
        assert redis_mgr is not None
        assert not redis_mgr.is_connected
        assert redis_mgr.redis is None

    def test_custom_pool_size(self) -> None:
        """Инициализация с кастомным размером пула."""
        redis_mgr = RedisManager(max_connections=20)
        assert redis_mgr._max_connections == 20

    def test_get_redis_singleton(self) -> None:
        """Получение глобального экземпляра."""
        r1 = get_redis()
        r2 = get_redis()
        assert r1 is r2


class TestRedisManagerConnection:
    """Тесты подключения к Redis."""

    async def test_disconnect_when_not_connected(self) -> None:
        """Отключение без подключения не должно вызывать ошибку."""
        redis_mgr = RedisManager()
        await redis_mgr.disconnect()
        assert not redis_mgr.is_connected


@pytest.mark.redis
class TestRedisManagerOperations:
    """Тесты операций с Redis (используют фабрику)."""

    @pytest.mark.asyncio
    async def test_set_and_get(self, redis_client_factory) -> None:
        """Тест установки и получения значения."""
        async with await redis_client_factory.create() as client:
            redis_mgr = RedisManager()
            redis_mgr._typed_client = TypedRedisClient(client)
            redis_mgr._connected = True

            await redis_mgr.set_value("test_key", "test_value")
            value = await redis_mgr.get("test_key")
            assert value == "test_value"

    @pytest.mark.asyncio
    async def test_set_with_ttl(self, redis_client_factory) -> None:
        """Тест установки значения с TTL."""
        async with await redis_client_factory.create() as client:
            redis_mgr = RedisManager()
            redis_mgr._typed_client = TypedRedisClient(client)
            redis_mgr._connected = True

            await redis_mgr.set_value("ttl_key", "ttl_value", ttl=60)
            value = await redis_mgr.get("ttl_key")
            assert value == "ttl_value"

            ttl = await redis_mgr.ttl("ttl_key")
            assert 58 <= ttl <= 60

    @pytest.mark.asyncio
    async def test_get_nonexistent_key(self, redis_client_factory) -> None:
        """Тест получения несуществующего ключа."""
        async with await redis_client_factory.create() as client:
            redis_mgr = RedisManager()
            redis_mgr._typed_client = TypedRedisClient(client)
            redis_mgr._connected = True

            value = await redis_mgr.get("nonexistent_key_xyz")
            assert value is None

    @pytest.mark.asyncio
    async def test_delete(self, redis_client_factory) -> None:
        """Тест удаления ключа."""
        async with await redis_client_factory.create() as client:
            redis_mgr = RedisManager()
            redis_mgr._typed_client = TypedRedisClient(client)
            redis_mgr._connected = True

            await redis_mgr.set_value("delete_key", "delete_value")
            deleted = await redis_mgr.delete("delete_key")
            assert deleted == 1

            value = await redis_mgr.get("delete_key")
            assert value is None

    @pytest.mark.asyncio
    async def test_delete_multiple(self, redis_client_factory) -> None:
        """Тест удаления нескольких ключей."""
        async with await redis_client_factory.create() as client:
            redis_mgr = RedisManager()
            redis_mgr._typed_client = TypedRedisClient(client)
            redis_mgr._connected = True

            await redis_mgr.set_value("key1", "value1")
            await redis_mgr.set_value("key2", "value2")
            await redis_mgr.set_value("key3", "value3")

            deleted = await redis_mgr.delete("key1", "key2", "key3")
            assert deleted == 3

    @pytest.mark.asyncio
    async def test_exists(self, redis_client_factory) -> None:
        """Тест проверки существования ключа."""
        async with await redis_client_factory.create() as client:
            redis_mgr = RedisManager()
            redis_mgr._typed_client = TypedRedisClient(client)
            redis_mgr._connected = True

            await redis_mgr.set_value("exists_key", "value")
            count = await redis_mgr.exists("exists_key", "nonexistent")
            assert count == 1

    @pytest.mark.asyncio
    async def test_expire(self, redis_client_factory) -> None:
        """Тест установки TTL на существующий ключ."""
        async with await redis_client_factory.create() as client:
            redis_mgr = RedisManager()
            redis_mgr._typed_client = TypedRedisClient(client)
            redis_mgr._connected = True

            await redis_mgr.set_value("expire_key", "value")
            result = await redis_mgr.expire("expire_key", 100)
            assert result is True

            ttl = await redis_mgr.ttl("expire_key")
            assert 98 <= ttl <= 100

    @pytest.mark.asyncio
    async def test_incr(self, redis_client_factory) -> None:
        """Тест инкремента."""
        async with await redis_client_factory.create() as client:
            redis_mgr = RedisManager()
            redis_mgr._typed_client = TypedRedisClient(client)
            redis_mgr._connected = True

            await redis_mgr.set_value("counter", "10")
            new_value = await redis_mgr.incr("counter")
            assert new_value == 11

            new_value = await redis_mgr.incr("counter", 5)
            assert new_value == 16

    @pytest.mark.asyncio
    async def test_decr(self, redis_client_factory) -> None:
        """Тест декремента."""
        async with await redis_client_factory.create() as client:
            redis_mgr = RedisManager()
            redis_mgr._typed_client = TypedRedisClient(client)
            redis_mgr._connected = True

            await redis_mgr.set_value("decr_counter", "10")
            new_value = await redis_mgr.decr("decr_counter")
            assert new_value == 9

            new_value = await redis_mgr.decr("decr_counter", 3)
            assert new_value == 6


@pytest.mark.redis
class TestRedisManagerHashOperations:
    """Тесты хеш-операций."""

    @pytest.mark.asyncio
    async def test_hset_hget(self, redis_client_factory) -> None:
        """Тест установки и получения значения хеша."""
        async with await redis_client_factory.create() as client:
            redis_mgr = RedisManager()
            redis_mgr._typed_client = TypedRedisClient(client)
            redis_mgr._connected = True

            await redis_mgr.hset("user:1", "name", "Alice")
            await redis_mgr.hset("user:1", "age", "30")

            name = await redis_mgr.hget("user:1", "name")
            age = await redis_mgr.hget("user:1", "age")

            assert name == "Alice"
            assert age == "30"

    @pytest.mark.asyncio
    async def test_hgetall(self, redis_client_factory) -> None:
        """Тест получения всех полей хеша."""
        async with await redis_client_factory.create() as client:
            redis_mgr = RedisManager()
            redis_mgr._typed_client = TypedRedisClient(client)
            redis_mgr._connected = True

            await redis_mgr.hset("user:2", "name", "Bob")
            await redis_mgr.hset("user:2", "email", "bob@example.com")

            data = await redis_mgr.hgetall("user:2")
            assert data == {"name": "Bob", "email": "bob@example.com"}

    @pytest.mark.asyncio
    async def test_hdel(self, redis_client_factory) -> None:
        """Тест удаления полей хеша."""
        async with await redis_client_factory.create() as client:
            redis_mgr = RedisManager()
            redis_mgr._typed_client = TypedRedisClient(client)
            redis_mgr._connected = True

            await redis_mgr.hset("user:3", "name", "Charlie")
            await redis_mgr.hset("user:3", "email", "charlie@example.com")

            deleted = await redis_mgr.hdel("user:3", "email")
            assert deleted == 1

            data = await redis_mgr.hgetall("user:3")
            assert data == {"name": "Charlie"}


@pytest.mark.redis
class TestRedisManagerListOperations:
    """Тесты операций со списками."""

    @pytest.mark.asyncio
    async def test_lpush_rpush(self, redis_client_factory) -> None:
        """Тест добавления в список."""
        async with await redis_client_factory.create() as client:
            redis_mgr = RedisManager()
            redis_mgr._typed_client = TypedRedisClient(client)
            redis_mgr._connected = True

            await redis_mgr.lpush("queue", "item1")
            await redis_mgr.lpush("queue", "item2")

            items = await redis_mgr.lrange("queue")
            assert items == ["item2", "item1"]

    @pytest.mark.asyncio
    async def test_lpop_rpop(self, redis_client_factory) -> None:
        """Тест получения и удаления из списка."""
        async with await redis_client_factory.create() as client:
            redis_mgr = RedisManager()
            redis_mgr._typed_client = TypedRedisClient(client)
            redis_mgr._connected = True

            await redis_mgr.rpush("mylist", "a", "b", "c")

            item = await redis_mgr.lpop("mylist")
            assert item == "a"

            item = await redis_mgr.rpop("mylist")
            assert item == "c"

    @pytest.mark.asyncio
    async def test_llen(self, redis_client_factory) -> None:
        """Тест получения длины списка."""
        async with await redis_client_factory.create() as client:
            redis_mgr = RedisManager()
            redis_mgr._typed_client = TypedRedisClient(client)
            redis_mgr._connected = True

            await redis_mgr.rpush("listlen", "a", "b", "c")
            length = await redis_mgr.llen("listlen")
            assert length == 3


@pytest.mark.redis
class TestRedisManagerSetOperations:
    """Тесты операций с множествами."""

    @pytest.mark.asyncio
    async def test_sadd_smembers(self, redis_client_factory) -> None:
        """Тест добавления в множество и получения элементов."""
        async with await redis_client_factory.create() as client:
            redis_mgr = RedisManager()
            redis_mgr._typed_client = TypedRedisClient(client)
            redis_mgr._connected = True

            await redis_mgr.sadd("tags", "python", "redis", "async", "python")

            members = await redis_mgr.smembers("tags")
            assert members == {"python", "redis", "async"}

    @pytest.mark.asyncio
    async def test_sismember(self, redis_client_factory) -> None:
        """Тест проверки членства в множестве."""
        async with await redis_client_factory.create() as client:
            redis_mgr = RedisManager()
            redis_mgr._typed_client = TypedRedisClient(client)
            redis_mgr._connected = True

            await redis_mgr.sadd("colors", "red", "green", "blue")

            is_member = await redis_mgr.sismember("colors", "green")
            assert is_member is True

            is_member = await redis_mgr.sismember("colors", "yellow")
            assert is_member is False

    @pytest.mark.asyncio
    async def test_srem(self, redis_client_factory) -> None:
        """Тест удаления из множества."""
        async with await redis_client_factory.create() as client:
            redis_mgr = RedisManager()
            redis_mgr._typed_client = TypedRedisClient(client)
            redis_mgr._connected = True

            await redis_mgr.sadd("letters", "a", "b", "c")
            removed = await redis_mgr.srem("letters", "b")
            assert removed == 1

            members = await redis_mgr.smembers("letters")
            assert members == {"a", "c"}


@pytest.mark.redis
class TestRedisManagerPubSub:
    """Тесты Pub/Sub."""

    @pytest.mark.asyncio
    async def test_publish_subscribe(self, redis_client_factory) -> None:
        """Тест публикации и подписки."""
        async with await redis_client_factory.create() as client:
            redis_mgr = RedisManager()
            redis_mgr._typed_client = TypedRedisClient(client)
            redis_mgr._connected = True

            # Подписаться на канал
            pubsub = await redis_mgr.subscribe("test_channel")

            # Опубликовать сообщение
            subscribers = await redis_mgr.publish("test_channel", "test_message")
            assert subscribers >= 0

            # Получить сообщение
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=2)
            if message:
                assert message["data"] == "test_message"

            await pubsub.unsubscribe("test_channel")
            await pubsub.close()


@pytest.mark.redis
class TestRedisManagerStreams:
    """Тесты Streams."""

    @pytest.mark.asyncio
    async def test_xadd_xlen(self, redis_client_factory) -> None:
        """Тест добавления в stream и получения длины."""
        async with await redis_client_factory.create() as client:
            redis_mgr = RedisManager()
            redis_mgr._typed_client = TypedRedisClient(client)
            redis_mgr._connected = True

            msg_id = await redis_mgr.xadd("test_stream", {"event": "test", "data": "value"})
            assert msg_id is not None

            length = await redis_mgr.xlen("test_stream")
            assert length == 1

    @pytest.mark.asyncio
    async def test_xrange(self, redis_client_factory) -> None:
        """Тест получения диапазона из stream."""
        async with await redis_client_factory.create() as client:
            redis_mgr = RedisManager()
            redis_mgr._typed_client = TypedRedisClient(client)
            redis_mgr._connected = True

            await redis_mgr.xadd("test_stream2", {"field1": "value1"})
            await redis_mgr.xadd("test_stream2", {"field2": "value2"})

            messages = await redis_mgr.xrange("test_stream2")
            assert len(messages) == 2

    @pytest.mark.asyncio
    async def test_xdel(self, redis_client_factory) -> None:
        """Тест удаления из stream."""
        async with await redis_client_factory.create() as client:
            redis_mgr = RedisManager()
            redis_mgr._typed_client = TypedRedisClient(client)
            redis_mgr._connected = True

            msg_id = await redis_mgr.xadd("test_stream3", {"data": "value"})
            deleted = await redis_mgr.xdel("test_stream3", msg_id)
            assert deleted == 1


@pytest.mark.redis
class TestRedisManagerHealthCheck:
    """Тесты health check."""

    @pytest.mark.asyncio
    async def test_health_check_when_not_connected(self) -> None:
        """Health check без подключения."""
        redis_mgr = RedisManager()

        health = await redis_mgr.health_check()
        assert health["status"] == "unhealthy"
        assert health["connected"] is False

    @pytest.mark.asyncio
    async def test_health_check_with_connection(self, redis_client_factory) -> None:
        """Health check с подключением."""
        async with await redis_client_factory.create() as client:
            redis_mgr = RedisManager()
            redis_mgr._redis = client
            redis_mgr._typed_client = TypedRedisClient(client)
            redis_mgr._connected = True

            health = await redis_mgr.health_check()
            assert health["status"] == "healthy"
            assert health["connected"] is True
            assert "max_connections" in health


@pytest.mark.redis
class TestRedisManagerUtilities:
    """Тесты утилит."""

    @pytest.mark.asyncio
    async def test_keys_pattern(self, redis_client_factory) -> None:
        """Тест поиска ключей по шаблону."""
        async with await redis_client_factory.create() as client:
            redis_mgr = RedisManager()
            redis_mgr._typed_client = TypedRedisClient(client)
            redis_mgr._connected = True

            await redis_mgr.set_value("pattern_test_1", "value1")
            await redis_mgr.set_value("pattern_test_2", "value2")

            keys = await redis_mgr.keys("pattern_test_*")
            assert len(keys) >= 2

    @pytest.mark.asyncio
    async def test_info(self, redis_client_factory) -> None:
        """Тест получения информации о Redis."""
        async with await redis_client_factory.create() as client:
            redis_mgr = RedisManager()
            redis_mgr._typed_client = TypedRedisClient(client)
            redis_mgr._connected = True

            info = await redis_mgr.info("server")
            assert "redis_version" in info

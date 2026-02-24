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
        import uuid

        async with await redis_client_factory.create() as client:
            redis_mgr = RedisManager()
            redis_mgr._typed_client = TypedRedisClient(client)
            redis_mgr._connected = True

            key = f"test_key:{uuid.uuid4()}"
            await redis_mgr.set_value(key, "test_value")
            value = await redis_mgr.get(key)
            assert value == "test_value"

    @pytest.mark.asyncio
    async def test_set_with_ttl(self, redis_client_factory) -> None:
        """Тест установки значения с TTL."""
        import uuid

        async with await redis_client_factory.create() as client:
            redis_mgr = RedisManager()
            redis_mgr._typed_client = TypedRedisClient(client)
            redis_mgr._connected = True

            key = f"ttl_key:{uuid.uuid4()}"
            await redis_mgr.set_value(key, "ttl_value", ttl=60)
            value = await redis_mgr.get(key)
            assert value == "ttl_value"

            ttl = await redis_mgr.ttl(key)
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
        import uuid

        async with await redis_client_factory.create() as client:
            redis_mgr = RedisManager()
            redis_mgr._typed_client = TypedRedisClient(client)
            redis_mgr._connected = True

            key = f"delete_key:{uuid.uuid4()}"
            await redis_mgr.set_value(key, "delete_value")
            deleted = await redis_mgr.delete(key)
            assert deleted == 1

            value = await redis_mgr.get(key)
            assert value is None

    @pytest.mark.asyncio
    async def test_delete_multiple(self, redis_client_factory) -> None:
        """Тест удаления нескольких ключей."""
        import uuid

        async with await redis_client_factory.create() as client:
            redis_mgr = RedisManager()
            redis_mgr._typed_client = TypedRedisClient(client)
            redis_mgr._connected = True

            prefix = f"key:{uuid.uuid4().hex[:8]}"
            await redis_mgr.set_value(f"{prefix}1", "value1")
            await redis_mgr.set_value(f"{prefix}2", "value2")
            await redis_mgr.set_value(f"{prefix}3", "value3")

            deleted = await redis_mgr.delete(f"{prefix}1", f"{prefix}2", f"{prefix}3")
            assert deleted == 3

    @pytest.mark.asyncio
    async def test_exists(self, redis_client_factory) -> None:
        """Тест проверки существования ключа."""
        import uuid

        async with await redis_client_factory.create() as client:
            redis_mgr = RedisManager()
            redis_mgr._typed_client = TypedRedisClient(client)
            redis_mgr._connected = True

            key = f"exists_key:{uuid.uuid4()}"
            await redis_mgr.set_value(key, "value")
            count = await redis_mgr.exists(key, "nonexistent")
            assert count == 1

    @pytest.mark.asyncio
    async def test_expire(self, redis_client_factory) -> None:
        """Тест установки TTL на существующий ключ."""
        import uuid

        async with await redis_client_factory.create() as client:
            redis_mgr = RedisManager()
            redis_mgr._typed_client = TypedRedisClient(client)
            redis_mgr._connected = True

            key = f"expire_key:{uuid.uuid4()}"
            await redis_mgr.set_value(key, "value")
            result = await redis_mgr.expire(key, 100)
            assert result is True

            ttl = await redis_mgr.ttl(key)
            assert 98 <= ttl <= 100

    @pytest.mark.asyncio
    async def test_incr(self, redis_client_factory) -> None:
        """Тест инкремента."""
        import uuid

        async with await redis_client_factory.create() as client:
            redis_mgr = RedisManager()
            redis_mgr._typed_client = TypedRedisClient(client)
            redis_mgr._connected = True

            key = f"counter:{uuid.uuid4()}"
            await redis_mgr.set_value(key, "10")
            new_value = await redis_mgr.incr(key)
            assert new_value == 11

            new_value = await redis_mgr.incr(key, 5)
            assert new_value == 16

    @pytest.mark.asyncio
    async def test_decr(self, redis_client_factory) -> None:
        """Тест декремента."""
        import uuid

        async with await redis_client_factory.create() as client:
            redis_mgr = RedisManager()
            redis_mgr._typed_client = TypedRedisClient(client)
            redis_mgr._connected = True

            key = f"decr_counter:{uuid.uuid4()}"
            await redis_mgr.set_value(key, "10")
            new_value = await redis_mgr.decr(key)
            assert new_value == 9

            new_value = await redis_mgr.decr(key, 3)
            assert new_value == 6


@pytest.mark.redis
class TestRedisManagerHashOperations:
    """Тесты хеш-операций."""

    @pytest.mark.asyncio
    async def test_hset_hget(self, redis_client_factory) -> None:
        """Тест установки и получения значения хеша."""
        import uuid

        async with await redis_client_factory.create() as client:
            redis_mgr = RedisManager()
            redis_mgr._typed_client = TypedRedisClient(client)
            redis_mgr._connected = True

            key = f"user:{uuid.uuid4()}"
            await redis_mgr.hset(key, "name", "Alice")
            await redis_mgr.hset(key, "age", "30")

            name = await redis_mgr.hget(key, "name")
            age = await redis_mgr.hget(key, "age")

            assert name == "Alice"
            assert age == "30"

    @pytest.mark.asyncio
    async def test_hgetall(self, redis_client_factory) -> None:
        """Тест получения всех полей хеша."""
        import uuid

        async with await redis_client_factory.create() as client:
            redis_mgr = RedisManager()
            redis_mgr._typed_client = TypedRedisClient(client)
            redis_mgr._connected = True

            key = f"user:{uuid.uuid4()}"
            await redis_mgr.hset(key, "name", "Bob")
            await redis_mgr.hset(key, "email", "bob@example.com")

            data = await redis_mgr.hgetall(key)
            assert data == {"name": "Bob", "email": "bob@example.com"}

    @pytest.mark.asyncio
    async def test_hdel(self, redis_client_factory) -> None:
        """Тест удаления полей хеша."""
        import uuid

        async with await redis_client_factory.create() as client:
            redis_mgr = RedisManager()
            redis_mgr._typed_client = TypedRedisClient(client)
            redis_mgr._connected = True

            key = f"user:{uuid.uuid4()}"
            await redis_mgr.hset(key, "name", "Charlie")
            await redis_mgr.hset(key, "email", "charlie@example.com")

            deleted = await redis_mgr.hdel(key, "email")
            assert deleted == 1

            data = await redis_mgr.hgetall(key)
            assert data == {"name": "Charlie"}


@pytest.mark.redis
class TestRedisManagerListOperations:
    """Тесты операций со списками."""

    @pytest.mark.asyncio
    async def test_lpush_rpush(self, redis_client_factory) -> None:
        """Тест добавления в список."""
        import uuid

        async with await redis_client_factory.create() as client:
            redis_mgr = RedisManager()
            redis_mgr._typed_client = TypedRedisClient(client)
            redis_mgr._connected = True

            key = f"queue:{uuid.uuid4()}"
            await redis_mgr.lpush(key, "item1")
            await redis_mgr.lpush(key, "item2")

            items = await redis_mgr.lrange(key)
            assert items == ["item2", "item1"]

    @pytest.mark.asyncio
    async def test_lpop_rpop(self, redis_client_factory) -> None:
        """Тест получения и удаления из списка."""
        import uuid

        async with await redis_client_factory.create() as client:
            redis_mgr = RedisManager()
            redis_mgr._typed_client = TypedRedisClient(client)
            redis_mgr._connected = True

            # Уникальный ключ для изоляции тестов
            key = f"mylist:{uuid.uuid4()}"

            await redis_mgr.rpush(key, "a", "b", "c")

            item = await redis_mgr.lpop(key)
            assert item == "a"

            item = await redis_mgr.rpop(key)
            assert item == "c"

    @pytest.mark.asyncio
    async def test_llen(self, redis_client_factory) -> None:
        """Тест получения длины списка."""
        import uuid

        async with await redis_client_factory.create() as client:
            redis_mgr = RedisManager()
            redis_mgr._typed_client = TypedRedisClient(client)
            redis_mgr._connected = True

            key = f"listlen:{uuid.uuid4()}"
            await redis_mgr.rpush(key, "a", "b", "c")
            length = await redis_mgr.llen(key)
            assert length == 3


@pytest.mark.redis
class TestRedisManagerSetOperations:
    """Тесты операций с множествами."""

    @pytest.mark.asyncio
    async def test_sadd_smembers(self, redis_client_factory) -> None:
        """Тест добавления в множество и получения элементов."""
        import uuid

        async with await redis_client_factory.create() as client:
            redis_mgr = RedisManager()
            redis_mgr._typed_client = TypedRedisClient(client)
            redis_mgr._connected = True

            key = f"tags:{uuid.uuid4()}"
            await redis_mgr.sadd(key, "python", "redis", "async", "python")

            members = await redis_mgr.smembers(key)
            assert members == {"python", "redis", "async"}

    @pytest.mark.asyncio
    async def test_sismember(self, redis_client_factory) -> None:
        """Тест проверки членства в множестве."""
        import uuid

        async with await redis_client_factory.create() as client:
            redis_mgr = RedisManager()
            redis_mgr._typed_client = TypedRedisClient(client)
            redis_mgr._connected = True

            key = f"colors:{uuid.uuid4()}"
            await redis_mgr.sadd(key, "red", "green", "blue")

            is_member = await redis_mgr.sismember(key, "green")
            assert is_member is True

            is_member = await redis_mgr.sismember(key, "yellow")
            assert is_member is False

    @pytest.mark.asyncio
    async def test_srem(self, redis_client_factory) -> None:
        """Тест удаления из множества."""
        import uuid

        async with await redis_client_factory.create() as client:
            redis_mgr = RedisManager()
            redis_mgr._typed_client = TypedRedisClient(client)
            redis_mgr._connected = True

            key = f"letters:{uuid.uuid4()}"
            await redis_mgr.sadd(key, "a", "b", "c")
            removed = await redis_mgr.srem(key, "b")
            assert removed == 1

            members = await redis_mgr.smembers(key)
            assert members == {"a", "c"}


@pytest.mark.redis
class TestRedisManagerPubSub:
    """Тесты Pub/Sub."""

    @pytest.mark.asyncio
    async def test_publish_subscribe(self, redis_client_factory) -> None:
        """Тест публикации и подписки."""
        import uuid

        async with await redis_client_factory.create() as client:
            redis_mgr = RedisManager()
            redis_mgr._typed_client = TypedRedisClient(client)
            redis_mgr._connected = True

            channel = f"test_channel:{uuid.uuid4()}"
            # Подписаться на канал
            pubsub = await redis_mgr.subscribe(channel)

            # Опубликовать сообщение
            subscribers = await redis_mgr.publish(channel, "test_message")
            assert subscribers >= 0

            # Получить сообщение
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=2)
            if message:
                assert message["data"] == "test_message"

            await pubsub.unsubscribe(channel)
            await pubsub.close()


@pytest.mark.redis
class TestRedisManagerStreams:
    """Тесты Streams."""

    @pytest.mark.asyncio
    async def test_xadd_xlen(self, redis_client_factory) -> None:
        """Тест добавления в stream и получения длины."""
        import uuid

        async with await redis_client_factory.create() as client:
            redis_mgr = RedisManager()
            redis_mgr._typed_client = TypedRedisClient(client)
            redis_mgr._connected = True

            key = f"test_stream:{uuid.uuid4()}"
            msg_id = await redis_mgr.xadd(key, {"event": "test", "data": "value"})
            assert msg_id is not None

            length = await redis_mgr.xlen(key)
            assert length == 1

    @pytest.mark.asyncio
    async def test_xrange(self, redis_client_factory) -> None:
        """Тест получения диапазона из stream."""
        import uuid

        async with await redis_client_factory.create() as client:
            redis_mgr = RedisManager()
            redis_mgr._typed_client = TypedRedisClient(client)
            redis_mgr._connected = True

            key = f"test_stream2:{uuid.uuid4()}"
            await redis_mgr.xadd(key, {"field1": "value1"})
            await redis_mgr.xadd(key, {"field2": "value2"})

            messages = await redis_mgr.xrange(key)
            assert len(messages) == 2

    @pytest.mark.asyncio
    async def test_xdel(self, redis_client_factory) -> None:
        """Тест удаления из stream."""
        import uuid

        async with await redis_client_factory.create() as client:
            redis_mgr = RedisManager()
            redis_mgr._typed_client = TypedRedisClient(client)
            redis_mgr._connected = True

            key = f"test_stream3:{uuid.uuid4()}"
            msg_id = await redis_mgr.xadd(key, {"data": "value"})
            deleted = await redis_mgr.xdel(key, msg_id)
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
        import uuid

        async with await redis_client_factory.create() as client:
            redis_mgr = RedisManager()
            redis_mgr._typed_client = TypedRedisClient(client)
            redis_mgr._connected = True

            prefix = f"pattern_test_{uuid.uuid4().hex[:8]}"
            await redis_mgr.set_value(f"{prefix}_1", "value1")
            await redis_mgr.set_value(f"{prefix}_2", "value2")

            keys = await redis_mgr.keys(f"{prefix}_*")
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

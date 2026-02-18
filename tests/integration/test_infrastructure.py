# ==================== CRYPTOTEHNOLOG Infrastructure Tests ====================
# Integration tests for infrastructure services (Redis, PostgreSQL, Vault)

import asyncio
import json

import pytest
import redis.asyncio as redis
from asyncpg import connect as asyncpg_connect


@pytest.mark.integration
class TestRedisConnection:
    """Test cases for Redis connection."""

    @pytest.fixture
    async def redis_client(self, test_settings):
        """Create Redis client for testing."""
        client = await redis.from_url(
            test_settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        yield client
        await client.close()

    @pytest.mark.asyncio
    async def test_redis_connection(self, redis_client):
        """Test that we can connect to Redis."""
        # Ping Redis
        result = await redis_client.ping()
        assert result is True

    @pytest.mark.asyncio
    async def test_redis_set_get(self, redis_client):
        """Test that we can set and get values from Redis."""
        # Set a value
        await redis_client.set("test_key", "test_value")

        # Get the value
        value = await redis_client.get("test_key")

        assert value == "test_value"

        # Clean up
        await redis_client.delete("test_key")

    @pytest.mark.asyncio
    async def test_redis_list_operations(self, redis_client):
        """Test that we can perform list operations in Redis."""
        list_key = "test_list"

        # Push values to list
        await redis_client.lpush(list_key, "value1", "value2", "value3")

        # Get list length
        length = await redis_client.llen(list_key)
        assert length == 3

        # Get all values
        values = await redis_client.lrange(list_key, 0, -1)
        assert len(values) == 3
        assert "value1" in values

        # Clean up
        await redis_client.delete(list_key)

    @pytest.mark.asyncio
    async def test_redis_hash_operations(self, redis_client):
        """Test that we can perform hash operations in Redis."""
        hash_key = "test_hash"

        # Set hash fields
        await redis_client.hset(hash_key, mapping={"field1": "value1", "field2": "value2"})

        # Get hash field
        value = await redis_client.hget(hash_key, "field1")
        assert value == "value1"

        # Get all hash fields
        all_fields = await redis_client.hgetall(hash_key)
        assert len(all_fields) == 2
        assert "field1" in all_fields

        # Clean up
        await redis_client.delete(hash_key)


@pytest.mark.integration
class TestPostgreSQLConnection:
    """Test cases for PostgreSQL connection."""

    @pytest.fixture
    async def pg_connection(self, test_settings):
        """Create PostgreSQL connection for testing."""
        conn = await asyncpg_connect(test_settings.postgres_async_url)
        yield conn
        await conn.close()

    @pytest.mark.asyncio
    async def test_postgresql_connection(self, pg_connection):
        """Test that we can connect to PostgreSQL."""
        # Execute a simple query
        result = await pg_connection.fetchval("SELECT 1")
        assert result == 1

    @pytest.mark.asyncio
    async def test_postgresql_create_table(self, pg_connection):
        """Test that we can create a table in PostgreSQL."""
        # Create a test table
        await pg_connection.execute("""
            CREATE TABLE IF NOT EXISTS test_table (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100),
                value INTEGER
            )
        """)

        # Insert a row
        await pg_connection.execute(
            "INSERT INTO test_table (name, value) VALUES ($1, $2)", "test", 42
        )

        # Query the row
        result = await pg_connection.fetchrow("SELECT * FROM test_table WHERE name = $1", "test")

        assert result is not None
        assert result["name"] == "test"
        assert result["value"] == 42

        # Clean up
        await pg_connection.execute("DROP TABLE test_table")

    @pytest.mark.asyncio
    async def test_postgresql_jsonb_operations(self, pg_connection):
        """Test that we can perform JSONB operations in PostgreSQL."""
        # Create a test table with JSONB column
        await pg_connection.execute("""
            CREATE TABLE IF NOT EXISTS test_jsonb (
                id SERIAL PRIMARY KEY,
                data JSONB
            )
        """)

        # Insert JSONB data (asyncpg requires JSON as string)
        test_data = {"key1": "value1", "key2": 123, "key3": {"nested": "value"}}
        await pg_connection.execute("INSERT INTO test_jsonb (data) VALUES ($1)", json.dumps(test_data))

        # Query and verify JSONB data
        result = await pg_connection.fetchrow("SELECT data FROM test_jsonb WHERE id = 1")
        assert result is not None

        # asyncpg returns JSONB as string, need to decode
        data_str = result["data"]
        data = json.loads(data_str)

        assert data["key1"] == "value1"
        assert data["key2"] == 123
        assert data["key3"]["nested"] == "value"

        # Clean up
        await pg_connection.execute("DROP TABLE test_jsonb")

    @pytest.mark.asyncio
    async def test_postgresql_transaction(self, pg_connection):
        """Test that PostgreSQL transactions work correctly."""
        # Create table first
        await pg_connection.execute("""
            CREATE TABLE IF NOT EXISTS test_transaction (
                id SERIAL PRIMARY KEY,
                value INTEGER
            )
        """)

        # Insert multiple rows in transaction
        async with pg_connection.transaction():
            for i in range(5):
                await pg_connection.execute(
                    "INSERT INTO test_transaction (value) VALUES ($1)", i
                )

            # Query all rows within transaction
            results = await pg_connection.fetch("SELECT * FROM test_transaction")
            assert len(results) == 5

        # After commit, rows should exist
        results = await pg_connection.fetch("SELECT * FROM test_transaction")
        assert len(results) == 5

        # Test rollback
        try:
            async with pg_connection.transaction():
                await pg_connection.execute("INSERT INTO test_transaction (value) VALUES ($1)", 999)
                raise Exception("Intentional rollback")
        except Exception:
            pass  # Expected exception for rollback

        # After rollback, row should not exist
        result = await pg_connection.fetchval(
            "SELECT COUNT(*) FROM test_transaction WHERE value = 999"
        )
        assert result == 0

        # Clean up
        await pg_connection.execute("DROP TABLE test_transaction")


@pytest.mark.integration
class TestInfrastructureIntegration:
    """Test cases for infrastructure integration."""

    @pytest.mark.asyncio
    async def test_redis_postgresql_integration(self, test_settings):
        """Test integration between Redis and PostgreSQL."""
        # Create Redis client
        redis_client = await redis.from_url(
            test_settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )

        # Create PostgreSQL connection
        pg_conn = await asyncpg_connect(test_settings.postgres_async_url)

        try:
            # Store data in Redis
            await redis_client.set("integration_test", "test_value")

            # Retrieve from Redis
            redis_value = await redis_client.get("integration_test")
            assert redis_value == "test_value"

            # Store data in PostgreSQL
            await pg_conn.execute("""
                CREATE TEMP TABLE integration_test (
                    id SERIAL PRIMARY KEY,
                    value VARCHAR(100)
                )
            """)

            await pg_conn.execute(
                "INSERT INTO integration_test (value) VALUES ($1)", redis_value
            )

            # Retrieve from PostgreSQL
            pg_value = await pg_conn.fetchval("SELECT value FROM integration_test WHERE id = 1")
            assert pg_value == redis_value

            # Clean up Redis
            await redis_client.delete("integration_test")
        finally:
            await redis_client.close()
            await pg_conn.close()

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, test_settings):
        """Test that concurrent Redis operations work correctly."""
        # Create Redis client
        redis_client = await redis.from_url(
            test_settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )

        try:
            # Perform concurrent Redis operations
            async def redis_set_get(i):
                await redis_client.set(f"concurrent_{i}", i)
                return await redis_client.get(f"concurrent_{i}")

            # Run operations concurrently
            tasks = [redis_set_get(i) for i in range(20)]
            results = await asyncio.gather(*tasks)

            # Verify all operations completed
            assert len(results) == 20
            assert all(r is not None for r in results)

            # Verify values
            for i, result in enumerate(results):
                assert result == str(i)

            # Clean up Redis
            for i in range(20):
                await redis_client.delete(f"concurrent_{i}")
        finally:
            await redis_client.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])

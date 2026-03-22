# ==================== CRYPTOTEHNOLOG Integration Test Configuration ====================
# Pytest configuration for integration tests (requires real DB)

import asyncio
from collections.abc import AsyncGenerator
import os
from pathlib import Path
import sys
from typing import TYPE_CHECKING

import asyncpg
import pytest
import pytest_asyncio
import redis.asyncio as redis

from cryptotechnolog.config.settings import Settings

# Windows asyncio fix
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

if TYPE_CHECKING:
    from collections.abc import Generator

# Set test environment
os.environ["ENVIRONMENT"] = "test"
os.environ["DEBUG"] = "true"

# Unique lock ID for test DB initialization
_TEST_DB_INIT_LOCK_ID = 1234567890


def _should_skip_external_integration_setup() -> bool:
    """Определить, нужно ли пропустить внешний integration setup."""
    return os.environ.get("SKIP_EXTERNAL_INTEGRATION_SETUP", "").lower() in {
        "1",
        "true",
        "yes",
    }


# ==================== Event Loop Fixture ====================


# NOTE: We don't define a custom event_loop fixture here.
# pytest-asyncio will automatically create a function-scoped event loop
# for each async test, which is the recommended approach.
# This avoids "RuntimeError: Event loop is closed" issues.


# ==================== Migration Helpers ====================


def get_migration_files() -> list[Path]:
    """Get sorted list of migration SQL files."""
    migrations_dir = Path(__file__).parent.parent.parent / "scripts" / "migrations"

    if not migrations_dir.exists():
        return []

    migrations = []
    for f in migrations_dir.glob("*.sql"):
        # Skip control_plane_additions.sql - apply it last
        if f.name == "control_plane_additions.sql":
            continue
        migrations.append(f)

    # Sort by version number (001, 002, etc.)
    migrations.sort(key=lambda x: x.name.split("_")[0])
    return migrations


async def apply_migrations(conn: asyncpg.Connection) -> None:
    """Apply all migrations in order."""
    migration_files = get_migration_files()

    for migration_file in migration_files:
        sql = migration_file.read_text(encoding="utf-8")
        await conn.execute(sql)

    # Apply control_plane_additions.sql last
    control_plane = (
        Path(__file__).parent.parent.parent
        / "scripts"
        / "migrations"
        / "control_plane_additions.sql"
    )
    if control_plane.exists():
        sql = control_plane.read_text(encoding="utf-8")
        await conn.execute(sql)


async def drop_all_tables(conn: asyncpg.Connection) -> None:
    """Drop all tables in public schema."""
    tables = await conn.fetch(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'public' "
        "AND tablename NOT LIKE 'pg_%' AND tablename NOT LIKE 'sql_%'"
    )

    if tables:
        table_names = [t["tablename"] for t in tables]
        for table in table_names:
            await conn.execute(f"DROP TABLE IF EXISTS {table} CASCADE")


# ==================== Database Fixtures ====================


@pytest_asyncio.fixture(scope="session", autouse=True)
async def test_db_setup() -> AsyncGenerator[None, None]:
    """Initialize test DB using migrations (single source of truth).

    Uses PostgreSQL Advisory Lock to prevent concurrent initialization
    from multiple pytest-xdist workers.

    This approach ensures:
    - CI and local environments have identical schema
    - Schema always matches migrations (not hardcoded SQL)
    - No duplication between init-db.sql and conftest.py
    """
    if _should_skip_external_integration_setup():
        yield
        return

    settings = Settings()

    conn = await asyncpg.connect(
        settings.postgres_test_async_url,
        command_timeout=60,
    )
    try:
        lock_acquired = await conn.fetchval(
            "SELECT pg_try_advisory_lock($1)",
            _TEST_DB_INIT_LOCK_ID,
        )

        if not lock_acquired:
            await conn.execute(
                "SELECT pg_advisory_lock($1)",
                _TEST_DB_INIT_LOCK_ID,
            )

        try:
            # Always refresh schema from migrations for consistency
            print("\n[test_db_setup] Dropping existing tables...")
            await drop_all_tables(conn)

            print("[test_db_setup] Applying migrations...")
            await apply_migrations(conn)
            print("[test_db_setup] Migrations applied successfully.")

        finally:
            await conn.execute(
                "SELECT pg_advisory_unlock($1)",
                _TEST_DB_INIT_LOCK_ID,
            )
    finally:
        await conn.close()

    yield  # Required for async generator fixture


@pytest_asyncio.fixture()
async def clean_tables_between_tests() -> AsyncGenerator[None, None]:
    """Clean tables between tests (but keep schema from migrations)."""
    settings = Settings()
    conn = await asyncpg.connect(
        settings.postgres_test_async_url,
        command_timeout=60,
    )
    try:
        tables = await conn.fetch(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' "
            "AND tablename NOT LIKE 'pg_%' AND tablename NOT LIKE 'sql_%' "
            "AND tablename != 'schema_migrations'"
        )

        if tables:
            table_names = [t["tablename"] for t in tables]
            await conn.execute(f"TRUNCATE TABLE {', '.join(table_names)} RESTART IDENTITY CASCADE")

        # Re-insert initial state for state_machine_states
        await conn.execute("""
            INSERT INTO state_machine_states (id, current_state, version)
            VALUES (1, 'boot', 0)
            ON CONFLICT (id) DO NOTHING
        """)

        yield
    finally:
        await conn.close()


@pytest.fixture
def db_connection_factory():
    """Factory for creating test DB connection."""

    class DBConnectionFactory:
        @staticmethod
        async def create() -> asyncpg.Connection:
            settings = Settings()
            conn = await asyncpg.connect(
                settings.postgres_test_async_url,
                command_timeout=60,
            )
            return conn

    return DBConnectionFactory


# ==================== Pool Fixture for Integration Tests ====================


@pytest_asyncio.fixture(scope="function")
async def db_pool():
    """
    Function-scoped database pool for integration tests.

    Creates its own connection pool to avoid event loop issues.
    The pool is closed after each test to ensure clean state.
    """
    settings = Settings()

    # Create our own pool instead of using global get_database()
    pool = await asyncpg.create_pool(
        settings.postgres_test_async_url,
        min_size=1,
        max_size=5,
        command_timeout=60,
    )

    # Verify schema exists (migrations are applied in test_db_setup)
    async with pool.acquire() as conn:
        tables = await conn.fetch(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' "
            "AND tablename = 'schema_migrations'"
        )
        if not tables:
            # Apply migrations if not present
            await apply_migrations(conn)

    yield pool

    # Close the pool after each test to avoid event loop issues
    await pool.close()


# ==================== Settings Fixtures ====================


@pytest.fixture
def test_env(monkeypatch: pytest.MonkeyPatch) -> "Generator[dict[str, str], None, None]":
    """Set test environment."""
    env_vars = {
        "ENVIRONMENT": "test",
        "DEBUG": "true",
    }
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)
    yield env_vars


@pytest.fixture
def test_settings(test_env: dict[str, str]) -> "Settings":
    """Return test settings instance."""
    return Settings()


# ==================== Markers ====================


def pytest_configure(config: pytest.Config) -> None:
    """Register markers."""
    config.addinivalue_line("markers", "integration: integration tests with external dependencies")
    config.addinivalue_line("markers", "db: tests requiring DB connection")
    config.addinivalue_line("markers", "redis: tests requiring Redis connection")


# ==================== Redis Fixtures ====================


@pytest.fixture(scope="session", autouse=True)
async def redis_clean_state() -> None:
    """Clean Redis before all tests."""
    if _should_skip_external_integration_setup():
        return

    settings = Settings()
    client = redis.from_url(
        settings.redis_url,
        socket_timeout=10,
        socket_connect_timeout=10,
    )
    try:
        await client.flushdb()
    except (TimeoutError, redis.RedisError) as exc:
        pytest.skip(f"Redis integration setup unavailable: {exc}")
    finally:
        await client.close()


@pytest.fixture
def redis_client_factory():
    """Factory for creating Redis client."""

    class RedisClientFactory:
        @staticmethod
        async def create() -> redis.Redis:
            settings = Settings()
            client = redis.from_url(
                settings.redis_url,
                max_connections=settings.redis_pool_max_connections,
                socket_timeout=settings.redis_pool_socket_timeout,
                socket_connect_timeout=10,
                decode_responses=True,
            )
            await asyncio.wait_for(client.ping(), timeout=10.0)
            return client

    return RedisClientFactory

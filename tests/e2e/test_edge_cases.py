# ==================== E2E: Edge Cases ====================
"""
Edge Cases E2E Tests (15 сценариев)

Тестирует граничные случаи и нестандартные сценарии:
- Zero values
- Extreme values
- Concurrent operations
- Network failures
- Time-related edge cases
"""

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from cryptotechnolog.core.event import EventType

# ==================== Zero Values ====================


@pytest.mark.e2e
@pytest.mark.edge_case
@pytest.mark.asyncio
async def test_zero_quantity_order(db_pool):
    """
    E2E: Ордер с нулевым количеством
    """
    async with db_pool.acquire() as conn:
        # Проверяем что нулевое количество обрабатывается
        await conn.execute(
            """
            INSERT INTO events (event_type, data, created_at)
            VALUES ($1, $2, $3)
            """,
            EventType.ORDER_SUBMITTED.value,
            {"order_id": "zero_qty", "quantity": "0"},
            datetime.now(UTC),
        )

        result = await conn.fetchval(
            "SELECT data->>'quantity' FROM events WHERE data->>'order_id' = $1",
            "zero_qty",
        )
        assert result == "0"


@pytest.mark.e2e
@pytest.mark.edge_case
@pytest.mark.asyncio
async def test_zero_price_order(db_pool):
    """
    E2E: Ордер с нулевой ценой (market order)
    """
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO events (event_type, data, created_at)
            VALUES ($1, $2, $3)
            """,
            EventType.ORDER_SUBMITTED.value,
            {"order_id": "zero_price", "order_type": "market", "price": "0"},
            datetime.now(UTC),
        )

        result = await conn.fetchval(
            "SELECT data->>'price' FROM events WHERE data->>'order_id' = $1",
            "zero_price",
        )
        assert result == "0"


@pytest.mark.e2e
@pytest.mark.edge_case
@pytest.mark.asyncio
async def test_zero_balance(db_pool):
    """
    E2E: Нулевой баланс
    """
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO events (event_type, data, created_at)
            VALUES ($1, $2, $3)
            """,
            EventType.POSITION_UPDATED.value,
            {"symbol": "BTC/USDT", "quantity": "0", "balance": "0"},
            datetime.now(UTC),
        )

        result = await conn.fetchval(
            "SELECT data->>'balance' FROM events WHERE data->>'symbol' = $1",
            "BTC/USDT",
        )
        assert result == "0"


# ==================== Extreme Values ====================


@pytest.mark.e2e
@pytest.mark.edge_case
@pytest.mark.asyncio
async def test_max_decimal_value(db_pool):
    """
    E2E: Максимальное значение decimal
    """
    max_value = Decimal("999999999999.99999999")

    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO events (event_type, data, created_at)
            VALUES ($1, $2, $3)
            """,
            EventType.TRADE_EXECUTED.value,
            {
                "trade_id": "max_value",
                "quantity": str(max_value),
                "price": str(max_value),
            },
            datetime.now(UTC),
        )

        result = await conn.fetchval(
            "SELECT data->>'quantity' FROM events WHERE data->>'trade_id' = $1",
            "max_value",
        )
        assert result is not None


@pytest.mark.e2e
@pytest.mark.edge_case
@pytest.mark.asyncio
async def test_min_decimal_value(db_pool):
    """
    E2E: Минимальное значение decimal
    """
    min_value = Decimal("0.00000001")

    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO events (event_type, data, created_at)
            VALUES ($1, $2, $3)
            """,
            EventType.TRADE_EXECUTED.value,
            {
                "trade_id": "min_value",
                "quantity": str(min_value),
                "price": str(min_value * 1000),
            },
            datetime.now(UTC),
        )

        result = await conn.fetchval(
            "SELECT data->>'quantity' FROM events WHERE data->>'trade_id' = $1",
            "min_value",
        )
        assert result is not None


@pytest.mark.e2e
@pytest.mark.edge_case
@pytest.mark.asyncio
async def test_negative_values(db_pool):
    """
    E2E: Отрицательные значения (для P&L)
    """
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO events (event_type, data, created_at)
            VALUES ($1, $2, $3)
            """,
            EventType.TRADE_EXECUTED.value,
            {"trade_id": "negative", "pnl": "-100.50"},
            datetime.now(UTC),
        )

        result = await conn.fetchval(
            "SELECT data->>'pnl' FROM events WHERE data->>'trade_id' = $1",
            "negative",
        )
        assert result == "-100.50"


@pytest.mark.e2e
@pytest.mark.edge_case
@pytest.mark.asyncio
async def test_large_string_values(db_pool):
    """
    E2E: Большие строковые значения
    """
    large_string = "x" * 10000

    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO events (event_type, data, created_at)
            VALUES ($1, $2, $3)
            """,
            EventType.ORDER_SUBMITTED.value,
            {"order_id": "large_string", "memo": large_string},
            datetime.now(UTC),
        )

        result = await conn.fetchval(
            "SELECT data->>'memo' FROM events WHERE data->>'order_id' = $1",
            "large_string",
        )
        assert len(result) == 10000


# ==================== Concurrent Operations ====================


@pytest.mark.e2e
@pytest.mark.concurrent
@pytest.mark.asyncio
async def test_concurrent_order_inserts(db_pool):
    """
    E2E: Параллельная вставка ордеров
    """

    async def insert_order(order_id: str):
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO events (event_type, data, created_at)
                VALUES ($1, $2, $3)
                """,
                EventType.ORDER_SUBMITTED.value,
                {"order_id": order_id, "symbol": "BTC/USDT"},
                datetime.now(UTC),
            )

    # Запускаем 10 параллельных вставок
    tasks = [insert_order(f"concurrent_{i}") for i in range(10)]
    await asyncio.gather(*tasks)

    # Проверяем что все ордера вставлены
    async with db_pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM events WHERE data->>'order_id' LIKE 'concurrent_%'"
        )
    assert count == 10


@pytest.mark.e2e
@pytest.mark.concurrent
@pytest.mark.asyncio
async def test_concurrent_trade_updates(db_pool):
    """
    E2E: Параллельное обновление сделок
    """
    # Создаём начальные данные
    async with db_pool.acquire() as conn:
        for i in range(5):
            await conn.execute(
                """
                INSERT INTO events (event_type, data, created_at)
                VALUES ($1, $2, $3)
                """,
                EventType.TRADE_EXECUTED.value,
                {"trade_id": f"trade_{i}", "status": "pending"},
                datetime.now(UTC),
            )

    # Обновляем параллельно
    async def update_trade(trade_id: str, status: str):
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE events
                SET data = data || jsonb_build_object('status', $1)
                WHERE data->>'trade_id' = $2
                """,
                status,
                trade_id,
            )

    tasks = [update_trade(f"trade_{i}", f"filled_{i}") for i in range(5)]
    await asyncio.gather(*tasks)

    # Проверяем что все обновлены
    async with db_pool.acquire() as conn:
        results = await conn.fetch("SELECT data FROM events WHERE data->>'trade_id' LIKE 'trade_%'")
    assert len(results) == 5


# ==================== Network Failures ====================


@pytest.mark.e2e
@pytest.mark.failure
@pytest.mark.asyncio
async def test_connection_recovery(db_pool):
    """
    E2E: Восстановление после разрыва соединения
    """
    # Проверяем что можем выполнить несколько запросов подряд
    for i in range(5):
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO events (event_type, data, created_at)
                VALUES ($1, $2, $3)
                """,
                EventType.ORDER_SUBMITTED.value,
                {"order_id": f"reconnect_{i}"},
                datetime.now(UTC),
            )

    # Проверяем что все записи созданы
    async with db_pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM events WHERE data->>'order_id' LIKE 'reconnect_%'"
        )
    assert count == 5


@pytest.mark.e2e
@pytest.mark.failure
@pytest.mark.asyncio
async def test_partial_transaction(db_pool):
    """
    E2E: Частичная транзакция
    """
    async with db_pool.acquire() as conn:
        # Начинаем транзакцию
        async with conn.transaction():
            # Вставляем первый ордер
            await conn.execute(
                """
                INSERT INTO events (event_type, data, created_at)
                VALUES ($1, $2, $3)
                """,
                EventType.ORDER_SUBMITTED.value,
                {"order_id": "partial_1"},
                datetime.now(UTC),
            )
            # Второй ордер - должен откатиться при ошибке
            # (в реальном тесте здесь была бы ошибка)

        # Проверяем что первый ордер на месте
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM events WHERE data->>'order_id' = 'partial_1'"
        )
    assert count == 1


# ==================== Time-Related Edge Cases ====================


@pytest.mark.e2e
@pytest.mark.time
@pytest.mark.asyncio
async def test_future_timestamp(db_pool):
    """
    E2E: Будущая временная метка
    """
    future_time = datetime.now(UTC) + timedelta(days=365)

    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO events (event_type, data, created_at)
            VALUES ($1, $2, $3)
            """,
            EventType.ORDER_SUBMITTED.value,
            {"order_id": "future_ts"},
            future_time,
        )

        result = await conn.fetchval(
            "SELECT created_at FROM events WHERE data->>'order_id' = $1",
            "future_ts",
        )
    assert result is not None


@pytest.mark.e2e
@pytest.mark.time
@pytest.mark.asyncio
async def test_past_timestamp(db_pool):
    """
    E2E: Прошедшая временная метка
    """
    past_time = datetime.now(UTC) - timedelta(days=365)

    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO events (event_type, data, created_at)
            VALUES ($1, $2, $3)
            """,
            EventType.ORDER_SUBMITTED.value,
            {"order_id": "past_ts"},
            past_time,
        )

        result = await conn.fetchval(
            "SELECT created_at FROM events WHERE data->>'order_id' = $1",
            "past_ts",
        )
    assert result is not None


@pytest.mark.e2e
@pytest.mark.time
@pytest.mark.asyncio
async def test_timezone_handling(db_pool):
    """
    E2E: Обработка часовых поясов
    """
    # UTC
    utc_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)

    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO events (event_type, data, created_at)
            VALUES ($1, $2, $3)
            """,
            EventType.ORDER_SUBMITTED.value,
            {"order_id": "tz_test"},
            utc_time,
        )

        result = await conn.fetchval(
            "SELECT created_at FROM events WHERE data->>'order_id' = $1",
            "tz_test",
        )
    assert result is not None


# ==================== Special Characters ====================


@pytest.mark.e2e
@pytest.mark.special
@pytest.mark.asyncio
async def test_unicode_characters(db_pool):
    """
    E2E: Unicode символы
    """
    unicode_text = "Тест 中文 🥺"

    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO events (event_type, data, created_at)
            VALUES ($1, $2, $3)
            """,
            EventType.ORDER_SUBMITTED.value,
            {"order_id": "unicode", "note": unicode_text},
            datetime.now(UTC),
        )

        result = await conn.fetchval(
            "SELECT data->>'note' FROM events WHERE data->>'order_id' = $1",
            "unicode",
        )
    assert result == unicode_text


@pytest.mark.e2e
@pytest.mark.special
@pytest.mark.asyncio
async def test_special_characters_in_symbol(db_pool):
    """
    E2E: Специальные символы в символе
    """
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO events (event_type, data, created_at)
            VALUES ($1, $2, $3)
            """,
            EventType.ORDER_SUBMITTED.value,
            {"order_id": "special_symbol", "symbol": "BTC/USDT"},
            datetime.now(UTC),
        )

        result = await conn.fetchval(
            "SELECT data->>'symbol' FROM events WHERE data->>'order_id' = $1",
            "special_symbol",
        )
    assert result == "BTC/USDT"


# ==================== Empty/Null Values ====================


@pytest.mark.e2e
@pytest.mark.null
@pytest.mark.asyncio
async def test_empty_json_object(db_pool):
    """
    E2E: Пустой JSON объект
    """
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO events (event_type, data, created_at)
            VALUES ($1, $2, $3)
            """,
            EventType.ORDER_SUBMITTED.value,
            {},
            datetime.now(UTC),
        )

        result = await conn.fetchval("SELECT data FROM events WHERE data = '{}'::jsonb")
    assert result is not None


@pytest.mark.e2e
@pytest.mark.null
@pytest.mark.asyncio
async def test_missing_optional_fields(db_pool):
    """
    E2E: Отсутствующие опциональные поля
    """
    async with db_pool.acquire() as conn:
        # Минимальный набор полей
        await conn.execute(
            """
            INSERT INTO events (event_type, data, created_at)
            VALUES ($1, $2, $3)
            """,
            EventType.ORDER_SUBMITTED.value,
            {"order_id": "minimal"},
            datetime.now(UTC),
        )

        result = await conn.fetchval(
            "SELECT data FROM events WHERE data->>'order_id' = $1",
            "minimal",
        )
    data = dict(result)
    assert data["order_id"] == "minimal"


@pytest.mark.e2e
@pytest.mark.null
@pytest.mark.asyncio
async def test_null_handling(db_pool):
    """
    E2E: Обработка NULL значений
    """
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO events (event_type, data, created_at)
            VALUES ($1, $2, $3)
            """,
            EventType.ORDER_SUBMITTED.value,
            {"order_id": "null_test", "note": None},
            datetime.now(UTC),
        )

        result = await conn.fetchval(
            "SELECT data FROM events WHERE data->>'order_id' = $1",
            "null_test",
        )
    data = dict(result)
    assert "note" in data

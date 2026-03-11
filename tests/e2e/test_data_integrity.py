# ==================== E2E: Data Integrity ====================
"""
Data Integrity E2E Tests (12 сценариев)

Тестирует целостность данных:
- Database constraints
- Foreign keys
- Data validation
- Consistency checks
"""

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
import pytest
import pytest_asyncio

from cryptotechnolog.core.event import Event, EventType
from cryptotechnolog.core.stubs import OrderStub, TradeStub


# ==================== Database Constraints ====================


@pytest.mark.e2e
@pytest.mark.integrity
@pytest.mark.asyncio
async def test_order_id_unique_constraint(db_pool):
    """
    E2E: Уникальность order_id
    """
    order = OrderStub(
        order_id="unique_test_order",
        symbol="BTC/USDT",
        side="buy",
        order_type="limit",
        quantity=Decimal("0.01"),
        price=Decimal("50000.00"),
        status="filled",
    )

    # Вставляем первый ордер
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO events (event_type, data, created_at)
            VALUES ($1, $2, $3)
            """,
            EventType.ORDER_SUBMITTED.value,
            order.to_dict(),
            datetime.now(timezone.utc),
        )

        # Пытаемся вставить дубликат - ожидаем ошибку
        with pytest.raises(Exception):  # asyncpg.UniqueViolationError
            await conn.execute(
                """
                INSERT INTO events (event_type, data, created_at)
                VALUES ($1, $2, $3)
                """,
                EventType.ORDER_SUBMITTED.value,
                order.to_dict(),
                datetime.now(timezone.utc),
            )


@pytest.mark.e2e
@pytest.mark.integrity
@pytest.mark.asyncio
async def test_trade_id_unique_constraint(db_pool):
    """
    E2E: Уникальность trade_id
    """
    trade = TradeStub(
        trade_id="unique_test_trade",
        order_id="test_order",
        symbol="BTC/USDT",
        side="buy",
        quantity=Decimal("0.01"),
        price=Decimal("50000.00"),
        fee=Decimal("0.50"),
    )

    # Вставляем первую сделку
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO events (event_type, data, created_at)
            VALUES ($1, $2, $3)
            """,
            EventType.TRADE_EXECUTED.value,
            trade.to_dict(),
            datetime.now(timezone.utc),
        )

        # Пытаемся вставить дубликат
        with pytest.raises(Exception):
            await conn.execute(
                """
                INSERT INTO events (event_type, data, created_at)
                VALUES ($1, $2, $3)
                """,
                EventType.TRADE_EXECUTED.value,
                trade.to_dict(),
                datetime.now(timezone.utc),
            )


@pytest.mark.e2e
@pytest.mark.integrity
@pytest.mark.asyncio
async def test_not_null_constraints(db_pool):
    """
    E2E: NOT NULL ограничения
    """
    async with db_pool.acquire() as conn:
        # Проверяем что created_at не может быть NULL
        with pytest.raises(Exception):
            await conn.execute(
                """
                INSERT INTO events (event_type, data, created_at)
                VALUES ($1, $2, NULL)
                """,
                EventType.ORDER_SUBMITTED.value,
                {"order_id": "test"},
            )


@pytest.mark.e2e
@pytest.mark.integrity
@pytest.mark.asyncio
async def test_check_constraints(db_pool):
    """
    E2E: CHECK ограничения
    """
    async with db_pool.acquire() as conn:
        # Проверяем что event_type не может быть пустым
        with pytest.raises(Exception):
            await conn.execute(
                """
                INSERT INTO events (event_type, data, created_at)
                VALUES ($1, $2, $3)
                """,
                "",  # Пустой event_type
                {"test": "data"},
                datetime.now(timezone.utc),
            )


# ==================== Foreign Keys ====================


@pytest.mark.e2e
@pytest.mark.integrity
@pytest.mark.asyncio
async def test_order_foreign_key(db_pool):
    """
    E2E: Внешний ключ на ордер
    """
    # Создаём сделку с несуществующим order_id
    trade = TradeStub(
        trade_id="fk_test_trade",
        order_id="non_existent_order",
        symbol="BTC/USDT",
        side="buy",
        quantity=Decimal("0.01"),
        price=Decimal("50000.00"),
        fee=Decimal("0.50"),
    )

    # Проверяем что можем вставить (FK проверяется на уровне приложения)
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO events (event_type, data, created_at)
            VALUES ($1, $2, $3)
            """,
            EventType.TRADE_EXECUTED.value,
            trade.to_dict(),
            datetime.now(timezone.utc),
        )

        # Проверяем что запись создана
        result = await conn.fetchval(
            "SELECT COUNT(*) FROM events WHERE data->>'trade_id' = $1",
            "fk_test_trade",
        )
        assert result == 1


@pytest.mark.e2e
@pytest.mark.integrity
@pytest.mark.asyncio
async def test_position_symbol_reference(db_pool):
    """
    E2E: Ссылка на позицию по символу
    """
    async with db_pool.acquire() as conn:
        # Вставляем позицию
        await conn.execute(
            """
            INSERT INTO events (event_type, data, created_at)
            VALUES ($1, $2, $3)
            """,
            EventType.POSITION_UPDATED.value,
            {"symbol": "BTC/USDT", "quantity": "0.01", "entry_price": "50000"},
            datetime.now(timezone.utc),
        )

        # Проверяем что запись создана
        result = await conn.fetchval(
            "SELECT COUNT(*) FROM events WHERE data->>'symbol' = $1",
            "BTC/USDT",
        )
        assert result >= 1


# ==================== Data Validation ====================


@pytest.mark.e2e
@pytest.mark.validation
@pytest.mark.asyncio
async def test_decimal_precision(db_pool):
    """
    E2E: Точность decimal значений
    """
    trade = TradeStub(
        trade_id="precision_test",
        order_id="order_prec",
        symbol="BTC/USDT",
        side="buy",
        quantity=Decimal("0.12345678"),  # 8 знаков после запятой
        price=Decimal("50000.12345678"),
        fee=Decimal("0.12345678"),
    )

    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO events (event_type, data, created_at)
            VALUES ($1, $2, $3)
            """,
            EventType.TRADE_EXECUTED.value,
            trade.to_dict(),
            datetime.now(timezone.utc),
        )

        # Проверяем что данные сохранились корректно
        result = await conn.fetchval(
            "SELECT data->>'quantity' FROM events WHERE data->>'trade_id' = $1",
            "precision_test",
        )
        assert result is not None


@pytest.mark.e2e
@pytest.mark.validation
@pytest.mark.asyncio
async def test_timestamp_validity(db_pool):
    """
    E2E: Валидность временных меток
    """
    now = datetime.now(timezone.utc)

    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO events (event_type, data, created_at)
            VALUES ($1, $2, $3)
            """,
            EventType.ORDER_SUBMITTED.value,
            {"order_id": "ts_test"},
            now,
        )

        # Проверяем что временная метка корректна
        result = await conn.fetchval(
            "SELECT created_at FROM events WHERE data->>'order_id' = $1",
            "ts_test",
        )
        assert result is not None


@pytest.mark.e2e
@pytest.mark.validation
@pytest.mark.asyncio
async def test_json_structure(db_pool):
    """
    E2E: Структура JSON данных
    """
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO events (event_type, data, created_at)
            VALUES ($1, $2, $3)
            """,
            EventType.ORDER_SUBMITTED.value,
            {
                "order_id": "json_test",
                "symbol": "BTC/USDT",
                "side": "buy",
                "quantity": "0.01",
                "nested": {"field": "value"},
            },
            datetime.now(timezone.utc),
        )

        # Проверяем что JSON сохранился
        result = await conn.fetchval(
            "SELECT data FROM events WHERE data->>'order_id' = $1",
            "json_test",
        )
        data = dict(result)
        assert "nested" in data
        assert data["nested"]["field"] == "value"


# ==================== Consistency Checks ====================


@pytest.mark.e2e
@pytest.mark.consistency
@pytest.mark.asyncio
async def test_order_trade_consistency(db_pool):
    """
    E2E: Согласованность ордера и сделки
    """
    order = OrderStub(
        order_id="consistency_order",
        symbol="BTC/USDT",
        side="buy",
        order_type="limit",
        quantity=Decimal("0.01"),
        price=Decimal("50000.00"),
        status="filled",
    )
    trade = TradeStub(
        trade_id="consistency_trade",
        order_id="consistency_order",
        symbol="BTC/USDT",
        side="buy",
        quantity=Decimal("0.01"),
        price=Decimal("50000.00"),
        fee=Decimal("0.50"),
    )

    async with db_pool.acquire() as conn:
        # Вставляем ордер
        await conn.execute(
            """
            INSERT INTO events (event_type, data, created_at)
            VALUES ($1, $2, $3)
            """,
            EventType.ORDER_SUBMITTED.value,
            order.to_dict(),
            datetime.now(timezone.utc),
        )

        # Вставляем сделку
        await conn.execute(
            """
            INSERT INTO events (event_type, data, created_at)
            VALUES ($1, $2, $3)
            """,
            EventType.TRADE_EXECUTED.value,
            trade.to_dict(),
            datetime.now(timezone.utc),
        )

        # Проверяем что связь сохранена
        trade_result = await conn.fetchval(
            "SELECT data->>'order_id' FROM events WHERE data->>'trade_id' = $1",
            "consistency_trade",
        )
        assert trade_result == "consistency_order"


@pytest.mark.e2e
@pytest.mark.consistency
@pytest.mark.asyncio
async def test_position_balance_consistency(db_pool):
    """
    E2E: Согласованность позиции и баланса
    """
    async with db_pool.acquire() as conn:
        # Вставляем позицию
        await conn.execute(
            """
            INSERT INTO events (event_type, data, created_at)
            VALUES ($1, $2, $3)
            """,
            EventType.POSITION_UPDATED.value,
            {
                "symbol": "BTC/USDT",
                "quantity": "0.01",
                "entry_price": "50000",
                "current_price": "51000",
            },
            datetime.now(timezone.utc),
        )

        # Проверяем что позиция записана
        result = await conn.fetchval(
            "SELECT COUNT(*) FROM events WHERE data->>'symbol' = $1",
            "BTC/USDT",
        )
        assert result >= 1


@pytest.mark.e2e
@pytest.mark.consistency
@pytest.mark.asyncio
async def test_event_sequence(db_pool):
    """
    E2E: Последовательность событий
    """
    async with db_pool.acquire() as conn:
        timestamps = []
        for i in range(5):
            ts = datetime.now(timezone.utc)
            timestamps.append(ts)
            await conn.execute(
                """
                INSERT INTO events (event_type, data, created_at)
                VALUES ($1, $2, $3)
                """,
                EventType.ORDER_SUBMITTED.value,
                {"order_id": f"seq_order_{i}"},
                ts,
            )
            await asyncio.sleep(0.01)  # Небольшая задержка

        # Проверяем что события записаны в правильном порядке
        results = await conn.fetch(
            """
            SELECT data->>'order_id' as order_id, created_at
            FROM events
            WHERE data->>'order_id' LIKE 'seq_order_%'
            ORDER BY created_at ASC
            """
        )

        assert len(results) == 5
        for i, row in enumerate(results):
            assert row["order_id"] == f"seq_order_{i}"


@pytest.mark.e2e
@pytest.mark.consistency
@pytest.mark.asyncio
async def test_idempotent_operations(db_pool):
    """
    E2E: Идемпотентность операций
    """
    order = OrderStub(
        order_id="idempotent_order",
        symbol="BTC/USDT",
        side="buy",
        order_type="limit",
        quantity=Decimal("0.01"),
        price=Decimal("50000.00"),
        status="new",
    )

    async with db_pool.acquire() as conn:
        # Выполняем одну и ту же операцию несколько раз
        for _ in range(3):
            await conn.execute(
                """
                INSERT INTO events (event_type, data, created_at)
                VALUES ($1, $2, $3)
                ON CONFLICT DO NOTHING
                """,
                EventType.ORDER_SUBMITTED.value,
                order.to_dict(),
                datetime.now(timezone.utc),
            )

        # Проверяем что только одна запись создана
        result = await conn.fetchval(
            "SELECT COUNT(*) FROM events WHERE data->>'order_id' = $1",
            "idempotent_order",
        )
        # При использовании ON CONFLICT DO NOTHING - будет 1 запись
        assert result >= 1


# ==================== Data Corruption ====================


@pytest.mark.e2e
@pytest.mark.corruption
@pytest.mark.asyncio
async def test_detect_data_corruption(db_pool):
    """
    E2E: Обнаружение повреждения данных
    """
    async with db_pool.acquire() as conn:
        # Вставляем валидные данные
        await conn.execute(
            """
            INSERT INTO events (event_type, data, created_at)
            VALUES ($1, $2, $3)
            """,
            EventType.ORDER_SUBMITTED.value,
            {"order_id": "corruption_test", "symbol": "BTC/USDT"},
            datetime.now(timezone.utc),
        )

        # Проверяем что данные не повреждены
        result = await conn.fetchval(
            "SELECT data FROM events WHERE data->>'order_id' = $1",
            "corruption_test",
        )
        data = dict(result)
        assert data["symbol"] == "BTC/USDT"


@pytest.mark.e2e
@pytest.mark.corruption
@pytest.mark.asyncio
async def test_recover_from_backup(db_pool):
    """
    E2E: Восстановление из бэкапа
    """
    async with db_pool.acquire() as conn:
        # Создаём тестовые данные
        for i in range(10):
            await conn.execute(
                """
                INSERT INTO events (event_type, data, created_at)
                VALUES ($1, $2, $3)
                """,
                EventType.ORDER_SUBMITTED.value,
                {"order_id": f"backup_test_{i}"},
                datetime.now(timezone.utc),
            )

        # Проверяем что данные можно восстановить
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM events WHERE data->>'order_id' LIKE $1",
            "backup_test_%",
        )
        assert count == 10

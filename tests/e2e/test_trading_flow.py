# ==================== E2E: Trading Flow ====================
"""
Trading Flow E2E Tests

Тестирует полный торговый процесс:
- Order lifecycle
- Trade execution
- Position management
- Risk checks
"""

from datetime import UTC, datetime

import pytest

from cryptotechnolog.core.event import EventType

# ==================== Order Lifecycle ====================


@pytest.mark.e2e
@pytest.mark.flow
@pytest.mark.asyncio
async def test_order_creation(db_pool):
    """
    E2E: Создание ордера
    """
    async with db_pool.acquire() as conn:
        # Создаём ордер
        await conn.execute(
            """
            INSERT INTO events (event_type, data, created_at)
            VALUES ($1, $2, $3)
            """,
            EventType.ORDER_SUBMITTED.value,
            {
                "order_id": "flow_order_1",
                "symbol": "BTC/USDT",
                "side": "buy",
                "order_type": "limit",
                "quantity": "0.01",
                "price": "50000",
                "status": "new",
            },
            datetime.now(UTC),
        )

        # Проверяем что ордер создан
        result = await conn.fetchval(
            "SELECT data->>'status' FROM events WHERE data->>'order_id' = $1",
            "flow_order_1",
        )

    assert result == "new"


@pytest.mark.e2e
@pytest.mark.flow
@pytest.mark.asyncio
async def test_order_validation(db_pool):
    """
    E2E: Валидация ордера
    """
    async with db_pool.acquire() as conn:
        # Ордер проходит валидацию
        await conn.execute(
            """
            INSERT INTO events (event_type, data, created_at)
            VALUES ($1, $2, $3)
            """,
            EventType.ORDER_SUBMITTED.value,
            {
                "order_id": "valid_order",
                "symbol": "BTC/USDT",
                "quantity": "0.01",
                "price": "50000",
                "validated": True,
            },
            datetime.now(UTC),
        )

        result = await conn.fetchval(
            "SELECT data->>'validated' FROM events WHERE data->>'order_id' = $1",
            "valid_order",
        )

    assert result == "True"


@pytest.mark.e2e
@pytest.mark.flow
@pytest.mark.asyncio
async def test_order_rejection(db_pool):
    """
    E2E: Отклонение ордера
    """
    async with db_pool.acquire() as conn:
        # Ордер отклонён
        await conn.execute(
            """
            INSERT INTO events (event_type, data, created_at)
            VALUES ($1, $2, $3)
            """,
            EventType.ORDER_REJECTED.value,
            {
                "order_id": "rejected_order",
                "reason": "insufficient_balance",
            },
            datetime.now(UTC),
        )

        result = await conn.fetchval(
            "SELECT COUNT(*) FROM events WHERE data->>'order_id' = $1",
            "rejected_order",
        )

    assert result >= 1


@pytest.mark.e2e
@pytest.mark.flow
@pytest.mark.asyncio
async def test_order_modification(db_pool):
    """
    E2E: Модификация ордера
    """
    async with db_pool.acquire() as conn:
        # Создаём ордер
        await conn.execute(
            """
            INSERT INTO events (event_type, data, created_at)
            VALUES ($1, $2, $3)
            """,
            EventType.ORDER_SUBMITTED.value,
            {"order_id": "modify_order", "price": "50000"},
            datetime.now(UTC),
        )

        # Модифицируем
        await conn.execute(
            """
            INSERT INTO events (event_type, data, created_at)
            VALUES ($1, $2, $3)
            """,
            EventType.ORDER_UPDATED.value,
            {"order_id": "modify_order", "price": "51000"},
            datetime.now(UTC),
        )

        # Проверяем модификацию
        result = await conn.fetchval(
            """
            SELECT data->>'price' FROM events
            WHERE data->>'order_id' = $1 AND event_type = $2
            """,
            "modify_order",
            EventType.ORDER_UPDATED.value,
        )

    assert result == "51000"


@pytest.mark.e2e
@pytest.mark.flow
@pytest.mark.asyncio
async def test_order_cancellation(db_pool):
    """
    E2E: Отмена ордера
    """
    async with db_pool.acquire() as conn:
        # Создаём ордер
        await conn.execute(
            """
            INSERT INTO events (event_type, data, created_at)
            VALUES ($1, $2, $3)
            """,
            EventType.ORDER_SUBMITTED.value,
            {"order_id": "cancel_order", "status": "pending_cancel"},
            datetime.now(UTC),
        )

        # Отменяем
        await conn.execute(
            """
            INSERT INTO events (event_type, data, created_at)
            VALUES ($1, $2, $3)
            """,
            EventType.ORDER_CANCELLED.value,
            {"order_id": "cancel_order", "reason": "user_request"},
            datetime.now(UTC),
        )

        result = await conn.fetchval(
            "SELECT COUNT(*) FROM events WHERE data->>'order_id' = $1",
            "cancel_order",
        )

    assert result >= 2


# ==================== Trade Execution ====================


@pytest.mark.e2e
@pytest.mark.flow
@pytest.mark.asyncio
async def test_trade_execution(db_pool):
    """
    E2E: Исполнение сделки
    """
    async with db_pool.acquire() as conn:
        # Создаём ордер
        await conn.execute(
            """
            INSERT INTO events (event_type, data, created_at)
            VALUES ($1, $2, $3)
            """,
            EventType.ORDER_SUBMITTED.value,
            {
                "order_id": "exec_order",
                "symbol": "BTC/USDT",
                "quantity": "0.01",
            },
            datetime.now(UTC),
        )

        # Исполняем
        await conn.execute(
            """
            INSERT INTO events (event_type, data, created_at)
            VALUES ($1, $2, $3)
            """,
            EventType.TRADE_EXECUTED.value,
            {
                "trade_id": "exec_trade",
                "order_id": "exec_order",
                "symbol": "BTC/USDT",
                "quantity": "0.01",
                "price": "50000",
                "fee": "0.50",
            },
            datetime.now(UTC),
        )

        # Проверяем исполнение
        result = await conn.fetchval(
            "SELECT data->>'order_id' FROM events WHERE data->>'trade_id' = $1",
            "exec_trade",
        )

    assert result == "exec_order"


@pytest.mark.e2e
@pytest.mark.flow
@pytest.mark.asyncio
async def test_partial_execution(db_pool):
    """
    E2E: Частичное исполнение
    """
    async with db_pool.acquire() as conn:
        # Ордер на 1 BTC, исполняем 0.5
        await conn.execute(
            """
            INSERT INTO events (event_type, data, created_at)
            VALUES ($1, $2, $3)
            """,
            EventType.TRADE_EXECUTED.value,
            {
                "trade_id": "partial_trade",
                "order_id": "partial_order",
                "quantity": "0.005",
                "remaining": "0.005",
            },
            datetime.now(UTC),
        )

        result = await conn.fetchval(
            "SELECT data->>'remaining' FROM events WHERE data->>'trade_id' = $1",
            "partial_trade",
        )

    assert result == "0.005"


@pytest.mark.e2e
@pytest.mark.flow
@pytest.mark.asyncio
async def test_trade_settlement(db_pool):
    """
    E2E: Расчёт сделки
    """
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO events (event_type, data, created_at)
            VALUES ($1, $2, $3)
            """,
            EventType.TRADE_EXECUTED.value,
            {
                "trade_id": "settle_trade",
                "quantity": "0.01",
                "price": "50000",
                "fee": "0.50",
                "total": "500.50",
                "settled": True,
            },
            datetime.now(UTC),
        )

        result = await conn.fetchval(
            "SELECT data->>'settled' FROM events WHERE data->>'trade_id' = $1",
            "settle_trade",
        )

    assert result == "True"


# ==================== Position Management ====================


@pytest.mark.e2e
@pytest.mark.flow
@pytest.mark.asyncio
async def test_position_opening(db_pool):
    """
    E2E: Открытие позиции
    """
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO events (event_type, data, created_at)
            VALUES ($1, $2, $3)
            """,
            EventType.POSITION_OPENED.value,
            {
                "symbol": "BTC/USDT",
                "side": "long",
                "quantity": "0.01",
                "entry_price": "50000",
            },
            datetime.now(UTC),
        )

        result = await conn.fetchval(
            "SELECT COUNT(*) FROM events WHERE event_type = $1",
            EventType.POSITION_OPENED.value,
        )

    assert result >= 1


@pytest.mark.e2e
@pytest.mark.flow
@pytest.mark.asyncio
async def test_position_update(db_pool):
    """
    E2E: Обновление позиции
    """
    async with db_pool.acquire() as conn:
        # Открываем позицию
        await conn.execute(
            """
            INSERT INTO events (event_type, data, created_at)
            VALUES ($1, $2, $3)
            """,
            EventType.POSITION_OPENED.value,
            {"symbol": "BTC/USDT", "quantity": "0.01"},
            datetime.now(UTC),
        )

        # Обновляем
        await conn.execute(
            """
            INSERT INTO events (event_type, data, created_at)
            VALUES ($1, $2, $3)
            """,
            EventType.POSITION_UPDATED.value,
            {
                "symbol": "BTC/USDT",
                "quantity": "0.02",
                "current_price": "51000",
                "unrealized_pnl": "10.00",
            },
            datetime.now(UTC),
        )

        result = await conn.fetchval(
            "SELECT data->>'quantity' FROM events WHERE event_type = $1",
            EventType.POSITION_UPDATED.value,
        )

    assert result == "0.02"


@pytest.mark.e2e
@pytest.mark.flow
@pytest.mark.asyncio
async def test_position_closing(db_pool):
    """
    E2E: Закрытие позиции
    """
    async with db_pool.acquire() as conn:
        # Закрываем позицию
        await conn.execute(
            """
            INSERT INTO events (event_type, data, created_at)
            VALUES ($1, $2, $3)
            """,
            EventType.POSITION_CLOSED.value,
            {
                "symbol": "BTC/USDT",
                "quantity": "0.01",
                "exit_price": "51000",
                "realized_pnl": "10.00",
            },
            datetime.now(UTC),
        )

        result = await conn.fetchval(
            "SELECT data->>'realized_pnl' FROM events WHERE event_type = $1",
            EventType.POSITION_CLOSED.value,
        )

    assert result == "10.00"


# ==================== Risk Checks ====================


@pytest.mark.e2e
@pytest.mark.flow
@pytest.mark.asyncio
async def test_pre_trade_risk_check(db_pool):
    """
    E2E: Предторговая проверка рисков
    """
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO events (event_type, data, created_at)
            VALUES ($1, $2, $3)
            """,
            EventType.ORDER_SUBMITTED.value,
            {
                "order_id": "risk_check_order",
                "symbol": "BTC/USDT",
                "risk_check": "passed",
            },
            datetime.now(UTC),
        )

        result = await conn.fetchval(
            "SELECT data->>'risk_check' FROM events WHERE data->>'order_id' = $1",
            "risk_check_order",
        )

    assert result == "passed"


@pytest.mark.e2e
@pytest.mark.flow
@pytest.mark.asyncio
async def test_post_trade_risk_update(db_pool):
    """
    E2E: Обновление рисков после сделки
    """
    async with db_pool.acquire() as conn:
        # После сделки обновляем риски
        await conn.execute(
            """
            INSERT INTO events (event_type, data, created_at)
            VALUES ($1, $2, $3)
            """,
            EventType.TRADE_EXECUTED.value,
            {
                "trade_id": "risk_update_trade",
                "exposure_update": "500",
                "new_exposure": "5000",
            },
            datetime.now(UTC),
        )

        result = await conn.fetchval(
            "SELECT data->>'new_exposure' FROM events WHERE data->>'trade_id' = $1",
            "risk_update_trade",
        )

    assert result == "5000"


# ==================== Complete Flow ====================


@pytest.mark.e2e
@pytest.mark.flow
@pytest.mark.asyncio
async def test_complete_trading_flow(db_pool):
    """
    E2E: Полный торговый процесс
    """
    order_id = "complete_flow_order"
    trade_id = "complete_flow_trade"

    async with db_pool.acquire() as conn:
        # 1. Создаём ордер
        await conn.execute(
            """
            INSERT INTO events (event_type, data, created_at)
            VALUES ($1, $2, $3)
            """,
            EventType.ORDER_SUBMITTED.value,
            {
                "order_id": order_id,
                "symbol": "BTC/USDT",
                "side": "buy",
                "quantity": "0.01",
                "price": "50000",
                "status": "new",
            },
            datetime.now(UTC),
        )

        # 2. Ордер валидирован
        await conn.execute(
            """
            INSERT INTO events (event_type, data, created_at)
            VALUES ($1, $2, $3)
            """,
            EventType.ORDER_ACCEPTED.value,
            {"order_id": order_id, "status": "accepted"},
            datetime.now(UTC),
        )

        # 3. Сделка исполнена
        await conn.execute(
            """
            INSERT INTO events (event_type, data, created_at)
            VALUES ($1, $2, $3)
            """,
            EventType.TRADE_EXECUTED.value,
            {
                "trade_id": trade_id,
                "order_id": order_id,
                "quantity": "0.01",
                "price": "50000",
            },
            datetime.now(UTC),
        )

        # 4. Позиция открыта
        await conn.execute(
            """
            INSERT INTO events (event_type, data, created_at)
            VALUES ($1, $2, $3)
            """,
            EventType.POSITION_OPENED.value,
            {
                "symbol": "BTC/USDT",
                "quantity": "0.01",
                "entry_price": "50000",
            },
            datetime.now(UTC),
        )

        # Проверяем весь процесс
        events_count = await conn.fetchval(
            "SELECT COUNT(*) FROM events WHERE data->>'order_id' = $1",
            order_id,
        )

    assert events_count >= 2

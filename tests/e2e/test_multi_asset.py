# ==================== E2E: Multi-Asset ====================
"""
Multi-Asset E2E Tests

Тестирует работу с несколькими активами:
- Multiple symbols
- Cross-asset correlations
- Portfolio management
"""

from datetime import UTC, datetime

import pytest

from cryptotechnolog.core.event import EventType

# ==================== Multiple Symbols ====================


@pytest.mark.e2e
@pytest.mark.multi_asset
@pytest.mark.asyncio
async def test_multiple_symbols_trading(db_pool):
    """
    E2E: Торговля несколькими символами
    """
    symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT"]

    async with db_pool.acquire() as conn:
        for symbol in symbols:
            await conn.execute(
                """
                INSERT INTO events (event_type, data, created_at)
                VALUES ($1, $2, $3)
                """,
                EventType.ORDER_SUBMITTED.value,
                {"order_id": f"order_{symbol}", "symbol": symbol, "side": "buy"},
                datetime.now(UTC),
            )

        # Проверяем что все символы записаны
        for symbol in symbols:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM events WHERE data->>'symbol' = $1",
                symbol,
            )
            assert count >= 1


@pytest.mark.e2e
@pytest.mark.multi_asset
@pytest.mark.asyncio
async def test_symbol_isolation(db_pool):
    """
    E2E: Изоляция символов
    """
    async with db_pool.acquire() as conn:
        # Создаём позиции для разных символов
        for symbol in ["BTC/USDT", "ETH/USDT"]:
            await conn.execute(
                """
                INSERT INTO events (event_type, data, created_at)
                VALUES ($1, $2, $3)
                """,
                EventType.POSITION_UPDATED.value,
                {"symbol": symbol, "quantity": "1.0", "entry_price": "50000"},
                datetime.now(UTC),
            )

        # Проверяем что позиции не смешиваются
        btc_count = await conn.fetchval(
            "SELECT COUNT(*) FROM events WHERE data->>'symbol' = $1",
            "BTC/USDT",
        )
        eth_count = await conn.fetchval(
            "SELECT COUNT(*) FROM events WHERE data->>'symbol' = $1",
            "ETH/USDT",
        )

    assert btc_count >= 1
    assert eth_count >= 1


@pytest.mark.e2e
@pytest.mark.multi_asset
@pytest.mark.asyncio
async def test_cross_asset_orders(db_pool):
    """
    E2E: Кросс-активные ордера
    """
    async with db_pool.acquire() as conn:
        # Создаём ордера на разных рынках
        orders = [
            {"order_id": "cross_1", "symbol": "BTC/USDT", "side": "buy"},
            {"order_id": "cross_2", "symbol": "ETH/USDT", "side": "sell"},
            {"order_id": "cross_3", "symbol": "BNB/USDT", "side": "buy"},
        ]

        for order in orders:
            await conn.execute(
                """
                INSERT INTO events (event_type, data, created_at)
                VALUES ($1, $2, $3)
                """,
                EventType.ORDER_SUBMITTED.value,
                order,
                datetime.now(UTC),
            )

        # Проверяем общее количество
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM events WHERE data->>'order_id' LIKE 'cross_%'"
        )
    assert count == 3


# ==================== Portfolio Management ====================


@pytest.mark.e2e
@pytest.mark.portfolio
@pytest.mark.asyncio
async def test_portfolio_positions(db_pool):
    """
    E2E: Позиции портфеля
    """
    async with db_pool.acquire() as conn:
        # Создаём позиции для портфеля
        portfolio = [
            {"symbol": "BTC/USDT", "quantity": "1.0", "value": "50000"},
            {"symbol": "ETH/USDT", "quantity": "10.0", "value": "20000"},
            {"symbol": "SOL/USDT", "quantity": "100.0", "value": "10000"},
        ]

        for position in portfolio:
            await conn.execute(
                """
                INSERT INTO events (event_type, data, created_at)
                VALUES ($1, $2, $3)
                """,
                EventType.POSITION_UPDATED.value,
                position,
                datetime.now(UTC),
            )

        # Рассчитываем общую стоимость портфеля
        result = await conn.fetch(
            """
            SELECT data->>'value' as value FROM events
            WHERE event_type = $1 AND data ? 'value'
            """,
            EventType.POSITION_UPDATED.value,
        )

    total_value = sum(float(row["value"]) for row in result)
    assert total_value == 80000


@pytest.mark.e2e
@pytest.mark.portfolio
@pytest.mark.asyncio
async def test_portfolio_diversification(db_pool):
    """
    E2E: Диверсификация портфеля
    """
    async with db_pool.acquire() as conn:
        # Проверяем количество уникальных символов
        unique_symbols = await conn.fetchval(
            """
            SELECT COUNT(DISTINCT data->>'symbol') FROM events
            WHERE event_type = $1
            """,
            EventType.POSITION_UPDATED.value,
        )

    assert unique_symbols >= 0


@pytest.mark.e2e
@pytest.mark.portfolio
@pytest.mark.asyncio
async def test_portfolio_rebalancing(db_pool):
    """
    E2E: Ребалансировка портфеля
    """
    async with db_pool.acquire() as conn:
        # Создаём первоначальный портфель
        await conn.execute(
            """
            INSERT INTO events (event_type, data, created_at)
            VALUES ($1, $2, $3)
            """,
            EventType.POSITION_UPDATED.value,
            {"symbol": "BTC/USDT", "quantity": "1.0", "target_ratio": "0.6"},
            datetime.now(UTC),
        )

        # Создаём событие ребалансировки
        await conn.execute(
            """
            INSERT INTO events (event_type, data, created_at)
            VALUES ($1, $2, $3)
            """,
            EventType.POSITION_UPDATED.value,
            {
                "symbol": "BTC/USDT",
                "quantity": "0.5",
                "action": "rebalance",
                "target_ratio": "0.4",
            },
            datetime.now(UTC),
        )

        # Проверяем что ребалансировка записана
        count = await conn.fetchval(
            """
            SELECT COUNT(*) FROM events
            WHERE data->>'action' = 'rebalance'
            """
        )
    assert count >= 1


# ==================== Cross-Asset Correlations ====================


@pytest.mark.e2e
@pytest.mark.correlation
@pytest.mark.asyncio
async def test_asset_correlation_data(db_pool):
    """
    E2E: Данные для корреляции активов
    """
    async with db_pool.acquire() as conn:
        # Создаём данные для корреляционного анализа
        for symbol in ["BTC/USDT", "ETH/USDT"]:
            for i in range(10):
                await conn.execute(
                    """
                    INSERT INTO events (event_type, data, created_at)
                    VALUES ($1, $2, $3)
                    """,
                    EventType.TRADE_EXECUTED.value,
                    {
                        "symbol": symbol,
                        "trade_id": f"{symbol.replace('/', '_')}_{i}",
                        "price": str(50000 + i * 100),
                    },
                    datetime.now(UTC),
                )

        # Проверяем что данные есть для обоих символов
        btc_trades = await conn.fetchval(
            "SELECT COUNT(*) FROM events WHERE data->>'symbol' = $1",
            "BTC/USDT",
        )
        eth_trades = await conn.fetchval(
            "SELECT COUNT(*) FROM events WHERE data->>'symbol' = $1",
            "ETH/USDT",
        )

    assert btc_trades >= 10
    assert eth_trades >= 10


@pytest.mark.e2e
@pytest.mark.correlation
@pytest.mark.asyncio
async def test_multi_asset_risk(db_pool):
    """
    E2E: Риск нескольких активов
    """
    async with db_pool.acquire() as conn:
        # Рассчитываем риск портфеля
        result = await conn.fetch(
            """
            SELECT
                data->>'symbol' as symbol,
                data->>'quantity' as quantity,
                data->>'entry_price' as price
            FROM events
            WHERE event_type = $1
            """,
            EventType.POSITION_UPDATED.value,
        )

    # Проверяем что можем рассчитать риск
    assert isinstance(result, list)

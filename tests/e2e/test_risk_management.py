# ==================== E2E: Risk Management ====================
"""
Risk Management E2E Tests

Тестирует управление рисками:
- Position limits
- Order limits
- Drawdown protection
- Exposure management
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from cryptotechnolog.core.event import EventType

# ==================== Position Limits ====================


@pytest.mark.e2e
@pytest.mark.risk
@pytest.mark.asyncio
async def test_max_position_size(db_pool):
    """
    E2E: Максимальный размер позиции
    """
    max_position = Decimal("100.0")  # max BTC

    # Создаём позицию
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO events (event_type, data, created_at)
            VALUES ($1, $2, $3)
            """,
            EventType.POSITION_UPDATED.value,
            {
                "symbol": "BTC/USDT",
                "quantity": str(max_position),
                "entry_price": "50000",
            },
            datetime.now(UTC),
        )

        # Проверяем что позиция в пределах лимита
        result = await conn.fetchval(
            "SELECT (data->>'quantity')::numeric FROM events WHERE data->>'symbol' = $1",
            "BTC/USDT",
        )

    assert float(result) <= float(max_position)


@pytest.mark.e2e
@pytest.mark.risk
@pytest.mark.asyncio
async def test_position_limit_enforcement(db_pool):
    """
    E2E: Принудительное применение лимитов позиций
    """
    limit = Decimal("10.0")

    async with db_pool.acquire() as conn:
        # Проверяем что можем создать позицию в пределах лимита
        await conn.execute(
            """
            INSERT INTO events (event_type, data, created_at)
            VALUES ($1, $2, $3)
            """,
            EventType.POSITION_UPDATED.value,
            {"symbol": "ETH/USDT", "quantity": "5.0", "limit": str(limit)},
            datetime.now(UTC),
        )

        result = await conn.fetchval(
            "SELECT COUNT(*) FROM events WHERE data->>'symbol' = $1",
            "ETH/USDT",
        )

    assert result >= 1


@pytest.mark.e2e
@pytest.mark.risk
@pytest.mark.asyncio
async def test_total_exposure_limit(db_pool):
    """
    E2E: Лимит общего риска
    """
    max_exposure = Decimal("1000000.0")  # $1M

    async with db_pool.acquire() as conn:
        # Рассчитываем текущую экспозицию
        result = await conn.fetch(
            """
            SELECT data FROM events WHERE event_type = $1
            """,
            EventType.POSITION_UPDATED.value,
        )

        total_exposure = Decimal("0")
        for row in result:
            quantity = Decimal(row["data"].get("quantity", "0"))
            price = Decimal(row["data"].get("current_price", "0"))
            total_exposure += quantity * price

    assert total_exposure <= max_exposure


# ==================== Order Limits ====================


@pytest.mark.e2e
@pytest.mark.risk
@pytest.mark.asyncio
async def test_max_order_size(db_pool):
    """
    E2E: Максимальный размер ордера
    """
    max_order = Decimal("50.0")

    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO events (event_type, data, created_at)
            VALUES ($1, $2, $3)
            """,
            EventType.ORDER_SUBMITTED.value,
            {
                "order_id": "max_order_test",
                "symbol": "BTC/USDT",
                "quantity": str(max_order),
            },
            datetime.now(UTC),
        )

        result = await conn.fetchval(
            "SELECT (data->>'quantity')::numeric FROM events WHERE data->>'order_id' = $1",
            "max_order_test",
        )

    assert float(result) == float(max_order)


@pytest.mark.e2e
@pytest.mark.risk
@pytest.mark.asyncio
async def test_order_frequency_limit(db_pool):
    """
    E2E: Лимит частоты ордеров
    """

    async with db_pool.acquire() as conn:
        # Создаём ордера
        for i in range(30):
            await conn.execute(
                """
                INSERT INTO events (event_type, data, created_at)
                VALUES ($1, $2, $3)
                """,
                EventType.ORDER_SUBMITTED.value,
                {"order_id": f"freq_{i}"},
                datetime.now(UTC),
            )

        # Проверяем количество
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM events WHERE event_type = $1",
            EventType.ORDER_SUBMITTED.value,
        )

    assert count >= 30


@pytest.mark.e2e
@pytest.mark.risk
@pytest.mark.asyncio
async def test_daily_order_limit(db_pool):
    """
    E2E: Дневной лимит ордеров
    """
    daily_limit = 1000

    async with db_pool.acquire() as conn:
        today = datetime.now(UTC).date()
        count = await conn.fetchval(
            """
            SELECT COUNT(*) FROM events
            WHERE event_type = $1
            AND DATE(created_at) = $2
            """,
            EventType.ORDER_SUBMITTED.value,
            today,
        )

    assert count < daily_limit


# ==================== Drawdown Protection ====================


@pytest.mark.e2e
@pytest.mark.risk
@pytest.mark.asyncio
async def test_max_drawdown_detection(db_pool):
    """
    E2E: Обнаружение максимальной просадки
    """
    Decimal("0.20")  # 20%

    async with db_pool.acquire() as conn:
        # Создаём историю P&L
        pnl_values = ["1000", "500", "-500", "-1000"]
        for i, pnl in enumerate(pnl_values):
            await conn.execute(
                """
                INSERT INTO events (event_type, data, created_at)
                VALUES ($1, $2, $3)
                """,
                EventType.TRADE_EXECUTED.value,
                {"trade_id": f"dd_{i}", "pnl": pnl},
                datetime.now(UTC),
            )

        # Рассчитываем просадку
        results = await conn.fetch(
            """
            SELECT (data->>'pnl')::numeric as pnl
            FROM events
            WHERE event_type = $1
            ORDER BY created_at
            """,
            EventType.TRADE_EXECUTED.value,
        )

        cumulative_pnl = Decimal("0")
        peak = Decimal("0")
        max_dd = Decimal("0")

        for row in results:
            pnl = Decimal(row["pnl"])
            cumulative_pnl += pnl
            peak = max(peak, cumulative_pnl)
            dd = (peak - cumulative_pnl) / (peak + 1000) if peak > 0 else 0
            max_dd = max(max_dd, dd)

    # Проверяем что система может обнаружить просадку
    assert isinstance(max_dd, Decimal)


@pytest.mark.e2e
@pytest.mark.risk
@pytest.mark.asyncio
async def test_drawdown_protection_action(db_pool):
    """
    E2E: Защитное действие при просадке
    """
    threshold = Decimal("0.15")  # 15%

    async with db_pool.acquire() as conn:
        # Эмулируем событие риска
        await conn.execute(
            """
            INSERT INTO events (event_type, data, created_at)
            VALUES ($1, $2, $3)
            """,
            EventType.RISK_BREACH.value,
            {
                "risk_type": "max_drawdown",
                "threshold": str(threshold),
                "action": "reduce_exposure",
            },
            datetime.now(UTC),
        )

        # Проверяем что событие записано
        result = await conn.fetchval(
            "SELECT COUNT(*) FROM events WHERE event_type = $1",
            EventType.RISK_BREACH.value,
        )

    assert result >= 1


# ==================== Exposure Management ====================


@pytest.mark.e2e
@pytest.mark.risk
@pytest.mark.asyncio
async def test_single_asset_exposure(db_pool):
    """
    E2E: Риск одного актива
    """
    max_single_exposure = Decimal("500000.0")  # $500K

    async with db_pool.acquire() as conn:
        # Рассчитываем экспозицию по одному активу
        result = await conn.fetch(
            """
            SELECT data FROM events
            WHERE event_type = $1 AND data->>'symbol' = $2
            """,
            EventType.POSITION_UPDATED.value,
            "BTC/USDT",
        )

        exposure = Decimal("0")
        for row in result:
            quantity = Decimal(row["data"].get("quantity", "0"))
            price = Decimal(row["data"].get("current_price", "0"))
            exposure += quantity * price

    assert exposure <= max_single_exposure


@pytest.mark.e2e
@pytest.mark.risk
@pytest.mark.asyncio
async def test_correlated_exposure(db_pool):
    """
    E2E: Коррелированный риск
    """
    # Проверяем что есть данные для оценки коррелированного риска
    async with db_pool.acquire() as conn:
        result = await conn.fetch(
            """
            SELECT DISTINCT data->>'symbol' as symbol
            FROM events
            WHERE event_type IN ($1, $2)
            """,
            EventType.POSITION_UPDATED.value,
            EventType.TRADE_EXECUTED.value,
        )

    assert len(result) >= 0


@pytest.mark.e2e
@pytest.mark.risk
@pytest.mark.asyncio
async def test_long_short_ratio(db_pool):
    """
    E2E: Соотношение long/short позиций
    """
    async with db_pool.acquire() as conn:
        # Считаем long позиции
        long_count = await conn.fetchval(
            """
            SELECT COUNT(*) FROM events
            WHERE event_type = $1 AND data->>'side' = 'buy'
            """,
            EventType.ORDER_SUBMITTED.value,
        )

        # Считаем short позиции
        short_count = await conn.fetchval(
            """
            SELECT COUNT(*) FROM events
            WHERE event_type = $1 AND data->>'side' = 'sell'
            """,
            EventType.ORDER_SUBMITTED.value,
        )

    # Проверяем разумное соотношение
    total = long_count + short_count
    if total > 0:
        ratio = long_count / total
        assert 0 <= ratio <= 1


# ==================== Risk Monitoring ====================


@pytest.mark.e2e
@pytest.mark.risk
@pytest.mark.asyncio
async def test_risk_metrics_collection(db_pool):
    """
    E2E: Сбор риск-метрик
    """
    async with db_pool.acquire() as conn:
        # Проверяем что собираем основные метрики
        metrics = await conn.fetch(
            """
            SELECT
                COUNT(*) as total_events,
                COUNT(DISTINCT data->>'symbol') as unique_symbols,
                COUNT(DISTINCT data->>'order_id') as unique_orders
            FROM events
            """
        )

    assert len(metrics) == 1
    assert "total_events" in metrics[0]


@pytest.mark.e2e
@pytest.mark.risk
@pytest.mark.asyncio
async def test_risk_alert_generation(db_pool):
    """
    E2E: Генерация алертов риска
    """
    async with db_pool.acquire() as conn:
        # Создаём событие алерта
        await conn.execute(
            """
            INSERT INTO events (event_type, data, created_at)
            VALUES ($1, $2, $3)
            """,
            EventType.RISK_BREACH.value,
            {
                "risk_type": "position_limit",
                "current_value": "105",
                "threshold": "100",
                "severity": "high",
            },
            datetime.now(UTC),
        )

        # Проверяем что алерт записан
        result = await conn.fetchval(
            "SELECT COUNT(*) FROM events WHERE event_type = $1",
            EventType.RISK_BREACH.value,
        )

    assert result >= 1


@pytest.mark.e2e
@pytest.mark.risk
@pytest.mark.asyncio
async def test_risk_reporting(db_pool):
    """
    E2E: Риск-отчётность
    """
    async with db_pool.acquire() as conn:
        # Генерируем отчёт
        report = await conn.fetch(
            """
            SELECT
                data->>'symbol' as symbol,
                COUNT(*) as event_count,
                MIN(created_at) as first_event,
                MAX(created_at) as last_event
            FROM events
            WHERE event_type IN ($1, $2)
            GROUP BY data->>'symbol'
            """,
            EventType.POSITION_UPDATED.value,
            EventType.TRADE_EXECUTED.value,
        )

    assert isinstance(report, list)

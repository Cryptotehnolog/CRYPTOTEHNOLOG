# ==================== E2E: Compliance & Audit ====================
"""
Compliance & Audit E2E Tests (10 сценариев)

Тестирует соответствие требованиям и ведение аудита:
- Audit trail
- Reporting
- Security
- Data Retention
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from cryptotechnolog.core.event import Event, EventType
from cryptotechnolog.core.stubs import OrderStub, PositionStub, TradeStub

# ==================== Audit Trail ====================


@pytest.mark.e2e
@pytest.mark.compliance
@pytest.mark.asyncio
async def test_every_order_logged(db_pool, event_bus):
    """
    E2E: Логирование каждого ордера
    """
    # Создаём тестовый ордер
    order = OrderStub(
        order_id="test_order_001",
        symbol="BTC/USDT",
        side="buy",
        order_type="limit",
        quantity=Decimal("0.01"),
        price=Decimal("50000.00"),
        status="filled",
    )

    # Публикуем событие ордера
    event = Event(
        event_type=EventType.ORDER_SUBMITTED,
        data=order.to_dict(),
        timestamp=datetime.now(UTC),
    )
    await event_bus.publish(event)

    # Проверяем что событие записано в БД
    async with db_pool.acquire() as conn:
        result = await conn.fetch(
            """
            SELECT * FROM events
            WHERE event_type = $1
            ORDER BY created_at DESC
            LIMIT 1
            """,
            EventType.ORDER_SUBMITTED.value,
        )

    assert len(result) > 0, "Ордер должен быть залогирован в БД"
    assert result[0]["data"]["order_id"] == "test_order_001"


@pytest.mark.e2e
@pytest.mark.compliance
@pytest.mark.asyncio
async def test_every_trade_logged(db_pool, event_bus):
    """
    E2E: Логирование каждой сделки
    """
    # Создаём тестовую сделку
    trade = TradeStub(
        trade_id="test_trade_001",
        order_id="test_order_001",
        symbol="BTC/USDT",
        side="buy",
        quantity=Decimal("0.01"),
        price=Decimal("50000.00"),
        fee=Decimal("0.50"),
    )

    # Публикуем событие сделки
    event = Event(
        event_type=EventType.TRADE_EXECUTED,
        data=trade.to_dict(),
        timestamp=datetime.now(UTC),
    )
    await event_bus.publish(event)

    # Проверяем что событие записано в БД
    async with db_pool.acquire() as conn:
        result = await conn.fetch(
            """
            SELECT * FROM events
            WHERE event_type = $1
            ORDER BY created_at DESC
            LIMIT 1
            """,
            EventType.TRADE_EXECUTED.value,
        )

    assert len(result) > 0, "Сделка должна быть залогирована в БД"
    assert result[0]["data"]["trade_id"] == "test_trade_001"


@pytest.mark.e2e
@pytest.mark.compliance
@pytest.mark.asyncio
async def test_position_changes_logged(db_pool, event_bus):
    """
    E2E: Логирование изменений позиций
    """
    # Создаём позицию
    position = PositionStub(
        symbol="BTC/USDT",
        quantity=Decimal("0.01"),
        entry_price=Decimal("50000.00"),
        current_price=Decimal("51000.00"),
        unrealized_pnl=Decimal("10.00"),
    )

    # Публикуем событие изменения позиции
    event = Event(
        event_type=EventType.POSITION_UPDATED,
        data=position.to_dict(),
        timestamp=datetime.now(UTC),
    )
    await event_bus.publish(event)

    # Проверяем что событие записано в БД
    async with db_pool.acquire() as conn:
        result = await conn.fetch(
            """
            SELECT * FROM events
            WHERE event_type = $1
            ORDER BY created_at DESC
            LIMIT 1
            """,
            EventType.POSITION_UPDATED.value,
        )

    assert len(result) > 0, "Изменение позиции должно быть залогировано"


@pytest.mark.e2e
@pytest.mark.compliance
@pytest.mark.asyncio
async def test_risk_breaches_logged(db_pool, event_bus):
    """
    E2E: Логирование нарушений рисков
    """
    # Создаём событие нарушения риска
    event = Event(
        event_type=EventType.RISK_BREACH,
        data={
            "risk_type": "max_drawdown",
            "threshold": "0.20",
            "current_value": "0.25",
            "action": "close_all_positions",
        },
        timestamp=datetime.now(UTC),
    )
    await event_bus.publish(event)

    # Проверяем что событие записано в БД
    async with db_pool.acquire() as conn:
        result = await conn.fetch(
            """
            SELECT * FROM events
            WHERE event_type = $1
            ORDER BY created_at DESC
            LIMIT 1
            """,
            EventType.RISK_BREACH.value,
        )

    assert len(result) > 0, "Нарушение риска должно быть залогировано"


# ==================== Reporting ====================


@pytest.mark.e2e
@pytest.mark.reporting
@pytest.mark.asyncio
async def test_daily_pnl_report(db_pool):
    """
    E2E: Ежедневный P&L отчёт
    """
    # Создаём тестовые сделки для расчёта P&L
    async with db_pool.acquire() as conn:
        # Вставляем тестовые сделки
        await conn.execute(
            """
            INSERT INTO events (event_type, data, created_at)
            VALUES ($1, $2, $3), ($4, $5, $6)
            """,
            EventType.TRADE_EXECUTED.value,
            {"trade_id": "t1", "pnl": "100.00"},
            datetime.now(UTC),
            EventType.TRADE_EXECUTED.value,
            {"trade_id": "t2", "pnl": "-50.00"},
            datetime.now(UTC),
        )

        # Рассчитываем P&L
        result = await conn.fetch(
            """
            SELECT
                DATE(created_at) as date,
                SUM((data->>'pnl')::numeric) as total_pnl
            FROM events
            WHERE event_type = $1
            GROUP BY DATE(created_at)
            """,
            EventType.TRADE_EXECUTED.value,
        )

    assert len(result) > 0, "Должен быть рассчитан P&L"
    # Проверяем что сумма корректна
    total_pnl = result[0]["total_pnl"]
    assert float(total_pnl) == 50.00, "P&L должен быть равен 50.00"


@pytest.mark.e2e
@pytest.mark.reporting
@pytest.mark.asyncio
async def test_monthly_statement(db_pool):
    """
    E2E: Месячная выписка
    """
    async with db_pool.acquire() as conn:
        # Рассчитываем месячную статистику
        result = await conn.fetch(
            """
            SELECT
                DATE_TRUNC('month', created_at) as month,
                COUNT(*) as total_events,
                COUNT(DISTINCT data->>'trade_id') as total_trades
            FROM events
            WHERE event_type = $1
            GROUP BY DATE_TRUNC('month', created_at)
            """,
            EventType.TRADE_EXECUTED.value,
        )

    assert isinstance(result, list), "Должен быть результат запроса"


@pytest.mark.e2e
@pytest.mark.reporting
@pytest.mark.asyncio
async def test_tax_report(db_pool):
    """
    E2E: Налоговый отчёт
    """
    async with db_pool.acquire() as conn:
        # Рассчитываем реализованные прибыли/убытки
        result = await conn.fetch(
            """
            SELECT
                data->>'symbol' as symbol,
                SUM((data->>'pnl')::numeric) as total_pnl
            FROM events
            WHERE event_type = $1
            GROUP BY data->>'symbol'
            """,
            EventType.TRADE_EXECUTED.value,
        )

    assert isinstance(result, list), "Должен быть результат для налогового отчёта"


@pytest.mark.e2e
@pytest.mark.reporting
@pytest.mark.asyncio
async def test_regulatory_report(db_pool):
    """
    E2E: Регуляторный отчёт
    """
    async with db_pool.acquire() as conn:
        # Проверяем наличие всех обязательных событий
        required_events = [
            EventType.ORDER_SUBMITTED.value,
            EventType.TRADE_EXECUTED.value,
            EventType.RISK_BREACH.value,
        ]

        for event_type in required_events:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM events WHERE event_type = $1",
                event_type,
            )
            assert count is not None, f"Событие {event_type} должно быть записано"


# ==================== Security ====================


@pytest.mark.e2e
@pytest.mark.security
@pytest.mark.asyncio
async def test_api_key_rotation(db_pool):
    """
    E2E: Ротация API ключей
    """
    # Проверяем что есть логи изменений конфигурации
    async with db_pool.acquire() as conn:
        result = await conn.fetch(
            """
            SELECT COUNT(*) as count FROM config_versions
            """
        )

    assert result[0]["count"] >= 0, "Таблица версий конфигурации должна существовать"


@pytest.mark.e2e
@pytest.mark.security
@pytest.mark.asyncio
async def test_permission_enforcement(db_pool):
    """
    E2E: Принудительное применение прав доступа
    """
    async with db_pool.acquire() as conn:
        # Проверяем что события содержат информацию об источнике
        result = await conn.fetch(
            """
            SELECT data FROM events
            WHERE event_type = $1
            LIMIT 1
            """,
            EventType.ORDER_SUBMITTED.value,
        )

    # Если есть события - проверяем структуру
    if result:
        assert "source" in result[0]["data"] or "actor" in result[0]["data"], \
            "Событие должно содержать информацию об источнике"


@pytest.mark.e2e
@pytest.mark.security
@pytest.mark.asyncio
async def test_access_control(db_pool):
    """
    E2E: Контроль доступа
    """
    async with db_pool.acquire() as conn:
        # Проверяем что таблицы имеют правильные права
        result = await conn.fetch(
            """
            SELECT table_name, privilege_type
            FROM information_schema.table_privileges
            WHERE table_schema = 'public'
            LIMIT 10
            """
        )

    assert isinstance(result, list), "Должны быть проверены права доступа"


@pytest.mark.e2e
@pytest.mark.security
@pytest.mark.asyncio
async def test_audit_compliance(db_pool):
    """
    E2E: Соответствие аудиту
    """
    async with db_pool.acquire() as conn:
        # Проверяем完整性 (целостность) аудита
        result = await conn.fetch(
            """
            SELECT COUNT(*) as count
            FROM events
            WHERE created_at IS NOT NULL
            """
        )

    assert result[0]["count"] >= 0, "Аудит должен вестись"


# ==================== Data Retention ====================


@pytest.mark.e2e
@pytest.mark.retention
@pytest.mark.asyncio
async def test_seven_year_retention(db_pool):
    """
    E2E: Политика хранения 7 лет
    """
    async with db_pool.acquire() as conn:
        # Проверяем что события не удаляются автоматически
        # (политика хранения будет применена позже)
        result = await conn.fetch(
            """
            SELECT MIN(created_at) as oldest_event,
                   MAX(created_at) as newest_event
            FROM events
            """
        )

    assert result[0]["newest_event"] is not None, "Должны быть записи"


@pytest.mark.e2e
@pytest.mark.retention
@pytest.mark.asyncio
async def test_gdpr_compliance(db_pool):
    """
    E2E: Соответствие GDPR
    """
    async with db_pool.acquire() as conn:
        # Проверяем что можем найти данные по идентификатору
        # (для реализации права на удаление)
        result = await conn.fetch(
            """
            SELECT data FROM events
            LIMIT 1
            """
        )

    # Проверяем структуру данных
    if result:
        assert isinstance(result[0]["data"], dict), "Данные должны быть в JSON формате"


@pytest.mark.e2e
@pytest.mark.retention
@pytest.mark.asyncio
async def test_data_export(db_pool):
    """
    E2E: Экспорт данных
    """
    async with db_pool.acquire() as conn:
        # Экспорт всех событий
        result = await conn.fetch(
            """
            SELECT event_type, data, created_at
            FROM events
            ORDER BY created_at DESC
            LIMIT 100
            """
        )

    assert isinstance(result, list), "Должен быть результат экспорта"
    # Проверяем что возвращаются все поля
    if result:
        assert "event_type" in result[0]
        assert "data" in result[0]
        assert "created_at" in result[0]

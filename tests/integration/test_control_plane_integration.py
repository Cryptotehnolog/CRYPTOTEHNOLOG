"""
Integration Tests for Control Plane with Real Database.

Тесты с реальным подключением к PostgreSQL.
Требуют запущенную БД и применяемые миграции.

Запуск: uv run pytest tests/integration/test_control_plane_integration.py -v
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch
import uuid

import pytest

from cryptotechnolog.core.enhanced_event_bus import EnhancedEventBus
from cryptotechnolog.core.event import Event, SystemEventSource, SystemEventType
from cryptotechnolog.core.global_instances import set_enhanced_event_bus
from cryptotechnolog.core.listeners import (
    register_all_listeners,
)
from cryptotechnolog.core.state_machine_enums import SystemState

# ==================== Fixtures ====================


@pytest.fixture
def test_event_bus():
    """Create fresh EnhancedEventBus for tests."""
    bus = EnhancedEventBus(
        capacities={"critical": 100, "high": 500, "normal": 10000, "low": 50000},
        rate_limit=100,
    )
    set_enhanced_event_bus(bus)
    yield bus
    set_enhanced_event_bus(None)


@pytest.fixture
def setup_listeners(test_event_bus, db_pool):
    """Register all listeners on the test EnhancedEventBus with real DB pool."""
    # Мокаем get_db_pool чтобы возвращал реальный пул из фикстуры
    with (
        patch("cryptotechnolog.core.listeners.state_machine.get_db_pool", return_value=db_pool),
        patch("cryptotechnolog.core.listeners.risk.get_db_pool", return_value=db_pool),
        patch("cryptotechnolog.core.listeners.audit.get_db_pool", return_value=db_pool),
        patch("cryptotechnolog.core.listeners.metrics.get_db_pool", return_value=db_pool),
    ):
        registry = register_all_listeners()
        test_event_bus.enable_listeners()
        yield registry
        test_event_bus.disable_listeners()


# ==================== State Machine Tests ====================


@pytest.mark.asyncio
async def test_state_transition_persisted(db_pool, test_event_bus, setup_listeners):
    """Test that state transitions are persisted to database."""
    # Publish state transition event
    event = Event.new(
        SystemEventType.STATE_TRANSITION,
        SystemEventSource.STATE_MACHINE,
        {
            "from_state": SystemState.BOOT.value,
            "to_state": SystemState.READY.value,
            "trigger": "manual_start",
            "operator": "test_user",
            "duration_ms": 150,
        },
    )

    await test_event_bus.publish(event)

    # Wait for async processing
    await test_event_bus.drain()

    # Verify transition was recorded
    async with db_pool.acquire() as conn:
        result = await conn.fetchrow("""
            SELECT from_state, to_state, trigger, operator, duration_ms
            FROM state_transitions
            ORDER BY id DESC LIMIT 1
            """)

    assert result is not None
    assert result["from_state"] == "boot"
    assert result["to_state"] == "ready"
    assert result["trigger"] == "manual_start"
    assert result["operator"] == "test_user"
    assert result["duration_ms"] == 150


@pytest.mark.asyncio
async def test_current_state_updated(db_pool, test_event_bus, setup_listeners):
    """Test that current state is updated in database."""
    # Publish state transition
    event = Event.new(
        SystemEventType.STATE_TRANSITION,
        SystemEventSource.STATE_MACHINE,
        {
            "from_state": SystemState.BOOT.value,
            "to_state": SystemState.READY.value,
            "trigger": "auto",
        },
    )

    await test_event_bus.publish(event)
    await test_event_bus.drain()

    # Verify current state
    async with db_pool.acquire() as conn:
        result = await conn.fetchrow(
            "SELECT current_state, version FROM state_machine_states WHERE id = 1"
        )

    assert result is not None
    assert result["current_state"] == "ready"
    assert result["version"] >= 1


@pytest.mark.asyncio
async def test_system_events_persisted(db_pool, test_event_bus, setup_listeners):
    """Test that system events are persisted."""
    # Publish system ready event
    event = Event.new(
        SystemEventType.SYSTEM_READY,
        SystemEventSource.SYSTEM_CONTROLLER,
        {"timestamp": datetime.now(UTC).isoformat()},
    )

    await test_event_bus.publish(event)
    await test_event_bus.drain()

    # Verify state machine was updated
    async with db_pool.acquire() as conn:
        state = await conn.fetchrow("SELECT current_state FROM state_machine_states WHERE id = 1")

    assert state["current_state"] == "ready"


# ==================== Audit Tests ====================


@pytest.mark.asyncio
async def test_audit_events_persisted(db_pool, test_event_bus, setup_listeners):
    """Test that audit events are persisted for all events."""
    # Publish various events
    events = [
        Event.new(SystemEventType.SYSTEM_BOOT, SystemEventSource.SYSTEM_CONTROLLER, {}),
        Event.new(
            SystemEventType.STATE_TRANSITION,
            SystemEventSource.STATE_MACHINE,
            {"from_state": "boot", "to_state": "ready"},
        ),
        Event.new(
            SystemEventType.WATCHDOG_ALERT, SystemEventSource.WATCHDOG, {"reason": "test alert"}
        ),
    ]

    for event in events:
        await test_event_bus.publish(event)

    await test_event_bus.drain()

    # Verify audit events - ищем запись с правильной severity
    async with db_pool.acquire() as conn:
        result = await conn.fetchrow(
            "SELECT event_type, severity FROM audit_events WHERE event_type = 'WATCHDOG_ALERT' AND severity = 'WARNING' LIMIT 1"
        )

    assert result is not None
    assert result["severity"] == "WARNING"


@pytest.mark.asyncio
async def test_audit_event_structure(db_pool, test_event_bus, setup_listeners):
    """Test that audit events have correct structure."""
    event = Event.new(
        SystemEventType.STATE_TRANSITION,
        SystemEventSource.STATE_MACHINE,
        {
            "from_state": "boot",
            "to_state": "ready",
            "entity_id": "test-entity",
        },
    )
    event.correlation_id = uuid.uuid4()
    event.metadata = {"source": "test"}

    await test_event_bus.publish(event)
    await test_event_bus.drain()

    # Verify audit event structure
    async with db_pool.acquire() as conn:
        result = await conn.fetchrow("""
            SELECT event_type, entity_type, entity_id, metadata, severity
            FROM audit_events
            WHERE event_type = 'STATE_TRANSITION'
            """)

    assert result is not None
    assert result["entity_type"] == "state_machine"
    assert "source" in result["metadata"]


# ==================== Risk Events Tests ====================


@pytest.mark.asyncio
async def test_risk_events_persisted(db_pool, test_event_bus, setup_listeners):
    """Test that risk events are persisted."""
    # Publish risk violation event
    event = Event.new(
        SystemEventType.RISK_VIOLATION,
        SystemEventSource.RISK_ENGINE,
        {
            "symbol": "BTCUSDT",
            "side": "BUY",
            "size": 10000,
            "price": 50000,
            "limit_type": "POSITION_SIZE",
            "current_value": 15000,
            "max_value": 10000,
            "reason": "Position size exceeds limit",
            "order_id": "order-123",
        },
    )

    await test_event_bus.publish(event)
    await test_event_bus.drain()

    # Verify risk event
    async with db_pool.acquire() as conn:
        result = await conn.fetchrow("""
            SELECT event_type, symbol, allowed, reason
            FROM risk_events
            ORDER BY id DESC LIMIT 1
            """)

    assert result is not None
    assert result["event_type"] == "RISK_VIOLATION"
    assert result["symbol"] == "BTCUSDT"
    assert result["allowed"] is False
    assert "limit" in result["reason"].lower()


@pytest.mark.asyncio
async def test_order_rejected_persisted(db_pool, test_event_bus, setup_listeners):
    """Test that order rejections are persisted."""
    event = Event.new(
        SystemEventType.ORDER_REJECTED,
        SystemEventSource.EXECUTION_CORE,
        {
            "symbol": "ETHUSDT",
            "side": "SELL",
            "size": 500,
            "price": 3000,
            "order_id": "order-456",
            "reason": "Insufficient balance",
        },
    )

    await test_event_bus.publish(event)
    await test_event_bus.drain()

    # Verify order rejection
    async with db_pool.acquire() as conn:
        result = await conn.fetchrow(
            "SELECT event_type, symbol, allowed, rejected_order_id FROM risk_events WHERE event_type = 'ORDER_REJECTED' ORDER BY id DESC LIMIT 1"
        )

    assert result is not None
    assert result["event_type"] == "ORDER_REJECTED"
    assert result["rejected_order_id"] == "order-456"


# ==================== Metrics Tests ====================


@pytest.mark.asyncio
async def test_performance_metrics_persisted(db_pool, test_event_bus, setup_listeners):
    """Test that performance metrics are persisted."""
    # Publish order filled event with timing
    submit_time = datetime.now(UTC)
    fill_time = datetime.now(UTC)

    event = Event.new(
        SystemEventType.ORDER_FILLED,
        SystemEventSource.EXECUTION_CORE,
        {
            "symbol": "BTCUSDT",
            "side": "BUY",
            "filled_size": 0.5,
            "price": 50000,
            "order_id": "order-789",
            "submit_time": submit_time,
            "fill_time": fill_time,
        },
    )

    await test_event_bus.publish(event)
    await test_event_bus.drain()

    # Verify metrics
    async with db_pool.acquire() as conn:
        results = await conn.fetch(
            "SELECT metric_name, value FROM performance_metrics WHERE metric_category = 'order_latency'"
        )

    assert len(results) >= 1


# ==================== Database Connection Tests ====================


@pytest.mark.asyncio
async def test_db_connection_available(db_pool):
    """Test that database connection is available."""
    assert db_pool is not None

    async with db_pool.acquire() as conn:
        result = await conn.fetchval("SELECT 1")
        assert result == 1


@pytest.mark.asyncio
async def test_migrations_applied(db_pool):
    """Test that all migrations are applied."""
    async with db_pool.acquire() as conn:
        # Check key tables exist
        tables = await conn.fetch("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name IN (
                'state_machine_states', 'state_transitions', 'audit_events',
                'risk_events', 'performance_metrics', 'event_store'
            )
        """)

        table_names = [t["table_name"] for t in tables]
        assert "state_machine_states" in table_names
        assert "audit_events" in table_names
        assert "risk_events" in table_names

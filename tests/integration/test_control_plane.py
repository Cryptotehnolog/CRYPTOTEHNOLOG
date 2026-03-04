"""
Integration tests for control plane with listeners.

Тестирует интеграцию EventBus с listeners (State, Audit, Metrics, Risk).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cryptotechnolog.core.enhanced_event_bus import EnhancedEventBus
from cryptotechnolog.core.event import Event, SystemEventSource, SystemEventType
from cryptotechnolog.core.global_instances import (
    get_enhanced_event_bus,
    set_enhanced_event_bus,
)
from cryptotechnolog.core.listeners import (
    get_listener_registry,
    register_all_listeners,
)


# ==================== Test Configuration ====================


class MockConnection:
    """Mock asyncpg connection for tests."""

    async def execute(self, *args, **kwargs):
        return None

    async def fetch(self, *args, **kwargs):
        return []

    async def fetchrow(self, *args, **kwargs):
        return None

    async def fetchval(self, *args, **kwargs):
        return None

    async def close(self):
        pass


class PoolAcquireContext:
    """Mock for async with pool.acquire() as conn."""

    async def __aenter__(self):
        return MockConnection()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None


class MockPool:
    """Mock database pool that properly implements async context manager."""

    def acquire(self):
        return PoolAcquireContext()

    async def close(self):
        pass


@pytest.fixture(autouse=True)
def mock_database():
    """Mock database to avoid real connections in tests."""
    mock_pool = MockPool()

    with patch("cryptotechnolog.core.database.get_database") as mock_db:
        mock_db_instance = MagicMock()
        mock_db_instance.pool = mock_pool
        mock_db_instance.is_connected = True
        mock_db_instance.connect = AsyncMock()
        mock_db_instance.disconnect = AsyncMock()
        mock_db.return_value = mock_db_instance

        with (
            patch(
                "cryptotechnolog.core.listeners.state_machine.get_db_pool", return_value=mock_pool
            ),
            patch("cryptotechnolog.core.listeners.risk.get_db_pool", return_value=mock_pool),
            patch("cryptotechnolog.core.listeners.audit.get_db_pool", return_value=mock_pool),
            patch("cryptotechnolog.core.listeners.metrics.get_db_pool", return_value=mock_pool),
        ):
            yield mock_pool


@pytest.fixture
def test_event_bus():
    """Create fresh EnhancedEventBus for tests."""
    bus = EnhancedEventBus(
        capacities={
            "critical": 100,
            "high": 100,
            "normal": 100,
            "low": 100,
        }
    )
    set_enhanced_event_bus(bus)
    yield bus
    set_enhanced_event_bus(None)


@pytest.fixture
def setup_listeners(test_event_bus):
    """Register all listeners on the test EventBus."""
    registry = register_all_listeners()
    test_event_bus.enable_listeners()
    yield registry
    test_event_bus.disable_listeners()


# ==================== Event Bus + Listeners Tests ====================


@pytest.mark.asyncio
async def test_all_listeners_registered(test_event_bus):
    """Test that all listeners are registered."""
    register_all_listeners()
    test_event_bus.enable_listeners()

    registry = get_listener_registry()

    assert len(registry.all_listeners) == 4

    listener_names = [listener.name for listener in registry.all_listeners]
    assert "state_machine_listener" in listener_names
    assert "risk_check_listener" in listener_names
    assert "audit_listener" in listener_names
    assert "metrics_listener" in listener_names


@pytest.mark.asyncio
async def test_listener_handles_correct_events(test_event_bus, setup_listeners):
    """Test that listeners handle correct event types."""
    registry = get_listener_registry()

    # State machine listener
    sm_listener = registry.get_listener("state_machine_listener")
    assert sm_listener is not None

    state_event = Event.new(SystemEventType.STATE_TRANSITION, "test", {})
    assert sm_listener.handles_event(state_event)

    # Risk listener
    risk_listener = registry.get_listener("risk_check_listener")
    assert risk_listener is not None

    order_event = Event.new(SystemEventType.ORDER_SUBMITTED, "test", {})
    assert risk_listener.handles_event(order_event)


@pytest.mark.asyncio
async def test_listener_metrics(test_event_bus, setup_listeners):
    """Test that listener metrics are tracked."""
    # Получаем тот же registry, который был зарегистрирован в event_bus
    registry = test_event_bus.listener_registry
    assert registry is not None

    audit_listener = registry.get_listener("audit_listener")
    assert audit_listener is not None

    # Publish some events
    for _ in range(3):
        event = Event.new(SystemEventType.SYSTEM_BOOT, SystemEventSource.SYSTEM_CONTROLLER, {})
        await test_event_bus.publish(event)

    # Wait for async processing - даем время задачам выполниться
    await test_event_bus.drain(timeout=5.0)

    # Check metrics
    metrics = registry.metrics
    assert metrics["total_listeners"] == 4

    assert audit_listener.metrics["events_processed"] >= 3


@pytest.mark.asyncio
async def test_event_published_without_listeners(test_event_bus):
    """Test that events work without listeners."""
    # Don't enable listeners - publish возвращает False без подписчиков
    event = Event.new(SystemEventType.SYSTEM_BOOT, SystemEventSource.SYSTEM_CONTROLLER, {})

    # Should publish without error (но возвращает False т.к. нет подписчиков)
    result = await test_event_bus.publish(event)
    assert test_event_bus.metrics["published"] == 1


@pytest.mark.asyncio
async def test_listener_error_does_not_crash_bus(test_event_bus, setup_listeners):
    """Test that listener errors don't crash EventBus."""
    # This should not raise any exceptions
    event = Event.new(
        SystemEventType.STATE_TRANSITION,
        SystemEventSource.STATE_MACHINE,
        {
            "from_state": "boot",
            "to_state": "ready",
        },
    )

    # Multiple events should all be published
    for _ in range(10):
        await test_event_bus.publish(event)

    await test_event_bus.drain(timeout=5.0)

    # Bus should still be functional
    assert test_event_bus.metrics["published"] >= 10


@pytest.mark.asyncio
async def test_audit_listener_receives_all_events(test_event_bus, setup_listeners):
    """Test that audit listener receives all events via wildcard."""
    registry = test_event_bus.listener_registry
    audit_listener = registry.get_listener("audit_listener")
    assert audit_listener is not None

    # Publish different event types
    events = [
        Event.new(SystemEventType.SYSTEM_BOOT, SystemEventSource.SYSTEM_CONTROLLER, {}),
        Event.new(SystemEventType.SYSTEM_READY, SystemEventSource.SYSTEM_CONTROLLER, {}),
        Event.new(
            SystemEventType.ORDER_FILLED, SystemEventSource.EXECUTION_CORE, {"order_id": "123"}
        ),
    ]

    for event in events:
        await test_event_bus.publish(event)

    await test_event_bus.drain(timeout=5.0)

    # Audit listener должен получить все события
    assert audit_listener.metrics["events_processed"] >= 3


@pytest.mark.asyncio
async def test_state_machine_listener_persists_transition(test_event_bus, setup_listeners):
    """Test that state machine listener processes transitions."""
    registry = test_event_bus.listener_registry
    sm_listener = registry.get_listener("state_machine_listener")
    assert sm_listener is not None

    event = Event.new(
        SystemEventType.STATE_TRANSITION,
        SystemEventSource.STATE_MACHINE,
        {
            "from_state": "boot",
            "to_state": "ready",
            "trigger": "manual",
            "operator": "test",
        },
    )

    await test_event_bus.publish(event)
    await test_event_bus.drain(timeout=5.0)

    assert sm_listener.metrics["events_processed"] >= 1


@pytest.mark.asyncio
async def test_risk_listener_persists_violation(test_event_bus, setup_listeners):
    """Test that risk listener processes violations."""
    registry = test_event_bus.listener_registry
    risk_listener = registry.get_listener("risk_check_listener")
    assert risk_listener is not None

    event = Event.new(
        SystemEventType.RISK_VIOLATION,
        SystemEventSource.RISK_ENGINE,
        {
            "symbol": "BTCUSDT",
            "limit_type": "POSITION_SIZE",
            "current_value": 15000,
            "max_value": 10000,
        },
    )

    await test_event_bus.publish(event)
    await test_event_bus.drain(timeout=5.0)

    assert risk_listener.metrics["events_processed"] >= 1


@pytest.mark.asyncio
async def test_multiple_events_same_type(test_event_bus, setup_listeners):
    """Test processing multiple events of the same type."""
    registry = test_event_bus.listener_registry
    sm_listener = registry.get_listener("state_machine_listener")

    # Publish 5 state transitions
    for i in range(5):
        event = Event.new(
            SystemEventType.STATE_TRANSITION,
            SystemEventSource.STATE_MACHINE,
            {"from_state": "boot", "to_state": "ready", "trigger": f"test_{i}"},
        )
        await test_event_bus.publish(event)

    await test_event_bus.drain(timeout=5.0)

    assert sm_listener.metrics["events_processed"] >= 5


@pytest.mark.asyncio
async def test_event_bus_drain_clears_pending_tasks(test_event_bus):
    """Test that drain properly clears pending tasks."""
    register_all_listeners()
    test_event_bus.enable_listeners()

    # Publish events
    for _ in range(3):
        event = Event.new(SystemEventType.SYSTEM_BOOT, SystemEventSource.SYSTEM_CONTROLLER, {})
        await test_event_bus.publish(event)

    # Drain should wait for tasks
    await test_event_bus.drain(timeout=5.0)

    # After drain, pending tasks should be cleared
    assert len(test_event_bus.pending_tasks) == 0


@pytest.mark.asyncio
async def test_listeners_can_be_disabled(test_event_bus):
    """Test that listeners can be disabled."""
    register_all_listeners()
    test_event_bus.enable_listeners()

    registry = test_event_bus.listener_registry
    assert registry is not None

    # Disable listeners
    test_event_bus.disable_listeners()

    # Publish event
    event = Event.new(SystemEventType.SYSTEM_BOOT, SystemEventSource.SYSTEM_CONTROLLER, {})
    await test_event_bus.publish(event)

    await test_event_bus.drain(timeout=5.0)

    # Metrics should not change after disable
    audit_listener = registry.get_listener("audit_listener")
    assert audit_listener.metrics["events_processed"] == 0

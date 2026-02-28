"""
Unit Tests for Control Plane (Event Bus + Listeners).

Простые тесты Event Bus и Listeners без зависимости от БД.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.event import Event, SystemEventSource, SystemEventType
from src.core.event_bus import EventBus, get_event_bus, set_event_bus
from src.core.listeners import (
    register_all_listeners,
    get_listener_registry,
)


# ==================== Test Configuration ====================


@pytest.fixture(autouse=True)
def mock_database():
    """Mock database to avoid real connections in tests."""
    mock_pool = AsyncMock()
    mock_pool.acquire = AsyncMock()
    mock_pool.close = AsyncMock()
    
    with patch('src.core.database.get_database') as mock_db:
        mock_db_instance = MagicMock()
        mock_db_instance.pool = mock_pool
        mock_db_instance.is_connected = True
        mock_db_instance.connect = AsyncMock()
        mock_db_instance.disconnect = AsyncMock()
        mock_db.return_value = mock_db_instance
        
        with patch('src.core.listeners.state_machine.get_db_pool', return_value=mock_pool):
            with patch('src.core.listeners.risk.get_db_pool', return_value=mock_pool):
                with patch('src.core.listeners.audit.get_db_pool', return_value=mock_pool):
                    with patch('src.core.listeners.metrics.get_db_pool', return_value=mock_pool):
                        yield mock_pool


@pytest.fixture
def test_event_bus():
    """Create fresh EventBus for tests."""
    bus = EventBus(capacity=100)
    set_event_bus(bus)
    yield bus
    bus.clear()
    set_event_bus(None)


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
    
    listener_names = [l.name for l in registry.all_listeners]
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
    registry = test_event_bus._listener_registry
    assert registry is not None
    
    audit_listener = registry.get_listener("audit_listener")
    assert audit_listener is not None
    
    # Publish some events
    for _ in range(3):
        event = Event.new(SystemEventType.SYSTEM_BOOT, SystemEventSource.SYSTEM_CONTROLLER, {})
        test_event_bus.publish(event)
    
    # Wait for async processing - даем время задачам выполниться
    await test_event_bus.flush()
    
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
    result = test_event_bus.publish(event)
    assert test_event_bus.publish_count == 1


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
        test_event_bus.publish(event)
    
    await test_event_bus.flush()
    
    # Bus should still be functional
    assert test_event_bus.publish_count >= 10


@pytest.mark.asyncio
async def test_audit_listener_receives_all_events(test_event_bus, setup_listeners):
    """Test that audit listener receives all events via wildcard."""
    registry = test_event_bus._listener_registry
    audit_listener = registry.get_listener("audit_listener")
    assert audit_listener is not None
    
    # Publish different event types
    events = [
        Event.new(SystemEventType.SYSTEM_BOOT, SystemEventSource.SYSTEM_CONTROLLER, {}),
        Event.new(SystemEventType.SYSTEM_READY, SystemEventSource.SYSTEM_CONTROLLER, {}),
        Event.new(SystemEventType.ORDER_FILLED, SystemEventSource.EXECUTION_CORE, {"order_id": "123"}),
    ]
    
    for event in events:
        test_event_bus.publish(event)
    
    await test_event_bus.flush()
    
    # Audit listener должен получить все события
    assert audit_listener.metrics["events_processed"] >= 3


@pytest.mark.asyncio
async def test_state_machine_listener_persists_transition(test_event_bus, setup_listeners):
    """Test that state machine listener processes transitions."""
    registry = test_event_bus._listener_registry
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
    
    test_event_bus.publish(event)
    await test_event_bus.flush()
    
    assert sm_listener.metrics["events_processed"] >= 1


@pytest.mark.asyncio
async def test_risk_listener_persists_violation(test_event_bus, setup_listeners):
    """Test that risk listener processes violations."""
    registry = test_event_bus._listener_registry
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
    
    test_event_bus.publish(event)
    await test_event_bus.flush()
    
    assert risk_listener.metrics["events_processed"] >= 1


@pytest.mark.asyncio
async def test_multiple_events_same_type(test_event_bus, setup_listeners):
    """Test processing multiple events of the same type."""
    registry = test_event_bus._listener_registry
    sm_listener = registry.get_listener("state_machine_listener")
    
    # Publish 5 state transitions
    for i in range(5):
        event = Event.new(
            SystemEventType.STATE_TRANSITION,
            SystemEventSource.STATE_MACHINE,
            {"from_state": "boot", "to_state": "ready", "trigger": f"test_{i}"},
        )
        test_event_bus.publish(event)
    
    await test_event_bus.flush()
    
    assert sm_listener.metrics["events_processed"] >= 5


@pytest.mark.asyncio
async def test_event_bus_flush_clears_pending_tasks(test_event_bus):
    """Test that flush properly clears pending tasks."""
    register_all_listeners()
    test_event_bus.enable_listeners()
    
    # Publish events
    for _ in range(3):
        event = Event.new(SystemEventType.SYSTEM_BOOT, SystemEventSource.SYSTEM_CONTROLLER, {})
        test_event_bus.publish(event)
    
    # Flush should wait for tasks
    await test_event_bus.flush()
    
    # After flush, pending tasks should be cleared
    assert len(test_event_bus._pending_tasks) == 0


@pytest.mark.asyncio
async def test_listeners_can_be_disabled(test_event_bus):
    """Test that listeners can be disabled."""
    register_all_listeners()
    test_event_bus.enable_listeners()
    
    registry = test_event_bus._listener_registry
    assert registry is not None
    
    # Disable listeners
    test_event_bus.disable_listeners()
    
    # Publish event
    event = Event.new(SystemEventType.SYSTEM_BOOT, SystemEventSource.SYSTEM_CONTROLLER, {})
    test_event_bus.publish(event)
    
    await test_event_bus.flush()
    
    # Metrics should not change after disable
    audit_listener = registry.get_listener("audit_listener")
    assert audit_listener.metrics["events_processed"] == 0

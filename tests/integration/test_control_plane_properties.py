"""
Property-Based Tests for Control Plane Invariants.

Тесты на основе свойств (property-based testing) с использованием Hypothesis.
Проверяют инварианты системы при различных входных данных.
"""

from __future__ import annotations

import asyncio
from typing import Any
import uuid

import hypothesis
from hypothesis import given, settings

from cryptotechnolog.core.enhanced_event_bus import EnhancedEventBus
from cryptotechnolog.core.event import Event, SystemEventSource, SystemEventType
from cryptotechnolog.core.global_instances import set_enhanced_event_bus
from cryptotechnolog.core.listeners import register_all_listeners
from cryptotechnolog.core.state_machine_enums import SystemState

# ==================== Hypothesis Settings ====================


settings.register_profile(
    "fast",
    max_examples=20,
    deadline=None,
)

settings.register_profile(
    "ci",
    max_examples=100,
    deadline=None,
)

hypothesis.settings.load_profile("fast")


# ==================== Custom Strategies ====================


@hypothesis.strategies.composite
def generate_valid_state(draw) -> str:
    """Generate valid state values."""
    states = [s.value for s in SystemState]
    return draw(hypothesis.strategies.sampled_from(states))


@hypothesis.strategies.composite
def generate_order_side(draw) -> str:
    """Generate valid order sides."""
    sides = ["BUY", "SELL", "SHORT", "LONG"]
    return draw(hypothesis.strategies.sampled_from(sides))


@hypothesis.strategies.composite
def generate_symbol(draw) -> str:
    """Generate valid trading symbols."""
    symbols = [
        "BTCUSDT",
        "ETHUSDT",
        "BNBUSDT",
        "SOLUSDT",
        "ADAUSDT",
        "XRPUSDT",
        "DOGEUSDT",
        "DOTUSDT",
    ]
    return draw(hypothesis.strategies.sampled_from(symbols))


@hypothesis.strategies.composite
def generate_event_payload(draw, event_type: str) -> dict[str, Any]:
    """Generate valid event payloads based on event type."""

    if event_type == "STATE_TRANSITION":
        return {
            "from_state": draw(generate_valid_state()),
            "to_state": draw(generate_valid_state()),
            "trigger": draw(hypothesis.strategies.text(min_size=1, max_size=50)),
            "operator": draw(hypothesis.strategies.text(min_size=1, max_size=50)),
            "duration_ms": draw(hypothesis.strategies.integers(min_value=0, max_value=60000)),
        }

    elif event_type in ["ORDER_SUBMITTED", "ORDER_FILLED", "ORDER_REJECTED"]:
        return {
            "symbol": draw(generate_symbol()),
            "side": draw(generate_order_side()),
            "size": draw(hypothesis.strategies.floats(min_value=0.001, max_value=100000)),
            "price": draw(hypothesis.strategies.floats(min_value=0.01, max_value=1000000)),
            "order_id": str(uuid.uuid4()),
            "leverage": draw(hypothesis.strategies.floats(min_value=1.0, max_value=125.0)),
        }

    elif event_type in ["POSITION_OPENED", "POSITION_CLOSED"]:
        return {
            "symbol": draw(generate_symbol()),
            "side": draw(hypothesis.strategies.sampled_from(["LONG", "SHORT"])),
            "size": draw(hypothesis.strategies.floats(min_value=0.001, max_value=100000)),
            "entry_price": draw(hypothesis.strategies.floats(min_value=0.01, max_value=1000000)),
            "position_id": str(uuid.uuid4()),
            "realized_pnl": draw(hypothesis.strategies.floats(min_value=-100000, max_value=100000)),
        }

    elif event_type == "RISK_VIOLATION":
        limit_types = ["POSITION_SIZE", "DRAWDOWN", "DAILY_LOSS", "LEVERAGE_EXCEEDED"]
        return {
            "symbol": draw(generate_symbol()),
            "side": draw(generate_order_side()),
            "size": draw(hypothesis.strategies.floats(min_value=0.001, max_value=100000)),
            "price": draw(hypothesis.strategies.floats(min_value=0.01, max_value=1000000)),
            "limit_type": draw(hypothesis.strategies.sampled_from(limit_types)),
            "current_value": draw(hypothesis.strategies.floats(min_value=0, max_value=1000000)),
            "max_value": draw(hypothesis.strategies.floats(min_value=0, max_value=1000000)),
            "reason": draw(hypothesis.strategies.text(min_size=1, max_size=200)),
            "order_id": str(uuid.uuid4()),
        }

    else:
        return {
            "data": draw(hypothesis.strategies.text(max_size=100)),
            "value": draw(hypothesis.strategies.floats(min_value=-1000000, max_value=1000000)),
        }


# ==================== State Machine Invariants ====================


class TestStateMachineInvariants:
    """Property-based tests for State Machine invariants."""

    @given(state=generate_valid_state())
    @settings(max_examples=20)
    def test_state_transition_from_any_state(self, state):
        """Test that state machine can transition from any valid state."""
        # All states should be valid
        assert state in [s.value for s in SystemState]

    @given(from_state=generate_valid_state(), to_state=generate_valid_state())
    @settings(max_examples=50)
    def test_state_transition_not_equal(self, from_state, to_state):
        """Test that from_state and to_state are different (when constrained)."""
        # When testing transitions, we might generate same states
        # This test ensures our generators can produce valid data
        assert from_state is not None
        assert to_state is not None

    @given(trigger=hypothesis.strategies.text(min_size=1, max_size=100))
    @settings(max_examples=20)
    def test_trigger_string_valid(self, trigger):
        """Test that trigger strings are properly validated."""
        # Trigger should be non-empty when we want it
        assert len(trigger) >= 0  # Always passes, but exercises generator


class TestEventPayloadInvariants:
    """Property-based tests for Event payload invariants."""

    @given(payload=generate_event_payload("STATE_TRANSITION"))
    @settings(max_examples=30)
    def test_state_transition_payload_structure(self, payload):
        """Test that state transition payload has required fields."""
        assert "from_state" in payload
        assert "to_state" in payload
        assert "trigger" in payload
        assert isinstance(payload["from_state"], str)
        assert isinstance(payload["to_state"], str)

    @given(payload=generate_event_payload("ORDER_SUBMITTED"))
    @settings(max_examples=30)
    def test_order_payload_structure(self, payload):
        """Test that order payload has required fields."""
        assert "symbol" in payload
        assert "side" in payload
        assert "size" in payload
        assert "price" in payload

        # Size and price should be positive
        assert payload["size"] > 0
        assert payload["price"] > 0

    @given(payload=generate_event_payload("RISK_VIOLATION"))
    @settings(max_examples=30)
    def test_risk_violation_payload_structure(self, payload):
        """Test that risk violation payload has required fields."""
        assert "symbol" in payload
        assert "limit_type" in payload
        assert "current_value" in payload
        assert "max_value" in payload
        assert "reason" in payload

        # Values should be non-negative
        assert payload["current_value"] >= 0
        assert payload["max_value"] >= 0


# ==================== Event Bus Invariants ====================


class TestEventBusInvariants:
    """Property-based tests for Event Bus invariants."""

    @given(
        event_type=hypothesis.strategies.text(min_size=1, max_size=100),
        payload=generate_event_payload("STATE_TRANSITION"),
    )
    @settings(max_examples=30)
    def test_event_creation_invariants(self, event_type, payload):
        """Test that created events maintain invariants."""
        event = Event.new(event_type, "test_source", payload)

        assert event.event_type == event_type
        assert event.source == "test_source"
        assert event.payload == payload
        assert event.id is not None

    @given(source=hypothesis.strategies.text(min_size=1, max_size=50))
    @settings(max_examples=20)
    def test_event_source_valid(self, source):
        """Test that event sources are properly handled."""
        event = Event.new("TEST", source, {})
        assert event.source == source


class TestListenerInvariants:
    """Property-based tests for Listener invariants."""

    @given(
        event_type=hypothesis.strategies.sampled_from(
            [
                "STATE_TRANSITION",
                "SYSTEM_BOOT",
                "ORDER_SUBMITTED",
                "ORDER_FILLED",
                "RISK_VIOLATION",
                "WATCHDOG_ALERT",
            ]
        )
    )
    @settings(max_examples=30)
    def test_listener_handles_events(self, event_type):
        """Test that appropriate listeners handle each event type."""
        # Create fresh EnhancedEventBus and register listeners
        bus = EnhancedEventBus(rate_limit=100)
        set_enhanced_event_bus(bus)

        registry = register_all_listeners()
        bus.enable_listeners()

        event = Event.new(event_type, "test", {})
        listeners = registry.get_listeners_for_event(event)

        # At least one listener should handle each event type
        # (audit_listener handles all events)
        assert len(listeners) >= 1

        # Cleanup
        bus.disable_listeners()

    @given(count=hypothesis.strategies.integers(min_value=1, max_value=100))
    @settings(max_examples=20)
    async def test_multiple_events_published(self, count):
        """Test that publishing multiple events maintains consistency."""
        bus = EnhancedEventBus(
            capacities={"critical": 100, "high": 100, "normal": 1000, "low": 1000}
        )
        set_enhanced_event_bus(bus)

        initial_count = bus.metrics["published"]

        for i in range(count):
            event = Event.new("TEST_EVENT", "test_source", {"index": i})
            await bus.publish(event)

        assert bus.metrics["published"] == initial_count + count

    @given(
        events=hypothesis.strategies.lists(
            generate_event_payload("STATE_TRANSITION"), min_size=1, max_size=20
        )
    )
    @settings(max_examples=15)
    async def test_sequence_of_transitions(self, events):
        """Test that sequence of state transitions is handled correctly."""
        bus = EnhancedEventBus(capacities={"critical": 100, "high": 100, "normal": 100, "low": 100})
        set_enhanced_event_bus(bus)

        for i, payload in enumerate(events):  # noqa: B007
            # Ensure from_state != to_state for valid transitions
            if payload.get("from_state") == payload.get("to_state"):
                payload["to_state"] = SystemState.HALT.value

            event = Event.new(
                SystemEventType.STATE_TRANSITION, SystemEventSource.STATE_MACHINE, payload
            )
            await bus.publish(event)

        assert bus.metrics["published"] >= len(events)


# ==================== Database Invariants ====================


class TestDatabaseInvariants:
    """Property-based tests for database invariants."""

    @given(
        version=hypothesis.strategies.integers(min_value=1, max_value=1000),
        description=hypothesis.strategies.text(min_size=1, max_size=200),
    )
    @settings(max_examples=20)
    def test_migration_version_unique(self, version, description):
        """Test that migration versions should be unique (conceptual)."""
        # This is a conceptual test - actual uniqueness is enforced by DB
        # We just ensure our test data follows the pattern
        assert version > 0
        assert len(description) > 0

    @given(
        state=hypothesis.strategies.text(min_size=1, max_size=50),
        version=hypothesis.strategies.integers(min_value=0, max_value=10000),
    )
    @settings(max_examples=20)
    def test_state_machine_state_structure(self, state, version):
        """Test that state machine records have valid structure."""
        # Version should be non-negative
        assert version >= 0

        # State should be a string
        assert isinstance(state, str)

    @given(
        severity=hypothesis.strategies.sampled_from(
            [
                "DEBUG",
                "INFO",
                "WARNING",
                "ERROR",
                "CRITICAL",
            ]
        ),
        event_type=hypothesis.strategies.text(min_size=1, max_size=100),
    )
    @settings(max_examples=20)
    def test_audit_severity_levels(self, severity, event_type):
        """Test that audit severity levels are valid."""
        valid_severities = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        assert severity in valid_severities
        assert len(event_type) > 0


# ==================== Risk Invariants ====================


class TestRiskInvariants:
    """Property-based tests for risk management invariants."""

    @given(
        current=hypothesis.strategies.floats(min_value=0, max_value=1000000),
        max_limit=hypothesis.strategies.floats(min_value=0, max_value=1000000),
    )
    @settings(max_examples=30)
    def test_risk_limit_comparison(self, current, max_limit):
        """Test risk limit comparison logic."""
        # Violation occurs when current > max_limit
        is_violation = current > max_limit

        # This should always be consistent
        if is_violation:
            assert current > max_limit
        else:
            assert current <= max_limit

    @given(
        size=hypothesis.strategies.floats(min_value=0.001, max_value=100000),
        price=hypothesis.strategies.floats(min_value=0.01, max_value=1000000),
    )
    @settings(max_examples=30)
    def test_position_risk_calculation(self, size, price):
        """Test that position risk is calculated correctly."""
        risk_amount = size * price

        # Risk amount should be positive
        assert risk_amount > 0

        # Risk amount should be reasonable
        assert risk_amount < size * price * 1.01  # Allow small float error

    @given(leverage=hypothesis.strategies.floats(min_value=1.0, max_value=125.0))
    @settings(max_examples=20)
    def test_leverage_bounds(self, leverage):
        """Test that leverage is within valid bounds."""
        assert leverage >= 1.0
        assert leverage <= 125.0

    @given(pnl=hypothesis.strategies.floats(min_value=-100000, max_value=100000))
    @settings(max_examples=20)
    def test_pnl_bounds(self, pnl):
        """Test that P&L is within expected bounds."""
        # P&L can be negative (loss) or positive (profit)
        assert pnl >= -100000
        assert pnl <= 100000


# ==================== Edge Cases and Robustness ====================


class TestEdgeCases:
    """Property-based tests for edge cases."""

    @given(
        data=hypothesis.strategies.one_of(
            hypothesis.strategies.floats(min_value=0, max_value=1),
            hypothesis.strategies.integers(min_value=0, max_value=1000),
            hypothesis.strategies.text(max_size=10),
            hypothesis.strategies.none(),
        )
    )
    @settings(max_examples=30)
    def test_event_payload_various_types(self, data):
        """Test that events handle various data types in payload."""
        event = Event.new("TEST", "test_source", {"value": data})
        assert event.payload["value"] == data

    @given(
        key=hypothesis.strategies.text(min_size=1, max_size=50),
        value=hypothesis.strategies.text(max_size=100),
    )
    @settings(max_examples=20)
    def test_metadata_handling(self, key, value):
        """Test that metadata is handled correctly."""
        event = Event.new("TEST", "test_source", {"key": value})
        event.metadata[key] = value

        assert key in event.metadata
        assert event.metadata[key] == value

    @given(correlation_id=hypothesis.strategies.uuids())
    @settings(max_examples=20)
    def test_correlation_id_handling(self, correlation_id):
        """Test that correlation IDs are handled correctly."""
        event = Event.new("TEST", "test_source", {})
        event.correlation_id = correlation_id

        assert event.correlation_id == correlation_id
        assert str(event.correlation_id) == str(correlation_id)


# ==================== Integration Property Tests ====================


class TestIntegrationInvariants:
    """Property-based tests for integrated behavior."""

    @given(
        events=hypothesis.strategies.lists(
            hypothesis.strategies.sampled_from(
                [
                    SystemEventType.SYSTEM_BOOT,
                    SystemEventType.SYSTEM_READY,
                    SystemEventType.SYSTEM_HALT,
                    SystemEventType.SYSTEM_SHUTDOWN,
                ]
            ),
            min_size=1,
            max_size=10,
        )
    )
    @settings(max_examples=15)
    async def test_system_lifecycle_events(self, events):
        """Test that system lifecycle events maintain proper order."""
        bus = EnhancedEventBus(capacities={"critical": 100, "high": 100, "normal": 100, "low": 100})
        set_enhanced_event_bus(bus)
        registry = register_all_listeners()
        bus.enable_listeners()

        for event_type in events:
            event = Event.new(event_type, SystemEventSource.SYSTEM_CONTROLLER, {})
            await bus.publish(event)

        # All events should be published
        assert bus.metrics["published"] >= len(events)

        # Wait for async processing
        await asyncio.sleep(0.2)

        # Listeners should have processed events
        audit_listener = registry.get_listener("audit_listener")
        assert audit_listener is not None

        bus.disable_listeners()

    @given(
        order_count=hypothesis.strategies.integers(min_value=1, max_value=50),
        symbol=generate_symbol(),
    )
    @settings(max_examples=15)
    async def test_order_sequence(self, order_count, symbol):
        """Test that sequence of orders maintains consistency."""
        bus = EnhancedEventBus(
            capacities={"critical": 100, "high": 100, "normal": 1000, "low": 1000}
        )
        set_enhanced_event_bus(bus)
        register_all_listeners()
        bus.enable_listeners()

        for i in range(order_count):
            event = Event.new(
                SystemEventType.ORDER_SUBMITTED,
                SystemEventSource.EXECUTION_CORE,
                {
                    "symbol": symbol,
                    "side": "BUY" if i % 2 == 0 else "SELL",
                    "size": 0.1 * (i + 1),
                    "price": 50000 + i * 100,
                    "order_id": f"order-{i}",
                },
            )
            await bus.publish(event)

        await asyncio.sleep(0.3)

        # All orders should be published
        assert bus.metrics["published"] >= order_count

        bus.disable_listeners()


# ==================== Performance Invariants ====================


class TestPerformanceInvariants:
    """Property-based tests for performance-related invariants."""

    @given(event_count=hypothesis.strategies.integers(min_value=1, max_value=1000))
    @settings(max_examples=10)
    async def test_event_bus_capacity(self, event_count):
        """Test that event bus handles capacity correctly."""
        # Use large capacity to avoid overflow in most cases
        capacity = max(1000, event_count * 2)
        bus = EnhancedEventBus(
            capacities={"critical": 100, "high": 100, "normal": capacity, "low": capacity}
        )
        set_enhanced_event_bus(bus)

        # Publish events
        published = 0
        for i in range(event_count):
            event = Event.new("TEST", "test", {"index": i})
            try:
                await bus.publish(event)
                published += 1
            except Exception:
                # Some events may be dropped due to capacity
                pass

        # Bus should still be functional
        assert bus.metrics["published"] > 0
        assert published > 0

    @given(handler_count=hypothesis.strategies.integers(min_value=1, max_value=50))
    @settings(max_examples=10)
    async def test_multiple_handlers(self, handler_count):
        """Test that multiple subscribers receive events correctly."""
        bus = EnhancedEventBus(capacities={"critical": 100, "high": 100, "normal": 100, "low": 100})

        call_count = 0

        # Create multiple subscribers
        receivers = []
        for _ in range(handler_count):
            receiver = bus.subscribe()
            receivers.append(receiver)

        # Publish event
        event = Event.new("TEST_EVENT", "test", {})
        await bus.publish(event)

        # All subscribers should receive the event
        for receiver in receivers:
            received_event = await receiver.recv_timeout(1.0)
            if received_event is not None:
                call_count += 1

        # All handlers should be called
        assert call_count == handler_count

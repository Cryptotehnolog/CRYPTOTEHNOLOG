# ==================== Tests for circuit_breaker.py ====================

import asyncio
import time

import pytest

from cryptotechnolog.core.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerError,
    CircuitState,
    circuit_breaker,
)


class TestCircuitState:
    """Tests for CircuitState enum."""

    def test_circuit_state_values(self):
        """Test CircuitState enum values."""
        assert CircuitState.CLOSED.value == "closed"
        assert CircuitState.OPEN.value == "open"
        assert CircuitState.HALF_OPEN.value == "half_open"


class TestCircuitBreakerError:
    """Tests for CircuitBreakerError exception."""

    def test_circuit_breaker_error_is_exception(self):
        """Test CircuitBreakerError inherits from Exception."""
        assert issubclass(CircuitBreakerError, Exception)

    def test_circuit_breaker_error_message(self):
        """Test CircuitBreakerError can hold message."""
        error = CircuitBreakerError("Test error")
        assert str(error) == "Test error"


class TestCircuitBreaker:
    """Tests for CircuitBreaker class."""

    def test_init_default(self):
        """Test initialization with default values."""
        cb = CircuitBreaker(name="test")
        assert cb.name == "test"
        assert cb.state == CircuitState.CLOSED
        assert cb.is_closed
        assert not cb.is_open
        assert not cb.is_half_open
        assert cb.failure_count == 0

    def test_init_custom_values(self):
        """Test initialization with custom values."""
        cb = CircuitBreaker(
            name="custom",
            failure_threshold=10,
            recovery_timeout=30,
            success_threshold=5,
        )
        assert cb.name == "custom"
        assert cb._failure_threshold == 10
        assert cb._recovery_timeout == 30
        assert cb._success_threshold == 5

    def test_properties(self):
        """Test all property getters."""
        cb = CircuitBreaker(name="test")
        assert cb.name == "test"
        assert cb.state == CircuitState.CLOSED
        assert cb.is_closed
        assert not cb.is_open
        assert not cb.is_half_open
        assert cb.failure_count == 0

    def test_reset(self):
        """Test manual reset."""
        cb = CircuitBreaker(name="test")
        cb._failure_count = 5
        cb._state = CircuitState.OPEN
        
        cb.reset()
        
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_get_stats(self):
        """Test get_stats returns correct data."""
        cb = CircuitBreaker(
            name="test",
            failure_threshold=5,
            recovery_timeout=60,
        )
        
        stats = cb.get_stats()
        
        assert stats["name"] == "test"
        assert stats["state"] == "closed"
        assert stats["failure_count"] == 0
        assert stats["success_count"] == 0
        assert stats["failure_threshold"] == 5
        assert stats["recovery_timeout"] == 60


class TestCircuitBreakerStateTransitions:
    """Tests for circuit breaker state transitions."""

    @pytest.mark.asyncio
    async def test_success_in_closed_state(self):
        """Test success recording in CLOSED state."""
        cb = CircuitBreaker(name="test", failure_threshold=3)
        
        async with cb:
            pass
        
        assert cb.failure_count == 0
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_failure_opens_circuit(self):
        """Test failures open circuit after threshold."""
        cb = CircuitBreaker(name="test", failure_threshold=3)
        
        for _ in range(3):
            try:
                async with cb:
                    raise Exception("error")
            except Exception:
                pass
        
        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_excluded_exception_not_counted(self):
        """Test excluded exceptions don't count as failures."""
        cb = CircuitBreaker(
            name="test",
            failure_threshold=2,
            excluded_exceptions=(ValueError,),
        )
        
        # These shouldn't count
        for _ in range(2):
            try:
                async with cb:
                    raise ValueError("excluded")
            except ValueError:
                pass
        
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    @pytest.mark.asyncio
    async def test_open_blocks_execution(self):
        """Test OPEN state blocks execution."""
        cb = CircuitBreaker(name="test", failure_threshold=1)
        
        # Open the circuit
        try:
            async with cb:
                raise Exception("error")
        except Exception:
            pass
        
        assert cb.state == CircuitState.OPEN
        
        # Now should raise error
        with pytest.raises(CircuitBreakerError):
            async with cb:
                pass


class TestCircuitBreakerDecorator:
    """Tests for circuit_breaker decorator."""

    def test_decorator_creates_breaker(self):
        """Test decorator creates circuit breaker."""
        @circuit_breaker("test", failure_threshold=3)
        async def test_func():
            return "success"
        
        assert hasattr(test_func, "circuit_breaker")
        assert test_func.circuit_breaker.name == "test"

    @pytest.mark.asyncio
    async def test_decorator_executes_function(self):
        """Test decorator executes wrapped function."""
        @circuit_breaker("test")
        async def test_func():
            return "success"
        
        result = await test_func()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_decorator_protects_function(self):
        """Test decorator protects function after failures."""
        call_count = 0
        
        @circuit_breaker("test", failure_threshold=2)
        async def test_func():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise Exception("error")
            return "success"
        
        # First two calls fail
        for _ in range(2):
            try:
                await test_func()
            except Exception:
                pass
        
        # Third call should be blocked because circuit is open
        with pytest.raises(CircuitBreakerError):
            await test_func()


class TestCircuitBreakerAsync:
    """Additional async tests for CircuitBreaker."""

    @pytest.mark.asyncio
    async def test_half_open_to_closed_transition(self):
        """Test transition from HALF_OPEN to CLOSED after successes."""
        cb = CircuitBreaker(
            name="test",
            failure_threshold=1,
            success_threshold=2,
        )
        
        # Open the circuit
        try:
            async with cb:
                raise Exception("error")
        except Exception:
            pass
        
        assert cb.state == CircuitState.OPEN
        
        # Wait for recovery
        cb._last_failure_time = 0
        
        # Should transition to HALF_OPEN
        async with cb:
            pass
        
        assert cb.state == CircuitState.HALF_OPEN
        
        # Two more successes should close it
        async with cb:
            pass
        async with cb:
            pass
        
        assert cb.state == CircuitState.CLOSED

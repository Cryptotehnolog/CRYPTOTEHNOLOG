"""
Circuit Breaker Pattern Implementation.

Provides fault tolerance for external dependencies (DB, Redis, Exchange APIs).
States: CLOSED (normal) -> OPEN (failing) -> HALF_OPEN (testing recovery)

Features:
- Configurable failure threshold and recovery timeout
- Success rate tracking
- Event callbacks for state changes
- Thread-safe operation
"""

from __future__ import annotations

import asyncio
from enum import Enum
from functools import wraps
import time
from typing import TYPE_CHECKING, Any, TypeVar

from cryptotechnolog.config import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

logger = get_logger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing - requests blocked
    HALF_OPEN = "half_open"  # Testing recovery


class CircuitBreakerError(Exception):
    """Raised when circuit is open."""

    pass


class CircuitBreaker:
    """
    Circuit breaker for fault tolerance.

    Prevents cascading failures by failing fast when a service is down.

    Args:
        failure_threshold: Number of failures before opening circuit
        recovery_timeout: Seconds to wait before trying recovery
        success_threshold: Successes needed in HALF_OPEN to close circuit
        excluded_exceptions: Exceptions that don't count as failures

    Example:
        >>> cb = CircuitBreaker(failure_threshold=5, recovery_timeout=30)
        >>> async with cb:
        ...     await redis_client.ping()
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        success_threshold: int = 3,
        excluded_exceptions: tuple[type[Exception], ...] = (),
        on_state_change: Callable[[CircuitState, CircuitState], None] | None = None,
    ) -> None:
        self._name = name
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._success_threshold = success_threshold
        self._excluded_exceptions = excluded_exceptions
        self._on_state_change = on_state_change

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = 0.0

        self._lock = asyncio.Lock()

        logger.info(
            "Circuit breaker initialized",
            name=name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
        )

    @property
    def name(self) -> str:
        """Get circuit breaker name."""
        return self._name

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self._state

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        return self._state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (failing)."""
        return self._state == CircuitState.OPEN

    @property
    def is_half_open(self) -> bool:
        """Check if circuit is half-open (testing recovery)."""
        return self._state == CircuitState.HALF_OPEN

    @property
    def failure_count(self) -> int:
        """Get current failure count."""
        return self._failure_count

    async def _check_recovery(self) -> None:
        """Check if circuit should transition from OPEN to HALF_OPEN."""
        if self._state != CircuitState.OPEN:
            return

        time_since_failure = time.time() - self._last_failure_time
        if time_since_failure >= self._recovery_timeout:
            await self._transition_to(CircuitState.HALF_OPEN)
            self._success_count = 0

    async def _transition_to(self, new_state: CircuitState) -> None:
        """Transition to new state with callback."""
        old_state = self._state
        self._state = new_state

        logger.info(
            "Circuit breaker state changed",
            name=self._name,
            old_state=old_state.value,
            new_state=new_state.value,
        )

        if self._on_state_change:
            try:
                self._on_state_change(old_state, new_state)
            except Exception as e:
                logger.warning(
                    "Circuit breaker state change callback failed",
                    name=self._name,
                    error=str(e),
                )

    async def _record_success(self) -> None:
        """Record successful operation."""
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self._success_threshold:
                await self._transition_to(CircuitState.CLOSED)
                self._failure_count = 0
        elif self._state == CircuitState.CLOSED:
            # Reset failure count on success
            self._failure_count = max(0, self._failure_count - 1)

    async def _record_failure(self) -> None:
        """Record failed operation."""
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._state == CircuitState.HALF_OPEN:
            # Any failure in HALF_OPEN opens the circuit again
            await self._transition_to(CircuitState.OPEN)
        elif self._state == CircuitState.CLOSED and self._failure_count >= self._failure_threshold:
            await self._transition_to(CircuitState.OPEN)

    async def __aenter__(self) -> CircuitBreaker:
        """Acquire circuit breaker."""
        async with self._lock:
            await self._check_recovery()

            if self._state == CircuitState.OPEN:
                raise CircuitBreakerError(
                    f"Circuit breaker '{self._name}' is OPEN. "
                    f"Recovery timeout: {self._recovery_timeout}s"
                )

        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Release circuit breaker."""
        async with self._lock:
            if exc_val is None:
                await self._record_success()
            elif isinstance(exc_val, self._excluded_exceptions):
                # Excluded exceptions don't affect circuit
                pass
            else:
                await self._record_failure()

    async def execute(
        self, func: Callable[..., Coroutine[Any, Any, T]], *args: Any, **kwargs: Any
    ) -> Coroutine[Any, Any, T]:
        """Execute function with circuit breaker protection.

        Args:
            func: Async function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Coroutine that executes the function with circuit breaker protection

        Raises:
            CircuitBreakerError: If circuit is open
        """
        @wraps(func)
        async def wrapped() -> T:
            async with self:
                return await func(*args, **kwargs)

        return wrapped()

    def reset(self) -> None:
        """Manually reset circuit breaker to closed state."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = 0.0

        logger.info("Circuit breaker manually reset", name=self._name)

    def get_stats(self) -> dict[str, Any]:
        """Get circuit breaker statistics."""
        return {
            "name": self._name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "failure_threshold": self._failure_threshold,
            "recovery_timeout": self._recovery_timeout,
            "last_failure_time": self._last_failure_time,
        }


# ==================== Decorator ====================


def circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    recovery_timeout: int = 60,
    success_threshold: int = 3,
) -> Callable[
    [Callable[..., Coroutine[Any, Any, T]]], Callable[..., Coroutine[Any, Any, T]]
]:
    """Decorator to add circuit breaker to async functions.

    Args:
        name: Circuit breaker name
        failure_threshold: Failures before opening
        recovery_timeout: Seconds before recovery attempt
        success_threshold: Successes needed to close

    Example:
        @circuit_breaker("redis", failure_threshold=3)
        async def get_from_redis(key: str) -> str | None:
            return await redis.get(key)
    """

    def decorator(
        func: Callable[..., Coroutine[Any, Any, T]]
    ) -> Callable[..., Coroutine[Any, Any, T]]:
        _breaker = CircuitBreaker(
            name=name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            success_threshold=success_threshold,
        )

        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            async with _breaker:
                return await func(*args, **kwargs)

        # Attach breaker to function for inspection
        wrapper.circuit_breaker = _breaker  # type: ignore[attr-defined]
        return wrapper

    return decorator

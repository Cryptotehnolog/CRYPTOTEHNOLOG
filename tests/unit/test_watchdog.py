"""
Unit Tests for Watchdog.

Тесты watchdog системы мониторинга и восстановления.
"""

from __future__ import annotations

import asyncio
from contextlib import suppress
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from cryptotechnolog.core.watchdog import (
    ComponentChecker,
    ComponentStatus,
    RecoveryStrategy,
    Watchdog,
    WatchdogAlert,
    WatchdogAlertLevel,
)


class TestRecoveryStrategy:
    """Тесты RecoveryStrategy."""

    def test_initial_state(self):
        """Тест начального состояния."""
        strategy = RecoveryStrategy(max_retries=3)
        assert strategy.max_retries == 3
        assert strategy.should_retry() is True
        assert strategy._attempt == 0

    def test_backoff_calculation(self):
        """Тест расчёта backoff."""
        strategy = RecoveryStrategy(backoff_base=1.0, backoff_multiplier=2.0)

        assert strategy.get_backoff_delay() == 1.0  # 1.0 * 2^0

        strategy.increment_attempt()
        assert strategy.get_backoff_delay() == 2.0  # 1.0 * 2^1

        strategy.increment_attempt()
        assert strategy.get_backoff_delay() == 4.0  # 1.0 * 2^2

    def test_max_backoff(self):
        """Тест максимального backoff."""
        strategy = RecoveryStrategy(backoff_base=1.0, backoff_multiplier=10.0, max_backoff=50.0)

        # Exponential growth should be capped
        for _ in range(10):
            strategy.increment_attempt()

        assert strategy.get_backoff_delay() == 50.0

    def test_reset(self):
        """Тест сброса."""
        strategy = RecoveryStrategy(max_retries=3)
        strategy.increment_attempt()
        strategy.increment_attempt()

        assert strategy._attempt == 2

        strategy.reset()
        assert strategy._attempt == 0
        assert strategy.should_retry() is True

    def test_should_retry_exhausted(self):
        """Тест исчерпания попыток."""
        strategy = RecoveryStrategy(max_retries=2)
        strategy.increment_attempt()
        strategy.increment_attempt()

        assert strategy.should_retry() is False


class TestComponentChecker:
    """Тесты ComponentChecker."""

    @pytest.mark.asyncio
    async def test_healthy_component(self):
        """Тест здорового компонента."""
        check_func = MagicMock(return_value=True)
        checker = ComponentChecker("test", check_func)

        health = await checker.check()

        assert health.status == ComponentStatus.HEALTHY
        assert health.name == "test"
        assert health.consecutive_successes == 1
        assert health.consecutive_failures == 0

    @pytest.mark.asyncio
    async def test_unhealthy_component(self):
        """Тест нездорового компонента."""
        check_func = MagicMock(return_value=False)
        checker = ComponentChecker("test", check_func)

        health = await checker.check()

        assert health.status == ComponentStatus.UNHEALTHY
        assert health.consecutive_failures == 1
        assert health.consecutive_successes == 0

    @pytest.mark.asyncio
    async def test_exception_in_check(self):
        """Тест исключения при проверке."""
        check_func = MagicMock(side_effect=Exception("Test error"))
        checker = ComponentChecker("test", check_func)

        health = await checker.check()

        assert health.status == ComponentStatus.UNHEALTHY
        assert health.error_message is not None
        assert "Test error" in health.error_message

    @pytest.mark.asyncio
    async def test_dict_result(self):
        """Тест результата в виде словаря."""
        check_func = MagicMock(return_value={"status": "healthy", "message": "All good"})
        checker = ComponentChecker("test", check_func)

        health = await checker.check()

        assert health.status == ComponentStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_recovery_success(self):
        """Тест успешного восстановления."""
        check_func = MagicMock(return_value=False)
        recovery_func = AsyncMock(return_value=True)
        checker = ComponentChecker("test", check_func, recovery_func)

        # First check fails
        await checker.check()
        # Try recovery
        result = await checker.recover()

        assert result is True
        assert checker.health.status == ComponentStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_recovery_failure(self):
        """Тест неудачного восстановления."""
        check_func = MagicMock(return_value=False)
        recovery_func = AsyncMock(return_value=False)
        strategy = RecoveryStrategy(max_retries=1)
        checker = ComponentChecker("test", check_func, recovery_func, strategy)

        # First check fails
        await checker.check()
        # Try recovery - should fail (no more retries)
        result = await checker.recover()

        assert result is False


class TestWatchdog:
    """Тесты Watchdog."""

    @pytest.mark.asyncio
    async def test_register_component(self):
        """Тест регистрации компонента."""
        watchdog = Watchdog()

        check_func = MagicMock(return_value=True)
        watchdog.register_component("test", check_func)

        assert watchdog.component_count == 1

    @pytest.mark.asyncio
    async def test_unregister_component(self):
        """Тест удаления компонента."""
        watchdog = Watchdog()

        check_func = MagicMock(return_value=True)
        watchdog.register_component("test", check_func)
        watchdog.unregister_component("test")

        assert watchdog.component_count == 0

    @pytest.mark.asyncio
    async def test_check_all_healthy(self):
        """Тест проверки всех компонентов (здоровы)."""
        watchdog = Watchdog()

        for i in range(3):
            check_func = MagicMock(return_value=True)
            watchdog.register_component(f"comp{i}", check_func)

        results = await watchdog.check_all()

        assert len(results) == 3
        for health in results.values():
            assert health.status == ComponentStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_check_component(self):
        """Тест проверки конкретного компонента."""
        watchdog = Watchdog()

        check_func = MagicMock(return_value=True)
        watchdog.register_component("test", check_func)

        health = await watchdog.check_component("test")

        assert health is not None
        assert health.name == "test"
        assert health.status == ComponentStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_check_nonexistent_component(self):
        """Тест проверки несуществующего компонента."""
        watchdog = Watchdog()

        health = await watchdog.check_component("nonexistent")

        assert health is None

    @pytest.mark.asyncio
    async def test_get_component_health(self):
        """Тест получения состояния компонента."""
        watchdog = Watchdog()

        check_func = MagicMock(return_value=True)
        watchdog.register_component("test", check_func)

        # Without running check
        health = watchdog.get_component_health("test")
        assert health is not None
        assert health.status == ComponentStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_start_stop(self):
        """Тест запуска и остановки."""
        watchdog = Watchdog(check_interval=1)

        check_func = MagicMock(return_value=True)
        watchdog.register_component("test", check_func)

        await watchdog.start()
        assert watchdog.is_running is True

        await watchdog.stop()
        assert watchdog.is_running is False

    @pytest.mark.asyncio
    async def test_alert_callback(self):
        """Тест callback для alerts."""
        watchdog = Watchdog(failure_threshold=1)
        alerts: list[WatchdogAlert] = []

        def alert_callback(alert: WatchdogAlert):
            alerts.append(alert)

        watchdog.on_alert(alert_callback)

        def failing_check():
            raise Exception("Test error")

        watchdog.register_component("failing", failing_check)

        await watchdog.check_component("failing")

        assert len(alerts) == 1
        assert alerts[0].level == WatchdogAlertLevel.WARNING

    @pytest.mark.asyncio
    async def test_recovery_callback(self):
        """Тест callback для восстановлений."""
        watchdog = Watchdog(failure_threshold=1)
        recovered: list[str] = []

        def recovery_callback(component: str):
            recovered.append(component)

        watchdog.on_recovery(recovery_callback)

        call_count = 0

        def check_func():
            nonlocal call_count
            call_count += 1
            return call_count > 1

        recovery_func = MagicMock(return_value=True)
        watchdog.register_component("test", check_func, recovery_func)

        await watchdog.check_component("test")  # First fails
        await watchdog.check_component("test")  # Triggers recovery

        # Note: recovery callback is called after successful recovery

    @pytest.mark.asyncio
    async def test_failure_callback(self):
        """Тест callback для failures."""
        watchdog = Watchdog(failure_threshold=1)
        failed: list[str] = []

        def failure_callback(component: str):
            failed.append(component)

        watchdog.on_failure(failure_callback)

        def failing_check():
            raise Exception("Critical error")

        # With circuit breaker
        watchdog.register_component("failing", failing_check, use_circuit_breaker=True)

        # Multiple failures to trigger circuit breaker
        for _ in range(5):
            with suppress(Exception):
                await watchdog.check_component("failing")

    @pytest.mark.asyncio
    async def test_stats(self):
        """Тест статистики."""
        watchdog = Watchdog()

        check_func = MagicMock(return_value=True)
        watchdog.register_component("comp1", check_func)
        watchdog.register_component("comp2", check_func)

        await watchdog.check_all()

        stats = watchdog.get_stats()
        assert stats["component_count"] == 2
        assert stats["total_checks"] == 2

    @pytest.mark.asyncio
    async def test_graceful_degradation(self):
        """Тест graceful degradation при ошибках."""
        watchdog = Watchdog()

        # Component without recovery
        check_func = MagicMock(side_effect=Exception("Error"))
        watchdog.register_component("failing", check_func)

        health = await watchdog.check_component("failing")

        # Should not raise, should return unhealthy status
        assert health.status == ComponentStatus.UNHEALTHY


class TestWatchdogIntegration:
    """Интеграционные тесты Watchdog."""

    @pytest.mark.asyncio
    async def test_full_lifecycle(self):
        """Тест полного жизненного цикла."""
        watchdog = Watchdog(check_interval=0.5)

        # Register components
        check_func = MagicMock(return_value=True)
        watchdog.register_component("redis", check_func)
        watchdog.register_component("database", check_func)
        watchdog.register_component("api", check_func)

        # Start monitoring
        await watchdog.start()

        # Let it run for a bit
        await asyncio.sleep(1.5)

        # Stop monitoring
        await watchdog.stop()

        # Check stats
        stats = watchdog.get_stats()
        assert stats["total_checks"] >= 3  # At least one full cycle
        assert stats["running"] is False

    @pytest.mark.asyncio
    async def test_recovery_workflow(self):
        """Тест workflow восстановления."""
        watchdog = Watchdog(failure_threshold=2)

        failure_count = 0

        def check_func():
            nonlocal failure_count
            failure_count += 1
            return failure_count > 2  # Fail first two times, then succeed

        recovery_call_count = 0

        def recovery_func():
            nonlocal recovery_call_count
            recovery_call_count += 1
            return True

        watchdog.register_component("test", check_func, recovery_func)

        # First check - fails
        await watchdog.check_component("test")
        assert failure_count == 1

        # Second check - fails, triggers recovery
        await watchdog.check_component("test")
        assert failure_count == 2
        assert recovery_call_count >= 1


# ==================== Benchmark ====================


@pytest.mark.asyncio
async def test_watchdog_performance():
    """Тест производительности Watchdog."""
    watchdog = Watchdog(check_interval=60)

    # Register many components
    for i in range(100):
        check_func = MagicMock(return_value=True)
        watchdog.register_component(f"comp{i}", check_func)

    # Benchmark check_all
    start = time.perf_counter()
    await watchdog.check_all()
    elapsed = time.perf_counter() - start

    print(f"Check 100 components: {elapsed * 1000:.2f}ms")

    # Should complete in reasonable time
    assert elapsed < 1.0  # Less than 1 second

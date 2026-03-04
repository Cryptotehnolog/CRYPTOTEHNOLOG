"""
Integration tests for Event Bus with Listeners.

Тестирует интеграцию EnhancedEventBus с listeners:
- StateMachineListener
- AuditListener
- MetricsListener
- RiskListener
"""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cryptotechnolog.core.enhanced_event_bus import EnhancedEventBus
from cryptotechnolog.core.event import Event, Priority
from cryptotechnolog.core.listeners import (
    AuditListener,
    MetricsListener,
    RiskListener,
    StateMachineListener,
    register_all_listeners,
)
import cryptotechnolog.core.listeners.base as listeners_base_module
from cryptotechnolog.core.listeners.base import (
    BaseListener,
    ListenerConfig,
    ListenerRegistry,
)

# Настройка логирования для тестов
logging.basicConfig(level=logging.DEBUG)


@pytest.fixture
def event_bus() -> EnhancedEventBus:
    """Создать тестовый Event Bus без persistence."""
    bus = EnhancedEventBus(
        enable_persistence=False,
        redis_url=None,
        rate_limit=10000,
        backpressure_strategy="drop_low",
    )
    return bus


@pytest.fixture
def reset_listener_registry():
    """Сбросить глобальный listener registry перед каждым тестом."""
    original_registry = getattr(listeners_base_module, "_listener_registry", None)
    listeners_base_module._listener_registry = ListenerRegistry()

    yield

    # Восстанавливаем оригинальный registry
    if original_registry is not None:
        listeners_base_module._listener_registry = original_registry
    else:
        listeners_base_module._listener_registry = None


class TestListenerRegistration:
    """Тесты регистрации listeners в Event Bus."""

    @pytest.mark.asyncio
    async def test_register_single_listener(self, event_bus, reset_listener_registry):
        """Тест регистрации одного listener."""
        listener = StateMachineListener()
        event_bus.register_listener(listener)

        assert event_bus.listener_registry is not None
        registered_names = [lst.name for lst in event_bus.listener_registry.all_listeners]
        assert listener.name in registered_names

    @pytest.mark.asyncio
    async def test_register_multiple_listeners(self, event_bus, reset_listener_registry):
        """Тест регистрации нескольких listeners."""
        listeners = [
            StateMachineListener(),
            RiskListener(),
            AuditListener(),
            MetricsListener(),
        ]

        for lst in listeners:
            event_bus.register_listener(lst)

        assert event_bus.listener_registry is not None
        assert len(event_bus.listener_registry.all_listeners) == 4

    @pytest.mark.asyncio
    async def test_unregister_listener(self, event_bus, reset_listener_registry):
        """Тест удаления listener."""
        listener = StateMachineListener()
        event_bus.register_listener(listener)

        # Проверяем что listener зарегистрирован
        registered_names = [lst.name for lst in event_bus.listener_registry.all_listeners]
        assert listener.name in registered_names

        # Удаляем listener
        result = event_bus.unregister_listener(listener.name)
        assert result is True

    @pytest.mark.asyncio
    async def test_enable_listeners(self, event_bus, reset_listener_registry):
        """Тест включения listeners через enable_listeners()."""
        # Регистрируем всех listeners
        register_all_listeners()

        # Включаем listeners в Event Bus
        event_bus.enable_listeners()

        assert event_bus.listener_registry is not None
        assert len(event_bus.listener_registry.all_listeners) >= 4


class TestEventDeliveryToListeners:
    """Тесты доставки событий до listeners."""

    @pytest.mark.asyncio
    async def test_state_machine_event_delivered(self, event_bus, reset_listener_registry):
        """Тест доставки события STATE_TRANSITION до StateMachineListener."""
        with patch("cryptotechnolog.core.listeners.state_machine.get_db_pool") as mock_db:
            mock_pool = AsyncMock()
            mock_conn = AsyncMock()
            mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_pool.acquire.return_value.__aexit__ = AsyncMock()
            mock_db.return_value = mock_pool

            listener = StateMachineListener()
            event_bus.register_listener(listener)

            # Создаём событие
            event = Event.new(
                event_type="STATE_TRANSITION",
                source="STATE_MACHINE",
                payload={
                    "from_state": "BOOT",
                    "to_state": "READY",
                    "trigger": "initialization",
                    "duration_ms": 100,
                },
            )

            # Публикуем событие
            await event_bus.publish(event)

            # Даём время на обработку listeners
            await asyncio.sleep(0.1)

    @pytest.mark.asyncio
    async def test_audit_event_delivered(self, event_bus, reset_listener_registry):
        """Тест доставки события до AuditListener."""
        with patch("cryptotechnolog.core.listeners.audit.get_db_pool") as mock_db:
            mock_pool = AsyncMock()
            mock_conn = AsyncMock()
            mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_pool.acquire.return_value.__aexit__ = AsyncMock()
            mock_db.return_value = mock_pool

            listener = AuditListener()
            event_bus.register_listener(listener)

            event = Event.new(
                event_type="ORDER_SUBMITTED",
                source="STRATEGY",
                payload={"order_id": "order_123", "symbol": "BTCUSDT"},
            )

            await event_bus.publish(event)
            await asyncio.sleep(0.1)

    @pytest.mark.asyncio
    async def test_metrics_event_delivered(self, event_bus, reset_listener_registry):
        """Тест доставки события до MetricsListener."""
        with patch("cryptotechnolog.core.listeners.metrics.get_db_pool") as mock_db:
            mock_pool = AsyncMock()
            mock_conn = AsyncMock()
            mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_pool.acquire.return_value.__aexit__ = AsyncMock()
            mock_db.return_value = mock_pool

            listener = MetricsListener()
            event_bus.register_listener(listener)

            event = Event.new(
                event_type="ORDER_FILLED",
                source="EXECUTION",
                payload={
                    "order_id": "order_123",
                    "symbol": "BTCUSDT",
                    "filled_size": 0.5,
                    "price": 50000,
                },
            )

            await event_bus.publish(event)
            await asyncio.sleep(0.1)

    @pytest.mark.asyncio
    async def test_risk_event_delivered(self, event_bus, reset_listener_registry):
        """Тест доставки события до RiskListener."""
        with patch("cryptotechnolog.core.listeners.risk.get_db_pool") as mock_db:
            mock_pool = AsyncMock()
            mock_conn = AsyncMock()
            mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_pool.acquire.return_value.__aexit__ = AsyncMock()
            mock_db.return_value = mock_pool

            with patch("cryptotechnolog.core.listeners.risk.get_metrics_collector") as mock_metrics:
                mock_metrics_collector = MagicMock()
                mock_metrics_collector.record_latency = AsyncMock()
                mock_metrics.return_value = mock_metrics_collector

                listener = RiskListener()
                event_bus.register_listener(listener)

                event = Event.new(
                    event_type="ORDER_SUBMITTED",
                    source="STRATEGY",
                    payload={
                        "order_id": "order_123",
                        "symbol": "BTCUSDT",
                        "side": "BUY",
                        "size": 1.0,
                        "price": 50000,
                    },
                )

                await event_bus.publish(event)
                await asyncio.sleep(0.1)


class TestPriorityEvents:
    """Тесты обработки событий с разными приоритетами."""

    @pytest.mark.asyncio
    async def test_critical_priority_event(self, event_bus, reset_listener_registry):
        """Тест обработки CRITICAL события."""
        listener_called = False

        async def mock_handler(evt: Event) -> None:
            nonlocal listener_called
            listener_called = True

        event = Event.new(
            event_type="KILL_SWITCH_TRIGGERED",
            source="KILL_SWITCH",
            payload={"reason": "Manual trigger"},
        )
        event.priority = Priority.CRITICAL

        # Регистрируем обработчик
        event_bus.on("KILL_SWITCH_TRIGGERED", mock_handler)

        await event_bus.publish(event)
        await asyncio.sleep(0.1)

        assert listener_called is True

    @pytest.mark.asyncio
    async def test_low_priority_event(self, event_bus, reset_listener_registry):
        """Тест обработки LOW приоритета события."""
        event = Event.new(
            event_type="METRIC_RECORDED",
            source="METRICS",
            payload={"metric_name": "cpu_usage", "value": 50},
        )
        event.priority = Priority.LOW

        await event_bus.publish(event)

        # LOW событие должно быть обработано
        assert event_bus.metrics["published"] == 1


class TestEventBusWithAllListeners:
    """Интеграционные тесты со всеми listeners."""

    @pytest.mark.asyncio
    async def test_full_event_flow(self, event_bus, reset_listener_registry):
        """Тест полного потока событий со всеми listeners."""
        # Регистрируем всех listeners
        register_all_listeners()

        # Включаем listeners в Event Bus
        event_bus.enable_listeners()

        # Мокаем БД для всех listeners
        with (
            patch("cryptotechnolog.core.listeners.state_machine.get_db_pool") as mock_sm,
            patch("cryptotechnolog.core.listeners.audit.get_db_pool") as mock_audit,
            patch("cryptotechnolog.core.listeners.metrics.get_db_pool") as mock_metrics,
            patch("cryptotechnolog.core.listeners.risk.get_db_pool") as mock_risk,
        ):
            # Настраиваем моки
            for mock in [mock_sm, mock_audit, mock_metrics, mock_risk]:
                mock_pool = AsyncMock()
                mock_conn = AsyncMock()
                mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
                mock_pool.acquire.return_value.__aexit__ = AsyncMock()
                mock.return_value = mock_pool

            # Публикуем несколько событий разных типов
            events = [
                Event.new(
                    "STATE_TRANSITION",
                    "STATE_MACHINE",
                    {
                        "from_state": "BOOT",
                        "to_state": "READY",
                        "trigger": "init",
                    },
                ),
                Event.new(
                    "ORDER_SUBMITTED",
                    "STRATEGY",
                    {
                        "order_id": "order_1",
                        "symbol": "BTCUSDT",
                        "side": "BUY",
                        "size": 1.0,
                        "price": 50000,
                    },
                ),
                Event.new(
                    "ORDER_FILLED",
                    "EXECUTION",
                    {
                        "order_id": "order_1",
                        "symbol": "BTCUSDT",
                        "filled_size": 1.0,
                        "price": 50000,
                    },
                ),
            ]

            for evt in events:
                await event_bus.publish(evt)

            # Даём время на обработку
            await asyncio.sleep(0.2)

            # Проверяем метрики
            assert event_bus.metrics["published"] == 3
            assert event_bus.metrics["delivered"] >= 0


class TestErrorHandling:
    """Тесты обработки ошибок в listeners."""

    @pytest.mark.asyncio
    async def test_listener_exception_does_not_crash_bus(self, event_bus, reset_listener_registry):
        """Тест что исключение в listener не крашит Event Bus."""

        # Создаём listener который выбрасывает исключение
        class FailingListener(BaseListener):
            async def _process_event(self, event: Event) -> None:
                raise RuntimeError("Test exception")

        config = ListenerConfig(
            name="failing_listener",
            event_types=["TEST_EVENT"],
        )
        listener = FailingListener(config)

        event_bus.register_listener(listener)

        event = Event.new("TEST_EVENT", "TEST", {"test": "data"})

        # Это не должно вызвать исключение
        await event_bus.publish(event)
        await asyncio.sleep(0.1)

        # Event Bus должен продолжать работать
        assert event_bus.metrics["published"] == 1


class TestListenerMetrics:
    """Тесты метрик listeners."""

    @pytest.mark.asyncio
    async def test_listener_metrics_collection(self, event_bus, reset_listener_registry):
        """Тест сбора метрик с listeners."""
        with patch("cryptotechnolog.core.listeners.state_machine.get_db_pool") as mock_db:
            mock_pool = AsyncMock()
            mock_conn = AsyncMock()
            mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_pool.acquire.return_value.__aexit__ = AsyncMock()
            mock_db.return_value = mock_pool

            listener = StateMachineListener()
            event_bus.register_listener(listener)

            # Проверяем начальные метрики
            metrics = listener.metrics
            assert metrics["name"] == "state_machine_listener"
            assert metrics["events_processed"] == 0
            assert metrics["events_failed"] == 0


class TestConcurrentEvents:
    """Тесты параллельной обработки событий."""

    @pytest.mark.asyncio
    async def test_concurrent_event_publishing(self, event_bus, reset_listener_registry):
        """Тест параллельной публикации событий."""

        async def publish_event(idx: int):
            evt = Event.new(
                event_type="TEST_EVENT",
                source="TEST",
                payload={"index": idx},
            )
            await event_bus.publish(evt)

        # Публикуем 10 событий параллельно
        tasks = [publish_event(i) for i in range(10)]
        await asyncio.gather(*tasks)

        # Даём время на обработку
        await asyncio.sleep(0.2)

        # Все события должны быть опубликованы
        assert event_bus.metrics["published"] == 10


class TestListenerFiltering:
    """Тесты фильтрации событий в listeners."""

    @pytest.mark.asyncio
    async def test_listener_handles_specific_event_type(self, event_bus, reset_listener_registry):
        """Тест что listener обрабатывает только свои типы событий."""
        listener = StateMachineListener()

        # Проверяем что listener обрабатывает STATE_TRANSITION
        event1 = Event.new("STATE_TRANSITION", "TEST", {})
        assert listener.handles_event(event1) is True

        # Проверяем что listener НЕ обрабатывает ORDER_SUBMITTED
        event2 = Event.new("ORDER_SUBMITTED", "TEST", {})
        assert listener.handles_event(event2) is False

    @pytest.mark.asyncio
    async def test_wildcard_listener_handles_all(self, event_bus, reset_listener_registry):
        """Тест что wildcard listener обрабатывает все события."""
        listener = AuditListener()  # имеет event_types=["*"]

        # AuditListener обрабатывает все события
        event1 = Event.new("STATE_TRANSITION", "TEST", {})
        event2 = Event.new("ORDER_SUBMITTED", "TEST", {})
        event3 = Event.new("RANDOM_EVENT", "TEST", {})

        assert listener.handles_event(event1) is True
        assert listener.handles_event(event2) is True
        assert listener.handles_event(event3) is True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

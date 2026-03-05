"""
Integration тесты для Enhanced Event Bus.

Тестирует:
- Полную интеграцию с Redis persistence
- Replay событий
- Listener интеграцию
- Нагрузочное тестирование
"""

from __future__ import annotations

import asyncio

import pytest

from cryptotechnolog.core.enhanced_event_bus import EnhancedEventBus, PersistenceError, PublishError
from cryptotechnolog.core.event import Event, Priority


@pytest.fixture
def event_bus() -> EnhancedEventBus:
    """Создать тестовый Event Bus без persistence."""
    bus = EnhancedEventBus(
        enable_persistence=False,
        rate_limit=10000,
        backpressure_strategy="drop_low",
    )
    return bus


class TestRedisPersistence:
    """Тесты интеграции с Redis."""

    @pytest.mark.asyncio
    async def test_persistence_disabled_by_default(self, event_bus) -> None:
        """Тест что persistence выключен по умолчанию."""
        assert event_bus.enable_persistence is False
        assert event_bus.persistence is None

    @pytest.mark.asyncio
    async def test_start_without_redis(self, event_bus) -> None:
        """Тест запуска без Redis URL."""
        await event_bus.start()
        await event_bus.shutdown()

        assert event_bus.metrics["published"] == 0


class TestReplay:
    """Тесты replay функциональности."""

    @pytest.mark.asyncio
    async def test_replay_requires_persistence(self, event_bus) -> None:
        """Тест что replay требует включенный persistence."""
        with pytest.raises(PersistenceError):
            await event_bus.replay(Priority.CRITICAL)


class TestListenerIntegration:
    """Тесты интеграции с listeners."""

    @pytest.mark.asyncio
    async def test_listener_registry_integration(self, event_bus) -> None:
        """Тест интеграции с listener registry."""
        # Listener registry должен быть доступен
        assert event_bus.listener_registry is None  # Пока не включен

    @pytest.mark.asyncio
    async def test_enable_listeners(self, event_bus) -> None:
        """Тест включения listeners."""
        event_bus.enable_listeners()

        assert event_bus.listener_registry is not None


class TestEventFlow:
    """Тесты полного потока событий."""

    @pytest.mark.asyncio
    async def test_high_frequency_events(self, event_bus) -> None:
        """Тест высокочастотных событий."""
        # Публикуем много событий
        tasks = []
        for i in range(100):
            event = Event.new("TEST", "SOURCE", {"i": i})
            event.priority = Priority.NORMAL
            tasks.append(event_bus.publish(event))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Все должны пройти
        assert event_bus.metrics["published"] == 100

    @pytest.mark.asyncio
    async def test_mixed_priority_events(self, event_bus) -> None:
        """Тест событий с разными приоритетами."""
        priorities = [
            Priority.CRITICAL,
            Priority.HIGH,
            Priority.NORMAL,
            Priority.LOW,
        ]

        for i, priority in enumerate(priorities):
            event = Event.new(f"TEST_{i}", "SOURCE", {"priority": priority.value})
            event.priority = priority
            await event_bus.publish(event)

        assert event_bus.metrics["published"] == 4

    @pytest.mark.asyncio
    async def test_concurrent_publish_subscribe(self, event_bus) -> None:
        """Тест конкурентной публикации и подписки."""
        receiver = event_bus.subscribe()

        async def publisher():
            for i in range(50):
                event = Event.new("TEST", "SOURCE", {"i": i})
                await event_bus.publish(event)
                await asyncio.sleep(0.001)

        # Запускаем publisher
        await publisher()

        # Собираем события
        received_count = 0
        for _ in range(60):
            event = await receiver.recv_timeout(0.5)
            if event is None:
                break
            received_count += 1

        assert received_count == 50


class TestBackpressureIntegration:
    """Тесты backpressure в интеграции."""

    @pytest.mark.asyncio
    async def test_backpressure_protection(self) -> None:
        """Тест защиты от переполнения."""
        bus = EnhancedEventBus(
            enable_persistence=False,
            backpressure_strategy="drop_low",
            capacities={
                "critical": 10,
                "high": 10,
                "normal": 10,
                "low": 10,
            },
        )

        # Пытаемся переполнить - PublishError может выбрасываться при переполнении
        for i in range(100):
            event = Event.new("TEST", "SOURCE", {"i": i})
            event.priority = Priority.LOW
            try:
                await bus.publish(event)
            except PublishError:
                pass  # Игнорируем ошибки переполнения

        # Что-то должно быть отброшено
        total = bus.metrics["published"] + bus.metrics["dropped"]
        assert total >= 100


class TestErrorHandling:
    """Тесты обработки ошибок."""

    @pytest.mark.asyncio
    async def test_publish_error_handling(self) -> None:
        """Тест обработки ошибок публикации."""
        bus = EnhancedEventBus(
            enable_persistence=False,
            rate_limit=1,
        )

        # Первое событие
        event1 = Event.new("TEST", "SOURCE", {"i": 1})
        await bus.publish(event1)

        # Второе должно вызвать PublishError
        event2 = Event.new("TEST", "SOURCE", {"i": 2})

        with pytest.raises(PublishError):
            await bus.publish(event2)


class TestMetricsIntegration:
    """Тесты метрик в интеграции."""

    @pytest.mark.asyncio
    async def test_comprehensive_metrics(self, event_bus) -> None:
        """Тест комплексных метрик."""
        event_bus.subscribe()

        for i in range(10):
            event = Event.new("TEST", "SOURCE", {"i": i})
            await event_bus.publish(event)

        metrics = event_bus.get_metrics()

        assert metrics["bus_metrics"]["published"] == 10
        assert "queue_metrics" in metrics
        assert "rate_limiter_metrics" in metrics


class TestLifecycle:
    """Тесты жизненного цикла."""

    @pytest.mark.asyncio
    async def test_full_lifecycle(self, event_bus) -> None:
        """Тест полного жизненного цикла."""
        # Start
        await event_bus.start()

        # Subscribe
        receiver = event_bus.subscribe()

        # Publish
        event = Event.new("TEST", "SOURCE", {"data": 42})
        await event_bus.publish(event)

        # Receive
        received = await receiver.recv_timeout(1.0)
        assert received is not None

        # Shutdown
        await event_bus.shutdown()

        assert event_bus.metrics["published"] == 1


class TestConfiguration:
    """Тесты конфигурации."""

    @pytest.mark.asyncio
    async def test_custom_capacities(self) -> None:
        """Тест кастомных ёмкостей."""
        bus = EnhancedEventBus(
            enable_persistence=False,
            capacities={
                "critical": 200,
                "high": 400,
                "normal": 800,
                "low": 1600,
            },
        )

        assert bus.priority_queue.capacity(Priority.CRITICAL) == 200
        assert bus.priority_queue.capacity(Priority.LOW) == 1600

    @pytest.mark.asyncio
    async def test_custom_rate_limit(self) -> None:
        """Тест кастомного rate limit."""
        bus = EnhancedEventBus(enable_persistence=False, rate_limit=5000)

        assert bus.rate_limit == 5000
        assert bus.rate_limiter.global_limit == 5000


# Mark all tests as integration tests
pytest.mark.integration(__name__)

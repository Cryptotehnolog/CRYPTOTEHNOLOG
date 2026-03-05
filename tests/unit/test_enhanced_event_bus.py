"""
Unit тесты для Enhanced Event Bus.

Тестирует:
- PriorityQueue (4 уровня приоритета)
- RateLimiter (sliding window)
- Backpressure strategies
- Event publish/subscribe
- Metrics collection
"""

from __future__ import annotations

import asyncio
import uuid

import pytest

from cryptotechnolog.core.enhanced_event_bus import (
    BackpressureStrategy,
    EnhancedEventBus,
    PriorityQueue,
    PublishError,
    RateLimiter,
)
from cryptotechnolog.core.event import Event, Priority


class TestPriorityQueue:
    """Тесты PriorityQueue."""

    def test_default_capacities(self) -> None:
        """Тест ёмкостей по умолчанию."""
        pq = PriorityQueue()
        assert pq.capacity(Priority.CRITICAL) == 100
        assert pq.capacity(Priority.HIGH) == 500
        assert pq.capacity(Priority.NORMAL) == 10000
        assert pq.capacity(Priority.LOW) == 50000

    def test_custom_capacities(self) -> None:
        """Тест кастомных ёмкостей."""
        caps = {
            Priority.CRITICAL: 50,
            Priority.HIGH: 100,
            Priority.NORMAL: 500,
            Priority.LOW: 1000,
        }
        pq = PriorityQueue(caps)
        assert pq.capacity(Priority.CRITICAL) == 50
        assert pq.capacity(Priority.LOW) == 1000

    @pytest.mark.asyncio
    async def test_push_pop_by_priority(self) -> None:
        """Тест FIFO внутри одного приоритета."""
        pq = PriorityQueue()

        # Создаём события с одинаковым приоритетом
        event1 = Event.new("TEST", "SRC", {"id": 1})
        event1.priority = Priority.HIGH

        event2 = Event.new("TEST", "SRC", {"id": 2})
        event2.priority = Priority.HIGH

        await pq.push(event1)
        await pq.push(event2)

        popped1 = await pq.pop()
        popped2 = await pq.pop()

        assert popped1 is not None
        assert popped2 is not None
        assert popped1.payload["id"] == 1
        assert popped2.payload["id"] == 2

    @pytest.mark.asyncio
    async def test_priority_order(self) -> None:
        """Тест порядка по приоритету."""
        pq = PriorityQueue()

        # Добавляем в порядке LOW -> CRITICAL
        low = Event.new("LOW", "SRC", {"p": "low"})
        low.priority = Priority.LOW

        critical = Event.new("CRITICAL", "SRC", {"p": "critical"})
        critical.priority = Priority.CRITICAL

        high = Event.new("HIGH", "SRC", {"p": "high"})
        high.priority = Priority.HIGH

        normal = Event.new("NORMAL", "SRC", {"p": "normal"})
        normal.priority = Priority.NORMAL

        # Добавляем в произвольном порядке
        await pq.push(low)
        await pq.push(critical)
        await pq.push(high)
        await pq.push(normal)

        # Извлекаем - должен быть CRITICAL первым
        first = await pq.pop()
        assert first is not None
        assert first.event_type == "CRITICAL"

        second = await pq.pop()
        assert second is not None
        assert second.event_type == "HIGH"

    @pytest.mark.asyncio
    async def test_queue_full_returns_false(self) -> None:
        """Тест возврата False при полной очереди."""
        # Маленькая ёмкость для теста
        caps = {
            Priority.CRITICAL: 2,
            Priority.HIGH: 2,
            Priority.NORMAL: 2,
            Priority.LOW: 2,
        }
        pq = PriorityQueue(caps)

        # Заполняем очередь CRITICAL
        for i in range(2):
            event = Event.new("TEST", "SRC", {"i": i})
            event.priority = Priority.CRITICAL
            await pq.push(event)

        # Третий должен вернуть False
        event = Event.new("TEST", "SRC", {"i": 3})
        event.priority = Priority.CRITICAL
        result = await pq.push(event)

        assert result is False

    @pytest.mark.asyncio
    async def test_push_wait_with_timeout(self) -> None:
        """Тест push_wait с таймаутом."""
        caps = {
            Priority.CRITICAL: 1,
            Priority.HIGH: 1,
            Priority.NORMAL: 1,
            Priority.LOW: 1,
        }
        pq = PriorityQueue(caps)

        # Заполняем
        event1 = Event.new("TEST", "SRC", {"i": 1})
        event1.priority = Priority.CRITICAL
        await pq.push(event1)

        # Пытаемся добавить ещё одно с таймаутом 0.1 сек
        event2 = Event.new("TEST", "SRC", {"i": 2})
        event2.priority = Priority.CRITICAL
        result = await pq.push_wait(event2, timeout=0.1)

        assert result is False

    def test_size_and_capacity(self) -> None:
        """Тест методов size и capacity."""
        pq = PriorityQueue()

        assert pq.size(Priority.CRITICAL) == 0
        assert pq.capacity(Priority.CRITICAL) == 100
        assert pq.total_size() == 0

    def test_get_metrics(self) -> None:
        """Тест метрик."""
        pq = PriorityQueue()
        metrics = pq.get_metrics()

        assert "total_pushed" in metrics
        assert "total_popped" in metrics
        assert "dropped_by_priority" in metrics
        assert "queue_sizes" in metrics
        assert "queue_capacities" in metrics


class TestRateLimiter:
    """Тесты RateLimiter."""

    def test_default_global_limit(self) -> None:
        """Тест глобального лимита по умолчанию."""
        limiter = RateLimiter(global_limit=100)
        assert limiter.global_limit == 100

    def test_set_source_limit(self) -> None:
        """Тест установки лимита для источника."""
        limiter = RateLimiter()
        limiter.set_source_limit("STRATEGY", 50)

        assert limiter.source_limits["STRATEGY"] == 50

    def test_check_within_limit(self) -> None:
        """Тест проверки в пределах лимита."""
        limiter = RateLimiter(global_limit=10)

        # Первые 10 должны пройти
        for _ in range(10):
            assert limiter.check("SOURCE") is True

    def test_check_exceeds_limit(self) -> None:
        """Тест превышения лимита."""
        limiter = RateLimiter(global_limit=5)

        # Заполняем до лимита
        for _ in range(5):
            limiter.check("SOURCE")

        # Следующий должен быть отклонён
        assert limiter.check("SOURCE") is False

    def test_source_specific_limit(self) -> None:
        """Тест лимита для конкретного источника."""
        limiter = RateLimiter(global_limit=100)
        limiter.set_source_limit("STRATEGY", 3)

        # 3 от STRATEGY должны пройти
        for _ in range(3):
            assert limiter.check("STRATEGY") is True

        # 4-й должен быть отклонён
        assert limiter.check("STRATEGY") is False

        # Другой источник должен работать
        assert limiter.check("OTHER") is True

    def test_get_metrics(self) -> None:
        """Тест метрик rate limiter."""
        limiter = RateLimiter(global_limit=100)
        limiter.set_source_limit("TEST", 50)
        limiter.check("TEST")

        metrics = limiter.get_metrics()

        assert metrics["global_limit"] == 100
        assert "TEST" in metrics["source_limits"]
        assert metrics["source_limits"]["TEST"] == 50


class TestBackpressureStrategy:
    """Тесты стратегий backpressure."""

    @pytest.mark.asyncio
    async def test_drop_low_strategy(self) -> None:
        """Тест DROP_LOW стратегии."""
        bus = EnhancedEventBus(
            enable_persistence=False,
            backpressure_strategy="drop_low",
            capacities={
                "critical": 2,
                "high": 2,
                "normal": 2,
                "low": 2,
            },
        )

        # Заполняем LOW очередь
        for i in range(3):
            event = Event.new("TEST", "SRC", {"i": i})
            event.priority = Priority.LOW
            await bus.publish(event)

        # LOW события должны быть отброшены
        assert bus.metrics["dropped"] >= 1

    @pytest.mark.asyncio
    async def test_drop_normal_strategy(self) -> None:
        """Тест DROP_NORMAL стратегии."""
        bus = EnhancedEventBus(
            enable_persistence=False,
            backpressure_strategy="drop_normal",
            capacities={
                "critical": 2,
                "high": 2,
                "normal": 2,
                "low": 2,
            },
        )

        # Заполняем NORMAL очередь
        for i in range(3):
            event = Event.new("TEST", "SRC", {"i": i})
            event.priority = Priority.NORMAL
            await bus.publish(event)

        # NORMAL события должны быть отброшены
        assert bus.metrics["dropped"] >= 1

    @pytest.mark.asyncio
    async def test_set_strategy(self) -> None:
        """Тест установки стратегии."""
        bus = EnhancedEventBus(enable_persistence=False)

        bus.set_backpressure_strategy("drop_normal")
        assert bus.backpressure_strategy == BackpressureStrategy.DROP_NORMAL

        with pytest.raises(ValueError):
            bus.set_backpressure_strategy("invalid_strategy")


class TestEnhancedEventBusPublish:
    """Тесты публикации событий."""

    @pytest.mark.asyncio
    async def test_publish_basic(self) -> None:
        """Тест базовой публикации."""
        bus = EnhancedEventBus(enable_persistence=False)
        bus.subscribe()  # Добавляем подписчика

        event = Event.new("TEST", "SOURCE", {"data": 42})

        result = await bus.publish(event)

        assert result is True
        assert bus.metrics["published"] == 1

    @pytest.mark.asyncio
    async def test_publish_with_priority(self) -> None:
        """Тест публикации с приоритетом."""
        bus = EnhancedEventBus(enable_persistence=False)

        event = Event.new("TEST", "SOURCE", {"data": 42})
        event.priority = Priority.HIGH

        await bus.publish(event)

        assert bus.metrics["published"] == 1

    @pytest.mark.asyncio
    async def test_publish_with_correlation_id(self) -> None:
        """Тест publish_with_priority с correlation_id."""
        bus = EnhancedEventBus(enable_persistence=False)
        bus.subscribe()

        result = await bus.publish_with_priority(
            event_type="ORDER",
            source="STRATEGY",
            payload={"order_id": "123"},
            priority=Priority.CRITICAL,
            correlation_id=str(uuid.uuid4()),
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_publish_rate_limit_exceeded(self) -> None:
        """Тест превышения rate limit."""
        bus = EnhancedEventBus(
            enable_persistence=False,
            rate_limit=1,
        )

        event1 = Event.new("TEST", "SOURCE", {"i": 1})
        await bus.publish(event1)

        event2 = Event.new("TEST", "SOURCE", {"i": 2})

        with pytest.raises(PublishError):
            await bus.publish(event2)

        assert bus.metrics["rate_limited"] >= 1


class TestEnhancedEventBusSubscribe:
    """Тесты подписки."""

    @pytest.mark.asyncio
    async def test_subscribe_and_receive(self) -> None:
        """Тест подписки и получения событий."""
        bus = EnhancedEventBus(enable_persistence=False)

        receiver = bus.subscribe()

        event = Event.new("TEST", "SOURCE", {"data": 42})
        await bus.publish(event)

        received = await receiver.recv()

        assert received is not None
        assert received.event_type == "TEST"

    @pytest.mark.asyncio
    async def test_multiple_subscribers(self) -> None:
        """Тест нескольких подписчиков."""
        bus = EnhancedEventBus(enable_persistence=False)

        receiver1 = bus.subscribe()
        receiver2 = bus.subscribe()

        event = Event.new("TEST", "SOURCE", {"data": 42})
        await bus.publish(event)

        received1 = await receiver1.recv()
        received2 = await receiver2.recv()

        assert received1 is not None
        assert received2 is not None

    @pytest.mark.asyncio
    async def test_unsubscribe(self) -> None:
        """Тест отписки."""
        bus = EnhancedEventBus(enable_persistence=False)

        receiver = bus.subscribe()
        bus.unsubscribe(receiver)

        assert len(bus.subscribers) == 0

    @pytest.mark.asyncio
    async def test_try_recv(self) -> None:
        """Тест try_recv."""
        bus = EnhancedEventBus(enable_persistence=False)

        receiver = bus.subscribe()

        # Без событий - должен вернуть None
        result = await receiver.try_recv()
        assert result is None

        # После публикации
        event = Event.new("TEST", "SOURCE", {"data": 42})
        await bus.publish(event)

        result = await receiver.try_recv()
        assert result is not None
        assert result.event_type == "TEST"

    @pytest.mark.asyncio
    async def test_recv_timeout(self) -> None:
        """Тест recv_timeout."""
        bus = EnhancedEventBus(enable_persistence=False)

        receiver = bus.subscribe()

        # Таймаут должен вернуть None
        result = await receiver.recv_timeout(0.1)
        assert result is None

    @pytest.mark.asyncio
    async def test_receiver_close(self) -> None:
        """Тест закрытия приёмника."""
        bus = EnhancedEventBus(enable_persistence=False)

        receiver = bus.subscribe()
        receiver.close()

        result = await receiver.recv()
        assert result is None


class TestEventHandlers:
    """Тесты обработчиков событий."""

    @pytest.mark.asyncio
    async def test_on_handler(self) -> None:
        """Тест регистрации обработчика через on()."""
        bus = EnhancedEventBus(enable_persistence=False)

        received_events: list[Event] = []

        def handler(event: Event) -> None:
            received_events.append(event)

        bus.on("TEST_EVENT", handler)

        event = Event.new("TEST_EVENT", "SOURCE", {"data": 42})
        await bus.publish(event)

        await asyncio.sleep(0.1)

        assert len(received_events) == 1
        assert received_events[0].event_type == "TEST_EVENT"

    @pytest.mark.asyncio
    async def test_async_handler(self) -> None:
        """Тест async обработчика."""
        bus = EnhancedEventBus(enable_persistence=False)

        received_events: list[Event] = []

        async def handler(event: Event) -> None:
            received_events.append(event)

        bus.on("TEST_EVENT", handler)

        event = Event.new("TEST_EVENT", "SOURCE", {"data": 42})
        await bus.publish(event)

        await asyncio.sleep(0.1)

        assert len(received_events) == 1

    @pytest.mark.asyncio
    async def test_wildcard_handler(self) -> None:
        """Тест wildcard обработчика."""
        bus = EnhancedEventBus(enable_persistence=False)

        received_events: list[Event] = []

        def handler(event: Event) -> None:
            received_events.append(event)

        bus.on("*", handler)

        event1 = Event.new("EVENT_1", "SOURCE", {"data": 1})
        event2 = Event.new("EVENT_2", "SOURCE", {"data": 2})

        await bus.publish(event1)
        await bus.publish(event2)

        await asyncio.sleep(0.1)

        assert len(received_events) == 2


class TestMetrics:
    """Тесты метрик."""

    @pytest.mark.asyncio
    async def test_metrics_published(self) -> None:
        """Тест метрики published."""
        bus = EnhancedEventBus(enable_persistence=False)

        for i in range(5):
            event = Event.new("TEST", "SOURCE", {"i": i})
            await bus.publish(event)

        assert bus.metrics["published"] == 5

    @pytest.mark.asyncio
    async def test_metrics_delivered(self) -> None:
        """Тест метрики delivered."""
        bus = EnhancedEventBus(enable_persistence=False)

        bus.subscribe()
        bus.subscribe()

        event = Event.new("TEST", "SOURCE", {"data": 42})
        await bus.publish(event)

        assert bus.metrics["delivered"] == 2

    def test_get_metrics(self) -> None:
        """Тест get_metrics()."""
        bus = EnhancedEventBus(enable_persistence=False)

        metrics = bus.get_metrics()

        assert "bus_metrics" in metrics
        assert "queue_metrics" in metrics
        assert "rate_limiter_metrics" in metrics
        assert "subscriber_count" in metrics
        assert "rate_limit" in metrics


class TestRateLimit:
    """Тесты rate limit."""

    @pytest.mark.asyncio
    async def test_set_rate_limit(self) -> None:
        """Тест установки rate limit."""
        bus = EnhancedEventBus(enable_persistence=False, rate_limit=100)

        bus.set_rate_limit(50)

        assert bus.rate_limit == 50
        assert bus.rate_limiter.global_limit == 50


class TestShutdown:
    """Тесты shutdown."""

    @pytest.mark.asyncio
    async def test_start_and_shutdown(self) -> None:
        """Тест start и shutdown."""
        bus = EnhancedEventBus(enable_persistence=False)

        await bus.start()
        await bus.shutdown()

        # После shutdown очередь должна быть пустой
        assert bus.priority_queue.total_size() == 0


# Mark all tests as unit tests
pytest.mark.unit(__name__)

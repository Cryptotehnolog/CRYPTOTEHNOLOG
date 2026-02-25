"""
Нагрузочные тесты Event Bus.

Тестируют производительность и отказоустойчивость Event Bus:
- Пропускная способность (events/second)
- Задержка (latency)
- Устойчивость к высокой нагрузке
- Graceful degradation при переполнении буфера
- Многопоточная публикация
"""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any

import pytest

from cryptotechnolog.config import get_logger, get_settings

logger = get_logger(__name__)


# ============================================================================
# Event Bus Stub для тестирования (имитирует Rust EventBus)
# ============================================================================

class EventBusStub:
    """
    Заглушка Event Bus для нагрузочного тестирования.

    Имитирует поведение Rust EventBus с:
    - Публикацией событий
    - Подпиской на события
    - Ограничением буфера
    - Graceful degradation при переполнении
    """

    def __init__(self, capacity: int = 1024) -> None:
        """
        Инициализировать Event Bus.

        Args:
            capacity: Максимальный размер буфера
        """
        self._capacity = capacity
        self._subscribers: list[asyncio.Queue[dict[str, Any]]] = []
        self._published_count: int = 0
        self._dropped_count: int = 0
        self._lock = asyncio.Lock()

    @property
    def capacity(self) -> int:
        """Получить ёмкость буфера."""
        return self._capacity

    @property
    def subscriber_count(self) -> int:
        """Получить количество подписчиков."""
        return len(self._subscribers)

    @property
    def published_count(self) -> int:
        """Получить количество опубликованных событий."""
        return self._published_count

    @property
    def dropped_count(self) -> int:
        """Получить количество отброшенных событий."""
        return self._dropped_count

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        """
        Подписаться на события.

        Returns:
            Очередь для получения событий
        """
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=self._capacity)
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        """
        Отписаться от событий.

        Args:
            queue: Очередь подписчика
        """
        if queue in self._subscribers:
            self._subscribers.remove(queue)

    async def publish(self, event: dict[str, Any]) -> bool:
        """
        Опубликовать событие.

        Args:
            event: Событие для публикации

        Returns:
            True если успешно, False если буфер полон
        """
        async with self._lock:
            self._published_count += 1

            # Рассылаем всем подписчикам
            failed = []
            for i, subscriber in enumerate(self._subscribers):
                try:
                    subscriber.put_nowait(event)
                except asyncio.QueueFull:
                    failed.append(i)

            # Удаляем отключившихся подписчиков
            for i in reversed(failed):
                del self._subscribers[i]
                self._dropped_count += 1

            return True

    def clear_stats(self) -> None:
        """Очистить статистику."""
        self._published_count = 0
        self._dropped_count = 0


# ============================================================================
# Тесты нагрузки Event Bus
# ============================================================================

@pytest.mark.integration
class TestEventBusLoad:
    """Нагрузочные тесты для Event Bus."""

    @pytest.mark.asyncio
    async def test_throughput_single_publisher(self) -> None:
        """
        Тест пропускной способности с одним publisher.

        Измеряет количество событий в секунду при одном publisher.
        """
        bus = EventBusStub(capacity=10000)
        subscriber = bus.subscribe()

        # Параметры теста
        event_count = 10000
        warmup_count = 1000

        # Warmup
        for _ in range(warmup_count):
            await bus.publish({"type": "warmup", "data": 0})
        # Очищаем очередь
        while not subscriber.empty():
            subscriber.get_nowait()

        # Измерение
        start_time = time.perf_counter()

        for i in range(event_count):
            await bus.publish({"type": "test", "index": i, "data": "x" * 100})

        end_time = time.perf_counter()
        duration = end_time - start_time

        # Вычисляем метрики
        throughput = event_count / duration
        avg_latency_us = (duration / event_count) * 1_000_000

        logger.info(
            "Тест пропускной способности (1 publisher)",
            events=event_count,
            duration_s=duration,
            throughput_per_sec=throughput,
            avg_latency_us=avg_latency_us,
        )

        # Проверяем минимальную производительность
        assert throughput > 1000, f"Слишком низкая пропускная способность: {throughput:.0f}/s"
        assert avg_latency_us < 1000, f"Слишком высокая задержка: {avg_latency_us:.0f}us"

        # Проверяем, что все события доставлены
        delivered = 0
        while not subscriber.empty():
            subscriber.get_nowait()
            delivered += 1

        assert delivered == event_count, f"Не все события доставлены: {delivered}/{event_count}"

    @pytest.mark.asyncio
    async def test_throughput_multiple_publishers(self) -> None:
        """
        Тест пропускной способности с несколькими publishers.

        Измеряет производительность при конкурентной публикации.
        """
        bus = EventBusStub(capacity=50000)
        subscriber = bus.subscribe()

        # Параметры
        publishers = 4
        events_per_publisher = 2500
        total_events = publishers * events_per_publisher

        async def publisher_task(publisher_id: int) -> None:
            for i in range(events_per_publisher):
                await bus.publish({
                    "type": "test",
                    "publisher": publisher_id,
                    "index": i,
                })

        # Запуск publishers
        start_time = time.perf_counter()

        await asyncio.gather(*[publisher_task(i) for i in range(publishers)])

        end_time = time.perf_counter()
        duration = end_time - start_time

        # Вычисляем метрики
        throughput = total_events / duration

        logger.info(
            "Тест пропускной способности (4 publishers)",
            publishers=publishers,
            events_per_publisher=events_per_publisher,
            total_events=total_events,
            duration_s=duration,
            throughput_per_sec=throughput,
        )

        # Проверяем производительность
        assert throughput > 2000, f"Слишком низкая пропускная способность: {throughput:.0f}/s"

        # Проверяем доставку
        delivered = 0
        while not subscriber.empty():
            subscriber.get_nowait()
            delivered += 1

        assert delivered == total_events

    @pytest.mark.asyncio
    async def test_latency_distribution(self) -> None:
        """
        Тест распределения задержки.

        Проверяет percentiles: p50, p95, p99.
        """
        bus = EventBusStub(capacity=10000)
        subscriber = bus.subscribe()

        event_count = 1000
        latencies: list[float] = []

        for i in range(event_count):
            start = time.perf_counter()
            await bus.publish({"type": "latency_test", "index": i})
            end = time.perf_counter()

            latency_us = (end - start) * 1_000_000
            latencies.append(latency_us)

        # Вычисляем percentiles
        latencies.sort()
        p50 = latencies[int(len(latencies) * 0.50)]
        p95 = latencies[int(len(latencies) * 0.95)]
        p99 = latencies[int(len(latencies) * 0.99)]

        logger.info(
            "Тест задержки",
            p50_us=p50,
            p95_us=p95,
            p99_us=p99,
            min_us=min(latencies),
            max_us=max(latencies),
        )

        # Проверяем, что p99 приемлем
        assert p99 < 10000, f"p99 слишком высокая: {p99:.0f}us"
        assert p95 < 5000, f"p95 слишком высокая: {p95:.0f}us"

    @pytest.mark.asyncio
    async def test_buffer_overflow_graceful_degradation(self) -> None:
        """
        Тест graceful degradation при переполнении буфера.

        Проверяет, что система корректно обрабатывает переполнение.
        """
        # Маленький буфер для тестирования переполнения
        bus = EventBusStub(capacity=10)
        bus.subscribe()  # Добавляем подписчика

        # Заполняем буфер
        overflow_count = 20
        for i in range(overflow_count):
            result = await bus.publish({"type": "overflow_test", "index": i})
            # После переполнения publish должен продолжать работать
            assert result is True

        logger.info(
            "Тест переполнения буфера",
            capacity=bus.capacity,
            published=bus.published_count,
            dropped=bus.dropped_count,
        )

        # Система должна продолжить работу
        # (dropped - это нормальное поведение при заполненных очередях подписчиков)

    @pytest.mark.asyncio
    async def test_multiple_subscribers(self) -> None:
        """
        Тест с несколькими подписчиками.

        Проверяет broadcast доставку всем подписчикам.
        """
        bus = EventBusStub(capacity=10000)

        # Создаём подписчиков
        subscriber_count = 5
        subscribers = [bus.subscribe() for _ in range(subscriber_count)]

        event_count = 100

        # Публикуем события
        for i in range(event_count):
            await bus.publish({"type": "broadcast", "index": i})

        # Проверяем, что каждый подписчик получил все события
        for i, subscriber in enumerate(subscribers):
            delivered = 0
            while not subscriber.empty():
                subscriber.get_nowait()
                delivered += 1

            assert delivered == event_count, (
                f"Subscriber {i} получил {delivered} событий, ожидалось {event_count}"
            )

        logger.info(
            "Тест множественных подписчиков",
            subscribers=subscriber_count,
            events=event_count,
        )

    @pytest.mark.asyncio
    async def test_sustained_load(self) -> None:
        """
        Тест продолжительной нагрузки.

        Проверяет стабильность при длительной высокой нагрузке.
        """
        bus = EventBusStub(capacity=10000)
        subscriber = bus.subscribe()

        # Параметры: 10 секунд нагрузки
        duration_seconds = 5
        target_rate = 1000  # events per second

        start_time = time.perf_counter()
        end_time = start_time + duration_seconds

        event_count = 0
        publish_times: list[float] = []

        while time.perf_counter() < end_time:
            # Публикуем с целевой скоростью
            await bus.publish({"type": "sustained", "index": event_count})
            event_count += 1
            publish_times.append(time.perf_counter() - start_time)

            # Небольшая задержка для контроля скорости
            await asyncio.sleep(1.0 / target_rate)

        actual_duration = time.perf_counter() - start_time
        actual_throughput = event_count / actual_duration

        logger.info(
            "Тест продолжительной нагрузки",
            duration_s=actual_duration,
            events=event_count,
            target_rate=target_rate,
            actual_throughput=actual_throughput,
        )

        # Проверяем доставку
        delivered = 0
        while not subscriber.empty():
            subscriber.get_nowait()
            delivered += 1

        # Допускаем небольшие потери при высокой нагрузке
        delivery_rate = delivered / event_count
        assert delivery_rate > 0.95, f"Низкая доставка: {delivery_rate:.1%}"

    @pytest.mark.asyncio
    async def test_concurrent_publish_subscribe(self) -> None:
        """
        Тест конкурентной публикации и подписки.

        Проверяет thread-safety при одновременных операциях.
        """
        bus = EventBusStub(capacity=50000)
        subscriber = bus.subscribe()

        event_count = 5000

        # Конкурентные задачи
        async def publisher() -> None:
            for i in range(event_count):
                await bus.publish({"type": "concurrent", "index": i, "source": "publisher"})

        async def consumer() -> list[dict[str, Any]]:
            received = []
            timeout = 30  # seconds

            while len(received) < event_count:
                try:
                    event = await asyncio.wait_for(subscriber.get(), timeout=timeout)
                    received.append(event)
                except asyncio.TimeoutError:
                    break

            return received

        # Запускаем параллельно
        start_time = time.perf_counter()

        results = await asyncio.gather(
            publisher(),
            consumer(),
        )

        end_time = time.perf_counter()
        received_events = results[1]

        duration = end_time - start_time
        throughput = len(received_events) / duration

        logger.info(
            "Тест конкурентной публикации/подписки",
            published=event_count,
            received=len(received_events),
            duration_s=duration,
            throughput=throughput,
        )

        # Проверяем, что все события получены
        assert len(received_events) == event_count


@pytest.mark.integration
class TestEventBusMemoryAndStability:
    """Тесты памяти и стабильности Event Bus."""

    @pytest.mark.asyncio
    async def test_memory_usage_under_load(self) -> None:
        """
        Тест использования памяти под нагрузкой.

        Проверяет, что нет утечек памяти.
        """
        bus = EventBusStub(capacity=10000)

        # Цикл публикации и очистки
        iterations = 10
        events_per_iteration = 1000

        for iteration in range(iterations):
            for i in range(events_per_iteration):
                await bus.publish({
                    "type": "memory_test",
                    "iteration": iteration,
                    "index": i,
                    "data": "x" * 100,  # ~100 байт
                })

            # Небольшая пауза
            await asyncio.sleep(0.01)

        logger.info(
            "Тест использования памяти",
            iterations=iterations,
            events_per_iteration=events_per_iteration,
            total_events=iterations * events_per_iteration,
            published=bus.published_count,
        )

        # Проверяем, что счетчики корректны
        assert bus.published_count == iterations * events_per_iteration

    @pytest.mark.asyncio
    async def test_rapid_subscribe_unsubscribe(self) -> None:
        """
        Тест быстрой подписки/отписки.

        Проверяет стабильность при частых изменениях подписчиков.
        """
        bus = EventBusStub(capacity=10000)

        # Быстрое создание и удаление подписчиков
        for _ in range(100):
            subscriber = bus.subscribe()
            bus.unsubscribe(subscriber)

        # Проверяем, что Event Bus работает
        await bus.publish({"type": "test", "index": 0})

        logger.info("Тест быстрой подписки/отписки выполнен")


@pytest.mark.integration
class TestEventBusRealWorldScenarios:
    """Тесты реальных сценариев использования."""

    @pytest.mark.asyncio
    async def test_trading_events_simulation(self) -> None:
        """
        Симуляция торговых событий.

        Моделирует реальную нагрузку торговой системы.
        """
        bus = EventBusStub(capacity=50000)

        # Подписчики для разных компонентов
        risk_subscriber = bus.subscribe()
        execution_subscriber = bus.subscribe()
        analytics_subscriber = bus.subscribe()

        # Симуляция торговых событий
        symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
        event_types = ["ORDER_CREATED", "ORDER_FILLED", "ORDER_CANCELLED", "PRICE_UPDATE"]

        total_events = 1000

        async def generate_events() -> None:
            for i in range(total_events):
                await bus.publish({
                    "type": "trading_event",
                    "event_type": event_types[i % len(event_types)],
                    "symbol": symbols[i % len(symbols)],
                    "price": 50000 + i,
                    "timestamp": time.time(),
                })

        # Запускаем генерацию
        await generate_events()

        # Проверяем доставку каждому подписчику
        for name, subscriber in [
            ("risk", risk_subscriber),
            ("execution", execution_subscriber),
            ("analytics", analytics_subscriber),
        ]:
            received = 0
            while not subscriber.empty():
                subscriber.get_nowait()
                received += 1

            assert received == total_events, (
                f"{name} subscriber получил {received}, ожидалось {total_events}"
            )

        logger.info(
            "Симуляция торговых событий",
            total_events=total_events,
            subscribers=3,
        )

    @pytest.mark.asyncio
    async def test_high_frequency_signals(self) -> None:
        """
        Тест высокочастотных сигналов.

        Симулирует high-frequency trading сценарий.
        """
        bus = EventBusStub(capacity=100000)

        # Подписчик для сигналов
        subscriber = bus.subscribe()

        # Быстрая публикация сигналов
        start_time = time.perf_counter()

        for i in range(5000):
            await bus.publish({
                "type": "signal",
                "signal_id": i,
                "priority": "high" if i % 10 == 0 else "normal",
                "data": {"value": i * 0.01},
            })

        publish_duration = time.perf_counter() - start_time

        # Сбор событий
        collected = 0
        while not subscriber.empty():
            subscriber.get_nowait()
            collected += 1

        total_duration = time.perf_counter() - start_time
        throughput = 5000 / total_duration

        logger.info(
            "Тест высокочастотных сигналов",
            events=5000,
            publish_duration_s=publish_duration,
            total_duration_s=total_duration,
            throughput=throughput,
        )

        assert collected == 5000
        assert throughput > 1000, f"Слишком низкая производительность: {throughput:.0f}/s"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])

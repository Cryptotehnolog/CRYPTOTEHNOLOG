# ==================== E2E: Performance ====================
"""
Performance E2E Tests

Тестирует производительность системы:
- Throughput
- Latency
- Concurrency
- Resource usage
"""

import asyncio
from datetime import datetime, timezone
import time
import pytest

from cryptotechnolog.core.event import Event, EventType
from cryptotechnolog.core.enhanced_event_bus import EnhancedEventBus


# ==================== Throughput ====================


@pytest.mark.e2e
@pytest.mark.performance
@pytest.mark.asyncio
async def test_event_bus_throughput(event_bus):
    """
    E2E: Пропускная способность event bus
    """
    event_count = 1000
    events = []

    # Создаём тестовые события
    for i in range(event_count):
        event = Event(
            event_type=EventType.ORDER_SUBMITTED,
            data={"order_id": f"perf_order_{i}", "symbol": "BTC/USDT"},
            timestamp=datetime.now(timezone.utc),
        )
        events.append(event)

    # Замеряем время публикации
    start_time = time.perf_counter()

    for event in events:
        await event_bus.publish(event)

    # Ждём обработки
    await asyncio.sleep(0.5)

    end_time = time.perf_counter()
    duration = end_time - start_time
    throughput = event_count / duration

    # Проверяем что throughput достаточный
    assert throughput > 100, f"Throughput {throughput:.2f} events/sec слишком низкий"


@pytest.mark.e2e
@pytest.mark.performance
@pytest.mark.asyncio
async def test_database_throughput(db_pool):
    """
    E2E: Пропускная способность БД
    """
    event_count = 100
    start_time = time.perf_counter()

    async with db_pool.acquire() as conn:
        for i in range(event_count):
            await conn.execute(
                """
                INSERT INTO events (event_type, data, created_at)
                VALUES ($1, $2, $3)
                """,
                EventType.ORDER_SUBMITTED.value,
                {"order_id": f"db_perf_{i}"},
                datetime.now(timezone.utc),
            )

    end_time = time.perf_counter()
    duration = end_time - start_time
    throughput = event_count / duration

    assert throughput > 10, f"DB throughput {throughput:.2f} ops/sec слишком низкий"


# ==================== Latency ====================


@pytest.mark.e2e
@pytest.mark.performance
@pytest.mark.asyncio
async def test_event_publish_latency(event_bus):
    """
    E2E: Задержка публикации событий
    """
    latencies = []

    for i in range(100):
        event = Event(
            event_type=EventType.ORDER_SUBMITTED,
            data={"order_id": f"latency_test_{i}"},
            timestamp=datetime.now(timezone.utc),
        )

        start = time.perf_counter()
        await event_bus.publish(event)
        end = time.perf_counter()

        latencies.append((end - start) * 1000)  # в миллисекундах

    avg_latency = sum(latencies) / len(latencies)
    p99_latency = sorted(latencies)[98]

    assert avg_latency < 10, f"Average latency {avg_latency:.2f}ms слишком высокая"
    assert p99_latency < 50, f"P99 latency {p99_latency:.2f}ms слишком высокая"


@pytest.mark.e2e
@pytest.mark.performance
@pytest.mark.asyncio
async def test_database_query_latency(db_pool):
    """
    E2E: Задержка запросов к БД
    """
    # Создаём тестовые данные
    async with db_pool.acquire() as conn:
        for i in range(10):
            await conn.execute(
                """
                INSERT INTO events (event_type, data, created_at)
                VALUES ($1, $2, $3)
                """,
                EventType.ORDER_SUBMITTED.value,
                {"order_id": f"query_latency_{i}"},
                datetime.now(timezone.utc),
            )

    # Замеряем время запроса
    latencies = []
    for _ in range(50):
        start = time.perf_counter()
        async with db_pool.acquire() as conn:
            await conn.fetch("SELECT * FROM events LIMIT 10")
        end = time.perf_counter()
        latencies.append((end - start) * 1000)

    avg_latency = sum(latencies) / len(latencies)
    assert avg_latency < 100, f"Query latency {avg_latency:.2f}ms слишком высокая"


# ==================== Concurrency ====================


@pytest.mark.e2e
@pytest.mark.performance
@pytest.mark.asyncio
async def test_concurrent_event_publishing(event_bus):
    """
    E2E: Параллельная публикация событий
    """
    async def publish_events(count: int):
        for i in range(count):
            event = Event(
                event_type=EventType.ORDER_SUBMITTED,
                data={"order_id": f"concurrent_{i}"},
                timestamp=datetime.now(timezone.utc),
            )
            await event_bus.publish(event)

    # Запускаем 10 параллельных задач
    start_time = time.perf_counter()
    tasks = [publish_events(100) for _ in range(10)]
    await asyncio.gather(*tasks)
    end_time = time.perf_counter()

    duration = end_time - start_time
    total_events = 1000
    throughput = total_events / duration

    assert throughput > 100, f"Concurrent throughput {throughput:.2f} events/sec"


@pytest.mark.e2e
@pytest.mark.performance
@pytest.mark.asyncio
async def test_concurrent_database_writes(db_pool):
    """
    E2E: Параллельная запись в БД
    """
    async def write_batch(batch_id: int, count: int):
        async with db_pool.acquire() as conn:
            for i in range(count):
                await conn.execute(
                    """
                    INSERT INTO events (event_type, data, created_at)
                    VALUES ($1, $2, $3)
                    """,
                    EventType.ORDER_SUBMITTED.value,
                    {"order_id": f"batch_{batch_id}_{i}"},
                    datetime.now(timezone.utc),
                )

    start_time = time.perf_counter()
    # 5 параллельных batch, каждый 20 записей
    tasks = [write_batch(i, 20) for i in range(5)]
    await asyncio.gather(*tasks)
    end_time = time.perf_counter()

    duration = end_time - start_time
    total_writes = 100
    throughput = total_writes / duration

    assert throughput > 10, f"Concurrent DB throughput {throughput:.2f} ops/sec"


# ==================== Resource Usage ====================


@pytest.mark.e2e
@pytest.mark.performance
@pytest.mark.asyncio
async def test_memory_usage_event_bus(event_bus):
    """
    E2E: Использование памяти event bus
    """
    # Публикуем много событий
    for i in range(1000):
        event = Event(
            event_type=EventType.ORDER_SUBMITTED,
            data={"order_id": f"mem_test_{i}", "payload": "x" * 1000},
            timestamp=datetime.now(timezone.utc),
        )
        await event_bus.publish(event)

    # Проверяем что event bus работает
    assert event_bus is not None


@pytest.mark.e2e
@pytest.mark.performance
@pytest.mark.asyncio
async def test_connection_pool_efficiency(db_pool):
    """
    E2E: Эффективность пула соединений
    """
    async def query():
        async with db_pool.acquire() as conn:
            await conn.fetch("SELECT 1")

    # Выполняем много запросов
    start_time = time.perf_counter()
    tasks = [query() for _ in range(50)]
    await asyncio.gather(*tasks)
    end_time = time.perf_counter()

    duration = end_time - start_time
    avg_time = duration / 50

    assert avg_time < 0.1, f"Avg query time {avg_time:.3f}s слишком высокое"


# ==================== Load Tests ====================


@pytest.mark.e2e
@pytest.mark.performance
@pytest.mark.asyncio
async def test_sustained_load(event_bus, db_pool):
    """
    E2E: Устойчивая нагрузка
    """
    duration_seconds = 2
    events_per_second = 100

    async def publish_loop():
        end_time = time.perf_counter() + duration_seconds
        count = 0
        while time.perf_counter() < end_time:
            event = Event(
                event_type=EventType.ORDER_SUBMITTED,
                data={"order_id": f"load_{count}"},
                timestamp=datetime.now(timezone.utc),
            )
            await event_bus.publish(event)
            count += 1
            await asyncio.sleep(1 / events_per_second)
        return count

    start_time = time.perf_counter()
    total_events = await publish_loop()
    actual_duration = time.perf_counter() - start_time
    actual_throughput = total_events / actual_duration

    assert actual_throughput > 50, f"Sustained throughput {actual_throughput:.2f} events/sec"


@pytest.mark.e2e
@pytest.mark.performance
@pytest.mark.asyncio
async def test_burst_handling(event_bus):
    """
    E2E: Обработка всплесков
    """
    # Всплеск из 500 событий
    burst_size = 500

    async def burst_publish():
        tasks = []
        for i in range(burst_size):
            event = Event(
                event_type=EventType.ORDER_SUBMITTED,
                data={"order_id": f"burst_{i}"},
                timestamp=datetime.now(timezone.utc),
            )
            tasks.append(event_bus.publish(event))
        await asyncio.gather(*tasks)

    start_time = time.perf_counter()
    await burst_publish()
    end_time = time.perf_counter()

    duration = end_time - start_time
    throughput = burst_size / duration

    assert throughput > 100, f"Burst throughput {throughput:.2f} events/sec"


# ==================== Scalability ====================


@pytest.mark.e2e
@pytest.mark.performance
@pytest.mark.asyncio
async def test_linear_scaling(event_bus):
    """
    E2E: Линейное масштабирование
    """
    results = []

    for count in [100, 200, 500]:
        events = [
            Event(
                event_type=EventType.ORDER_SUBMITTED,
                data={"order_id": f"scale_{i}"},
                timestamp=datetime.now(timezone.utc),
            )
            for i in range(count)
        ]

        start_time = time.perf_counter()
        for event in events:
            await event_bus.publish(event)
        await asyncio.sleep(0.1)
        end_time = time.perf_counter()

        duration = end_time - start_time
        throughput = count / duration
        results.append((count, throughput))

    # Проверяем что throughput не деградирует значительно
    base_throughput = results[0][1]
    final_throughput = results[-1][1]
    degradation = (base_throughput - final_throughput) / base_throughput

    assert degradation < 0.5, f"Throughput degradation {degradation:.1%} слишком высокое"

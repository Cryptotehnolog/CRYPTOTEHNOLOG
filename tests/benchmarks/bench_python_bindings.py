"""
Python бенчмарки для CRYPTOTEHNOLOG.

Бенчмарки для оценки производительности:
- Python компонентов (stubs)
- Event Bus
- Database operations
- Redis operations
- Risk calculations

Запуск:
    python -m pytest tests/benchmarks/bench_python_bindings.py -v --benchmark-only
    python -m pytest tests/benchmarks/bench_python_bindings.py -v --benchmark-autosave
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import TYPE_CHECKING, Any
import uuid

import pytest

from cryptotechnolog.core.enhanced_event_bus import (
    EnhancedEventBus,
    PriorityQueue,
    RateLimiter,
)
from cryptotechnolog.core.event import Event, Priority
from cryptotechnolog.core.health import (
    ComponentHealth,
    DatabaseHealthCheck,
    HealthChecker,
    HealthStatus,
)
from cryptotechnolog.core.metrics import MetricsCollector
from cryptotechnolog.core.stubs import (
    ExecutionLayerStub,
    Order,
    PortfolioGovernorStub,
    RiskEngineStub,
    StateMachineStub,
    Strategy,
    StrategyManagerStub,
    get_stub_components,
)

if TYPE_CHECKING:
    from collections.abc import Callable

# ============================================================================
# Утилиты для бенчмарков
# ============================================================================


def benchmark(
    name: str,
    iterations: int = 10000,
) -> Callable:
    """
    Декоратор для создания бенчмарка.

    Args:
        name: Название бенчмарка
        iterations: Количество итераций

    Returns:
        Декоратор для тестовой функции
    """

    def decorator(func: Callable) -> Callable:
        async def wrapper() -> dict[str, Any]:
            # Warmup
            for _ in range(100):
                await func()

            # Benchmark
            start = time.perf_counter()
            for _ in range(iterations):
                await func()
            end = time.perf_counter()

            duration = end - start
            ops_per_sec = iterations / duration
            ns_per_op = (duration / iterations) * 1_000_000_000

            return {
                "name": name,
                "iterations": iterations,
                "duration_s": duration,
                "ops_per_sec": ops_per_sec,
                "ns_per_op": ns_per_op,
            }

        return wrapper

    return decorator


def sync_benchmark(
    name: str,
    iterations: int = 10000,
) -> Callable:
    """
    Декоратор для синхронного бенчмарка.

    Args:
        name: Название бенчмарка
        iterations: Количество итераций

    Returns:
        Декоратор для тестовой функции
    """

    def decorator(func: Callable) -> Callable:
        def wrapper() -> dict[str, Any]:
            # Warmup
            for _ in range(100):
                func()

            # Benchmark
            start = time.perf_counter()
            for _ in range(iterations):
                func()
            end = time.perf_counter()

            duration = end - start
            ops_per_sec = iterations / duration
            ns_per_op = (duration / iterations) * 1_000_000_000

            return {
                "name": name,
                "iterations": iterations,
                "duration_s": duration,
                "ops_per_sec": ops_per_sec,
                "ns_per_op": ns_per_op,
            }

        return wrapper

    return decorator


# ============================================================================
# Risk Engine Benchmarks
# ============================================================================


@pytest.mark.benchmark
class TestRiskEngineBenchmarks:
    """Бенчмарки RiskEngineStub."""

    @pytest.mark.asyncio
    async def test_check_trade_benchmark(self) -> None:
        """Бенчмарк проверки сделки."""
        engine = RiskEngineStub()
        iterations = 10000

        start = time.perf_counter()
        for _ in range(iterations):
            await engine.check_trade("BTC/USDT", 1000.0, "buy")
        end = time.perf_counter()

        duration = end - start
        ops_per_sec = iterations / duration
        ns_per_op = (duration / iterations) * 1_000_000_000

        print(f"\nRiskEngine.check_trade: {ops_per_sec:,.0f} ops/sec ({ns_per_op:,.0f} ns/op)")

    @pytest.mark.asyncio
    async def test_get_risk_limits_benchmark(self) -> None:
        """Бенчмарк получения лимитов риска."""
        engine = RiskEngineStub()
        iterations = 10000

        start = time.perf_counter()
        for _ in range(iterations):
            await engine.get_risk_limits()
        end = time.perf_counter()

        duration = end - start
        ops_per_sec = iterations / duration

        print(f"\nRiskEngine.get_risk_limits: {ops_per_sec:,.0f} ops/sec")


# ============================================================================
# Execution Layer Benchmarks
# ============================================================================


@pytest.mark.benchmark
class TestExecutionLayerBenchmarks:
    """Бенчмарки ExecutionLayerStub."""

    @pytest.mark.asyncio
    async def test_execute_order_benchmark(self) -> None:
        """Бенчмарк исполнения ордера."""
        executor = ExecutionLayerStub()
        order = Order(
            order_id="bench_001",
            symbol="BTC/USDT",
            side="buy",
            order_type="market",
            size=0.1,
        )
        iterations = 10000

        start = time.perf_counter()
        for _ in range(iterations):
            await executor.execute_order(order)
        end = time.perf_counter()

        duration = end - start
        ops_per_sec = iterations / duration

        print(f"\nExecutionLayer.execute_order: {ops_per_sec:,.0f} ops/sec")

    @pytest.mark.asyncio
    async def test_cancel_order_benchmark(self) -> None:
        """Бенчмарк отмены ордера."""
        executor = ExecutionLayerStub()
        iterations = 10000

        start = time.perf_counter()
        for _ in range(iterations):
            await executor.cancel_order("order_001", "BTC/USDT")
        end = time.perf_counter()

        duration = end - start
        ops_per_sec = iterations / duration

        print(f"\nExecutionLayer.cancel_order: {ops_per_sec:,.0f} ops/sec")


# ============================================================================
# Strategy Manager Benchmarks
# ============================================================================


@pytest.mark.benchmark
class TestStrategyManagerBenchmarks:
    """Бенчмарки StrategyManagerStub."""

    @pytest.mark.asyncio
    async def test_register_strategy_benchmark(self) -> None:
        """Бенчмарк регистрации стратегии."""
        manager = StrategyManagerStub()
        iterations = 10000

        start = time.perf_counter()
        for i in range(iterations):
            strategy = Strategy(name=f"strategy_{i}", enabled=False)
            await manager.register_strategy(strategy)
        end = time.perf_counter()

        duration = end - start
        ops_per_sec = iterations / duration

        print(f"\nStrategyManager.register_strategy: {ops_per_sec:,.0f} ops/sec")

    @pytest.mark.asyncio
    async def test_get_enabled_strategies_benchmark(self) -> None:
        """Бенчмарк получения включённых стратегий."""
        manager = StrategyManagerStub()

        # Регистрируем стратегии
        for i in range(100):
            strategy = Strategy(
                name=f"strategy_{i}",
                enabled=i % 2 == 0,
            )
            await manager.register_strategy(strategy)

        iterations = 10000

        start = time.perf_counter()
        for _ in range(iterations):
            await manager.get_enabled_strategies()
        end = time.perf_counter()

        duration = end - start
        ops_per_sec = iterations / duration

        print(f"\nStrategyManager.get_enabled_strategies: {ops_per_sec:,.0f} ops/sec")


# ============================================================================
# State Machine Benchmarks
# ============================================================================


@pytest.mark.benchmark
class TestStateMachineBenchmarks:
    """Бенчмарки StateMachineStub."""

    @pytest.mark.asyncio
    async def test_transition_benchmark(self) -> None:
        """Бенчмарк перехода состояния."""
        sm = StateMachineStub()
        iterations = 10000

        states = ["TRADING", "HALTED", "DEGRADED", "READY"]

        start = time.perf_counter()
        for idx, _ in enumerate(range(iterations)):
            await sm.transition(states[idx % len(states)], "benchmark")
        end = time.perf_counter()

        duration = end - start
        ops_per_sec = iterations / duration

        print(f"\nStateMachine.transition: {ops_per_sec:,.0f} ops/sec")


# ============================================================================
# Portfolio Governor Benchmarks
# ============================================================================


@pytest.mark.benchmark
class TestPortfolioGovernorBenchmarks:
    """Бенчмарки PortfolioGovernorStub."""

    @pytest.mark.asyncio
    async def test_open_position_benchmark(self) -> None:
        """Бенчмарк открытия позиции."""
        pg = PortfolioGovernorStub()
        iterations = 10000

        start = time.perf_counter()
        for i in range(iterations):
            await pg.open_position(f"SYM_{i}", 0.1, 50000.0)
        end = time.perf_counter()

        duration = end - start
        ops_per_sec = iterations / duration

        print(f"\nPortfolioGovernor.open_position: {ops_per_sec:,.0f} ops/sec")

    @pytest.mark.asyncio
    async def test_get_positions_benchmark(self) -> None:
        """Бенчмарк получения позиций."""
        pg = PortfolioGovernorStub()

        # Открываем позиции
        for i in range(50):
            await pg.open_position(f"SYM_{i}", 0.1, 50000.0)

        iterations = 10000

        start = time.perf_counter()
        for _ in range(iterations):
            await pg.get_positions()
        end = time.perf_counter()

        duration = end - start
        ops_per_sec = iterations / duration

        print(f"\nPortfolioGovernor.get_positions: {ops_per_sec:,.0f} ops/sec")


# ============================================================================
# Health Check Benchmarks
# ============================================================================


@pytest.mark.benchmark
class TestHealthCheckBenchmarks:
    """Бенчмарки Health Checker."""

    def test_component_health_creation(self) -> None:
        """Бенчмарк создания ComponentHealth."""
        iterations = 100000

        start = time.perf_counter()
        for _ in range(iterations):
            _ = ComponentHealth(
                component="test",
                status=HealthStatus.HEALTHY,
                message="OK",
            )
        end = time.perf_counter()

        duration = end - start
        ops_per_sec = iterations / duration

        print(f"\nComponentHealth creation: {ops_per_sec:,.0f} ops/sec")

    @pytest.mark.asyncio
    async def test_health_checker_check_system(self) -> None:
        """Бенчмарк проверки системы."""
        checker = HealthChecker()
        iterations = 1000

        # Регистрируем проверки
        for _i in range(5):

            class MockDB:
                async def health_check(self):
                    return {"status": "healthy", "connected": True}

            checker.register_check(DatabaseHealthCheck(MockDB()))

        start = time.perf_counter()
        for _ in range(iterations):
            await checker.check_system()
        end = time.perf_counter()

        duration = end - start
        ops_per_sec = iterations / duration

        print(f"\nHealthChecker.check_system: {ops_per_sec:,.0f} ops/sec")


# ============================================================================
# Metrics Benchmarks
# ============================================================================


@pytest.mark.benchmark
class TestMetricsBenchmarks:
    """Бенчмарки Metrics Collector."""

    def test_metrics_collector_counter(self) -> None:
        """Бенчмарк счётчика метрик."""
        collector = MetricsCollector()
        iterations = 100000

        start = time.perf_counter()
        for i in range(iterations):
            counter = collector.get_counter(f"counter_{i % 10}")
            counter.inc_sync()
        end = time.perf_counter()

        duration = end - start
        ops_per_sec = iterations / duration

        print(f"\nMetricsCollector.get_counter: {ops_per_sec:,.0f} ops/sec")

    def test_metrics_collector_gauge(self) -> None:
        """Бенчмарк gauge метрик."""
        collector = MetricsCollector()
        iterations = 100000

        start = time.perf_counter()
        for i in range(iterations):
            gauge = collector.get_gauge(f"gauge_{i % 10}")
            gauge.set_sync(float(i))
        end = time.perf_counter()

        duration = end - start
        ops_per_sec = iterations / duration

        print(f"\nMetricsCollector.get_gauge: {ops_per_sec:,.0f} ops/sec")


# ============================================================================
# Data Processing Benchmarks
# ============================================================================


@pytest.mark.benchmark
class TestDataProcessingBenchmarks:
    """Бенчмарки обработки данных."""

    def test_json_serialization(self) -> None:
        """Бенчмарк JSON сериализации."""
        data = {
            "symbol": "BTC/USDT",
            "price": 50000.0,
            "quantity": 0.1,
            "timestamp": 1234567890,
            "metadata": {"source": "test", "version": "1.0"},
        }
        iterations = 50000

        start = time.perf_counter()
        for _ in range(iterations):
            json.dumps(data)
        end = time.perf_counter()

        duration = end - start
        ops_per_sec = iterations / duration

        print(f"\nJSON serialization: {ops_per_sec:,.0f} ops/sec")

    def test_json_deserialization(self) -> None:
        """Бенчмарк JSON десериализации."""
        json_str = json.dumps(
            {
                "symbol": "BTC/USDT",
                "price": 50000.0,
                "quantity": 0.1,
                "timestamp": 1234567890,
            }
        )
        iterations = 50000

        start = time.perf_counter()
        for _ in range(iterations):
            json.loads(json_str)
        end = time.perf_counter()

        duration = end - start
        ops_per_sec = iterations / duration

        print(f"\nJSON deserialization: {ops_per_sec:,.0f} ops/sec")

    def test_uuid_generation(self) -> None:
        """Бенчмарк генерации UUID."""
        iterations = 100000

        start = time.perf_counter()
        for _ in range(iterations):
            _ = uuid.uuid4()
        end = time.perf_counter()

        duration = end - start
        ops_per_sec = iterations / duration

        print(f"\nUUID generation: {ops_per_sec:,.0f} ops/sec")


# ============================================================================
# Stubs Utilities Benchmarks
# ============================================================================


@pytest.mark.benchmark
class TestStubsUtilitiesBenchmarks:
    """Бенчмарки утилит для работы со stubs."""

    def test_create_stub(self) -> None:
        """Бенчмарк создания stub."""
        iterations = 50000

        start = time.perf_counter()
        for _ in range(iterations):
            _ = RiskEngineStub()
        end = time.perf_counter()

        duration = end - start
        ops_per_sec = iterations / duration

        print(f"\nRiskEngineStub creation: {ops_per_sec:,.0f} ops/sec")

    def test_get_stub_components(self) -> None:
        """Бенчмарк получения списка stubs."""
        iterations = 100000

        start = time.perf_counter()
        for _ in range(iterations):
            _ = get_stub_components()
        end = time.perf_counter()

        duration = end - start
        ops_per_sec = iterations / duration

        print(f"\nget_stub_components: {ops_per_sec:,.0f} ops/sec")


# ============================================================================
# Combined Scenarios Benchmarks
# ============================================================================


@pytest.mark.benchmark
class TestCombinedScenariosBenchmarks:
    """Бенчмарки комплексных сценариев."""

    @pytest.mark.asyncio
    async def test_trading_flow_simulation(self) -> None:
        """Бенчмарк симуляции торгового потока."""
        # Создаём компоненты
        risk_engine = RiskEngineStub()
        execution_layer = ExecutionLayerStub()
        strategy_manager = StrategyManagerStub()

        iterations = 1000

        async def trading_flow(i: int) -> None:
            # 1. Проверка риска
            await risk_engine.check_trade("BTC/USDT", 1000.0, "buy")

            # 2. Исполнение ордера
            order = Order(
                order_id=f"order_{i}",
                symbol="BTC/USDT",
                side="buy",
                order_type="market",
                size=0.1,
            )
            await execution_layer.execute_order(order)

            # 3. Проверка стратегий
            await strategy_manager.get_enabled_strategies()

        start = time.perf_counter()
        for i in range(iterations):
            await trading_flow(i)
        end = time.perf_counter()

        duration = end - start
        ops_per_sec = iterations / duration

        print(f"\nTrading flow simulation: {ops_per_sec:,.0f} flows/sec")

    @pytest.mark.asyncio
    async def test_concurrent_event_processing(self) -> None:
        """Бенчмарк конкурентной обработки событий."""
        risk_engine = RiskEngineStub()
        execution_layer = ExecutionLayerStub()

        iterations = 5000

        async def process_event(i: int) -> None:
            await risk_engine.check_trade("BTC/USDT", 1000.0, "buy")
            await execution_layer.execute_order(
                Order(
                    order_id=f"order_{i}",
                    symbol="BTC/USDT",
                    side="buy",
                    order_type="market",
                    size=0.1,
                )
            )

        start = time.perf_counter()
        await asyncio.gather(*[process_event(i) for i in range(iterations)])
        end = time.perf_counter()

        duration = end - start
        ops_per_sec = iterations / duration

        print(f"\nConcurrent event processing: {ops_per_sec:,.0f} events/sec")


# ============================================================================
# Enhanced Event Bus Benchmarks
# ============================================================================


@pytest.mark.benchmark
class TestEnhancedEventBusBenchmarks:
    """Бенчмарки EnhancedEventBus."""

    @pytest.mark.asyncio
    async def test_event_bus_creation(self) -> None:
        """Бенчмарк создания EnhancedEventBus."""
        iterations = 10000

        start = time.perf_counter()
        for _ in range(iterations):
            _ = EnhancedEventBus(enable_persistence=False)
        end = time.perf_counter()

        duration = end - start
        ops_per_sec = iterations / duration
        ns_per_op = (duration / iterations) * 1_000_000_000

        print(f"\nEnhancedEventBus creation: {ops_per_sec:,.0f} ops/sec ({ns_per_op:,.0f} ns/op)")

    @pytest.mark.asyncio
    async def test_event_creation(self) -> None:
        """Бенчмарк создания события."""
        iterations = 100000

        start = time.perf_counter()
        for i in range(iterations):
            _ = Event.new("TEST", "SOURCE", {"i": i})
        end = time.perf_counter()

        duration = end - start
        ops_per_sec = iterations / duration
        ns_per_op = (duration / iterations) * 1_000_000_000

        print(f"\nEvent.new: {ops_per_sec:,.0f} ops/sec ({ns_per_op:,.0f} ns/op)")

    @pytest.mark.asyncio
    async def test_event_publish_no_subscribers(self) -> None:
        """Бенчмарк публикации без подписчиков."""
        bus = EnhancedEventBus(
            enable_persistence=False,
            capacities={"critical": 100000, "high": 100000, "normal": 100000, "low": 100000},
        )
        iterations = 50000

        start = time.perf_counter()
        for i in range(iterations):
            event = Event.new("TEST", "SOURCE", {"i": i})
            await bus.publish(event)
        end = time.perf_counter()

        duration = end - start
        ops_per_sec = iterations / duration

        print(f"\nEvent publish (no subscribers): {ops_per_sec:,.0f} ops/sec")

    @pytest.mark.asyncio
    async def test_event_publish_with_subscriber(self) -> None:
        """Бенчмарк публикации с одним подписчиком."""
        bus = EnhancedEventBus(
            enable_persistence=False,
            capacities={"critical": 100000, "high": 100000, "normal": 100000, "low": 100000},
        )
        _ = bus.subscribe()
        iterations = 20000

        start = time.perf_counter()
        for i in range(iterations):
            event = Event.new("TEST", "SOURCE", {"i": i})
            await bus.publish(event)
        end = time.perf_counter()

        duration = end - start
        ops_per_sec = iterations / duration

        print(f"\nEvent publish (1 subscriber): {ops_per_sec:,.0f} ops/sec")

    @pytest.mark.asyncio
    async def test_event_publish_multiple_subscribers(self) -> None:
        """Бенчмарк публикации с несколькими подписчиками."""
        bus = EnhancedEventBus(
            enable_persistence=False,
            capacities={"critical": 100000, "high": 100000, "normal": 100000, "low": 100000},
        )
        for _ in range(4):
            bus.subscribe()
        iterations = 10000

        start = time.perf_counter()
        for i in range(iterations):
            event = Event.new("TEST", "SOURCE", {"i": i})
            await bus.publish(event)
        end = time.perf_counter()

        duration = end - start
        ops_per_sec = iterations / duration

        print(f"\nEvent publish (4 subscribers): {ops_per_sec:,.0f} ops/sec")

    @pytest.mark.asyncio
    async def test_priority_queue_push_pop(self) -> None:
        """Бенчмарк PriorityQueue push/pop."""
        pq = PriorityQueue()
        iterations = 50000

        # Подготовка событий
        events = [Event.new("TEST", "SOURCE", {"i": i}) for i in range(iterations)]

        start = time.perf_counter()
        for event in events:
            await pq.push(event)
        for _ in range(iterations):
            await pq.pop()
        end = time.perf_counter()

        duration = end - start
        ops_per_sec = iterations / duration

        print(f"\nPriorityQueue push+pop: {ops_per_sec:,.0f} ops/sec")

    @pytest.mark.asyncio
    async def test_rate_limiter_check(self) -> None:
        """Бенчмарк RateLimiter check."""
        limiter = RateLimiter(global_limit=100000)
        iterations = 100000

        start = time.perf_counter()
        for i in range(iterations):
            limiter.check(f"SOURCE_{i % 10}")
        end = time.perf_counter()

        duration = end - start
        ops_per_sec = iterations / duration
        ns_per_op = (duration / iterations) * 1_000_000_000

        print(f"\nRateLimiter.check: {ops_per_sec:,.0f} ops/sec ({ns_per_op:,.0f} ns/op)")

    @pytest.mark.asyncio
    async def test_concurrent_event_publishing(self) -> None:
        """Бенчмарк конкурентной публикации событий."""
        bus = EnhancedEventBus(enable_persistence=False)
        _ = bus.subscribe()
        iterations = 5000

        async def publish_events(start_idx: int) -> None:
            for i in range(start_idx, start_idx + iterations // 10):
                event = Event.new("TEST", "SOURCE", {"i": i})
                await bus.publish(event)

        start = time.perf_counter()
        await asyncio.gather(*[publish_events(i * 1000) for i in range(10)])
        end = time.perf_counter()

        duration = end - start
        ops_per_sec = (iterations * 10) / duration

        print(f"\nConcurrent event publishing: {ops_per_sec:,.0f} ops/sec")

    @pytest.mark.asyncio
    async def test_mixed_priority_events(self) -> None:
        """Бенчмарк событий с разными приоритетами."""
        bus = EnhancedEventBus(
            enable_persistence=False,
            capacities={"critical": 100000, "high": 100000, "normal": 100000, "low": 100000},
        )
        _ = bus.subscribe()
        iterations = 20000

        priorities = [Priority.CRITICAL, Priority.HIGH, Priority.NORMAL, Priority.LOW]

        start = time.perf_counter()
        for i in range(iterations):
            event = Event.new("TEST", "SOURCE", {"i": i})
            event.priority = priorities[i % len(priorities)]
            await bus.publish(event)
        end = time.perf_counter()

        duration = end - start
        ops_per_sec = iterations / duration

        print(f"\nMixed priority events: {ops_per_sec:,.0f} ops/sec")


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "benchmark"])

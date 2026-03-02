"""
Тесты для Health Check System (src/core/health.py).

Проверяют:
- ComponentHealth (состояние компонента)
- SystemHealth (общее состояние)
- DatabaseHealthCheck (проверка PostgreSQL)
- RedisHealthCheck (проверка Redis)
- EventBusHealthCheck (проверка Event Bus)
- MetricsHealthCheck (проверка метрик)
- HealthChecker (центральный компонент)
"""

import asyncio

import pytest

from cryptotechnolog.core.health import (
    ComponentHealth,
    DatabaseHealthCheck,
    EventBusHealthCheck,
    HealthChecker,
    HealthStatus,
    MetricsHealthCheck,
    RedisHealthCheck,
    SystemHealth,
    get_health_checker,
    init_health_checker,
)


class TestComponentHealth:
    """Тесты для ComponentHealth."""

    def test_init(self) -> None:
        """Инициализация состояния компонента."""
        health = ComponentHealth(
            component="test_component",
            status=HealthStatus.HEALTHY,
            message="Все работает",
        )

        assert health.component == "test_component"
        assert health.status == HealthStatus.HEALTHY
        assert health.message == "Все работает"
        assert health.timestamp > 0
        assert health.latency_ms == 0.0

    def test_is_healthy(self) -> None:
        """Проверка метода is_healthy()."""
        healthy = ComponentHealth(component="test", status=HealthStatus.HEALTHY)
        assert healthy.is_healthy()

        unhealthy = ComponentHealth(component="test", status=HealthStatus.UNHEALTHY)
        assert not unhealthy.is_healthy()

        degraded = ComponentHealth(component="test", status=HealthStatus.DEGRADED)
        assert not degraded.is_healthy()

    def test_to_dict(self) -> None:
        """Преобразование в словарь."""
        health = ComponentHealth(
            component="test",
            status=HealthStatus.HEALTHY,
            message="OK",
            details={"key": "value"},
            latency_ms=10.5,
        )

        result = health.to_dict()

        assert result["component"] == "test"
        assert result["status"] == "healthy"
        assert result["message"] == "OK"
        assert result["details"] == {"key": "value"}
        assert result["latency_ms"] == 10.5


class TestSystemHealth:
    """Тесты для SystemHealth."""

    def test_init(self) -> None:
        """Инициализация общего состояния."""
        components = {
            "postgresql": ComponentHealth(
                component="postgresql",
                status=HealthStatus.HEALTHY,
            ),
        }

        health = SystemHealth(
            overall_status=HealthStatus.HEALTHY,
            components=components,
        )

        assert health.overall_status == HealthStatus.HEALTHY
        assert len(health.components) == 1
        assert health.version == "1.1.0"

    def test_is_healthy(self) -> None:
        """Проверка метода is_healthy()."""
        healthy = SystemHealth(
            overall_status=HealthStatus.HEALTHY,
            components={},
        )
        assert healthy.is_healthy()

        unhealthy = SystemHealth(
            overall_status=HealthStatus.UNHEALTHY,
            components={},
        )
        assert not unhealthy.is_healthy()

    def test_get_unhealthy_components(self) -> None:
        """Получение списка нездоровых компонентов."""
        components = {
            "postgresql": ComponentHealth(
                component="postgresql",
                status=HealthStatus.HEALTHY,
            ),
            "redis": ComponentHealth(
                component="redis",
                status=HealthStatus.UNHEALTHY,
            ),
            "event_bus": ComponentHealth(
                component="event_bus",
                status=HealthStatus.DEGRADED,
            ),
        }

        health = SystemHealth(
            overall_status=HealthStatus.UNHEALTHY,
            components=components,
        )

        unhealthy = health.get_unhealthy_components()
        assert "redis" in unhealthy
        assert "event_bus" in unhealthy
        assert "postgresql" not in unhealthy

    def test_to_dict(self) -> None:
        """Преобразование в словарь."""
        health = SystemHealth(
            overall_status=HealthStatus.HEALTHY,
            components={
                "test": ComponentHealth(
                    component="test",
                    status=HealthStatus.HEALTHY,
                ),
            },
        )

        result = health.to_dict()

        assert result["overall_status"] == "healthy"
        assert "test" in result["components"]
        assert result["version"] == "1.1.0"


class TestDatabaseHealthCheck:
    """Тесты для DatabaseHealthCheck."""

    def test_init(self) -> None:
        """Инициализация проверки."""
        check = DatabaseHealthCheck()
        assert check.name == "postgresql"
        assert check.timeout == 5.0

    def test_init_with_timeout(self) -> None:
        """Инициализация с кастомным таймаутом."""
        check = DatabaseHealthCheck(timeout=10.0)
        assert check.timeout == 10.0

    def test_set_db_manager(self) -> None:
        """Установка менеджера БД."""
        check = DatabaseHealthCheck()

        class MockDBManager:
            async def health_check(self):
                return {"status": "healthy", "connected": True}

        mock_db = MockDBManager()
        check.set_db_manager(mock_db)
        assert check._db_manager is mock_db

    @pytest.mark.asyncio
    async def test_check_without_manager(self) -> None:
        """Проверка без менеджера БД."""
        check = DatabaseHealthCheck()
        result = await check.check()

        assert result.status == HealthStatus.UNKNOWN
        assert "не настроен" in result.message

    @pytest.mark.asyncio
    async def test_check_with_healthy_db(self) -> None:
        """Проверка со здоровым менеджером БД."""

        class MockDBManager:
            async def health_check(self):
                return {
                    "status": "healthy",
                    "connected": True,
                    "pool_size": 5,
                    "pool_max_size": 10,
                }

        check = DatabaseHealthCheck(MockDBManager())
        result = await check.check()

        assert result.status == HealthStatus.HEALTHY
        assert "активно" in result.message

    @pytest.mark.asyncio
    async def test_check_with_unhealthy_db(self) -> None:
        """Проверка с нездоровым менеджером БД."""

        class MockDBManager:
            async def health_check(self):
                return {
                    "status": "unhealthy",
                    "connected": False,
                    "error": "Connection refused",
                }

        check = DatabaseHealthCheck(MockDBManager())
        result = await check.check()

        assert result.status == HealthStatus.UNHEALTHY


class TestRedisHealthCheck:
    """Тесты для RedisHealthCheck."""

    def test_init(self) -> None:
        """Инициализация проверки."""
        check = RedisHealthCheck()
        assert check.name == "redis"

    def test_set_redis_manager(self) -> None:
        """Установка менеджера Redis."""
        check = RedisHealthCheck()

        class MockRedisManager:
            async def health_check(self):
                return {"status": "healthy", "connected": True}

        mock_redis = MockRedisManager()
        check.set_redis_manager(mock_redis)
        assert check._redis_manager is mock_redis

    @pytest.mark.asyncio
    async def test_check_without_manager(self) -> None:
        """Проверка без менеджера Redis."""
        check = RedisHealthCheck()
        result = await check.check()

        assert result.status == HealthStatus.UNKNOWN
        assert "не настроен" in result.message

    @pytest.mark.asyncio
    async def test_check_with_healthy_redis(self) -> None:
        """Проверка со здоровым менеджером Redis."""

        class MockRedisManager:
            async def health_check(self):
                return {
                    "status": "healthy",
                    "connected": True,
                    "max_connections": 50,
                }

        check = RedisHealthCheck(MockRedisManager())
        result = await check.check()

        assert result.status == HealthStatus.HEALTHY


class TestEventBusHealthCheck:
    """Тесты для EventBusHealthCheck."""

    def test_init(self) -> None:
        """Инициализация проверки."""
        check = EventBusHealthCheck()
        assert check.name == "event_bus"

    def test_set_event_bus(self) -> None:
        """Установка Event Bus."""
        check = EventBusHealthCheck()

        class MockEventBus:
            async def get_metrics(self):
                return {"published": 100}

        mock_bus = MockEventBus()
        check.set_event_bus(mock_bus)
        assert check._event_bus is mock_bus

    @pytest.mark.asyncio
    async def test_check_without_event_bus(self) -> None:
        """Проверка без Event Bus."""
        check = EventBusHealthCheck()
        result = await check.check()

        assert result.status == HealthStatus.UNKNOWN

    @pytest.mark.asyncio
    async def test_check_with_event_bus(self) -> None:
        """Проверка с Event Bus."""

        class MockEventBus:
            async def get_metrics(self):
                return {"published": 100}

        check = EventBusHealthCheck(MockEventBus())
        result = await check.check()

        assert result.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_check_with_publish_only(self) -> None:
        """Проверка с Event Bus без get_metrics."""

        class MockEventBus:
            async def publish(self, event):
                pass

        check = EventBusHealthCheck(MockEventBus())
        result = await check.check()

        assert result.status == HealthStatus.HEALTHY


class TestMetricsHealthCheck:
    """Тесты для MetricsHealthCheck."""

    def test_init(self) -> None:
        """Инициализация проверки."""
        check = MetricsHealthCheck()
        assert check.name == "metrics"

    def test_set_metrics_collector(self) -> None:
        """Установка коллектора метрик."""
        check = MetricsHealthCheck()

        class MockCollector:
            enabled = True

            def get_metric_names(self):
                return ["counter1", "gauge1"]

        mock_collector = MockCollector()
        check.set_metrics_collector(mock_collector)
        assert check._metrics_collector is mock_collector

    @pytest.mark.asyncio
    async def test_check_without_collector(self) -> None:
        """Проверка без коллектора метрик."""
        check = MetricsHealthCheck()
        result = await check.check()

        assert result.status == HealthStatus.UNKNOWN

    @pytest.mark.asyncio
    async def test_check_with_enabled_collector(self) -> None:
        """Проверка с включенным коллектором."""

        class MockCollector:
            enabled = True

            def get_metric_names(self):
                return ["counter1", "gauge1"]

        check = MetricsHealthCheck(MockCollector())
        result = await check.check()

        assert result.status == HealthStatus.HEALTHY
        assert "активна" in result.message

    @pytest.mark.asyncio
    async def test_check_with_disabled_collector(self) -> None:
        """Проверка с отключенным коллектором."""

        class MockCollector:
            enabled = False

            def get_metric_names(self):
                return []

        check = MetricsHealthCheck(MockCollector())
        result = await check.check()

        assert result.status == HealthStatus.DEGRADED


class TestHealthChecker:
    """Тесты для HealthChecker."""

    def test_init(self) -> None:
        """Инициализация проверяльщика."""
        checker = HealthChecker()
        assert len(checker.get_registered_checks()) == 0

    def test_register_check(self) -> None:
        """Регистрация проверки."""
        checker = HealthChecker()

        check = DatabaseHealthCheck()
        checker.register_check(check)

        assert "postgresql" in checker.get_registered_checks()

    def test_register_multiple_checks(self) -> None:
        """Регистрация нескольких проверок."""
        checker = HealthChecker()

        checker.register_check(DatabaseHealthCheck())
        checker.register_check(RedisHealthCheck())
        checker.register_check(EventBusHealthCheck())

        checks = checker.get_registered_checks()
        assert len(checks) == 3
        assert "postgresql" in checks
        assert "redis" in checks
        assert "event_bus" in checks

    def test_unregister_check(self) -> None:
        """Удаление проверки."""
        checker = HealthChecker()

        checker.register_check(DatabaseHealthCheck())
        assert "postgresql" in checker.get_registered_checks()

        result = checker.unregister_check("postgresql")
        assert result is True
        assert "postgresql" not in checker.get_registered_checks()

    def test_unregister_nonexistent(self) -> None:
        """Удаление несуществующей проверки."""
        checker = HealthChecker()

        result = checker.unregister_check("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_check_component_not_registered(self) -> None:
        """Проверка незарегистрированного компонента."""
        checker = HealthChecker()

        with pytest.raises(ValueError, match="не зарегистрирован"):
            await checker.check_component("nonexistent")

    @pytest.mark.asyncio
    async def test_check_system_empty(self) -> None:
        """Проверка системы без зарегистрированных компонентов."""
        checker = HealthChecker()

        result = await checker.check_system()

        assert result.overall_status == HealthStatus.UNKNOWN

    @pytest.mark.asyncio
    async def test_check_system_all_healthy(self) -> None:
        """Проверка системы когда все компоненты здоровы."""
        checker = HealthChecker()

        class HealthyDB:
            async def health_check(self):
                return {"status": "healthy", "connected": True}

        class HealthyRedis:
            async def health_check(self):
                return {"status": "healthy", "connected": True}

        checker.register_check(DatabaseHealthCheck(HealthyDB()))
        checker.register_check(RedisHealthCheck(HealthyRedis()))

        result = await checker.check_system()

        assert result.overall_status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_check_system_with_unhealthy(self) -> None:
        """Проверка системы с нездоровым компонентом."""

        class HealthyDB:
            async def health_check(self):
                return {"status": "healthy", "connected": True}

        class UnhealthyRedis:
            async def health_check(self):
                return {"status": "unhealthy", "error": "Connection failed"}

        checker = HealthChecker()
        checker.register_check(DatabaseHealthCheck(HealthyDB()))
        checker.register_check(RedisHealthCheck(UnhealthyRedis()))

        result = await checker.check_system()

        assert result.overall_status == HealthStatus.UNHEALTHY
        assert "redis" in result.get_unhealthy_components()

    @pytest.mark.asyncio
    async def test_check_system_with_degraded(self) -> None:
        """Проверка системы с деградировавшим компонентом."""

        class HealthyDB:
            async def health_check(self):
                return {"status": "healthy", "connected": True}

        class DegradedMetrics:
            def __init__(self):
                self.enabled = False

            def get_metric_names(self):
                return []

        checker = HealthChecker()
        checker.register_check(DatabaseHealthCheck(HealthyDB()))
        checker.register_check(MetricsHealthCheck(DegradedMetrics()))

        result = await checker.check_system()

        assert result.overall_status == HealthStatus.DEGRADED

    @pytest.mark.asyncio
    async def test_status_callback(self) -> None:
        """Тест callback при изменении статуса."""
        checker = HealthChecker()

        callback_called = []

        async def callback(health: SystemHealth) -> None:
            callback_called.append(health.overall_status)

        checker.on_status_change(callback)

        # Регистрируем здоровую проверку
        class HealthyDB:
            async def health_check(self):
                return {"status": "healthy", "connected": True}

        checker.register_check(DatabaseHealthCheck(HealthyDB()))

        # Первая проверка
        await checker.check_system()

        # Вторая проверка - статус не изменился
        await checker.check_system()

        # Callback должен быть вызван
        assert len(callback_called) >= 1

    @pytest.mark.asyncio
    async def test_get_last_health(self) -> None:
        """Получение последнего известного состояния."""
        checker = HealthChecker()

        class HealthyDB:
            async def health_check(self):
                return {"status": "healthy", "connected": True}

        checker.register_check(DatabaseHealthCheck(HealthyDB()))

        # До проверки
        assert checker.get_last_health() is None

        # После проверки
        await checker.check_system()
        last = checker.get_last_health()

        assert last is not None
        assert last.overall_status == HealthStatus.HEALTHY


class TestHealthCheckerGlobal:
    """Тесты для глобального экземпляра."""

    def test_get_health_checker_singleton(self) -> None:
        """Получение глобального экземпляра."""
        checker1 = get_health_checker()
        checker2 = get_health_checker()

        assert checker1 is checker2

    def test_init_health_checker(self) -> None:
        """Инициализация с компонентами."""

        class MockDB:
            pass

        class MockRedis:
            pass

        checker = init_health_checker(
            db_manager=MockDB(),
            redis_manager=MockRedis(),
        )

        assert "postgresql" in checker.get_registered_checks()
        assert "redis" in checker.get_registered_checks()


class TestHealthStatusEnum:
    """Тесты для enum HealthStatus."""

    def test_values(self) -> None:
        """Проверка значений enum."""
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"
        assert HealthStatus.DEGRADED.value == "degraded"
        assert HealthStatus.UNKNOWN.value == "unknown"


class TestHealthCheckerEdgeCases:
    """Тесты граничных случаев."""

    @pytest.mark.asyncio
    async def test_check_system_with_exception(self) -> None:
        """Проверка системы с исключением в проверке."""

        class FailingCheck:
            name = "failing"

            async def check(self):
                raise RuntimeError("Test error")

        checker = HealthChecker()
        checker.register_check(FailingCheck())

        result = await checker.check_system()

        # Система должна быть UNKNOWN из-за исключения
        assert result.overall_status == HealthStatus.UNKNOWN

    @pytest.mark.asyncio
    async def test_check_system_parallel(self) -> None:
        """Параллельные проверки."""

        class HealthyComponent:
            def __init__(self, name: str):
                self.name = name

            async def health_check(self):
                return {"status": "healthy", "connected": True}

        checker = HealthChecker()
        checker.register_check(DatabaseHealthCheck(HealthyComponent("db")))
        checker.register_check(RedisHealthCheck(HealthyComponent("redis")))

        # Выполняем несколько проверок параллельно
        results = await asyncio.gather(
            checker.check_system(),
            checker.check_system(),
            checker.check_system(),
        )

        # Все результаты должны быть здоровы
        for result in results:
            assert result.overall_status == HealthStatus.HEALTHY


pytest.mark.unit(__name__)

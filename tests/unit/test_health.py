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
from unittest.mock import AsyncMock, patch

import pytest

from cryptotechnolog.config import reload_settings, update_settings
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
from cryptotechnolog.runtime_identity import build_runtime_identity, get_release_identity


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
        assert health.version == get_release_identity().version

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
            readiness_status="ready",
            diagnostics={"runtime_started": True},
        )

        result = health.to_dict()

        assert result["overall_status"] == "healthy"
        assert "test" in result["components"]
        assert result["version"] == get_release_identity().version
        assert result["runtime_identity"]["version"] == get_release_identity().version
        assert result["readiness"]["status"] == "ready"
        assert result["diagnostics"]["runtime_started"] is True

    def test_to_dict_includes_runtime_config_truth(self) -> None:
        """runtime_identity должен сохранять config truth в operator-facing payload."""
        identity = build_runtime_identity(
            bootstrap_module="cryptotechnolog.bootstrap",
            bootstrap_mode="production",
            active_risk_path="phase5_risk_engine",
            config_identity="settings:test:d:\\CRYPTOTEHNOLOG\\config",
            config_revision="abc123",
        )
        health = SystemHealth(
            overall_status=HealthStatus.HEALTHY,
            components={},
            runtime_identity=identity,
            diagnostics={
                "config_identity": identity.config_identity,
                "config_revision": identity.config_revision,
            },
        )

        result = health.to_dict()

        assert result["runtime_identity"]["config_identity"] == identity.config_identity
        assert result["runtime_identity"]["config_revision"] == identity.config_revision
        assert result["diagnostics"]["config_identity"] == identity.config_identity
        assert result["diagnostics"]["config_revision"] == identity.config_revision


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
        assert checker.get_runtime_identity().version == get_release_identity().version

    def test_init_uses_health_policy_settings(self) -> None:
        """HealthChecker должен читать operational defaults из canonical settings."""
        try:
            update_settings({
                "health_check_timeout_seconds": 6.5,
                "health_background_check_interval_seconds": 45.0,
                "health_check_and_wait_timeout_seconds": 20.0,
            })
            checker = HealthChecker()
            check = DatabaseHealthCheck()
            assert checker._check_interval == 45.0
            assert checker._check_and_wait_timeout == 20.0
            assert check.timeout == 6.5
        finally:
            reload_settings()

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

    @pytest.mark.asyncio
    async def test_check_system_builds_ready_readiness_truth(self) -> None:
        """Readiness должен отражать фактическую готовность runtime."""

        class HealthyDB:
            async def health_check(self):
                return {"status": "healthy", "connected": True}

        identity = build_runtime_identity(
            bootstrap_module="cryptotechnolog.bootstrap",
            bootstrap_mode="production",
            active_risk_path="phase5_risk_engine",
        )
        checker = HealthChecker(runtime_identity=identity)
        checker.set_runtime_diagnostics(
            composition_root_built=True,
            runtime_started=True,
            runtime_ready=True,
            active_risk_path="phase5_risk_engine",
            config_identity="settings:test:d:\\CRYPTOTEHNOLOG\\config",
            config_revision="rev-123",
        )
        checker.register_check(DatabaseHealthCheck(HealthyDB()))

        result = await checker.check_system()

        assert result.readiness_status == "ready"
        assert result.readiness_reasons == []
        assert result.diagnostics["active_risk_path"] == "phase5_risk_engine"
        assert result.diagnostics["config_identity"] == "settings:test:d:\\CRYPTOTEHNOLOG\\config"
        assert result.diagnostics["config_revision"] == "rev-123"

    @pytest.mark.asyncio
    async def test_check_system_exposes_blocked_startup_reason(self) -> None:
        """Readiness должен показывать причину заблокированного startup."""
        identity = build_runtime_identity(
            bootstrap_module="cryptotechnolog.bootstrap",
            bootstrap_mode="production",
            active_risk_path="phase5_risk_engine",
        )
        checker = HealthChecker(runtime_identity=identity)
        checker.set_runtime_diagnostics(
            composition_root_built=True,
            runtime_started=False,
            runtime_ready=False,
            active_risk_path="phase5_risk_engine",
            failure_reason="Production bootstrap не поднял подключение к БД",
        )

        result = await checker.check_system()

        assert result.readiness_status == "not_ready"
        assert "runtime_not_started" in result.readiness_reasons
        assert any(
            reason.startswith("startup_failed:Production bootstrap не поднял подключение к БД")
            for reason in result.readiness_reasons
        )

    @pytest.mark.asyncio
    async def test_check_system_exposes_market_data_runtime_readiness_truth(self) -> None:
        """Readiness должен учитывать nested diagnostics Market Data runtime."""
        identity = build_runtime_identity(
            bootstrap_module="cryptotechnolog.bootstrap",
            bootstrap_mode="production",
            active_risk_path="phase5_risk_engine",
        )
        checker = HealthChecker(runtime_identity=identity)
        checker.set_runtime_diagnostics(
            composition_root_built=True,
            runtime_started=True,
            runtime_ready=False,
            active_risk_path="phase5_risk_engine",
            market_data_runtime={
                "started": True,
                "ready": False,
                "lifecycle_state": "blocked",
                "readiness_reasons": ["universe_confidence_blocked"],
                "degraded_reasons": ["universe_empty"],
            },
        )

        result = await checker.check_system()

        assert result.readiness_status == "not_ready"
        assert "market_data_runtime_not_ready" in result.readiness_reasons
        assert "universe_confidence_blocked" in result.readiness_reasons
        assert "market_data:universe_empty" in result.readiness_reasons

    @pytest.mark.asyncio
    async def test_check_system_treats_phase6_to_phase8_as_not_ready_only(self) -> None:
        """Phase 6-8 upstream runtimes не должны создавать not_started drift в readiness truth."""
        identity = build_runtime_identity(
            bootstrap_module="cryptotechnolog.bootstrap",
            bootstrap_mode="production",
            active_risk_path="phase5_risk_engine",
        )
        checker = HealthChecker(runtime_identity=identity)
        checker.set_runtime_diagnostics(
            composition_root_built=True,
            runtime_started=True,
            runtime_ready=False,
            active_risk_path="phase5_risk_engine",
            market_data_runtime={"started": False, "ready": False, "readiness_reasons": []},
            shared_analysis_runtime={"started": False, "ready": False, "readiness_reasons": []},
            intelligence_runtime={"started": False, "ready": False, "readiness_reasons": []},
            signal_runtime={"started": False, "ready": False, "readiness_reasons": []},
        )

        result = await checker.check_system()

        assert result.readiness_status == "not_ready"
        assert "market_data_runtime_not_ready" in result.readiness_reasons
        assert "shared_analysis_runtime_not_ready" in result.readiness_reasons
        assert "intelligence_runtime_not_ready" in result.readiness_reasons
        assert "signal_runtime_not_ready" in result.readiness_reasons
        assert "market_data_runtime_not_started" not in result.readiness_reasons
        assert "shared_analysis_runtime_not_started" not in result.readiness_reasons
        assert "intelligence_runtime_not_started" not in result.readiness_reasons
        assert "signal_runtime_not_started" not in result.readiness_reasons

    @pytest.mark.asyncio
    async def test_check_and_wait_uses_readiness_truth_when_runtime_context_present(self) -> None:
        """check_and_wait должен ждать readiness, а не только overall health."""
        identity = build_runtime_identity(
            bootstrap_module="cryptotechnolog.bootstrap",
            bootstrap_mode="production",
            active_risk_path="phase5_risk_engine",
        )
        checker = HealthChecker(runtime_identity=identity)
        not_ready = SystemHealth(
            overall_status=HealthStatus.HEALTHY,
            components={},
            runtime_identity=identity,
            readiness_status="not_ready",
            diagnostics={
                "composition_root_built": True,
                "runtime_started": True,
                "runtime_ready": False,
                "startup_state": "starting",
                "shutdown_state": "not_shutting_down",
                "bootstrap_module": identity.bootstrap_module,
                "bootstrap_mode": identity.bootstrap_mode,
                "active_risk_path": identity.active_risk_path,
                "failure_reason": None,
                "degraded_reasons": [],
            },
        )
        ready = SystemHealth(
            overall_status=HealthStatus.HEALTHY,
            components={},
            runtime_identity=identity,
            readiness_status="ready",
            diagnostics={
                "composition_root_built": True,
                "runtime_started": True,
                "runtime_ready": True,
                "startup_state": "ready",
                "shutdown_state": "not_shutting_down",
                "bootstrap_module": identity.bootstrap_module,
                "bootstrap_mode": identity.bootstrap_mode,
                "active_risk_path": identity.active_risk_path,
                "failure_reason": None,
                "degraded_reasons": [],
            },
        )
        checker.check_system = AsyncMock(side_effect=[not_ready, ready])  # type: ignore[method-assign]

        with patch("cryptotechnolog.core.health.asyncio.sleep", new=AsyncMock()) as mocked_sleep:
            result = await checker.check_and_wait(timeout=2.0)

        assert result.readiness_status == "ready"
        assert checker.check_system.await_count == 2
        assert mocked_sleep.await_count == 1

    @pytest.mark.asyncio
    async def test_check_and_wait_falls_back_to_health_for_generic_usage(self) -> None:
        """Без runtime context helper должен оставаться совместимым с health-only usage."""
        checker = HealthChecker()
        healthy = SystemHealth(
            overall_status=HealthStatus.HEALTHY,
            components={},
            readiness_status="not_ready",
            diagnostics={
                "composition_root_built": False,
                "runtime_started": False,
                "runtime_ready": False,
                "startup_state": "not_started",
                "shutdown_state": "not_shutting_down",
                "bootstrap_module": None,
                "bootstrap_mode": None,
                "active_risk_path": None,
                "failure_reason": None,
                "degraded_reasons": [],
            },
        )
        checker.check_system = AsyncMock(return_value=healthy)  # type: ignore[method-assign]

        result = await checker.check_and_wait(timeout=0.1)

        assert result.overall_status == HealthStatus.HEALTHY
        assert checker.check_system.await_count == 1


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

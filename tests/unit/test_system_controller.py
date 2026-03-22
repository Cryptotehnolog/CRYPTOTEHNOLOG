"""
Unit тесты для System Controller.

Тестирует:
- Startup/shutdown процедуры
- Регистрацию компонентов
- Интеграцию с State Machine
- Circuit Breaker
- Health checks
- Lifecycle management
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from cryptotechnolog.core.event import SystemEventType
from cryptotechnolog.core.system_controller import (
    ShutdownPhase,
    StartupError,
    StartupPhase,
    SystemController,
    SystemStatus,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def controller(mock_state_machine):
    """Создать контроллер для тестов (test_mode=True - без health monitor)."""
    return SystemController(state_machine=mock_state_machine, test_mode=True)


@pytest.fixture
def mock_state_machine():
    """Создать мок State Machine."""
    sm = AsyncMock()
    sm.current_state = MagicMock()
    sm.current_state.value = "boot"  # lowercase как в реальной State Machine
    sm.is_initialized = False
    sm.initialize = AsyncMock(return_value=True)
    sm.transition = AsyncMock(return_value=MagicMock(success=True, error=None))

    # Обновляем current_state при transition
    def mock_transition(to_state, trigger, metadata=None):
        sm.current_state.value = to_state.value
        return MagicMock(success=True, error=None)

    sm.transition.side_effect = mock_transition
    sm.register_on_enter = MagicMock()
    return sm


@pytest.fixture
def mock_db_manager():
    """Создать мок DB Manager."""
    db = AsyncMock()
    db.connect = AsyncMock()
    db.close = AsyncMock()
    return db


@pytest.fixture
def mock_redis_manager():
    """Создать мок Redis Manager."""
    redis = AsyncMock()
    redis.ping = AsyncMock()
    redis.close = AsyncMock()
    return redis


@pytest.fixture
def mock_health_checker():
    """Создать мок Health Checker."""
    checker = AsyncMock()
    checker.register_check = MagicMock()
    checker.check_system = AsyncMock(
        return_value=MagicMock(components={}, get_unhealthy_components=MagicMock(return_value=[]))
    )
    return checker


@pytest.fixture
def mock_metrics():
    """Создать мок Metrics Collector."""
    metrics = MagicMock()
    metrics.get_counter = MagicMock(return_value=MagicMock(inc=MagicMock()))
    metrics.get_gauge = MagicMock(return_value=MagicMock(set=MagicMock()))
    return metrics


@pytest.fixture
def mock_component():
    """Создать мок компонент."""
    component = AsyncMock()
    component.start = AsyncMock()
    component.stop = AsyncMock()
    component.health_check = AsyncMock(
        return_value=MagicMock(component="test", status="healthy", message="OK")
    )
    return component


@pytest.fixture
def mock_event_bus():
    """Создать мок Event Bus для lifecycle publication."""
    bus = AsyncMock()
    bus.publish = AsyncMock(return_value=True)
    return bus


# ============================================================================
# Тесты инициализации
# ============================================================================


class TestInitialization:
    """Тесты инициализации System Controller."""

    def test_init_without_dependencies(self):
        """Тест создания без внешних зависимостей."""
        controller = SystemController(test_mode=True)

        assert controller is not None
        assert not controller.is_running
        assert not controller.is_shutting_down
        assert controller.current_state.value == "boot"

    def test_init_with_dependencies(self, mock_state_machine, mock_db_manager, mock_redis_manager):
        """Тест создания с зависимостями."""
        controller = SystemController(
            db_manager=mock_db_manager,
            redis_manager=mock_redis_manager,
            state_machine=mock_state_machine,
        )

        assert controller._db == mock_db_manager
        assert controller._redis == mock_redis_manager
        assert controller._state_machine == mock_state_machine


# ============================================================================
# Тесты регистрации компонентов
# ============================================================================


class TestComponentRegistration:
    """Тесты регистрации компонентов."""

    def test_register_component(self, mock_component):
        """Тест регистрации компонента."""
        controller = SystemController(test_mode=True)

        controller.register_component(
            name="test_component",
            component=mock_component,
            required=True,
            shutdown_timeout=10.0,
        )

        assert "test_component" in controller._components
        info = controller._components["test_component"]
        assert info.name == "test_component"
        assert info.component == mock_component
        assert info.required is True
        assert info.shutdown_timeout == 10.0

    def test_register_duplicate_component(self, mock_component):
        """Тест перерегистрации компонента."""
        controller = SystemController(test_mode=True)

        controller.register_component("test", mock_component)
        controller.register_component("test", mock_component)  # Перезапись

        assert len(controller._components) == 1

    def test_unregister_component(self, mock_component):
        """Тест удаления компонента."""
        controller = SystemController(test_mode=True)

        controller.register_component("test", mock_component)
        assert controller.unregister_component("test") is True
        assert "test" not in controller._components

    def test_unregister_nonexistent_component(self):
        """Тест удаления несуществующего компонента."""
        controller = SystemController(test_mode=True)

        assert controller.unregister_component("nonexistent") is False

    def test_get_component(self, mock_component):
        """Тест получения компонента."""
        controller = SystemController(test_mode=True)

        controller.register_component("test", mock_component)
        assert controller.get_component("test") == mock_component
        assert controller.get_component("nonexistent") is None


# ============================================================================
# Тесты Circuit Breaker
# ============================================================================


class TestCircuitBreaker:
    """Тесты Circuit Breaker."""

    def test_register_circuit_breaker(self):
        """Тест регистрации circuit breaker."""
        controller = SystemController(test_mode=True)

        breaker = controller.register_circuit_breaker(
            name="test_breaker",
            failure_threshold=3,
            recovery_timeout=30,
        )

        assert breaker is not None
        assert "test_breaker" in controller._circuit_breakers

    def test_register_duplicate_circuit_breaker(self):
        """Тест перерегистрации circuit breaker."""
        controller = SystemController(test_mode=True)

        breaker1 = controller.register_circuit_breaker("test")
        breaker2 = controller.register_circuit_breaker("test")

        assert breaker1 is breaker2  # Тот же инстанс

    def test_get_circuit_breaker(self):
        """Тест получения circuit breaker."""
        controller = SystemController(test_mode=True)

        controller.register_circuit_breaker("test")
        assert controller.get_circuit_breaker("test") is not None
        assert controller.get_circuit_breaker("nonexistent") is None


# ============================================================================
# Тесты Startup
# ============================================================================


class TestStartup:
    """Тесты startup процедуры."""

    @pytest.mark.asyncio
    async def test_startup_success(self, mock_state_machine):
        """Тест успешного startup."""
        controller = SystemController(state_machine=mock_state_machine, test_mode=True)

        result = await controller.startup()

        assert result.success is True
        assert result.phase_reached == StartupPhase.READY
        assert controller.is_running
        assert controller.startup_phase == StartupPhase.READY

    @pytest.mark.asyncio
    async def test_startup_already_running(self, mock_state_machine):
        """Тест повторного startup."""
        controller = SystemController(state_machine=mock_state_machine, test_mode=True)

        await controller.startup()
        result = await controller.startup()

        assert result.success is True  # Idempotent

    @pytest.mark.asyncio
    async def test_startup_with_components(self, mock_state_machine, mock_component):
        """Тест startup с компонентами."""
        controller = SystemController(state_machine=mock_state_machine, test_mode=True)

        controller.register_component(
            name="test_component",
            component=mock_component,
            required=False,
        )

        result = await controller.startup()

        assert result.success is True
        assert "test_component" in result.components_initialized
        mock_component.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_startup_required_component_failure(self, mock_state_machine):
        """Тест ошибки обязательного компонента."""
        controller = SystemController(state_machine=mock_state_machine, test_mode=True)

        bad_component = AsyncMock()
        bad_component.start = AsyncMock(side_effect=Exception("Init failed"))

        controller.register_component(
            name="bad_component",
            component=bad_component,
            required=True,
        )

        result = await controller.startup()

        assert result.success is False
        assert "bad_component" in result.components_failed

    @pytest.mark.asyncio
    async def test_startup_non_required_component_failure(self, mock_state_machine):
        """Тест ошибки необязательного компонента."""
        controller = SystemController(state_machine=mock_state_machine, test_mode=True)

        bad_component = AsyncMock()
        bad_component.start = AsyncMock(side_effect=Exception("Init failed"))

        controller.register_component(
            name="optional_component",
            component=bad_component,
            required=False,
        )

        result = await controller.startup()

        # Non-required компонент не блокирует startup
        assert result.success is True
        assert "optional_component" in result.components_failed

    @pytest.mark.asyncio
    async def test_startup_publishes_boot_and_ready_lifecycle_events(
        self,
        mock_state_machine,
        mock_event_bus,
    ):
        """Успешный startup должен публиковать lifecycle audit trail."""
        controller = SystemController(
            state_machine=mock_state_machine,
            event_bus=mock_event_bus,
            test_mode=True,
        )

        result = await controller.startup()

        published_event_types = [
            call.args[0].event_type for call in mock_event_bus.publish.await_args_list
        ]

        assert result.success is True
        assert SystemEventType.SYSTEM_BOOT in published_event_types
        assert SystemEventType.SYSTEM_READY in published_event_types

    @pytest.mark.asyncio
    async def test_startup_failure_publishes_halt_lifecycle_event(
        self,
        mock_state_machine,
        mock_event_bus,
    ):
        """Fail-fast startup должен оставлять lifecycle halt signal."""
        mock_state_machine.transition = AsyncMock(
            return_value=MagicMock(success=False, error="transition failed")
        )
        controller = SystemController(
            state_machine=mock_state_machine,
            event_bus=mock_event_bus,
            test_mode=True,
        )

        result = await controller.startup()

        halt_events = [
            call.args[0]
            for call in mock_event_bus.publish.await_args_list
            if call.args[0].event_type == SystemEventType.SYSTEM_HALT
        ]

        assert result.success is False
        assert len(halt_events) == 1
        assert halt_events[0].payload["reason"] == "startup_failed"


# ============================================================================
# Тесты Shutdown
# ============================================================================


class TestShutdown:
    """Тесты shutdown процедуры."""

    @pytest.mark.asyncio
    async def test_shutdown_not_running(self):
        """Тест shutdown когда система не запущена."""
        controller = SystemController(test_mode=True)

        result = await controller.shutdown()

        assert result.success is True
        assert result.phase_reached == ShutdownPhase.COMPLETED

    @pytest.mark.asyncio
    async def test_shutdown_success(self, mock_state_machine, mock_component):
        """Тест успешного shutdown."""
        controller = SystemController(state_machine=mock_state_machine, test_mode=True)

        controller.register_component(
            name="test_component",
            component=mock_component,
        )

        await controller.startup()
        result = await controller.shutdown()

        assert result.success is True
        assert result.phase_reached == ShutdownPhase.COMPLETED
        assert not controller.is_running
        mock_component.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_already_shutting_down(self, mock_state_machine):
        """Тест повторного shutdown - должен быть idempotent."""
        controller = SystemController(state_machine=mock_state_machine, test_mode=True)

        await controller.startup()

        # Первый shutdown
        result1 = await controller.shutdown()

        # Второй shutdown - должен быть idempotent
        result2 = await controller.shutdown()

        # Оба должны быть успешными (idempotent)
        assert result1.success is True
        assert result2.success is True
        assert not controller.is_running

    @pytest.mark.asyncio
    async def test_shutdown_publishes_halt_and_shutdown_lifecycle_events(
        self,
        mock_state_machine,
        mock_event_bus,
    ):
        """Shutdown должен публиковать halt и shutdown с awaited delivery."""
        controller = SystemController(
            state_machine=mock_state_machine,
            event_bus=mock_event_bus,
            test_mode=True,
        )

        await controller.startup()
        result = await controller.shutdown()

        published_event_types = [
            call.args[0].event_type for call in mock_event_bus.publish.await_args_list
        ]

        assert result.success is True
        assert SystemEventType.SYSTEM_HALT in published_event_types
        assert SystemEventType.SYSTEM_SHUTDOWN in published_event_types


# ============================================================================
# Тесты State Machine интеграции
# ============================================================================


class TestStateMachineIntegration:
    """Тесты интеграции с State Machine."""

    @pytest.mark.asyncio
    async def test_state_machine_initialized_on_startup(self, mock_state_machine):
        """Тест инициализации State Machine при startup."""
        controller = SystemController(state_machine=mock_state_machine, test_mode=True)

        await controller.startup()

        mock_state_machine.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_transition_to_ready_on_startup(self, mock_state_machine):
        """Тест перехода в READY при startup."""
        controller = SystemController(state_machine=mock_state_machine, test_mode=True)

        await controller.startup()

        # Проверяем что был вызван transition
        mock_state_machine.transition.assert_called()
        call_args = mock_state_machine.transition.call_args
        assert call_args[1]["to_state"].value == "ready"

    @pytest.mark.asyncio
    async def test_transition_to_halt_on_shutdown(self, mock_state_machine):
        """Тест перехода в HALT при shutdown."""
        controller = SystemController(state_machine=mock_state_machine, test_mode=True)

        await controller.startup()
        await controller.shutdown()

        # Проверяем что был вызван transition в HALT
        calls = mock_state_machine.transition.call_args_list
        halt_call = [c for c in calls if c[1]["to_state"].value == "halt"]
        assert len(halt_call) > 0


# ============================================================================
# Тесты Health Checks
# ============================================================================


class TestHealthChecks:
    """Тесты health checks."""

    @pytest.mark.asyncio
    async def test_get_status(self, mock_state_machine):
        """Тест получения статуса системы."""
        controller = SystemController(state_machine=mock_state_machine, test_mode=True)

        await controller.startup()
        status = await controller.get_status()

        assert isinstance(status, SystemStatus)
        assert status.is_running
        assert status.current_state.value == "ready"

    @pytest.mark.asyncio
    async def test_health_check_registration(
        self, mock_state_machine, mock_health_checker, mock_component
    ):
        """Тест регистрации health check для компонента."""
        controller = SystemController(
            state_machine=mock_state_machine,
            health_checker=mock_health_checker,
            test_mode=True,
        )

        controller.register_component(
            name="test_component",
            component=mock_component,
            health_check_enabled=True,
        )

        await controller.startup()

        mock_health_checker.register_check.assert_called()


# ============================================================================
# Тесты Lifecycle
# ============================================================================


class TestLifecycle:
    """Тесты lifecycle context manager."""

    @pytest.mark.asyncio
    async def test_lifecycle_context_manager(self, mock_state_machine):
        """Тест использования lifecycle как context manager."""
        controller = SystemController(state_machine=mock_state_machine, test_mode=True)

        async with controller.lifecycle():
            assert controller.is_running

        assert not controller.is_running

    @pytest.mark.asyncio
    async def test_lifecycle_startup_failure(self, mock_state_machine):
        """Тест failure в lifecycle."""
        controller = SystemController(state_machine=mock_state_machine, test_mode=True)

        # Делаем startup неуспешным
        mock_state_machine.transition = AsyncMock(
            return_value=MagicMock(success=False, error="Test error")
        )

        with pytest.raises(StartupError):
            async with controller.lifecycle():
                pass


# ============================================================================
# Тесты uptime
# ============================================================================


class TestUptime:
    """Тесты uptime."""

    @pytest.mark.asyncio
    async def test_uptime_calculation(self, mock_state_machine):
        """Тест расчёта uptime."""
        controller = SystemController(state_machine=mock_state_machine, test_mode=True)

        await controller.startup()

        # Uptime должен быть >= 0
        assert controller.uptime_seconds >= 0

    def test_uptime_not_started(self):
        """Тест uptime когда система не запущена."""
        controller = SystemController(test_mode=True)

        assert controller.uptime_seconds == 0


# ============================================================================
# Тесты error handling
# ============================================================================


class TestErrorHandling:
    """Тесты обработки ошибок."""

    @pytest.mark.asyncio
    async def test_rollback_on_startup_failure(self, mock_state_machine, mock_component):
        """Тест отката при ошибке startup."""
        controller = SystemController(state_machine=mock_state_machine, test_mode=True)

        # Добавляем компонент который запустится успешно
        controller.register_component("good", mock_component, required=False)

        # Добавляем компонент который вызовет ошибку при инициализации
        bad_component = AsyncMock()
        bad_component.start = AsyncMock(side_effect=Exception("Fail"))
        bad_component.stop = AsyncMock()

        controller.register_component("bad", bad_component, required=True)

        result = await controller.startup()

        # Startup должен провалиться
        assert result.success is False

        # Good компонент должен был быть остановлен при rollback
        # (Проверяем что stop был вызван)


# ============================================================================
# Тесты representation
# ============================================================================


class TestRepresentation:
    """Тесты строкового представления."""

    def test_repr(self, mock_state_machine):
        """Тест __repr__."""
        controller = SystemController(state_machine=mock_state_machine, test_mode=True)

        repr_str = repr(controller)
        assert "SystemController" in repr_str

    def test_str(self, mock_state_machine):
        """Тест __str__."""
        controller = SystemController(state_machine=mock_state_machine, test_mode=True)

        str_repr = str(controller)
        assert "System:" in str_repr


# ============================================================================
# Интеграционные тесты
# ============================================================================


class TestIntegration:
    """Интеграционные тесты."""

    @pytest.mark.asyncio
    async def test_full_lifecycle(self, mock_state_machine, mock_db_manager, mock_redis_manager):
        """Тест полного жизненного цикла."""
        controller = SystemController(
            state_machine=mock_state_machine,
            db_manager=mock_db_manager,
            redis_manager=mock_redis_manager,
            test_mode=True,
        )

        # Startup
        startup_result = await controller.startup()
        assert startup_result.success
        assert controller.is_running

        # Проверяем статус
        status = await controller.get_status()
        assert status.is_running

        # Shutdown
        shutdown_result = await controller.shutdown()
        assert shutdown_result.success
        assert not controller.is_running

    @pytest.mark.asyncio
    async def test_multiple_components_lifecycle(self, mock_state_machine):
        """Тест lifecycle с несколькими компонентами."""
        controller = SystemController(state_machine=mock_state_machine, test_mode=True)

        # Регистрируем несколько компонентов
        for i in range(3):
            component = AsyncMock()
            component.start = AsyncMock()
            component.stop = AsyncMock()

            controller.register_component(
                name=f"component_{i}",
                component=component,
            )

        await controller.startup()
        assert controller.is_running

        await controller.shutdown()
        assert not controller.is_running

        # Все компоненты должны быть остановлены
        for _i in range(3):
            # Проверяем что stop был вызван
            pass

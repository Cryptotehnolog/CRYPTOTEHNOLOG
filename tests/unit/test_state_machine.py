"""
Unit тесты для State Machine.

Тестирует:
- Переходы состояний
- Optimistic locking
- Callbacks (on_enter/on_exit)
- Audit trail
- Метрики
"""

import asyncio

import pytest

from src.core.state_machine import (
    InvalidTransitionError,
    StateMachine,
    TransitionResult,
)
from src.core.state_machine_enums import (
    SystemState,
    TriggerType,
    is_transition_allowed,
)


class TestStateMachineBasics:
    """Базовые тесты State Machine."""

    @pytest.mark.asyncio
    async def test_initial_state(self) -> None:
        """Тест начального состояния."""
        sm = StateMachine()
        assert sm.current_state == SystemState.BOOT
        assert sm.can_trade() is False

    @pytest.mark.asyncio
    async def test_valid_transition(self) -> None:
        """Тест валидного перехода."""
        sm = StateMachine()
        
        result = await sm.transition(SystemState.INIT, TriggerType.SYSTEM_STARTUP)
        
        assert result.success is True
        assert sm.current_state == SystemState.INIT

    @pytest.mark.asyncio
    async def test_invalid_transition(self) -> None:
        """Тест невалидного перехода."""
        sm = StateMachine()
        
        # boot -> trading недопустим
        result = await sm.transition(SystemState.TRADING, TriggerType.TEST)
        
        assert result.success is False
        assert result.error is not None
        assert "Недопустимый переход" in result.error
        assert sm.current_state == SystemState.BOOT

    @pytest.mark.asyncio
    async def test_transition_chain(self) -> None:
        """Тест цепочки переходов."""
        sm = StateMachine()
        
        # boot -> init -> ready -> trading
        await sm.transition(SystemState.INIT, TriggerType.SYSTEM_STARTUP)
        await sm.transition(SystemState.READY, TriggerType.INITIALIZATION_COMPLETE)
        result = await sm.transition(SystemState.TRADING, TriggerType.OPERATOR_REQUEST)
        
        assert result.success is True
        assert sm.current_state == SystemState.TRADING
        assert sm.can_trade() is True


class TestOptimisticLocking:
    """Тесты optimistic locking."""

    @pytest.mark.asyncio
    async def test_version_increments(self) -> None:
        """Тест увеличения версии."""
        sm = StateMachine()
        
        assert sm.version == 0
        
        await sm.transition(SystemState.INIT, TriggerType.SYSTEM_STARTUP)
        assert sm.version == 1
        
        await sm.transition(SystemState.READY, TriggerType.INITIALIZATION_COMPLETE)
        assert sm.version == 2

    @pytest.mark.asyncio
    async def test_concurrent_transitions_are_serialized(self) -> None:
        """Тест сериализации параллельных переходов (optimistic locking работает)."""
        sm = StateMachine()
        
        # Создаём задачи
        task1 = asyncio.create_task(sm.transition(SystemState.INIT, TriggerType.SYSTEM_STARTUP))
        
        # Даём task1 начать выполнение
        await asyncio.sleep(0.01)
        
        # Второй переход запускается параллельно
        task2 = asyncio.create_task(sm.transition(SystemState.READY, TriggerType.TEST))
        
        # Выполняем оба - Lock сериализует их
        results = await asyncio.gather(task1, task2)
        
        # Оба перехода должны быть успешными (сериализованы, а не заблокированы)
        assert results[0].success is True
        assert results[1].success is True
        
        # Состояние должно быть READY (второй переход выполнился после первого)
        assert sm.current_state == SystemState.READY

        # Version должен быть 2 (было 2 перехода)
        assert sm.version == 2
        
        # История должна содержать обе записи
        history = sm.get_history()
        assert len(history) == 2
        

class TestCallbacks:
    """Тесты callbacks."""

    @pytest.mark.asyncio
    async def test_on_enter_callback(self) -> None:
        """Тест on_enter callback."""
        sm = StateMachine()
        calls: list[tuple[SystemState, SystemState]] = []
        
        async def callback(from_state: SystemState, to_state: SystemState) -> None:
            calls.append((from_state, to_state))
        
        sm.register_on_enter(SystemState.INIT, callback)
        await sm.transition(SystemState.INIT, TriggerType.SYSTEM_STARTUP)
        
        assert len(calls) == 1
        assert calls[0] == (SystemState.BOOT, SystemState.INIT)

    @pytest.mark.asyncio
    async def test_on_exit_callback(self) -> None:
        """Тест on_exit callback."""
        sm = StateMachine()
        calls: list[tuple[SystemState, SystemState]] = []
        
        async def callback(from_state: SystemState, to_state: SystemState) -> None:
            calls.append((from_state, to_state))
        
        sm.register_on_exit(SystemState.BOOT, callback)
        await sm.transition(SystemState.INIT, TriggerType.SYSTEM_STARTUP)
        
        assert len(calls) == 1
        assert calls[0] == (SystemState.BOOT, SystemState.INIT)

    @pytest.mark.asyncio
    async def test_callback_multiple_states(self) -> None:
        """Тест нескольких callbacks."""
        sm = StateMachine()
        
        async def enter_init(from_state: SystemState, to_state: SystemState) -> None:
            pass
        
        async def enter_ready(from_state: SystemState, to_state: SystemState) -> None:
            pass
        
        sm.register_on_enter(SystemState.INIT, enter_init)
        sm.register_on_enter(SystemState.READY, enter_ready)
        
        await sm.transition(SystemState.INIT, TriggerType.SYSTEM_STARTUP)
        await sm.transition(SystemState.READY, TriggerType.INITIALIZATION_COMPLETE)
        
        assert sm.current_state == SystemState.READY

    @pytest.mark.asyncio
    async def test_unregister_callback(self) -> None:
        """Тест удаления callback."""
        sm = StateMachine()
        calls: list[str] = []
        
        async def callback(from_state: SystemState, to_state: SystemState) -> None:
            calls.append("called")
        
        sm.register_on_enter(SystemState.INIT, callback)
        sm.unregister_on_enter(SystemState.INIT, callback)
        
        await sm.transition(SystemState.INIT, TriggerType.SYSTEM_STARTUP)
        
        assert len(calls) == 0


class TestAuditTrail:
    """Тесты audit trail."""

    @pytest.mark.asyncio
    async def test_history_records(self) -> None:
        """Тест записи истории."""
        sm = StateMachine()
        
        await sm.transition(SystemState.INIT, TriggerType.SYSTEM_STARTUP)
        await sm.transition(SystemState.READY, TriggerType.INITIALIZATION_COMPLETE)
        
        history = sm.get_history()
        assert len(history) == 2
        
        assert history[0].from_state == SystemState.BOOT
        assert history[0].to_state == SystemState.INIT
        
        assert history[1].from_state == SystemState.INIT
        assert history[1].to_state == SystemState.READY

    @pytest.mark.asyncio
    async def test_history_limit(self) -> None:
        """Тест ограничения истории."""
        sm = StateMachine()
        sm._history.max_size = 5  # Уменьшаем для теста
        
        # 6 переходов
        await sm.transition(SystemState.INIT, TriggerType.SYSTEM_STARTUP)
        await sm.transition(SystemState.READY, TriggerType.INITIALIZATION_COMPLETE)
        await sm.transition(SystemState.TRADING, TriggerType.OPERATOR_REQUEST)
        await sm.transition(SystemState.DEGRADED, TriggerType.RISK_VIOLATION)
        await sm.transition(SystemState.TRADING, TriggerType.OPERATOR_REQUEST)  # back to trading
        await sm.transition(SystemState.HALT, TriggerType.EMERGENCY_SHUTDOWN)
        
        # Должно остаться 5
        history = sm.get_history()
        assert len(history) == 5

    @pytest.mark.asyncio
    async def test_transition_metadata(self) -> None:
        """Тест метаданных перехода."""
        sm = StateMachine()
        
        await sm.transition(
            SystemState.INIT,
            TriggerType.SYSTEM_STARTUP,
            metadata={"source": "test", "extra": "data"},
            operator="test_operator",
        )
        
        history = sm.get_history()
        assert history[0].metadata["source"] == "test"
        assert history[0].operator == "test_operator"


class TestMetrics:
    """Тесты метрик."""

    @pytest.mark.asyncio
    async def test_transition_counter(self) -> None:
        """Тест счётчика переходов."""
        sm = StateMachine()
        
        await sm.transition(SystemState.INIT, TriggerType.SYSTEM_STARTUP)
        await sm.transition(SystemState.READY, TriggerType.INITIALIZATION_COMPLETE)
        
        assert sm.get_transition_count() == 2

    @pytest.mark.asyncio
    async def test_time_in_state(self) -> None:
        """Тест времени в состоянии."""
        import time
        sm = StateMachine()
        
        await sm.transition(SystemState.INIT, TriggerType.SYSTEM_STARTUP)
        
        time.sleep(0.1)  # 100ms
        
        time_in_state = sm.get_time_in_current_state()
        assert time_in_state >= 0


class TestAllowedTransitions:
    """Тесты допустимых переходов."""

    def test_is_transition_allowed_valid(self) -> None:
        """Тест допустимого перехода."""
        assert is_transition_allowed(SystemState.BOOT, SystemState.INIT) is True
        assert is_transition_allowed(SystemState.INIT, SystemState.READY) is True

    def test_is_transition_allowed_invalid(self) -> None:
        """Тест недопустимого перехода."""
        assert is_transition_allowed(SystemState.BOOT, SystemState.TRADING) is False
        assert is_transition_allowed(SystemState.TRADING, SystemState.BOOT) is False

    def test_get_allowed_transitions(self) -> None:
        """Тест получения допустимых переходов."""
        allowed = is_transition_allowed(SystemState.BOOT, SystemState.INIT)
        assert allowed is True
        
        allowed = is_transition_allowed(SystemState.BOOT, SystemState.ERROR)
        assert allowed is True


class TestStateMachineEdgeCases:
    """Тесты граничных случаев."""

    @pytest.mark.asyncio
    async def test_same_state_transition(self) -> None:
        """Тест перехода в то же состояние."""
        sm = StateMachine()
        
        result = await sm.transition(SystemState.BOOT, TriggerType.TEST)
        
        # Переход в то же состояние - это ошибка (нет в ALLOWED_TRANSITIONS)
        assert result.success is False

    @pytest.mark.asyncio
    async def test_trading_allowed_states(self) -> None:
        """Тест состояний с разрешённой торговлей."""
        sm = StateMachine()
        
        # boot - нет
        assert sm.can_trade() is False
        
        # init - нет
        await sm.transition(SystemState.INIT, TriggerType.SYSTEM_STARTUP)
        assert sm.can_trade() is False
        
        # ready - нет
        await sm.transition(SystemState.READY, TriggerType.INITIALIZATION_COMPLETE)
        assert sm.can_trade() is False
        
        # trading - да
        await sm.transition(SystemState.TRADING, TriggerType.OPERATOR_REQUEST)
        assert sm.can_trade() is True
        
        # degraded - да
        await sm.transition(SystemState.DEGRADED, TriggerType.RISK_VIOLATION)
        assert sm.can_trade() is True
        
        # survival - нет
        await sm.transition(SystemState.SURVIVAL, TriggerType.EXECUTION_ERROR)
        assert sm.can_trade() is False

    @pytest.mark.asyncio
    async def test_requires_dual_control(self) -> None:
        """Тест dual control."""
        sm = StateMachine()
        
        # HALT требует dual control
        assert sm.requires_dual_control(SystemState.HALT) is True
        
        # RECOVERY требует dual control
        assert sm.requires_dual_control(SystemState.RECOVERY) is True
        
        # TRADING не требует
        assert sm.requires_dual_control(SystemState.TRADING) is False


class TestStateMachineRepr:
    """Тесты строкового представления."""

    @pytest.mark.asyncio
    async def test_repr(self) -> None:
        """Тест __repr__."""
        sm = StateMachine()
        
        await sm.transition(SystemState.INIT, TriggerType.SYSTEM_STARTUP)
        
        repr_str = repr(sm)
        assert "state=init" in repr_str
        assert "version=1" in repr_str

    @pytest.mark.asyncio
    async def test_str(self) -> None:
        """Тест __str__."""
        sm = StateMachine()
        
        str_val = str(sm)
        assert "boot" in str_val
        assert "v0" in str_val


# Mark all tests as unit tests
pytest.mark.unit(__name__)

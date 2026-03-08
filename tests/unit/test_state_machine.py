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
import time

import pytest

from cryptotechnolog.core.state_machine import (
    StateMachine,
)
from cryptotechnolog.core.state_machine_enums import (
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


class TestStateMachineUncoveredMethods:
    """Тесты для непокрытых методов State Machine."""

    @pytest.mark.asyncio
    async def test_is_state_timeout_exceeded(self) -> None:
        """Тест проверки таймаута состояния."""
        sm = StateMachine()

        # По умолчанию таймаут не превышен
        assert sm.is_state_timeout_exceeded() is False

    @pytest.mark.asyncio
    async def test_get_next_state_on_timeout(self) -> None:
        """Тест получения следующего состояния при таймауте."""
        sm = StateMachine()

        # Переходим в состояние с таймаутом
        await sm.transition(SystemState.INIT, TriggerType.SYSTEM_STARTUP)

        # Получаем следующее состояние при таймауте
        next_state = sm._get_next_state_on_timeout()

        # Для INIT таймаут ведёт в ERROR
        assert next_state == SystemState.ERROR

    @pytest.mark.asyncio
    async def test_get_state_policy_description(self) -> None:
        """Тест получения описания политики состояния."""
        sm = StateMachine()

        # Переходим в состояние TRADING
        await sm.transition(SystemState.INIT, TriggerType.SYSTEM_STARTUP)
        await sm.transition(SystemState.READY, TriggerType.INITIALIZATION_COMPLETE)
        await sm.transition(SystemState.TRADING, TriggerType.OPERATOR_REQUEST)

        desc = sm.get_state_policy_description()
        # Описание на русском языке
        assert len(desc) > 0

    @pytest.mark.asyncio
    async def test_get_state_timeout(self) -> None:
        """Тест получения таймаута текущего состояния."""
        sm = StateMachine()

        # Для BOOT таймаут 60 секунд
        timeout = sm.get_state_timeout()
        assert timeout == 60

    @pytest.mark.asyncio
    async def test_get_state_timeout_trading(self) -> None:
        """Тест таймаута для состояния TRADING (нет таймаута)."""
        sm = StateMachine()

        # Переходим в TRADING
        await sm.transition(SystemState.INIT, TriggerType.SYSTEM_STARTUP)
        await sm.transition(SystemState.READY, TriggerType.INITIALIZATION_COMPLETE)
        await sm.transition(SystemState.TRADING, TriggerType.OPERATOR_REQUEST)

        # TRADING не имеет таймаута
        timeout = sm.get_state_timeout()
        assert timeout is None

    @pytest.mark.asyncio
    async def test_can_trade_method(self) -> None:
        """Тест метода can_trade."""
        sm = StateMachine()

        # BOOT не разрешает торговлю
        assert sm.can_trade() is False

    @pytest.mark.asyncio
    async def test_is_transitioning(self) -> None:
        """Тест метода is_transitioning."""
        sm = StateMachine()

        # По умолчанию не в процессе перехода
        assert sm.is_transitioning() is False

    @pytest.mark.asyncio
    async def test_is_trade_allowed(self) -> None:
        """Тест метода is_trade_allowed."""
        sm = StateMachine()

        # По умолчанию торговля не разрешена
        assert sm.is_trade_allowed() is False

    @pytest.mark.asyncio
    async def test_get_allowed_transitions(self) -> None:
        """Тест получения списка допустимых переходов."""
        sm = StateMachine()

        allowed = sm.get_allowed_transitions()

        # Из BOOT можно перейти только в INIT
        assert SystemState.INIT in allowed

    @pytest.mark.asyncio
    async def test_can_transition_to(self) -> None:
        """Тест проверки возможности перехода."""
        sm = StateMachine()

        # Из BOOT можно перейти в INIT
        assert sm.can_transition_to(SystemState.INIT) is True

        # Из BOOT нельзя перейти напрямую в TRADING
        assert sm.can_transition_to(SystemState.TRADING) is False

    @pytest.mark.asyncio
    async def test_get_transition_count(self) -> None:
        """Тест получения количества переходов."""
        sm = StateMachine()

        assert sm.get_transition_count() == 0

        await sm.transition(SystemState.INIT, TriggerType.SYSTEM_STARTUP)

        assert sm.get_transition_count() == 1

    @pytest.mark.asyncio
    async def test_get_time_in_current_state(self) -> None:
        """Тест получения времени в текущем состоянии."""
        sm = StateMachine()

        time_in_state = sm.get_time_in_current_state()
        assert time_in_state >= 0

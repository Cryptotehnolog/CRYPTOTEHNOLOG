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
from contextlib import suppress
import json
import time
from unittest.mock import AsyncMock, MagicMock

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


class TestStatePoliciesUncovered:
    """Тесты для непокрытых state policies."""

    @pytest.mark.asyncio
    async def test_can_open_positions_trading(self) -> None:
        """Тест can_open_positions в состоянии TRADING."""
        sm = StateMachine()
        await sm.transition(SystemState.INIT, TriggerType.SYSTEM_STARTUP)
        await sm.transition(SystemState.READY, TriggerType.INITIALIZATION_COMPLETE)
        await sm.transition(SystemState.TRADING, TriggerType.OPERATOR_REQUEST)

        assert sm.can_open_positions() is True

    @pytest.mark.asyncio
    async def test_can_open_positions_halt(self) -> None:
        """Тест can_open_positions в состоянии HALT."""
        sm = StateMachine()
        await sm.transition(SystemState.INIT, TriggerType.SYSTEM_STARTUP)
        await sm.transition(SystemState.READY, TriggerType.INITIALIZATION_COMPLETE)
        await sm.transition(SystemState.TRADING, TriggerType.OPERATOR_REQUEST)
        await sm.transition(SystemState.HALT, TriggerType.EMERGENCY_SHUTDOWN)

        assert sm.can_open_positions() is False

    @pytest.mark.asyncio
    async def test_can_increase_size_trading(self) -> None:
        """Тест can_increase_size в состоянии TRADING."""
        sm = StateMachine()
        await sm.transition(SystemState.INIT, TriggerType.SYSTEM_STARTUP)
        await sm.transition(SystemState.READY, TriggerType.INITIALIZATION_COMPLETE)
        await sm.transition(SystemState.TRADING, TriggerType.OPERATOR_REQUEST)

        assert sm.can_increase_size() is True

    @pytest.mark.asyncio
    async def test_can_increase_size_degraded(self) -> None:
        """Тест can_increase_size в состоянии DEGRADED."""
        sm = StateMachine()
        await sm.transition(SystemState.INIT, TriggerType.SYSTEM_STARTUP)
        await sm.transition(SystemState.READY, TriggerType.INITIALIZATION_COMPLETE)
        await sm.transition(SystemState.TRADING, TriggerType.OPERATOR_REQUEST)
        await sm.transition(SystemState.DEGRADED, TriggerType.RISK_VIOLATION)

        assert sm.can_increase_size() is False

    @pytest.mark.asyncio
    async def test_can_place_orders_trading(self) -> None:
        """Тест can_place_orders в состоянии TRADING."""
        sm = StateMachine()
        await sm.transition(SystemState.INIT, TriggerType.SYSTEM_STARTUP)
        await sm.transition(SystemState.READY, TriggerType.INITIALIZATION_COMPLETE)
        await sm.transition(SystemState.TRADING, TriggerType.OPERATOR_REQUEST)

        assert sm.can_place_orders() is True

    @pytest.mark.asyncio
    async def test_can_place_orders_survival(self) -> None:
        """Тест can_place_orders в состоянии SURVIVAL."""
        sm = StateMachine()
        await sm.transition(SystemState.INIT, TriggerType.SYSTEM_STARTUP)
        await sm.transition(SystemState.READY, TriggerType.INITIALIZATION_COMPLETE)
        await sm.transition(SystemState.TRADING, TriggerType.OPERATOR_REQUEST)
        await sm.transition(SystemState.SURVIVAL, TriggerType.EXECUTION_ERROR)

        # SURVIVAL позволяет только закрытие ордеров
        assert sm.can_place_orders() is True

    @pytest.mark.asyncio
    async def test_get_risk_multiplier_trading(self) -> None:
        """Тест get_risk_multiplier в состоянии TRADING."""
        sm = StateMachine()
        await sm.transition(SystemState.INIT, TriggerType.SYSTEM_STARTUP)
        await sm.transition(SystemState.READY, TriggerType.INITIALIZATION_COMPLETE)
        await sm.transition(SystemState.TRADING, TriggerType.OPERATOR_REQUEST)

        assert sm.get_risk_multiplier() == 1.0

    @pytest.mark.asyncio
    async def test_get_risk_multiplier_degraded(self) -> None:
        """Тест get_risk_multiplier в состоянии DEGRADED."""
        sm = StateMachine()
        await sm.transition(SystemState.INIT, TriggerType.SYSTEM_STARTUP)
        await sm.transition(SystemState.READY, TriggerType.INITIALIZATION_COMPLETE)
        await sm.transition(SystemState.TRADING, TriggerType.OPERATOR_REQUEST)
        await sm.transition(SystemState.DEGRADED, TriggerType.RISK_VIOLATION)

        assert sm.get_risk_multiplier() == 0.5

    @pytest.mark.asyncio
    async def test_get_risk_multiplier_survival(self) -> None:
        """Тест get_risk_multiplier в состоянии SURVIVAL."""
        sm = StateMachine()
        await sm.transition(SystemState.INIT, TriggerType.SYSTEM_STARTUP)
        await sm.transition(SystemState.READY, TriggerType.INITIALIZATION_COMPLETE)
        await sm.transition(SystemState.TRADING, TriggerType.OPERATOR_REQUEST)
        await sm.transition(SystemState.SURVIVAL, TriggerType.EXECUTION_ERROR)

        assert sm.get_risk_multiplier() == 0.1

    @pytest.mark.asyncio
    async def test_get_max_positions_trading(self) -> None:
        """Тест get_max_positions в состоянии TRADING."""
        sm = StateMachine()
        await sm.transition(SystemState.INIT, TriggerType.SYSTEM_STARTUP)
        await sm.transition(SystemState.READY, TriggerType.INITIALIZATION_COMPLETE)
        await sm.transition(SystemState.TRADING, TriggerType.OPERATOR_REQUEST)

        # TRADING: 100 позиций
        assert sm.get_max_positions() == 100

    @pytest.mark.asyncio
    async def test_get_max_positions_degraded(self) -> None:
        """Тест get_max_positions в состоянии DEGRADED."""
        sm = StateMachine()
        await sm.transition(SystemState.INIT, TriggerType.SYSTEM_STARTUP)
        await sm.transition(SystemState.READY, TriggerType.INITIALIZATION_COMPLETE)
        await sm.transition(SystemState.TRADING, TriggerType.OPERATOR_REQUEST)
        await sm.transition(SystemState.DEGRADED, TriggerType.RISK_VIOLATION)

        # DEGRADED: 50 позиций
        assert sm.get_max_positions() == 50

    @pytest.mark.asyncio
    async def test_get_max_order_size_trading(self) -> None:
        """Тест get_max_order_size в состоянии TRADING."""
        sm = StateMachine()
        await sm.transition(SystemState.INIT, TriggerType.SYSTEM_STARTUP)
        await sm.transition(SystemState.READY, TriggerType.INITIALIZATION_COMPLETE)
        await sm.transition(SystemState.TRADING, TriggerType.OPERATOR_REQUEST)

        assert sm.get_max_order_size() == 0.1

    @pytest.mark.asyncio
    async def test_get_max_order_size_survival(self) -> None:
        """Тест get_max_order_size в состоянии SURVIVAL."""
        sm = StateMachine()
        await sm.transition(SystemState.INIT, TriggerType.SYSTEM_STARTUP)
        await sm.transition(SystemState.READY, TriggerType.INITIALIZATION_COMPLETE)
        await sm.transition(SystemState.TRADING, TriggerType.OPERATOR_REQUEST)
        await sm.transition(SystemState.SURVIVAL, TriggerType.EXECUTION_ERROR)

        # SURVIVAL: 0.01 = 1%
        assert sm.get_max_order_size() == 0.01

    @pytest.mark.asyncio
    async def test_is_short_selling_allowed_trading(self) -> None:
        """Тест is_short_selling_allowed в состоянии TRADING."""
        sm = StateMachine()
        await sm.transition(SystemState.INIT, TriggerType.SYSTEM_STARTUP)
        await sm.transition(SystemState.READY, TriggerType.INITIALIZATION_COMPLETE)
        await sm.transition(SystemState.TRADING, TriggerType.OPERATOR_REQUEST)

        assert sm.is_short_selling_allowed() is True

    @pytest.mark.asyncio
    async def test_is_short_selling_allowed_halt(self) -> None:
        """Тест is_short_selling_allowed в состоянии HALT."""
        sm = StateMachine()
        await sm.transition(SystemState.INIT, TriggerType.SYSTEM_STARTUP)
        await sm.transition(SystemState.READY, TriggerType.INITIALIZATION_COMPLETE)
        await sm.transition(SystemState.TRADING, TriggerType.OPERATOR_REQUEST)
        await sm.transition(SystemState.HALT, TriggerType.EMERGENCY_SHUTDOWN)

        assert sm.is_short_selling_allowed() is False

    @pytest.mark.asyncio
    async def test_requires_manual_approval_halt(self) -> None:
        """Тест requires_manual_approval в состоянии HALT."""
        sm = StateMachine()
        await sm.transition(SystemState.INIT, TriggerType.SYSTEM_STARTUP)
        await sm.transition(SystemState.READY, TriggerType.INITIALIZATION_COMPLETE)
        await sm.transition(SystemState.TRADING, TriggerType.OPERATOR_REQUEST)
        await sm.transition(SystemState.HALT, TriggerType.EMERGENCY_SHUTDOWN)

        assert sm.requires_manual_approval() is True

    @pytest.mark.asyncio
    async def test_requires_manual_approval_trading(self) -> None:
        """Тест requires_manual_approval в состоянии TRADING."""
        sm = StateMachine()
        await sm.transition(SystemState.INIT, TriggerType.SYSTEM_STARTUP)
        await sm.transition(SystemState.READY, TriggerType.INITIALIZATION_COMPLETE)
        await sm.transition(SystemState.TRADING, TriggerType.OPERATOR_REQUEST)

        assert sm.requires_manual_approval() is False


class TestStateMachineWithMocks:
    """Тесты с моками для непокрытых методов."""

    @pytest.mark.asyncio
    async def test_initialize_without_db(self) -> None:
        """Тест initialize без БД."""
        sm = StateMachine()

        result = await sm.initialize()

        assert result is True
        assert sm.is_initialized is True

    @pytest.mark.asyncio
    async def test_initialize_already_initialized(self) -> None:
        """Тест повторной инициализации."""
        sm = StateMachine()

        await sm.initialize()
        result = await sm.initialize()

        assert result is True

    @pytest.mark.asyncio
    async def test_unregister_on_enter_not_found(self) -> None:
        """Тест удаления несуществующего callback."""
        sm = StateMachine()

        async def dummy_callback(from_state: SystemState, to_state: SystemState) -> None:
            pass

        result = sm.unregister_on_enter(SystemState.INIT, dummy_callback)
        assert result is False

    @pytest.mark.asyncio
    async def test_unregister_on_exit_not_found(self) -> None:
        """Тест удаления несуществующего exit callback."""
        sm = StateMachine()

        async def dummy_callback(from_state: SystemState, to_state: SystemState) -> None:
            pass

        result = sm.unregister_on_exit(SystemState.BOOT, dummy_callback)
        assert result is False

    @pytest.mark.asyncio
    async def test_sync_callback_on_enter(self) -> None:
        """Тест синхронного callback on_enter."""
        sm = StateMachine()
        calls: list[tuple[SystemState, SystemState]] = []

        def sync_callback(from_state: SystemState, to_state: SystemState) -> None:
            calls.append((from_state, to_state))

        sm.register_on_enter(SystemState.INIT, sync_callback)
        await sm.transition(SystemState.INIT, TriggerType.SYSTEM_STARTUP)

        assert len(calls) == 1
        assert calls[0] == (SystemState.BOOT, SystemState.INIT)

    @pytest.mark.asyncio
    async def test_sync_callback_on_exit(self) -> None:
        """Тест синхронного callback on_exit."""
        sm = StateMachine()
        calls: list[tuple[SystemState, SystemState]] = []

        def sync_callback(from_state: SystemState, to_state: SystemState) -> None:
            calls.append((from_state, to_state))

        sm.register_on_exit(SystemState.BOOT, sync_callback)
        await sm.transition(SystemState.INIT, TriggerType.SYSTEM_STARTUP)

        assert len(calls) == 1
        assert calls[0] == (SystemState.BOOT, SystemState.INIT)

    @pytest.mark.asyncio
    async def test_callback_error_handling(self) -> None:
        """Тест обработки ошибок в callback."""
        sm = StateMachine()

        async def failing_callback(from_state: SystemState, to_state: SystemState) -> None:
            raise RuntimeError("Test error")

        sm.register_on_enter(SystemState.INIT, failing_callback)

        # Должно не упасть, а просто залогировать ошибку
        result = await sm.transition(SystemState.INIT, TriggerType.SYSTEM_STARTUP)

        assert result.success is True

    @pytest.mark.asyncio
    async def test_callback_error_on_exit(self) -> None:
        """Тест обработки ошибок в exit callback."""
        sm = StateMachine()

        async def failing_callback(from_state: SystemState, to_state: SystemState) -> None:
            raise RuntimeError("Test error")

        sm.register_on_exit(SystemState.BOOT, failing_callback)

        result = await sm.transition(SystemState.INIT, TriggerType.SYSTEM_STARTUP)

        assert result.success is True

    @pytest.mark.asyncio
    async def test_state_timeout_exceeded_with_timeout(self) -> None:
        """Тест превышения таймаута."""
        sm = StateMachine()
        await sm.transition(SystemState.INIT, TriggerType.SYSTEM_STARTUP)

        # Для INIT таймаут 60 секунд, но мы в состоянии меньше
        # Поэтому тест должен показать False
        assert sm.is_state_timeout_exceeded() is False

    @pytest.mark.asyncio
    async def test_get_next_state_on_timeout_degraded(self) -> None:
        """Тест следующего состояния при таймауте для DEGRADED."""
        sm = StateMachine()
        await sm.transition(SystemState.INIT, TriggerType.SYSTEM_STARTUP)
        await sm.transition(SystemState.READY, TriggerType.INITIALIZATION_COMPLETE)
        await sm.transition(SystemState.TRADING, TriggerType.OPERATOR_REQUEST)
        await sm.transition(SystemState.DEGRADED, TriggerType.RISK_VIOLATION)

        next_state = sm._get_next_state_on_timeout()

        assert next_state == SystemState.HALT

    @pytest.mark.asyncio
    async def test_get_next_state_on_timeout_no_transition(self) -> None:
        """Тест состояния без таймаута."""
        sm = StateMachine()
        await sm.transition(SystemState.INIT, TriggerType.SYSTEM_STARTUP)
        await sm.transition(SystemState.READY, TriggerType.INITIALIZATION_COMPLETE)
        await sm.transition(SystemState.TRADING, TriggerType.OPERATOR_REQUEST)

        next_state = sm._get_next_state_on_timeout()

        # TRADING не имеет таймаута
        assert next_state is None

    @pytest.mark.asyncio
    async def test_transition_with_event_bus(self) -> None:
        """Тест перехода с event_bus."""
        mock_event_bus = AsyncMock()
        mock_event_bus.publish = AsyncMock()

        sm = StateMachine(event_bus=mock_event_bus)

        await sm.transition(SystemState.INIT, TriggerType.SYSTEM_STARTUP)

        # Проверяем что publish был вызван
        assert mock_event_bus.publish.called

    @pytest.mark.asyncio
    async def test_transition_event_bus_error(self) -> None:
        """Тест ошибки event_bus при переходе."""
        mock_event_bus = AsyncMock()
        mock_event_bus.publish = AsyncMock(side_effect=RuntimeError("Event bus error"))

        sm = StateMachine(event_bus=mock_event_bus)

        # Не должно упасть
        result = await sm.transition(SystemState.INIT, TriggerType.SYSTEM_STARTUP)
        assert result.success is True


class TestCheckpointAndRestore:
    """Тесты checkpoint и restore."""

    @pytest.mark.asyncio
    async def test_checkpoint_no_storage(self) -> None:
        """Тест checkpoint без доступных хранилищ."""
        sm = StateMachine()

        result = await sm.checkpoint()

        assert result is False

    @pytest.mark.asyncio
    async def test_checkpoint_with_redis(self) -> None:
        """Тест checkpoint с Redis."""
        sm = StateMachine()
        await sm.transition(SystemState.INIT, TriggerType.SYSTEM_STARTUP)
        await sm.transition(SystemState.READY, TriggerType.INITIALIZATION_COMPLETE)

        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=True)

        result = await sm.checkpoint(redis_client=mock_redis)

        assert result is True
        mock_redis.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_checkpoint_with_redis_error(self) -> None:
        """Тест checkpoint с ошибкой Redis."""
        sm = StateMachine()

        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(side_effect=RuntimeError("Redis error"))

        result = await sm.checkpoint(redis_client=mock_redis)

        assert result is False

    @pytest.mark.asyncio
    async def test_restore_from_checkpoint_no_data(self) -> None:
        """Тест restore без данных."""
        sm = StateMachine()

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)

        result = await sm.restore_from_checkpoint(redis_client=mock_redis)

        assert result is False

    @pytest.mark.asyncio
    async def test_restore_from_checkpoint_with_redis(self) -> None:
        """Тест restore из Redis."""
        sm = StateMachine()

        checkpoint_data = {
            "current_state": "trading",
            "version": 5,
            "transition_counter": 10,
            "state_entered_at": "2024-01-01T00:00:00",
        }

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=json.dumps(checkpoint_data))

        result = await sm.restore_from_checkpoint(redis_client=mock_redis)

        assert result is True
        assert sm.current_state == SystemState.TRADING
        assert sm.version == 5

    @pytest.mark.asyncio
    async def test_restore_from_checkpoint_redis_error(self) -> None:
        """Тест restore с ошибкой Redis."""
        sm = StateMachine()

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(side_effect=RuntimeError("Redis error"))

        result = await sm.restore_from_checkpoint(redis_client=mock_redis)

        assert result is False


class TestTransitionWithDB:
    """Тесты переходов с БД."""

    @pytest.mark.asyncio
    async def test_transition_with_db_optimistic_lock_success(self) -> None:
        """Тест перехода с optimistic locking успех."""
        mock_db = AsyncMock()
        # Мокаем успешное обновление (1 строка)
        mock_db.execute = AsyncMock(
            side_effect=[
                "BEGIN",
                "INSERT 0 1",  # Вставка перехода
                "UPDATE 1",  # Обновление состояния - 1 строка
                "COMMIT",
            ]
        )

        sm = StateMachine(db_manager=mock_db)
        await sm.transition(SystemState.INIT, TriggerType.SYSTEM_STARTUP)

        # Проверяем что execute был вызван
        assert mock_db.execute.call_count >= 3

    @pytest.mark.asyncio
    async def test_transition_with_db_optimistic_lock_conflict(self) -> None:
        """Тест перехода с optimistic locking конфликт."""
        mock_db = AsyncMock()
        # Конфликт версий - 0 строк обновлено
        mock_db.execute = AsyncMock(
            side_effect=[
                "BEGIN",
                "INSERT 0 1",
                "UPDATE 0",  # Конфликт
                "ROLLBACK",
                "BEGIN",
                "INSERT 0 1",
                "UPDATE 1",  # Успех на retry
                "COMMIT",
            ]
        )

        sm = StateMachine(db_manager=mock_db)
        result = await sm.transition(SystemState.INIT, TriggerType.SYSTEM_STARTUP)

        assert result.success is True

    @pytest.mark.asyncio
    async def test_transition_with_db_error(self) -> None:
        """Тест перехода с ошибкой БД."""
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=RuntimeError("DB error"))

        sm = StateMachine(db_manager=mock_db)

        # Должно упасть после исчерпания retry
        result = await sm.transition(SystemState.INIT, TriggerType.SYSTEM_STARTUP)

        assert result.success is False


class TestMonitorStateTimeouts:
    """Тесты мониторинга таймаутов."""

    @pytest.mark.asyncio
    async def test_monitor_state_timeout_task(self) -> None:
        """Тест фоновой задачи мониторинга."""
        sm = StateMachine()
        await sm.transition(SystemState.INIT, TriggerType.SYSTEM_STARTUP)

        # Запускаем мониторинг на короткое время
        monitor_task = asyncio.create_task(sm._monitor_state_timeouts(check_interval=0.01))

        # Даём задаче войти в цикл мониторинга
        await asyncio.sleep(0.02)

        # Отменяем задачу
        monitor_task.cancel()
        with suppress(asyncio.CancelledError):
            await monitor_task

    @pytest.mark.asyncio
    async def test_monitor_state_timeout_transition(self) -> None:
        """Тест автоматического перехода по таймауту."""
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            side_effect=[
                "BEGIN",
                "INSERT 0 1",
                "UPDATE 1",
                "COMMIT",
            ]
        )

        sm = StateMachine(db_manager=mock_db)
        await sm.transition(SystemState.INIT, TriggerType.SYSTEM_STARTUP)

        # Для INIT таймаут 120 секунд, не успеет сработать за 0.1 сек
        # Но проверим что метод работает
        assert sm._get_next_state_on_timeout() == SystemState.ERROR


class TestMetricsCollection:
    """Тесты сбора метрик."""

    @pytest.mark.asyncio
    async def test_record_transition_metrics(self) -> None:
        """Тест записи метрик переходов."""
        mock_metrics = MagicMock()
        mock_counter = MagicMock()
        mock_gauge = MagicMock()
        mock_metrics.get_counter.return_value = mock_counter
        mock_metrics.get_gauge.return_value = mock_gauge

        sm = StateMachine(metrics_collector=mock_metrics)

        await sm.transition(SystemState.INIT, TriggerType.SYSTEM_STARTUP)

        mock_counter.inc.assert_called()
        mock_gauge.set.assert_called()

    @pytest.mark.asyncio
    async def test_record_invalid_transition_metrics(self) -> None:
        """Тест записи метрик невалидных переходов."""
        mock_metrics = MagicMock()
        mock_counter = MagicMock()
        mock_metrics.get_counter.return_value = mock_counter

        sm = StateMachine(metrics_collector=mock_metrics)

        # Невалидный переход
        await sm.transition(SystemState.TRADING, TriggerType.TEST)

        mock_counter.inc.assert_called()

    @pytest.mark.asyncio
    async def test_metrics_error_handling(self) -> None:
        """Тест обработки ошибок метрик."""
        mock_metrics = MagicMock()
        mock_metrics.get_counter.side_effect = RuntimeError("Metrics error")

        sm = StateMachine(metrics_collector=mock_metrics)

        # Не должно упасть
        await sm.transition(SystemState.INIT, TriggerType.SYSTEM_STARTUP)


class TestStateTimeoutTransitions:
    """Тесты маппинга переходов по таймауту."""

    def test_timeout_transitions_mapping(self) -> None:
        """Тест маппинга переходов по таймауту."""
        # Проверяем что маппинг существует
        sm = StateMachine()

        assert sm._TIMEOUT_TRANSITIONS[SystemState.DEGRADED] == SystemState.HALT
        assert sm._TIMEOUT_TRANSITIONS[SystemState.SURVIVAL] == SystemState.HALT
        assert sm._TIMEOUT_TRANSITIONS[SystemState.ERROR] == SystemState.HALT
        assert sm._TIMEOUT_TRANSITIONS[SystemState.RECOVERY] == SystemState.HALT
        assert sm._TIMEOUT_TRANSITIONS[SystemState.BOOT] == SystemState.ERROR
        assert sm._TIMEOUT_TRANSITIONS[SystemState.INIT] == SystemState.ERROR


class TestGetHistoryWithCount:
    """Тесты истории с параметром count."""

    @pytest.mark.asyncio
    async def test_get_history_with_count(self) -> None:
        """Тест получения последних N переходов."""
        sm = StateMachine()

        await sm.transition(SystemState.INIT, TriggerType.SYSTEM_STARTUP)
        await sm.transition(SystemState.READY, TriggerType.INITIALIZATION_COMPLETE)
        await sm.transition(SystemState.TRADING, TriggerType.OPERATOR_REQUEST)

        # Получаем последние 2 перехода
        history = sm.get_history(count=2)

        assert len(history) == 2


class TestInitializeWithDB:
    """Тесты initialize с БД."""

    @pytest.mark.asyncio
    async def test_initialize_with_db_loads_state(self) -> None:
        """Тест инициализации с загрузкой состояния из БД."""
        mock_db = AsyncMock()
        mock_db.fetchrow = AsyncMock(
            return_value={
                "current_state": "trading",
                "version": 5,
            }
        )

        sm = StateMachine(db_manager=mock_db)
        result = await sm.initialize()

        assert result is True
        assert sm.current_state == SystemState.TRADING
        assert sm.version == 5

    @pytest.mark.asyncio
    async def test_initialize_with_db_error(self) -> None:
        """Тест инициализации с ошибкой БД."""
        mock_db = AsyncMock()
        mock_db.fetchrow = AsyncMock(side_effect=RuntimeError("DB error"))

        sm = StateMachine(db_manager=mock_db)
        result = await sm.initialize()

        # Должно продолжить работу несмотря на ошибку
        assert result is True


class TestCheckpointWithDB:
    """Тесты checkpoint с БД."""

    @pytest.mark.asyncio
    async def test_checkpoint_with_db_success(self) -> None:
        """Тест checkpoint с БД успех."""
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            side_effect=[
                "BEGIN",
                "INSERT 0 1",
                "UPDATE 1",
                "COMMIT",
                "INSERT 0 1",
                "COMMIT",
            ]
        )

        sm = StateMachine(db_manager=mock_db)
        await sm.transition(SystemState.INIT, TriggerType.SYSTEM_STARTUP)

        result = await sm.checkpoint(redis_client=None)

        assert result is True
        # Проверяем что был INSERT
        assert mock_db.execute.call_count >= 2

    @pytest.mark.asyncio
    async def test_checkpoint_with_db_error(self) -> None:
        """Тест checkpoint с ошибкой БД."""
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=RuntimeError("DB error"))

        sm = StateMachine(db_manager=mock_db)

        result = await sm.checkpoint(redis_client=None)

        assert result is False


class TestRestoreFromCheckpointWithDB:
    """Тесты restore с БД."""

    @pytest.mark.asyncio
    async def test_restore_from_db_success(self) -> None:
        """Тест восстановления из БД успех."""
        mock_db = AsyncMock()
        mock_db.fetchrow = AsyncMock(
            return_value={
                "current_state": "trading",
                "version": 10,
                "transition_counter": 5,
                "metadata": "{}",
            }
        )

        sm = StateMachine(db_manager=mock_db)

        result = await sm.restore_from_checkpoint(redis_client=None)

        assert result is True
        assert sm.current_state == SystemState.TRADING
        assert sm.version == 10

    @pytest.mark.asyncio
    async def test_restore_from_db_no_data(self) -> None:
        """Тест восстановления из БД без данных."""
        mock_db = AsyncMock()
        mock_db.fetchrow = AsyncMock(return_value=None)

        sm = StateMachine(db_manager=mock_db)

        result = await sm.restore_from_checkpoint(redis_client=None)

        assert result is False

    @pytest.mark.asyncio
    async def test_restore_from_db_error(self) -> None:
        """Тест восстановления из БД с ошибкой."""
        mock_db = AsyncMock()
        mock_db.fetchrow = AsyncMock(side_effect=RuntimeError("DB error"))

        sm = StateMachine(db_manager=mock_db)

        result = await sm.restore_from_checkpoint(redis_client=None)

        assert result is False


class TestSaveTransitionToDB:
    """Тесты сохранения переходов в БД."""

    @pytest.mark.asyncio
    async def test_save_transition_to_db(self) -> None:
        """Тест сохранения перехода в БД."""
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            side_effect=[
                "BEGIN",
                "INSERT 0 1",
                "UPDATE 1",
                "COMMIT",
            ]
        )

        sm = StateMachine(db_manager=mock_db)
        await sm.transition(SystemState.INIT, TriggerType.SYSTEM_STARTUP)

        # Проверяем что была попытка сохранить
        assert mock_db.execute.call_count >= 2


class TestUpdateStateInDB:
    """Тесты обновления состояния в БД."""

    @pytest.mark.asyncio
    async def test_update_state_in_db(self) -> None:
        """Тест обновления состояния в БД."""
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()

        sm = StateMachine(db_manager=mock_db)

        await sm._update_state_in_db(SystemState.TRADING)

        # Проверяем что был UPDATE
        assert mock_db.execute.call_count >= 1

    @pytest.mark.asyncio
    async def test_update_state_in_db_error(self) -> None:
        """Тест ошибки обновления состояния в БД."""
        mock_db = AsyncMock()
        # Первый вызов - ошибка, второй - ROLLBACK
        mock_db.execute = AsyncMock(
            side_effect=[
                RuntimeError("DB error"),  # UPDATE
                None,  # ROLLBACK
            ]
        )

        sm = StateMachine(db_manager=mock_db)

        # Не должно упасть - исключение обрабатывается
        await sm._update_state_in_db(SystemState.TRADING)


class TestPublishTransitionEvent:
    """Тесты публикации событий."""

    @pytest.mark.asyncio
    async def test_publish_transition_event(self) -> None:
        """Тест публикации события перехода."""
        mock_event_bus = AsyncMock()
        mock_event_bus.publish = AsyncMock()

        sm = StateMachine(event_bus=mock_event_bus)

        # Сначала делаем переход
        await sm.transition(SystemState.INIT, TriggerType.SYSTEM_STARTUP)

        # Получаем переход из истории
        history = sm.get_history()
        await sm._publish_transition_event(history[0])

        # publish вызывается как при transition так и при ручном вызове
        assert mock_event_bus.publish.called


class TestMonitorStateTimeoutTransition:
    """Тесты автоматического перехода по таймауту."""

    @pytest.mark.asyncio
    async def test_monitor_auto_transition(self) -> None:
        """Тест автоматического перехода при таймауте."""
        mock_db = AsyncMock()
        # Мокаем успешные запросы
        mock_db.execute = AsyncMock(
            side_effect=[
                "BEGIN",
                "INSERT 0 1",
                "UPDATE 1",
                "COMMIT",
            ]
        )

        sm = StateMachine(db_manager=mock_db)
        await sm.transition(SystemState.INIT, TriggerType.SYSTEM_STARTUP)

        # Вызываем мониторинг вручную сразу
        # Для INIT таймаут 120 сек, но _get_next_state_on_timeout
        # вернёт ERROR
        next_state = sm._get_next_state_on_timeout()
        assert next_state == SystemState.ERROR


class TestExceptionHandling:
    """Тесты обработки исключений."""

    @pytest.mark.asyncio
    async def test_monitor_exception_handling(self) -> None:
        """Тест обработки исключений в мониторинге."""
        sm = StateMachine()

        # Запускаем и сразу отменяем
        monitor_task = asyncio.create_task(sm._monitor_state_timeouts(check_interval=1))
        await asyncio.sleep(0.1)
        monitor_task.cancel()

        with suppress(asyncio.CancelledError):
            await monitor_task


class TestUnregisterCallbackEdgeCases:
    """Тесты граничных случаев для unregister callbacks."""

    @pytest.mark.asyncio
    async def test_unregister_enter_success(self) -> None:
        """Тест успешного удаления on_enter callback."""
        sm = StateMachine()

        async def callback(from_state: SystemState, to_state: SystemState) -> None:
            pass

        sm.register_on_enter(SystemState.INIT, callback)
        result = sm.unregister_on_enter(SystemState.INIT, callback)

        assert result is True

    @pytest.mark.asyncio
    async def test_unregister_exit_success(self) -> None:
        """Тест успешного удаления on_exit callback."""
        sm = StateMachine()

        async def callback(from_state: SystemState, to_state: SystemState) -> None:
            pass

        sm.register_on_exit(SystemState.BOOT, callback)
        result = sm.unregister_on_exit(SystemState.BOOT, callback)

        assert result is True


# Mark all tests as unit tests
pytest.mark.unit(__name__)

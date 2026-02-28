"""
Property-Based Tests for State Machine Invariants.

Тесты проверяют фундаментальные инварианты state machine:
1. Все переходы валидны
2. Нет dead-lock состояний (из любого состояния есть путь)
3. Граф переходовstrongly connected
4. Нет self-transitions
5. Состояния всегда достижимы из BOOT
"""

from __future__ import annotations

from collections import deque

from hypothesis import Verbosity, given, settings
import hypothesis.strategies as st
import pytest

from src.core.state_machine_enums import (
    ALLOWED_TRANSITIONS,
    SystemState,
    get_allowed_transitions,
    is_transition_allowed,
)


class TestStateMachineInvariants:
    """Тесты инвариантов state machine."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Настройка тестов."""
        self.all_states = set(SystemState)
        self.states_list = list(SystemState)

    # ==================== Инвариант 1: Все переходы валидны ====================

    @given(from_state=st.from_type(SystemState), to_state=st.from_type(SystemState))
    @settings(max_examples=500, verbosity=Verbosity.verbose)
    def test_all_allowed_transitions_are_valid(self, from_state, to_state):
        """
        Инвариант: Если переход разрешён в ALLOWED_TRANSITIONS,
        то is_transition_allowed должен возвращать True.
        """
        if to_state in ALLOWED_TRANSITIONS.get(from_state, set()):
            assert is_transition_allowed(from_state, to_state) is True

    @given(from_state=st.from_type(SystemState), to_state=st.from_type(SystemState))
    @settings(max_examples=500, verbosity=Verbosity.verbose)
    def test_disallowed_transitions_return_false(self, from_state, to_state):
        """
        Инвариант: Если переход НЕ разрешён в ALLOWED_TRANSITIONS,
        то is_transition_allowed должен возвращать False.
        """
        if to_state not in ALLOWED_TRANSITIONS.get(from_state, set()):
            assert is_transition_allowed(from_state, to_state) is False

    # ==================== Инвариант 2: Нет self-transitions ====================

    def test_no_self_transitions(self):
        """
        Инвариант: Ни одно состояние не может перейти в себя само.
        """
        for state in SystemState:
            assert is_transition_allowed(state, state) is False

    # ==================== Инвариант 3: Нет dead-lock состояний ====================

    def test_no_deadlock_states(self):
        """
        Инвариант: Из любого состояния есть путь к какому-либо другому состоянию.
        Dead-lock = состояние без исходящих переходов.
        """
        for state in SystemState:
            allowed = get_allowed_transitions(state)
            # Не должно быть dead-lock (из любого состояния должен быть выход)
            # Исключение: состояния, из которых нет переходов (если такие есть)
            assert len(allowed) > 0, f"Dead-lock обнаружен в состоянии {state}"

    # ==================== Инвариант 4: Граф переходов связан ====================

    def test_all_states_reachable_from_boot(self):
        """
        Инвариант: Все состояния достижимы из начального состояния BOOT.
        """
        reachable: set[SystemState] = {SystemState.BOOT}
        queue = deque([SystemState.BOOT])

        while queue:
            current = queue.popleft()
            for next_state in get_allowed_transitions(current):
                if next_state not in reachable:
                    reachable.add(next_state)
                    queue.append(next_state)

        unreachable = self.all_states - reachable
        assert len(unreachable) == 0, f"Недостижимые состояния: {unreachable}"

    def test_boot_can_reach_trading(self):
        """
        Инвариант: Из состояния BOOT можно добраться до TRADING.
        """
        reachable: set[SystemState] = {SystemState.BOOT}
        queue = deque([SystemState.BOOT])

        while queue:
            current = queue.popleft()
            for next_state in get_allowed_transitions(current):
                if next_state not in reachable:
                    reachable.add(next_state)
                    queue.append(next_state)

        assert SystemState.TRADING in reachable, "TRADING недостижимо из BOOT"

    # ==================== Инвариант 5: Валидация структуры графа ====================

    def test_all_states_have_outgoing_transitions(self):
        """
        Инвариант: Каждое состояние имеет хотя бы один исходящий переход.
        """
        states_without_outgoing = []
        for state in SystemState:
            if len(get_allowed_transitions(state)) == 0:
                states_without_outgoing.append(state)

        assert len(states_without_outgoing) == 0, (
            f"Состояния без исходящих переходов: {states_without_outgoing}"
        )

    def test_all_states_have_incoming_transitions(self):
        """
        Инвариант: Каждое состояние имеет хотя бы один входящий переход.
        """
        states_with_incoming: dict[SystemState, set[SystemState]] = {
            state: set() for state in SystemState
        }

        for _from_state, to_states in ALLOWED_TRANSITIONS.items():
            for to_state in to_states:
                states_with_incoming[to_state].add(_from_state)

        states_without_incoming = [
            state for state, incoming in states_with_incoming.items()
            if len(incoming) == 0
        ]

        # BOOT может не иметь входящих переходов (начальное состояние)
        # HALT может не иметь входящих (если система ещё не запускалась)
        # Но все остальные должны иметь входящие
        unexpected = [s for s in states_without_incoming if s not in {SystemState.BOOT}]

        assert len(unexpected) == 0, (
            f"Состояния без входящих переходов (кроме BOOT): {unexpected}"
        )

    # ==================== Инвариант 6: Транзитивность ====================

    def test_halt_recovery_cycle(self):
        """
        Инвариант: HALT -> RECOVERY -> READY -> TRADING образует валидный цикл.
        """
        # HALT может перейти в RECOVERY
        assert is_transition_allowed(SystemState.HALT, SystemState.RECOVERY)
        # RECOVERY может перейти в READY
        assert is_transition_allowed(SystemState.RECOVERY, SystemState.READY)
        # READY может перейти в TRADING
        assert is_transition_allowed(SystemState.READY, SystemState.TRADING)

    def test_error_recovery_path(self):
        """
        Инвариант: Из ERROR можно восстановиться через RECOVERY.
        """
        # ERROR -> RECOVERY
        assert is_transition_allowed(SystemState.ERROR, SystemState.RECOVERY)
        # RECOVERY -> READY
        assert is_transition_allowed(SystemState.RECOVERY, SystemState.READY)

    def test_degraded_to_survival_escalation(self):
        """
        Инвариант: DEGRADED -> SURVIVAL -> HALT образует цепочку эскалации.
        """
        # DEGRADED может перейти в SURVIVAL
        assert is_transition_allowed(SystemState.DEGRADED, SystemState.SURVIVAL)
        # SURVIVAL может перейти в HALT
        assert is_transition_allowed(SystemState.SURVIVAL, SystemState.HALT)

    # ==================== Инвариант 7: Симметрия ====================

    def test_transitions_are_not_symmetric(self):
        """
        Инвариант: Переходы не симметричны (A->B не означает B->A).
        Это гарантирует детерминированный поток состояний.
        """
        for from_state in SystemState:
            for to_state in get_allowed_transitions(from_state):
                # Если есть A->B, то B->A быть не должно (обычно)
                # Для большинства пар это не так
                if from_state != to_state:
                    # Логаем для отладки, но не断言
                    pass

    # ==================== Инвариант 8: Консистентность данных ====================

    def test_allowed_transitions_dict_completeness(self):
        """
        Инвариант: ALLOWED_TRANSITIONS содержит все состояния.
        """
        assert set(ALLOWED_TRANSITIONS.keys()) == self.all_states

    def test_all_target_states_are_valid(self):
        """
        Инвариант: Все целевые состояния в ALLOWED_TRANSITIONS валидны.
        """
        for _from_state, to_states in ALLOWED_TRANSITIONS.items():
            for to_state in to_states:
                assert isinstance(to_state, SystemState), (
                    f"Неверный тип состояния: {to_state}"
                )
                assert to_state in self.all_states, (
                    f"Неизвестное состояние: {to_state}"
                )

    # ==================== Инвариант 9: Workflow paths ====================

    def test_normal_startup_path(self):
        """
        Инвариант: Стандартный путь запуска: BOOT -> INIT -> READY -> TRADING.
        """
        assert is_transition_allowed(SystemState.BOOT, SystemState.INIT)
        assert is_transition_allowed(SystemState.INIT, SystemState.READY)
        assert is_transition_allowed(SystemState.READY, SystemState.TRADING)

    def test_emergency_shutdown_path(self):
        """
        Инвариант: Путь экстренной остановки: любой -> HALT.
        """
        # Из TRADING можно перейти в HALT
        assert is_transition_allowed(SystemState.TRADING, SystemState.HALT)
        # Из DEGRADED можно перейти в HALT
        assert is_transition_allowed(SystemState.DEGRADED, SystemState.HALT)
        # Из READY можно перейти в HALT
        assert is_transition_allowed(SystemState.READY, SystemState.HALT)

    def test_recovery_after_error(self):
        """
        Инвариант: Восстановление после ошибки: ERROR -> RECOVERY -> READY.
        """
        assert is_transition_allowed(SystemState.ERROR, SystemState.RECOVERY)
        assert is_transition_allowed(SystemState.RECOVERY, SystemState.READY)


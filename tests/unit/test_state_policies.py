"""
Тесты для State Policies.

Проверяет:
- can_open_positions()
- can_increase_size()
- can_place_orders()
- get_risk_multiplier()
- get_max_positions()
- get_max_order_size()
- is_short_selling_allowed()
- requires_manual_approval()
- get_state_policy_description()
"""

import pytest
from src.core.state_machine_enums import (
    SystemState,
    MAX_STATE_TIMES,
    STATE_POLICIES,
    get_state_policy,
)


class TestStatePolicies:
    """Тесты для State Policies."""

    @pytest.mark.parametrize(
        "state,expected",
        [
            (SystemState.BOOT, False),
            (SystemState.INIT, False),
            (SystemState.READY, False),
            (SystemState.TRADING, True),
            (SystemState.RISK_REDUCTION, False),
            (SystemState.DEGRADED, False),
            (SystemState.SURVIVAL, False),
            (SystemState.ERROR, False),
            (SystemState.HALT, False),
            (SystemState.RECOVERY, False),
        ],
    )
    def test_can_open_positions(self, state, expected):
        """Проверить can_open_positions для каждого состояния."""
        policy = get_state_policy(state)
        assert policy.allow_new_positions == expected

    @pytest.mark.parametrize(
        "state,expected",
        [
            (SystemState.BOOT, False),
            (SystemState.INIT, False),
            (SystemState.READY, False),
            (SystemState.TRADING, True),
            (SystemState.RISK_REDUCTION, False),
            (SystemState.DEGRADED, False),
            (SystemState.SURVIVAL, False),
            (SystemState.ERROR, False),
            (SystemState.HALT, False),
            (SystemState.RECOVERY, False),
        ],
    )
    def test_can_increase_size(self, state, expected):
        """Проверить can_increase_size для каждого состояния."""
        policy = get_state_policy(state)
        assert policy.allow_increase_size == expected

    @pytest.mark.parametrize(
        "state,expected",
        [
            (SystemState.BOOT, False),
            (SystemState.INIT, False),
            (SystemState.READY, False),
            (SystemState.TRADING, True),
            (SystemState.RISK_REDUCTION, True),  # Только закрытие
            (SystemState.DEGRADED, True),  # Только закрытие
            (SystemState.SURVIVAL, True),  # Только закрытие
            (SystemState.ERROR, False),
            (SystemState.HALT, False),
            (SystemState.RECOVERY, False),
        ],
    )
    def test_can_place_orders(self, state, expected):
        """Проверить can_place_orders для каждого состояния."""
        policy = get_state_policy(state)
        assert policy.allow_new_orders == expected

    @pytest.mark.parametrize(
        "state,expected",
        [
            (SystemState.BOOT, 0.0),
            (SystemState.INIT, 0.0),
            (SystemState.READY, 0.0),
            (SystemState.TRADING, 1.0),
            (SystemState.RISK_REDUCTION, 0.25),
            (SystemState.DEGRADED, 0.5),
            (SystemState.SURVIVAL, 0.1),
            (SystemState.ERROR, 0.0),
            (SystemState.HALT, 0.0),
            (SystemState.RECOVERY, 0.0),
        ],
    )
    def test_risk_multiplier(self, state, expected):
        """Проверить risk_multiplier для каждого состояния."""
        policy = get_state_policy(state)
        assert policy.risk_multiplier == expected

    @pytest.mark.parametrize(
        "state,expected",
        [
            (SystemState.BOOT, 0),
            (SystemState.INIT, 0),
            (SystemState.READY, 0),
            (SystemState.TRADING, 100),
            (SystemState.RISK_REDUCTION, 20),
            (SystemState.DEGRADED, 50),
            (SystemState.SURVIVAL, 0),
            (SystemState.ERROR, 0),
            (SystemState.HALT, 0),
            (SystemState.RECOVERY, 0),
        ],
    )
    def test_max_positions(self, state, expected):
        """Проверить max_positions для каждого состояния."""
        policy = get_state_policy(state)
        assert policy.max_positions == expected

    @pytest.mark.parametrize(
        "state,expected",
        [
            (SystemState.BOOT, 0.0),
            (SystemState.INIT, 0.0),
            (SystemState.READY, 0.0),
            (SystemState.TRADING, 0.1),
            (SystemState.RISK_REDUCTION, 0.02),
            (SystemState.DEGRADED, 0.05),
            (SystemState.SURVIVAL, 0.01),
            (SystemState.ERROR, 0.0),
            (SystemState.HALT, 0.0),
            (SystemState.RECOVERY, 0.0),
        ],
    )
    def test_max_order_size(self, state, expected):
        """Проверить max_order_size для каждого состояния."""
        policy = get_state_policy(state)
        assert policy.max_order_size == expected

    @pytest.mark.parametrize(
        "state,expected",
        [
            (SystemState.BOOT, False),
            (SystemState.INIT, False),
            (SystemState.READY, False),
            (SystemState.TRADING, True),
            (SystemState.RISK_REDUCTION, False),
            (SystemState.DEGRADED, False),
            (SystemState.SURVIVAL, False),
            (SystemState.ERROR, False),
            (SystemState.HALT, False),
            (SystemState.RECOVERY, False),
        ],
    )
    def test_short_selling_allowed(self, state, expected):
        """Проверить is_short_selling_allowed для каждого состояния."""
        policy = get_state_policy(state)
        assert policy.allow_short_selling == expected

    @pytest.mark.parametrize(
        "state,expected",
        [
            (SystemState.BOOT, True),
            (SystemState.INIT, True),
            (SystemState.READY, True),
            (SystemState.TRADING, False),
            (SystemState.RISK_REDUCTION, True),
            (SystemState.DEGRADED, True),
            (SystemState.SURVIVAL, True),
            (SystemState.ERROR, True),
            (SystemState.HALT, True),
            (SystemState.RECOVERY, True),
        ],
    )
    def test_requires_manual_approval(self, state, expected):
        """Проверить requires_manual_approval для каждого состояния."""
        policy = get_state_policy(state)
        assert policy.require_manual_approval == expected


class TestStateTimeoutTransitions:
    """Тесты для автоматических переходов по таймауту."""

    @pytest.mark.parametrize(
        "state,expected_timeout",
        [
            (SystemState.BOOT, 60),
            (SystemState.INIT, 120),
            (SystemState.READY, 3600),
            (SystemState.TRADING, None),
            (SystemState.RISK_REDUCTION, 1800),
            (SystemState.DEGRADED, 3600),
            (SystemState.SURVIVAL, 1800),
            (SystemState.ERROR, 300),
            (SystemState.HALT, None),
            (SystemState.RECOVERY, 600),
        ],
    )
    def test_max_state_times(self, state, expected_timeout):
        """Проверить MAX_STATE_TIMES для каждого состояния."""
        timeout = MAX_STATE_TIMES.get(state)
        if expected_timeout is None:
            assert timeout == -1  # Без ограничений
        else:
            assert timeout == expected_timeout

    def test_all_states_have_policy(self):
        """Проверить что все состояния имеют политику."""
        for state in SystemState:
            assert state in STATE_POLICIES
            policy = STATE_POLICIES[state]
            assert policy is not None
            assert isinstance(policy.allow_new_positions, bool)
            assert isinstance(policy.risk_multiplier, float)
            assert isinstance(policy.max_positions, int)

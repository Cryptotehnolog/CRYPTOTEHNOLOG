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

from cryptotechnolog.config import reload_settings, update_settings
from cryptotechnolog.core.state_machine_enums import (
    MAX_STATE_TIMES,
    STATE_POLICIES,
    SystemState,
    get_state_policy,
    get_state_timeout_limit,
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


def test_get_state_policy_reads_settings_overrides_for_working_modes() -> None:
    try:
        update_settings({
            "system_trading_risk_multiplier": 0.85,
            "system_degraded_max_positions": 42,
            "system_risk_reduction_max_order_size": 0.015,
            "system_survival_max_positions": 1,
        })

        assert get_state_policy(SystemState.TRADING).risk_multiplier == 0.85
        assert get_state_policy(SystemState.DEGRADED).max_positions == 42
        assert get_state_policy(SystemState.RISK_REDUCTION).max_order_size == 0.015
        assert get_state_policy(SystemState.SURVIVAL).max_positions == 1
    finally:
        reload_settings()


def test_get_state_timeout_limit_reads_settings_overrides_for_configured_states() -> None:
    try:
        update_settings({
            "system_boot_max_seconds": 75,
            "system_init_max_seconds": 150,
            "system_ready_max_seconds": 4200,
            "system_risk_reduction_max_seconds": 2100,
            "system_degraded_max_seconds": 3900,
            "system_survival_max_seconds": 1950,
            "system_error_max_seconds": 420,
            "system_recovery_max_seconds": 720,
        })

        assert get_state_timeout_limit(SystemState.BOOT) == 75
        assert get_state_timeout_limit(SystemState.INIT) == 150
        assert get_state_timeout_limit(SystemState.READY) == 4200
        assert get_state_timeout_limit(SystemState.RISK_REDUCTION) == 2100
        assert get_state_timeout_limit(SystemState.DEGRADED) == 3900
        assert get_state_timeout_limit(SystemState.SURVIVAL) == 1950
        assert get_state_timeout_limit(SystemState.ERROR) == 420
        assert get_state_timeout_limit(SystemState.RECOVERY) == 720
        assert get_state_timeout_limit(SystemState.TRADING) is None
        assert get_state_timeout_limit(SystemState.HALT) is None
    finally:
        reload_settings()

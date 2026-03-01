"""
Тесты для новых Triggers v4.4.

Проверяет:
- LOW_UNIVERSE_QUALITY
- STABLE_RECOVERED
- RISK_BREACH
- FAST_VELOCITY_ALERT
- SLOW_VELOCITY_ALERT
- STATE_TIMEOUT_EXCEEDED
"""


import pytest

from src.core.state_machine import StateMachine
from src.core.state_machine_enums import (
    SystemState,
    TriggerType,
    is_transition_allowed,
)


class TestNewTriggers:
    """Тесты для новых triggers."""

    @pytest.mark.asyncio
    async def test_risk_breach_trigger(self):
        """Проверить переход RISK_BREACH: TRADING → RISK_REDUCTION."""
        sm = StateMachine()
        await sm.initialize()
        # BOOT → INIT → READY → TRADING
        await sm.transition(SystemState.INIT, trigger="test")
        await sm.transition(SystemState.READY, trigger="test")
        await sm.transition(SystemState.TRADING, trigger="test")

        # Проверяем что можем перейти в RISK_REDUCTION
        assert is_transition_allowed(SystemState.TRADING, SystemState.RISK_REDUCTION)

        # Выполняем переход с trigger RISK_BREACH
        result = await sm.transition(
            SystemState.RISK_REDUCTION,
            trigger=TriggerType.RISK_BREACH.value,
        )

        assert result.success
        assert sm.current_state == SystemState.RISK_REDUCTION

    @pytest.mark.asyncio
    async def test_low_universe_quality_trigger(self):
        """Проверить переход LOW_UNIVERSE_QUALITY: TRADING → DEGRADED."""
        sm = StateMachine()
        await sm.initialize()
        await sm.transition(SystemState.INIT, trigger="test")
        await sm.transition(SystemState.READY, trigger="test")
        await sm.transition(SystemState.TRADING, trigger="test")

        assert is_transition_allowed(SystemState.TRADING, SystemState.DEGRADED)

        result = await sm.transition(
            SystemState.DEGRADED,
            trigger=TriggerType.LOW_UNIVERSE_QUALITY.value,
        )

        assert result.success
        assert sm.current_state == SystemState.DEGRADED

    @pytest.mark.asyncio
    async def test_fast_velocity_alert_trigger(self):
        """Проверить переход FAST_VELOCITY_ALERT: TRADING → DEGRADED."""
        sm = StateMachine()
        await sm.initialize()
        await sm.transition(SystemState.INIT, trigger="test")
        await sm.transition(SystemState.READY, trigger="test")
        await sm.transition(SystemState.TRADING, trigger="test")

        result = await sm.transition(
            SystemState.DEGRADED,
            trigger=TriggerType.FAST_VELOCITY_ALERT.value,
        )

        assert result.success

    @pytest.mark.asyncio
    async def test_stable_recovered_trigger(self):
        """Проверить переход STABLE_RECOVERED: DEGRADED → TRADING."""
        sm = StateMachine()
        await sm.initialize()
        await sm.transition(SystemState.INIT, trigger="test")
        await sm.transition(SystemState.READY, trigger="test")
        await sm.transition(SystemState.TRADING, trigger="test")
        await sm.transition(SystemState.DEGRADED, trigger="test")

        assert is_transition_allowed(SystemState.DEGRADED, SystemState.TRADING)

        result = await sm.transition(
            SystemState.TRADING,
            trigger=TriggerType.STABLE_RECOVERED.value,
        )

        assert result.success
        assert sm.current_state == SystemState.TRADING

    @pytest.mark.asyncio
    async def test_slow_velocity_alert_trigger(self):
        """Проверить переход SLOW_VELOCITY_ALERT: DEGRADED → RISK_REDUCTION."""
        sm = StateMachine()
        await sm.initialize()
        await sm.transition(SystemState.INIT, trigger="test")
        await sm.transition(SystemState.READY, trigger="test")
        await sm.transition(SystemState.TRADING, trigger="test")
        await sm.transition(SystemState.DEGRADED, trigger="test")

        assert is_transition_allowed(SystemState.DEGRADED, SystemState.RISK_REDUCTION)

        result = await sm.transition(
            SystemState.RISK_REDUCTION,
            trigger=TriggerType.SLOW_VELOCITY_ALERT.value,
        )

        assert result.success
        assert sm.current_state == SystemState.RISK_REDUCTION


class TestRiskReductionState:
    """Тесты для состояния RISK_REDUCTION."""

    @pytest.mark.asyncio
    async def test_risk_reduction_state_transitions(self):
        """Проверить допустимые переходы из RISK_REDUCTION."""
        sm = StateMachine()
        await sm.initialize()
        await sm.transition(SystemState.INIT, trigger="test")
        await sm.transition(SystemState.READY, trigger="test")
        await sm.transition(SystemState.TRADING, trigger="test")
        await sm.transition(
            SystemState.RISK_REDUCTION,
            trigger=TriggerType.RISK_BREACH.value,
        )

        # Из RISK_REDUCTION можно перейти в разные состояния
        assert is_transition_allowed(SystemState.RISK_REDUCTION, SystemState.TRADING)
        assert is_transition_allowed(SystemState.RISK_REDUCTION, SystemState.DEGRADED)
        assert is_transition_allowed(SystemState.RISK_REDUCTION, SystemState.SURVIVAL)
        assert is_transition_allowed(SystemState.RISK_REDUCTION, SystemState.HALT)

    @pytest.mark.asyncio
    async def test_risk_reduction_policies(self):
        """Проверить политики для RISK_REDUCTION."""
        sm = StateMachine()
        await sm.initialize()
        await sm.transition(SystemState.INIT, trigger="test")
        await sm.transition(SystemState.READY, trigger="test")
        await sm.transition(SystemState.TRADING, trigger="test")
        await sm.transition(
            SystemState.RISK_REDUCTION,
            trigger=TriggerType.RISK_BREACH.value,
        )

        # В RISK_REDUCTION нельзя открывать новые позиции
        assert sm.can_open_positions() is False
        assert sm.can_place_orders() is True  # Закрытие разрешено

        # Риск снижен
        assert sm.get_risk_multiplier() == 0.25
        assert sm.get_max_positions() == 20

    @pytest.mark.asyncio
    async def test_risk_reduction_timeout(self):
        """Проверить таймаут для RISK_REDUCTION."""
        sm = StateMachine()
        await sm.initialize()
        await sm.transition(SystemState.INIT, trigger="test")
        await sm.transition(SystemState.READY, trigger="test")
        await sm.transition(SystemState.TRADING, trigger="test")
        await sm.transition(
            SystemState.RISK_REDUCTION,
            trigger=TriggerType.RISK_BREACH.value,
        )

        timeout = sm.get_state_timeout()
        assert timeout == 1800  # 30 минут


class TestStateTimeoutExceeded:
    """Тесты для trigger STATE_TIMEOUT_EXCEEDED."""

    @pytest.mark.asyncio
    async def test_state_timeout_exceeded_trigger(self):
        """Проверить trigger STATE_TIMEOUT_EXCEEDED."""
        sm = StateMachine()
        await sm.initialize()
        await sm.transition(SystemState.INIT, trigger="test")
        await sm.transition(SystemState.READY, trigger="test")
        await sm.transition(SystemState.TRADING, trigger="test")
        await sm.transition(SystemState.DEGRADED, trigger="test")

        result = await sm.transition(
            SystemState.HALT,
            trigger=TriggerType.STATE_TIMEOUT_EXCEEDED.value,
        )

        assert result.success

    def test_trigger_type_values(self):
        """Проверить что все новые trigger types имеют значения."""
        assert TriggerType.LOW_UNIVERSE_QUALITY.value == "low_universe_quality"
        assert TriggerType.STABLE_RECOVERED.value == "stable_recovered"
        assert TriggerType.RISK_BREACH.value == "risk_breach"
        assert TriggerType.FAST_VELOCITY_ALERT.value == "fast_velocity_alert"
        assert TriggerType.SLOW_VELOCITY_ALERT.value == "slow_velocity_alert"
        assert TriggerType.STATE_TIMEOUT_EXCEEDED.value == "state_timeout_exceeded"

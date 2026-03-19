from decimal import Decimal

import pytest

from cryptotechnolog.risk.drawdown_monitor import (
    DrawdownLevel,
    DrawdownMonitor,
    DrawdownMonitorConfig,
    DrawdownMonitorError,
)


class TestDrawdownMonitor:
    """Тесты доменного мониторинга просадки."""

    def setup_method(self) -> None:
        self.monitor = DrawdownMonitor(starting_equity=Decimal("10000"))

    def test_calculates_current_drawdown_against_peak_equity(self) -> None:
        """Просадка должна считаться от peak equity через Decimal."""
        self.monitor.update_equity(Decimal("12000"))
        assessment = self.monitor.update_equity(Decimal("10800"))

        assert assessment.peak_equity == Decimal("12000")
        assert assessment.current_equity == Decimal("10800")
        assert assessment.drawdown_percent == Decimal("0.10")

    def test_returns_soft_drawdown_warning(self) -> None:
        """Превышение soft limit должно давать доменный warning-результат."""
        assessment = self.monitor.update_equity(Decimal("9400"))

        assert assessment.level is DrawdownLevel.SOFT
        assert assessment.soft_breached is True
        assert assessment.hard_breached is False
        assert "мягкий лимит" in assessment.reason

    def test_returns_hard_drawdown_trigger(self) -> None:
        """Превышение hard limit должно иметь приоритет над soft warning."""
        assessment = self.monitor.update_equity(Decimal("8900"))

        assert assessment.level is DrawdownLevel.HARD
        assert assessment.soft_breached is True
        assert assessment.hard_breached is True
        assert "жёсткий лимит" in assessment.reason

    def test_triggers_velocity_drawdown_from_trade_window(self) -> None:
        """Сумма убытков в окне сделок должна активировать velocity drawdown."""
        self.monitor.record_trade_result(Decimal("-0.8"))
        self.monitor.record_trade_result(Decimal("0.4"))
        assessment = self.monitor.record_trade_result(Decimal("-1.3"))

        assert assessment.level is DrawdownLevel.VELOCITY
        assert assessment.velocity_triggered is True
        assert assessment.recent_losses_r == Decimal("2.1")

    def test_velocity_window_uses_only_configured_number_of_trades(self) -> None:
        """Velocity drawdown должен учитывать только последние N сделок."""
        monitor = DrawdownMonitor(
            starting_equity=Decimal("10000"),
            config=DrawdownMonitorConfig(
                soft_limit=Decimal("0.05"),
                hard_limit=Decimal("0.10"),
                velocity_loss_r=Decimal("2.0"),
                velocity_window_trades=3,
            ),
        )

        monitor.record_trade_result(Decimal("-1.2"))
        monitor.record_trade_result(Decimal("-0.5"))
        monitor.record_trade_result(Decimal("0.1"))
        assessment = monitor.record_trade_result(Decimal("-0.9"))

        assert assessment.recent_losses_r == Decimal("1.4")
        assert assessment.velocity_triggered is False

    def test_recovers_to_normal_when_limits_are_not_breached(self) -> None:
        """После восстановления equity доменный уровень должен вернуться в NORMAL."""
        self.monitor.update_equity(Decimal("9400"))
        assessment = self.monitor.update_equity(Decimal("10000"))

        assert assessment.level is DrawdownLevel.NORMAL
        assert assessment.drawdown_percent == Decimal("0")

    def test_rejects_non_positive_equity(self) -> None:
        """Капитал должен быть положительным на всём жизненном цикле monitor."""
        with pytest.raises(DrawdownMonitorError, match="положительным"):
            DrawdownMonitor(starting_equity=Decimal("0"))

        with pytest.raises(DrawdownMonitorError, match="положительным"):
            self.monitor.update_equity(Decimal("-1"))

    def test_assess_equity_is_read_only_for_pre_trade_path(self) -> None:
        """Pre-trade оценка equity не должна мутировать внутреннее состояние monitor."""
        self.monitor.update_equity(Decimal("12000"))

        assessment = self.monitor.assess_equity(Decimal("10800"))

        assert assessment.peak_equity == Decimal("12000")
        assert assessment.current_equity == Decimal("10800")
        assert assessment.drawdown_percent == Decimal("0.10")
        assert self.monitor.get_current_equity() == Decimal("12000")
        assert self.monitor.get_peak_equity() == Decimal("12000")

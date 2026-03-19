"""
Доменный монитор просадки и velocity drawdown.

Модуль не зависит от Event Bus, БД или orchestration.
Он только считает состояние риска капитала и возвращает доменный результат.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class DrawdownMonitorError(Exception):
    """Базовая ошибка DrawdownMonitor."""


class DrawdownLevel(StrEnum):
    """Уровни реакции на просадку."""

    NORMAL = "normal"
    SOFT = "soft"
    HARD = "hard"
    VELOCITY = "velocity"


@dataclass(slots=True, frozen=True)
class DrawdownMonitorConfig:
    """
    Конфигурация доменного мониторинга просадки.

    Значения задаются как доли капитала:
    - 0.05 = 5%
    - 0.10 = 10%
    """

    soft_limit: Decimal = Decimal("0.05")
    hard_limit: Decimal = Decimal("0.10")
    velocity_loss_r: Decimal = Decimal("2.0")
    velocity_window_trades: int = 10


@dataclass(slots=True, frozen=True)
class DrawdownAssessment:
    """
    Доменный результат оценки просадки.

    Это foundation для будущих решений `RiskEngine`:
    - warning на soft limit
    - stop/reject на hard limit
    - future velocity killswitch
    """

    current_equity: Decimal
    peak_equity: Decimal
    drawdown_percent: Decimal
    soft_limit: Decimal
    hard_limit: Decimal
    velocity_loss_r: Decimal
    velocity_window_trades: int
    recent_losses_r: Decimal
    level: DrawdownLevel
    soft_breached: bool
    hard_breached: bool
    velocity_triggered: bool
    reason: str


class DrawdownMonitor:
    """
    Монитор просадки капитала.

    Содержит два независимых доменных контура:
    - equity drawdown относительно peak equity;
    - velocity drawdown по окну последних сделок в R.
    """

    def __init__(
        self,
        *,
        starting_equity: Decimal,
        config: DrawdownMonitorConfig | None = None,
    ) -> None:
        """Инициализировать монитор просадки от стартового капитала."""
        if starting_equity <= 0:
            raise DrawdownMonitorError("Стартовый капитал должен быть положительным")

        self._config = config or DrawdownMonitorConfig()
        self._current_equity = starting_equity
        self._peak_equity = starting_equity
        self._recent_trade_results_r: deque[Decimal] = deque(
            maxlen=self._config.velocity_window_trades
        )

    def update_equity(self, current_equity: Decimal) -> DrawdownAssessment:
        """
        Обновить текущее значение капитала и вернуть оценку просадки.

        Raises:
            DrawdownMonitorError: Если капитал невалиден.
        """
        if current_equity <= 0:
            raise DrawdownMonitorError("Текущий капитал должен быть положительным")

        self._current_equity = current_equity
        self._peak_equity = max(self._peak_equity, current_equity)

        return self.assess()

    def assess_equity(self, current_equity: Decimal) -> DrawdownAssessment:
        """
        Оценить drawdown для переданного equity без мутации внутреннего состояния.

        Этот путь нужен для pre-trade checks, чтобы не было двойного учёта
        equity между read-only gate и event-driven/runtime обновлениями.
        """
        if current_equity <= 0:
            raise DrawdownMonitorError("Текущий капитал должен быть положительным")

        peak_equity = max(self._peak_equity, current_equity)

        return self._build_assessment(
            current_equity=current_equity,
            peak_equity=peak_equity,
        )

    def record_trade_result(self, realized_pnl_r: Decimal) -> DrawdownAssessment:
        """Учесть результат сделки для velocity drawdown и вернуть актуальную оценку."""
        self._recent_trade_results_r.append(realized_pnl_r)
        return self.assess()

    def assess(self) -> DrawdownAssessment:
        """Собрать доменную оценку drawdown и velocity состояния."""
        return self._build_assessment(
            current_equity=self._current_equity,
            peak_equity=self._peak_equity,
        )

    def _build_assessment(
        self,
        *,
        current_equity: Decimal,
        peak_equity: Decimal,
    ) -> DrawdownAssessment:
        """Собрать оценку drawdown/velocity для заданной пары equity/peak."""
        if current_equity >= peak_equity:
            drawdown_percent = Decimal("0")
        else:
            drawdown_percent = (peak_equity - current_equity) / peak_equity
        recent_losses_r = self.get_recent_losses_r()

        soft_breached = drawdown_percent >= self._config.soft_limit
        hard_breached = drawdown_percent >= self._config.hard_limit
        velocity_triggered = recent_losses_r >= self._config.velocity_loss_r

        if hard_breached:
            level = DrawdownLevel.HARD
            reason = "Превышен жёсткий лимит просадки"
        elif velocity_triggered:
            level = DrawdownLevel.VELOCITY
            reason = "Сработал velocity drawdown по окну сделок"
        elif soft_breached:
            level = DrawdownLevel.SOFT
            reason = "Превышен мягкий лимит просадки"
        else:
            level = DrawdownLevel.NORMAL
            reason = "Просадка находится в допустимых пределах"

        return DrawdownAssessment(
            current_equity=current_equity,
            peak_equity=peak_equity,
            drawdown_percent=drawdown_percent,
            soft_limit=self._config.soft_limit,
            hard_limit=self._config.hard_limit,
            velocity_loss_r=self._config.velocity_loss_r,
            velocity_window_trades=self._config.velocity_window_trades,
            recent_losses_r=recent_losses_r,
            level=level,
            soft_breached=soft_breached,
            hard_breached=hard_breached,
            velocity_triggered=velocity_triggered,
            reason=reason,
        )

    def get_current_drawdown(self) -> Decimal:
        """Получить текущую просадку относительно peak equity."""
        if self._current_equity >= self._peak_equity:
            return Decimal("0")
        return (self._peak_equity - self._current_equity) / self._peak_equity

    def get_recent_losses_r(self) -> Decimal:
        """Получить сумму убытков в R по текущему окну сделок."""
        return sum(
            (abs(result_r) for result_r in self._recent_trade_results_r if result_r < 0),
            start=Decimal("0"),
        )

    def get_peak_equity(self) -> Decimal:
        """Получить текущий peak equity."""
        return self._peak_equity

    def get_current_equity(self) -> Decimal:
        """Получить текущее значение капитала из monitor."""
        return self._current_equity

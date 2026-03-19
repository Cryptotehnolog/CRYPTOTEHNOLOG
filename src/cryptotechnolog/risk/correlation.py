"""
Доменный correlation layer для pre-trade checks.

На этом шаге реализована простая, но расширяемая модель:
- symbol -> correlation group;
- эвристическая оценка корреляции;
- лимиты по группам.

Позже этот слой можно заменить на матрицы, окна и статистические модели
без переписывания `RiskEngine`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .portfolio_state import PortfolioSnapshot


class CorrelationViolation(StrEnum):
    """Тип нарушения correlation-инвариантов."""

    NONE = "none"
    CORRELATION_LIMIT = "correlation_limit"
    GROUP_LIMIT = "group_limit"


class CorrelationGroup(StrEnum):
    """Correlation groups для pre-trade risk gating."""

    MAJORS = "Majors"
    L1 = "L1"
    DEFI = "DeFi"
    MEMES = "Memes"
    OTHER = "Other"


@dataclass(slots=True, frozen=True)
class CorrelationConfig:
    """
    Конфигурация correlation foundation.

    Основа пока эвристическая, но интерфейс стабилен для будущей
    более богатой модели корреляции.
    """

    correlation_limit: Decimal = Decimal("0.80")
    same_group_correlation: Decimal = Decimal("0.65")
    cross_group_correlation: Decimal = Decimal("0.25")
    max_positions_per_group: dict[CorrelationGroup, int] = field(
        default_factory=lambda: {
            CorrelationGroup.MAJORS: 2,
            CorrelationGroup.L1: 2,
            CorrelationGroup.DEFI: 2,
            CorrelationGroup.MEMES: 1,
            CorrelationGroup.OTHER: 1,
        }
    )
    group_symbols: dict[CorrelationGroup, frozenset[str]] = field(
        default_factory=lambda: {
            CorrelationGroup.MAJORS: frozenset({"BTC/USDT", "ETH/USDT"}),
            CorrelationGroup.L1: frozenset({"SOL/USDT", "AVAX/USDT", "NEAR/USDT", "APT/USDT"}),
            CorrelationGroup.DEFI: frozenset({"UNI/USDT", "AAVE/USDT", "SNX/USDT"}),
            CorrelationGroup.MEMES: frozenset({"DOGE/USDT", "SHIB/USDT", "PEPE/USDT"}),
        }
    )
    pair_overrides: dict[frozenset[str], Decimal] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class CorrelationAssessment:
    """
    Результат pre-trade correlation assessment.

    Возвращается как доменный результат для `RiskEngine`,
    а не как bool или произвольный словарь.
    """

    allowed: bool
    group: CorrelationGroup
    violation: CorrelationViolation
    max_correlation: Decimal
    correlation_limit: Decimal
    group_position_count: int
    group_position_limit: int
    violating_symbol: str | None
    reason: str


class CorrelationEvaluator:
    """
    Эвристический evaluator корреляции для pre-trade checks.

    Сейчас он решает две задачи:
    - ограничение слишком высокой корреляции с уже открытыми позициями;
    - ограничение количества позиций в одной correlation group.
    """

    def __init__(self, config: CorrelationConfig | None = None) -> None:
        self._config = config or CorrelationConfig()

    def assess_new_position(
        self,
        *,
        symbol: str,
        portfolio: PortfolioSnapshot,
    ) -> CorrelationAssessment:
        """Оценить допустимость новой позиции относительно текущего портфеля."""
        group = self.get_group(symbol)
        group_position_count = self._count_positions_in_group(group=group, portfolio=portfolio)
        group_limit = self._config.max_positions_per_group.get(group, 1)

        violating_symbol: str | None = None
        max_correlation = Decimal("0")
        for record in portfolio.positions:
            correlation = self.estimate_correlation(symbol_a=symbol, symbol_b=record.symbol)
            if correlation > max_correlation:
                max_correlation = correlation
                violating_symbol = record.symbol

        if max_correlation > self._config.correlation_limit:
            return CorrelationAssessment(
                allowed=False,
                group=group,
                violation=CorrelationViolation.CORRELATION_LIMIT,
                max_correlation=max_correlation,
                correlation_limit=self._config.correlation_limit,
                group_position_count=group_position_count,
                group_position_limit=group_limit,
                violating_symbol=violating_symbol,
                reason="Корреляция с открытым портфелем превышает допустимый лимит",
            )

        if group_position_count >= group_limit:
            return CorrelationAssessment(
                allowed=False,
                group=group,
                violation=CorrelationViolation.GROUP_LIMIT,
                max_correlation=max_correlation,
                correlation_limit=self._config.correlation_limit,
                group_position_count=group_position_count,
                group_position_limit=group_limit,
                violating_symbol=violating_symbol,
                reason="Превышен лимит связанных позиций в correlation group",
            )

        return CorrelationAssessment(
            allowed=True,
            group=group,
            violation=CorrelationViolation.NONE,
            max_correlation=max_correlation,
            correlation_limit=self._config.correlation_limit,
            group_position_count=group_position_count,
            group_position_limit=group_limit,
            violating_symbol=violating_symbol,
            reason="Корреляционные ограничения соблюдены",
        )

    def get_group(self, symbol: str) -> CorrelationGroup:
        """Определить correlation group для символа."""
        for group, symbols in self._config.group_symbols.items():
            if symbol in symbols:
                return group
        return CorrelationGroup.OTHER

    def estimate_correlation(self, *, symbol_a: str, symbol_b: str) -> Decimal:
        """
        Оценить корреляцию между двумя символами.

        На этом шаге используется простая модель:
        - одинаковый символ -> 1.0;
        - pair override -> заданное значение;
        - одна group -> same_group_correlation;
        - разные groups -> cross_group_correlation.
        """
        if symbol_a == symbol_b:
            return Decimal("1")

        override = self._config.pair_overrides.get(frozenset({symbol_a, symbol_b}))
        if override is not None:
            return override

        if self.get_group(symbol_a) == self.get_group(symbol_b):
            return self._config.same_group_correlation
        return self._config.cross_group_correlation

    def _count_positions_in_group(
        self,
        *,
        group: CorrelationGroup,
        portfolio: PortfolioSnapshot,
    ) -> int:
        """Подсчитать количество открытых позиций в указанной correlation group."""
        return sum(1 for record in portfolio.positions if self.get_group(record.symbol) is group)

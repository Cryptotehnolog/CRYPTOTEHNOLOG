"""
Доменный менеджер funding rates и funding opportunities.

На этом шаге модуль остаётся автономным и не зависит от Event Bus,
runtime wiring или persistence. Он предоставляет сильный доменный
foundation для будущей интеграции в event-driven контур.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from .models import (
    FundingExchangeRecommendation,
    FundingOpportunity,
    FundingRateQuote,
    FundingRateSnapshot,
    PositionSide,
)

if TYPE_CHECKING:
    from datetime import datetime


MIN_QUOTES_FOR_OPPORTUNITY = 2


class FundingManagerError(Exception):
    """Базовая ошибка FundingManager."""


@dataclass(slots=True, frozen=True)
class FundingManagerConfig:
    """
    Конфигурация доменного funding foundation.

    Все значения выражаются как funding rate за один период.
    """

    min_arbitrage_spread: Decimal = Decimal("0.002")
    min_annualized_spread: Decimal = Decimal("0.05")
    max_acceptable_funding: Decimal = Decimal("0.003")
    min_exchange_improvement: Decimal = Decimal("0.0005")
    min_quotes_for_opportunity: int = MIN_QUOTES_FOR_OPPORTUNITY
    funding_periods_per_day: int = 3
    days_per_year: int = 365


class FundingManager:
    """
    Менеджер funding rate opportunities.

    Обязанности текущего шага:
    - хранить актуальные funding snapshots;
    - рекомендовать лучшую биржу для LONG/SHORT;
    - находить funding arbitrage opportunities;
    - возвращать типизированные доменные результаты.
    """

    def __init__(self, config: FundingManagerConfig | None = None) -> None:
        self._config = config or FundingManagerConfig()
        self._snapshots: dict[str, FundingRateSnapshot] = {}

    def update_snapshot(self, snapshot: FundingRateSnapshot) -> tuple[FundingOpportunity, ...]:
        """
        Сохранить funding snapshot и вернуть найденные opportunities для символа.

        Raises:
            FundingManagerError: Если snapshot невалиден.
        """
        self._validate_snapshot(snapshot)
        self._snapshots[snapshot.symbol] = snapshot
        return self.find_opportunities(symbol=snapshot.symbol)

    def get_snapshot(self, symbol: str) -> FundingRateSnapshot | None:
        """Получить последний funding snapshot по символу."""
        return self._snapshots.get(symbol)

    def recommend_exchange(
        self,
        *,
        symbol: str,
        side: PositionSide,
        current_exchange: str | None = None,
    ) -> FundingExchangeRecommendation:
        """
        Рекомендовать биржу для открытия позиции с учётом funding.

        Для LONG выбирается минимальный funding rate.
        Для SHORT выбирается максимальный funding rate.
        """
        snapshot = self._require_snapshot(symbol)
        quotes = snapshot.quotes

        if side is PositionSide.LONG:
            recommended = min(quotes, key=lambda quote: quote.rate)
        else:
            recommended = max(quotes, key=lambda quote: quote.rate)

        current_rate = self._get_current_rate(snapshot=snapshot, current_exchange=current_exchange)
        if current_rate is None:
            rate_improvement = Decimal("0")
            should_switch = False
        else:
            rate_improvement = self._calculate_rate_improvement(
                side=side,
                current_rate=current_rate,
                recommended_rate=recommended.rate,
            )
            should_switch = (
                current_exchange is not None
                and current_exchange != recommended.exchange
                and rate_improvement >= self._config.min_exchange_improvement
            )

        entry_allowed = self._is_entry_allowed(side=side, rate=recommended.rate)
        if entry_allowed:
            reason = "Подобрана оптимальная биржа по funding rate"
        else:
            reason = "Даже лучшая доступная funding ставка превышает допустимый лимит"

        return FundingExchangeRecommendation(
            symbol=symbol,
            side=side,
            current_exchange=current_exchange,
            current_rate=current_rate,
            recommended_exchange=recommended.exchange,
            recommended_rate=recommended.rate,
            rate_improvement=rate_improvement,
            should_switch=should_switch,
            entry_allowed=entry_allowed,
            reason=reason,
        )

    def find_opportunities(self, *, symbol: str | None = None) -> tuple[FundingOpportunity, ...]:
        """
        Найти funding arbitrage opportunities.

        Если `symbol` не задан, проверяются все доступные snapshots.
        """
        if symbol is not None:
            snapshot = self._require_snapshot(symbol)
            opportunity = self._build_opportunity(snapshot)
            return (opportunity,) if opportunity is not None else ()

        opportunities: list[FundingOpportunity] = []
        for snapshot in self._snapshots.values():
            opportunity = self._build_opportunity(snapshot)
            if opportunity is not None:
                opportunities.append(opportunity)
        return tuple(opportunities)

    def _build_opportunity(self, snapshot: FundingRateSnapshot) -> FundingOpportunity | None:
        """Собрать funding opportunity для одного символа при достаточном spread."""
        if len(snapshot.quotes) < self._config.min_quotes_for_opportunity:
            return None

        sorted_quotes = sorted(snapshot.quotes, key=lambda quote: quote.rate)
        long_quote = sorted_quotes[0]
        short_quote = sorted_quotes[-1]

        spread = short_quote.rate - long_quote.rate
        annualized_spread = self._annualize(spread)

        if spread < self._config.min_arbitrage_spread:
            return None

        if annualized_spread < self._config.min_annualized_spread:
            return None

        return FundingOpportunity(
            symbol=snapshot.symbol,
            long_exchange=long_quote.exchange,
            long_rate=long_quote.rate,
            short_exchange=short_quote.exchange,
            short_rate=short_quote.rate,
            spread=spread,
            annualized_spread=annualized_spread,
            detected_at=snapshot.recorded_at,
        )

    def _annualize(self, rate: Decimal) -> Decimal:
        """Перевести funding spread за период в годовой эквивалент."""
        return (
            rate
            * Decimal(self._config.funding_periods_per_day)
            * Decimal(self._config.days_per_year)
        )

    def _is_entry_allowed(self, *, side: PositionSide, rate: Decimal) -> bool:
        """
        Проверить, допустима ли ставка funding для новой позиции.

        Для LONG недопустима слишком высокая положительная ставка.
        Для SHORT недопустима слишком высокая отрицательная ставка.
        """
        if side is PositionSide.LONG:
            return rate <= self._config.max_acceptable_funding
        return rate >= -self._config.max_acceptable_funding

    def _calculate_rate_improvement(
        self,
        *,
        side: PositionSide,
        current_rate: Decimal,
        recommended_rate: Decimal,
    ) -> Decimal:
        """Посчитать side-aware улучшение funding относительно текущей биржи."""
        if side is PositionSide.LONG:
            return current_rate - recommended_rate
        return recommended_rate - current_rate

    def _get_current_rate(
        self,
        *,
        snapshot: FundingRateSnapshot,
        current_exchange: str | None,
    ) -> Decimal | None:
        """Получить funding rate текущей биржи, если она есть в snapshot."""
        if current_exchange is None:
            return None

        for quote in snapshot.quotes:
            if quote.exchange == current_exchange:
                return quote.rate
        return None

    def _require_snapshot(self, symbol: str) -> FundingRateSnapshot:
        """Получить snapshot по символу или явно завершиться ошибкой."""
        snapshot = self._snapshots.get(symbol)
        if snapshot is None:
            raise FundingManagerError(f"Нет funding snapshot для символа {symbol}")
        return snapshot

    def _validate_snapshot(self, snapshot: FundingRateSnapshot) -> None:
        """Проверить корректность funding snapshot перед сохранением."""
        if not snapshot.symbol:
            raise FundingManagerError("Funding snapshot должен содержать символ")
        if not snapshot.quotes:
            raise FundingManagerError("Funding snapshot должен содержать хотя бы одну ставку")

        seen_exchanges: set[str] = set()
        for quote in snapshot.quotes:
            if not quote.exchange:
                raise FundingManagerError("Funding snapshot содержит пустое имя биржи")
            if quote.exchange in seen_exchanges:
                raise FundingManagerError("Funding snapshot содержит дублирующиеся биржи")
            seen_exchanges.add(quote.exchange)
            if not isinstance(quote.rate, Decimal):
                raise FundingManagerError("Funding rate должен передаваться как Decimal")

    @staticmethod
    def make_snapshot(
        *,
        symbol: str,
        rates: dict[str, Decimal],
        recorded_at: datetime | None = None,
    ) -> FundingRateSnapshot:
        """
        Утилита для сборки snapshot из карты `exchange -> rate`.

        Нужна как тонкий bridge для будущих adapter-слоёв, не нарушая
        типизированный доменный контракт на границе manager.
        """
        quotes = tuple(
            FundingRateQuote(exchange=exchange, rate=rate) for exchange, rate in rates.items()
        )
        if recorded_at is None:
            return FundingRateSnapshot(symbol=symbol, quotes=quotes)
        return FundingRateSnapshot(symbol=symbol, quotes=quotes, recorded_at=recorded_at)

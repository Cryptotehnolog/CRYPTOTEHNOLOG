from datetime import UTC, datetime
from decimal import Decimal

import pytest

from cryptotechnolog.risk.funding_manager import (
    FundingManager,
    FundingManagerConfig,
    FundingManagerError,
)
from cryptotechnolog.risk.models import (
    FundingRateQuote,
    FundingRateSnapshot,
    PositionSide,
)


def make_snapshot(
    *,
    symbol: str = "BTC/USDT",
    quotes: tuple[FundingRateQuote, ...],
    recorded_at: datetime | None = None,
) -> FundingRateSnapshot:
    snapshot_time = recorded_at or datetime(2026, 3, 19, tzinfo=UTC)
    return FundingRateSnapshot(
        symbol=symbol,
        quotes=quotes,
        recorded_at=snapshot_time,
    )


class TestFundingManager:
    """Тесты доменного FundingManager."""

    def setup_method(self) -> None:
        self.manager = FundingManager()
        self.snapshot = make_snapshot(
            quotes=(
                FundingRateQuote(exchange="bybit", rate=Decimal("0.0010")),
                FundingRateQuote(exchange="okx", rate=Decimal("-0.0004")),
                FundingRateQuote(exchange="binance", rate=Decimal("0.0006")),
            )
        )

    def test_stores_and_returns_latest_snapshot(self) -> None:
        """Менеджер должен хранить последний funding snapshot по символу."""
        self.manager.update_snapshot(self.snapshot)

        stored = self.manager.get_snapshot("BTC/USDT")

        assert stored == self.snapshot

    def test_recommends_exchange_with_lowest_rate_for_long(self) -> None:
        """Для LONG должна рекомендоваться биржа с минимальным funding rate."""
        self.manager.update_snapshot(self.snapshot)

        recommendation = self.manager.recommend_exchange(
            symbol="BTC/USDT",
            side=PositionSide.LONG,
            current_exchange="bybit",
        )

        assert recommendation.recommended_exchange == "okx"
        assert recommendation.recommended_rate == Decimal("-0.0004")
        assert recommendation.current_rate == Decimal("0.0010")
        assert recommendation.rate_improvement == Decimal("0.0014")
        assert recommendation.should_switch is True
        assert recommendation.entry_allowed is True

    def test_recommends_exchange_with_highest_rate_for_short(self) -> None:
        """Для SHORT должна рекомендоваться биржа с максимальным funding rate."""
        self.manager.update_snapshot(self.snapshot)

        recommendation = self.manager.recommend_exchange(
            symbol="BTC/USDT",
            side=PositionSide.SHORT,
            current_exchange="okx",
        )

        assert recommendation.recommended_exchange == "bybit"
        assert recommendation.recommended_rate == Decimal("0.0010")
        assert recommendation.current_rate == Decimal("-0.0004")
        assert recommendation.rate_improvement == Decimal("0.0014")
        assert recommendation.should_switch is True
        assert recommendation.entry_allowed is True

    def test_does_not_switch_when_improvement_is_below_threshold(self) -> None:
        """Смена биржи не нужна, если улучшение funding недостаточно велико."""
        manager = FundingManager(FundingManagerConfig(min_exchange_improvement=Decimal("0.0005")))
        manager.update_snapshot(
            make_snapshot(
                quotes=(
                    FundingRateQuote(exchange="bybit", rate=Decimal("0.0008")),
                    FundingRateQuote(exchange="okx", rate=Decimal("0.0004")),
                )
            )
        )

        recommendation = manager.recommend_exchange(
            symbol="BTC/USDT",
            side=PositionSide.LONG,
            current_exchange="bybit",
        )

        assert recommendation.recommended_exchange == "okx"
        assert recommendation.rate_improvement == Decimal("0.0004")
        assert recommendation.should_switch is False

    def test_blocks_long_entry_when_best_rate_is_too_expensive(self) -> None:
        """Для LONG даже лучшая биржа не должна проходить при слишком дорогом funding."""
        manager = FundingManager(FundingManagerConfig(max_acceptable_funding=Decimal("0.003")))
        manager.update_snapshot(
            make_snapshot(
                quotes=(
                    FundingRateQuote(exchange="bybit", rate=Decimal("0.0045")),
                    FundingRateQuote(exchange="okx", rate=Decimal("0.0035")),
                )
            )
        )

        recommendation = manager.recommend_exchange(
            symbol="BTC/USDT",
            side=PositionSide.LONG,
            current_exchange="bybit",
        )

        assert recommendation.recommended_exchange == "okx"
        assert recommendation.entry_allowed is False
        assert "превышает допустимый лимит" in recommendation.reason

    def test_blocks_short_entry_when_best_rate_is_too_negative(self) -> None:
        """Для SHORT слишком отрицательный funding должен блокировать новую позицию."""
        manager = FundingManager(FundingManagerConfig(max_acceptable_funding=Decimal("0.003")))
        manager.update_snapshot(
            make_snapshot(
                quotes=(
                    FundingRateQuote(exchange="bybit", rate=Decimal("-0.0045")),
                    FundingRateQuote(exchange="okx", rate=Decimal("-0.0035")),
                )
            )
        )

        recommendation = manager.recommend_exchange(
            symbol="BTC/USDT",
            side=PositionSide.SHORT,
            current_exchange="bybit",
        )

        assert recommendation.recommended_exchange == "okx"
        assert recommendation.entry_allowed is False

    def test_detects_funding_arbitrage_opportunity(self) -> None:
        """Должна находиться cross-exchange opportunity при достаточном spread."""
        opportunities = self.manager.update_snapshot(
            make_snapshot(
                quotes=(
                    FundingRateQuote(exchange="bybit", rate=Decimal("0.0014")),
                    FundingRateQuote(exchange="okx", rate=Decimal("-0.0010")),
                    FundingRateQuote(exchange="binance", rate=Decimal("0.0008")),
                )
            )
        )

        assert len(opportunities) == 1
        opportunity = opportunities[0]
        assert opportunity.symbol == "BTC/USDT"
        assert opportunity.long_exchange == "okx"
        assert opportunity.short_exchange == "bybit"
        assert opportunity.spread == Decimal("0.0024")
        assert opportunity.annualized_spread == Decimal("2.6280")

    def test_ignores_snapshot_with_insufficient_spread(self) -> None:
        """Недостаточный funding spread не должен давать arbitrage opportunity."""
        manager = FundingManager(FundingManagerConfig(min_arbitrage_spread=Decimal("0.002")))

        opportunities = manager.update_snapshot(
            make_snapshot(
                quotes=(
                    FundingRateQuote(exchange="bybit", rate=Decimal("0.0010")),
                    FundingRateQuote(exchange="okx", rate=Decimal("0.0018")),
                )
            )
        )

        assert opportunities == ()

    def test_finds_opportunities_across_all_stored_symbols(self) -> None:
        """Менеджер должен уметь собрать opportunities по всем сохранённым snapshots."""
        self.manager.update_snapshot(
            make_snapshot(
                quotes=(
                    FundingRateQuote(exchange="bybit", rate=Decimal("0.0014")),
                    FundingRateQuote(exchange="okx", rate=Decimal("-0.0010")),
                    FundingRateQuote(exchange="binance", rate=Decimal("0.0008")),
                )
            )
        )
        self.manager.update_snapshot(
            make_snapshot(
                symbol="ETH/USDT",
                quotes=(
                    FundingRateQuote(exchange="bybit", rate=Decimal("0.0001")),
                    FundingRateQuote(exchange="okx", rate=Decimal("0.0002")),
                ),
            )
        )

        opportunities = self.manager.find_opportunities()

        assert len(opportunities) == 1
        assert opportunities[0].symbol == "BTC/USDT"

    def test_rejects_invalid_snapshot_with_duplicate_exchange(self) -> None:
        """Snapshot с дублирующейся биржей должен отклоняться явно."""
        snapshot = make_snapshot(
            quotes=(
                FundingRateQuote(exchange="bybit", rate=Decimal("0.0001")),
                FundingRateQuote(exchange="bybit", rate=Decimal("0.0002")),
            )
        )

        with pytest.raises(FundingManagerError, match="дублирующиеся биржи"):
            self.manager.update_snapshot(snapshot)

    def test_fails_explicitly_when_snapshot_is_missing(self) -> None:
        """Отсутствие funding snapshot не должно маскироваться молчаливым fallback."""
        with pytest.raises(FundingManagerError, match="Нет funding snapshot"):
            self.manager.recommend_exchange(
                symbol="SOL/USDT",
                side=PositionSide.LONG,
                current_exchange="bybit",
            )

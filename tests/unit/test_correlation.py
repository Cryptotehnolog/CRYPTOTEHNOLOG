from datetime import UTC, datetime
from decimal import Decimal

from cryptotechnolog.risk.correlation import (
    CorrelationConfig,
    CorrelationEvaluator,
    CorrelationGroup,
    CorrelationViolation,
)
from cryptotechnolog.risk.models import Position, PositionSide
from cryptotechnolog.risk.portfolio_state import PortfolioState
from cryptotechnolog.risk.risk_ledger import RiskLedger


def make_position(
    *,
    position_id: str,
    symbol: str,
    side: PositionSide = PositionSide.LONG,
    entry_price: Decimal = Decimal("100"),
    initial_stop: Decimal = Decimal("95"),
    current_stop: Decimal = Decimal("95"),
    quantity: Decimal = Decimal("2"),
) -> Position:
    now = datetime(2026, 3, 19, tzinfo=UTC)
    return Position(
        position_id=position_id,
        symbol=symbol,
        side=side,
        entry_price=entry_price,
        initial_stop=initial_stop,
        current_stop=current_stop,
        quantity=quantity,
        risk_capital_usd=Decimal("10000"),
        opened_at=now,
        updated_at=now,
    )


class TestCorrelationEvaluator:
    """Тесты доменного correlation layer."""

    def setup_method(self) -> None:
        self.evaluator = CorrelationEvaluator()

    def test_resolves_symbol_group(self) -> None:
        """Символы должны раскладываться по ожидаемым correlation groups."""
        assert self.evaluator.get_group("BTC/USDT") is CorrelationGroup.MAJORS
        assert self.evaluator.get_group("SOL/USDT") is CorrelationGroup.L1
        assert self.evaluator.get_group("UNI/USDT") is CorrelationGroup.DEFI
        assert self.evaluator.get_group("PEPE/USDT") is CorrelationGroup.MEMES
        assert self.evaluator.get_group("ARB/USDT") is CorrelationGroup.OTHER

    def test_rejects_when_pair_correlation_exceeds_limit(self) -> None:
        """Слишком высокая корреляция с портфелем должна блокировать новую позицию."""
        ledger = RiskLedger()
        record = ledger.register_position(make_position(position_id="pos-1", symbol="BTC/USDT"))
        portfolio = PortfolioState([record]).snapshot()
        evaluator = CorrelationEvaluator(
            CorrelationConfig(
                correlation_limit=Decimal("0.80"),
                pair_overrides={frozenset({"BTC/USDT", "ETH/USDT"}): Decimal("0.92")},
            )
        )

        assessment = evaluator.assess_new_position(symbol="ETH/USDT", portfolio=portfolio)

        assert assessment.allowed is False
        assert assessment.violation is CorrelationViolation.CORRELATION_LIMIT
        assert assessment.max_correlation == Decimal("0.92")
        assert assessment.violating_symbol == "BTC/USDT"

    def test_rejects_when_group_limit_is_exceeded(self) -> None:
        """Лимит по correlation group должен ограничивать связанные позиции."""
        ledger = RiskLedger()
        first = ledger.register_position(make_position(position_id="pos-1", symbol="BTC/USDT"))
        second = ledger.register_position(make_position(position_id="pos-2", symbol="ETH/USDT"))
        portfolio = PortfolioState([first, second]).snapshot()
        evaluator = CorrelationEvaluator(
            CorrelationConfig(
                correlation_limit=Decimal("1.10"),
                max_positions_per_group={
                    CorrelationGroup.MAJORS: 2,
                    CorrelationGroup.L1: 2,
                    CorrelationGroup.DEFI: 2,
                    CorrelationGroup.MEMES: 1,
                    CorrelationGroup.OTHER: 1,
                },
                pair_overrides={frozenset({"BTC/USDT", "ETH/USDT"}): Decimal("0.50")},
            )
        )

        assessment = evaluator.assess_new_position(symbol="BTC/USDT", portfolio=portfolio)

        assert assessment.allowed is False
        assert assessment.violation is CorrelationViolation.GROUP_LIMIT
        assert assessment.group is CorrelationGroup.MAJORS
        assert assessment.group_position_count == 2

    def test_allows_diversified_position(self) -> None:
        """Низкая межгрупповая корреляция должна позволять новую позицию."""
        ledger = RiskLedger()
        record = ledger.register_position(make_position(position_id="pos-1", symbol="BTC/USDT"))
        portfolio = PortfolioState([record]).snapshot()

        assessment = self.evaluator.assess_new_position(symbol="UNI/USDT", portfolio=portfolio)

        assert assessment.allowed is True
        assert assessment.violation is CorrelationViolation.NONE
        assert assessment.group is CorrelationGroup.DEFI

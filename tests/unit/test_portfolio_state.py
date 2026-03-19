from datetime import UTC, datetime
from decimal import Decimal

import pytest

from cryptotechnolog.risk.models import Position, PositionSide
from cryptotechnolog.risk.portfolio_state import (
    PortfolioLedgerSyncError,
    PortfolioPositionNotFoundError,
    PortfolioState,
)
from cryptotechnolog.risk.risk_ledger import RiskLedger


def make_position(
    *,
    position_id: str,
    side: PositionSide,
    entry_price: Decimal,
    initial_stop: Decimal,
    current_stop: Decimal,
    quantity: Decimal,
) -> Position:
    now = datetime(2026, 3, 19, tzinfo=UTC)
    return Position(
        position_id=position_id,
        symbol="BTC/USDT",
        side=side,
        entry_price=entry_price,
        initial_stop=initial_stop,
        current_stop=current_stop,
        quantity=quantity,
        risk_capital_usd=Decimal("10000"),
        opened_at=now,
        updated_at=now,
    )


class TestPortfolioState:
    """Тесты доменного snapshot портфеля."""

    def test_builds_snapshot_of_open_positions(self) -> None:
        """Snapshot должен содержать все активные позиции без transport-слоя."""
        ledger = RiskLedger()
        first = ledger.register_position(
            make_position(
                position_id="pos-1",
                side=PositionSide.LONG,
                entry_price=Decimal("100"),
                initial_stop=Decimal("95"),
                current_stop=Decimal("97"),
                quantity=Decimal("2"),
            )
        )
        second = ledger.register_position(
            make_position(
                position_id="pos-2",
                side=PositionSide.SHORT,
                entry_price=Decimal("200"),
                initial_stop=Decimal("205"),
                current_stop=Decimal("203"),
                quantity=Decimal("1.5"),
            )
        )

        state = PortfolioState([first, second])
        snapshot = state.snapshot()

        assert snapshot.position_count == 2
        assert {record.position_id for record in snapshot.positions} == {"pos-1", "pos-2"}

    def test_calculates_aggregate_exposure_and_risk_with_decimal_math(self) -> None:
        """Aggregate exposure и aggregate risk должны считаться через Decimal."""
        ledger = RiskLedger()
        long_record = ledger.register_position(
            make_position(
                position_id="pos-1",
                side=PositionSide.LONG,
                entry_price=Decimal("100"),
                initial_stop=Decimal("95"),
                current_stop=Decimal("97"),
                quantity=Decimal("2"),
            )
        )
        short_record = ledger.register_position(
            make_position(
                position_id="pos-2",
                side=PositionSide.SHORT,
                entry_price=Decimal("200"),
                initial_stop=Decimal("205"),
                current_stop=Decimal("203"),
                quantity=Decimal("1.5"),
            )
        )

        state = PortfolioState([long_record, short_record])
        snapshot = state.snapshot()

        assert snapshot.total_long_exposure_usd == Decimal("200")
        assert snapshot.total_short_exposure_usd == Decimal("300.0")
        assert snapshot.total_exposure_usd == Decimal("500.0")
        assert snapshot.total_risk_usd == Decimal("10.5")
        assert snapshot.total_risk_r == Decimal("0.00105")

    def test_updates_and_removes_positions(self) -> None:
        """PortfolioState должен поддерживать upsert и release snapshot-записей."""
        ledger = RiskLedger()
        initial = ledger.register_position(
            make_position(
                position_id="pos-1",
                side=PositionSide.LONG,
                entry_price=Decimal("100"),
                initial_stop=Decimal("95"),
                current_stop=Decimal("95"),
                quantity=Decimal("2"),
            )
        )

        state = PortfolioState([initial])
        updated = ledger.update_position_risk(position_id="pos-1", new_stop=Decimal("98"))
        state.sync_position_from_ledger(updated)
        state.assert_position_matches_ledger(updated)
        state.assert_total_risk_matches_ledger(ledger.get_total_risk_r())

        assert state.get_position("pos-1").current_stop == Decimal("98")

        removed = state.release_position_from_ledger("pos-1")
        assert removed.position_id == "pos-1"
        assert state.snapshot().position_count == 0

    def test_detects_when_portfolio_state_diverges_from_ledger(self) -> None:
        """Явный sync-contract должен падать при незаметной рассинхронизации."""
        ledger = RiskLedger()
        record = ledger.register_position(
            make_position(
                position_id="pos-1",
                side=PositionSide.LONG,
                entry_price=Decimal("100"),
                initial_stop=Decimal("95"),
                current_stop=Decimal("95"),
                quantity=Decimal("2"),
            )
        )
        state = PortfolioState([record])
        updated = ledger.update_position_risk(position_id="pos-1", new_stop=Decimal("98"))

        with pytest.raises(PortfolioLedgerSyncError, match="рассинхронизирован"):
            state.assert_position_matches_ledger(updated)

        with pytest.raises(PortfolioLedgerSyncError, match="агрегированному риску"):
            state.assert_total_risk_matches_ledger(ledger.get_total_risk_r())

    def test_raises_error_for_unknown_position(self) -> None:
        """Запрос неизвестной позиции должен завершаться явной ошибкой."""
        state = PortfolioState()

        with pytest.raises(PortfolioPositionNotFoundError, match="missing"):
            state.get_position("missing")

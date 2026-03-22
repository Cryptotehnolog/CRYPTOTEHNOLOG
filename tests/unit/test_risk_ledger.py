from datetime import UTC, datetime
from decimal import Decimal

import pytest

from cryptotechnolog.risk.models import Position, PositionRiskRecord, PositionSide, TrailingState
from cryptotechnolog.risk.risk_ledger import (
    InvalidLedgerOperationError,
    PositionAlreadyRegisteredError,
    PositionNotFoundError,
    RiskIncreaseNotAllowedError,
    RiskLedger,
)


def make_position(
    *,
    position_id: str = "pos-1",
    symbol: str = "BTC/USDT",
    side: PositionSide = PositionSide.LONG,
    entry_price: Decimal = Decimal("100"),
    initial_stop: Decimal = Decimal("95"),
    current_stop: Decimal = Decimal("95"),
    quantity: Decimal = Decimal("2"),
    risk_capital_usd: Decimal = Decimal("10000"),
) -> Position:
    """Создать тестовую позицию для ledger."""
    now = datetime(2026, 3, 19, tzinfo=UTC)
    return Position(
        position_id=position_id,
        symbol=symbol,
        side=side,
        entry_price=entry_price,
        initial_stop=initial_stop,
        current_stop=current_stop,
        quantity=quantity,
        risk_capital_usd=risk_capital_usd,
        trailing_state=TrailingState.INACTIVE,
        opened_at=now,
        updated_at=now,
    )


class TestRiskLedger:
    """Тесты позиционного RiskLedger."""

    def setup_method(self) -> None:
        self.ledger = RiskLedger()

    def test_register_position_creates_position_risk_record(self) -> None:
        """Регистрация создаёт позиционную запись с initial и current risk."""
        record = self.ledger.register_position(make_position())

        assert isinstance(record, PositionRiskRecord)
        assert record.position_id == "pos-1"
        assert record.initial_risk_usd == Decimal("10")
        assert record.current_risk_usd == Decimal("10")
        assert record.initial_risk_r == Decimal("0.001")
        assert record.current_risk_r == Decimal("0.001")
        assert self.ledger.get_total_risk_r() == Decimal("0.001")

    def test_rejects_duplicate_active_registration(self) -> None:
        """Нельзя повторно регистрировать уже активную позицию."""
        position = make_position()
        self.ledger.register_position(position)

        with pytest.raises(PositionAlreadyRegisteredError, match="уже зарегистрирована"):
            self.ledger.register_position(position)

    def test_updates_risk_after_stop_move(self) -> None:
        """Движение стопа должно пересчитывать текущий риск позиции."""
        self.ledger.register_position(make_position())

        updated = self.ledger.update_position_risk(
            position_id="pos-1",
            new_stop=Decimal("98"),
            trailing_state=TrailingState.ACTIVE,
        )

        assert updated.current_stop == Decimal("98")
        assert updated.current_risk_usd == Decimal("4")
        assert updated.current_risk_r == Decimal("0.0004")
        assert updated.trailing_state is TrailingState.ACTIVE
        assert self.ledger.get_total_risk_r() == Decimal("0.0004")

    def test_long_breakeven_or_profit_stop_has_zero_downside_risk(self) -> None:
        """Для LONG риск должен стать нулевым, если стоп уже не ниже entry."""
        self.ledger.register_position(make_position())

        updated = self.ledger.update_position_risk(
            position_id="pos-1",
            new_stop=Decimal("101"),
            trailing_state=TrailingState.ACTIVE,
        )

        assert updated.current_risk_usd == Decimal("0")
        assert updated.current_risk_r == Decimal("0")
        assert self.ledger.get_total_risk_r() == Decimal("0")

    def test_short_breakeven_or_profit_stop_has_zero_downside_risk(self) -> None:
        """Для SHORT риск должен стать нулевым, если стоп уже не выше entry."""
        self.ledger.register_position(
            make_position(
                side=PositionSide.SHORT,
                entry_price=Decimal("100"),
                initial_stop=Decimal("105"),
                current_stop=Decimal("105"),
            )
        )

        updated = self.ledger.update_position_risk(
            position_id="pos-1",
            new_stop=Decimal("99"),
            trailing_state=TrailingState.ACTIVE,
        )

        assert updated.current_risk_usd == Decimal("0")
        assert updated.current_risk_r == Decimal("0")
        assert self.ledger.get_total_risk_r() == Decimal("0")

    def test_rejects_risk_increase_without_explicit_scenario(self) -> None:
        """По умолчанию ledger запрещает update, который увеличивает риск."""
        self.ledger.register_position(make_position())

        with pytest.raises(RiskIncreaseNotAllowedError, match="увеличивает риск"):
            self.ledger.update_position_risk(
                position_id="pos-1",
                new_stop=Decimal("90"),
            )

    def test_release_position_frees_total_risk(self) -> None:
        """Закрытие позиции должно освобождать её риск из ledger."""
        self.ledger.register_position(make_position())

        released = self.ledger.release_position("pos-1")

        assert released.position_id == "pos-1"
        assert self.ledger.get_total_risk_r() == Decimal("0")
        with pytest.raises(PositionNotFoundError):
            self.ledger.get_position_record("pos-1")

    def test_total_risk_is_sum_of_active_position_records(self) -> None:
        """Суммарный риск считается только по активным позиционным записям."""
        self.ledger.register_position(make_position(position_id="pos-1"))
        self.ledger.register_position(
            make_position(
                position_id="pos-2",
                symbol="ETH/USDT",
                quantity=Decimal("3"),
                current_stop=Decimal("96"),
            )
        )

        assert self.ledger.get_total_risk_r() == Decimal("0.0022")

    def test_update_unknown_position_raises_error(self) -> None:
        """Обновление неизвестной позиции должно завершаться ошибкой."""
        with pytest.raises(PositionNotFoundError, match="не найдена"):
            self.ledger.update_position_risk(
                position_id="missing",
                new_stop=Decimal("100"),
            )

    def test_release_unknown_position_raises_error(self) -> None:
        """Освобождение неизвестной позиции должно завершаться ошибкой."""
        with pytest.raises(PositionNotFoundError, match="не найдена"):
            self.ledger.release_position("missing")

    def test_registry_is_position_based_not_limit_type_based(self) -> None:
        """Ledger хранит позиционные записи, а не агрегаты по limit_type."""
        record = self.ledger.register_position(
            make_position(
                position_id="btc-long-1",
                symbol="BTC/USDT",
            )
        )

        assert record.position_id == "btc-long-1"
        assert record.symbol == "BTC/USDT"
        assert not hasattr(record, "limit_type")

    def test_register_rejects_invalid_domain_position(self) -> None:
        """Регистрация невалидной доменной позиции должна падать явно."""
        with pytest.raises(InvalidLedgerOperationError, match="Количество позиции"):
            self.ledger.register_position(make_position(quantity=Decimal("0")))

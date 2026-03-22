from decimal import Decimal

import pytest

from cryptotechnolog.risk.models import (
    Order,
    OrderSide,
    Position,
    PositionSide,
    RejectReason,
    StopUpdate,
    TrailingEvaluationType,
    TrailingMode,
    TrailingState,
    TrailingTier,
)
from cryptotechnolog.risk.position_sizing import (
    PositionSizer,
    PositionSizingError,
    PositionSizingParams,
)


class TestRiskModels:
    """Тесты базовых доменных моделей риска."""

    def test_order_and_position_models_are_typed(self) -> None:
        """Базовые модели должны сохранять доменный контракт без dict-структур."""
        order = Order(
            order_id="ord-1",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            entry_price=Decimal("100"),
            stop_loss=Decimal("95"),
        )
        position = Position(
            position_id="pos-1",
            symbol="BTC/USDT",
            side=PositionSide.LONG,
            entry_price=Decimal("100"),
            initial_stop=Decimal("95"),
            current_stop=Decimal("96"),
            quantity=Decimal("2"),
            risk_capital_usd=Decimal("1000"),
        )
        update = StopUpdate(
            position_id="pos-1",
            old_stop=Decimal("96"),
            new_stop=Decimal("97"),
            pnl_r=Decimal("1.5"),
            evaluation_type=TrailingEvaluationType.MOVE,
            tier=TrailingTier.T1,
            mode=TrailingMode.NORMAL,
            state="trading",
            risk_before=Decimal("0.01"),
            risk_after=Decimal("0.008"),
            should_execute=True,
            reason="Тестовый пересчёт",
        )

        assert order.side is OrderSide.BUY
        assert position.trailing_state is TrailingState.INACTIVE
        assert update.new_stop > update.old_stop


class TestPositionSizer:
    """Тесты R-unit position sizing."""

    def setup_method(self) -> None:
        self.sizer = PositionSizer()

    def test_calculates_position_size_with_decimal_only_math(self) -> None:
        """Размер позиции должен рассчитываться через Decimal-математику."""
        result = self.sizer.calculate_position_size(
            PositionSizingParams(
                entry_price=Decimal("100"),
                stop_loss=Decimal("95"),
                equity=Decimal("10000"),
                base_r_percent=Decimal("0.01"),
                max_r_per_trade=Decimal("0.02"),
                max_position_size=Decimal("5000"),
                quantity_step=Decimal("0.01"),
                price_precision=Decimal("0.01"),
            )
        )

        assert result.quantity == Decimal("20.00")
        assert result.position_size_usd == Decimal("2000.00")
        assert result.requested_risk_usd == Decimal("100.00")
        assert result.actual_risk_usd == Decimal("100.00")
        assert result.actual_risk_r == Decimal("0.01000000")
        assert result.capped_by_max_position_size is False

    def test_calculates_risk_usd(self) -> None:
        """Риск в USD равен абсолютной дистанции до стопа на количество."""
        risk_usd = self.sizer.calculate_risk_usd(
            entry_price=Decimal("120"),
            stop_loss=Decimal("115"),
            quantity=Decimal("3"),
        )

        assert risk_usd == Decimal("15")

    def test_calculates_risk_r(self) -> None:
        """Риск в R должен считаться как доля от капитала."""
        risk_r = self.sizer.calculate_risk_r(
            risk_usd=Decimal("50"),
            equity=Decimal("10000"),
        )

        assert risk_r == Decimal("0.005")

    def test_requires_stop_loss(self) -> None:
        """Стоп-лосс обязателен для расчёта риска."""
        with pytest.raises(PositionSizingError, match=RejectReason.STOP_LOSS_REQUIRED.value):
            self.sizer.calculate_position_size(
                PositionSizingParams(
                    entry_price=Decimal("100"),
                    stop_loss=None,  # type: ignore[arg-type]
                    equity=Decimal("10000"),
                    base_r_percent=Decimal("0.01"),
                    max_r_per_trade=Decimal("0.02"),
                    max_position_size=Decimal("5000"),
                )
            )

    def test_rejects_equal_entry_and_stop(self) -> None:
        """Entry и stop не могут совпадать."""
        with pytest.raises(PositionSizingError, match=RejectReason.ENTRY_EQUALS_STOP.value):
            self.sizer.calculate_position_size(
                PositionSizingParams(
                    entry_price=Decimal("100"),
                    stop_loss=Decimal("100"),
                    equity=Decimal("10000"),
                    base_r_percent=Decimal("0.01"),
                    max_r_per_trade=Decimal("0.02"),
                    max_position_size=Decimal("5000"),
                )
            )

    def test_rejects_when_target_risk_exceeds_max_r_per_trade(self) -> None:
        """Целевой риск сделки не должен превышать max_r_per_trade."""
        with pytest.raises(PositionSizingError, match="max_r_per_trade"):
            self.sizer.calculate_position_size(
                PositionSizingParams(
                    entry_price=Decimal("100"),
                    stop_loss=Decimal("99"),
                    equity=Decimal("10000"),
                    base_r_percent=Decimal("0.03"),
                    max_r_per_trade=Decimal("0.02"),
                    max_position_size=Decimal("5000"),
                )
            )

    def test_caps_position_by_max_position_size(self) -> None:
        """Лимит max_position_size должен уменьшать итоговый размер позиции."""
        result = self.sizer.calculate_position_size(
            PositionSizingParams(
                entry_price=Decimal("100"),
                stop_loss=Decimal("95"),
                equity=Decimal("10000"),
                base_r_percent=Decimal("0.01"),
                max_r_per_trade=Decimal("0.02"),
                max_position_size=Decimal("800"),
                quantity_step=Decimal("0.01"),
                price_precision=Decimal("0.01"),
            )
        )

        assert result.quantity == Decimal("8.00")
        assert result.position_size_usd == Decimal("800.00")
        assert result.actual_risk_usd == Decimal("40.00")
        assert result.actual_risk_r == Decimal("0.00400000")
        assert result.capped_by_max_position_size is True

    def test_rounds_quantity_down_without_increasing_risk(self) -> None:
        """Округление вниз не должно увеличивать риск позиции."""
        result = self.sizer.calculate_position_size(
            PositionSizingParams(
                entry_price=Decimal("123.45"),
                stop_loss=Decimal("120.00"),
                equity=Decimal("10000"),
                base_r_percent=Decimal("0.01"),
                max_r_per_trade=Decimal("0.02"),
                max_position_size=Decimal("10000"),
                quantity_step=Decimal("0.001"),
                price_precision=Decimal("0.01"),
            )
        )

        assert result.quantity == Decimal("28.985")
        assert result.actual_risk_usd <= result.requested_risk_usd
        assert result.position_size_usd > 0

    def test_rejects_zero_or_negative_quantity_inputs(self) -> None:
        """Количество позиции в risk formula должно быть положительным."""
        with pytest.raises(PositionSizingError, match=RejectReason.INVALID_QUANTITY.value):
            self.sizer.calculate_risk_usd(
                entry_price=Decimal("100"),
                stop_loss=Decimal("95"),
                quantity=Decimal("0"),
            )

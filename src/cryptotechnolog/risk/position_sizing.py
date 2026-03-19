"""
R-unit расчёт размера позиции.

Модуль намеренно автономен и не зависит от orchestration-слоёв.
Он задаёт базовую денежную математику для следующего шага с RiskLedger.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal, localcontext

from .models import PositionSize, RejectReason


class PositionSizingError(ValueError):
    """Ошибка расчёта размера позиции."""


@dataclass(slots=True, frozen=True)
class PositionSizingParams:
    """
    Параметры расчёта размера позиции.

    Все денежные и ценовые значения выражаются через Decimal.
    """

    entry_price: Decimal
    stop_loss: Decimal
    equity: Decimal
    base_r_percent: Decimal
    max_r_per_trade: Decimal
    max_position_size: Decimal
    quantity_step: Decimal = Decimal("0.00000001")
    price_precision: Decimal = Decimal("0.00000001")
    risk_precision: Decimal = Decimal("0.00000001")


class PositionSizer:
    """
    Калькулятор размера позиции по R-unit логике.

    Базовая формула:
    - requested_risk_usd = equity * base_r_percent
    - risk_per_unit = |entry_price - stop_loss|
    - quantity = requested_risk_usd / risk_per_unit

    После этого применяется:
    - валидация max_r_per_trade;
    - ограничение max_position_size;
    - округление quantity вниз до разрешённого шага.
    """

    @staticmethod
    def calculate_risk_usd(
        *,
        entry_price: Decimal,
        stop_loss: Decimal,
        quantity: Decimal,
    ) -> Decimal:
        """
        Рассчитать риск позиции в USD.

        Возвращает абсолютную потерю при достижении стоп-лосса.
        """
        PositionSizer._validate_price_pair(entry_price, stop_loss)
        PositionSizer._validate_positive(quantity, RejectReason.INVALID_QUANTITY)
        return (entry_price - stop_loss).copy_abs() * quantity

    @staticmethod
    def calculate_risk_r(
        *,
        risk_usd: Decimal,
        equity: Decimal,
    ) -> Decimal:
        """
        Рассчитать риск в R-долях от капитала.
        """
        PositionSizer._validate_positive(equity, "Капитал должен быть положительным")
        if risk_usd < 0:
            raise PositionSizingError("Риск в USD не может быть отрицательным")
        return risk_usd / equity

    def calculate_position_size(self, params: PositionSizingParams) -> PositionSize:
        """
        Рассчитать размер позиции по заданным параметрам риска.

        Raises:
            PositionSizingError: Если входные данные нарушают инварианты.
        """
        self._validate_params(params)

        requested_risk_usd = params.equity * params.base_r_percent
        requested_risk_r = self.calculate_risk_r(
            risk_usd=requested_risk_usd,
            equity=params.equity,
        )

        if requested_risk_r > params.max_r_per_trade:
            raise PositionSizingError(
                "Целевой риск на сделку превышает допустимый max_r_per_trade: "
                f"{requested_risk_r} > {params.max_r_per_trade}"
            )

        risk_per_unit = (params.entry_price - params.stop_loss).copy_abs()

        with localcontext() as context:
            context.prec = 28
            raw_quantity = requested_risk_usd / risk_per_unit

        quantity = self._round_down(raw_quantity, params.quantity_step)
        self._validate_positive(quantity, RejectReason.INVALID_QUANTITY)

        position_size_usd = quantity * params.entry_price
        capped_by_max_position_size = False

        if position_size_usd > params.max_position_size:
            capped_quantity = self._round_down(
                params.max_position_size / params.entry_price,
                params.quantity_step,
            )
            self._validate_positive(capped_quantity, RejectReason.INVALID_POSITION_SIZE)
            quantity = capped_quantity
            position_size_usd = quantity * params.entry_price
            capped_by_max_position_size = True

        actual_risk_usd = self.calculate_risk_usd(
            entry_price=params.entry_price,
            stop_loss=params.stop_loss,
            quantity=quantity,
        )
        actual_risk_r = self.calculate_risk_r(
            risk_usd=actual_risk_usd,
            equity=params.equity,
        )

        if actual_risk_r > params.max_r_per_trade:
            raise PositionSizingError(
                "Фактический риск после округления превысил max_r_per_trade: "
                f"{actual_risk_r} > {params.max_r_per_trade}"
            )

        if position_size_usd <= 0:
            raise PositionSizingError("Размер позиции должен быть положительным")

        return PositionSize(
            quantity=quantity,
            position_size_usd=self._quantize(position_size_usd, params.price_precision),
            requested_risk_usd=self._quantize(requested_risk_usd, params.price_precision),
            actual_risk_usd=self._quantize(actual_risk_usd, params.price_precision),
            actual_risk_r=self._quantize(actual_risk_r, params.risk_precision),
            risk_per_unit=self._quantize(risk_per_unit, params.price_precision),
            capped_by_max_position_size=capped_by_max_position_size,
        )

    @staticmethod
    def _validate_params(params: PositionSizingParams) -> None:
        """Проверить инварианты параметров расчёта."""
        PositionSizer._validate_price_pair(params.entry_price, params.stop_loss)
        PositionSizer._validate_positive(params.equity, "Капитал должен быть положительным")
        PositionSizer._validate_positive(
            params.base_r_percent,
            "Базовый риск на сделку должен быть положительным",
        )
        PositionSizer._validate_positive(
            params.max_r_per_trade,
            "Лимит max_r_per_trade должен быть положительным",
        )
        PositionSizer._validate_positive(
            params.max_position_size,
            "Лимит max_position_size должен быть положительным",
        )
        PositionSizer._validate_positive(
            params.quantity_step,
            "Шаг количества должен быть положительным",
        )
        PositionSizer._validate_positive(
            params.price_precision,
            "Точность цены должна быть положительной",
        )
        PositionSizer._validate_positive(
            params.risk_precision,
            "Точность R-величин должна быть положительной",
        )

    @staticmethod
    def _validate_price_pair(entry_price: Decimal, stop_loss: Decimal) -> None:
        """Проверить корректность пары entry/stop."""
        PositionSizer._validate_positive(entry_price, "Цена входа должна быть положительной")
        if stop_loss is None:
            raise PositionSizingError(RejectReason.STOP_LOSS_REQUIRED.value)
        PositionSizer._validate_positive(stop_loss, "Стоп-лосс должен быть положительным")
        if entry_price == stop_loss:
            raise PositionSizingError(RejectReason.ENTRY_EQUALS_STOP.value)

    @staticmethod
    def _validate_positive(value: Decimal, error: RejectReason | str) -> None:
        """Проверить, что значение положительно."""
        if value <= 0:
            message = error.value if isinstance(error, RejectReason) else error
            raise PositionSizingError(message)

    @staticmethod
    def _round_down(value: Decimal, step: Decimal) -> Decimal:
        """Округлить значение вниз до кратности шагу."""
        return (value / step).to_integral_value(rounding=ROUND_DOWN) * step

    @staticmethod
    def _quantize(value: Decimal, quantum: Decimal) -> Decimal:
        """Нормализовать Decimal до требуемой точности."""
        return value.quantize(quantum, rounding=ROUND_DOWN)

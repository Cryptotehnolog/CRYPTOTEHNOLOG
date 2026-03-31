"""
Позиционный RiskLedger.

Назначение:
    - быть единым источником истины по риску открытых позиций;
    - хранить текущий и исходный риск по каждой позиции;
    - обеспечивать жёсткий инвариант для следующего шага:
      движение стопа невозможно без успешного обновления ledger.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

from .models import Position, PositionRiskRecord, PositionSide, TrailingState


class RiskLedgerError(Exception):
    """Базовая ошибка RiskLedger."""


class PositionAlreadyRegisteredError(RiskLedgerError):
    """Позиция уже зарегистрирована в ledger."""


class PositionNotFoundError(RiskLedgerError):
    """Позиция не найдена в ledger."""


class RiskIncreaseNotAllowedError(RiskLedgerError):
    """Попытка увеличить риск без явного допустимого сценария."""


class InvalidLedgerOperationError(RiskLedgerError):
    """Операция с ledger нарушает доменный инвариант."""


class RiskLedger:
    """
    Позиционный ledger риска.

    Важно:
    - не хранит агрегаты по `limit_type`;
    - не смешивает risk limits и risk registry;
    - считает `total_risk_r` только из активных позиционных записей.
    """

    def __init__(self) -> None:
        """Инициализировать пустой позиционный ledger."""
        self._records: dict[str, PositionRiskRecord] = {}
        self._total_risk_r: Decimal = Decimal("0")

    def register_position(self, position: Position) -> PositionRiskRecord:
        """
        Зарегистрировать новую открытую позицию.

        Raises:
            PositionAlreadyRegisteredError: Если позиция уже активна.
            InvalidLedgerOperationError: Если доменные поля невалидны.
        """
        if position.position_id in self._records:
            raise PositionAlreadyRegisteredError(
                f"Позиция {position.position_id} уже зарегистрирована в RiskLedger"
            )

        self._validate_position(position)

        initial_risk_usd = self._calculate_risk_usd(
            side=position.side,
            entry_price=position.entry_price,
            stop=position.initial_stop,
            quantity=position.quantity,
        )
        current_risk_usd = self._calculate_risk_usd(
            side=position.side,
            entry_price=position.entry_price,
            stop=position.current_stop,
            quantity=position.quantity,
        )
        initial_risk_r = self._calculate_risk_r(
            risk_usd=initial_risk_usd,
            risk_capital_usd=position.risk_capital_usd,
        )
        current_risk_r = self._calculate_risk_r(
            risk_usd=current_risk_usd,
            risk_capital_usd=position.risk_capital_usd,
        )

        record = PositionRiskRecord(
            position_id=position.position_id,
            symbol=position.symbol,
            exchange_id=position.exchange_id,
            strategy_id=position.strategy_id,
            side=position.side,
            entry_price=position.entry_price,
            initial_stop=position.initial_stop,
            current_stop=position.current_stop,
            quantity=position.quantity,
            risk_capital_usd=position.risk_capital_usd,
            initial_risk_usd=initial_risk_usd,
            initial_risk_r=initial_risk_r,
            current_risk_usd=current_risk_usd,
            current_risk_r=current_risk_r,
            current_price=position.entry_price,
            unrealized_pnl_usd=Decimal("0"),
            unrealized_pnl_percent=Decimal("0"),
            trailing_state=position.trailing_state,
            opened_at=position.opened_at,
            updated_at=position.updated_at,
        )
        self._records[position.position_id] = record
        self._recalculate_total_risk()
        return record

    def update_position_risk(
        self,
        *,
        position_id: str,
        new_stop: Decimal,
        trailing_state: TrailingState | None = None,
        allow_risk_increase: bool = False,
        updated_at: datetime | None = None,
    ) -> PositionRiskRecord:
        """
        Обновить текущий риск позиции после изменения стопа.

        По умолчанию увеличение риска запрещено.

        Raises:
            PositionNotFoundError: Если позиция отсутствует.
            RiskIncreaseNotAllowedError: Если новый стоп увеличивает риск.
            InvalidLedgerOperationError: Если входные данные невалидны.
        """
        record = self.get_position_record(position_id)
        if new_stop <= 0:
            raise InvalidLedgerOperationError("Новый стоп должен быть положительным")

        new_risk_usd = self._calculate_risk_usd(
            side=record.side,
            entry_price=record.entry_price,
            stop=new_stop,
            quantity=record.quantity,
        )
        new_risk_r = self._calculate_risk_r(
            risk_usd=new_risk_usd,
            risk_capital_usd=record.risk_capital_usd,
        )

        if new_risk_usd > record.current_risk_usd and not allow_risk_increase:
            raise RiskIncreaseNotAllowedError(
                "Обновление RiskLedger увеличивает риск позиции без допустимого сценария"
            )

        next_updated_at = updated_at or datetime.now(UTC)
        new_record = replace(
            record,
            current_stop=new_stop,
            current_risk_usd=new_risk_usd,
            current_risk_r=new_risk_r,
            trailing_state=trailing_state or record.trailing_state,
            updated_at=next_updated_at,
        )
        self._records[position_id] = new_record
        self._recalculate_total_risk()
        return new_record

    def update_position_market(
        self,
        *,
        position_id: str,
        mark_price: Decimal,
        updated_at: datetime | None = None,
    ) -> PositionRiskRecord:
        """Синхронизировать текущую market truth позиции без изменения стопа/риска."""
        record = self.get_position_record(position_id)
        if mark_price <= 0:
            raise InvalidLedgerOperationError("Текущая цена должна быть положительной")

        pnl_usd = self._calculate_unrealized_pnl_usd(
            side=record.side,
            entry_price=record.entry_price,
            mark_price=mark_price,
            quantity=record.quantity,
        )
        pnl_percent = self._calculate_unrealized_pnl_percent(
            entry_price=record.entry_price,
            quantity=record.quantity,
            pnl_usd=pnl_usd,
        )

        new_record = replace(
            record,
            current_price=mark_price,
            unrealized_pnl_usd=pnl_usd,
            unrealized_pnl_percent=pnl_percent,
            updated_at=updated_at or datetime.now(UTC),
        )
        self._records[position_id] = new_record
        return new_record

    def release_position(self, position_id: str) -> PositionRiskRecord:
        """
        Освободить риск закрытой позиции.

        Raises:
            PositionNotFoundError: Если позиция отсутствует.
        """
        record = self.get_position_record(position_id)
        del self._records[position_id]
        self._recalculate_total_risk()
        return record

    def get_position_record(self, position_id: str) -> PositionRiskRecord:
        """
        Получить актуальную запись риска позиции.

        Raises:
            PositionNotFoundError: Если позиция отсутствует.
        """
        record = self._records.get(position_id)
        if record is None:
            raise PositionNotFoundError(f"Позиция {position_id} не найдена в RiskLedger")
        return record

    def get_total_risk_r(self) -> Decimal:
        """
        Получить суммарный текущий риск портфеля в R.
        """
        return self._total_risk_r

    def _recalculate_total_risk(self) -> None:
        """Пересчитать агрегированный риск только из активных записей ledger."""
        self._total_risk_r = sum(
            (record.current_risk_r for record in self._records.values()),
            start=Decimal("0"),
        )

    @staticmethod
    def _validate_position(position: Position) -> None:
        """Проверить доменные инварианты позиции при регистрации."""
        if position.quantity <= 0:
            raise InvalidLedgerOperationError("Количество позиции должно быть положительным")
        if position.entry_price <= 0:
            raise InvalidLedgerOperationError("Цена входа должна быть положительной")
        if position.initial_stop <= 0 or position.current_stop <= 0:
            raise InvalidLedgerOperationError("Стоп позиции должен быть положительным")
        if position.risk_capital_usd <= 0:
            raise InvalidLedgerOperationError("Базовый капитал риска должен быть положительным")

    @staticmethod
    def _calculate_risk_usd(
        *,
        side: PositionSide,
        entry_price: Decimal,
        stop: Decimal,
        quantity: Decimal,
    ) -> Decimal:
        """
        Рассчитать downside risk позиции в USD с учётом направления.

        Для LONG риск есть только пока стоп ниже entry.
        Для SHORT риск есть только пока стоп выше entry.
        Защищённая прибыль не считается риском.
        """
        if side is PositionSide.LONG:
            price_risk = max(entry_price - stop, Decimal("0"))
        else:
            price_risk = max(stop - entry_price, Decimal("0"))
        return price_risk * quantity

    @staticmethod
    def _calculate_risk_r(
        *,
        risk_usd: Decimal,
        risk_capital_usd: Decimal,
    ) -> Decimal:
        """Рассчитать риск позиции в R относительно риск-капитала."""
        return risk_usd / risk_capital_usd

    @staticmethod
    def _calculate_unrealized_pnl_usd(
        *,
        side: PositionSide,
        entry_price: Decimal,
        mark_price: Decimal,
        quantity: Decimal,
    ) -> Decimal:
        """Рассчитать нереализованный PnL позиции в USD."""
        if side is PositionSide.LONG:
            return (mark_price - entry_price) * quantity
        return (entry_price - mark_price) * quantity

    @staticmethod
    def _calculate_unrealized_pnl_percent(
        *,
        entry_price: Decimal,
        quantity: Decimal,
        pnl_usd: Decimal,
    ) -> Decimal:
        """Рассчитать нереализованный PnL как процент от входного номинала позиции."""
        notional_usd = entry_price * quantity
        if notional_usd <= 0:
            return Decimal("0")
        return (pnl_usd / notional_usd) * Decimal("100")

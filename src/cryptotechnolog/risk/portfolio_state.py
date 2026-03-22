"""
Портфельный snapshot открытых позиций.

Модуль хранит только доменное представление текущих позиций и агрегатов риска.
Он не зависит от transport payload, event listeners или orchestration.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    from .models import PositionRiskRecord
from .models import PositionSide


class PortfolioStateError(Exception):
    """Базовая ошибка PortfolioState."""


class PortfolioPositionNotFoundError(PortfolioStateError):
    """Позиция не найдена в текущем snapshot портфеля."""


class PortfolioLedgerSyncError(PortfolioStateError):
    """Нарушен контракт синхронизации между PortfolioState и RiskLedger."""


@dataclass(slots=True, frozen=True)
class PortfolioSnapshot:
    """
    Снимок текущего состояния открытых позиций.

    Этот контракт нужен как foundation для будущих pre-trade checks:
    - aggregate exposure
    - aggregate risk
    - количество открытых позиций
    """

    positions: tuple[PositionRiskRecord, ...]
    position_count: int
    total_exposure_usd: Decimal
    total_long_exposure_usd: Decimal
    total_short_exposure_usd: Decimal
    total_risk_usd: Decimal
    total_risk_r: Decimal


class PortfolioState:
    """
    Портфельное состояние поверх позиционных risk records.

    Важно:
    - хранит только позиции новой доменной модели;
    - не смешивает aggregate limits и transport events;
    - строит snapshot, пригодный для будущего `RiskEngine`.
    - принимает risk-данные только из `RiskLedger`, а не из произвольных payload.
    """

    def __init__(self, positions: Iterable[PositionRiskRecord] | None = None) -> None:
        """Инициализировать состояние портфеля."""
        self._positions: dict[str, PositionRiskRecord] = {}
        if positions is not None:
            for record in positions:
                self.upsert_position(record)

    def sync_position_from_ledger(self, record: PositionRiskRecord) -> None:
        """
        Синхронизировать позицию из `RiskLedger`.

        Это единственный допустимый путь обновления риск-среза портфеля.
        Exposure считается по тем же `PositionRiskRecord`, которые пришли из ledger.
        """
        self._positions[record.position_id] = record

    def upsert_position(self, record: PositionRiskRecord) -> None:
        """Совместимый alias к явному sync-контракту через RiskLedger."""
        self.sync_position_from_ledger(record)

    def release_position_from_ledger(self, position_id: str) -> PositionRiskRecord:
        """Удалить позицию по факту release из `RiskLedger`."""
        return self.remove_position(position_id)

    def remove_position(self, position_id: str) -> PositionRiskRecord:
        """
        Удалить позицию из snapshot.

        Raises:
            PortfolioPositionNotFoundError: Если позиция отсутствует.
        """
        record = self._positions.pop(position_id, None)
        if record is None:
            raise PortfolioPositionNotFoundError(
                f"Позиция {position_id} не найдена в PortfolioState"
            )
        return record

    def get_position(self, position_id: str) -> PositionRiskRecord:
        """
        Получить позицию из snapshot.

        Raises:
            PortfolioPositionNotFoundError: Если позиция отсутствует.
        """
        record = self._positions.get(position_id)
        if record is None:
            raise PortfolioPositionNotFoundError(
                f"Позиция {position_id} не найдена в PortfolioState"
            )
        return record

    def list_positions(self) -> tuple[PositionRiskRecord, ...]:
        """Получить все открытые позиции как неизменяемый набор записей."""
        return tuple(self._positions.values())

    def snapshot(self) -> PortfolioSnapshot:
        """Собрать агрегированный snapshot открытых позиций."""
        positions = tuple(self._positions.values())
        total_long_exposure_usd = Decimal("0")
        total_short_exposure_usd = Decimal("0")
        total_risk_usd = Decimal("0")
        total_risk_r = Decimal("0")

        for record in positions:
            exposure_usd = record.entry_price * record.quantity
            total_risk_usd += record.current_risk_usd
            total_risk_r += record.current_risk_r
            if record.side is PositionSide.LONG:
                total_long_exposure_usd += exposure_usd
            else:
                total_short_exposure_usd += exposure_usd

        return PortfolioSnapshot(
            positions=positions,
            position_count=len(positions),
            total_exposure_usd=total_long_exposure_usd + total_short_exposure_usd,
            total_long_exposure_usd=total_long_exposure_usd,
            total_short_exposure_usd=total_short_exposure_usd,
            total_risk_usd=total_risk_usd,
            total_risk_r=total_risk_r,
        )

    def assert_position_matches_ledger(self, record: PositionRiskRecord) -> None:
        """
        Проверить, что локальный snapshot позиции совпадает с записью ledger.

        Этот guard делает контракт `RiskLedger -> PortfolioState` явным и проверяемым.
        """
        current = self.get_position(record.position_id)
        if current != record:
            raise PortfolioLedgerSyncError(
                f"PortfolioState рассинхронизирован с RiskLedger по позиции {record.position_id}"
            )

    def assert_total_risk_matches_ledger(self, total_risk_r: Decimal) -> None:
        """Проверить, что агрегированный риск snapshot совпадает с total risk ledger."""
        snapshot = self.snapshot()
        if snapshot.total_risk_r != total_risk_r:
            raise PortfolioLedgerSyncError(
                "PortfolioState рассинхронизирован с RiskLedger по агрегированному риску"
            )

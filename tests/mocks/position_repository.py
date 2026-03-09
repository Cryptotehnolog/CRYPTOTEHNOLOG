"""
In-Memory Position Repository — Заглушка для тестирования.

Хранит позиции в словаре (в памяти) для быстрых изолированных тестов.
"""

from typing import Any

from cryptotechnolog.core.interfaces import PositionRepository


class InMemoryPositionRepository:
    """
    In-memory реализация PositionRepository для тестирования.
    """

    def __init__(self) -> None:
        """Инициализировать in-memory хранилище."""
        self._positions: dict[str, dict[str, Any]] = {}

    async def save(self, position: dict[str, Any]) -> None:
        """Сохранить позицию."""
        position_id = position.get("id")
        if position_id:
            self._positions[position_id] = position.copy()

    async def find_by_id(self, position_id: str) -> dict[str, Any] | None:
        """Найти позицию по ID."""
        return self._positions.get(position_id)

    async def find_by_symbol(self, symbol: str) -> dict[str, Any] | None:
        """Найти позицию по символу."""
        for position in self._positions.values():
            if position.get("symbol") == symbol and position.get("status") == "open":
                return position.copy()
        return None

    async def find_all(self) -> list[dict[str, Any]]:
        """Найти все открытые позиции."""
        return [
            position.copy()
            for position in self._positions.values()
            if position.get("status") == "open"
        ]

    async def update_pnl(self, position_id: str, pnl: float) -> bool:
        """Обновить PnL позиции."""
        if position_id in self._positions:
            self._positions[position_id]["pnl"] = pnl
            return True
        return False

    async def close(self, position_id: str) -> bool:
        """Закрыть позицию."""
        if position_id in self._positions:
            self._positions[position_id]["status"] = "closed"
            return True
        return False

    # ==================== Утилиты для тестов ====================

    def clear(self) -> None:
        """Очистить все позиции."""
        self._positions.clear()

    def count(self) -> int:
        """Количество позиций."""
        return len(self._positions)

    def seed(self, positions: list[dict[str, Any]]) -> None:
        """Заполнить тестовыми данными."""
        for position in positions:
            position_id = position.get("id")
            if position_id:
                self._positions[position_id] = position.copy()

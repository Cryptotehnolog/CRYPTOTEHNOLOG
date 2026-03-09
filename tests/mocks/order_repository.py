"""
In-Memory Order Repository — Заглушка для тестирования.

Хранит ордера в словаре (в памяти) для быстрых изолированных тестов.
"""

from typing import Any


class InMemoryOrderRepository:
    """
    In-memory реализация OrderRepository для тестирования.

    Хранит данные в словаре, не требует БД.
    """

    def __init__(self) -> None:
        """Инициализировать in-memory хранилище."""
        self._orders: dict[str, dict[str, Any]] = {}

    async def save(self, order: dict[str, Any]) -> None:
        """Сохранить ордер."""
        order_id = order.get("id")
        if order_id:
            self._orders[order_id] = order.copy()

    async def find_by_id(self, order_id: str) -> dict[str, Any] | None:
        """Найти ордер по ID."""
        return self._orders.get(order_id)

    async def find_by_symbol(self, symbol: str) -> list[dict[str, Any]]:
        """Найти все ордера по символу."""
        return [order.copy() for order in self._orders.values() if order.get("symbol") == symbol]

    async def find_open_orders(self, symbol: str | None = None) -> list[dict[str, Any]]:
        """Найти открытые ордера."""
        open_statuses = ("open", "pending")
        result = []
        for order in self._orders.values():
            if order.get("status") in open_statuses and (
                symbol is None or order.get("symbol") == symbol
            ):
                result.append(order.copy())
        return result

    async def update_status(self, order_id: str, status: str) -> bool:
        """Обновить статус ордера."""
        if order_id in self._orders:
            self._orders[order_id]["status"] = status
            return True
        return False

    async def delete(self, order_id: str) -> bool:
        """Удалить ордер."""
        if order_id in self._orders:
            del self._orders[order_id]
            return True
        return False

    # ==================== Утилиты для тестов ====================

    def clear(self) -> None:
        """Очистить все ордера."""
        self._orders.clear()

    def count(self) -> int:
        """Количество ордеров."""
        return len(self._orders)

    def seed(self, orders: list[dict[str, Any]]) -> None:
        """Заполнить тестовыми данными."""
        for order in orders:
            order_id = order.get("id")
            if order_id:
                self._orders[order_id] = order.copy()

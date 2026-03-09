"""
In-Memory Risk Limit Repository — Заглушка для тестирования.

Хранит лимиты риска в словаре (в памяти).
"""

from typing import Any

from cryptotechnolog.core.interfaces import RiskLimitRepository


class InMemoryRiskLimitRepository:
    """
    In-memory реализация RiskLimitRepository для тестирования.
    """

    def __init__(self) -> None:
        """Инициализировать in-memory хранилище."""
        self._limits: dict[str, dict[str, Any]] = {}

    async def get_limits(self, account_id: str) -> dict[str, Any] | None:
        """Получить лимиты для аккаунта."""
        return self._limits.get(account_id)

    async def save_limits(self, account_id: str, limits: dict[str, Any]) -> None:
        """Сохранить лимиты для аккаунта."""
        self._limits[account_id] = limits.copy()

    async def update_current_exposure(self, account_id: str, exposure: dict[str, Any]) -> None:
        """Обновить текущую экспозицию."""
        if account_id in self._limits:
            self._limits[account_id]["current_exposure"] = exposure
        else:
            self._limits[account_id] = {"current_exposure": exposure}

    # ==================== Утилиты для тестов ====================

    def clear(self) -> None:
        """Очистить все лимиты."""
        self._limits.clear()

    def seed(self, account_id: str, limits: dict[str, Any]) -> None:
        """Заполнить тестовыми данными."""
        self._limits[account_id] = limits.copy()

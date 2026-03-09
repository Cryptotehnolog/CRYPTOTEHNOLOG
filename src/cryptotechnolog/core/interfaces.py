"""
Core Interfaces — Абстракции для обеспечения тестируемости и заменяемости.

Содержит Protocol (интерфейсы) для:
- Logger — абстракция логгера
- Repository — абстракции доступа к данным

Принципы:
- Dependency Inversion — зависимости от абстракций, а не от конкретных реализаций
- Interface Segregation — маленькие специфичные интерфейсы
"""

from typing import Any, Protocol

# ==================== Logger Interface ====================


class Logger(Protocol):
    """
    Протокол логгера для обеспечения тестируемости.

    Позволяет подменять реализацию логгера на MockLogger в тестах.
    """

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None: ...

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None: ...

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None: ...

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None: ...

    def critical(self, msg: str, *args: Any, **kwargs: Any) -> None: ...

    def exception(self, msg: str, *args: Any, **kwargs: Any) -> None: ...

    def bind(self, **kwargs: Any) -> "Logger": ...


# ==================== Repository Interfaces ====================


class OrderRepository(Protocol):
    """
    Протокол репозитория ордеров.

    Абстрагирует доступ к данным ордеров,
    позволяя подменять реализацию (PostgreSQL, SQLite в памяти, мок).
    """

    async def save(self, order: dict[str, Any]) -> None: ...

    """Сохранить ордер в хранилище."""

    async def find_by_id(self, order_id: str) -> dict[str, Any] | None: ...

    """Найти ордер по ID."""

    async def find_by_symbol(self, symbol: str) -> list[dict[str, Any]]: ...

    """Найти все ордера по символу."""

    async def find_open_orders(self, symbol: str | None = None) -> list[dict[str, Any]]: ...

    """Найти открытые ордера (опционально по символу)."""

    async def update_status(self, order_id: str, status: str) -> bool: ...

    """Обновить статус ордера."""

    async def delete(self, order_id: str) -> bool: ...

    """Удалить ордер."""


class PositionRepository(Protocol):
    """
    Протокол репозитория позиций.

    Абстрагирует доступ к данным позиций.
    """

    async def save(self, position: dict[str, Any]) -> None: ...

    """Сохранить позицию."""

    async def find_by_id(self, position_id: str) -> dict[str, Any] | None: ...

    """Найти позицию по ID."""

    async def find_by_symbol(self, symbol: str) -> dict[str, Any] | None: ...

    """Найти позицию по символу."""

    async def find_all(self) -> list[dict[str, Any]]: ...

    """Найти все позиции."""

    async def update_pnl(self, position_id: str, pnl: float) -> bool: ...

    """Обновить PnL позиции."""

    async def close(self, position_id: str) -> bool: ...

    """Закрыть позицию."""


class RiskLimitRepository(Protocol):
    """
    Протокол репозитория лимитов риска.

    Абстрагирует доступ к лимитам риска.
    """

    async def get_limits(self, account_id: str) -> dict[str, Any] | None: ...

    """Получить лимиты для аккаунта."""

    async def save_limits(self, account_id: str, limits: dict[str, Any]) -> None: ...

    """Сохранить лимиты для аккаунта."""

    async def update_current_exposure(self, account_id: str, exposure: dict[str, Any]) -> None: ...

    """Обновить текущую экспозицию."""

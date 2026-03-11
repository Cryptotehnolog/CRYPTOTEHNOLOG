"""
Adapters — Реализации интерфейсов.

Содержит конкретные реализации Protocol из interfaces.py:
- StructlogAdapter — адаптер для structlog
- Concrete repositories — реализации для PostgreSQL
"""

from typing import Any, cast

import structlog

# ==================== Logger Adapter ====================


class StructlogAdapter:
    """
    Адаптер для structlog.

    Реализует интерфейс Logger, используя structlog внутри.
    """

    def __init__(self, name: str | None = None) -> None:
        """
        Инициализировать адаптер.

        Аргументы:
            name: Имя логгера (опционально)
        """
        self._logger = structlog.get_logger(name)

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._logger.debug(msg, *args, **kwargs)

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._logger.info(msg, *args, **kwargs)

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._logger.warning(msg, *args, **kwargs)

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._logger.error(msg, *args, **kwargs)

    def critical(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._logger.critical(msg, *args, **kwargs)

    def exception(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._logger.exception(msg, *args, **kwargs)

    def bind(self, **kwargs: Any) -> "StructlogAdapter":
        """
        Создать новый логгер с привязанным контекстом.

        Аргументы:
            **kwargs: Контекст для привязки

        Returns:
            Новый StructlogAdapter с привязанным контекстом
        """
        bound_logger = self._logger.bind(**kwargs)
        adapter = StructlogAdapter.__new__(StructlogAdapter)
        adapter._logger = bound_logger
        return adapter


# ==================== Concrete Repositories ====================


class PostgresOrderRepository:
    """
    PostgreSQL реализация OrderRepository.

    Использует пул соединений для доступа к БД.
    """

    def __init__(self, pool: Any) -> None:
        """
        Инициализировать репозиторий.

        Аргументы:
            pool: Пул соединений asyncpg
        """
        self._pool = pool

    async def save(self, order: dict[str, Any]) -> None:
        """Сохранить ордер."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO orders (id, symbol, side, quantity, price, status, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, NOW())
                ON CONFLICT (id) DO UPDATE SET
                    status = EXCLUDED.status,
                    quantity = EXCLUDED.quantity,
                    price = EXCLUDED.price
                """,
                order.get("id"),
                order.get("symbol"),
                order.get("side"),
                order.get("quantity"),
                order.get("price"),
                order.get("status", "open"),
            )

    async def find_by_id(self, order_id: str) -> dict[str, Any] | None:
        """Найти ордер по ID."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM orders WHERE id = $1",
                order_id,
            )
            return dict(row) if row else None

    async def find_by_symbol(self, symbol: str) -> list[dict[str, Any]]:
        """Найти все ордера по символу."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM orders WHERE symbol = $1 ORDER BY created_at DESC",
                symbol,
            )
            return [dict(row) for row in rows]

    async def find_open_orders(self, symbol: str | None = None) -> list[dict[str, Any]]:
        """Найти открытые ордера."""
        async with self._pool.acquire() as conn:
            if symbol:
                rows = await conn.fetch(
                    "SELECT * FROM orders WHERE status IN ('open', 'pending') AND symbol = $1",
                    symbol,
                )
            else:
                rows = await conn.fetch(
                    "SELECT * FROM orders WHERE status IN ('open', 'pending')",
                )
            return [dict(row) for row in rows]

    async def update_status(self, order_id: str, status: str) -> bool:
        """Обновить статус ордера."""
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE orders SET status = $1, updated_at = NOW() WHERE id = $2",
                status,
                order_id,
            )
            return cast("str", result) == "UPDATE 1"

    async def delete(self, order_id: str) -> bool:
        """Удалить ордер."""
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM orders WHERE id = $1",
                order_id,
            )
            return cast("str", result) == "DELETE 1"


class PostgresPositionRepository:
    """
    PostgreSQL реализация PositionRepository.
    """

    def __init__(self, pool: Any) -> None:
        self._pool = pool

    async def save(self, position: dict[str, Any]) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO positions (id, symbol, side, quantity, entry_price, current_price, pnl, status)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (id) DO UPDATE SET
                    current_price = EXCLUDED.current_price,
                    pnl = EXCLUDED.pnl,
                    status = EXCLUDED.status
                """,
                position.get("id"),
                position.get("symbol"),
                position.get("side"),
                position.get("quantity"),
                position.get("entry_price"),
                position.get("current_price"),
                position.get("pnl", 0.0),
                position.get("status", "open"),
            )

    async def find_by_id(self, position_id: str) -> dict[str, Any] | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM positions WHERE id = $1",
                position_id,
            )
            return dict(row) if row else None

    async def find_by_symbol(self, symbol: str) -> dict[str, Any] | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM positions WHERE symbol = $1 AND status = 'open'",
                symbol,
            )
            return dict(row) if row else None

    async def find_all(self) -> list[dict[str, Any]]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM positions WHERE status = 'open'")
            return [dict(row) for row in rows]

    async def update_pnl(self, position_id: str, pnl: float) -> bool:
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE positions SET pnl = $1, updated_at = NOW() WHERE id = $2",
                pnl,
                position_id,
            )
            return cast("str", result) == "UPDATE 1"

    async def close(self, position_id: str) -> bool:
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE positions SET status = 'closed', closed_at = NOW() WHERE id = $1",
                position_id,
            )
            return cast("str", result) == "UPDATE 1"


class PostgresRiskLimitRepository:
    """
    PostgreSQL реализация RiskLimitRepository.
    """

    def __init__(self, pool: Any) -> None:
        self._pool = pool

    async def get_limits(self, account_id: str) -> dict[str, Any] | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM risk_limits WHERE account_id = $1",
                account_id,
            )
            return dict(row) if row else None

    async def save_limits(self, account_id: str, limits: dict[str, Any]) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO risk_limits (account_id, max_position_size, max_daily_loss, max_leverage)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (account_id) DO UPDATE SET
                    max_position_size = EXCLUDED.max_position_size,
                    max_daily_loss = EXCLUDED.max_daily_loss,
                    max_leverage = EXCLUDED.max_leverage
                """,
                account_id,
                limits.get("max_position_size"),
                limits.get("max_daily_loss"),
                limits.get("max_leverage"),
            )

    async def update_current_exposure(self, account_id: str, exposure: dict[str, Any]) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO risk_limits (account_id, current_exposure)
                VALUES ($1, $2)
                ON CONFLICT (account_id) DO UPDATE SET
                    current_exposure = EXCLUDED.current_exposure
                """,
                account_id,
                exposure,
            )

"""
PostgreSQL repository для persistence foundation Risk Engine.

Модуль содержит только инфраструктурную реализацию repository.
Контракты и audit dataclasses вынесены в `persistence_contracts.py`,
чтобы orchestration-слой не тянул зависимость на `asyncpg`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import asyncpg

from .persistence_contracts import (
    ClosedPositionHistoryRecord,
    IRiskPersistenceRepository,
    PositionRiskLedgerAuditRecord,
    RiskCheckAuditRecord,
    TrailingStopMovementRecord,
    TrailingStopSnapshotRecord,
)

if TYPE_CHECKING:
    from .models import PositionRiskRecord


class RiskPersistenceError(Exception):
    """Базовая ошибка persistence-слоя Risk Engine."""

    def __init__(self, operation: str, reason: str) -> None:
        self.operation = operation
        self.reason = reason
        super().__init__(f"Ошибка {operation}: {reason}")


class RiskPersistenceRepository(IRiskPersistenceRepository):
    """
    Тонкий PostgreSQL repository для persistence foundation Risk Engine.

    Важно:
    - работает только с новой доменной моделью Фазы 5;
    - не использует legacy `risk_ledger` из `core/listeners/risk.py`;
    - не содержит orchestration-решений.
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def save_risk_check(self, record: RiskCheckAuditRecord) -> None:
        """Сохранить audit-запись pre-trade risk check."""
        query = """
            INSERT INTO risk_checks (
                order_id,
                symbol,
                system_state,
                decision,
                reason,
                risk_r,
                position_size_usd,
                position_size_base,
                current_total_r,
                max_total_r,
                correlation_with_portfolio,
                recommended_exchange,
                max_size,
                check_duration_ms,
                details,
                created_at
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8,
                $9, $10, $11, $12, $13, $14, $15, $16
            )
        """
        await self._execute(
            "save_risk_check",
            query,
            record.order_id,
            record.symbol,
            record.system_state,
            record.decision,
            record.reason,
            record.risk_r,
            record.position_size_usd,
            record.position_size_base,
            record.current_total_r,
            record.max_total_r,
            record.correlation_with_portfolio,
            record.recommended_exchange,
            record.max_size,
            record.check_duration_ms,
            record.details,
            record.created_at,
        )

    async def upsert_position_risk_record(self, record: PositionRiskRecord) -> None:
        """Сохранить или обновить актуальный snapshot позиционного risk ledger."""
        query = """
            INSERT INTO position_risk_ledger (
                position_id,
                symbol,
                exchange_id,
                strategy_id,
                side,
                entry_price,
                initial_stop,
                current_stop,
                quantity,
                risk_capital_usd,
                initial_risk_usd,
                initial_risk_r,
                current_risk_usd,
                current_risk_r,
                current_price,
                unrealized_pnl_usd,
                unrealized_pnl_percent,
                trailing_state,
                opened_at,
                updated_at
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8,
                $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20
            )
            ON CONFLICT (position_id) DO UPDATE SET
                symbol = EXCLUDED.symbol,
                exchange_id = EXCLUDED.exchange_id,
                strategy_id = EXCLUDED.strategy_id,
                side = EXCLUDED.side,
                entry_price = EXCLUDED.entry_price,
                initial_stop = EXCLUDED.initial_stop,
                current_stop = EXCLUDED.current_stop,
                quantity = EXCLUDED.quantity,
                risk_capital_usd = EXCLUDED.risk_capital_usd,
                initial_risk_usd = EXCLUDED.initial_risk_usd,
                initial_risk_r = EXCLUDED.initial_risk_r,
                current_risk_usd = EXCLUDED.current_risk_usd,
                current_risk_r = EXCLUDED.current_risk_r,
                current_price = EXCLUDED.current_price,
                unrealized_pnl_usd = EXCLUDED.unrealized_pnl_usd,
                unrealized_pnl_percent = EXCLUDED.unrealized_pnl_percent,
                trailing_state = EXCLUDED.trailing_state,
                opened_at = EXCLUDED.opened_at,
                updated_at = EXCLUDED.updated_at
        """
        await self._execute(
            "upsert_position_risk_record",
            query,
            record.position_id,
            record.symbol,
            record.exchange_id,
            record.strategy_id,
            record.side.value,
            record.entry_price,
            record.initial_stop,
            record.current_stop,
            record.quantity,
            record.risk_capital_usd,
            record.initial_risk_usd,
            record.initial_risk_r,
            record.current_risk_usd,
            record.current_risk_r,
            record.current_price,
            record.unrealized_pnl_usd,
            record.unrealized_pnl_percent,
            record.trailing_state.value,
            record.opened_at,
            record.updated_at,
        )

    async def append_position_risk_audit(self, record: PositionRiskLedgerAuditRecord) -> None:
        """Добавить audit-запись изменения позиционного risk ledger."""
        query = """
            INSERT INTO position_risk_ledger_audit (
                position_id,
                symbol,
                operation,
                old_stop,
                new_stop,
                old_risk_r,
                new_risk_r,
                trailing_state,
                reason,
                recorded_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        """
        await self._execute(
            "append_position_risk_audit",
            query,
            record.position_id,
            record.symbol,
            record.operation,
            record.old_stop,
            record.new_stop,
            record.old_risk_r,
            record.new_risk_r,
            record.trailing_state,
            record.reason,
            record.recorded_at,
        )

    async def upsert_trailing_stop_snapshot(self, record: TrailingStopSnapshotRecord) -> None:
        """Сохранить или обновить актуальный snapshot trailing stop."""
        query = """
            INSERT INTO trailing_stops (
                position_id,
                symbol,
                current_stop,
                previous_stop,
                trailing_state,
                last_evaluation_type,
                last_tier,
                last_mode,
                last_pnl_r,
                last_risk_before,
                last_risk_after,
                last_reason,
                last_evaluated_at,
                updated_at
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7,
                $8, $9, $10, $11, $12, $13, $14
            )
            ON CONFLICT (position_id) DO UPDATE SET
                symbol = EXCLUDED.symbol,
                current_stop = EXCLUDED.current_stop,
                previous_stop = EXCLUDED.previous_stop,
                trailing_state = EXCLUDED.trailing_state,
                last_evaluation_type = EXCLUDED.last_evaluation_type,
                last_tier = EXCLUDED.last_tier,
                last_mode = EXCLUDED.last_mode,
                last_pnl_r = EXCLUDED.last_pnl_r,
                last_risk_before = EXCLUDED.last_risk_before,
                last_risk_after = EXCLUDED.last_risk_after,
                last_reason = EXCLUDED.last_reason,
                last_evaluated_at = EXCLUDED.last_evaluated_at,
                updated_at = EXCLUDED.updated_at
        """
        await self._execute(
            "upsert_trailing_stop_snapshot",
            query,
            record.position_id,
            record.symbol,
            record.current_stop,
            record.previous_stop,
            record.trailing_state,
            record.last_evaluation_type,
            record.last_tier,
            record.last_mode,
            record.last_pnl_r,
            record.last_risk_before,
            record.last_risk_after,
            record.last_reason,
            record.last_evaluated_at,
            record.updated_at,
        )

    async def append_trailing_stop_movement(self, record: TrailingStopMovementRecord) -> None:
        """Добавить audit-запись отдельной оценки/движения trailing stop."""
        query = """
            INSERT INTO trailing_stop_movements (
                position_id,
                symbol,
                old_stop,
                new_stop,
                pnl_r,
                evaluation_type,
                tier,
                mode,
                system_state,
                risk_before,
                risk_after,
                should_execute,
                reason,
                created_at
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7,
                $8, $9, $10, $11, $12, $13, $14
            )
        """
        await self._execute(
            "append_trailing_stop_movement",
            query,
            record.position_id,
            record.symbol,
            record.old_stop,
            record.new_stop,
            record.pnl_r,
            record.evaluation_type,
            record.tier,
            record.mode,
            record.system_state,
            record.risk_before,
            record.risk_after,
            record.should_execute,
            record.reason,
            record.created_at,
        )

    async def append_closed_position_history(self, record: ClosedPositionHistoryRecord) -> None:
        """Сохранить каноническую запись истории закрытой позиции."""
        query = """
            INSERT INTO closed_position_history (
                position_id,
                symbol,
                exchange_id,
                strategy_id,
                side,
                entry_price,
                quantity,
                initial_stop,
                current_stop,
                trailing_state,
                opened_at,
                closed_at,
                exit_price,
                exit_reason,
                realized_pnl_r,
                realized_pnl_usd,
                realized_pnl_percent
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17
            )
            ON CONFLICT (position_id) DO UPDATE SET
                symbol = EXCLUDED.symbol,
                exchange_id = EXCLUDED.exchange_id,
                strategy_id = EXCLUDED.strategy_id,
                side = EXCLUDED.side,
                entry_price = EXCLUDED.entry_price,
                quantity = EXCLUDED.quantity,
                initial_stop = EXCLUDED.initial_stop,
                current_stop = EXCLUDED.current_stop,
                trailing_state = EXCLUDED.trailing_state,
                opened_at = EXCLUDED.opened_at,
                closed_at = EXCLUDED.closed_at,
                exit_price = EXCLUDED.exit_price,
                exit_reason = EXCLUDED.exit_reason,
                realized_pnl_r = EXCLUDED.realized_pnl_r,
                realized_pnl_usd = EXCLUDED.realized_pnl_usd,
                realized_pnl_percent = EXCLUDED.realized_pnl_percent
        """
        await self._execute(
            "append_closed_position_history",
            query,
            record.position_id,
            record.symbol,
            record.exchange_id,
            record.strategy_id,
            record.side,
            record.entry_price,
            record.quantity,
            record.initial_stop,
            record.current_stop,
            record.trailing_state,
            record.opened_at,
            record.closed_at,
            record.exit_price,
            record.exit_reason,
            record.realized_pnl_r,
            record.realized_pnl_usd,
            record.realized_pnl_percent,
        )

    async def list_closed_position_history(
        self,
        *,
        limit: int | None = None,
    ) -> tuple[ClosedPositionHistoryRecord, ...]:
        """Получить history закрытых позиций в порядке от новых к старым."""
        query = """
            SELECT
                position_id,
                symbol,
                exchange_id,
                strategy_id,
                side,
                entry_price,
                quantity,
                initial_stop,
                current_stop,
                trailing_state,
                opened_at,
                closed_at,
                exit_price,
                exit_reason,
                realized_pnl_r,
                realized_pnl_usd,
                realized_pnl_percent
            FROM closed_position_history
            ORDER BY closed_at DESC, position_id DESC
        """
        if limit is not None:
            query += " LIMIT $1"
            rows = await self._fetch("list_closed_position_history", query, limit)
        else:
            rows = await self._fetch("list_closed_position_history", query)

        return tuple(
            ClosedPositionHistoryRecord(
                position_id=row["position_id"],
                symbol=row["symbol"],
                exchange_id=row["exchange_id"],
                strategy_id=row["strategy_id"],
                side=row["side"],
                entry_price=row["entry_price"],
                quantity=row["quantity"],
                initial_stop=row["initial_stop"],
                current_stop=row["current_stop"],
                trailing_state=row["trailing_state"],
                opened_at=row["opened_at"],
                closed_at=row["closed_at"],
                exit_price=row["exit_price"],
                exit_reason=row["exit_reason"],
                realized_pnl_r=row["realized_pnl_r"],
                realized_pnl_usd=row["realized_pnl_usd"],
                realized_pnl_percent=row["realized_pnl_percent"],
            )
            for row in rows
        )

    async def delete_position_risk_record(self, position_id: str) -> None:
        """Удалить snapshot закрытой позиции из position_risk_ledger."""
        await self._execute(
            "delete_position_risk_record",
            "DELETE FROM position_risk_ledger WHERE position_id = $1",
            position_id,
        )

    async def delete_trailing_stop_snapshot(self, position_id: str) -> None:
        """Удалить trailing snapshot закрытой позиции."""
        await self._execute(
            "delete_trailing_stop_snapshot",
            "DELETE FROM trailing_stops WHERE position_id = $1",
            position_id,
        )

    async def _execute(self, operation: str, query: str, *args: Any) -> None:
        """Выполнить запрос и обернуть ошибки в доменное исключение persistence-слоя."""
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(query, *args)
        except asyncpg.PostgresError as error:
            raise RiskPersistenceError(operation, str(error)) from error
        except Exception as error:
            raise RiskPersistenceError(operation, str(error)) from error

    async def _fetch(self, operation: str, query: str, *args: Any) -> list[Any]:
        """Выполнить query/fetch и обернуть ошибки в доменное исключение persistence-слоя."""
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(query, *args)
                return list(rows)
        except asyncpg.PostgresError as error:
            raise RiskPersistenceError(operation, str(error)) from error
        except Exception as error:
            raise RiskPersistenceError(operation, str(error)) from error

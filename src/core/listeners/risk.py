"""
Risk Listener for Event Bus.

Обрабатывает события, связанные с Risk Management:
- Проверка лимитов при создании ордеров
- Отслеживание позиций для risk limits
- Запись risk events в БД
"""

from __future__ import annotations

from datetime import UTC, datetime
import json
import logging
from typing import TYPE_CHECKING, Any

from src.core.database import get_db_pool
from src.core.listeners.base import BaseListener, ListenerConfig

if TYPE_CHECKING:
    from src.core.event import Event

logger = logging.getLogger(__name__)


class RiskListener(BaseListener):
    """
    Listener для событий Risk Management.

    Обрабатывает:
    - ORDER_SUBMITTED: проверяет risk limits
    - ORDER_FILLED: обновляет текущие risk показатели
    - POSITION_OPENED/POSITION_CLOSED: отслеживает позиции
    - RISK_VIOLATION: записывает нарушения
    """

    def __init__(self, config: ListenerConfig | None = None):
        """Инициализировать Risk Listener."""
        if config is None:
            config = ListenerConfig(
                name="risk_check_listener",
                event_types=[
                    "ORDER_SUBMITTED",
                    "ORDER_FILLED",
                    "ORDER_REJECTED",
                    "POSITION_OPENED",
                    "POSITION_CLOSED",
                    "POSITION_SIZE_EXCEEDED",
                    "DRAWDOWN_EXCEEDED",
                    "DAILY_LOSS_LIMIT",
                    "RISK_VIOLATION",
                ],
                priority=90,
            )
        super().__init__(config)

    async def _process_event(self, event: Event) -> None:
        """
        Обработать событие Risk.

        Аргументы:
            event: Событие для обработки
        """
        handlers = {
            "ORDER_SUBMITTED": self._handle_order_submitted,
            "ORDER_FILLED": self._handle_order_filled,
            "ORDER_REJECTED": self._handle_order_rejected,
            "POSITION_OPENED": self._handle_position_opened,
            "POSITION_CLOSED": self._handle_position_closed,
            "POSITION_SIZE_EXCEEDED": self._handle_risk_violation,
            "DRAWDOWN_EXCEEDED": self._handle_risk_violation,
            "DAILY_LOSS_LIMIT": self._handle_risk_violation,
            "RISK_VIOLATION": self._handle_risk_violation,
        }

        handler = handlers.get(event.event_type)
        if handler:
            await handler(event)
        else:
            logger.warning(f"[{self.name}] No handler for event type: {event.event_type}")

    async def _handle_order_submitted(self, event: Event) -> None:
        """Обработать событие ORDER_SUBMITTED - записать в ledger."""
        payload = event.payload
        symbol = payload.get("symbol")
        side = payload.get("side")
        size = payload.get("size", 0)
        price = payload.get("price", 0)
        risk_amount = size * price if price else 0

        logger.info(
            f"[{self.name}] Order submitted: {symbol} {side} {size} @ {price} "
            f"(risk: ${risk_amount})"
        )

        # Обновление risk ledger
        await self._update_risk_ledger(
            limit_type="ORDER_SIZE",
            value=risk_amount,
        )

    async def _handle_order_filled(self, event: Event) -> None:
        """Обработать событие ORDER_FILLED - обновить позиции и P&L."""
        payload = event.payload
        symbol = payload.get("symbol")
        side = payload.get("side")
        size = payload.get("filled_size", 0)
        price = payload.get("price", 0)

        logger.info(
            f"[{self.name}] Order filled: {symbol} {side} {size} @ {price}"
        )

        # Обновление daily summary
        await self._update_daily_summary(
            symbol=symbol,
            orders_submitted=0,
            orders_filled=1,
            pnl=payload.get("realized_pnl", 0),
        )

    async def _handle_order_rejected(self, event: Event) -> None:
        """Обработать событие ORDER_REJECTED."""
        payload = event.payload
        symbol = payload.get("symbol")
        reason = payload.get("reason", "unknown")

        logger.warning(f"[{self.name}] Order rejected: {symbol} - {reason}")

        # Запись risk event
        await self._record_risk_event(
            event_type="ORDER_REJECTED",
            symbol=symbol,
            side=payload.get("side"),
            size=payload.get("size"),
            price=payload.get("price"),
            risk_amount=payload.get("size", 0) * payload.get("price", 0),
            allowed=False,
            reason=reason,
            rejected_order_id=payload.get("order_id"),
            metadata=event.metadata,
        )

    async def _handle_position_opened(self, event: Event) -> None:
        """Обработать событие POSITION_OPENED."""
        payload = event.payload
        symbol = payload.get("symbol")
        side = payload.get("side")
        size = payload.get("size", 0)
        entry_price = payload.get("entry_price", 0)
        position_id = payload.get("position_id")

        logger.info(
            f"[{self.name}] Position opened: {position_id} {symbol} {side} {size} @ {entry_price}"
        )

        # Обновление risk ledger
        risk_amount = size * entry_price
        await self._update_risk_ledger(
            limit_type="POSITION_SIZE",
            value=risk_amount,
        )

    async def _handle_position_closed(self, event: Event) -> None:
        """Обработать событие POSITION_CLOSED."""
        payload = event.payload
        symbol = payload.get("symbol")
        position_id = payload.get("position_id")
        realized_pnl = payload.get("realized_pnl", 0)

        logger.info(
            f"[{self.name}] Position closed: {position_id} {symbol} PnL: ${realized_pnl}"
        )

        # Обновление daily summary
        await self._update_daily_summary(
            symbol=symbol,
            orders_filled=0,
            pnl=realized_pnl,
        )

    async def _handle_risk_violation(self, event: Event) -> None:
        """Обработать событие RISK_VIOLATION."""
        payload = event.payload
        event_type = event.event_type
        symbol = payload.get("symbol")
        limit_type = payload.get("limit_type")
        current_value = payload.get("current_value", 0)
        max_value = payload.get("max_value", 0)
        reason = payload.get("reason", "Risk limit exceeded")

        logger.warning(
            f"[{self.name}] Risk violation: {event_type} - {symbol} "
            f"({current_value} > {max_value})"
        )

        # Запись risk event
        await self._record_risk_event(
            event_type=event_type,
            symbol=symbol,
            side=payload.get("side"),
            size=payload.get("size"),
            price=payload.get("price"),
            risk_amount=current_value,
            allowed=False,
            reason=reason,
            rejected_order_id=payload.get("order_id"),
            metadata={
                **event.metadata,
                "limit_type": limit_type,
                "max_value": max_value,
            },
        )

    async def _record_risk_event(
        self,
        event_type: str,
        symbol: str | None,
        side: str | None,
        size: float | None,
        price: float | None,
        risk_amount: float,
        allowed: bool,
        reason: str,
        rejected_order_id: str | None,
        metadata: dict[str, Any],
    ) -> None:
        """Записать risk event в БД."""
        pool = None
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO risk_events
                    (event_type, symbol, side, size, price, risk_amount, allowed,
                     reason, rejected_order_id, metadata)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    """,
                    event_type,
                    symbol,
                    side,
                    size,
                    price,
                    risk_amount,
                    allowed,
                    reason,
                    rejected_order_id,
                    json.dumps(metadata),
                )
        except Exception as e:
            logger.error(f"[{self.name}] Failed to record risk event: {e}")

    async def _update_risk_ledger(
        self,
        limit_type: str,
        value: float,
    ) -> None:
        """Обновить risk ledger в БД."""
        pool = None
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO risk_ledger (limit_type, limit_value, current_value, updated_at)
                    VALUES ($1,
                        (SELECT max_value FROM risk_limits WHERE limit_type = $1 LIMIT 1),
                        $2,
                        NOW())
                    ON CONFLICT (limit_type) DO UPDATE SET
                        current_value = risk_ledger.current_value + $2,
                        updated_at = NOW()
                    """,
                    limit_type,
                    value,
                )
        except Exception as e:
            logger.error(f"[{self.name}] Failed to update risk ledger: {e}")

    async def _update_daily_summary(
        self,
        symbol: str,
        orders_submitted: int = 0,
        orders_filled: int = 0,
        pnl: float = 0,
    ) -> None:
        """Обновить daily risk summary."""
        pool = None
        try:
            pool = await get_db_pool()
            today = datetime.now(UTC).date()

            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO daily_risk_summary
                    (trade_date, total_orders_submitted, total_risk_amount, last_updated)
                    VALUES ($1, $2, $3, NOW())
                    ON CONFLICT (trade_date) DO UPDATE SET
                        total_orders_submitted = daily_risk_summary.total_orders_submitted + $2,
                        total_risk_amount = daily_risk_summary.total_risk_amount + $3,
                        last_updated = NOW()
                    """,
                    today,
                    orders_submitted,
                    abs(pnl) if pnl < 0 else 0,
                )
        except Exception as e:
            logger.error(f"[{self.name}] Failed to update daily summary: {e}")

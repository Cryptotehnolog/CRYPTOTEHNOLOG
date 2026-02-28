"""
Metrics Listener for Event Bus.

Обрабатывает события для сбора метрик:
- Производительность ордеров (latency, fill rate)
- Системные метрики
- Бизнес метрики
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from src.core.database import get_db_pool
from src.core.event import Event
from src.core.listeners.base import BaseListener, ListenerConfig


logger = logging.getLogger(__name__)


class MetricsListener(BaseListener):
    """
    Listener для сбора метрик.

    Собирает метрики из различных событий:
    - ORDER_FILLED: latency, fill rate
    - POSITION_CLOSED: P&L метрики
    - RISK_VIOLATION: risk метрики
    - SYSTEM_*: системные метрики
    """

    def __init__(self, config: ListenerConfig | None = None):
        """Инициализировать Metrics Listener."""
        if config is None:
            config = ListenerConfig(
                name="metrics_listener",
                event_types=[
                    "ORDER_SUBMITTED",
                    "ORDER_FILLED",
                    "ORDER_CANCELLED",
                    "ORDER_REJECTED",
                    "POSITION_OPENED",
                    "POSITION_CLOSED",
                    "RISK_VIOLATION",
                    "SYSTEM_BOOT",
                    "SYSTEM_READY",
                    "SYSTEM_HALT",
                    "SYSTEM_SHUTDOWN",
                ],
                priority=10,  # Низкий приоритет - не блокирует другие listeners
            )
        super().__init__(config)

    async def _process_event(self, event: Event) -> None:
        """
        Обработать событие для метрик.

        Аргументы:
            event: Событие для обработки
        """
        handlers = {
            "ORDER_SUBMITTED": self._handle_order_submitted,
            "ORDER_FILLED": self._handle_order_filled,
            "ORDER_CANCELLED": self._handle_order_cancelled,
            "ORDER_REJECTED": self._handle_order_rejected,
            "POSITION_OPENED": self._handle_position_opened,
            "POSITION_CLOSED": self._handle_position_closed,
            "RISK_VIOLATION": self._handle_risk_violation,
            "SYSTEM_BOOT": self._handle_system_boot,
            "SYSTEM_READY": self._handle_system_ready,
            "SYSTEM_HALT": self._handle_system_halt,
            "SYSTEM_SHUTDOWN": self._handle_system_shutdown,
        }

        handler = handlers.get(event.event_type)
        if handler:
            await handler(event)
        else:
            logger.debug(f"[{self.name}] No handler for event type: {event.event_type}")

    async def _handle_order_submitted(self, event: Event) -> None:
        """Обработать ORDER_SUBMITTED - записать submission latency metric."""
        payload = event.payload
        submit_time = payload.get("submit_time")
        receive_time = datetime.now(timezone.utc)

        if submit_time:
            latency_ms = (receive_time - submit_time).total_seconds() * 1000
            await self._record_performance_metric(
                metric_category="order_latency",
                metric_name="order_submission_latency_ms",
                value=latency_ms,
                tags={"symbol": payload.get("symbol"), "side": payload.get("side")},
            )

    async def _handle_order_filled(self, event: Event) -> None:
        """Обработать ORDER_FILLED - записать fill latency и fill rate."""
        payload = event.payload
        symbol = payload.get("symbol")

        # Fill latency
        submit_time = payload.get("submit_time")
        fill_time = payload.get("fill_time")
        if submit_time and fill_time:
            latency_ms = (fill_time - submit_time).total_seconds() * 1000
            await self._record_performance_metric(
                metric_category="order_latency",
                metric_name="order_fill_latency_ms",
                value=latency_ms,
                tags={"symbol": symbol},
            )

        # Fill rate (успешные fills)
        await self._record_performance_metric(
            metric_category="fill_rate",
            metric_name="orders_filled_total",
            value=1,
            tags={"symbol": symbol},
        )

        # Size filled
        filled_size = payload.get("filled_size", 0)
        if filled_size:
            await self._record_performance_metric(
                metric_category="throughput",
                metric_name="volume_filled",
                value=filled_size,
                tags={"symbol": symbol},
            )

    async def _handle_order_cancelled(self, event: Event) -> None:
        """Обработать ORDER_CANCELLED."""
        payload = event.payload
        symbol = payload.get("symbol")

        await self._record_performance_metric(
            metric_category="fill_rate",
            metric_name="orders_cancelled_total",
            value=1,
            tags={"symbol": symbol},
        )

    async def _handle_order_rejected(self, event: Event) -> None:
        """Обработать ORDER_REJECTED - записать rejection rate."""
        payload = event.payload
        symbol = payload.get("symbol")

        await self._record_performance_metric(
            metric_category="error_rate",
            metric_name="orders_rejected_total",
            value=1,
            tags={"symbol": symbol},
        )

    async def _handle_position_opened(self, event: Event) -> None:
        """Обработать POSITION_OPENED."""
        payload = event.payload
        symbol = payload.get("symbol")
        size = payload.get("size", 0)
        leverage = payload.get("leverage", 1.0)

        # Exposure
        exposure = size * leverage
        await self._record_performance_metric(
            metric_category="resource_usage",
            metric_name="position_exposure",
            value=exposure,
            tags={"symbol": symbol},
        )

    async def _handle_position_closed(self, event: Event) -> None:
        """Обработать POSITION_CLOSED - записать P&L."""
        payload = event.payload
        symbol = payload.get("symbol")
        realized_pnl = payload.get("realized_pnl", 0)

        await self._record_performance_metric(
            metric_category="throughput",
            metric_name="realized_pnl",
            value=realized_pnl,
            tags={"symbol": symbol},
        )

    async def _handle_risk_violation(self, event: Event) -> None:
        """Обработать RISK_VIOLATION - записать error rate."""
        payload = event.payload
        symbol = payload.get("symbol")
        event_type = event.event_type

        await self._record_performance_metric(
            metric_category="error_rate",
            metric_name="risk_violations_total",
            value=1,
            tags={"symbol": symbol, "violation_type": event_type},
        )

    async def _handle_system_boot(self, event: Event) -> None:
        """Обработать SYSTEM_BOOT."""
        await self._record_system_metric(
            metric_name="system_state",
            value=1,
            tags={"state": "boot"},
        )

    async def _handle_system_ready(self, event: Event) -> None:
        """Обработать SYSTEM_READY."""
        await self._record_system_metric(
            metric_name="system_state",
            value=1,
            tags={"state": "ready"},
        )

    async def _handle_system_halt(self, event: Event) -> None:
        """Обработать SYSTEM_HALT."""
        await self._record_system_metric(
            metric_name="system_state",
            value=1,
            tags={"state": "halt"},
        )

    async def _handle_system_shutdown(self, event: Event) -> None:
        """Обработать SYSTEM_SHUTDOWN."""
        await self._record_system_metric(
            metric_name="system_state",
            value=1,
            tags={"state": "shutdown"},
        )

    async def _record_performance_metric(
        self,
        metric_category: str,
        metric_name: str,
        value: float,
        tags: dict[str, str] | None = None,
    ) -> None:
        """Записать метрику производительности в БД."""
        pool = None
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO performance_metrics
                    (metric_category, metric_name, value, tags)
                    VALUES ($1, $2, $3, $4)
                    """,
                    metric_category,
                    metric_name,
                    value,
                    json.dumps(tags) if tags else None,
                )
        except Exception as e:
            logger.debug(f"[{self.name}] Failed to record performance metric: {e}")

    async def _record_system_metric(
        self,
        metric_name: str,
        value: float,
        tags: dict[str, str] | None = None,
    ) -> None:
        """Записать системную метрику в БД."""
        pool = None
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO system_metrics
                    (metric_name, metric_type, value, labels)
                    VALUES ($1, 'gauge', $2, $3)
                    """,
                    metric_name,
                    value,
                    json.dumps(tags) if tags else None,
                )
        except Exception as e:
            logger.debug(f"[{self.name}] Failed to record system metric: {e}")

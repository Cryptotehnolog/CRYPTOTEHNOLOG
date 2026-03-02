"""
Audit Listener for Event Bus.

Обрабатывает все события для аудита:
- Записывает все события в audit_events таблицу
- Обеспечивает полный trail для compliance
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from ..database import get_db_pool
from .base import BaseListener, ListenerConfig

if TYPE_CHECKING:
    from ..event import Event

logger = logging.getLogger(__name__)


class AuditListener(BaseListener):
    """
    Listener для аудита всех событий.

    Записывает все события в БД для:
    - Compliance и regulatory requirements
    - Forensic analysis
    - Debugging и troubleshooting
    - Business intelligence
    """

    def __init__(self, config: ListenerConfig | None = None):
        """Инициализировать Audit Listener."""
        if config is None:
            config = ListenerConfig(
                name="audit_listener",
                event_types=["*"],  # Все события
                priority=50,
            )
        super().__init__(config)

    async def _process_event(self, event: Event) -> None:
        """
        Обработать событие для аудита.

        Аргументы:
            event: Событие для обработки
        """
        # Определяем severity на основе типа события
        severity = self._determine_severity(event)

        # Запись в audit_events
        await self._record_audit_event(
            event_type=event.event_type,
            entity_type=self._extract_entity_type(event),
            entity_id=self._extract_entity_id(event),
            old_state=event.payload.get("old_state"),
            new_state=event.payload.get("new_state"),
            operator=event.payload.get("operator", "system"),
            metadata={
                **event.metadata,
                "source": event.source,
                "correlation_id": str(event.correlation_id) if event.correlation_id else None,
                "payload_keys": list(event.payload.keys()),
            },
            severity=severity,
        )

    def _determine_severity(self, event: Event) -> str:
        """
        Определить severity события.

        Аргументы:
            event: Событие

        Возвращает:
            Уровень severity
        """
        critical_events = {
            "KILL_SWITCH_TRIGGERED",
            "EMERGENCY_STOP",
            "SYSTEM_SHUTDOWN",
            "CIRCUIT_BREAKER_OPENED",
        }

        error_events = {
            "ORDER_REJECTED",
            "EXECUTION_ERROR",
            "RISK_VIOLATION",
            "POSITION_SIZE_EXCEEDED",
            "DRAWDOWN_EXCEEDED",
            "HEALTH_CHECK_FAILED",
            "WATCHDOG_ALERT",
        }

        warning_events = {
            "ORDER_CANCELLED",
            "CIRCUIT_BREAKER_CLOSED",
            "DAILY_LOSS_LIMIT",
        }

        if event.event_type in critical_events:
            return "CRITICAL"
        elif event.event_type in error_events:
            return "ERROR"
        elif event.event_type in warning_events:
            return "WARNING"
        else:
            return "INFO"

    def _extract_entity_type(self, event: Event) -> str:
        """
        Извлечь тип сущности из события.

        Аргументы:
            event: Событие

        Возвращает:
            Тип сущности
        """
        payload = event.payload

        # Маппинг event_type -> entity_type
        entity_mapping = {
            "ORDER_SUBMITTED": "order",
            "ORDER_FILLED": "order",
            "ORDER_CANCELLED": "order",
            "ORDER_REJECTED": "order",
            "POSITION_OPENED": "position",
            "POSITION_CLOSED": "position",
            "STATE_TRANSITION": "state_machine",
            "SYSTEM_BOOT": "system",
            "SYSTEM_READY": "system",
            "SYSTEM_HALT": "system",
            "SYSTEM_SHUTDOWN": "system",
            "RISK_VIOLATION": "risk",
            "HEALTH_CHECK_FAILED": "health",
            "WATCHDOG_ALERT": "watchdog",
            "CIRCUIT_BREAKER_OPENED": "circuit_breaker",
            "CIRCUIT_BREAKER_CLOSED": "circuit_breaker",
        }

        return entity_mapping.get(event.event_type, payload.get("entity_type") or "unknown")

    def _extract_entity_id(self, event: Event) -> str:
        """
        Извлечь ID сущности из события.

        Аргументы:
            event: Событие

        Возвращает:
            ID сущности
        """
        payload = event.payload

        # Пытаемся найти ID в payload
        for id_field in ["order_id", "position_id", "entity_id", "id"]:
            if id_field in payload:
                return str(payload[id_field])

        return str(event.id)

    async def _record_audit_event(
        self,
        event_type: str,
        entity_type: str,
        entity_id: str,
        old_state: dict[str, Any] | None,
        new_state: dict[str, Any] | None,
        operator: str,
        metadata: dict[str, Any],
        severity: str,
    ) -> None:
        """Записать audit event в БД."""
        pool = None
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO audit_events
                    (event_type, entity_type, entity_id, old_state, new_state,
                     operator, metadata, severity)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """,
                    event_type,
                    entity_type,
                    entity_id,
                    json.dumps(old_state) if old_state else None,
                    json.dumps(new_state) if new_state else None,
                    operator,
                    json.dumps(metadata),
                    severity,
                )
        except Exception as e:
            # Audit listener никогда не должен падать - только логируем
            logger.error(f"[{self.name}] Failed to record audit event: {e}")

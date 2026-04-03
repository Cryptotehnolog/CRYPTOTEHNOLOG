"""
State Machine Listener for Event Bus.

Обрабатывает события, связанные со State Machine:
- STATE_TRANSITION - переходы состояний
- SYSTEM_* - системные события
- Публикует события изменений в БД
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from ..database import get_db_pool
from ..state_machine_enums import SystemState
from .base import BaseListener, ListenerConfig

if TYPE_CHECKING:
    from ..event import Event

logger = logging.getLogger(__name__)


class StateMachineListener(BaseListener):
    """
    Listener для событий State Machine.

    Обрабатывает:
    - STATE_TRANSITION: записывает переходы в БД
    - SYSTEM_BOOT/SYSTEM_SHUTDOWN: обновляет состояние
    - HEALTH_CHECK_FAILED: триггерит emergency остановку
    """

    def __init__(self, config: ListenerConfig | None = None):
        """Инициализировать State Machine Listener."""
        if config is None:
            config = ListenerConfig(
                name="state_machine_listener",
                event_types=[
                    "STATE_TRANSITION",
                    "SYSTEM_BOOT",
                    "SYSTEM_READY",
                    "SYSTEM_HALT",
                    "SYSTEM_SHUTDOWN",
                    "HEALTH_CHECK_FAILED",
                    "WATCHDOG_ALERT",
                    "CIRCUIT_BREAKER_OPENED",
                    "CIRCUIT_BREAKER_CLOSED",
                ],
                priority=100,
            )
        super().__init__(config)

    async def _process_event(self, event: Event) -> None:
        """
        Обработать событие State Machine.

        Аргументы:
            event: Событие для обработки
        """
        handlers = {
            "STATE_TRANSITION": self._handle_state_transition,
            "SYSTEM_BOOT": self._handle_system_boot,
            "SYSTEM_READY": self._handle_system_ready,
            "SYSTEM_HALT": self._handle_system_halt,
            "SYSTEM_SHUTDOWN": self._handle_system_shutdown,
            "HEALTH_CHECK_FAILED": self._handle_health_check_failed,
            "WATCHDOG_ALERT": self._handle_watchdog_alert,
            "CIRCUIT_BREAKER_OPENED": self._handle_circuit_breaker_opened,
            "CIRCUIT_BREAKER_CLOSED": self._handle_circuit_breaker_closed,
        }

        handler = handlers.get(event.event_type)
        if handler:
            await handler(event)
        else:
            logger.warning(f"[{self.name}] No handler for event type: {event.event_type}")

    async def _handle_state_transition(self, event: Event) -> None:
        """Обработать переход состояния."""
        payload = event.payload
        from_state = payload.get("from_state", "unknown")
        to_state = payload.get("to_state", "unknown")
        trigger = payload.get("trigger", "unknown")
        duration_ms = payload.get("duration_ms")
        operator = payload.get("operator", "system")

        logger.info(
            f"[{self.name}] State transition: {from_state} -> {to_state} (trigger: {trigger})"
        )

        # Запись в БД
        await self._record_transition(
            from_state=from_state,
            to_state=to_state,
            trigger=trigger,
            duration_ms=duration_ms,
            operator=operator,
            correlation_id=str(event.correlation_id) if event.correlation_id else None,
            metadata=event.metadata,
        )
        if not self._state_already_persisted(event):
            await self._update_current_state(to_state)

    async def _handle_system_boot(self, event: Event) -> None:
        """Обработать событие SYSTEM_BOOT."""
        logger.info(f"[{self.name}] System boot event received")
        if not self._state_already_persisted(event):
            await self._update_current_state(SystemState.BOOT.value)

    async def _handle_system_ready(self, event: Event) -> None:
        """Обработать событие SYSTEM_READY."""
        logger.info(f"[{self.name}] System ready event received")
        if not self._state_already_persisted(event):
            await self._update_current_state(SystemState.READY.value)

    async def _handle_system_halt(self, event: Event) -> None:
        """Обработать событие SYSTEM_HALT."""
        logger.warning(f"[{self.name}] System halt event received")
        if not self._state_already_persisted(event):
            await self._update_current_state(SystemState.HALT.value)

    async def _handle_system_shutdown(self, event: Event) -> None:
        """Обработать событие SYSTEM_SHUTDOWN."""
        logger.info(f"[{self.name}] System shutdown event received")
        if not self._state_already_persisted(event):
            await self._update_current_state(SystemState.HALT.value)

    async def _handle_health_check_failed(self, event: Event) -> None:
        """Обработать событие HEALTH_CHECK_FAILED."""
        payload = event.payload
        component = payload.get("component", "unknown")
        message = payload.get("message", "")

        logger.error(f"[{self.name}] Health check failed: {component} - {message}")

        # Запись в audit events
        await self._record_audit_event(
            event_type="HEALTH_CHECK_FAILED",
            entity_type="system",
            entity_id=component,
            old_state=None,
            new_state={"status": "unhealthy", "message": message},
            severity="ERROR",
            metadata=event.metadata,
        )

    async def _handle_watchdog_alert(self, event: Event) -> None:
        """Обработать событие WATCHDOG_ALERT."""
        payload = event.payload
        reason = payload.get("reason", "unknown")

        logger.error(f"[{self.name}] Watchdog alert: {reason}")

        await self._record_audit_event(
            event_type="WATCHDOG_ALERT",
            entity_type="watchdog",
            entity_id="main",
            old_state=None,
            new_state={"status": "alert", "reason": reason},
            severity="WARNING",
            metadata=event.metadata,
        )

    async def _handle_circuit_breaker_opened(self, event: Event) -> None:
        """Обработать событие CIRCUIT_BREAKER_OPENED."""
        payload = event.payload
        reason = payload.get("reason", "unknown")

        logger.warning(f"[{self.name}] Circuit breaker opened: {reason}")

        await self._record_audit_event(
            event_type="CIRCUIT_BREAKER_OPENED",
            entity_type="circuit_breaker",
            entity_id="main",
            old_state=None,
            new_state={"status": "open", "reason": reason},
            severity="WARNING",
            metadata=event.metadata,
        )

    async def _handle_circuit_breaker_closed(self, event: Event) -> None:
        """Обработать событие CIRCUIT_BREAKER_CLOSED."""
        logger.info(f"[{self.name}] Circuit breaker closed")

        await self._record_audit_event(
            event_type="CIRCUIT_BREAKER_CLOSED",
            entity_type="circuit_breaker",
            entity_id="main",
            old_state={"status": "open"},
            new_state={"status": "closed"},
            severity="INFO",
            metadata=event.metadata,
        )

    async def _record_transition(
        self,
        from_state: str,
        to_state: str,
        trigger: str,
        duration_ms: int | None,
        operator: str,
        correlation_id: str | None,
        metadata: dict[str, Any],
    ) -> None:
        """Записать переход состояния в БД."""
        pool = None
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO state_transitions
                    (from_state, to_state, trigger, metadata, operator, duration_ms, correlation_id)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """,
                    from_state,
                    to_state,
                    trigger,
                    json.dumps(metadata),
                    operator,
                    duration_ms,
                    correlation_id,
                )
        except Exception as e:
            logger.error(f"[{self.name}] Failed to record transition: {e}")
            # Не поднимаем исключение - логируем и продолжаем

    async def _update_current_state(self, state: str) -> None:
        """Обновить persisted current state для synthetic/manual control-plane events."""
        pool = None
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO state_machine_states (id, current_state, version, updated_at)
                    VALUES (1, $1, 1, NOW())
                    ON CONFLICT (id) DO UPDATE
                    SET current_state = EXCLUDED.current_state,
                        version = state_machine_states.version + 1,
                        updated_at = NOW()
                    """,
                    state,
                )
        except Exception as e:
            logger.error(f"[{self.name}] Failed to update current state: {e}")

    def _state_already_persisted(self, event: Event) -> bool:
        """Return True when canonical state machine/controller path already persisted current state."""
        return bool(event.metadata.get("state_already_persisted", False))

    async def _record_audit_event(
        self,
        event_type: str,
        entity_type: str,
        entity_id: str,
        old_state: dict[str, Any] | None,
        new_state: dict[str, Any] | None,
        severity: str,
        metadata: dict[str, Any],
    ) -> None:
        """Записать audit событие."""
        pool = None
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO audit_events
                    (event_type, entity_type, entity_id, old_state, new_state, severity, metadata)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """,
                    event_type,
                    entity_type,
                    entity_id,
                    json.dumps(old_state) if old_state else None,
                    json.dumps(new_state) if new_state else None,
                    severity,
                    json.dumps(metadata),
                )
        except Exception as e:
            logger.error(f"[{self.name}] Failed to record audit event: {e}")

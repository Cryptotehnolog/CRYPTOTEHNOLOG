"""
Event Types for Event Bus.

Основные типы событий для шины событий CRYPTOTEHNOLOG.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
import uuid


class Priority(StrEnum):
    """Приоритеты событий."""

    CRITICAL = "critical"  # Убийственные переключатели, системные сбои
    HIGH = "high"  # Нарушения рисков, критические ошибки исполнения
    NORMAL = "normal"  # Торговые сигналы, обычные операции
    LOW = "low"  # Метрики, информационные логи

    @classmethod
    def from_string(cls, value: str) -> Priority:
        """Создать Priority из строки."""
        try:
            return cls(value.lower())
        except ValueError:
            return cls.NORMAL

    def requires_persistence(self) -> bool:
        """Определить, требует ли приоритет персистентности."""
        return self in (Priority.CRITICAL, Priority.HIGH, Priority.NORMAL)


class EventType(StrEnum):
    """Типы событий для торговой платформы."""

    # Ордера
    ORDER_SUBMITTED = "ORDER_SUBMITTED"
    ORDER_ACCEPTED = "ORDER_ACCEPTED"
    ORDER_REJECTED = "ORDER_REJECTED"
    ORDER_UPDATED = "ORDER_UPDATED"
    ORDER_CANCELLED = "ORDER_CANCELLED"

    # Сделки
    TRADE_EXECUTED = "TRADE_EXECUTED"

    # Позиции
    POSITION_OPENED = "POSITION_OPENED"
    POSITION_UPDATED = "POSITION_UPDATED"
    POSITION_CLOSED = "POSITION_CLOSED"

    # Риски
    RISK_BREACH = "RISK_BREACH"

    # Системные
    SYSTEM_STATE_CHANGED = "SYSTEM_STATE_CHANGED"
    CONFIG_UPDATED = "CONFIG_UPDATED"
    CONFIG_ROLLEDBACK = "CONFIG_ROLLEDBACK"

    # Метрики
    METRICS_COLLECTED = "METRICS_COLLECTED"
    HEALTH_CHECK = "HEALTH_CHECK"

    def to_rust_priority(self) -> str:
        """Конвертировать в строку для Rust биндингов."""
        return self.value


@dataclass
class Event:
    """
    Событие для шины событий.

    События являются основным механизмом коммуникации между компонентами
    в торговой платформе CRYPTOTEHNOLOG.

    Атрибуты:
        id: Уникальный идентификатор события
        event_type: Тип события (например, "ORDER_SUBMITTED", "POSITION_OPENED")
        source: Источник события (например, "RISK_ENGINE", "EXECUTION_CORE")
        timestamp: Время создания события (UTC)
        payload: Данные события (JSON-совместимый dict)
        correlation_id: Опциональный ID для отслеживания связанных событий
        metadata: Дополнительные метаданные события
        priority: Приоритет события (CRITICAL/HIGH/NORMAL/LOW)
    """

    event_type: str
    source: str
    payload: dict[str, Any]
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: uuid.UUID | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    priority: Priority = Priority.NORMAL

    @classmethod
    def new(
        cls,
        event_type: str,
        source: str,
        payload: dict[str, Any],
    ) -> Event:
        """
        Создать новое событие.

        Аргументы:
            event_type: Тип события
            source: Источник события
            payload: Данные события

        Возвращает:
            Новая instance Event
        """
        return cls(
            event_type=event_type,
            source=source,
            payload=payload,
        )

    @classmethod
    def with_correlation_id(
        cls,
        event_type: str,
        source: str,
        payload: dict[str, Any],
        correlation_id: uuid.UUID,
    ) -> Event:
        """
        Создать событие с correlation ID.

        Используется для событий, которые являются частью большого workflow
        и должны отслеживаться вместе.

        Аргументы:
            event_type: Тип события
            source: Источник события
            payload: Данные события
            correlation_id: ID для корреляции связанных событий

        Возвращает:
            Новая instance Event
        """
        event = cls(event_type=event_type, source=source, payload=payload)
        event.correlation_id = correlation_id
        return event

    def with_metadata(self, key: str, value: Any) -> Event:
        """
        Добавить метаданные к событию.

        Аргументы:
            key: Ключ метаданных
            value: Значение метаданных

        Возвращает:
            Self для цепочки вызовов
        """
        self.metadata[key] = value
        return self

    def with_priority(self, priority: Priority) -> Event:
        """
        Создать копию события с указанным приоритетом.

        Аргументы:
            priority: Новый приоритет события

        Возвращает:
            Новая копия события с обновлённым приоритетом
        """
        new_event = copy.deepcopy(self)
        new_event.priority = priority
        return new_event

    def is_correlated_with(self, other: Event) -> bool:
        """
        Проверить, коррелировано ли это событие с другим.

        Аргументы:
            other: Другое событие для проверки

        Возвращает:
            True если события имеют одинаковый correlation ID
        """
        return self.correlation_id is not None and self.correlation_id == other.correlation_id

    def age_seconds(self) -> float:
        """
        Получить возраст события в секундах.

        Возвращает:
            Количество секунд с момента создания события
        """
        delta = datetime.now(UTC) - self.timestamp
        return delta.total_seconds()

    def to_dict(self) -> dict[str, Any]:
        """
        Конвертировать событие в словарь.

        Возвращает:
            Словарь с данными события
        """
        return {
            "id": str(self.id),
            "event_type": self.event_type,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "payload": self.payload,
            "correlation_id": str(self.correlation_id) if self.correlation_id else None,
            "metadata": self.metadata,
            "priority": self.priority.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Event:
        """
        Создать событие из словаря.

        Аргументы:
            data: Словарь с данными события

        Возвращает:
            Новая instance Event
        """
        return cls(
            id=uuid.UUID(data["id"]),
            event_type=data["event_type"],
            source=data["source"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            payload=data["payload"],
            correlation_id=(
                uuid.UUID(data["correlation_id"]) if data.get("correlation_id") else None
            ),
            metadata=data.get("metadata", {}),
            priority=Priority.from_string(data.get("priority", "normal")),
        )


# ==================== Event Types ====================


class SystemEventType:
    """Стандартные типы системных событий."""

    # Lifecycle events
    SYSTEM_BOOT = "SYSTEM_BOOT"
    SYSTEM_READY = "SYSTEM_READY"
    SYSTEM_HALT = "SYSTEM_HALT"
    SYSTEM_SHUTDOWN = "SYSTEM_SHUTDOWN"

    # State machine events
    STATE_TRANSITION = "STATE_TRANSITION"

    # Watchdog events
    WATCHDOG_ALERT = "WATCHDOG_ALERT"
    HEALTH_CHECK_FAILED = "HEALTH_CHECK_FAILED"
    CIRCUIT_BREAKER_OPENED = "CIRCUIT_BREAKER_OPENED"
    CIRCUIT_BREAKER_CLOSED = "CIRCUIT_BREAKER_CLOSED"

    # Risk events (Фаза 5)
    RISK_VIOLATION = "RISK_VIOLATION"
    POSITION_SIZE_EXCEEDED = "POSITION_SIZE_EXCEEDED"
    DRAWDOWN_EXCEEDED = "DRAWDOWN_EXCEEDED"

    # Execution events (Фаза 10)
    ORDER_SUBMITTED = "ORDER_SUBMITTED"
    ORDER_FILLED = "ORDER_FILLED"
    ORDER_CANCELLED = "ORDER_CANCELLED"
    ORDER_REJECTED = "ORDER_REJECTED"
    EXECUTION_ERROR = "EXECUTION_ERROR"

    # Kill switch (Фаза 12)
    KILL_SWITCH_TRIGGERED = "KILL_SWITCH_TRIGGERED"


class SystemEventSource:
    """Стандартные источники событий."""

    SYSTEM_CONTROLLER = "SYSTEM_CONTROLLER"
    STATE_MACHINE = "STATE_MACHINE"
    WATCHDOG = "WATCHDOG"
    HEALTH_CHECK = "HEALTH_CHECK"
    CIRCUIT_BREAKER = "CIRCUIT_BREAKER"
    RISK_ENGINE = "RISK_ENGINE"
    EXECUTION_CORE = "EXECUTION_CORE"
    STRATEGY_MANAGER = "STRATEGY_MANAGER"
    PORTFOLIO_GOVERNOR = "PORTFOLIO_GOVERNOR"
    KILL_SWITCH = "KILL_SWITCH"

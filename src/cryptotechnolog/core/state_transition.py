"""
Data classes для State Machine.

Определяет:
- StateTransition: запись о переходе состояния
- TransitionResult: результат попытки перехода
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from cryptotechnolog.config import get_logger

from .state_machine_enums import SystemState

logger = get_logger(__name__)


@dataclass
class StateTransition:
    """
    Запись о переходе состояния системы.

    Используется для:
    - Audit trail всех переходов
    - Логирования и мониторинга
    - Анализа инцидентов

    Атрибуты:
        transition_id: Уникальный ID перехода
        from_state: Предыдущее состояние
        to_state: Новое состояние
        trigger: Тип триггера
        timestamp: Время перехода
        metadata: Дополнительный контекст
        operator: Оператор (для ручных переходов)
        duration_ms: Длительность перехода в миллисекундах
    """

    transition_id: int
    from_state: SystemState
    to_state: SystemState
    trigger: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)
    operator: str | None = None
    duration_ms: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """
        Преобразовать в словарь для сериализации.

        Возвращает:
            Словарь с данными перехода
        """
        return {
            "transition_id": self.transition_id,
            "from_state": self.from_state.value,
            "to_state": self.to_state.value,
            "trigger": self.trigger,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            "operator": self.operator,
            "duration_ms": self.duration_ms,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StateTransition:
        """
        Создать из словаря.

        Аргументы:
            data: Словарь с данными

        Возвращает:
            Экземпляр StateTransition
        """
        return cls(
            transition_id=data["transition_id"],
            from_state=SystemState(data["from_state"]),
            to_state=SystemState(data["to_state"]),
            trigger=data["trigger"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            metadata=data.get("metadata", {}),
            operator=data.get("operator"),
            duration_ms=data.get("duration_ms"),
        )


@dataclass
class TransitionResult:
    """
    Результат попытки перехода состояния.

    Атрибуты:
        success: Успешность перехода
        transition: Данные перехода (если успешно)
        error: Сообщение об ошибке (если неуспешно)
        reason: Причина неудачи
    """

    success: bool
    transition: StateTransition | None = None
    error: str | None = None
    reason: str | None = None

    def __str__(self) -> str:
        """Строковое представление результата."""
        if self.success and self.transition:
            return f"Переход выполнен: {self.transition.from_state} → {self.transition.to_state}"
        return f"Переход не выполнен: {self.error}"


@dataclass
class StateHistory:
    """
    История переходов состояний.

    Хранит последние N переходов для анализа.

    Атрибуты:
        transitions: Список переходов
        max_size: Максимальный размер истории
    """

    transitions: list[StateTransition] = field(default_factory=list)
    max_size: int = 100

    def add(self, transition: StateTransition) -> None:
        """
        Добавить переход в историю.

        Аргументы:
            transition: Переход для добавления
        """
        self.transitions.append(transition)

        # Ограничить размер истории
        if len(self.transitions) > self.max_size:
            self.transitions = self.transitions[-self.max_size :]

    def get_recent(self, count: int = 10) -> list[StateTransition]:
        """
        Получить последние N переходов.

        Аргументы:
            count: Количество переходов

        Возвращает:
            Список последних переходов
        """
        return self.transitions[-count:]

    def get_by_trigger(self, trigger: str) -> list[StateTransition]:
        """
        Получить переходы по триггеру.

        Аргументы:
            trigger: Тип триггера

        Возвращает:
            Список переходов с данным триггером
        """
        return [t for t in self.transitions if t.trigger == trigger]

    def get_last_transition(self) -> StateTransition | None:
        """
        Получить последний переход.

        Возвращает:
            Последний переход или None
        """
        return self.transitions[-1] if self.transitions else None


@dataclass
class CallbackInfo:
    """
    Информация о колбэке для состояния.

    Атрибуты:
        name: Имя колбэка
        callback: Функция колбэка
        is_async: Является ли асинхронным
    """

    name: str
    callback: Any  # Callable
    is_async: bool = True

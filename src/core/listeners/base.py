"""
Base Listener Classes for Event Bus.

Базовые классы для listeners Event Bus в CRYPTOTEHNOLOG.
Реализует паттерн Observer для асинхронной обработки событий.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from src.core.event import Event

logger = logging.getLogger(__name__)


@dataclass
class ListenerConfig:
    """
    Конфигурация listener.

    Атрибуты:
        name: Имя listener
        event_types: Список типов событий для обработки (['*'] для всех)
        async_handler: Асинхронный обработчик
        sync_handler: Синхронный обработчик (fallback)
        priority: Приоритет (больше = раньше)
        enabled: Включен/выключен
        max_retries: Максимум попыток при ошибке
        retry_delay: Задержка между попытками (сек)
    """

    name: str
    event_types: list[str] = field(default_factory=lambda: ["*"])
    async_handler: Callable[[Event], Coroutine[Any, Any, None]] | None = None
    sync_handler: Callable[[Event], None] | None = None
    priority: int = 0
    enabled: bool = True
    max_retries: int = 3
    retry_delay: float = 1.0

    def handles_event(self, event: Event) -> bool:
        """
        Проверить, обрабатывает ли listener данное событие.

        Аргументы:
            event: Событие для проверки

        Возвращает:
            True если listener обрабатывает это событие
        """
        if not self.enabled:
            return False

        if "*" in self.event_types:
            return True

        return event.event_type in self.event_types


class BaseListener(ABC):
    """
    Базовый класс для всех listeners.

    Предоставляет общую функциональность для обработки событий,
    включая retry логику, логирование и метрики.
    """

    def __init__(self, config: ListenerConfig):
        """
        Инициализировать listener.

        Аргументы:
            config: Конфигурация listener
        """
        self.config = config
        self._events_processed: int = 0
        self._events_failed: int = 0
        self._last_event_time: datetime | None = None

    @property
    def name(self) -> str:
        """Имя listener."""
        return self.config.name

    @property
    def event_types(self) -> list[str]:
        """Типы событий, которые обрабатывает listener."""
        return self.config.event_types

    @property
    def is_enabled(self) -> bool:
        """Проверка, включен ли listener."""
        return self.config.enabled

    @property
    def metrics(self) -> dict[str, Any]:
        """Метрики listener."""
        return {
            "name": self.name,
            "events_processed": self._events_processed,
            "events_failed": self._events_failed,
            "last_event_time": self._last_event_time.isoformat() if self._last_event_time else None,
        }

    def handles_event(self, event: Event) -> bool:
        """
        Проверить, обрабатывает ли listener событие.

        Аргументы:
            event: Событие для проверки

        Возвращает:
            True если обрабатывает
        """
        return self.config.handles_event(event)

    async def handle(self, event: Event) -> bool:
        """
        Обработать событие с retry логикой.

        Аргументы:
            event: Событие для обработки

        Возвращает:
            True если успешно обработано
        """
        if not self.handles_event(event):
            return False

        last_error: Exception | None = None

        for attempt in range(self.config.max_retries):
            try:
                await self._process_event(event)
                self._events_processed += 1
                self._last_event_time = datetime.now(UTC)
                return True

            except Exception as e:
                last_error = e
                self._events_failed += 1

                if attempt < self.config.max_retries - 1:
                    logger.warning(
                        f"[{self.name}] Attempt {attempt + 1}/{self.config.max_retries} "
                        f"failed: {e}. Retrying in {self.config.retry_delay}s..."
                    )
                    await asyncio.sleep(self.config.retry_delay * (attempt + 1))
                else:
                    logger.error(
                        f"[{self.name}] All {self.config.max_retries} attempts failed "
                        f"for event {event.event_type}: {e}"
                    )

        # Log failed event for recovery
        await self._handle_failure(event, last_error)
        return False

    @abstractmethod
    async def _process_event(self, event: Event) -> None:
        """
        Обработать событие (реализуется в подклассах).

        Аргументы:
            event: Событие для обработки

        Исключения:
            Exception: Любая ошибка обработки
        """
        pass

    async def _handle_failure(self, event: Event, error: Exception | None) -> None:
        """
        Обработать неудачу обработки события.

        Может быть переопределен для реализации специальной логики
        (например, запись в dead letter queue).

        Аргументы:
            event: Событие, которое не удалось обработать
            error: Исключение, которое произошло
        """
        logger.error(
            f"[{self.name}] Failed to process event {event.event_type} (id={event.id}): {error}"
        )

    def enable(self) -> None:
        """Включить listener."""
        self.config.enabled = True
        logger.info(f"[{self.name}] Enabled")

    def disable(self) -> None:
        """Выключить listener."""
        self.config.enabled = False
        logger.info(f"[{self.name}] Disabled")


class ListenerRegistry:
    """
    Реестр listeners для Event Bus.

    Управляет регистрацией и вызовом listeners.
    """

    def __init__(self):
        """Инициализировать реестр."""
        self._listeners: dict[str, BaseListener] = {}
        self._event_type_to_listeners: dict[str, list[str]] = {}

    def register(self, listener: BaseListener) -> None:
        """
        Зарегистрировать listener.

        Аргументы:
            listener: Listener для регистрации
        """
        if listener.name in self._listeners:
            logger.warning(f"Listener {listener.name} already registered, replacing")

        self._listeners[listener.name] = listener

        # Update event type mapping
        for event_type in listener.event_types:
            if event_type not in self._event_type_to_listeners:
                self._event_type_to_listeners[event_type] = []
            if listener.name not in self._event_type_to_listeners[event_type]:
                self._event_type_to_listeners[event_type].append(listener.name)

        # Add to wildcard list
        if "*" not in self._event_type_to_listeners:
            self._event_type_to_listeners["*"] = []

        logger.info(f"Registered listener: {listener.name} for events: {listener.event_types}")

    def unregister(self, name: str) -> bool:
        """
        Удалить listener из реестра.

        Аргументы:
            name: Имя listener для удаления

        Возвращает:
            True если listener был удален
        """
        if name not in self._listeners:
            return False

        listener = self._listeners[name]
        for event_type in listener.event_types:
            if event_type in self._event_type_to_listeners:
                self._event_type_to_listeners[event_type].remove(name)

        del self._listeners[name]
        logger.info(f"Unregistered listener: {name}")
        return True

    def get_listener(self, name: str) -> BaseListener | None:
        """
        Получить listener по имени.

        Аргументы:
            name: Имя listener

        Возвращает:
            Listener или None если не найден
        """
        return self._listeners.get(name)

    def get_listeners_for_event(self, event: Event) -> list[BaseListener]:
        """
        Получить все listeners для события.

        Аргументы:
            event: Событие

        Возвращает:
            Список listeners, отсортированный по приоритету
        """
        listener_names: set[str] = set()

        # Get listeners for specific event type
        if event.event_type in self._event_type_to_listeners:
            listener_names.update(self._event_type_to_listeners[event.event_type])

        # Get wildcard listeners
        if "*" in self._event_type_to_listeners:
            listener_names.update(self._event_type_to_listeners["*"])

        # Get listeners and sort by priority
        listeners = []
        for name in listener_names:
            listener = self._listeners.get(name)
            if listener and listener.handles_event(event):
                listeners.append(listener)

        return sorted(listeners, key=lambda listener: listener.config.priority, reverse=True)

    @property
    def all_listeners(self) -> list[BaseListener]:
        """Получить все зарегистрированные listeners."""
        return list(self._listeners.values())

    @property
    def enabled_listeners(self) -> list[BaseListener]:
        """Получить все включенные listeners."""
        return [listener for listener in self._listeners.values() if listener.is_enabled]

    @property
    def metrics(self) -> dict[str, Any]:
        """Метрики всех listeners."""
        return {
            "total_listeners": len(self._listeners),
            "enabled_listeners": len(self.enabled_listeners),
            "listeners": {name: listener.metrics for name, listener in self._listeners.items()},
        }


# Global registry instance
_listener_registry: ListenerRegistry | None = None


def get_listener_registry() -> ListenerRegistry:
    """
    Получить глобальный экземпляр ListenerRegistry.

    Возвращает:
        Глобальный реестр listeners
    """
    global _listener_registry  # noqa: PLW0603
    if _listener_registry is None:
        _listener_registry = ListenerRegistry()
    return _listener_registry

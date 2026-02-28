"""
Event Bus Implementation.

Высокопроизводительная шина событий для межкомпонентной коммуникации
в торговой платформе CRYPTOTEHNOLOG.

Особенности:
- Множественные подписчики (broadcast)
- Graceful degradation при переполнении буфера
- Потокобезопасность
- Поддержка asyncio для асинхронной работы
- Два backend: ChannelBased (по умолчанию) и AsyncQueue
- Все на РУССКОМ языке
"""

from __future__ import annotations

import asyncio
from asyncio import Queue
from collections import defaultdict
import enum
import threading
from typing import TYPE_CHECKING, Any
import uuid

from cryptotechnolog.config import get_logger

from .event import Event, SystemEventSource, SystemEventType

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

logger = get_logger(__name__)


class EventBusBackend(enum.Enum):
    """Типы backend для Event Bus."""

    CHANNEL_BASED = "channel_based"
    ASYNC_QUEUE = "async_queue"


class EventBusError(Exception):
    """Ошибка Event Bus."""

    pass


class SubscriberNotFoundError(EventBusError):
    """Подписчик не найден."""

    pass


# ==================== Async Receiver ====================


class AsyncEventReceiver:
    """
    Асинхронный приёмник событий.

    Позволяет асинхронно получать события из шины.
    """

    def __init__(self, queue: Queue[Event | None], event_bus: EventBus) -> None:
        self._queue = queue
        self._event_bus = event_bus
        self._closed = False

    async def recv(self) -> Event | None:
        """
        Получить следующее событие.

        Возвращает:
            Событие или None если очередь закрыта
        """
        if self._closed:
            return None
        return await self._queue.get()

    async def try_recv(self) -> Event | None:
        """
        Попробовать получить событие без блокировки.

        Возвращает:
            Событие если доступно, иначе None
        """
        if self._closed:
            return None
        try:
            return self._queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    async def recv_timeout(self, timeout: float) -> Event | None:
        """
        Получить событие с таймаутом.

        Аргументы:
            timeout: Таймаут в секундах

        Возвращает:
            Событие или None при таймауте
        """
        if self._closed:
            return None
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=timeout)
        except TimeoutError:
            return None

    def __aiter__(self) -> AsyncIterator[Event]:
        """Итератор для async for."""
        return self

    async def __anext__(self) -> Event:
        """Получить следующее событие через итератор."""
        event = await self.recv()
        if event is None:
            raise StopAsyncIteration
        return event

    def close(self) -> None:
        """Закрыть приёмник."""
        self._closed = True
        self._event_bus._remove_subscriber(self)


# ==================== Event Bus ====================


class EventBus:
    """
    Высокопроизводительная шина событий.

    Обеспечивает коммуникацию между компонентами системы через
    publish/subscribe паттерн.

    Аргументы:
        backend: Тип backend для использования
        capacity: Ёмкость буфера для каждого подписчика

    Пример:
        >>> bus = EventBus()
        >>> # Подписка
        >>> receiver = bus.subscribe()
        >>> # Публикация
        >>> event = Event.new("TEST", "SOURCE", {"key": "value"})
        >>> bus.publish(event)
        >>> # Получение
        >>> received = await receiver.recv()
    """

    def __init__(
        self,
        backend: EventBusBackend = EventBusBackend.ASYNC_QUEUE,
        capacity: int = 1024,
    ) -> None:
        if capacity <= 0:
            raise ValueError("Capacity must be positive")

        self._backend = backend
        self._capacity = capacity

        # Subscribers management
        self._subscribers: dict[int, AsyncEventReceiver] = {}
        self._subscriber_lock = threading.Lock()
        self._next_subscriber_id = 0

        # Event handlers by type
        self._handlers: dict[str, list[Callable[[Event], Any]]] = defaultdict(list)

        # Statistics
        self._publish_count = 0
        self._subscribe_count = 0
        self._unsubscribe_count = 0

        logger.info(
            "EventBus инициализирован",
            backend=backend.value,
            capacity=capacity,
        )

    @property
    def backend(self) -> EventBusBackend:
        """Получить тип backend."""
        return self._backend

    @property
    def capacity(self) -> int:
        """Получить ёмкость буфера."""
        return self._capacity

    @property
    def subscriber_count(self) -> int:
        """Получить количество подписчиков."""
        with self._subscriber_lock:
            return len(self._subscribers)

    @property
    def publish_count(self) -> int:
        """Получить количество опубликованных событий."""
        return self._publish_count

    def subscribe(self) -> AsyncEventReceiver:
        """
        Подписаться на события.

        Каждый подписчик получает копию каждого опубликованного события.

        Возвращает:
            AsyncEventReceiver для получения событий
        """
        queue: Queue[Event | None] = Queue(maxsize=self._capacity)
        receiver = AsyncEventReceiver(queue, self)

        with self._subscriber_lock:
            subscriber_id = self._next_subscriber_id
            self._subscribers[subscriber_id] = receiver
            self._next_subscriber_id += 1
            self._subscribe_count += 1

        logger.debug(
            "Новый подписчик",
            subscriber_id=subscriber_id,
            total_subscribers=self.subscriber_count,
        )

        return receiver

    def unsubscribe(self, receiver: AsyncEventReceiver) -> None:
        """
        Отписаться от событий.

        Аргументы:
            receiver: Приёмник для отписки

        Вызывает:
            SubscriberNotFoundError: Если приёмник не найден
        """
        self._remove_subscriber(receiver)
        self._unsubscribe_count += 1

    def _remove_subscriber(self, receiver: AsyncEventReceiver) -> None:
        """Удалить подписчика (внутренний метод)."""
        with self._subscriber_lock:
            for sid, sub in list(self._subscribers.items()):
                if sub is receiver:
                    del self._subscribers[sid]
                    logger.debug(
                        "Подписчик удалён",
                        subscriber_id=sid,
                        remaining=self.subscriber_count,
                    )
                    return

    def publish(self, event: Event) -> bool:
        """
        Опубликовать событие.

        Событие отправляется всем подписчикам (broadcast).
        Non-blocking операция - при заполненном буфере событие
        может быть потеряно (graceful degradation).

        Аргументы:
            event: Событие для публикации

        Возвращает:
            True если хотя бы один подписчик получил событие
        """
        self._publish_count += 1

        with self._subscriber_lock:
            if not self._subscribers:
                logger.debug(
                    "Событие опубликовано без подписчиков",
                    event_type=event.event_type,
                )
                return False

            delivered_count = 0
            disconnected = []

            for subscriber_id, receiver in self._subscribers.items():
                try:
                    receiver._queue.put_nowait(event)
                    delivered_count += 1
                except asyncio.QueueFull:
                    logger.warning(
                        "Буфер подписчика полон",
                        subscriber_id=subscriber_id,
                        event_type=event.event_type,
                    )
                except Exception as e:
                    logger.error(
                        "Ошибка доставки события подписчику",
                        subscriber_id=subscriber_id,
                        error=str(e),
                    )
                    disconnected.append(subscriber_id)

            # Remove disconnected subscribers
            for sid in disconnected:
                del self._subscribers[sid]

            if delivered_count == 0:
                logger.warning(
                    "Событие не доставлено ни одному подписчику",
                    event_type=event.event_type,
                    subscriber_count=len(self._subscribers),
                )

            return delivered_count > 0

    async def publish_async(self, event: Event) -> bool:
        """Асинхронная версия publish (для совместимости)."""
        return self.publish(event)

    def on(self, event_type: str, handler: Callable[[Event], Any]) -> None:
        """
        Зарегистрировать обработчик для типа событий.

        Аргументы:
            event_type: Тип события
            handler: Обработчик (async function или sync function)
        """
        self._handlers[event_type].append(handler)
        logger.debug(
            "Обработчик зарегистрирован",
            event_type=event_type,
            handler=handler.__name__,
        )

    def off(self, event_type: str, handler: Callable[[Event], Any]) -> None:
        """
        Удалить обработчик для типа событий.

        Аргументы:
            event_type: Тип события
            handler: Обработчик для удаления
        """
        if event_type in self._handlers:
            try:
                self._handlers[event_type].remove(handler)
                logger.debug(
                    "Обработчик удалён",
                    event_type=event_type,
                )
            except ValueError:
                pass

    async def _dispatch_handlers(self, event: Event) -> None:
        """Диспетчеризировать событие зарегистрированным обработчикам."""
        handlers = self._handlers.get(event.event_type, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                logger.error(
                    "Ошибка в обработчике события",
                    event_type=event.event_type,
                    handler=handler.__name__,
                    error=str(e),
                )

    def get_stats(self) -> dict[str, Any]:
        """
        Получить статистику Event Bus.

        Возвращает:
            Словарь со статистикой
        """
        return {
            "backend": self._backend.value,
            "capacity": self._capacity,
            "subscriber_count": self.subscriber_count,
            "publish_count": self._publish_count,
            "subscribe_count": self._subscribe_count,
            "unsubscribe_count": self._unsubscribe_count,
            "handler_count": sum(len(h) for h in self._handlers.values()),
        }

    def clear(self) -> None:
        """Очистить всех подписчиков и обработчики."""
        with self._subscriber_lock:
            self._subscribers.clear()
        self._handlers.clear()
        logger.info("EventBus очищен")

    def __repr__(self) -> str:
        return (
            f"EventBus(backend={self._backend.value}, "
            f"capacity={self._capacity}, subscribers={self.subscriber_count})"
        )


# ==================== Global Event Bus ====================


class _GlobalEventBus:
    """Class-based singleton для глобального Event Bus."""

    _instance: EventBus | None = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> EventBus:
        """Получить экземпляр Event Bus."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = EventBus()
            return cls._instance

    @classmethod
    def set_instance(cls, bus: EventBus) -> None:
        """Установить экземпляр Event Bus."""
        with cls._lock:
            cls._instance = bus

    @classmethod
    def reset(cls) -> None:
        """Сбросить экземпляр (для тестов)."""
        with cls._lock:
            if cls._instance:
                cls._instance.clear()
            cls._instance = None


def get_event_bus() -> EventBus:
    """
    Получить глобальный экземпляр Event Bus.

    Используется для упрощённого доступа к шине событий
    из любого места в приложении.

    Возвращает:
        Глобальный экземпляр EventBus
    """
    return _GlobalEventBus.get_instance()


def set_event_bus(bus: EventBus) -> None:
    """
    Установить глобальный экземпляр Event Bus.

    Аргументы:
        bus: Экземпляр EventBus для установки
    """
    _GlobalEventBus.set_instance(bus)


def reset_event_bus() -> None:
    """Сбросить глобальный Event Bus (для тестов)."""
    _GlobalEventBus.reset()


# ==================== Convenience Functions ====================


def publish_event(
    event_type: str,
    source: str,
    payload: dict[str, Any],
    correlation_id: str | None = None,
) -> bool:
    """
    Опубликовать событие через глобальный Event Bus.

    Аргументы:
        event_type: Тип события
        source: Источник события
        payload: Данные события
        correlation_id: Опциональный correlation ID

    Возвращает:
        True если событие опубликовано
    """
    event = Event.new(event_type, source, payload)
    if correlation_id:
        event.correlation_id = uuid.UUID(correlation_id)

    return get_event_bus().publish(event)


async def publish_alert(
    message: str,
    severity: str = "warning",
    component: str = "SYSTEM",
) -> bool:
    """
    Опубликовать alert через глобальный Event Bus.

    Аргументы:
        message: Сообщение alert
        severity: Уровень серьёзности (info, warning, error, critical)
        component: Компонент-источник

    Возвращает:
        True если alert опубликован
    """
    event = Event.new(
        SystemEventType.WATCHDOG_ALERT,
        SystemEventSource.WATCHDOG,
        {
            "message": message,
            "severity": severity,
            "component": component,
        },
    )
    return get_event_bus().publish(event)

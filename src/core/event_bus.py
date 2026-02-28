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
from functools import partial
import threading
from typing import TYPE_CHECKING, Any
import uuid

from cryptotechnolog.config import get_logger

from .event import Event, SystemEventSource, SystemEventType

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    from src.core.listeners.base import BaseListener

from src.core.listeners import get_listener_registry

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

        # Listener registry integration
        self._listener_registry = None
        self._wildcard_listeners: list[BaseListener] = []
        self._pending_tasks: list[asyncio.Task] = []

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

    def _deliver_to_subscribers(self, event: Event) -> int:
        """Доставить событие подписчикам через queue. Возвращает количество доставленных."""
        delivered = 0
        with self._subscriber_lock:
            if not self._subscribers:
                return 0

            disconnected = []
            for subscriber_id, receiver in self._subscribers.items():
                try:
                    receiver._queue.put_nowait(event)
                    delivered += 1
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

            for sid in disconnected:
                del self._subscribers[sid]

        return delivered

    def _deliver_to_wildcard_listeners(self, event: Event) -> None:
        """Доставить событие wildcard listeners."""
        if not self._wildcard_listeners:
            return

        for listener in self._wildcard_listeners:
            if listener.handles_event(event):
                try:
                    result = listener.handle(event)
                    if asyncio.iscoroutine(result):
                        self._run_async_handler(result)
                except Exception as e:
                    logger.error(
                        "Ошибка в wildcard listener",
                        listener=listener.name,
                        error=str(e),
                    )

    def _deliver_to_handlers(self, event: Event) -> None:
        """Доставить событие зарегистрированным обработчикам."""
        handlers = self._handlers.get(event.event_type, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    result = handler(event)
                    if asyncio.iscoroutine(result):
                        self._run_async_handler(result)
                else:
                    handler(event)
            except Exception as e:
                logger.error(
                    "Ошибка в обработчике",
                    event_type=event.event_type,
                    error=str(e),
                )

    def _deliver_to_registry_listeners(self, event: Event) -> None:
        """Доставить событие listeners через registry."""
        if self._listener_registry is None:
            return

        try:
            coro = self._dispatch_to_listeners(event)
            self._run_async_handler(coro)
        except Exception as e:
            logger.debug("Не удалось диспетчеризовать listeners", error=str(e))

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

        delivered_count = self._deliver_to_subscribers(event)
        self._deliver_to_wildcard_listeners(event)

        try:
            self._deliver_to_handlers(event)
        except Exception as e:
            logger.error("Ошибка dispatch handlers", error=str(e))

        self._deliver_to_registry_listeners(event)

        return delivered_count > 0

    async def publish_async(self, event: Event) -> bool:
        """Асинхронная версия publish (для совместимости)."""
        return self.publish(event)

    def enable_listeners(self) -> None:
        """
        Включить listeners для Event Bus.

        Регистрирует всех listeners из ListenerRegistry
        и начинает обрабатывать события через них.
        """
        self._listener_registry = get_listener_registry()

        # Регистрируем каждого listener в EventBus для всех его типов событий
        for listener in self._listener_registry.all_listeners:
            event_types = listener.event_types
            if "*" in event_types:
                self._wildcard_listeners.append(listener)
            else:
                for event_type in event_types:
                    handler = partial(self._listener_wrapper, listener)
                    self.on(event_type, handler)

        logger.info(
            "Listeners enabled",
            listener_count=len(self._listener_registry.all_listeners),
        )

    def _listener_wrapper(self, listener: BaseListener, event: Event) -> None:
        """Обертка для вызова listener в синхронном контексте."""
        try:
            # Вызываем синхронно для гарантии выполнения
            result = listener.handle(event)
            # Если вернулся coroutine, пытаемся запустить
            if asyncio.iscoroutine(result):
                try:
                    loop = asyncio.get_running_loop()
                    task = loop.create_task(result)
                    # Сохраняем ссылку на задачу
                    self._pending_tasks.append(task)
                except RuntimeError:
                    # Нет running loop - пробуем запустить
                    try:
                        result.send(None)
                    except StopIteration:
                        pass
                    except Exception:
                        pass
        except Exception as e:
            logger.error(
                "Ошибка запуска listener",
                listener=listener.name,
                error=str(e),
            )

    def disable_listeners(self) -> None:
        """Выключить listeners."""
        self._listener_registry = None
        self._wildcard_listeners = []
        logger.info("Listeners disabled")

    async def flush(self) -> None:
        """Дождаться завершения всех асинхронных задач обработки."""
        if self._pending_tasks:
            # Фильтруем только незавершённые задачи
            pending = [t for t in self._pending_tasks if not t.done()]
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
            self._pending_tasks.clear()

    def _run_async_handler(self, coro) -> None:
        """Запустить асинхронный обработчик и отслеживать задачу."""
        try:
            loop = asyncio.get_running_loop()
            task = loop.create_task(coro)
            task.add_done_callback(
                lambda t: self._pending_tasks.remove(t) if t in self._pending_tasks else None
            )
            self._pending_tasks.append(task)
        except RuntimeError:
            # Нет running loop - выполняем синхронно через run_until_complete
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(coro)
            finally:
                loop.close()

    async def _dispatch_to_listeners(self, event: Event) -> None:
        """Диспетчеризировать событие зарегистрированным listeners."""
        if self._listener_registry is None:
            return

        try:
            listeners = self._listener_registry.get_listeners_for_event(event)
            for listener in listeners:
                try:
                    await listener.handle(event)
                except Exception as e:
                    logger.error(
                        "Ошибка в listener",
                        listener=listener.name,
                        event_type=event.event_type,
                        error=str(e),
                    )
        except Exception as e:
            logger.error(
                "Ошибка диспетчеризации listeners",
                event_type=event.event_type,
                error=str(e),
            )

    def on(self, event_type: str, handler: Callable[[Event], Any]) -> None:
        """
        Зарегистрировать обработчик для типа событий.

        Аргументы:
            event_type: Тип события
            handler: Обработчик (async function или sync function)
        """
        self._handlers[event_type].append(handler)
        # Получаем имя обработчика безопасно
        handler_name = getattr(handler, "__name__", str(handler))
        logger.debug(
            "Обработчик зарегистрирован",
            event_type=event_type,
            handler=handler_name,
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

    async def shutdown(self) -> None:
        """Корректно завершить работу EventBus."""
        # Отменяем все ожидающие задачи
        for task in self._pending_tasks:
            if not task.done():
                task.cancel()

        if self._pending_tasks:
            await asyncio.gather(*self._pending_tasks, return_exceptions=True)

        self._pending_tasks.clear()
        self.disable_listeners()
        self.clear()

    def clear(self) -> None:
        """Очистить всех подписчиков и обработчики."""
        with self._subscriber_lock:
            self._subscribers.clear()
        self._handlers.clear()
        self._wildcard_listeners.clear()
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

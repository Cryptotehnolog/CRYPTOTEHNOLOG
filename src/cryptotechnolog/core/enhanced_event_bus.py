"""
Enhanced Event Bus Implementation.

Расширенная шина событий с приоритетами, backpressure, persistence для
торговой платформы CRYPTOTEHNOLOG.

Особенности:
- 4 уровня приоритета (CRITICAL, HIGH, NORMAL, LOW)
- Раздельные очереди с разной ёмкостью для каждого приоритета
- Backpressure handling с различными стратегиями
- Persistence через Redis Streams (опционально)
- Rate limiting (global + per-source)
- Все на РУССКОМ языке
"""

from __future__ import annotations

import asyncio
from asyncio import Queue
from collections import defaultdict
from datetime import UTC, datetime
from enum import StrEnum
import json
import threading
from typing import TYPE_CHECKING, Any, ClassVar
import uuid

import redis.asyncio as redis

from cryptotechnolog.config import get_logger, get_settings

from .event import Event, Priority

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    from .listeners.base import BaseListener, ListenerRegistry

from .listeners import get_listener_registry

logger = get_logger(__name__)


class BackpressureStrategy(StrEnum):
    """Стратегии backpressure при переполнении."""

    DROP_LOW = "drop_low"  # Отбрасывать LOW события
    OVERFLOW_NORMAL = "overflow_normal"  # Переполнение в NORMAL очередь
    DROP_NORMAL = "drop_normal"  # Отбрасывать NORMAL + LOW
    BLOCK_CRITICAL = "block_critical"  # Блокировать только CRITICAL


# Threshold constants for backpressure fill ratios
_FILL_RATIO_LOW = 0.7
_FILL_RATIO_NORMAL = 0.8
_FILL_RATIO_HIGH = 0.9


class RateLimitError(Exception):
    """Ошибка превышения rate limit."""

    pass


class PersistenceError(Exception):
    """Ошибка сохранения в Redis."""

    pass


class BackpressureError(Exception):
    """Ошибка backpressure."""

    pass


class PublishError(Exception):
    """Ошибка публикации события."""

    pass


# ==================== Async Receiver ====================


class AsyncEventReceiver:
    """
    Асинхронный приёмник событий (модифицированная версия).
    """

    def __init__(self, queue: Queue[Event | None], event_bus: EnhancedEventBus) -> None:
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


# ==================== Priority Queue ====================


class PriorityQueue:
    """
    Очередь с приоритетами для событий.

    4 отдельные очереди с разной ёмкостью для каждого приоритета.
    """

    DEFAULT_CAPACITIES: ClassVar[dict[Priority, int]] = {
        Priority.CRITICAL: 100,
        Priority.HIGH: 500,
        Priority.NORMAL: 10000,
        Priority.LOW: 50000,
    }

    def __init__(self, capacities: dict[Priority, int] | None = None) -> None:
        """Инициализировать очередь с приоритетами."""
        caps = capacities if capacities is not None else self.DEFAULT_CAPACITIES
        self.queues = {
            priority: Queue[Event](maxsize=caps.get(priority, self.DEFAULT_CAPACITIES[priority]))
            for priority in Priority
        }
        self._lock = asyncio.Lock()
        self._total_pushed = 0
        self._total_popped = 0
        self._dropped_count = dict.fromkeys(Priority, 0)

    async def push(self, event: Event) -> bool:
        """
        Добавить событие в соответствующую очередь.

        Аргументы:
            event: Событие для добавления

        Возвращает:
            True если событие добавлено, False если очередь полная
        """
        queue = self.queues[event.priority]

        try:
            queue.put_nowait(event)
            self._total_pushed += 1
            return True
        except asyncio.QueueFull:
            self._dropped_count[event.priority] += 1
            return False

    async def push_wait(self, event: Event, timeout: float = 5.0) -> bool:
        """
        Добавить событие с ожиданием.

        Аргументы:
            event: Событие для добавления
            timeout: Таймаут ожидания в секундах

        Возвращает:
            True если событие добавлено, False при таймауте
        """
        queue = self.queues[event.priority]

        try:
            await asyncio.wait_for(queue.put(event), timeout=timeout)
            self._total_pushed += 1
            return True
        except TimeoutError:
            self._dropped_count[event.priority] += 1
            return False

    async def pop(self) -> Event | None:
        """
        Извлечь следующее событие по приоритету.

        Возвращает:
            Событие с наивысшим приоритетом или None если все очереди пустые
        """
        # Поиск в порядке приоритета: CRITICAL -> HIGH -> NORMAL -> LOW
        for priority in [Priority.CRITICAL, Priority.HIGH, Priority.NORMAL, Priority.LOW]:
            queue = self.queues[priority]
            try:
                event = queue.get_nowait()
                self._total_popped += 1
                return event
            except asyncio.QueueEmpty:
                continue
        return None

    def size(self, priority: Priority) -> int:
        """Получить размер очереди для заданного приоритета."""
        return self.queues[priority].qsize()

    def total_size(self) -> int:
        """Получить общий размер всех очередей."""
        return sum(q.qsize() for q in self.queues.values())

    def capacity(self, priority: Priority) -> int:
        """Получить ёмкость очереди для заданного приоритета."""
        return self.queues[priority].maxsize

    def get_metrics(self) -> dict[str, Any]:
        """Получить метрики очереди."""
        return {
            "total_pushed": self._total_pushed,
            "total_popped": self._total_popped,
            "dropped_by_priority": {p.value: count for p, count in self._dropped_count.items()},
            "queue_sizes": {p.value: self.size(p) for p in Priority},
            "queue_capacities": {p.value: self.capacity(p) for p in Priority},
        }


# ==================== Rate Limiter ====================


class RateLimiter:
    """
    Rate limiter с sliding window.

    Ограничивает частоту событий по источнику и глобально.
    """

    def __init__(self, global_limit: int = 10000) -> None:
        """Инициализировать rate limiter."""
        self.global_limit = global_limit
        self.source_limits: dict[str, int] = {}
        self.counts: dict[str, list[float]] = defaultdict(list)
        self.global_counts: list[float] = []
        self._lock = threading.Lock()

    def set_source_limit(self, source: str, limit: int) -> None:
        """Установить лимит для конкретного источника."""
        self.source_limits[source] = limit

    def check(self, source: str) -> bool:
        """
        Проверить, можно ли принять событие от источника.

        Аргументы:
            source: Источник события

        Возвращает:
            True если можно принять событие, False если превышен лимит
        """
        current_time = datetime.now(UTC).timestamp()

        with self._lock:
            # Проверить глобальный лимит
            self.global_counts = [t for t in self.global_counts if current_time - t < 1.0]
            if len(self.global_counts) >= self.global_limit:
                return False

            # Проверить лимит источника
            if source in self.source_limits:
                source_limit = self.source_limits[source]
                self.counts[source] = [
                    t for t in self.counts.get(source, []) if current_time - t < 1.0
                ]
                if len(self.counts[source]) >= source_limit:
                    return False

            # Увеличить счётчики
            self.global_counts.append(current_time)
            if source in self.source_limits:
                self.counts[source].append(current_time)

            return True

    def get_metrics(self) -> dict[str, Any]:
        """Получить метрики rate limiter."""
        with self._lock:
            return {
                "global_limit": self.global_limit,
                "global_rate": len(self.global_counts),
                "source_limits": self.source_limits.copy(),
                "source_rates": {source: len(counts) for source, counts in self.counts.items()},
            }


# ==================== Persistence Layer ====================


class PersistenceLayer:
    """
    Слой персистентности через Redis Streams.
    """

    def __init__(self, redis_url: str) -> None:
        """Инициализировать persistence layer."""
        self.redis_url = redis_url
        self.redis: redis.Redis | None = None
        self.stream_prefix = "events"
        self.max_stream_len = 100000  # Максимальная длина stream

    async def connect(self) -> None:
        """Установить соединение с Redis."""
        if self.redis is None:
            try:
                self.redis = redis.from_url(self.redis_url, decode_responses=True)
                await self.redis.ping()
                logger.info("Соединение с Redis для persistence установлено", url=self.redis_url)
            except Exception as e:
                logger.error("Ошибка подключения к Redis", error=str(e), url=self.redis_url)
                raise PersistenceError(f"Не удалось подключиться к Redis: {e}") from e

    async def disconnect(self) -> None:
        """Разорвать соединение с Redis."""
        if self.redis:
            await self.redis.close()
            self.redis = None
            logger.info("Соединение с Redis разорвано")

    async def save_event(self, event: Event) -> str | None:
        """
        Сохранить событие в Redis Stream.

        Аргументы:
            event: Событие для сохранения

        Возвращает:
            ID stream записи или None при ошибке
        """
        if self.redis is None:
            await self.connect()

        try:
            # Создать stream key на основе приоритета
            stream_key = f"{self.stream_prefix}:{event.priority.value}"

            # Сериализовать событие
            event_dict = event.to_dict()
            event_json = json.dumps(event_dict, ensure_ascii=False)

            # Добавить в stream с ограничением длины
            stream_id = await self.redis.xadd(
                stream_key, {"event": event_json}, maxlen=self.max_stream_len, approximate=True
            )

            logger.debug(
                "Событие сохранено в Redis",
                event_id=event.id,
                stream_id=stream_id,
                priority=event.priority.value,
            )

            return stream_id

        except Exception as e:
            logger.error("Ошибка сохранения события в Redis", event_id=event.id, error=str(e))
            raise PersistenceError(f"Ошибка сохранения события: {e}") from e

    async def save_batch(self, events: list[Event]) -> list[str | None]:
        """
        Сохранить batch событий.

        Аргументы:
            events: Список событий для сохранения

        Возвращает:
            Список ID stream записей
        """
        if not events:
            return []

        results = []
        for event in events:
            try:
                stream_id = await self.save_event(event)
                results.append(stream_id)
            except PersistenceError:
                results.append(None)

        return results

    async def replay(
        self, priority: Priority, from_id: str | None = None, limit: int = 100
    ) -> list[Event]:
        """
        Воспроизвести события из Redis Stream.

        Аргументы:
            priority: Приоритет для воспроизведения
            from_id: Начальный ID (None для начала)
            limit: Максимальное количество событий

        Возвращает:
            Список событий
        """
        if self.redis is None:
            await self.connect()

        try:
            stream_key = f"{self.stream_prefix}:{priority.value}"

            # Использовать '0-0' для начала если from_id не указан
            start = from_id if from_id else "0-0"

            # Чтение из stream
            stream_data = await self.redis.xrange(stream_key, min=start, max="+", count=limit)

            events = []
            for _stream_id, data in stream_data:
                event_json = data["event"]
                event_dict = json.loads(event_json)
                event = Event.from_dict(event_dict)
                events.append(event)

            logger.debug(
                "Воспроизведены события из Redis",
                count=len(events),
                priority=priority.value,
                from_id=from_id,
            )

            return events

        except Exception as e:
            logger.error(
                "Ошибка воспроизведения событий из Redis", error=str(e), priority=priority.value
            )
            raise PersistenceError(f"Ошибка воспроизведения: {e}") from e

    async def get_stream_length(self, priority: Priority) -> int:
        """Получить длину stream для заданного приоритета."""
        if self.redis is None:
            await self.connect()

        stream_key = f"{self.stream_prefix}:{priority.value}"
        return await self.redis.xlen(stream_key)


# ==================== Enhanced Event Bus ====================


class EnhancedEventBus:
    """
    Enhanced Event Bus с приоритетами, backpressure, persistence.

    Реализует расширенную функциональность поверх базового EventBus.
    """

    DEFAULT_SUBSCRIBER_CAPACITY = 1024

    def __init__(
        self,
        enable_persistence: bool = False,
        redis_url: str | None = None,
        capacities: dict[str, int] | None = None,
        rate_limit: int = 10000,
        backpressure_strategy: str = "drop_low",
        subscriber_capacity: int | None = None,
    ) -> None:
        """
        Инициализировать Enhanced Event Bus.

        Аргументы:
            enable_persistence: Включить сохранение событий в Redis
            redis_url: URL Redis для persistence (если включено)
            capacities: Ёмкости очередей для каждого приоритета
            rate_limit: Глобальный rate limit (событий в секунду)
            backpressure_strategy: Стратегия backpressure
            subscriber_capacity: Ёмкость очереди подписчика
        """
        # Конфигурация subscriber queue
        self.subscriber_capacity = subscriber_capacity or self.DEFAULT_SUBSCRIBER_CAPACITY
        # Настройки из параметров или defaults
        settings = get_settings()

        # Ёмкости очередей
        default_capacities = {
            Priority.CRITICAL: settings.event_bus_capacity_critical,
            Priority.HIGH: settings.event_bus_capacity_high,
            Priority.NORMAL: settings.event_bus_capacity_normal,
            Priority.LOW: settings.event_bus_capacity_low,
        }

        if capacities:
            for priority_str, capacity in capacities.items():
                priority = Priority.from_string(priority_str)
                default_capacities[priority] = capacity

        # Rate limit
        self.rate_limit = rate_limit or settings.event_bus_rate_limit

        # Backpressure strategy
        self.backpressure_strategy = BackpressureStrategy(
            backpressure_strategy or settings.event_bus_backpressure_strategy
        )

        # Инициализация компонентов
        self.priority_queue = PriorityQueue(default_capacities)
        self.rate_limiter = RateLimiter(global_limit=self.rate_limit)

        # Persistence
        self.enable_persistence = enable_persistence
        if enable_persistence and redis_url:
            redis_url = redis_url or settings.event_bus_redis_url
            self.persistence = PersistenceLayer(redis_url)
        else:
            self.persistence = None

        # Subscribers management
        self.subscribers: dict[int, AsyncEventReceiver] = {}
        self._subscriber_lock = threading.Lock()
        self.next_subscriber_id = 0

        # Event handlers by type
        self.handlers: dict[str, list[Callable[[Event], Any]]] = defaultdict(list)

        # Listener registry integration
        self.listener_registry: ListenerRegistry | None = None
        self.wildcard_listeners: list[BaseListener] = []
        self.pending_tasks: list[asyncio.Task] = []

        # Statistics
        self.metrics = {
            "published": 0,
            "delivered": 0,
            "dropped": 0,
            "persisted": 0,
            "rate_limited": 0,
        }

        logger.info(
            "EnhancedEventBus инициализирован",
            enable_persistence=enable_persistence,
            rate_limit=self.rate_limit,
            backpressure_strategy=self.backpressure_strategy.value,
            capacities=default_capacities,
        )

    async def start(self) -> None:
        """Запустить Enhanced Event Bus."""
        if self.enable_persistence and self.persistence:
            try:
                await self.persistence.connect()
                logger.info("Persistence layer запущен")
            except Exception as e:
                logger.error("Не удалось запустить persistence layer", error=str(e))
                self.enable_persistence = False

        logger.info("EnhancedEventBus запущен")

    async def shutdown(self) -> None:
        """Корректно завершить работу."""
        # Отменяем все ожидающие задачи
        for task in self.pending_tasks:
            if not task.done():
                task.cancel()

        if self.pending_tasks:
            await asyncio.gather(*self.pending_tasks, return_exceptions=True)

        # Отключаем persistence
        if self.persistence:
            await self.persistence.disconnect()

        logger.info("EnhancedEventBus завершен")

    def subscribe(self) -> AsyncEventReceiver:
        """
        Подписаться на события.

        Каждый подписчик получает копию каждого опубликованного события.

        Возвращает:
            AsyncEventReceiver для получения событий
        """
        queue: Queue[Event | None] = Queue(maxsize=self.subscriber_capacity)
        receiver = AsyncEventReceiver(queue, self)

        with self._subscriber_lock:
            subscriber_id = self.next_subscriber_id
            self.subscribers[subscriber_id] = receiver
            self.next_subscriber_id += 1

        logger.debug(
            "Новый подписчик EnhancedEventBus",
            subscriber_id=subscriber_id,
            total_subscribers=len(self.subscribers),
        )

        return receiver

    def _remove_subscriber(self, receiver: AsyncEventReceiver) -> None:
        """Удалить подписчика (внутренний метод)."""
        with self._subscriber_lock:
            for sid, sub in list(self.subscribers.items()):
                if sub is receiver:
                    del self.subscribers[sid]
                    logger.debug(
                        "Подписчик удалён",
                        subscriber_id=sid,
                        remaining=len(self.subscribers),
                    )
                    return

    def unsubscribe(self, receiver: AsyncEventReceiver) -> None:
        """
        Отписаться от событий.

        Аргументы:
            receiver: Приёмник для отписки
        """
        self._remove_subscriber(receiver)

    async def _check_rate_limit(self, source: str) -> bool:
        """
        Проверить rate limit для источника.

        Аргументы:
            source: Источник события

        Возвращает:
            True если лимит не превышен
        """
        if not self.rate_limiter.check(source):
            self.metrics["rate_limited"] += 1
            logger.warning(
                "Rate limit превышен",
                source=source,
                rate=self.rate_limit,
            )
            return False
        return True

    def _determine_backpressure_action(self, event: Event) -> BackpressureStrategy | None:
        """
        Определить действие backpressure на основе стратегии и состояния очередей.

        Аргументы:
            event: Событие для публикации

        Возвращает:
            Действие backpressure или None если событие должно быть принято
        """
        # Получить заполненность очереди для приоритета события
        queue_size = self.priority_queue.size(event.priority)
        queue_capacity = self.priority_queue.capacity(event.priority)
        fill_ratio = queue_size / queue_capacity if queue_capacity > 0 else 0.0

        # Применить стратегию backpressure
        if (
            self.backpressure_strategy == BackpressureStrategy.DROP_LOW
            and event.priority == Priority.LOW
            and fill_ratio > _FILL_RATIO_LOW
        ):
            return BackpressureStrategy.DROP_LOW

        elif (
            self.backpressure_strategy == BackpressureStrategy.OVERFLOW_NORMAL
            and event.priority == Priority.NORMAL
            and fill_ratio > _FILL_RATIO_NORMAL
        ):
            return BackpressureStrategy.OVERFLOW_NORMAL

        elif (
            self.backpressure_strategy == BackpressureStrategy.DROP_NORMAL
            and event.priority in (Priority.NORMAL, Priority.LOW)
            and fill_ratio > _FILL_RATIO_HIGH
        ):
            return BackpressureStrategy.DROP_NORMAL

        elif (
            self.backpressure_strategy == BackpressureStrategy.BLOCK_CRITICAL
            and event.priority == Priority.CRITICAL
            and fill_ratio > _FILL_RATIO_HIGH
        ):
            return BackpressureStrategy.BLOCK_CRITICAL

        # По умолчанию - принять событие
        return None

    async def _persist_event(self, event: Event) -> bool:
        """
        Сохранить событие в Redis (если включено и требуется по приоритету).

        Аргументы:
            event: Событие для сохранения

        Возвращает:
            True если успешно сохранено или не требуется
        """
        if not self.enable_persistence or not self.persistence:
            return True

        if not event.priority.requires_persistence():
            return True

        try:
            await self.persistence.save_event(event)
            self.metrics["persisted"] += 1
            return True
        except PersistenceError as e:
            logger.error("Ошибка сохранения события", event_id=event.id, error=str(e))
            # Для CRITICAL событий это критическая ошибка
            if event.priority == Priority.CRITICAL:
                raise BackpressureError(f"Критическая ошибка сохранения: {e}") from e
            return False

    def _deliver_to_subscribers(self, event: Event) -> int:
        """Доставить событие подписчикам. Возвращает количество доставленных."""
        delivered = 0
        with self._subscriber_lock:
            if not self.subscribers:
                return 0

            disconnected = []
            for subscriber_id, receiver in self.subscribers.items():
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
                del self.subscribers[sid]

        return delivered

    async def _call_handlers(self, event: Event) -> None:
        """
        Вызвать зарегистрированные обработчики для события.

        Аргументы:
            event: Событие для обработки
        """
        # Получить обработчики для конкретного типа события
        handlers = self.handlers.get(event.event_type, [])
        wildcard_handlers = self.handlers.get("*", [])

        all_handlers = handlers + wildcard_handlers

        for handler in all_handlers:
            try:
                # Проверить является ли обработчик async
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                logger.error(
                    "Ошибка в обработчике события",
                    event_type=event.event_type,
                    handler=str(handler),
                    error=str(e),
                )

    async def _call_listeners(self, event: Event) -> None:
        """
        Вызвать зарегистрированные listeners для события.

        Аргументы:
            event: Событие для обработки
        """
        if not self.listener_registry:
            return

        try:
            listeners = self.listener_registry.get_listeners_for_event(event)
            for listener in listeners:
                try:
                    await listener.handle(event)
                except Exception as e:
                    logger.error(
                        "Ошибка в listener",
                        event_type=event.event_type,
                        listener=listener.name,
                        error=str(e),
                    )
        except Exception as e:
            logger.error(
                "Ошибка при вызове listeners",
                event_type=event.event_type,
                error=str(e),
            )

    async def publish(self, event: Event) -> bool:
        """
        Опубликовать событие с учётом приоритета, rate limit и backpressure.

        Аргументы:
            event: Событие для публикации

        Возвращает:
            True если событие успешно опубликовано

        Вызывает:
            PublishError: Если событие не может быть опубликовано
        """
        # 1. Проверить rate limit
        if not await self._check_rate_limit(event.source):
            raise PublishError(f"Rate limit превышен для источника: {event.source}") from None

        # 2. Определить действие backpressure
        backpressure_action = self._determine_backpressure_action(event)

        # 3. Обработать событие в соответствии со стратегией
        if backpressure_action == BackpressureStrategy.DROP_LOW and event.priority == Priority.LOW:
            # Проверить заполненность очереди LOW
            fill_ratio = self.priority_queue.size(Priority.LOW) / self.priority_queue.capacity(
                Priority.LOW
            )
            if fill_ratio > _FILL_RATIO_LOW:
                self.metrics["dropped"] += 1
                logger.warning(
                    "LOW событие отброшено (backpressure)",
                    event_type=event.event_type,
                    source=event.source,
                )
                return False
        elif backpressure_action == BackpressureStrategy.DROP_NORMAL and event.priority in (
            Priority.NORMAL,
            Priority.LOW,
        ):
            self.metrics["dropped"] += 1
            logger.warning(
                f"{event.priority.value} событие отброшено (backpressure)",
                event_type=event.event_type,
                source=event.source,
            )
            return False

        # 4. Добавить событие в очередь
        if backpressure_action == BackpressureStrategy.BLOCK_CRITICAL:
            # Для CRITICAL - ждать с таймаутом
            success = await self.priority_queue.push_wait(event, timeout=5.0)
            if not success:
                raise PublishError("Таймаут добавления CRITICAL события в очередь") from None
        else:
            success = await self.priority_queue.push(event)
            if not success:
                self.metrics["dropped"] += 1
                raise PublishError(f"Очередь {event.priority.value} переполнена") from None

        # 5. Сохранить событие в persistence (async, не ждём завершения)
        if self.enable_persistence:
            task = asyncio.create_task(self._persist_event(event))
            self.pending_tasks.append(task)

        # 6. Обновить метрики
        self.metrics["published"] += 1

        # 7. Доставить подписчикам (синхронно)
        delivered = self._deliver_to_subscribers(event)
        self.metrics["delivered"] += delivered

        # 8. Вызвать зарегистрированные обработчики
        await self._call_handlers(event)

        # 9. Вызвать listeners если они включены
        await self._call_listeners(event)

        logger.debug(
            "Событие опубликовано",
            event_type=event.event_type,
            priority=event.priority.value,
            source=event.source,
            delivered=delivered,
        )

        return delivered > 0

    async def publish_with_priority(
        self,
        event_type: str,
        source: str,
        payload: dict[str, Any],
        priority: Priority = Priority.NORMAL,
        correlation_id: str | None = None,
    ) -> bool:
        """
        Удобный метод для публикации события с указанием приоритета.

        Аргументы:
            event_type: Тип события
            source: Источник события
            payload: Данные события
            priority: Приоритет события
            correlation_id: Опциональный correlation ID

        Возвращает:
            True если событие успешно опубликовано
        """
        event = Event.new(event_type, source, payload)
        event.priority = priority

        if correlation_id:
            event.correlation_id = uuid.UUID(correlation_id)

        return await self.publish(event)

    def set_backpressure_strategy(self, strategy: str) -> None:
        """Установить стратегию backpressure."""
        try:
            self.backpressure_strategy = BackpressureStrategy(strategy)
            logger.info("Стратегия backpressure обновлена", strategy=strategy)
        except ValueError as e:
            raise ValueError(f"Неизвестная стратегия backpressure: {strategy}") from e

    def set_rate_limit(self, limit: int) -> None:
        """Установить глобальный rate limit."""
        self.rate_limit = limit
        self.rate_limiter.global_limit = limit
        logger.info("Rate limit обновлён", limit=limit)

    async def replay(
        self,
        priority: Priority,
        from_id: str | None = None,
        limit: int = 100,
    ) -> list[Event]:
        """
        Воспроизвести события из persistence.

        Аргументы:
            priority: Приоритет для воспроизведения
            from_id: Начальный ID (None для начала)
            limit: Максимальное количество событий

        Возвращает:
            Список событий
        """
        if not self.enable_persistence or not self.persistence:
            raise PersistenceError("Persistence не включен") from None

        return await self.persistence.replay(priority, from_id, limit)

    def get_metrics(self) -> dict[str, Any]:
        """
        Получить метрики Enhanced Event Bus.

        Возвращает:
            Словарь с метриками
        """
        queue_metrics = self.priority_queue.get_metrics()
        rate_limiter_metrics = self.rate_limiter.get_metrics()

        return {
            "bus_metrics": self.metrics.copy(),
            "queue_metrics": queue_metrics,
            "rate_limiter_metrics": rate_limiter_metrics,
            "subscriber_count": len(self.subscribers),
            "enable_persistence": self.enable_persistence,
            "backpressure_strategy": self.backpressure_strategy.value,
            "rate_limit": self.rate_limit,
        }

    def on(self, event_type: str, handler: Callable[[Event], Any]) -> None:
        """Зарегистрировать обработчик для типа событий."""
        self.handlers[event_type].append(handler)
        handler_name = getattr(handler, "__name__", str(handler))
        logger.debug(
            "Обработчик зарегистрирован в EnhancedEventBus",
            event_type=event_type,
            handler=handler_name,
        )

    def off(self, event_type: str, handler: Callable[[Event], Any]) -> None:
        """Удалить обработчик для типа событий."""
        if event_type in self.handlers:
            try:
                self.handlers[event_type].remove(handler)
                logger.debug(
                    "Обработчик удалён из EnhancedEventBus",
                    event_type=event_type,
                )
            except ValueError:
                pass

    def register_listener(self, listener: BaseListener) -> None:
        """
        Зарегистрировать listener в Event Bus.

        Аргументы:
            listener: Listener для регистрации
        """
        if self.listener_registry is None:
            self.listener_registry = get_listener_registry()

        self.listener_registry.register(listener)
        logger.info(
            "Listener зарегистрирован в EnhancedEventBus",
            listener_name=listener.name,
            event_types=listener.event_types,
            total_listeners=len(self.listener_registry.all_listeners),
        )

    def unregister_listener(self, name: str) -> bool:
        """
        Удалить listener из Event Bus.

        Аргументы:
            name: Имя listener для удаления

        Возвращает:
            True если listener был удалён
        """
        if self.listener_registry is None:
            return False

        result = self.listener_registry.unregister(name)
        if result:
            logger.info("Listener удалён из EnhancedEventBus", listener_name=name)
        return result

    def enable_listeners(self) -> None:
        """Включить listeners для Event Bus."""
        registry = get_listener_registry()
        self.listener_registry = registry

        logger.info(
            "Listeners enabled для EnhancedEventBus",
            listener_count=len(registry.all_listeners),
        )

    def disable_listeners(self) -> None:
        """Выключить listeners."""
        self.listener_registry = None
        self.wildcard_listeners = []
        logger.info("Listeners disabled")

    async def drain(self, timeout: float = 30.0) -> bool:
        """
        Дождаться обработки всех ожидающих событий.

        Аргументы:
            timeout: Максимальное время ожидания в секундах

        Возвращает:
            True если все события обработаны, False при таймауте
        """
        logger.info("Начало drain EnhancedEventBus", timeout=timeout)

        start_time = asyncio.get_event_loop().time()

        while True:
            # Проверить общее количество событий в очередях
            total_pending = self.priority_queue.total_size()

            # Проверить события у подписчиков
            with self._subscriber_lock:
                subscriber_pending = sum(
                    receiver._queue.qsize() for receiver in self.subscribers.values()
                )

            total_pending += subscriber_pending

            if total_pending == 0:
                logger.info("EnhancedEventBus drain завершён")
                return True

            # Проверить таймаут
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed >= timeout:
                logger.warning(
                    "EnhancedEventBus drain - таймаут",
                    pending=total_pending,
                    elapsed=elapsed,
                )
                return False

            await asyncio.sleep(0.5)

    async def flush(self) -> None:
        """Дождаться завершения всех асинхронных задач обработки."""
        if self.pending_tasks:
            pending = [t for t in self.pending_tasks if not t.done()]
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
            self.pending_tasks.clear()

    def clear(self) -> None:
        """Очистить всех подписчиков и обработчики."""
        with self._subscriber_lock:
            self.subscribers.clear()
        self.handlers.clear()
        self.wildcard_listeners.clear()
        logger.info("EnhancedEventBus очищен")

    def __repr__(self) -> str:
        return (
            f"EnhancedEventBus(subscribers={len(self.subscribers)}, "
            f"strategy={self.backpressure_strategy.value}, "
            f"persistence={self.enable_persistence})"
        )

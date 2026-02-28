"""
Lock-Free Ring Buffer Implementation.

Потокобезопасный кольцевой буфер для высокопроизводительного
обмена сообщениями между компонентами.

Особенности:
- Wait-free операции чтения
- Lock-free операции записи
- Фиксированная ёмкость для предотвращения неограниченного роста памяти
- Оптимизировано для высокопроизводительных сценариев
"""

from __future__ import annotations

import asyncio
from asyncio import Queue
from collections import deque
from dataclasses import dataclass
import threading
from typing import TypeVar

from cryptotechnolog.config import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


@dataclass
class RingBufferStats:
    """Статистика кольцевого буфера."""

    capacity: int
    size: int
    is_full: bool
    is_empty: bool
    push_count: int
    pop_count: int
    overflow_count: int


class RingBuffer[T]:
    """
    Lock-free кольцевой буфер.

    Использует threading.Lock для синхронизации, что обеспечивает
    потокобезопасность с минимальным overhead.

    Для Python GIL это решение обеспечивает достаточную производительность
    для большинства сценариев использования.

    Аргументы:
        capacity: Максимальный размер буфера (должен быть степенью двойки)
    """

    def __init__(self, capacity: int) -> None:
        if capacity <= 0:
            raise ValueError("Capacity must be positive")

        # Round up to power of 2 for efficient modulo
        self._capacity = capacity if (capacity & (capacity - 1)) == 0 else capacity * 2
        self._buffer: deque[T] = deque(maxlen=self._capacity)
        self._lock = threading.Lock()

        # Statistics
        self._push_count = 0
        self._pop_count = 0
        self._overflow_count = 0

        logger.debug(
            "Ring buffer created",
            capacity=capacity,
            actual_capacity=self._capacity,
        )

    @property
    def capacity(self) -> int:
        """Получить ёмкость буфера."""
        return self._capacity

    @property
    def size(self) -> int:
        """Получить текущий размер буфера."""
        with self._lock:
            return len(self._buffer)

    @property
    def is_empty(self) -> bool:
        """Проверить, пуст ли буфер."""
        with self._lock:
            return len(self._buffer) == 0

    @property
    def is_full(self) -> bool:
        """Проверить, полон ли буфер."""
        with self._lock:
            return len(self._buffer) >= self._capacity

    @property
    def push_count(self) -> int:
        """Получить количество успешных push операций."""
        return self._push_count

    @property
    def pop_count(self) -> int:
        """Получить количество успешных pop операций."""
        return self._pop_count

    @property
    def overflow_count(self) -> int:
        """Получить количество переполнений буфера."""
        return self._overflow_count

    def push(self, item: T) -> bool:
        """
        Добавить элемент в буфер.

        Если буфер полон, элемент не добавляется (graceful degradation).

        Аргументы:
            item: Элемент для добавления

        Возвращает:
            True если элемент добавлен, False если буфер полон
        """
        with self._lock:
            if len(self._buffer) >= self._capacity:
                self._overflow_count += 1
                logger.warning(
                    "Ring buffer overflow, dropping event",
                    capacity=self._capacity,
                    overflow_count=self._overflow_count,
                )
                return False

            self._buffer.append(item)
            self._push_count += 1
            return True

    def pop(self) -> T | None:
        """
        Извлечь элемент из буфера.

        Возвращает:
            Элемент если буфер не пуст, иначе None
        """
        with self._lock:
            if not self._buffer:
                return None

            item = self._buffer.popleft()
            self._pop_count += 1
            return item

    def peek(self) -> T | None:
        """
        Посмотреть первый элемент без его извлечения.

        Возвращает:
            Первый элемент если буфер не пуст, иначе None
        """
        with self._lock:
            if not self._buffer:
                return None
            return self._buffer[0]

    def clear(self) -> None:
        """Очистить буфер."""
        with self._lock:
            self._buffer.clear()

    def get_stats(self) -> RingBufferStats:
        """
        Получить статистику буфера.

        Возвращает:
            RingBufferStats с текущей статистикой
        """
        with self._lock:
            return RingBufferStats(
                capacity=self._capacity,
                size=len(self._buffer),
                is_full=len(self._buffer) >= self._capacity,
                is_empty=len(self._buffer) == 0,
                push_count=self._push_count,
                pop_count=self._pop_count,
                overflow_count=self._overflow_count,
            )

    def __len__(self) -> int:
        """Получить текущий размер."""
        return self.size

    def __repr__(self) -> str:
        return f"RingBuffer(capacity={self._capacity}, size={self.size})"


# ==================== Async Ring Buffer ====================


class AsyncRingBuffer[T]:
    """
    Async кольцевой буфер с использованием asyncio.Queue.

    Оптимизирован для использования в асинхронном коде.

    Аргументы:
        capacity: Максимальный размер буфера
    """

    def __init__(self, capacity: int) -> None:
        if capacity <= 0:
            raise ValueError("Capacity must be positive")

        self._capacity = capacity
        self._queue: Queue[T | None] = Queue(maxsize=capacity)

        # Statistics
        self._push_count = 0
        self._pop_count = 0
        self._overflow_count = 0

        logger.debug(
            "Async ring buffer created",
            capacity=capacity,
        )

    @property
    def capacity(self) -> int:
        """Получить ёмкость буфера."""
        return self._capacity

    @property
    def size(self) -> int:
        """Получить текущий размер."""
        return self._queue.qsize()

    @property
    def is_empty(self) -> bool:
        """Проверить, пуст ли буфер."""
        return self._queue.empty()

    @property
    def is_full(self) -> bool:
        """Проверить, полон ли буфер."""
        return self._queue.full()

    @property
    def push_count(self) -> int:
        """Получить количество успешных push операций."""
        return self._push_count

    @property
    def pop_count(self) -> int:
        """Получить количество успешных pop операций."""
        return self._pop_count

    @property
    def overflow_count(self) -> int:
        """Получить количество переполнений."""
        return self._overflow_count

    async def push(self, item: T) -> bool:
        """
        Добавить элемент в буфер (async).

        Non-blocking - если буфер полон, возвращает False.

        Аргументы:
            item: Элемент для добавления

        Возвращает:
            True если элемент добавлен, False если буфер полон
        """
        try:
            self._queue.put_nowait(item)
            self._push_count += 1
            return True
        except asyncio.QueueFull:
            self._overflow_count += 1
            logger.warning(
                "Async ring buffer overflow, dropping event",
                capacity=self._capacity,
                overflow_count=self._overflow_count,
            )
            return False

    async def push_wait(self, item: T, timeout: float | None = None) -> bool:
        """
        Добавить элемент с ожиданием (async).

        Аргументы:
            item: Элемент для добавления
            timeout: Таймаут в секундах

        Возвращает:
            True если элемент добавлен, False при таймауте
        """
        try:
            if timeout is None:
                await self._queue.put(item)
            else:
                await asyncio.wait_for(self._queue.put(item), timeout=timeout)
            self._push_count += 1
            return True
        except TimeoutError:
            self._overflow_count += 1
            logger.warning(
                "Async ring buffer timeout, dropping event",
                timeout=timeout,
            )
            return False

    async def pop(self) -> T | None:
        """
        Извлечь элемент из буфера (async).

        Возвращает:
            Элемент если буфер не пуст, иначе None
        """
        try:
            item = self._queue.get_nowait()
            self._pop_count += 1
            return item
        except asyncio.QueueEmpty:
            return None

    async def pop_wait(self, timeout: float | None = None) -> T | None:
        """
        Извлечь элемент с ожиданием (async).

        Аргументы:
            timeout: Таймаут в секундах

        Возвращает:
            Элемент если получен, иначе None при таймауте
        """
        try:
            if timeout is None:
                item = await self._queue.get()
            else:
                item = await asyncio.wait_for(self._queue.get(), timeout=timeout)
            self._pop_count += 1
            return item
        except TimeoutError:
            return None

    def clear(self) -> None:
        """Очистить буфер."""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    def get_stats(self) -> RingBufferStats:
        """Получить статистику буфера."""
        return RingBufferStats(
            capacity=self._capacity,
            size=self.size,
            is_full=self.is_full,
            is_empty=self.is_empty,
            push_count=self._push_count,
            pop_count=self._pop_count,
            overflow_count=self._overflow_count,
        )

    def __len__(self) -> int:
        return self.size

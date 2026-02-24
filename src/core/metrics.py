"""
Metrics Collector — система сбора и хранения метрик.

Использует in-memory хранение с Redis для персистентности.
Поддерживает:
- Counters (счетчики)
- Gauges (текущие значения)
- Histograms (гистограммы)
- Event-driven collection (подписка на Event Bus)

Метрики соответствуют спецификации Prometheus:
- event_published_total{source, event_type, priority}
- event_delivered_total{event_type, subscriber}
- event_dropped_total{reason, priority}
- db_connections_active{database}
- db_query_duration_seconds{query_type, database, percentile}
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable

from cryptotechnolog.config import get_logger, get_settings

if TYPE_CHECKING:
    from collections.abc import Awaitable

logger = get_logger(__name__)


class MetricType(Enum):
    """Типы метрик."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"


@dataclass
class MetricMetadata:
    """Метаданные метрики."""

    name: str
    metric_type: MetricType
    description: str
    labels: dict[str, str] = field(default_factory=dict)
    unit: str = ""


@dataclass
class HistogramBuckets:
    """Buckets для гистограммы."""

    buckets: list[float] = field(
        default_factory=lambda: [0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0]
    )

    def get_bucket(self, value: float) -> int:
        """Получить индекс бакета для значения."""
        for i, bucket in enumerate(self.buckets):
            if value <= bucket:
                return i
        return len(self.buckets)


class Counter:
    """
    Счетчик — метрика, которая только увеличивается.

    Используется для подсчета событий, запросов, ошибок и т.д.

    Пример:
        >>> counter = Counter("requests_total", "Всего запросов")
        >>> counter.inc()
        >>> counter.inc(5)
        >>> print(counter.value)  # 6
    """

    def __init__(self, name: str, description: str = "", labels: dict[str, str] | None = None) -> None:
        """
        Инициализировать счетчик.

        Аргументы:
            name: Имя метрики
            description: Описание метрики
            labels: Дополнительные labels
        """
        self._name = name
        self._description = description
        self._labels = labels or {}
        self._value: float = 0.0
        self._lock = asyncio.Lock()

    @property
    def name(self) -> str:
        """Получить имя метрики."""
        return self._name

    @property
    def value(self) -> float:
        """Получить текущее значение."""
        return self._value

    @property
    def labels(self) -> dict[str, str]:
        """Получить labels."""
        return self._labels.copy()

    async def inc(self, amount: float = 1.0) -> None:
        """
        Увеличить счетчик.

        Аргументы:
            amount: Значение для добавления (по умолчанию 1)
        """
        async with self._lock:
            self._value += amount
            logger.debug(
                "Счетчик увеличен",
                metric=self._name,
                amount=amount,
                total=self._value,
            )

    def inc_sync(self, amount: float = 1.0) -> None:
        """Синхронное увеличение счетчика (без lock)."""
        self._value += amount

    def reset(self) -> None:
        """Сбросить счетчик в 0."""
        self._value = 0.0

    def get_for_prometheus(self) -> str:
        """
        Получить представление в формате Prometheus.

        Returns:
            Строка в формате Prometheus exposition format
        """
        labels_str = ",".join(f'{k}="{v}"' for k, v in self._labels.items())
        if labels_str:
            return f"{self._name}{{{labels_str}}} {self._value}"
        return f"{self._name} {self._value}"


class Gauge:
    """
    Gauge — метрика с текущим значением, может увеличиваться и уменьшаться.

    Используется для отслеживания текущих значений: память, количество соединений и т.д.

    Пример:
        >>> gauge = Gauge("memory_usage_bytes", "Использование памяти")
        >>> gauge.set(1024)
        >>> gauge.inc(256)
        >>> gauge.dec(128)
        >>> print(gauge.value)  # 1152
    """

    def __init__(
        self,
        name: str,
        description: str = "",
        labels: dict[str, str] | None = None,
    ) -> None:
        """
        Инициализировать gauge.

        Аргументы:
            name: Имя метрики
            description: Описание метрики
            labels: Дополнительные labels
        """
        self._name = name
        self._description = description
        self._labels = labels or {}
        self._value: float = 0.0
        self._lock = asyncio.Lock()

    @property
    def name(self) -> str:
        """Получить имя метрики."""
        return self._name

    @property
    def value(self) -> float:
        """Получить текущее значение."""
        return self._value

    @property
    def labels(self) -> dict[str, str]:
        """Получить labels."""
        return self._labels.copy()

    async def set(self, value: float) -> None:
        """
        Установить значение.

        Аргументы:
            value: Новое значение
        """
        async with self._lock:
            self._value = value
            logger.debug(
                "Gauge установлен",
                metric=self._name,
                value=value,
            )

    def set_sync(self, value: float) -> None:
        """Синхронная установка значения (без lock)."""
        self._value = value

    async def inc(self, amount: float = 1.0) -> None:
        """
        Увеличить значение.

        Аргументы:
            amount: Значение для добавления (по умолчанию 1)
        """
        async with self._lock:
            self._value += amount

    async def dec(self, amount: float = 1.0) -> None:
        """
        Уменьшить значение.

        Аргументы:
            amount: Значение для вычитания (по умолчанию 1)
        """
        async with self._lock:
            self._value -= amount

    def inc_sync(self, amount: float = 1.0) -> None:
        """Синхронное увеличение (без lock)."""
        self._value += amount

    def dec_sync(self, amount: float = 1.0) -> None:
        """Синхронное уменьшение (без lock)."""
        self._value -= amount

    def get_for_prometheus(self) -> str:
        """Получить представление в формате Prometheus."""
        labels_str = ",".join(f'{k}="{v}"' for k, v in self._labels.items())
        if labels_str:
            return f"{self._name}{{{labels_str}}} {self._value}"
        return f"{self._name} {self._value}"


class Histogram:
    """
    Гистограмма — метрика для отслеживания распределения значений.

    Используется для задержек, размеров ответов и т.д.

    Пример:
        >>> histogram = Histogram("request_duration_seconds", "Длительность запроса")
        >>> await histogram.observe(0.125)
        >>> await histogram.observe(0.5)
        >>> print(histogram.sum)  # Сумма всех наблюдений
        >>> print(histogram.count)  # Количество наблюдений
    """

    def __init__(
        self,
        name: str,
        description: str = "",
        labels: dict[str, str] | None = None,
        buckets: list[float] | None = None,
    ) -> None:
        """
        Инициализировать гистограмму.

        Аргументы:
            name: Имя метрики
            description: Описание метрики
            labels: Дополнительные labels
            buckets: Границы bucket-ов
        """
        self._name = name
        self._description = description
        self._labels = labels or {}
        self._buckets = HistogramBuckets(buckets or [0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0])

        # Buckets счетчики
        self._bucket_counts: list[int] = [0] * (len(self._buckets.buckets) + 1)
        self._sum: float = 0.0
        self._count: int = 0
        self._lock = asyncio.Lock()

    @property
    def name(self) -> str:
        """Получить имя метрики."""
        return self._name

    @property
    def sum(self) -> float:
        """Получить сумму всех наблюдений."""
        return self._sum

    @property
    def count(self) -> int:
        """Получить количество наблюдений."""
        return self._count

    @property
    def buckets(self) -> list[float]:
        """Получить границы bucket-ов."""
        return self._buckets.buckets

    @property
    def labels(self) -> dict[str, str]:
        """Получить labels."""
        return self._labels.copy()

    async def observe(self, value: float) -> None:
        """
        Записать наблюдение.

        Аргументы:
            value: Наблюдаемое значение
        """
        async with self._lock:
            self._count += 1
            self._sum += value

            # Увеличить все бакеты, которые больше или равны значению
            bucket_idx = self._buckets.get_bucket(value)
            for i in range(bucket_idx, len(self._bucket_counts)):
                self._bucket_counts[i] += 1

            logger.debug(
                "Гистограмма обновлена",
                metric=self._name,
                value=value,
                count=self._count,
            )

    def observe_sync(self, value: float) -> None:
        """Синхронное наблюдение (без lock)."""
        self._count += 1
        self._sum += value
        bucket_idx = self._buckets.get_bucket(value)
        # Увеличиваем только текущий бакет
        if bucket_idx < len(self._bucket_counts):
            self._bucket_counts[bucket_idx] += 1

    def get_quantile(self, quantile: float) -> float:
        """
        Получить значение для заданного квантиля.

        Аргументы:
            quantile: Квантиль (от 0 до 1)

        Returns:
            Значение для квантиля
        """
        if self._count == 0:
            return 0.0

        target_count = int(self._count * quantile)

        # Если target_count = 0, возвращаем минимальное значение
        if target_count == 0:
            return self._buckets.buckets[0] if self._buckets.buckets else 0.0

        # _bucket_counts[i] содержит количество наблюдений в i-м бакете
        # Вычисляем накопленную сумму от начала
        cumulative = 0
        for i in range(len(self._bucket_counts) - 1):
            cumulative += self._bucket_counts[i]
            if cumulative >= target_count:
                # Нашли бакет, возвращаем его границу
                return self._buckets.buckets[i]

        # Если не нашли в обычных бакетах, возвращаем +Inf (последний бакет)
        return self._buckets.buckets[-1] if self._buckets.buckets else float("inf")

    def get_percentile(self, percentile: float) -> float:
        """Получить значение для заданного перцентиля."""
        return self.get_quantile(percentile / 100.0)

    def get_for_prometheus(self) -> str:
        """Получить представление в формате Prometheus."""
        labels_str = ",".join(f'{k}="{v}"' for k, v in self._labels.items())
        base_labels = labels_str

        lines = []

        # HELP и TYPE для гистограммы
        lines.append(f"# HELP {self._name} {self._description or 'Histogram metric'}")
        lines.append(f"# TYPE {self._name} histogram")

        # Sum
        if base_labels:
            lines.append(f"{self._name}_sum{{{base_labels}}} {self._sum}")
            lines.append(f"{self._name}_count{{{base_labels}}} {self._count}")
        else:
            lines.append(f"{self._name}_sum {self._sum}")
            lines.append(f"{self._name}_count {self._count}")

        # Buckets - выводим накопленную сумму
        cumulative = 0
        for i, bucket in enumerate(self._buckets.buckets):
            cumulative += self._bucket_counts[i]
            bucket_labels = self._labels.copy()
            bucket_labels["le"] = str(bucket)
            bl_str = ",".join(f'{k}="{v}"' for k, v in bucket_labels.items())
            lines.append(f"{self._name}_bucket{{{bl_str}}} {cumulative}")

        # +Inf bucket (все наблюдения)
        inf_labels = self._labels.copy()
        inf_labels["le"] = "+Inf"
        inf_str = ",".join(f'{k}="{v}"' for k, v in inf_labels.items())
        lines.append(f"{self._name}_bucket{{{inf_str}}} {self._count}")

        return "\n".join(lines)


class MetricsCollector:
    """
    Коллектор метрик — центральный компонент для сбора метрик.

    Обеспечивает:
    - Регистрацию и хранение метрик
    - Автоматическое создание метрик по требованию
    - Сохранение в Redis для персистентности
    - Подписку на Event Bus

    Пример:
        >>> collector = MetricsCollector()
        >>> counter = collector.get_counter("requests_total", "Всего запросов")
        >>> await counter.inc()
        >>> gauge = collector.get_gauge("memory_bytes", "Использование памяти")
        >>> await gauge.set(1024 * 1024)
    """

    def __init__(self, redis_client: Any | None = None) -> None:
        """
        Инициализировать коллектор метрик.

        Аргументы:
            redis_client: Redis клиент для персистентности (опционально)
        """
        self._redis = redis_client
        self._counters: dict[str, Counter] = {}
        self._gauges: dict[str, Gauge] = {}
        self._histograms: dict[str, Histogram] = {}

        # Callbacks для event-driven метрик
        self._event_callbacks: list[Callable[..., Awaitable[None]]] = []

        settings = get_settings()
        self._enabled = settings.metrics_enabled

        logger.info(
            "Инициализирован коллектор метрик",
            enabled=self._enabled,
            redis=redis_client is not None,
        )

    @property
    def enabled(self) -> bool:
        """Проверить включены ли метрики."""
        return self._enabled

    def set_redis(self, redis_client: Any) -> None:
        """Установить Redis клиент для персистентности."""
        self._redis = redis_client
        logger.info("Redis клиент установлен для MetricsCollector")

    def _make_key(self, name: str, labels: dict[str, str]) -> str:
        """Создать уникальный ключ для метрики."""
        if not labels:
            return name
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"

    def get_counter(
        self,
        name: str,
        description: str = "",
        labels: dict[str, str] | None = None,
    ) -> Counter:
        """
        Получить или создать счетчик.

        Аргументы:
            name: Имя метрики
            description: Описание метрики
            labels: Labels для метрики

        Returns:
            Экземпляр Counter
        """
        key = self._make_key(name, labels or {})

        if key not in self._counters:
            self._counters[key] = Counter(name, description, labels)
            logger.debug(
                "Создан счетчик",
                name=name,
                labels=labels,
                key=key,
            )

        return self._counters[key]

    def get_gauge(
        self,
        name: str,
        description: str = "",
        labels: dict[str, str] | None = None,
    ) -> Gauge:
        """
        Получить или создать gauge.

        Аргументы:
            name: Имя метрики
            description: Описание метрики
            labels: Labels для метрики

        Returns:
            Экземпляр Gauge
        """
        key = self._make_key(name, labels or {})

        if key not in self._gauges:
            self._gauges[key] = Gauge(name, description, labels)
            logger.debug(
                "Создан gauge",
                name=name,
                labels=labels,
                key=key,
            )

        return self._gauges[key]

    def get_histogram(
        self,
        name: str,
        description: str = "",
        labels: dict[str, str] | None = None,
        buckets: list[float] | None = None,
    ) -> Histogram:
        """
        Получить или создать гистограмму.

        Аргументы:
            name: Имя метрики
            description: Описание метрики
            labels: Labels для метрики
            buckets: Границы bucket-ов

        Returns:
            Экземпляр Histogram
        """
        key = self._make_key(name, labels or {})

        if key not in self._histograms:
            self._histograms[key] = Histogram(name, description, labels, buckets)
            logger.debug(
                "Создана гистограмма",
                name=name,
                labels=labels,
                key=key,
            )

        return self._histograms[key]

    def get_all_metrics(self) -> dict[str, Any]:
        """
        Получить все метрики.

        Returns:
            Словарь со всеми метриками
        """
        return {
            "counters": {k: v.value for k, v in self._counters.items()},
            "gauges": {k: v.value for k, v in self._gauges.items()},
            "histograms": {
                k: {"count": v.count, "sum": v.sum}
                for k, v in self._histograms.items()
            },
        }

    async def record_event(
        self,
        event_type: str,
        source: str,
        priority: str = "normal",
    ) -> None:
        """
        Записать метрику для события.

        Аргументы:
            event_type: Тип события
            source: Источник события
            priority: Приоритет события
        """
        if not self._enabled:
            return

        # Счетчик опубликованных событий
        counter = self.get_counter(
            "event_published_total",
            "Всего опубликовано событий",
            {"source": source, "event_type": event_type, "priority": priority},
        )
        await counter.inc()

        # Общий счетчик
        total_counter = self.get_counter(
            "event_published_total",
            "Всего опубликовано событий",
            {"source": "all", "event_type": "all", "priority": "all"},
        )
        await total_counter.inc()

    async def record_event_delivery(
        self,
        event_type: str,
        subscriber: str,
    ) -> None:
        """
        Записать доставку события подписчику.

        Аргументы:
            event_type: Тип события
            subscriber: Имя подписчика
        """
        if not self._enabled:
            return

        counter = self.get_counter(
            "event_delivered_total",
            "Всего доставлено событий",
            {"event_type": event_type, "subscriber": subscriber},
        )
        await counter.inc()

    async def record_event_dropped(
        self,
        reason: str,
        priority: str = "normal",
    ) -> None:
        """
        Записать отброшенное событие.

        Аргументы:
            reason: Причина отбрасывания
            priority: Приоритет события
        """
        if not self._enabled:
            return

        counter = self.get_counter(
            "event_dropped_total",
            "Всего отброшено событий",
            {"reason": reason, "priority": priority},
        )
        await counter.inc()

    async def record_query_duration(
        self,
        query_type: str,
        database: str,
        duration_seconds: float,
    ) -> None:
        """
        Записать длительность запроса к БД.

        Аргументы:
            query_type: Тип запроса (SELECT, INSERT, UPDATE, DELETE)
            database: Имя базы данных
            duration_seconds: Длительность в секундах
        """
        if not self._enabled:
            return

        histogram = self.get_histogram(
            "db_query_duration_seconds",
            "Длительность запросов к БД",
            {"query_type": query_type, "database": database},
        )
        await histogram.observe(duration_seconds)

    async def record_connection_count(
        self,
        database: str,
        active: int,
        idle: int | None = None,
    ) -> None:
        """
        Записать количество соединений с БД.

        Аргументы:
            database: Имя базы данных
            active: Количество активных соединений
            idle: Количество простаивающих соединений (опционально)
        """
        if not self._enabled:
            return

        gauge = self.get_gauge(
            "db_connections_active",
            "Активные соединения с БД",
            {"database": database},
        )
        await gauge.set(active)

        if idle is not None:
            idle_gauge = self.get_gauge(
                "db_connections_idle",
                "Простаивающие соединения с БД",
                {"database": database},
            )
            await idle_gauge.set(idle)

    async def record_subscribers_count(
        self,
        event_type: str,
        count: int,
    ) -> None:
        """
        Записать количество подписчиков на событие.

        Аргументы:
            event_type: Тип события
            count: Количество подписчиков
        """
        if not self._enabled:
            return

        gauge = self.get_gauge(
            "subscribers_active",
            "Активные подписчики",
            {"event_type": event_type},
        )
        await gauge.set(count)

    async def record_publish_latency(
        self,
        priority: str,
        duration_seconds: float,
    ) -> None:
        """
        Записать задержку публикации события.

        Аргументы:
            priority: Приоритет события
            duration_seconds: Длительность в секундах
        """
        if not self._enabled:
            return

        histogram = self.get_histogram(
            "event_publish_latency_seconds",
            "Задержка публикации событий",
            {"priority": priority},
        )
        await histogram.observe(duration_seconds)

    def get_prometheus_metrics(self) -> str:
        """
        Получить все метрики в формате Prometheus.

        Returns:
            Строка в формате Prometheus exposition
        """
        lines = ["# HELP cryptotechnolog_metrics CRYPTOTEHNOLOG metrics", "# TYPE cryptotechnolog_metrics untyped"]

        # Counters
        for counter in self._counters.values():
            lines.append(f"# HELP {counter.name} Counter metric")
            lines.append(f"# TYPE {counter.name} counter")
            lines.append(counter.get_for_prometheus())

        # Gauges
        for gauge in self._gauges.values():
            lines.append(f"# HELP {gauge.name} Gauge metric")
            lines.append(f"# TYPE {gauge.name} gauge")
            lines.append(gauge.get_for_prometheus())

        # Histograms
        for histogram in self._histograms.values():
            lines.append(f"# HELP {histogram.name} Histogram metric")
            lines.append(f"# TYPE {histogram.name} histogram")
            lines.append(histogram.get_for_prometheus())

        return "\n".join(lines)

    async def save_to_redis(self) -> None:
        """Сохранить метрики в Redis для персистентности."""
        if self._redis is None:
            logger.warning("Redis не настроен, сохранение метрик пропущено")
            return

        try:
            metrics_data = self.get_all_metrics()
            import json

            await self._redis.set(
                "cryptotechnolog:metrics",
                json.dumps(metrics_data),
                ttl=300,  # 5 минут TTL
            )
            logger.debug("Метрики сохранены в Redis")
        except Exception as e:
            logger.error("Ошибка сохранения метрик в Redis", error=str(e))

    async def load_from_redis(self) -> None:
        """Загрузить метрики из Redis."""
        if self._redis is None:
            logger.warning("Redis не настроен, загрузка метрик пропущена")
            return

        try:
            import json

            data = await self._redis.get("cryptotechnolog:metrics")
            if data:
                metrics_data = json.loads(data)
                logger.info("Метрики загружены из Redis", data=metrics_data)
        except Exception as e:
            logger.error("Ошибка загрузки метрик из Redis", error=str(e))

    async def reset_all(self) -> None:
        """Сбросить все метрики."""
        for counter in self._counters.values():
            counter.reset()

        for gauge in self._gauges.values():
            await gauge.set(0)

        self._histograms.clear()
        logger.info("Все метрики сброшены")

    def get_metric_names(self) -> list[str]:
        """Получить список всех имен метрик."""
        names = []
        names.extend(counter.name for counter in self._counters.values())
        names.extend(gauge.name for gauge in self._gauges.values())
        names.extend(histogram.name for histogram in self._histograms.values())
        return list(set(names))


# Глобальный экземпляр
_metrics_collector: MetricsCollector | None = None


def get_metrics_collector() -> MetricsCollector:
    """
    Получить глобальный экземпляр MetricsCollector.

    Returns:
        Экземпляр коллектора метрик
    """
    global _metrics_collector  # noqa: PLW0603
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def init_metrics(redis_client: Any | None = None) -> MetricsCollector:
    """
    Инициализировать глобальный коллектор метрик.

    Аргументы:
        redis_client: Redis клиент для персистентности

    Returns:
        Инициализированный экземпляр
    """
    global _metrics_collector  # noqa: PLW0603
    _metrics_collector = MetricsCollector(redis_client)
    return _metrics_collector

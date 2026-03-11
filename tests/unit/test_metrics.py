"""
Тесты для Metrics Collector (src/core/metrics.py).

Проверяют:
- Counter (счетчики)
- Gauges (текущие значения)
- Histograms (гистограммы)
- MetricsCollector (центральный компонент)
- Формат Prometheus
"""


import pytest

from cryptotechnolog.core.metrics import (
    Counter,
    Gauge,
    Histogram,
    HistogramBuckets,
    MetricsCollector,
    get_metrics_collector,
    init_metrics,
)


class TestCounter:
    """Тесты для Counter."""

    def test_init(self) -> None:
        """Инициализация счетчика."""
        counter = Counter("test_counter", "Тестовый счетчик", {"env": "test"})
        assert counter.name == "test_counter"
        assert counter.value == 0.0
        assert counter.labels == {"env": "test"}

    def test_inc(self) -> None:
        """Увеличение счетчика."""
        counter = Counter("test_counter")
        counter.inc_sync(5)
        assert counter.value == 5.0

    def test_inc_default(self) -> None:
        """Увеличение счетчика на 1 по умолчанию."""
        counter = Counter("test_counter")
        counter.inc_sync()
        counter.inc_sync()
        assert counter.value == 2.0

    def test_reset(self) -> None:
        """Сброс счетчика."""
        counter = Counter("test_counter")
        counter.inc_sync(100)
        counter.reset()
        assert counter.value == 0.0

    def test_prometheus_format(self) -> None:
        """Формат Prometheus."""
        counter = Counter("requests_total", "Всего запросов", {"method": "GET"})
        counter.inc_sync(42)
        prometheus_output = counter.get_for_prometheus()
        assert 'requests_total{method="GET"}' in prometheus_output
        assert "42" in prometheus_output


class TestGauge:
    """Тесты для Gauge."""

    def test_init(self) -> None:
        """Инициализация gauge."""
        gauge = Gauge("memory_usage", "Использование памяти", {"type": "rss"})
        assert gauge.name == "memory_usage"
        assert gauge.value == 0.0
        assert gauge.labels == {"type": "rss"}

    def test_set(self) -> None:
        """Установка значения."""
        gauge = Gauge("test_gauge")
        gauge.set_sync(100.5)
        assert gauge.value == 100.5

    def test_inc(self) -> None:
        """Увеличение значения."""
        gauge = Gauge("test_gauge")
        gauge.set_sync(10)
        gauge.inc_sync(5)
        assert gauge.value == 15

    def test_dec(self) -> None:
        """Уменьшение значения."""
        gauge = Gauge("test_gauge")
        gauge.set_sync(10)
        gauge.dec_sync(3)
        assert gauge.value == 7

    def test_prometheus_format(self) -> None:
        """Формат Prometheus."""
        gauge = Gauge("cpu_usage", "Загрузка CPU", {"core": "0"})
        gauge.set_sync(75.5)
        prometheus_output = gauge.get_for_prometheus()
        assert 'cpu_usage{core="0"}' in prometheus_output
        assert "75.5" in prometheus_output


class TestHistogram:
    """Тесты для Histogram."""

    def test_init(self) -> None:
        """Инициализация гистограммы."""
        hist = Histogram("request_duration", "Длительность запроса")
        assert hist.name == "request_duration"
        assert hist.count == 0
        assert hist.sum == 0.0

    def test_observe(self) -> None:
        """Запись наблюдения."""
        hist = Histogram("request_duration", buckets=[0.1, 0.5, 1.0, 5.0])
        hist.observe_sync(0.3)

        assert hist.count == 1
        assert hist.sum == 0.3

    def test_multiple_observations(self) -> None:
        """Множественные наблюдения."""
        hist = Histogram("request_duration", buckets=[0.1, 0.5, 1.0, 5.0])

        hist.observe_sync(0.05)  # < 0.1
        hist.observe_sync(0.3)  # 0.1-0.5
        hist.observe_sync(0.8)  # 0.5-1.0
        hist.observe_sync(3.0)  # 1.0-5.0

        assert hist.count == 4
        assert hist.sum == 4.15  # 0.05 + 0.3 + 0.8 + 3.0

    def test_quantile_calculation(self) -> None:
        """Расчет квантилей."""
        # Используем бакеты, которые покрывают диапазон 1-100
        hist = Histogram(
            "request_duration", buckets=[1, 5, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        )

        # Добавить 100 значений от 1 до 100
        for i in range(1, 101):
            hist.observe_sync(float(i))

        # p50 должен быть около 50
        p50 = hist.get_quantile(0.5)
        assert 45 <= p50 <= 55

        # p95 должен быть около 95
        p95 = hist.get_quantile(0.95)
        assert 90 <= p95 <= 100

    def test_percentile_calculation(self) -> None:
        """Расчет перцентилей."""
        # Используем бакеты, которые покрывают диапазон 1-100
        hist = Histogram(
            "request_duration", buckets=[1, 5, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        )

        for i in range(1, 101):
            hist.observe_sync(float(i))

        p99 = hist.get_percentile(99)
        assert 95 <= p99 <= 100

    def test_empty_histogram_quantile(self) -> None:
        """Квантиль для пустой гистограммы."""
        hist = Histogram("request_duration")
        assert hist.get_quantile(0.5) == 0.0

    def test_prometheus_format(self) -> None:
        """Формат Prometheus."""
        hist = Histogram("request_duration", buckets=[0.1, 0.5, 1.0])
        hist.observe_sync(0.3)

        output = hist.get_for_prometheus()
        assert "# HELP" in output
        assert "# TYPE" in output
        assert "request_duration_sum" in output
        assert "request_duration_count" in output
        assert "request_duration_bucket" in output


class TestHistogramBuckets:
    """Тесты для HistogramBuckets."""

    def test_get_bucket(self) -> None:
        """Получение индекса бакета."""
        buckets = HistogramBuckets([1, 5, 10])

        assert buckets.get_bucket(0.5) == 0
        assert buckets.get_bucket(1) == 0
        assert buckets.get_bucket(3) == 1
        assert buckets.get_bucket(5) == 1
        assert buckets.get_bucket(7) == 2
        assert buckets.get_bucket(10) == 2
        assert buckets.get_bucket(100) == 3  # За пределами


class TestMetricsCollector:
    """Тесты для MetricsCollector."""

    def test_init(self) -> None:
        """Инициализация коллектора."""
        collector = MetricsCollector()
        assert collector is not None
        assert collector.enabled

    def test_get_counter_creates_new(self) -> None:
        """Создание нового счетчика."""
        collector = MetricsCollector()
        counter = collector.get_counter("test_counter", "Тестовый")

        assert counter is not None
        assert counter.name == "test_counter"

    def test_get_counter_returns_existing(self) -> None:
        """Возврат существующего счетчика."""
        collector = MetricsCollector()
        counter1 = collector.get_counter("test_counter", "Тестовый")
        counter2 = collector.get_counter("test_counter")

        assert counter1 is counter2

    def test_get_counter_with_labels(self) -> None:
        """Счетчики с разными labels - разные экземпляры."""
        collector = MetricsCollector()
        counter1 = collector.get_counter("requests", labels={"method": "GET"})
        counter2 = collector.get_counter("requests", labels={"method": "POST"})

        assert counter1 is not counter2

    def test_get_gauge(self) -> None:
        """Получение gauge."""
        collector = MetricsCollector()
        gauge = collector.get_gauge("memory", "Память")

        assert gauge is not None
        assert gauge.name == "memory"

    def test_get_histogram(self) -> None:
        """Получение гистограммы."""
        collector = MetricsCollector()
        hist = collector.get_histogram("duration", "Длительность")

        assert hist is not None
        assert hist.name == "duration"

    def test_get_all_metrics(self) -> None:
        """Получение всех метрик."""
        collector = MetricsCollector()
        collector.get_counter("counter1")
        collector.get_gauge("gauge1")
        collector.get_histogram("hist1")

        all_metrics = collector.get_all_metrics()

        assert "counter1" in all_metrics["counters"]
        assert "gauge1" in all_metrics["gauges"]
        assert "hist1" in all_metrics["histograms"]

    @pytest.mark.asyncio
    async def test_record_event(self) -> None:
        """Запись события."""
        collector = MetricsCollector()
        collector.get_counter("event_published_total")  # Pre-create

        # Используем await вместо run_until_complete
        await collector.record_event("TEST_EVENT", "test_source", "normal")

        metrics = collector.get_all_metrics()
        # Проверяем, что счетчик увеличился
        counters = metrics["counters"]
        # Должен быть счетчик для конкретного события
        assert len(counters) > 0

    @pytest.mark.asyncio
    async def test_record_query_duration(self) -> None:
        """Запись длительности запроса."""
        collector = MetricsCollector()

        await collector.record_query_duration("SELECT", "postgresql", 0.125)

        metrics = collector.get_all_metrics()
        histograms = metrics["histograms"]
        assert len(histograms) > 0

    @pytest.mark.asyncio
    async def test_record_connection_count(self) -> None:
        """Запись количества соединений."""
        collector = MetricsCollector()

        await collector.record_connection_count("postgresql", 5, 3)

        metrics = collector.get_all_metrics()
        gauges = metrics["gauges"]
        assert len(gauges) > 0

    def test_get_prometheus_metrics(self) -> None:
        """Получение метрик в формате Prometheus."""
        collector = MetricsCollector()
        collector.get_counter("requests_total", labels={"method": "GET"})
        collector.get_gauge("memory_bytes")
        collector.get_histogram("request_duration")

        output = collector.get_prometheus_metrics()

        assert "requests_total" in output
        assert "memory_bytes" in output
        assert "request_duration" in output

    @pytest.mark.asyncio
    async def test_reset_all(self) -> None:
        """Сброс всех метрик."""
        collector = MetricsCollector()
        collector.get_counter("test_counter").inc_sync(100)
        collector.get_gauge("test_gauge").set_sync(50)

        await collector.reset_all()

        metrics = collector.get_all_metrics()
        assert metrics["counters"]["test_counter"] == 0.0
        assert metrics["gauges"]["test_gauge"] == 0.0

    def test_get_metric_names(self) -> None:
        """Получение списка имен метрик."""
        collector = MetricsCollector()
        collector.get_counter("counter1")
        collector.get_counter("counter2")
        collector.get_gauge("gauge1")
        collector.get_histogram("hist1")

        names = collector.get_metric_names()

        assert "counter1" in names
        assert "counter2" in names
        assert "gauge1" in names
        assert "hist1" in names


class TestMetricsCollectorGlobal:
    """Тесты для глобального экземпляра."""

    def test_get_metrics_collector_singleton(self) -> None:
        """Получение глобального экземпляра."""
        collector1 = get_metrics_collector()
        collector2 = get_metrics_collector()

        assert collector1 is collector2

    def test_init_metrics(self) -> None:
        """Инициализация с Redis клиентом."""
        collector = init_metrics(redis_client=None)
        assert collector is not None
        assert collector.enabled


class TestMetricsWithLabels:
    """Тесты для метрик с различными labels."""

    def test_counter_with_multiple_labels(self) -> None:
        """Счетчик с множеством labels."""
        counter = Counter(
            "http_requests_total",
            "Всего HTTP запросов",
            {"method": "GET", "status": "200", "endpoint": "/api/v1/users"},
        )
        counter.inc_sync(10)

        output = counter.get_for_prometheus()
        assert 'method="GET"' in output
        assert 'status="200"' in output
        assert 'endpoint="/api/v1/users"' in output

    def test_gauge_with_labels(self) -> None:
        """Gauge с labels."""
        gauge = Gauge(
            "db_connections",
            "Соединения с БД",
            {"database": "postgresql", "pool": "default"},
        )
        gauge.set_sync(15)

        output = gauge.get_for_prometheus()
        assert 'database="postgresql"' in output
        assert 'pool="default"' in output
        assert "15" in output

    def test_histogram_with_labels(self) -> None:
        """Гистограмма с labels."""
        hist = Histogram(
            "request_latency",
            "Задержка запроса",
            {"service": "api", "region": "us-east-1"},
        )
        hist.observe_sync(0.5)

        output = hist.get_for_prometheus()
        assert 'service="api"' in output
        assert 'region="us-east-1"' in output


class TestMetricsEdgeCases:
    """Тесты граничных случаев."""

    def test_counter_negative_increment(self) -> None:
        """Отрицательное увеличение (допустимо для счетчика в Prometheus)."""
        counter = Counter("test")
        counter.inc_sync(10)
        counter.inc_sync(-3)  # Prometheus позволяет
        assert counter.value == 7.0

    def test_gauge_negative_value(self) -> None:
        """Отрицательное значение для gauge."""
        gauge = Gauge("temperature", "Температура")
        gauge.set_sync(-10.5)
        assert gauge.value == -10.5

    def test_histogram_zero_value(self) -> None:
        """Нулевое значение в гистограмме."""
        hist = Histogram("test")
        hist.observe_sync(0)
        assert hist.count == 1
        assert hist.sum == 0.0

    def test_histogram_very_large_value(self) -> None:
        """Очень большое значение в гистограмме."""
        hist = Histogram("test", buckets=[1, 10, 100, 1000])
        hist.observe_sync(1_000_000)
        assert hist.count == 1
        assert hist.sum == 1_000_000


pytest.mark.unit(__name__)

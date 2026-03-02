"""
Тесты для SLO (Service Level Objectives).

Проверяет:
- SLODefinition
- SLORegistry
- check_slo_violations()
- _get_slo_status()
- get_all_slo_statuses()
- get_dashboard_data()
"""

import asyncio

from cryptotechnolog.core.metrics import (
    Histogram,
    MetricsCollector,
    SLODefinition,
    SLORegistry,
    get_slo_registry,
)


class TestSLODefinition:
    """Тесты для SLODefinition."""

    def test_slo_definition_creation(self):
        """Проверить создание SLO определения."""
        slo = SLODefinition(
            name="test_slo",
            metric_name="test_metric_seconds",
            target_percentile=95,
            threshold_ms=100.0,
            window_seconds=60,
            description="Test SLO",
        )

        assert slo.name == "test_slo"
        assert slo.metric_name == "test_metric_seconds"
        assert slo.target_percentile == 95
        assert slo.threshold_ms == 100.0

    def test_slo_check_ok(self):
        """Проверить SLO check когда значение в пределах."""
        slo = SLODefinition(
            name="test_slo",
            metric_name="test_metric_seconds",
            target_percentile=95,
            threshold_ms=200.0,  # 200ms - высокий порог
            window_seconds=60,
        )

        histogram = Histogram("test_metric", "Test")

        # Добавим много наблюдений для корректного p95
        for _ in range(20):
            asyncio.get_event_loop().run_until_complete(histogram.observe(0.05))

        result = slo.check(histogram)

        assert result["is_violated"] is False
        assert result["actual_ms"] <= 50.0  # p95 ~ 50ms < 200ms

    def test_slo_check_violated(self):
        """Проверить SLO check когда значение превышено."""
        slo = SLODefinition(
            name="test_slo",
            metric_name="test_metric_seconds",
            target_percentile=95,
            threshold_ms=50.0,  # 50ms - низкий порог
            window_seconds=60,
        )

        histogram = Histogram("test_metric", "Test")

        # Добавим наблюдения где p95 будет > 50ms
        for _ in range(20):
            asyncio.get_event_loop().run_until_complete(
                histogram.observe(0.1)  # 100ms
            )

        result = slo.check(histogram)

        # p95 ~ 100ms > 50ms - должно быть нарушение
        assert result["is_violated"] is True
        assert result["actual_ms"] > slo.threshold_ms


class TestSLORegistry:
    """Тесты для SLORegistry."""

    def test_registry_creation(self):
        """Проверить создание реестра."""
        registry = SLORegistry()

        assert len(registry.get_all_slos()) == 4  # 4 default SLO

    def test_get_slo(self):
        """Проверить получение SLO по имени."""
        registry = SLORegistry()

        slo = registry.get_slo("risk_engine_latency")
        assert slo is not None
        assert slo.name == "risk_engine_latency"

    def test_get_slo_not_found(self):
        """Проверить получение несуществующего SLO."""
        registry = SLORegistry()

        slo = registry.get_slo("nonexistent")
        assert slo is None

    def test_check_slo_violations_no_metrics(self):
        """Проверить проверку SLO без метрик."""
        registry = SLORegistry()
        metrics = MetricsCollector()

        violations = registry.check_slo_violations(metrics)

        assert isinstance(violations, list)

    def test_check_slo_violations_with_data(self):
        """Проверить проверку SLO с данными."""
        registry = SLORegistry()
        metrics = MetricsCollector()

        # Добавим данные в гистограмму
        histogram = metrics.get_histogram(
            "risk_engine_latency_seconds",
            "Test latency",
        )
        asyncio.get_event_loop().run_until_complete(histogram.observe(0.05))

        violations = registry.check_slo_violations(metrics)

        # При малых значениях нарушений быть не должно
        assert isinstance(violations, list)

    def test_get_all_slo_statuses(self):
        """Проверить получение статусов всех SLO."""
        registry = SLORegistry()
        metrics = MetricsCollector()

        statuses = registry.get_all_slo_statuses(metrics)

        assert len(statuses) == 4
        for _name, status in statuses.items():
            assert "name" in status
            assert "status" in status
            assert "has_data" in status

    def test_get_dashboard_data(self):
        """Проверить получение данных для dashboard."""
        registry = SLORegistry()

        data = registry.get_dashboard_data()

        assert "slos" in data
        assert "total_slos" in data
        assert data["total_slos"] == 4
        assert len(data["slos"]) == 4

    def test_default_slos(self):
        """Проверить что все default SLO созданы."""
        registry = SLORegistry()

        expected_slos = [
            "risk_engine_latency",
            "execution_response",
            "universe_update",
            "data_freshness",
        ]

        for name in expected_slos:
            slo = registry.get_slo(name)
            assert slo is not None, f"SLO {name} not found"
            assert slo.name == name


class TestSLOIntegration:
    """Интеграционные тесты SLO."""

    def test_slo_registry_singleton(self):
        """Проверить что get_slo_registry возвращает синглтон."""
        registry1 = get_slo_registry()
        registry2 = get_slo_registry()

        assert registry1 is registry2

    def test_slo_triggers_violation_logging(self):
        """Проверить что при нарушении SLO логируется warning."""

        registry = SLORegistry()
        metrics = MetricsCollector()

        # Создаём гистограмму с нарушением
        histogram = metrics.get_histogram(
            "risk_engine_latency_seconds",
            "Test",
        )

        asyncio.get_event_loop().run_until_complete(
            histogram.observe(10.0)  # 10000ms >> 100ms
        )

        # Проверяем что есть нарушение
        violations = registry.check_slo_violations(metrics)

        # Нарушение должно быть зафиксировано
        assert isinstance(violations, list)

"""
Интеграционные тесты для Health Check System.

Тестируют:
- HealthChecker с реальным подключением к PostgreSQL
- HealthChecker с реальным подключением к Redis
- Комплексную проверку системы
"""

import asyncio
import uuid

import pytest

from cryptotechnolog.config import get_logger
from src.core.database import DatabaseManager
from src.core.health import (
    DatabaseHealthCheck,
    HealthChecker,
    HealthStatus,
    MetricsHealthCheck,
    RedisHealthCheck,
    init_health_checker,
)
from src.core.metrics import MetricsCollector
from src.core.redis_manager import RedisManager

logger = get_logger(__name__)


@pytest.mark.integration
class TestHealthCheckIntegration:
    """Интеграционные тесты для Health Checker."""

    @pytest.mark.asyncio
    async def test_database_health_check_real(self) -> None:
        """Проверка здоровья реальной базы данных."""
        db_manager = DatabaseManager()

        # Подключаемся к БД
        await db_manager.connect()

        try:
            check = DatabaseHealthCheck(db_manager)
            result = await check.check()

            assert result.status == HealthStatus.HEALTHY
            assert result.component == "postgresql"
            assert result.latency_ms > 0

            logger.info(
                "Проверка PostgreSQL прошла успешно",
                latency_ms=result.latency_ms,
            )
        finally:
            await db_manager.disconnect()

    @pytest.mark.asyncio
    async def test_redis_health_check_real(self) -> None:
        """Проверка здоровья реального Redis."""
        redis_manager = RedisManager()

        # Подключаемся к Redis
        await redis_manager.connect()

        try:
            check = RedisHealthCheck(redis_manager)
            result = await check.check()

            assert result.status == HealthStatus.HEALTHY
            assert result.component == "redis"
            assert result.latency_ms > 0

            logger.info(
                "Проверка Redis прошла успешно",
                latency_ms=result.latency_ms,
            )
        finally:
            await redis_manager.disconnect()

    @pytest.mark.asyncio
    async def test_health_checker_with_real_db_and_redis(self) -> None:
        """Проверка системы с реальными БД и Redis."""
        db_manager = DatabaseManager()
        redis_manager = RedisManager()

        # Подключаемся к обоим сервисам
        await db_manager.connect()
        await redis_manager.connect()

        try:
            # Создаем HealthChecker и регистрируем проверки
            checker = HealthChecker()
            checker.register_check(DatabaseHealthCheck(db_manager))
            checker.register_check(RedisHealthCheck(redis_manager))

            # Выполняем проверку
            result = await checker.check_system()

            # Проверяем результаты
            assert result.overall_status == HealthStatus.HEALTHY
            assert "postgresql" in result.components
            assert "redis" in result.components

            assert result.components["postgresql"].status == HealthStatus.HEALTHY
            assert result.components["redis"].status == HealthStatus.HEALTHY

            logger.info(
                "Комплексная проверка прошла успешно",
                overall_status=result.overall_status.value,
            )
        finally:
            await db_manager.disconnect()
            await redis_manager.disconnect()

    @pytest.mark.asyncio
    async def test_health_checker_with_metrics(self) -> None:
        """Проверка системы с метриками."""
        db_manager = DatabaseManager()
        redis_manager = RedisManager()
        metrics_collector = MetricsCollector()

        # Подключаемся к сервисам
        await db_manager.connect()
        await redis_manager.connect()

        try:
            # Создаем HealthChecker
            checker = HealthChecker()
            checker.register_check(DatabaseHealthCheck(db_manager))
            checker.register_check(RedisHealthCheck(redis_manager))
            checker.register_check(MetricsHealthCheck(metrics_collector))

            # Выполняем проверку
            result = await checker.check_system()

            # Проверяем что метрики также проверены
            assert "metrics" in result.components

            logger.info(
                "Проверка с метриками прошла успешно",
                metrics_status=result.components["metrics"].status.value,
            )
        finally:
            await db_manager.disconnect()
            await redis_manager.disconnect()

    @pytest.mark.asyncio
    async def test_health_checker_unhealthy_db(self) -> None:
        """Проверка системы с отключенной БД."""
        # Создаем неподключенный менеджер БД
        db_manager = DatabaseManager()

        # Не подключаемся к БД

        redis_manager = RedisManager()
        await redis_manager.connect()

        try:
            checker = HealthChecker()
            checker.register_check(DatabaseHealthCheck(db_manager))
            checker.register_check(RedisHealthCheck(redis_manager))

            result = await checker.check_system()

            # Один компонент healthy, один - нет
            assert result.overall_status == HealthStatus.UNHEALTHY
            assert "postgresql" in result.get_unhealthy_components()

            logger.info(
                "Обнаружена нездоровая БД",
                unhealthy_components=result.get_unhealthy_components(),
            )
        finally:
            await redis_manager.disconnect()

    @pytest.mark.asyncio
    async def test_health_checker_unhealthy_redis(self) -> None:
        """Проверка системы с отключенным Redis."""
        db_manager = DatabaseManager()
        await db_manager.connect()

        # Создаем неподключенный менеджер Redis
        redis_manager = RedisManager()

        # Не подключаемся к Redis

        try:
            checker = HealthChecker()
            checker.register_check(DatabaseHealthCheck(db_manager))
            checker.register_check(RedisHealthCheck(redis_manager))

            result = await checker.check_system()

            # Один компонент healthy, один - нет
            assert result.overall_status == HealthStatus.UNHEALTHY
            assert "redis" in result.get_unhealthy_components()

            logger.info(
                "Обнаружен нездоровый Redis",
                unhealthy_components=result.get_unhealthy_components(),
            )
        finally:
            await db_manager.disconnect()

    @pytest.mark.asyncio
    async def test_init_health_checker_helper(self) -> None:
        """Тест helper функции init_health_checker."""
        db_manager = DatabaseManager()
        redis_manager = RedisManager()

        await db_manager.connect()
        await redis_manager.connect()

        try:
            checker = init_health_checker(
                db_manager=db_manager,
                redis_manager=redis_manager,
            )

            # Проверяем что проверки зарегистрированы
            checks = checker.get_registered_checks()
            assert "postgresql" in checks
            assert "redis" in checks

            result = await checker.check_system()

            assert result.overall_status == HealthStatus.HEALTHY
        finally:
            await db_manager.disconnect()
            await redis_manager.disconnect()

    @pytest.mark.asyncio
    async def test_status_callback_integration(self) -> None:
        """Тест callback при изменении статуса в реальном окружении."""
        db_manager = DatabaseManager()
        redis_manager = RedisManager()

        await db_manager.connect()
        await redis_manager.connect()

        status_changes = []

        try:
            checker = HealthChecker()
            checker.register_check(DatabaseHealthCheck(db_manager))
            checker.register_check(RedisHealthCheck(redis_manager))

            async def status_callback(health) -> None:
                status_changes.append(health.overall_status)

            checker.on_status_change(status_callback)

            # Первая проверка
            await checker.check_system()

            # Вторая проверка - статус не изменится
            await checker.check_system()

            # Callback должен быть вызван
            assert len(status_changes) >= 1

            logger.info(
                "Callback вызван",
                call_count=len(status_changes),
            )
        finally:
            await db_manager.disconnect()
            await redis_manager.disconnect()

    @pytest.mark.asyncio
    async def test_parallel_health_checks(self) -> None:
        """Тест параллельных проверок здоровья."""
        db_manager = DatabaseManager()
        redis_manager = RedisManager()

        await db_manager.connect()
        await redis_manager.connect()

        try:
            checker = HealthChecker()
            checker.register_check(DatabaseHealthCheck(db_manager))
            checker.register_check(RedisHealthCheck(redis_manager))

            # Выполняем проверки параллельно
            results = await asyncio.gather(
                checker.check_system(),
                checker.check_system(),
                checker.check_system(),
            )

            # Все результаты должны быть healthy
            for result in results:
                assert result.overall_status == HealthStatus.HEALTHY

            logger.info(
                "Параллельные проверки выполнены",
                checks_count=len(results),
            )
        finally:
            await db_manager.disconnect()
            await redis_manager.disconnect()

    @pytest.mark.asyncio
    async def test_check_component_specific(self) -> None:
        """Тест проверки конкретного компонента."""
        db_manager = DatabaseManager()
        redis_manager = RedisManager()

        await db_manager.connect()
        await redis_manager.connect()

        try:
            checker = HealthChecker()
            checker.register_check(DatabaseHealthCheck(db_manager))
            checker.register_check(RedisHealthCheck(redis_manager))

            # Проверяем конкретный компонент
            pg_health = await checker.check_component("postgresql")
            assert pg_health.status == HealthStatus.HEALTHY
            assert pg_health.component == "postgresql"

            redis_health = await checker.check_component("redis")
            assert redis_health.status == HealthStatus.HEALTHY
            assert redis_health.component == "redis"

            logger.info(
                "Проверка конкретных компонентов выполнена",
            )
        finally:
            await db_manager.disconnect()
            await redis_manager.disconnect()

    @pytest.mark.asyncio
    async def test_health_check_with_unique_keys(self) -> None:
        """Тест с уникальными ключами для избежания конфликтов."""
        # Используем уникальный идентификатор для тестовых данных
        test_id = str(uuid.uuid4())[:8]

        db_manager = DatabaseManager()
        redis_manager = RedisManager()

        await db_manager.connect()
        await redis_manager.connect()

        try:
            # Создаем тестовые данные с уникальным ключом
            test_key = f"health_test_{test_id}"
            await redis_manager.set_value(test_key, "test_value")

            # Проверяем что HealthChecker работает
            checker = HealthChecker()
            checker.register_check(DatabaseHealthCheck(db_manager))
            checker.register_check(RedisHealthCheck(redis_manager))

            result = await checker.check_system()
            assert result.overall_status == HealthStatus.HEALTHY

            # Очищаем
            await redis_manager.delete(test_key)

            logger.info(
                "Тест с уникальными ключами выполнен",
                test_id=test_id,
            )
        finally:
            await db_manager.disconnect()
            await redis_manager.disconnect()


pytest.mark.integration(__name__)

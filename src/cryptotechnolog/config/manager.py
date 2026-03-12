"""
Менеджер конфигурации с поддержкой hot reload и GPG верификации.

Реализует централизованное управление конфигурацией системы.

Особенности:
    - DI через конструктор
    - Plugable providers (файл, Infisical, env)
    - Hot reload без рестарта с atomic swap
    - История версий в PostgreSQL
    - GPG верификация подписей
    - Infisical integration для секретов
    - Метрики и alerts

Все docstrings на русском языке.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
import hashlib
import logging
from pathlib import Path
import time
from typing import TYPE_CHECKING, Any, TypedDict


class HistogramStats(TypedDict):
    """Тип для статистики гистограммы."""

    count: float
    sum: float
    min: float
    max: float
    avg: float
    p50: float
    p95: float
    p99: float


# ruff: noqa: E402
# Импорты Protocol классов - необходимы в runtime для isinstance проверок
from cryptotechnolog.config.protocols import (
    IConfigLoader,
    IConfigParser,
    IConfigRepository,
    IConfigSigner,
    IConfigValidator,
)

if TYPE_CHECKING:
    from cryptotechnolog.config.models import SystemConfig
    from cryptotechnolog.core.enhanced_event_bus import EnhancedEventBus

logger = logging.getLogger(__name__)


class ConfigManagerError(Exception):
    """
    Ошибка работы ConfigManager.

    Атрибуты:
        operation: Операция которая вызвала ошибку
        reason: Причина ошибки
    """

    def __init__(self, operation: str, reason: str) -> None:
        """
        Инициализировать ошибку.

        Аргументы:
            operation: Название операции
            reason: Причина ошибки
        """
        self.operation = operation
        self.reason = reason
        message = f"Ошибка ConfigManager ({operation}): {reason}"
        super().__init__(message)


class ConfigManager:
    """
    Менеджер конфигурации с поддержкой hot reload и GPG верификации.

    Обеспечивает:
        - Загрузку конфигурации из различных источников
        - Валидацию через Pydantic
        - Проверку GPG подписей
        - Сохранение истории версий
        - Hot reload без рестарта системы с atomic swap
        - Infisical integration для секретов
        - Метрики для мониторинга
        - Alerts для критических ситуаций

    Пример использования:
        manager = ConfigManager(
            loader=file_provider,
            parser=yaml_parser,
            validator=pydantic_validator,
            signer=gpg_signer,
            repository=config_repo,
            event_bus=event_bus,
        )
        config = await manager.load()
    """

    # Максимальный возраст кэша секретов (24 часа) - для Infisical
    MAX_CACHE_AGE_HOURS = 24

    def __init__(
        self,
        loader: IConfigLoader,
        parser: IConfigParser,
        validator: IConfigValidator,
        signer: IConfigSigner,
        repository: IConfigRepository,
        event_bus: EnhancedEventBus,
    ) -> None:
        """
        Инициализировать менеджер конфигурации.

        Аргументы:
            loader: Загрузчик конфигурации
            parser: Парсер конфигурации
            validator: Валидатор конфигурации
            signer: Верификатор подписей
            repository: Репозиторий версий
            event_bus: Шина событий
        """
        self._loader = loader
        self._parser = parser
        self._validator = validator
        self._signer = signer
        self._repository = repository
        self._event_bus = event_bus

        # Atomic swap lock
        self._config_lock = asyncio.Lock()

        # Текущая конфигурация
        self._current_config: SystemConfig | None = None
        self._current_source: str | None = None
        self._internal_version: int = 0

        # Метрики
        self._metrics = ConfigMetrics()

        # Время последнего обновления конфигурации
        self._last_update_timestamp: datetime | None = None

    @property
    def current_config(self) -> SystemConfig | None:
        """
        Получить текущую конфигурацию (thread-safe).

        Returns:
            Текущая конфигурация или None
        """
        return self._current_config

    @property
    def internal_version(self) -> int:
        """
        Получить внутреннюю версию конфигурации.

        Returns:
            Внутренняя версия (инкрементируется при каждом reload)
        """
        return self._internal_version

    async def load(
        self,
        source: str,
        save_to_history: bool = True,
        loaded_by: str = "system",
    ) -> SystemConfig:
        """
        Загрузить и валидировать конфигурацию.

        Аргументы:
            source: Источник конфигурации (путь к файлу, URL и т.д.)
            save_to_history: Сохранять в историю версий
            loaded_by: Кто загрузил (оператор, система)

        Returns:
            Валидированная конфигурация

        Raises:
            ConfigManagerError: При ошибке загрузки
        """
        try:
            logger.info("Загрузка конфигурации из источника: %s", source)
            self._metrics.increment("config_loads_total", labels={"status": "started"})

            # Шаг 1: Загрузка байтов
            data = await self._load_and_measure(source)

            # Шаг 2: Верификация подписи
            await self._verify_signature(source)

            # Шаг 3: Парсинг
            parsed = await self._parse_bytes(data)

            # Шаг 4: Валидация
            config = await self._validate_parsed(parsed)

            # Шаг 5: Сохранение в историю
            if save_to_history:
                await self._save_to_history(config, data, loaded_by)

            # Шаг 6: Atomic swap
            old_config = await self._atomic_swap(config, source)

            # Шаг 7: Публикация события
            await self._publish_config_updated(
                old_config=old_config,
                new_config=config,
                source=source,
                trigger=loaded_by,
            )

            # Обновляем timestamp и gauge
            self._last_update_timestamp = datetime.now()
            self._update_gauges(config)

            self._metrics.increment("config_loads_total", labels={"status": "success"})
            return config

        except Exception as e:
            logger.error("Ошибка загрузки конфигурации, источник: %s, ошибка: %s", source, str(e))
            self._metrics.increment("config_loads_total", labels={"status": "error"})
            raise ConfigManagerError("load", str(e)) from e

    async def _load_and_measure(self, source: str) -> bytes:
        """Загрузить конфигурацию и замерить время."""
        start_time = time.monotonic()
        data = await self._loader.load(source)
        duration = (time.monotonic() - start_time) * 1000  # ms

        self._metrics.observe("config_load_duration_seconds", duration / 1000, {"phase": "load"})
        self._metrics.timing("config_load_phase", duration, {"phase": "load"})

        logger.debug("Конфигурация загружена, размер: %d байт", len(data))
        self._metrics.observe("config_load_bytes", len(data))
        return data

    async def _verify_signature(self, source: str) -> None:
        """Верифицировать подпись конфигурации."""
        start_time = time.monotonic()
        source_path = Path(source)
        signature_valid = await self._signer.verify(source_path)
        duration = (time.monotonic() - start_time) * 1000  # ms

        self._metrics.timing("config_load_phase", duration, {"phase": "signature_verify"})

        if signature_valid:
            logger.info("Подпись верифицирована для источника: %s", source)
            self._metrics.increment("config_loads_total", labels={"status": "signature_valid"})
        else:
            logger.warning("Подпись НЕ верифицирована для источника: %s", source)
            self._metrics.increment("config_loads_total", labels={"status": "signature_failed"})
            await self._publish_alert(
                alert_type="signature_failed",
                message=f"Подпись недействительна: {source}",
                severity="critical",
            )

    async def _parse_bytes(self, data: bytes) -> dict[str, Any]:
        """Распарсить байты конфигурации."""
        parsed = self._parser.parse(data)
        logger.debug("Конфигурация распарсена")
        return parsed

    async def _validate_parsed(self, parsed: dict[str, Any]) -> SystemConfig:
        """Валидировать распарсенную конфигурацию."""
        try:
            config = self._validator.validate(parsed)
            logger.info(
                "Конфигурация валидирована: version=%s, environment=%s",
                config.version,
                config.environment,
            )
            self._metrics.increment("config_loads_total", labels={"status": "validation_success"})
            return config
        except Exception as e:
            logger.error("Ошибка валидации конфигурации: %s", str(e))
            self._metrics.increment("config_loads_total", labels={"status": "validation_failed"})
            await self._publish_alert(
                alert_type="validation_failed",
                message=f"Ошибка валидации: {e}",
                severity="warning",
            )
            raise

    async def _save_to_history(
        self,
        config: SystemConfig,
        data: bytes,
        loaded_by: str,
    ) -> None:
        """Сохранить конфигурацию в историю версий."""
        content_hash = hashlib.sha256(data).hexdigest()
        yaml_content = data.decode("utf-8")
        await self._repository.save_version(
            version=config.version,
            content_hash=content_hash,
            config_yaml=yaml_content,
            loaded_by=loaded_by,
        )
        logger.info("Сохранено в историю, версия: %s", config.version)

    async def _atomic_swap(
        self,
        config: SystemConfig,
        source: str,
    ) -> SystemConfig | None:
        """Атомарно заменить текущую конфигурацию."""
        old_config = self._current_config
        old_version = old_config.version if old_config else None

        async with self._config_lock:
            self._current_config = config
            self._current_source = source
            self._internal_version += 1
            new_internal_version = self._internal_version

            logger.info(
                "Конфигурация обновлена атомарно: old_version=%s, new_version=%s, internal_version=%d",
                old_version,
                config.version,
                new_internal_version,
            )

        return old_config

    async def reload(
        self,
        loaded_by: str = "auto_reload",
    ) -> SystemConfig:
        """
        Перезагрузить конфигурацию (hot reload) с atomic swap.

        Аргументы:
            loaded_by: Кто инициировал перезагрузку

        Returns:
            Новая конфигурация

        Raises:
            ConfigManagerError: При ошибке перезагрузки
        """
        if self._current_source is None:
            raise ConfigManagerError("reload", "Нет загруженной конфигурации")

        logger.info("Hot reload конфигурации из источника: %s", self._current_source)
        self._metrics.increment("config_reloads_total", labels={"trigger": loaded_by})

        # Загружаем заново
        return await self.load(
            source=self._current_source,
            save_to_history=True,
            loaded_by=loaded_by,
        )

    async def load_from_history(
        self,
        version: str,
    ) -> SystemConfig:
        """
        Загрузить конфигурацию из истории версий.

        Аргументы:
            version: Версия конфигурации

        Returns:
            Конфигурация из истории

        Raises:
            ConfigManagerError: При ошибке загрузки
        """
        logger.info("Загрузка из истории, версия: %s", version)

        # Получаем версию из репозитория
        stored = await self._repository.get_by_version(version)
        if stored is None:
            raise ConfigManagerError("load_from_history", f"Версия {version} не найдена")

        # Парсим и валидируем
        data = stored["config_yaml"].encode("utf-8")
        parsed = self._parser.parse(data)
        config = self._validator.validate(parsed)

        logger.info("Загружено из истории, версия: %s", version)
        return config

    async def get_history(self, limit: int = 10) -> list[dict[str, Any]]:
        """
        Получить историю версий конфигурации.

        Аргументы:
            limit: Количество версий

        Returns:
            Список версий
        """
        return await self._repository.get_history(limit=limit)

    async def get_latest_from_history(self) -> dict[str, Any] | None:
        """
        Получить последнюю активную версию из истории.

        Returns:
            Последняя версия или None
        """
        return await self._repository.get_latest()

    # =========================================================================
    # Rollback Methods
    # =========================================================================

    async def rollback_to_version(
        self,
        version: str,
        loaded_by: str = "rollback",
    ) -> SystemConfig:
        """
        Выполнить rollback к указанной версии конфигурации.

        Загружает конфигурацию из истории, применяет её как текущую
        и публикует событие ROLLEDBACK.

        Аргументы:
            version: Версия для rollback
            loaded_by: Кто инициировал rollback

        Returns:
            Применённая конфигурация

        Raises:
            ConfigManagerError: При ошибке rollback
        """
        logger.info("Начало rollback к версии: %s", version)
        self._metrics.increment("config_rollbacks_total", labels={"target_version": version})

        try:
            # Получаем версию из репозитория
            stored = await self._repository.get_by_version(version)
            if stored is None:
                raise ConfigManagerError(
                    "rollback_to_version",
                    f"Версия {version} не найдена в истории",
                )

            # Парсим и валидируем
            data = stored["config_yaml"].encode("utf-8")
            parsed = self._parser.parse(data)
            config = self._validator.validate(parsed)

            # Сохраняем текущую конфигурацию перед rollback
            old_config = self._current_config
            old_version = old_config.version if old_config else None

            # Применяем rollback через atomic swap
            await self._atomic_swap(config, f"rollback:{version}")

            # Сохраняем в историю как новую версию с пометкой rollback
            await self._save_to_history(
                config,
                data,
                f"rollback_to_{version}_by_{loaded_by}",
            )

            # Публикуем событие ROLLEDBACK
            await self._publish_rollback_event(
                old_version=old_version,
                target_version=version,
                loaded_by=loaded_by,
            )

            self._metrics.increment("config_rollbacks_total", labels={"status": "success"})
            logger.info("Rollback выполнен: %s -> %s", old_version, version)

            return config

        except Exception as e:
            logger.error("Ошибка rollback к версии %s: %s", version, str(e))
            self._metrics.increment(
                "config_rollbacks_total",
                labels={"status": "error"},
            )
            raise ConfigManagerError("rollback_to_version", str(e)) from e

    async def rollback_to_previous(self, loaded_by: str = "rollback") -> SystemConfig:
        """
        Выполнить rollback к предыдущей версии конфигурации.

        Аргументы:
            loaded_by: Кто инициировал rollback

        Returns:
            Применённая конфигурация

        Raises:
            ConfigManagerError: Если нет предыдущей версии
        """
        logger.info("Запрос rollback к предыдущей версии")

        history = await self.get_history(limit=2)

        # history[0] - текущая версия, history[1] - предыдущая
        MIN_VERSIONS_FOR_ROLLBACK = 2
        if len(history) < MIN_VERSIONS_FOR_ROLLBACK:
            raise ConfigManagerError(
                "rollback_to_previous",
                "Нет предыдущей версии для rollback",
            )

        previous_version = history[1]["version"]
        return await self.rollback_to_version(previous_version, loaded_by)

    async def get_rollback_candidates(self) -> list[dict[str, Any]]:
        """
        Получить список доступных версий для rollback.

        Returns:
            Список версий с метаданными
        """
        history = await self.get_history(limit=20)

        # Фильтруем - исключаем текущую версию
        current_version = self._current_config.version if self._current_config else None
        candidates = [
            {
                "version": h["version"],
                "loaded_at": h.get("loaded_at"),
                "loaded_by": h.get("loaded_by"),
                "is_current": h["version"] == current_version,
            }
            for h in history
            if h["version"] != current_version
        ]

        return candidates

    async def compare_versions(
        self,
        version1: str,
        version2: str,
    ) -> dict[str, Any]:
        """
        Сравнить две версии конфигурации.

        Аргументы:
            version1: Первая версия
            version2: Вторая версия

        Returns:
            Diff между версиями
        """
        stored1 = await self._repository.get_by_version(version1)
        stored2 = await self._repository.get_by_version(version2)

        if stored1 is None:
            raise ConfigManagerError("compare_versions", f"Версия {version1} не найдена")
        if stored2 is None:
            raise ConfigManagerError("compare_versions", f"Версия {version2} не найдена")

        # Парсим обе версии
        data1 = stored1["config_yaml"].encode("utf-8")
        data2 = stored2["config_yaml"].encode("utf-8")

        parsed1 = self._parser.parse(data1)
        parsed2 = self._parser.parse(data2)

        config1 = self._validator.validate(parsed1)
        config2 = self._validator.validate(parsed2)

        # Вычисляем diff
        diff = self._compute_diff(config1, config2)

        return {
            "version1": version1,
            "version2": version2,
            "diff": diff,
            "reload_required": self._get_reload_required_sections(diff),
            "metadata1": {
                "loaded_at": stored1.get("loaded_at"),
                "loaded_by": stored1.get("loaded_by"),
            },
            "metadata2": {
                "loaded_at": stored2.get("loaded_at"),
                "loaded_by": stored2.get("loaded_by"),
            },
        }

    # =========================================================================
    # Events
    # =========================================================================

    async def _publish_config_updated(
        self,
        old_config: SystemConfig | None,
        new_config: SystemConfig,
        source: str,
        trigger: str,
    ) -> None:
        """
        Опубликовать событие CONFIG_UPDATED с полной структурой.

        Аргументы:
            old_config: Предыдущая конфигурация
            new_config: Новая конфигурация
            source: Источник конфигурации
            trigger: Триггер загрузки
        """
        try:
            # Локальный импорт для избежания циклических импортов
            # ruff: noqa: PLC0415
            from cryptotechnolog.core.event import Event, Priority

            # Вычисляем diff
            diff = self._compute_diff(old_config, new_config) if old_config else {}

            # Определяем что требует reload
            reload_required = self._get_reload_required_sections(diff)

            payload: dict[str, Any] = {
                "old_version": old_config.version if old_config else None,
                "new_version": new_config.version,
                "source": source,
                "trigger": trigger,
                "internal_version": self._internal_version,
                "changed_sections": list(diff.keys()),
                "diff": diff,
                "reload_required": reload_required,
            }

            event = Event.new(
                event_type="CONFIG_UPDATED",
                source="CONFIG_MANAGER",
                payload=payload,
            )
            event.priority = Priority.HIGH

            if self._event_bus is not None:
                await self._event_bus.publish(event)
            else:
                logger.debug("Event bus не настроен, событие CONFIG_UPDATED не опубликовано")

            logger.info(
                "Опубликовано событие CONFIG_UPDATED: old_version=%s, new_version=%s, "
                "changed_sections=%s, reload_required=%s",
                old_config.version if old_config else None,
                new_config.version,
                list(diff.keys()),
                list(reload_required.keys()),
            )
        except Exception as e:
            logger.error("Ошибка публикации CONFIG_UPDATED: %s", str(e))

    def _compute_diff(
        self,
        old_config: SystemConfig,
        new_config: SystemConfig,
    ) -> dict[str, Any]:
        """
        Вычислить diff между конфигурациями.

        Аргументы:
            old_config: Предыдущая конфигурация
            new_config: Новая конфигурация

        Returns:
            Словарь с изменениями
        """
        diff: dict[str, Any] = {}

        # Risk config
        if old_config.risk != new_config.risk:
            diff["risk"] = {
                "old": old_config.risk.model_dump(),
                "new": new_config.risk.model_dump(),
            }

        # Exchanges
        if old_config.exchanges != new_config.exchanges:
            diff["exchanges"] = {
                "old": [e.model_dump() for e in old_config.exchanges],
                "new": [e.model_dump() for e in new_config.exchanges],
            }

        # Strategies
        if old_config.strategies != new_config.strategies:
            diff["strategies"] = {
                "old": [s.model_dump() for s in old_config.strategies],
                "new": [s.model_dump() for s in new_config.strategies],
            }

        # System
        if old_config.system != new_config.system:
            diff["system"] = {
                "old": old_config.system,
                "new": new_config.system,
            }

        return diff

    def _get_reload_required_sections(self, diff: dict[str, Any]) -> dict[str, bool]:
        """
        Определить какие компоненты требуют перезагрузки.

        Аргументы:
            diff: Diff конфигураций

        Returns:
            Словарь {компонент: требует_reload}
        """
        reload_required: dict[str, bool] = {
            "risk_engine": "risk" in diff,
            "execution_layer": "exchanges" in diff,
            "strategy_manager": "strategies" in diff,
            "state_machine": "system" in diff,
        }
        return reload_required

    async def _publish_alert(
        self,
        alert_type: str,
        message: str,
        severity: str,
    ) -> None:
        """
        Опубликовать alert.

        Аргументы:
            alert_type: Тип алерта
            message: Сообщение
            severity: Критичность (critical, warning, info)
        """
        try:
            # Локальный импорт для избежания циклических импортов
            # ruff: noqa: PLC0415
            from cryptotechnolog.core.event import Event, Priority

            priority = Priority.CRITICAL if severity == "critical" else Priority.HIGH

            payload: dict[str, Any] = {
                "alert_type": alert_type,
                "message": message,
                "severity": severity,
                "source": "CONFIG_MANAGER",
                "timestamp": datetime.now().isoformat(),
            }

            event = Event.new(
                event_type="CONFIG_ALERT",
                source="CONFIG_MANAGER",
                payload=payload,
            )
            event.priority = priority

            if self._event_bus is not None:
                await self._event_bus.publish(event)
            else:
                logger.debug("Event bus не настроен, alert не опубликован")

            logger.warning(
                "Alert опубликован: type=%s, severity=%s, message=%s",
                alert_type,
                severity,
                message,
            )
        except Exception as e:
            logger.error("Ошибка публикации alert: %s", str(e))

    async def _publish_rollback_event(
        self,
        old_version: str | None,
        target_version: str,
        loaded_by: str,
    ) -> None:
        """
        Опубликовать событие ROLLEDBACK.

        Аргументы:
            old_version: Предыдущая версия
            target_version: Версия на которую выполнен rollback
            loaded_by: Кто инициировал rollback
        """
        try:
            from cryptotechnolog.core.event import Event, Priority

            payload: dict[str, Any] = {
                "old_version": old_version,
                "target_version": target_version,
                "loaded_by": loaded_by,
                "rollback_time": datetime.now().isoformat(),
            }

            event = Event.new(
                event_type="CONFIG_ROLLEDBACK",
                source="CONFIG_MANAGER",
                payload=payload,
            )
            event.priority = Priority.HIGH

            if self._event_bus is not None:
                await self._event_bus.publish(event)

            logger.info(
                "Опубликовано событие ROLLEDBACK: %s -> %s",
                old_version,
                target_version,
            )
        except Exception as e:
            logger.error("Ошибка публикации ROLLEDBACK: %s", str(e))

    # =========================================================================
    # Metrics
    # =========================================================================

    def _update_gauges(self, config: SystemConfig) -> None:
        """
        Обновить gauge метрики.

        Аргументы:
            config: Текущая конфигурация
        """
        # config_version{environment}
        self._metrics.gauge(
            "config_version",
            float(self._internal_version),
            {"environment": config.environment},
        )

        # config_file_age_seconds
        if self._last_update_timestamp:
            age_seconds = (datetime.now() - self._last_update_timestamp).total_seconds()
            self._metrics.gauge("config_file_age_seconds", age_seconds)

    def get_metrics(self) -> dict[str, Any]:
        """
        Получить метрики ConfigManager.

        Returns:
            Словарь с метриками
        """
        return self._metrics.to_dict()

    # =========================================================================
    # Nested Config Access (dot notation)
    # =========================================================================

    def get_config_value(self, key_path: str, default: Any = None) -> Any:
        """
        Получить значение из конфигурации по ключу (dot notation).

        Аргументы:
            key_path: Путь к значению через точку (например, "risk.base_r_percent")
            default: Значение по умолчанию если ключ не найден

        Returns:
            Значение по ключу или default

        Примеры:
            >>> manager.get_config_value("risk.base_r_percent")
            Decimal('0.02')
            >>> manager.get_config_value("exchanges[0].name")
            'bybit'
        """
        if self._current_config is None:
            return default

        try:
            # Разбиваем путь на части
            parts = key_path.split(".")
            current: Any = self._current_config

            for part in parts:
                # Проверяем индекс массива
                if "[" in part and "]" in part:
                    # Извлекаем имя поля и индекс
                    field_name, index_str = part.split("[")
                    index = int(index_str.rstrip("]"))

                    if field_name:
                        current = getattr(current, field_name)
                    current = current[index]
                elif part:
                    current = getattr(current, part)

            return current
        except (AttributeError, IndexError, KeyError, TypeError):
            return default

    def get_risk_config(self) -> dict[str, Any] | None:
        """
        Получить конфигурацию рисков.

        Returns:
            Словарь с параметрами рисков или None
        """
        if self._current_config is None:
            return None
        return self._current_config.risk.model_dump()

    def get_exchanges(self) -> list[dict[str, Any]]:
        """
        Получить список бирж.

        Returns:
            Список бирж
        """
        if self._current_config is None:
            return []
        return [e.model_dump() for e in self._current_config.exchanges]

    def get_strategies(self) -> list[dict[str, Any]]:
        """
        Получить список стратегий.

        Returns:
            Список стратегий
        """
        if self._current_config is None:
            return []
        return [s.model_dump() for s in self._current_config.strategies]


class ConfigMetrics:
    """
    Расширенные метрики ConfigManager.

    Содержит счётчики, гистограммы и тайминги для мониторинга.
    Поддерживает Prometheus-совместимый формат.
    """

    def __init__(self) -> None:
        """Инициализировать метрики."""
        self._counters: dict[str, int] = {}
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = {}
        self._timings: dict[str, list[float]] = {}  # Время выполнения операций

    def _make_key(self, name: str, labels: dict[str, str] | None = None) -> str:
        """
        Создать ключ метрики из имени и лейблов.

        Аргументы:
            name: Имя метрики
            labels: Лейблы

        Returns:
            Ключ метрики
        """
        if not labels:
            return name
        label_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"

    def increment(self, name: str, labels: dict[str, str] | None = None, value: int = 1) -> None:
        """
        Инкрементировать счётчик.

        Аргументы:
            name: Имя метрики
            labels: Лейблы
            value: Значение для инкремента
        """
        key = self._make_key(name, labels)
        self._counters[key] = self._counters.get(key, 0) + value

    def gauge(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        """
        Установить значение gauge.

        Аргументы:
            name: Имя метрики
            value: Значение
            labels: Лейблы
        """
        key = self._make_key(name, labels)
        self._gauges[key] = value

    def observe(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        """
        Наблюдать значение для гистограммы.

        Аргументы:
            name: Имя метрики
            value: Значение
            labels: Лейблы
        """
        key = self._make_key(name, labels)
        if key not in self._histograms:
            self._histograms[key] = []
        self._histograms[key].append(value)

    def timing(self, name: str, duration_ms: float, labels: dict[str, str] | None = None) -> None:
        """
        Записать время выполнения операции.

        Аргументы:
            name: Имя операции
            duration_ms: Время в миллисекундах
            labels: Лейблы
        """
        key = self._make_key(name, labels)
        if key not in self._timings:
            self._timings[key] = []
        self._timings[key].append(duration_ms)

    def to_dict(self) -> dict[str, Any]:
        """
        Конвертировать метрики в словарь.

        Returns:
            Словарь с метриками
        """
        return {
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "histograms": self._compute_histogram_stats(self._histograms),
            "timings": self._compute_histogram_stats(self._timings),
        }

    def _compute_histogram_stats(
        self,
        data: dict[str, list[float]],
    ) -> dict[str, HistogramStats]:
        """
        Вычислить статистику для гистограмм.

        Аргументы:
            data: Словарь значений

        Returns:
            Словарь со статистикой
        """
        result: dict[str, HistogramStats] = {}
        for key, values in data.items():
            if not values:
                result[key] = HistogramStats(
                    count=float(0),
                    sum=float(0),
                    min=float(0),
                    max=float(0),
                    avg=float(0),
                    p50=float(0),
                    p95=float(0),
                    p99=float(0),
                )
                continue

            sorted_values = sorted(values)
            values_count = float(len(values))

            def percentile(percentile_data: list[float], p: float) -> float:
                """Вычислить перцентиль."""
                idx = int(len(percentile_data) * p / 100)
                if idx >= len(percentile_data):
                    idx = len(percentile_data) - 1
                return percentile_data[idx]

            result[key] = HistogramStats(
                count=values_count,
                sum=sum(values),
                min=min(values),
                max=max(values),
                avg=sum(values) / values_count,
                p50=percentile(sorted_values, 50),
                p95=percentile(sorted_values, 95),
                p99=percentile(sorted_values, 99),
            )

        return result

    def to_prometheus_format(self) -> str:
        """
        Экспортировать метрики в Prometheus текстовом формате.

        Returns:
            Метрики в формате Prometheus
        """
        lines: list[str] = []

        # Counters
        for name, value in self._counters.items():
            lines.append(f"# TYPE {name} counter")
            lines.append(f"{name} {value}")

        # Gauges
        for gauge_name, gauge_value in self._gauges.items():
            lines.append(f"# TYPE {gauge_name} gauge")
            lines.append(f"{gauge_name} {gauge_value}")

        # Histograms
        histogram_data = self._compute_histogram_stats(self._histograms)
        for hist_name, hist_stats in histogram_data.items():
            lines.append(f"# TYPE {hist_name} histogram")
            lines.append(f"{hist_name}_count {hist_stats['count']}")
            lines.append(f"{hist_name}_sum {hist_stats['sum']}")
            lines.append(f"{hist_name}_min {hist_stats['min']}")
            lines.append(f"{hist_name}_max {hist_stats['max']}")
            lines.append(f"{hist_name}_avg {hist_stats['avg']}")
            lines.append(f"{hist_name}_p50 {hist_stats['p50']}")
            lines.append(f"{hist_name}_p95 {hist_stats['p95']}")
            lines.append(f"{hist_name}_p99 {hist_stats['p99']}")

        return "\n".join(lines)

"""
Менеджер конфигурации с поддержкой hot reload и GPG верификации.

Реализует централизованное управление конфигурацией системы.

Особенности:
    - DI через конструктор
    - Plugable providers (файл, Vault, env)
    - Hot reload без рестарта
    - История версий в PostgreSQL
    - GPG верификация подписей

Все docstrings на русском языке.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

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
        - Hot reload без рестарта системы

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
        self._current_config: SystemConfig | None = None
        self._current_source: str | None = None

    @property
    def current_config(self) -> SystemConfig | None:
        """
        Получить текущую конфигурацию.

        Returns:
            Текущая конфигурация или None
        """
        return self._current_config

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

            # Шаг 1: Загрузка байтов
            data = await self._loader.load(source)
            logger.debug("Конфигурация загружена, размер: %d байт", len(data))

            # Шаг 2: Верификация подписи (если требуется)
            source_path = Path(source)
            if await self._signer.verify(source_path):
                logger.info("Подпись верифицирована для источника: %s", source)
            else:
                logger.warning("Подпись НЕ верифицирована для источника: %s", source)

            # Шаг 3: Парсинг
            parsed = self._parser.parse(data)
            logger.debug("Конфигурация распарсена")

            # Шаг 4: Валидация
            config = self._validator.validate(parsed)
            logger.info(
                "Конфигурация валидирована: version=%s, environment=%s",
                config.version,
                config.environment,
            )

            # Шаг 5: Сохранение в историю
            if save_to_history:
                content_hash = hashlib.sha256(data).hexdigest()
                yaml_content = data.decode("utf-8")
                await self._repository.save_version(
                    version=config.version,
                    content_hash=content_hash,
                    config_yaml=yaml_content,
                    loaded_by=loaded_by,
                )
                logger.info("Сохранено в историю, версия: %s", config.version)

            # Шаг 6: Публикация события
            old_version: str | None = None
            if self._current_config:
                old_version = self._current_config.version
            await self._publish_config_updated(
                old_version=old_version,
                new_version=config.version,
                source=source,
            )

            # Сохраняем текущую конфигурацию
            self._current_config = config
            self._current_source = source

            return config

        except Exception as e:
            logger.error("Ошибка загрузки конфигурации, источник: %s, ошибка: %s", source, str(e))
            raise ConfigManagerError("load", str(e)) from e

    async def reload(
        self,
        loaded_by: str = "auto_reload",
    ) -> SystemConfig:
        """
        Перезагрузить конфигурацию (hot reload).

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

    async def _publish_config_updated(
        self,
        old_version: str | None,
        new_version: str,
        source: str,
    ) -> None:
        """
        Опубликовать событие CONFIG_UPDATED.

        Аргументы:
            old_version: Предыдущая версия
            new_version: Новая версия
            source: Источник конфигурации
        """
        try:
            # Локальный импорт для избежания циклических импортов
            # ruff: noqa: PLC0415
            from cryptotechnolog.core.event import Event, Priority

            payload: dict[str, Any] = {
                "old_version": old_version,
                "new_version": new_version,
                "source": source,
                "changed_sections": self._get_changed_sections(),
            }

            event = Event.new(
                event_type="CONFIG_UPDATED",
                source="CONFIG_MANAGER",
                payload=payload,
            )
            event.priority = Priority.HIGH

            await self._event_bus.publish(event)

            logger.info(
                "Опубликовано событие CONFIG_UPDATED: old_version=%s, new_version=%s",
                old_version,
                new_version,
            )
        except Exception as e:
            logger.error("Ошибка публикации CONFIG_UPDATED: %s", str(e))

    def _get_changed_sections(self) -> list[str]:
        """
        Определить изменённые секции конфигурации.

        Returns:
            Список изменённых секций
        """
        if self._current_config is None:
            return []

        # Для простоты возвращаем все основные секции
        sections = ["risk", "exchanges", "strategies", "system"]
        return sections

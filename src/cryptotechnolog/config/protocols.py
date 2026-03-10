"""
Протоколы (интерфейсы) для Config Manager.

SOLID принципы:
- Interface Segregation: узкие протоколы для разных задач
- Liskov Substitution: все реализации взаимозаменяемы
- Dependency Inversion: зависимости от абстракций

Все docstrings на русском языке.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from cryptotechnolog.config.models import SystemConfig


class IConfigLoader(Protocol):
    """
    Протокол для загрузки конфигурации из источника.

    Методы:
        load: Загрузить конфигурацию
        reload: Перезагрузить конфигурацию
    """

    async def load(self, source: str) -> bytes:
        """
        Загрузить конфигурацию из источника.

        Аргументы:
            source: Источник конфигурации (путь к файлу, URL и т.д.)

        Returns:
            Байты конфигурации

        Raises:
            IOError: При ошибке чтения
        """
        ...

    async def reload(self) -> bytes:
        """
        Перезагрузить конфигурацию из того же источника.

        Returns:
            Байты конфигурации

        Raises:
            IOError: При ошибке чтения
        """
        ...


class IConfigParser(Protocol):
    """
    Протокол для парсинга конфигурации.

    Методы:
        parse: Распарсить байты в словарь
    """

    def parse(self, data: bytes) -> dict[str, Any]:
        """
        Распарсить данные в словарь.

        Аргументы:
            data: Байты конфигурации

        Returns:
            Словарь с конфигурацией

        Raises:
            ParseError: При ошибке парсинга
        """
        ...


class IConfigValidator(Protocol):
    """
    Протокол для валидации конфигурации.

    Методы:
        validate: Валидировать и вернуть типизированную модель
    """

    def validate(self, data: dict[str, Any]) -> SystemConfig:
        """
        Валидировать данные и вернуть типизированную модель.

        Аргументы:
            data: Словарь с конфигурацией

        Returns:
            Валидированная модель SystemConfig

        Raises:
            ValidationError: При ошибке валидации
        """
        ...


class IConfigSigner(Protocol):
    """
    Протокол для проверки GPG подписей.

    Методы:
        verify: Проверить подпись файла
        is_signature_required: Нужна ли подпись для файла
    """

    async def verify(self, path: Path) -> bool:
        """
        Проверить подпись файла.

        Аргументы:
            path: Путь к файлу конфигурации

        Returns:
            True если подпись действительна

        Raises:
            SignatureError: При ошибке проверки подписи
        """
        ...

    def is_signature_required(self, path: Path) -> bool:
        """
        Проверить, нужна ли подпись для файла.

        Аргументы:
            path: Путь к файлу конфигурации

        Returns:
            True если подпись требуется
        """
        ...


class IConfigRepository(Protocol):
    """
    Протокол для хранения версий конфигурации.

    Методы:
        save_version: Сохранить версию конфигурации
        get_history: Получить историю версий
        get_latest: Получить последнюю версию
        get_by_version: Получить конкретную версию
    """

    async def save_version(
        self,
        version: str,
        content_hash: str,
        config_yaml: str,
        loaded_by: str,
    ) -> None:
        """
        Сохранить версию конфигурации.

        Аргументы:
            version: Версия конфигурации
            content_hash: SHA256 хеш содержимого
            config_yaml: YAML содержимое
            loaded_by: Кто загрузил (оператор или 'auto_reload')

        Raises:
            RepositoryError: При ошибке сохранения
        """
        ...

    async def get_history(self, limit: int = 10) -> list[dict[str, Any]]:
        """
        Получить историю версий конфигурации.

        Аргументы:
            limit: Количество версий

        Returns:
            Список версий
        """
        ...

    async def get_latest(self) -> dict[str, Any] | None:
        """
        Получить последнюю активную версию.

        Returns:
            Последняя версия или None
        """
        ...

    async def get_by_version(self, version: str) -> dict[str, Any] | None:
        """
        Получить конкретную версию конфигурации.

        Аргументы:
            version: Версия конфигурации

        Returns:
            Данные версии или None
        """
        ...


class IConfigWatcher(Protocol):
    """
    Протокол для мониторинга изменений файлов.

    Методы:
        watch: Начать мониторинг
        stop: Остановить мониторинг
        on_change: Установить callback на изменение
    """

    async def watch(self, paths: list[Path]) -> None:
        """
        Начать мониторинг изменений файлов.

        Аргументы:
            paths: Список путей для мониторинга

        Raises:
            WatcherError: При ошибке запуска мониторинга
        """
        ...

    async def stop(self) -> None:
        """
        Остановить мониторинг.
        """
        ...

    def on_change(self, callback: Callable[[Path], None]) -> None:
        """
        Установить callback на изменение файла.

        Аргументы:
            callback: Функция которая вызывается при изменении
        """
        ...

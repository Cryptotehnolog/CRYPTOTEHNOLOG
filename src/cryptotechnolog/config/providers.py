"""
Провайдеры для загрузки конфигурации.

Реализации:
- FileConfigProvider: загрузка из файлов (YAML, JSON)
- InfisicalConfigProvider: загрузка из Infisical
- EnvConfigProvider: загрузка из переменных окружения

Все docstrings на русском языке.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, cast

import httpx

from cryptotechnolog.config.protocols import IConfigLoader

# Константы для HTTP статус-кодов
HTTP_NOT_FOUND = 404
HTTP_OK = 200
KV_V2_MIN_PARTS = 2


class FileConfigProvider(IConfigLoader):
    """
    Провайдер для загрузки конфигурации из файлов.

    Поддерживаемые форматы:
    - YAML (.yaml, .yml)
    - JSON (.json)

    Пример использования:
        provider = FileConfigProvider(path="config/prod/settings.yaml")
        data = await provider.load("config/dev/settings.yaml")
    """

    def __init__(self, base_path: Path | None = None) -> None:
        """
        Инициализировать провайдер.

        Аргументы:
            base_path: Базовая директория для относительных путей
        """
        self._base_path = base_path or Path.cwd()
        self._last_source: str | None = None

    async def load(self, source: str) -> bytes:
        """
        Загрузить конфигурацию из файла.

        Аргументы:
            source: Путь к файлу конфигурации

        Returns:
            Байты содержимого файла

        Raises:
            IOError: Если файл не найден или не читается
        """
        self._last_source = source
        path = self._resolve_path(source)

        if not path.exists():
            raise FileNotFoundError(f"Конфигурационный файл не найден: {path}")

        if not path.is_file():
            raise ValueError(f"Указанный путь не является файлом: {path}")

        return path.read_bytes()

    async def reload(self) -> bytes:
        """
        Перезагрузить конфигурацию.

        Returns:
            Байты содержимого файла

        Raises:
            ValueError: Если source не был установлен
        """
        if not hasattr(self, "_last_source"):
            raise ValueError("Источник не был установлен при первичной загрузке")

        source = self._last_source
        if source is None:
            raise ValueError("Источник не был установлен при первичной загрузке")

        return await self.load(source)

    def _resolve_path(self, source: str) -> Path:
        """Разрешить относительный или абсолютный путь."""
        path = Path(source)

        if path.is_absolute():
            return path

        return self._base_path / path


class EnvConfigProvider(IConfigLoader):
    """
    Провайдер для загрузки конфигурации из переменных окружения.

    Загружает все переменные начинающиеся с префикса
    и преобразует их в JSON-совместимый формат.

    Пример использования:
        provider = EnvConfigProvider(prefix="CT_")
        data = await provider.load("")  # Загружает все переменные с префиксом CT_

    Переменные окружения:
        CT_RISK_MAX_POSITION=1000
        CT_RISK_MAX_DRAWDOWN=0.15
        CT_EXCHANGE_API_KEY=xxx
    """

    def __init__(self, prefix: str = "CT_") -> None:
        """
        Инициализировать провайдер.

        Аргументы:
            prefix: Префикс переменных окружения для загрузки
        """
        self._prefix = prefix.upper()
        self._last_source: str | None = None
        self._cached_data: bytes | None = None

    async def load(self, source: str) -> bytes:
        """
        Загрузить конфигурацию из переменных окружения.

        Аргументы:
            source: Ignored (существует для совместимости с интерфейсом)

        Returns:
            JSON-байты с конфигурацией

        Note:
            source игнорируется - все переменные с префиксом загружаются
        """
        self._last_source = source

        config: dict[str, Any] = {}

        for key, value in os.environ.items():
            if not key.startswith(self._prefix):
                continue

            # Убираем префикс из ключа
            clean_key = key[len(self._prefix) :]

            # Пытаемся преобразовать значение
            config[clean_key] = self._parse_value(value)

        self._cached_data = json.dumps(config).encode("utf-8")
        return self._cached_data

    async def reload(self) -> bytes:
        """
        Перезагрузить конфигурацию.

        Returns:
            JSON-байты с конфигурацией

        Note:
            Возвращает кешированное значение если есть,
            иначе загружает заново
        """
        if self._cached_data is not None:
            return self._cached_data

        return await self.load("")

    def _parse_value(self, value: str) -> Any:
        """
        Преобразовать строку в Python-значение.

        Логика:
        - "true"/"false" -> bool
        - Числа с точкой -> float
        - Целые числа -> int
        - JSON объекты/массивы -> dict/list
        - Остальное -> str
        """
        # Boolean
        if value.lower() == "true":
            return True
        if value.lower() == "false":
            return False

        # Числа
        try:
            if "." in value:
                return float(value)
            return int(value)
        except ValueError:
            pass

        # JSON
        if value.startswith("{") or value.startswith("["):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                pass

        # Строка
        return value


class InfisicalConfigProvider(IConfigLoader):
    """
    Провайдер для загрузки конфигурации из Infisical.

    Требует установленной переменной окружения:
    - INFISICAL_TOKEN: токен доступа к Infisical

    Пример использования:
        provider = InfisicalConfigProvider()
        secrets = await provider.load_secrets("development")
    """

    def __init__(
        self,
        token: str | None = None,
        project_id: str | None = None,
        environment: str = "development",
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        """
        Инициализировать провайдер.

        Аргументы:
            token: Токен доступа Infisical
            project_id: ID проекта в Infisical
            environment: Окружение (development, production)
            http_client: AsyncClient для HTTP запросов (для DI/тестирования)
        """
        self._token = token or os.environ.get("INFISICAL_TOKEN")
        self._project_id = project_id or os.environ.get("INFISICAL_PROJECT_ID")
        self._environment = environment
        self._last_source: str | None = None
        self._http_client = http_client
        self._cached_secrets: dict[str, Any] | None = None

        if not self._token:
            raise ValueError("INFISICAL_TOKEN не установлен")

    async def load(self, source: str) -> bytes:
        """
        Загрузить секреты из Infisical.

        Аргументы:
            source: Игнорируется (используется environment из конструктора)

        Returns:
            JSON-байты с секретами

        Raises:
            OSError: При ошибке запроса к Infisical
        """
        self._last_source = source

        secrets = await self._fetch_secrets()
        self._cached_secrets = secrets

        return json.dumps(secrets).encode("utf-8")

    async def reload(self) -> bytes:
        """
        Перезагрузить секреты из Infisical.

        Returns:
            JSON-байты с секретами
        """
        return await self.load(self._last_source or "")

    async def _fetch_secrets(self) -> dict[str, Any]:
        """
        Получить секреты из Infisical API.

        Returns:
            Словарь с секретами

        Raises:
            OSError: При ошибке запроса
        """
        # Используем Infisical API v2
        base_url = "https://api.infisical.com"
        url = f"{base_url}/v2/secrets"

        params = {
            "environment": self._environment,
            "projectId": self._project_id,
            "attachTo": "",
            "includeImportableSecrets": "false",
        }

        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

        try:
            if self._http_client:
                response = await self._http_client.get(url, headers=headers, params=params)
            else:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(url, headers=headers, params=params)

            if response.status_code == HTTP_NOT_FOUND:
                raise KeyError("Секреты не найдены в Infisical")

            if response.status_code != HTTP_OK:
                raise OSError(f"Ошибка Infisical: {response.status_code} - {response.text}")

            data = response.json()

            # Извлекаем секреты из ответа
            secrets: dict[str, Any] = {}
            if "secrets" in data:
                for secret in data["secrets"]:
                    key = secret.get("secretKey", "")
                    value = secret.get("secretValue", "")
                    if key:
                        secrets[key] = value

            return secrets

        except httpx.RequestError as e:
            raise OSError(f"Ошибка подключения к Infisical: {e}") from e

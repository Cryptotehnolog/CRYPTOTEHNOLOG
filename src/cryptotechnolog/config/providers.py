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
from typing import Any

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

    Требует установленных переменных окружения:
    - INFISICAL_TOKEN: токен доступа к Infisical
    - INFISICAL_URL: URL Infisical сервера (опционально, по умолчанию - локальный)

    Поддерживает:
    - Локальный Infisical (localhost:8080)
    - Machine Identity для bot-доступа
    - Fallback на .env файл если Infisical недоступен

    Пример использования:
        provider = InfisicalConfigProvider()
        secrets = await provider.load_secrets("development")

    Пример Machine Identity:
        provider = InfisicalConfigProvider(
            use_machine_identity=True,
            project_id="crypto-trading"
        )
    """

    DEFAULT_LOCAL_URL = "http://127.0.0.1:8080"
    DEFAULT_CLOUD_URL = "https://api.infisical.com"

    def __init__(
        self,
        token: str | None = None,
        project_id: str | None = None,
        environment: str = "development",
        http_client: httpx.AsyncClient | None = None,
        use_machine_identity: bool = False,
        local_url: str | None = None,
        fallback_to_env: bool = True,
    ) -> None:
        """
        Инициализировать провайдер.

        Аргументы:
            token: Токен доступа Infisical
            project_id: ID проекта в Infisical
            environment: Окружение (development, staging, production)
            http_client: AsyncClient для HTTP запросов (для DI/тестирования)
            use_machine_identity: Использовать Machine Identity вместо токена
            local_url: URL локального Infisical (по умолчанию http://127.0.0.1:8080)
            fallback_to_env: Использовать .env если Infisical недоступен
        """
        self._project_id = project_id or os.environ.get("INFISICAL_PROJECT_ID")
        self._environment = environment
        self._last_source: str | None = None
        self._http_client = http_client
        self._cached_secrets: dict[str, Any] | None = None
        self._use_machine_identity = use_machine_identity
        self._fallback_to_env = fallback_to_env

        # Determine Infisical URL (local or cloud)
        self._infisical_url = local_url or os.environ.get(
            "INFISICAL_URL", self.DEFAULT_LOCAL_URL
        )

        # Get token
        if use_machine_identity:
            # Machine Identity - читается из файла
            self._token = self._load_machine_identity_token()
        else:
            self._token = token or os.environ.get("INFISICAL_TOKEN")

        if not self._token and fallback_to_env:
            # Fallback to .env - load from .env.infisical
            self._token = self._load_token_from_env_file()

        if not self._token:
            raise ValueError(
                "INFISICAL_TOKEN не установлен и не найден в .env.infisical. "
                "Запустите scripts/setup_infisical.ps1 для инициализации."
            )

    def _load_machine_identity_token(self) -> str | None:
        """
        Загрузить токен Machine Identity из файла.

        Файл ищется в:
        - ./secrets/infisical-token (local development)
        - ~/.infisical/credentials (Infisical CLI)
        """
        # Try local file first
        local_token_path = Path("secrets/infisical-token")
        if local_token_path.exists():
            return local_token_path.read_text().strip()

        # Try Infisical CLI credentials
        cli_creds_path = Path.home() / ".infisical" / "credentials"
        if cli_creds_path.exists():
            import configparser
            creds = configparser.ConfigParser()
            creds.read(cli_creds_path)
            if creds.has_option("default", "token"):
                return creds.get("default", "token")

        return None

    def _load_token_from_env_file(self) -> str | None:
        """
        Загрузить токен из .env.infisical файла.
        """
        env_file = Path(".env.infisical")
        if not env_file.exists():
            return None

        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line.startswith("#") or not line:
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                if key.strip() == "INFISICAL_TOKEN":
                    return value.strip()

        return None

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
        # Используем Infisical API v2 - сконфигурированный URL
        base_url = self._infisical_url
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
            # Если включен fallback и локальный Infisical недоступен - пробуем cloud
            if self._fallback_to_env and base_url == self.DEFAULT_LOCAL_URL:
                # Retry with cloud URL
                return await self._fetch_secrets_cloud()
            raise OSError(f"Ошибка подключения к Infisical: {e}") from e

    async def _fetch_secrets_cloud(self) -> dict[str, Any]:
        """
        Получить секреты из облачного Infisical (fallback).

        Returns:
            Словарь с секретами
        """
        base_url = self.DEFAULT_CLOUD_URL
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

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers, params=params)

        if response.status_code == HTTP_NOT_FOUND:
            raise KeyError("Секреты не найдены в Infisical")

        if response.status_code != HTTP_OK:
            raise OSError(f"Ошибка Infisical: {response.status_code} - {response.text}")

        data = response.json()

        secrets: dict[str, Any] = {}
        if "secrets" in data:
            for secret in data["secrets"]:
                key = secret.get("secretKey", "")
                value = secret.get("secretValue", "")
                if key:
                    secrets[key] = value

        return secrets

    def get_url(self) -> str:
        """
        Получить текущий URL Infisical.

        Returns:
            URL Infisical сервера
        """
        return self._infisical_url

    def is_local(self) -> bool:
        """
        Проверить используется ли локальный Infisical.

        Returns:
            True если используется локальный Infisical
        """
        return self._infisical_url == self.DEFAULT_LOCAL_URL

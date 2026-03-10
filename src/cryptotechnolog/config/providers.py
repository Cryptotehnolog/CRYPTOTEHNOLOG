"""
Провайдеры для загрузки конфигурации.

Реализации:
- FileConfigProvider: загрузка из файлов (YAML, JSON)
- VaultConfigProvider: загрузка из HashiCorp Vault
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


class VaultConfigProvider(IConfigLoader):
    """
    Провайдер для загрузки конфигурации из HashiCorp Vault.

    Требует установленных переменных окружения:
    - VAULT_ADDR: адрес Vault сервера
    - VAULT_TOKEN: токен доступа

    Пример использования:
        provider = VaultConfigProvider()
        data = await provider.load("secret/data/cryptotechnolog/config")
    """

    def __init__(
        self,
        vault_addr: str | None = None,
        vault_token: str | None = None,
        mount_point: str = "secret",
    ) -> None:
        """
        Инициализировать провайдер.

        Аргументы:
            vault_addr: Адрес Vault сервера
            vault_token: Токен доступа
            mount_point: Точка монтирования (по умолчанию "secret")
        """
        self._vault_addr = vault_addr or os.environ.get("VAULT_ADDR")
        self._vault_token = vault_token or os.environ.get("VAULT_TOKEN")
        self._mount_point = mount_point
        self._last_source: str | None = None

        if not self._vault_addr:
            raise ValueError("VAULT_ADDR не установлен")

        if not self._vault_token:
            raise ValueError("VAULT_TOKEN не установлен")

    async def load(self, source: str) -> bytes:
        """
        Загрузить конфигурацию из Vault.

        Аргументы:
            source: Путь к секрету (например, "secret/data/myapp/config")

        Returns:
            Байты содержимого секрета в формате JSON

        Raises:
            IOError: При ошибке连接到 Vault
            KeyError: Если секрет не найден
        """
        self._last_source = source

        # Формируем URL для KV v2
        path_parts = source.lstrip("/").split("/")
        if len(path_parts) >= KV_V2_MIN_PARTS and path_parts[0] == "data":
            # KV v2 format: /v1/<mount>/data/<path>
            secret_path = "/".join(path_parts[1:])
            url = f"{self._vault_addr}/v1/{self._mount_point}/data/{secret_path}"
        else:
            # KV v1 format
            url = f"{self._vault_addr}/v1/{self._mount_point}/{source}"

        headers: dict[str, str] = {"X-Vault-Token": cast("str", self._vault_token)}

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers)

            if response.status_code == HTTP_NOT_FOUND:
                raise KeyError(f"Секрет не найден в Vault: {source}")

            if response.status_code != HTTP_OK:
                raise OSError(f"Ошибка Vault: {response.status_code} - {response.text}")

            data = response.json()

            # Извлекаем данные из KV v2 формата
            if "data" in data and "data" in data["data"]:
                content = json.dumps(data["data"]["data"])
            elif "data" in data:
                content = json.dumps(data["data"])
            else:
                content = json.dumps(data)

            return content.encode("utf-8")

    async def reload(self) -> bytes:
        """
        Перезагрузить конфигурацию из Vault.

        Returns:
            Байты содержимого секрета

        Raises:
            ValueError: Если source не был установлен
        """
        if not self._last_source:
            raise ValueError("Источник не был установлен при первичной загрузке")

        return await self.load(self._last_source)


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

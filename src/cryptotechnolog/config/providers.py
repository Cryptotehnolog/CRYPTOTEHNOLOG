"""
Провайдеры для загрузки конфигурации.

Реализации:
- FileConfigProvider: загрузка из файлов (YAML, JSON)
- InfisicalConfigProvider: загрузка из Infisical
- EnvConfigProvider: загрузка из переменных окружения

Все docstrings на русском языке.
"""

from __future__ import annotations

import configparser
import json
import logging
import os
from pathlib import Path
from typing import Any

import httpx

from cryptotechnolog.config.protocols import IConfigLoader

# Константы для HTTP статус-кодов
HTTP_NOT_FOUND = 404
HTTP_FORBIDDEN = 403
HTTP_OK = 200

# Настройка логирования
logger = logging.getLogger(__name__)


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
    - ИЛИ INFISICAL_CLIENT_ID + INFISICAL_CLIENT_SECRET: для Machine Identity
    - INFISICAL_URL: URL Infisical сервера (опционально, по умолчанию - локальный)

    Поддерживает:
    - Локальный Infisical (localhost:8080)
    - Machine Identity (Client ID + Client Secret)
    - Fallback на .env файл если Infisical недоступен

    Пример использования:
        provider = InfisicalConfigProvider()
        secrets = await provider.load_secrets("development")

    Пример Machine Identity:
        provider = InfisicalConfigProvider(
            use_machine_identity=True,
            client_id="your-client-id",
            client_secret="your-client-secret",
            project_id="crypto-trading"
        )
    """

    DEFAULT_LOCAL_URL = "http://127.0.0.1:8080"

    def _resolve_secret_paths(
        self,
        secret_paths: list[str] | None,
    ) -> list[str]:
        """
        Разрешить список путей к секретам.

        Аргументы:
            secret_paths: Переданный список путей

        Returns:
            Список путей к секретам
        """
        if secret_paths:
            return secret_paths

        paths_env = os.environ.get("INFISICAL_SECRET_PATHS", "")
        if paths_env:
            return [p.strip() for p in paths_env.split(",") if p.strip()]

        # По умолчанию используем один путь для обратной совместимости
        single_path = os.environ.get("INFISICAL_SECRET_PATH", "/staging/crypto")
        return [single_path]

    def _resolve_secret_keys(
        self,
        secret_keys: list[str] | None,
    ) -> list[str]:
        """
        Разрешить список ключей секретов.

        Аргументы:
            secret_keys: Переданный список ключей

        Returns:
            Список имён секретов
        """
        if secret_keys:
            return secret_keys

        keys_env = os.environ.get("INFISICAL_SECRET_KEYS", "")
        if keys_env:
            return [k.strip() for k in keys_env.split(",") if k.strip()]

        return []

    def _resolve_credentials(
        self,
        use_machine_identity: bool,
        client_id: str | None,
        client_secret: str | None,
        token: str | None,
        fallback_to_env: bool,
    ) -> None:
        """
        Разрешить и валидировать credentials для аутентификации.

        Аргументы:
            use_machine_identity: Использовать Machine Identity
            client_id: Client ID
            client_secret: Client Secret
            token: Токен доступа
            fallback_to_env: Fallback на .env файл

        Raises:
            ValueError: При отсутствии необходимых credentials
        """
        # Проверяем Machine Identity
        if use_machine_identity or client_id:
            self._resolve_machine_identity_credentials(client_id, client_secret)
        else:
            self._resolve_token_credentials(token, fallback_to_env)

    def _resolve_machine_identity_credentials(
        self,
        client_id: str | None,
        client_secret: str | None,
    ) -> None:
        """
        Разрешить и валидировать Machine Identity credentials.

        Raises:
            ValueError: При отсутствии обязательных параметров
        """
        self._client_id = client_id or os.environ.get("INFISICAL_CLIENT_ID")
        self._client_secret = client_secret or os.environ.get("INFISICAL_CLIENT_SECRET")

        # Валидация обязательных параметров для Machine Identity
        if not self._client_id:
            raise ValueError(
                "INFISICAL_CLIENT_ID не установлен. Укажите client_id или "
                "установите переменную окружения INFISICAL_CLIENT_ID."
            )
        if not self._client_secret:
            raise ValueError(
                "INFISICAL_CLIENT_SECRET не установлен. Укажите client_secret или "
                "установите переменную окружения INFISICAL_CLIENT_SECRET."
            )

        # Валидация project_id для Machine Identity
        if not self._project_id:
            raise ValueError(
                "INFISICAL_PROJECT_ID не установлен. Укажите project_id или "
                "установите переменную окружения INFISICAL_PROJECT_ID."
            )

        logger.debug(
            "Machine Identity настроен: client_id=%s, project_id=%s, paths=%s",
            self._client_id[:8] + "..." if self._client_id else None,
            self._project_id,
            self._secret_paths,
        )

        # Always load from .env.infisical to get secret keys and paths
        self._load_token_from_env_file()

        self._token = None  # Will be fetched dynamically

    def _resolve_token_credentials(
        self,
        token: str | None,
        fallback_to_env: bool,
    ) -> None:
        """
        Разрешить token-based credentials.

        Args:
            token: Переданный токен
            fallback_to_env: Fallback на .env файл

        Raises:
            ValueError: При отсутствии токена
        """
        self._client_id = None
        self._client_secret = None

        # Token-based auth
        self._token = token or os.environ.get("INFISICAL_TOKEN")

        if not self._token and fallback_to_env:
            # Fallback to .env - load from .env.infisical
            self._token = self._load_token_from_env_file()

        if not self._token and not (self._client_id and self._client_secret):
            raise ValueError(
                "INFISICAL_TOKEN не установлен и не найден в .env.infisical. "
                "Запустите scripts/setup_infisical.ps1 для инициализации."
            )

    def __init__(
        self,
        token: str | None = None,
        project_id: str | None = None,
        environment: str = "development",
        http_client: httpx.AsyncClient | None = None,
        use_machine_identity: bool = False,
        client_id: str | None = None,
        client_secret: str | None = None,
        local_url: str | None = None,
        fallback_to_env: bool = True,
        secret_paths: list[str] | None = None,
        secret_keys: list[str] | None = None,
    ) -> None:
        """
        Инициализировать провайдер.

        Аргументы:
            token: Токен доступа Infisical
            project_id: ID проекта в Infisical
            environment: Окружение (development, staging, production)
            http_client: AsyncClient для HTTP запросов (для DI/тестирования)
            use_machine_identity: Использовать Machine Identity
            client_id: Client ID для Machine Identity
            client_secret: Client Secret для Machine Identity
            local_url: URL локального Infisical (по умолчанию http://127.0.0.1:8080)
            fallback_to_env: Использовать .env если Infisical недоступен
            secret_paths: Список путей к папкам с секретами (например: ["/production/crypto", "/staging/telegram"])
            secret_keys: Список имён секретов для загрузки (например: ["API_KEY", "API_SECRET"])
        """
        self._project_id = project_id or os.environ.get("INFISICAL_PROJECT_ID")
        self._environment = environment
        self._last_source: str | None = None
        self._http_client = http_client
        self._cached_secrets: dict[str, Any] | None = None
        self._use_machine_identity = use_machine_identity
        self._fallback_to_env = fallback_to_env

        # Разрешаем пути к секретам
        self._secret_paths = self._resolve_secret_paths(secret_paths)

        # Разрешаем ключи секретов
        self._secret_keys = self._resolve_secret_keys(secret_keys)

        # Determine Infisical URL (local or cloud)
        self._infisical_url = local_url or os.environ.get("INFISICAL_URL", self.DEFAULT_LOCAL_URL)

        # Разрешаем и валидируем credentials
        self._resolve_credentials(
            use_machine_identity=use_machine_identity,
            client_id=client_id,
            client_secret=client_secret,
            token=token,
            fallback_to_env=fallback_to_env,
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
            creds = configparser.ConfigParser()
            creds.read(cli_creds_path)
            if creds.has_option("default", "token"):
                return creds.get("default", "token")

        return None

    def _load_token_from_env_file(self) -> str | None:
        """
        Загрузить токен или credentials из .env.infisical файла.
        """
        env_file = Path(".env.infisical")
        if not env_file.exists():
            return None

        # Read file and remove BOM if present
        content = env_file.read_text(encoding="utf-8-sig")

        # Load all variables from .env.infisical
        env_vars = {}
        for line in content.splitlines():
            stripped_line = line.strip()
            if stripped_line.startswith("#") or not stripped_line:
                continue
            if "=" in stripped_line:
                key, value = stripped_line.split("=", 1)
                env_vars[key.strip()] = value.strip()

        # Check for Client ID/Secret first (Machine Identity)
        if "INFISICAL_CLIENT_ID" in env_vars:
            self._client_id = env_vars["INFISICAL_CLIENT_ID"]
        if "INFISICAL_CLIENT_SECRET" in env_vars:
            self._client_secret = env_vars["INFISICAL_CLIENT_SECRET"]
        if "INFISICAL_PROJECT_ID" in env_vars:
            self._project_id = env_vars["INFISICAL_PROJECT_ID"]
        if "INFISICAL_SECRET_PATH" in env_vars:
            self._secret_paths = [env_vars["INFISICAL_SECRET_PATH"]]
        if "INFISICAL_SECRET_PATHS" in env_vars:
            paths = env_vars["INFISICAL_SECRET_PATHS"]
            self._secret_paths = [p.strip() for p in paths.split(",") if p.strip()]

        # Load secret keys
        if "INFISICAL_SECRET_KEYS" in env_vars:
            keys = env_vars["INFISICAL_SECRET_KEYS"]
            self._secret_keys = [k.strip() for k in keys.split(",") if k.strip()]

        # Fallback to token
        if "INFISICAL_TOKEN" in env_vars:
            return env_vars["INFISICAL_TOKEN"]

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
        Получить секреты из Infisical API v3.

        Returns:
            Словарь с секретами

        Raises:
            OSError: При ошибке запроса
        """
        # If using Machine Identity with Client ID/Secret, get token first
        if self._client_id and self._client_secret and not self._token:
            await self._authenticate_machine_identity()

        secrets: dict[str, Any] = {}

        # Получаем секреты из каждого пути
        for secret_path in self._secret_paths:
            path_secrets = await self._fetch_secrets_from_path(secret_path)
            secrets.update(path_secrets)

        return secrets

    async def _fetch_secrets_from_path(self, secret_path: str) -> dict[str, Any]:
        """
        Получить секреты из указанного пути.

        Args:
            secret_path: Путь к папке с секретами (например /staging/crypto)

        Returns:
            Словарь с секретами из этого пути
        """
        # Определяем список ключей которые нужно получить
        secret_keys = self._get_secret_keys()

        secrets: dict[str, Any] = {}

        # Infisical API v3: получаем каждый секрет отдельно
        for key in secret_keys:
            try:
                secret = await self._fetch_single_secret(key, secret_path)
                if secret:
                    secrets[key] = secret
            except Exception:
                # Пропускаем секрет который не найден
                continue

        return secrets

    def _get_secret_keys(self) -> list[str]:
        """
        Получить список ключей секретов для загрузки.

        Returns:
            Список имён секретов
        """
        # Если ключи уже загружены из .env.infisical - используем их
        if self._secret_keys:
            return self._secret_keys

        # Иначе пробуем из переменной окружения
        keys_env = os.environ.get("INFISICAL_SECRET_KEYS", "")
        if keys_env:
            return [k.strip() for k in keys_env.split(",") if k.strip()]

        # Если не указано - возвращаем пустой список
        return []

    async def _fetch_single_secret(self, key: str, secret_path: str = "/") -> str | None:
        """
        Получить один секрет по имени.

        Args:
            key: Имя секрета
            secret_path: Путь к папке с секретами

        Returns:
            Значение секрета или None если не найден
        """
        base_url = self._infisical_url

        # Используем endpoint для получения конкретного секрета
        url = f"{base_url}/api/v3/secrets/raw/{key}"

        params = {
            "workspaceId": self._project_id,
            "environment": self._environment,
        }

        # Add path if specified (for folder-based secrets)
        if secret_path:
            params["secretPath"] = secret_path

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
                # Секрет не найден - это нормально
                logger.debug("Секрет '%s' не найден в path '%s'", key, secret_path)
                return None

            if response.status_code == HTTP_FORBIDDEN:
                # Нет доступа к секрету
                logger.warning(
                    "Нет доступа к секрету '%s' в path '%s': код %d",
                    key,
                    secret_path,
                    response.status_code,
                )
                return None

            if response.status_code != HTTP_OK:
                # Другая ошибка - логируем и продолжаем
                logger.error(
                    "Ошибка при получении секрета '%s' из path '%s': код %d, тело: %s",
                    key,
                    secret_path,
                    response.status_code,
                    response.text[:200],
                )
                return None

            data = response.json()

            # Извлекаем значение из ответа
            if "secret" in data:
                return data["secret"].get("secretValue", "")

            return None

        except httpx.RequestError as e:
            logger.error("Ошибка подключения к Infisical при получении '%s': %s", key, str(e))
            return None

    async def _authenticate_machine_identity(self) -> None:
        """
        Аутентифицироваться через Machine Identity (Client ID + Client Secret).

        Использует Universal Auth в Infisical.
        """
        base_url = self._infisical_url
        url = f"{base_url}/api/v1/auth/universal-auth/login"

        logger.debug("Аутентификация Machine Identity: url=%s", url)

        payload = {
            "clientId": self._client_id,
            "clientSecret": self._client_secret,
        }

        headers = {
            "Content-Type": "application/json",
        }

        try:
            if self._http_client:
                response = await self._http_client.post(url, json=payload, headers=headers)
            else:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(url, json=payload, headers=headers)

            if response.status_code != HTTP_OK:
                logger.error(
                    "Ошибка аутентификации Machine Identity: код=%d, тело=%s",
                    response.status_code,
                    response.text[:200],
                )
                raise OSError(
                    f"Ошибка аутентификации Machine Identity: {response.status_code} - {response.text}"
                )

            data = response.json()
            self._token = data.get("accessToken")

            if not self._token:
                raise OSError("Не получен accessToken от Infisical")

            logger.info(
                "Успешная аутентификация Machine Identity для project_id=%s", self._project_id
            )

        except httpx.RequestError as e:
            logger.error("Ошибка подключения к Infisical: %s", str(e))
            raise OSError(f"Ошибка подключения к Infisical: {e}") from e

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

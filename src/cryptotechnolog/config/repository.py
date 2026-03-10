"""
Репозиторий для хранения версий конфигурации.

Реализует интерфейс IConfigRepository для сохранения
истории версий конфигурации в PostgreSQL.

Все docstrings на русском языке.
"""

from __future__ import annotations

from typing import Any

import asyncpg

from cryptotechnolog.config.protocols import IConfigRepository


class RepositoryError(Exception):
    """
    Ошибка работы с репозиторием.

    Атрибуты:
        operation: Операция которая вызвала ошибку
        reason: Причина ошибки
    """

    def __init__(self, operation: str, reason: str) -> None:
        """
        Инициализировать ошибку репозитория.

        Аргументы:
            operation: Название операции
            reason: Причина ошибки
        """
        self.operation = operation
        self.reason = reason
        message = f"Ошибка {operation}: {reason}"
        super().__init__(message)


class ConfigRepository(IConfigRepository):
    """
    Репозиторий для хранения версий конфигурации.

    Сохраняет историю всех изменений конфигурации в PostgreSQL.
    Позволяет получить историю версий и выполнить rollback.

    Пример использования:
        repo = ConfigRepository(pool)
        await repo.save_version("1.0.0", "abc123", "...", "operator")
        history = await repo.get_history(limit=10)
    """

    TABLE_NAME = "config_versions"

    def __init__(self, pool: asyncpg.Pool) -> None:
        """
        Инициализировать репозиторий.

        Аргументы:
            pool: Пул соединений к PostgreSQL
        """
        self._pool = pool

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
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    f"""
                    INSERT INTO {self.TABLE_NAME}
                        (version, content_hash, config_yaml, loaded_by)
                    VALUES ($1, $2, $3, $4)
                    """,
                    version,
                    content_hash,
                    config_yaml,
                    loaded_by,
                )
        except asyncpg.UniqueViolationError:
            # Версия уже существует - обновляем
            async with self._pool.acquire() as conn:
                await conn.execute(
                    f"""
                    UPDATE {self.TABLE_NAME}
                    SET content_hash = $1,
                        config_yaml = $2,
                        loaded_by = $3,
                        loaded_at = CURRENT_TIMESTAMP
                    WHERE version = $4
                    """,
                    content_hash,
                    config_yaml,
                    loaded_by,
                    version,
                )
        except asyncpg.PostgresConnectionError as e:
            raise RepositoryError("save_version", f"Ошибка подключения: {e}") from e
        except Exception as e:
            raise RepositoryError("save_version", str(e)) from e

    async def get_history(self, limit: int = 10) -> list[dict[str, Any]]:
        """
        Получить историю версий конфигурации.

        Аргументы:
            limit: Количество версий

        Returns:
            Список версий

        Raises:
            RepositoryError: При ошибке получения истории
        """
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(
                    f"""
                    SELECT
                        id,
                        version,
                        content_hash,
                        loaded_by,
                        loaded_at,
                        is_active,
                        signature_valid,
                        signature_key_id
                    FROM {self.TABLE_NAME}
                    ORDER BY loaded_at DESC
                    LIMIT $1
                    """,
                    limit,
                )

                return [dict(row) for row in rows]
        except asyncpg.PostgresConnectionError as e:
            raise RepositoryError("get_history", f"Ошибка подключения: {e}") from e
        except Exception as e:
            raise RepositoryError("get_history", str(e)) from e

    async def get_latest(self) -> dict[str, Any] | None:
        """
        Получить последнюю активную версию.

        Returns:
            Последняя версия или None

        Raises:
            RepositoryError: При ошибке получения версии
        """
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(f"""
                    SELECT
                        id,
                        version,
                        content_hash,
                        config_yaml,
                        loaded_by,
                        loaded_at,
                        is_active,
                        signature_valid,
                        signature_key_id
                    FROM {self.TABLE_NAME}
                    WHERE is_active = TRUE
                    ORDER BY loaded_at DESC
                    LIMIT 1
                    """)

                return dict(row) if row else None
        except asyncpg.PostgresConnectionError as e:
            raise RepositoryError("get_latest", f"Ошибка подключения: {e}") from e
        except Exception as e:
            raise RepositoryError("get_latest", str(e)) from e

    async def get_by_version(self, version: str) -> dict[str, Any] | None:
        """
        Получить версию по номеру.

        Аргументы:
            version: Версия конфигурации

        Returns:
            Версия конфигурации или None

        Raises:
            RepositoryError: При ошибке получения версии
        """
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    f"""
                    SELECT
                        id,
                        version,
                        content_hash,
                        config_yaml,
                        loaded_by,
                        loaded_at,
                        is_active,
                        signature_valid,
                        signature_key_id
                    FROM {self.TABLE_NAME}
                    WHERE version = $1
                    """,
                    version,
                )

                return dict(row) if row else None
        except asyncpg.PostgresConnectionError as e:
            raise RepositoryError("get_by_version", f"Ошибка подключения: {e}") from e
        except Exception as e:
            raise RepositoryError("get_by_version", str(e)) from e

    async def get_by_hash(self, content_hash: str) -> dict[str, Any] | None:
        """
        Получить версию по хешу содержимого.

        Аргументы:
            content_hash: SHA256 хеш содержимого

        Returns:
            Версия конфигурации или None

        Raises:
            RepositoryError: При ошибке получения версии
        """
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    f"""
                    SELECT
                        id,
                        version,
                        content_hash,
                        config_yaml,
                        loaded_by,
                        loaded_at,
                        is_active,
                        signature_valid,
                        signature_key_id
                    FROM {self.TABLE_NAME}
                    WHERE content_hash = $1
                    """,
                    content_hash,
                )

                return dict(row) if row else None
        except asyncpg.PostgresConnectionError as e:
            raise RepositoryError("get_by_hash", f"Ошибка подключения: {e}") from e
        except Exception as e:
            raise RepositoryError("get_by_hash", str(e)) from e

"""
Тесты для ConfigRepository.

Тестирование:
    - ConfigRepository: сохранение версий конфигурации

Все docstrings на русском языке.
"""

from unittest.mock import AsyncMock, MagicMock

import asyncpg
import pytest

from cryptotechnolog.config.repository import ConfigRepository, RepositoryError


class TestConfigRepository:
    """Тесты для ConfigRepository."""

    @pytest.fixture
    def mock_pool(self) -> MagicMock:
        """Создать мок пула соединений."""
        pool = MagicMock()
        pool.acquire = MagicMock()
        return pool

    @pytest.fixture
    def repo(self, mock_pool: MagicMock) -> ConfigRepository:
        """Создать репозиторий с моком."""
        return ConfigRepository(mock_pool)

    def test_init(self, repo: ConfigRepository, mock_pool: MagicMock) -> None:
        """Тест инициализации."""
        assert repo._pool == mock_pool
        assert repo.TABLE_NAME == "config_versions"

    @pytest.mark.asyncio
    async def test_save_version_success(self, repo: ConfigRepository, mock_pool: MagicMock) -> None:
        """Тест успешного сохранения версии."""
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        await repo.save_version("1.0.0", "abc123", "version: 1.0.0", "operator")

        mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_version_duplicate(self, repo: ConfigRepository, mock_pool: MagicMock) -> None:
        """Тест обновления при дубликате версии."""
        mock_conn = AsyncMock()
        # Первый вызов - UniqueViolationError, второй - успех
        mock_conn.execute.side_effect = [
            asyncpg.UniqueViolationError("duplicate key", "23505", "unique_version"),
            None
        ]
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Должно выполнить UPDATE после UniqueViolationError
        await repo.save_version("1.0.0", "abc123", "version: 1.0.0", "operator")

        assert mock_conn.execute.call_count == 2  # INSERT + UPDATE

    @pytest.mark.asyncio
    async def test_save_version_connection_error(self, repo: ConfigRepository, mock_pool: MagicMock) -> None:
        """Тест ошибки подключения."""
        mock_conn = AsyncMock()
        mock_conn.execute.side_effect = asyncpg.PostgresConnectionError("connection failed")
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        with pytest.raises(RepositoryError) as exc_info:
            await repo.save_version("1.0.0", "abc123", "version: 1.0.0", "operator")

        assert "save_version" in exc_info.value.operation

    @pytest.mark.asyncio
    async def test_get_history(self, repo: ConfigRepository, mock_pool: MagicMock) -> None:
        """Тест получения истории версий."""
        mock_conn = AsyncMock()
        mock_conn.fetch.return_value = [
            {
                "id": 1,
                "version": "1.0.0",
                "content_hash": "abc123",
                "loaded_by": "operator",
                "loaded_at": "2024-01-01 00:00:00",
                "is_active": True,
                "signature_valid": True,
                "signature_key_id": "ABC123",
            }
        ]
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        result = await repo.get_history(limit=10)

        assert len(result) == 1
        assert result[0]["version"] == "1.0.0"
        mock_conn.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_history_empty(self, repo: ConfigRepository, mock_pool: MagicMock) -> None:
        """Тест получения пустой истории."""
        mock_conn = AsyncMock()
        mock_conn.fetch.return_value = []
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        result = await repo.get_history(limit=10)

        assert result == []

    @pytest.mark.asyncio
    async def test_get_latest(self, repo: ConfigRepository, mock_pool: MagicMock) -> None:
        """Тест получения последней активной версии."""
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = {
            "id": 1,
            "version": "1.0.0",
            "content_hash": "abc123",
            "config_yaml": "version: 1.0.0",
            "loaded_by": "operator",
            "loaded_at": "2024-01-01 00:00:00",
            "is_active": True,
            "signature_valid": True,
            "signature_key_id": "ABC123",
        }
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        result = await repo.get_latest()

        assert result is not None
        assert result["version"] == "1.0.0"
        mock_conn.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_latest_none(self, repo: ConfigRepository, mock_pool: MagicMock) -> None:
        """Тест получения None когда нет активных версий."""
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = None
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        result = await repo.get_latest()

        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_version(self, repo: ConfigRepository, mock_pool: MagicMock) -> None:
        """Тест получения версии по номеру."""
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = {
            "id": 1,
            "version": "1.0.0",
            "content_hash": "abc123",
            "config_yaml": "version: 1.0.0",
            "loaded_by": "operator",
            "loaded_at": "2024-01-01 00:00:00",
            "is_active": True,
            "signature_valid": True,
            "signature_key_id": "ABC123",
        }
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        result = await repo.get_by_version("1.0.0")

        assert result is not None
        assert result["version"] == "1.0.0"

    @pytest.mark.asyncio
    async def test_get_by_hash(self, repo: ConfigRepository, mock_pool: MagicMock) -> None:
        """Тест получения версии по хешу."""
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = {
            "id": 1,
            "version": "1.0.0",
            "content_hash": "abc123",
            "config_yaml": "version: 1.0.0",
            "loaded_by": "operator",
            "loaded_at": "2024-01-01 00:00:00",
            "is_active": True,
            "signature_valid": True,
            "signature_key_id": "ABC123",
        }
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        result = await repo.get_by_hash("abc123")

        assert result is not None
        assert result["content_hash"] == "abc123"


class TestRepositoryIntegration:
    """Интеграционные тесты для ConfigRepository."""

    def test_repository_implements_protocol(self) -> None:
        """Тест что ConfigRepository реализует IConfigRepository."""
        mock_pool = MagicMock()
        repo = ConfigRepository(mock_pool)

        # Проверяем наличие методов (structural typing)
        assert hasattr(repo, "save_version")
        assert hasattr(repo, "get_history")
        assert hasattr(repo, "get_latest")
        assert callable(repo.save_version)
        assert callable(repo.get_history)
        assert callable(repo.get_latest)

    def test_repository_error_attributes(self) -> None:
        """Тест что RepositoryError содержит нужные атрибуты."""
        error = RepositoryError("test_operation", "test_reason")

        assert error.operation == "test_operation"
        assert error.reason == "test_reason"
        assert "test_operation" in str(error)
        assert "test_reason" in str(error)

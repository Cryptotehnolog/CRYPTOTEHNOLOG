"""
Unit тесты для ConfigManager.

Тестирует:
    - Загрузку конфигурации
    - Валидацию
    - Сохранение в историю
    - Hot reload
    - Публикацию событий

Все docstrings на русском языке.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cryptotechnolog.config.manager import ConfigManager, ConfigManagerError
from cryptotechnolog.config.models import SystemConfig
from cryptotechnolog.core.event import Event, Priority


# Фикстуры для моков компонентов
@pytest.fixture
def mock_loader() -> MagicMock:
    """Создать мок загрузчика конфигурации."""
    loader = MagicMock()
    loader.load = AsyncMock(return_value=b"version: 1.0.0\nenvironment: test\n")
    return loader


@pytest.fixture
def mock_parser() -> MagicMock:
    """Создать мок парсера конфигурации."""
    parser = MagicMock()
    parser.parse = MagicMock(return_value={"version": "1.0.0", "environment": "test"})
    return parser


@pytest.fixture
def mock_validator() -> MagicMock:
    """Создать мок валидатора конфигурации."""
    from decimal import Decimal

    from cryptotechnolog.config.models import ExchangeConfig, RiskConfig, StrategyConfig, SystemConfig

    validator = MagicMock()
    config = SystemConfig(
        version="1.0.0",
        environment="test",
        risk=RiskConfig(
            base_r_percent=Decimal("0.01"),
            max_r_per_trade=Decimal("0.05"),
            max_drawdown_hard=Decimal("0.20"),
            max_drawdown_soft=Decimal("0.10"),
            correlation_limit=Decimal("0.7"),
        ),
        exchanges=[],
        strategies=[],
    )
    validator.validate = MagicMock(return_value=config)
    return validator


@pytest.fixture
def mock_signer() -> MagicMock:
    """Создать мок GPG верификатора."""
    signer = MagicMock()
    signer.verify = AsyncMock(return_value=True)
    signer.is_signature_required = MagicMock(return_value=False)
    return signer


@pytest.fixture
def mock_repository() -> MagicMock:
    """Создать мок репозитория."""
    repository = MagicMock()
    repository.save_version = AsyncMock()
    repository.get_history = AsyncMock(
        return_value=[
            {"version": "1.0.0", "loaded_at": "2024-01-01", "is_active": True}
        ]
    )
    repository.get_latest = AsyncMock(
        return_value={"version": "1.0.0", "config_yaml": "version: 1.0.0"}
    )
    repository.get_by_version = AsyncMock(
        return_value={"version": "1.0.0", "config_yaml": "version: 1.0.0"}
    )
    return repository


@pytest.fixture
def mock_event_bus() -> MagicMock:
    """Создать мок Event Bus."""
    event_bus = MagicMock()
    event_bus.publish = AsyncMock(return_value=True)
    return event_bus


@pytest.fixture
def config_manager(
    mock_loader: MagicMock,
    mock_parser: MagicMock,
    mock_validator: MagicMock,
    mock_signer: MagicMock,
    mock_repository: MagicMock,
    mock_event_bus: MagicMock,
) -> ConfigManager:
    """Создать ConfigManager с моками."""
    return ConfigManager(
        loader=mock_loader,
        parser=mock_parser,
        validator=mock_validator,
        signer=mock_signer,
        repository=mock_repository,
        event_bus=mock_event_bus,
    )


class TestConfigManagerInit:
    """Тесты инициализации ConfigManager."""

    def test_init_success(self, config_manager: ConfigManager) -> None:
        """Тест успешной инициализации."""
        assert config_manager._loader is not None
        assert config_manager._parser is not None
        assert config_manager._validator is not None
        assert config_manager._signer is not None
        assert config_manager._repository is not None
        assert config_manager._event_bus is not None
        assert config_manager.current_config is None

    def test_current_config_property(self, config_manager: ConfigManager) -> None:
        """Тест свойства current_config."""
        assert config_manager.current_config is None


class TestConfigManagerLoad:
    """Тесты загрузки конфигурации."""

    @pytest.mark.asyncio
    async def test_load_success(
        self,
        config_manager: ConfigManager,
        mock_loader: MagicMock,
        mock_parser: MagicMock,
        mock_validator: MagicMock,
        mock_signer: MagicMock,
        mock_repository: MagicMock,
        mock_event_bus: MagicMock,
    ) -> None:
        """Тест успешной загрузки конфигурации."""
        config = await config_manager.load("config.yaml")

        # Проверяем вызовы
        mock_loader.load.assert_called_once_with("config.yaml")
        mock_parser.parse.assert_called_once()
        mock_validator.validate.assert_called_once()
        mock_repository.save_version.assert_called_once()
        mock_event_bus.publish.assert_called_once()

        # Проверяем результат
        assert config.version == "1.0.0"
        assert config.environment == "test"

    @pytest.mark.asyncio
    async def test_load_without_history(
        self,
        config_manager: ConfigManager,
        mock_repository: MagicMock,
    ) -> None:
        """Тест загрузки без сохранения в историю."""
        await config_manager.load("config.yaml", save_to_history=False)

        mock_repository.save_version.assert_not_called()

    @pytest.mark.asyncio
    async def test_load_with_custom_loaded_by(
        self,
        config_manager: ConfigManager,
        mock_repository: MagicMock,
    ) -> None:
        """Тест загрузки с указанием загрузившего."""
        await config_manager.load("config.yaml", loaded_by="operator")

        mock_repository.save_version.assert_called_once()
        call_kwargs = mock_repository.save_version.call_args
        assert call_kwargs.kwargs["loaded_by"] == "operator"


class TestConfigManagerReload:
    """Тесты hot reload."""

    @pytest.mark.asyncio
    async def test_reload_success(
        self,
        config_manager: ConfigManager,
        mock_loader: MagicMock,
    ) -> None:
        """Тест успешного hot reload."""
        # Сначала загружаем
        await config_manager.load("config.yaml")

        # Перезагружаем
        await config_manager.reload()

        # Проверяем что load был вызван дважды
        assert mock_loader.load.call_count == 2

    @pytest.mark.asyncio
    async def test_reload_without_loaded_config(
        self,
        config_manager: ConfigManager,
    ) -> None:
        """Тест reload без предварительной загрузки."""
        with pytest.raises(ConfigManagerError) as exc_info:
            await config_manager.reload()

        assert "Нет загруженной конфигурации" in str(exc_info.value)


class TestConfigManagerHistory:
    """Тесты работы с историей версий."""

    @pytest.mark.asyncio
    async def test_load_from_history_success(
        self,
        config_manager: ConfigManager,
        mock_repository: MagicMock,
        mock_parser: MagicMock,
        mock_validator: MagicMock,
    ) -> None:
        """Тест загрузки версии из истории."""
        config = await config_manager.load_from_history("1.0.0")

        mock_repository.get_by_version.assert_called_once_with("1.0.0")
        assert config.version == "1.0.0"

    @pytest.mark.asyncio
    async def test_load_from_history_not_found(
        self,
        config_manager: ConfigManager,
        mock_repository: MagicMock,
    ) -> None:
        """Тест загрузки несуществующей версии."""
        mock_repository.get_by_version = AsyncMock(return_value=None)

        with pytest.raises(ConfigManagerError) as exc_info:
            await config_manager.load_from_history("999.0.0")

        assert "не найдена" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_history(
        self,
        config_manager: ConfigManager,
        mock_repository: MagicMock,
    ) -> None:
        """Тест получения истории версий."""
        history = await config_manager.get_history(limit=5)

        mock_repository.get_history.assert_called_once_with(limit=5)
        assert len(history) == 1
        assert history[0]["version"] == "1.0.0"

    @pytest.mark.asyncio
    async def test_get_latest_from_history(
        self,
        config_manager: ConfigManager,
        mock_repository: MagicMock,
    ) -> None:
        """Тест получения последней версии."""
        latest = await config_manager.get_latest_from_history()

        mock_repository.get_latest.assert_called_once()
        assert latest is not None
        assert latest["version"] == "1.0.0"


class TestConfigManagerErrors:
    """Тесты обработки ошибок."""

    @pytest.mark.asyncio
    async def test_load_error(
        self,
        config_manager: ConfigManager,
        mock_loader: MagicMock,
    ) -> None:
        """Тест обработки ошибки загрузки."""
        mock_loader.load = AsyncMock(side_effect=IOError("File not found"))

        with pytest.raises(ConfigManagerError) as exc_info:
            await config_manager.load("config.yaml")

        assert exc_info.value.operation == "load"


class TestConfigManagerPublish:
    """Тесты публикации событий."""

    @pytest.mark.asyncio
    async def test_publish_config_updated_event(
        self,
        config_manager: ConfigManager,
        mock_event_bus: MagicMock,
    ) -> None:
        """Тест публикации события CONFIG_UPDATED."""
        # Загружаем конфигурацию
        await config_manager.load("config.yaml")

        # Проверяем что publish был вызван
        mock_event_bus.publish.assert_called_once()

        # Получаем Event который был передан
        call_args = mock_event_bus.publish.call_args
        event: Event = call_args.args[0]

        # Проверяем параметры события
        assert event.event_type == "CONFIG_UPDATED"
        assert event.source == "CONFIG_MANAGER"
        assert event.priority == Priority.HIGH
        assert "new_version" in event.payload
        assert event.payload["new_version"] == "1.0.0"

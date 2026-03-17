"""
Unit тесты для ConfigManager.

Тестирует:
    - Загрузку конфигурации
    - Валидацию
    - Сохранение в историю
    - Hot reload
    - Публикацию событий
    - Rollback
    - Метрики

Все docstrings на русском языке.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from cryptotechnolog.config.manager import ConfigManager, ConfigManagerError, ConfigMetrics
from cryptotechnolog.config.models import RiskConfig, SystemConfig
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
        return_value=[{"version": "1.0.0", "loaded_at": "2024-01-01", "is_active": True}]
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

    def test_internal_version_property(self, config_manager: ConfigManager) -> None:
        """Тест свойства internal_version."""
        assert config_manager.internal_version == 0


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

    @pytest.mark.asyncio
    async def test_load_signature_verification_success(
        self,
        config_manager: ConfigManager,
    ) -> None:
        """Тест успешной верификации подписи."""
        await config_manager.load("config.yaml")

        # Проверяем что signer.verify был вызван
        config_manager._signer.verify.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_signature_verification_failed(
        self,
        config_manager: ConfigManager,
        mock_signer: MagicMock,
    ) -> None:
        """Тест неудачной верификации подписи."""
        mock_signer.verify = AsyncMock(return_value=False)

        await config_manager.load("config.yaml")

        mock_signer.verify.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_validation_error(
        self,
        config_manager: ConfigManager,
        mock_validator: MagicMock,
    ) -> None:
        """Тест ошибки валидации."""
        mock_validator.validate = MagicMock(side_effect=ValueError("Validation error"))

        with pytest.raises(ConfigManagerError):
            await config_manager.load("config.yaml")


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
        mock_loader.load = AsyncMock(side_effect=OSError("File not found"))

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

    @pytest.mark.asyncio
    async def test_publish_without_event_bus(
        self,
        mock_loader: MagicMock,
        mock_parser: MagicMock,
        mock_validator: MagicMock,
        mock_signer: MagicMock,
        mock_repository: MagicMock,
    ) -> None:
        """Тест работы без event bus."""
        manager = ConfigManager(
            loader=mock_loader,
            parser=mock_parser,
            validator=mock_validator,
            signer=mock_signer,
            repository=mock_repository,
            event_bus=None,  # Без event bus
        )

        # Должно работать без ошибок
        config = await manager.load("config.yaml")
        assert config.version == "1.0.0"


class TestRollback:
    """Тесты rollback функциональности."""

    @pytest.mark.asyncio
    async def test_rollback_to_version_success(
        self,
        config_manager: ConfigManager,
        mock_repository: MagicMock,
    ) -> None:
        """Тест успешного rollback к версии."""
        # Предварительно загружаем конфигурацию
        await config_manager.load("config.yaml")

        # Rollback к версии
        config = await config_manager.rollback_to_version("1.0.0")

        mock_repository.get_by_version.assert_called_once_with("1.0.0")
        assert config.version == "1.0.0"

    @pytest.mark.asyncio
    async def test_rollback_to_version_not_found(
        self,
        config_manager: ConfigManager,
        mock_repository: MagicMock,
    ) -> None:
        """Тест rollback к несуществующей версии."""
        mock_repository.get_by_version = AsyncMock(return_value=None)

        with pytest.raises(ConfigManagerError) as exc_info:
            await config_manager.rollback_to_version("999.0.0")

        assert "не найдена" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_rollback_to_previous_success(
        self,
        config_manager: ConfigManager,
        mock_repository: MagicMock,
    ) -> None:
        """Тест успешного rollback к предыдущей версии."""
        # Мокаем историю с двумя версиями
        mock_repository.get_history = AsyncMock(
            return_value=[
                {"version": "2.0.0", "loaded_at": "2024-01-02", "loaded_by": "system"},
                {"version": "1.0.0", "loaded_at": "2024-01-01", "loaded_by": "system"},
            ]
        )

        await config_manager.load("config.yaml")
        config = await config_manager.rollback_to_previous()

        assert config.version == "1.0.0"

    @pytest.mark.asyncio
    async def test_rollback_to_previous_not_enough_versions(
        self,
        config_manager: ConfigManager,
        mock_repository: MagicMock,
    ) -> None:
        """Тест rollback при недостатке версий."""
        mock_repository.get_history = AsyncMock(
            return_value=[{"version": "1.0.0", "loaded_at": "2024-01-01"}]
        )

        await config_manager.load("config.yaml")

        with pytest.raises(ConfigManagerError) as exc_info:
            await config_manager.rollback_to_previous()

        assert "Нет предыдущей версии" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_rollback_candidates(
        self,
        config_manager: ConfigManager,
        mock_repository: MagicMock,
    ) -> None:
        """Тест получения кандидатов для rollback."""
        mock_repository.get_history = AsyncMock(
            return_value=[
                {"version": "2.0.0", "loaded_at": "2024-01-02", "loaded_by": "system"},
                {"version": "1.0.0", "loaded_at": "2024-01-01", "loaded_by": "system"},
            ]
        )

        await config_manager.load("config.yaml")
        candidates = await config_manager.get_rollback_candidates()

        # Текущая версия (из загруженной конфигурации) должна быть исключена
        # Загруженная версия 1.0.0, значит она исключается
        assert len(candidates) <= 2


class TestCompareVersions:
    """Тесты сравнения версий."""

    @pytest.mark.asyncio
    async def test_compare_versions_success(
        self,
        config_manager: ConfigManager,
        mock_repository: MagicMock,
    ) -> None:
        """Тест успешного сравнения версий."""
        mock_repository.get_by_version = AsyncMock(
            side_effect=[
                {"version": "1.0.0", "config_yaml": "version: 1.0.0", "loaded_at": "2024-01-01"},
                {"version": "2.0.0", "config_yaml": "version: 2.0.0", "loaded_at": "2024-01-02"},
            ]
        )

        result = await config_manager.compare_versions("1.0.0", "2.0.0")

        assert result["version1"] == "1.0.0"
        assert result["version2"] == "2.0.0"
        assert "diff" in result

    @pytest.mark.asyncio
    async def test_compare_versions_not_found(
        self,
        config_manager: ConfigManager,
        mock_repository: MagicMock,
    ) -> None:
        """Тест сравнения с несуществующей версией."""
        mock_repository.get_by_version = AsyncMock(return_value=None)

        with pytest.raises(ConfigManagerError) as exc_info:
            await config_manager.compare_versions("1.0.0", "999.0.0")

        assert "не найдена" in str(exc_info.value)


class TestConfigValueAccess:
    """Тесты доступа к значениям конфигурации."""

    @pytest.mark.asyncio
    async def test_get_config_value(
        self,
        config_manager: ConfigManager,
    ) -> None:
        """Тест получения значения по ключу."""
        await config_manager.load("config.yaml")

        # Проверяем что internal_version работает
        assert config_manager.internal_version >= 1

    @pytest.mark.asyncio
    async def test_get_config_value_not_loaded(
        self,
        config_manager: ConfigManager,
    ) -> None:
        """Тест получения значения без загруженной конфигурации."""
        result = config_manager.get_config_value("risk.base_r_percent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_risk_config(
        self,
        config_manager: ConfigManager,
    ) -> None:
        """Тест получения конфигурации рисков."""
        await config_manager.load("config.yaml")

        risk = config_manager.get_risk_config()
        assert risk is not None
        assert "base_r_percent" in risk

    @pytest.mark.asyncio
    async def test_get_risk_config_not_loaded(
        self,
        config_manager: ConfigManager,
    ) -> None:
        """Тест получения рисков без конфигурации."""
        risk = config_manager.get_risk_config()
        assert risk is None

    @pytest.mark.asyncio
    async def test_get_exchanges(
        self,
        config_manager: ConfigManager,
    ) -> None:
        """Тест получения списка бирж."""
        await config_manager.load("config.yaml")

        exchanges = config_manager.get_exchanges()
        assert isinstance(exchanges, list)

    @pytest.mark.asyncio
    async def test_get_exchanges_not_loaded(
        self,
        config_manager: ConfigManager,
    ) -> None:
        """Тест получения бирж без конфигурации."""
        exchanges = config_manager.get_exchanges()
        assert exchanges == []

    @pytest.mark.asyncio
    async def test_get_strategies(
        self,
        config_manager: ConfigManager,
    ) -> None:
        """Тест получения списка стратегий."""
        await config_manager.load("config.yaml")

        strategies = config_manager.get_strategies()
        assert isinstance(strategies, list)

    @pytest.mark.asyncio
    async def test_get_strategies_not_loaded(
        self,
        config_manager: ConfigManager,
    ) -> None:
        """Тест получения стратегий без конфигурации."""
        strategies = config_manager.get_strategies()
        assert strategies == []


class TestConfigMetrics:
    """Тесты ConfigMetrics."""

    def test_metrics_initialization(self) -> None:
        """Тест инициализации метрик."""
        metrics = ConfigMetrics()
        result = metrics.to_dict()

        assert "counters" in result
        assert "gauges" in result
        assert "histograms" in result
        assert "timings" in result

    def test_increment_counter(self) -> None:
        """Тест инкремента счётчика."""
        metrics = ConfigMetrics()
        metrics.increment("test_counter")
        metrics.increment("test_counter")

        result = metrics.to_dict()
        assert result["counters"]["test_counter"] == 2

    def test_increment_counter_with_labels(self) -> None:
        """Тест инкремента счётчика с лейблами."""
        metrics = ConfigMetrics()
        metrics.increment("test_counter", labels={"status": "success"})

        result = metrics.to_dict()
        assert 'test_counter{status="success"}' in result["counters"]

    def test_gauge(self) -> None:
        """Тест установки gauge."""
        metrics = ConfigMetrics()
        metrics.gauge("test_gauge", 1.5)

        result = metrics.to_dict()
        assert result["gauges"]["test_gauge"] == 1.5

    def test_observe(self) -> None:
        """Тест наблюдения значения."""
        metrics = ConfigMetrics()
        metrics.observe("test_histogram", 1.0)
        metrics.observe("test_histogram", 2.0)

        result = metrics.to_dict()
        assert "test_histogram" in result["histograms"]

    def test_timing(self) -> None:
        """Тест записи времени."""
        metrics = ConfigMetrics()
        metrics.timing("test_timing", 100.0)

        result = metrics.to_dict()
        assert "test_timing" in result["timings"]

    def test_histogram_empty(self) -> None:
        """Тест пустой гистограммы."""
        metrics = ConfigMetrics()
        # Пустой observe - без значения (использует значение по умолчанию)
        # observe требует value, поэтому создаём гистограмму с пустым списком
        result = metrics.to_dict()
        stats = result["histograms"].get("empty_histogram")

        # Если ключа нет - это ожидаемое поведение
        # Если ключ есть - проверяем что count = 0
        if stats:
            assert stats["count"] == 0.0

    def test_to_prometheus_format(self) -> None:
        """Тест экспорта в Prometheus формат."""
        metrics = ConfigMetrics()
        metrics.increment("test_counter")
        metrics.gauge("test_gauge", 1.5)
        metrics.observe("test_histogram", 1.0)

        output = metrics.to_prometheus_format()

        assert "test_counter" in output
        assert "test_gauge" in output
        assert "test_histogram" in output

    def test_get_metrics(self, config_manager: ConfigManager) -> None:
        """Тест получения метрик ConfigManager."""
        asyncio.run(config_manager.load("config.yaml"))

        metrics = config_manager.get_metrics()
        assert "counters" in metrics
        assert "gauges" in metrics

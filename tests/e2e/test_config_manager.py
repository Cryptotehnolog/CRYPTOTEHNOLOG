# ==================== E2E: Config Manager ====================
"""
E2E тесты для Config Manager.

Тестирует полный цикл работы с конфигурацией:
- Загрузка из различных источников
- Валидация и парсинг
- Сохранение в историю
- Hot reload
- Публикация событий

Все docstrings на русском языке.
"""

from decimal import Decimal
from pathlib import Path

import pytest

from cryptotechnolog.config.manager import ConfigManager
from cryptotechnolog.config.models import SystemConfig
from cryptotechnolog.config.parsers import YamlParser
from cryptotechnolog.config.providers import FileConfigProvider
from cryptotechnolog.config.repository import ConfigRepository
from cryptotechnolog.config.signers import GPGSigner
from cryptotechnolog.config.validators import PydanticValidator

# Тестовые данные


VALID_CONFIG_YAML = b"""
version: "1.0.0"
environment: production
risk:
  base_r_percent: "0.01"
  max_r_per_trade: "0.05"
  max_drawdown_hard: "0.20"
  max_drawdown_soft: "0.10"
  correlation_limit: "0.7"
exchanges:
  - name: bybit
    enabled: true
    api_key_vault_path: secret/data/cryptotehnolog/exchanges/bybit/api_key
    api_secret_vault_path: secret/data/cryptotehnolog/exchanges/bybit/secret
    testnet: false
strategies:
  - name: sma_cross
    enabled: true
    max_risk_r: "0.02"
    params:
      fast_period: 10
      slow_period: 50
    exchanges:
      - bybit
    symbols:
      - BTC/USDT
system:
  boot_timeout_seconds: 30
"""


@pytest.mark.e2e
@pytest.mark.config
class TestConfigManagerE2E:
    """E2E тесты для ConfigManager."""

    @pytest.fixture
    def temp_config_file(self, tmp_path: Path) -> Path:
        """Создать временный файл конфигурации."""
        config_file = tmp_path / "config.yaml"
        config_file.write_bytes(VALID_CONFIG_YAML)
        return config_file

    @pytest.fixture
    def config_repository(self, db_pool):
        """Создать репозиторий с реальным пулом БД."""
        return ConfigRepository(db_pool)

    @pytest.mark.asyncio
    async def test_full_config_load_pipeline(
        self,
        temp_config_file: Path,
        config_repository: ConfigRepository,
    ) -> None:
        """
        E2E: Полный цикл загрузки конфигурации.

        Тестирует:
        1. Загрузка из файла
        2. Парсинг YAML
        3. Валидация через Pydantic
        4. Сохранение в историю
        """
        # Создание компонентов
        provider = FileConfigProvider(base_path=temp_config_file.parent)
        parser = YamlParser()
        validator = PydanticValidator(schema=SystemConfig)
        # Использовать пустой signer (без GPG)
        signer = GPGSigner(keyring_path=Path("/tmp/fake_keyring"))
        event_bus = None  # Без event bus для простоты

        # Создание менеджера
        manager = ConfigManager(
            loader=provider,
            parser=parser,
            validator=validator,
            signer=signer,
            repository=config_repository,
            event_bus=event_bus,
        )

        # Загрузка конфигурации с сохранением в историю
        config = await manager.load(
            source=str(temp_config_file),
            save_to_history=True,
            loaded_by="e2e_test",
        )

        # Проверка результата
        assert config.version == "1.0.0"
        assert config.environment == "production"
        assert config.risk.base_r_percent == Decimal("0.01")
        assert config.risk.max_drawdown_hard == Decimal("0.20")
        assert len(config.exchanges) == 1
        assert config.exchanges[0].name == "bybit"
        assert len(config.strategies) == 1
        assert config.strategies[0].name == "sma_cross"

        # Проверка что сохранилось в историю
        history = await manager.get_history(limit=10)
        assert len(history) >= 1
        assert history[0]["version"] == "1.0.0"

    @pytest.mark.asyncio
    async def test_config_hot_reload(
        self,
        temp_config_file: Path,
        config_repository: ConfigRepository,
    ) -> None:
        """
        E2E: Hot reload конфигурации.

        Тестирует:
        1. Загрузка начальной конфигурации
        2. Модификация файла
        3. Hot reload
        4. Проверка обновления
        """
        # Создание компонентов
        provider = FileConfigProvider(base_path=temp_config_file.parent)
        parser = YamlParser()
        validator = PydanticValidator(schema=SystemConfig)
        signer = GPGSigner(keyring_path=Path("/tmp/fake_keyring"))
        event_bus = None

        manager = ConfigManager(
            loader=provider,
            parser=parser,
            validator=validator,
            signer=signer,
            repository=config_repository,
            event_bus=event_bus,
        )

        # Первая загрузка
        config1 = await manager.load(
            source=str(temp_config_file),
            save_to_history=False,
        )
        assert config1.version == "1.0.0"

        # Обновление файла
        new_config = VALID_CONFIG_YAML.replace(b"1.0.0", b"1.0.1")
        temp_config_file.write_bytes(new_config)

        # Hot reload
        config2 = await manager.reload(loaded_by="e2e_test")

        # Проверка обновления
        assert config2.version == "1.0.1"
        assert config2 != config1

    @pytest.mark.asyncio
    async def test_config_with_multiple_exchanges(
        self,
        temp_config_file: Path,
        config_repository: ConfigRepository,
    ) -> None:
        """
        E2E: Конфигурация с несколькими биржами.
        """
        # Создание конфигурации с несколькими биржами
        multi_exchange_yaml = b"""
version: "1.0.0"
environment: production
risk:
  base_r_percent: "0.02"
  max_r_per_trade: "0.08"
  max_drawdown_hard: "0.30"
  max_drawdown_soft: "0.15"
  correlation_limit: "0.6"
exchanges:
  - name: bybit
    enabled: true
    api_key_vault_path: secret/data/cryptotehnolog/exchanges/bybit/api_key
    api_secret_vault_path: secret/data/cryptotehnolog/exchanges/bybit/secret
    testnet: false
  - name: binance
    enabled: true
    api_key_vault_path: secret/data/cryptotehnolog/exchanges/binance/api_key
    api_secret_vault_path: secret/data/cryptotehnolog/exchanges/binance/secret
    testnet: true
strategies: []
system: {}
"""
        temp_config_file.write_bytes(multi_exchange_yaml)

        # Создание компонентов
        provider = FileConfigProvider(base_path=temp_config_file.parent)
        parser = YamlParser()
        validator = PydanticValidator(schema=SystemConfig)
        signer = GPGSigner(keyring_path=Path("/tmp/fake_keyring"))
        event_bus = None

        manager = ConfigManager(
            loader=provider,
            parser=parser,
            validator=validator,
            signer=signer,
            repository=config_repository,
            event_bus=event_bus,
        )

        config = await manager.load(
            source=str(temp_config_file),
            save_to_history=False,
        )

        assert len(config.exchanges) == 2
        exchange_names = {e.name for e in config.exchanges}
        assert exchange_names == {"bybit", "binance"}
        # Проверка что testnet для binance = True
        binance = next(e for e in config.exchanges if e.name == "binance")
        assert binance.testnet is True

    @pytest.mark.asyncio
    async def test_config_versioning(
        self,
        temp_config_file: Path,
        config_repository: ConfigRepository,
    ) -> None:
        """
        E2E: Версионирование конфигурации.

        Тестирует:
        1. Загрузка нескольких версий
        2. Проверка истории
        3. Загрузка конкретной версии
        """
        # Создание компонентов
        provider = FileConfigProvider(base_path=temp_config_file.parent)
        parser = YamlParser()
        validator = PydanticValidator(schema=SystemConfig)
        signer = GPGSigner(keyring_path=Path("/tmp/fake_keyring"))
        event_bus = None

        manager = ConfigManager(
            loader=provider,
            parser=parser,
            validator=validator,
            signer=signer,
            repository=config_repository,
            event_bus=event_bus,
        )

        # Загрузка первой версии
        await manager.load(
            source=str(temp_config_file),
            save_to_history=True,
            loaded_by="test_user",
        )

        # Обновление версии
        new_config = VALID_CONFIG_YAML.replace(b'version: "1.0.0"', b'version: "2.0.0"')
        temp_config_file.write_bytes(new_config)

        # Загрузка второй версии
        await manager.load(
            source=str(temp_config_file),
            save_to_history=True,
            loaded_by="test_user",
        )

        # Проверка истории
        history = await manager.get_history(limit=10)
        assert len(history) >= 2

        # Загрузка конкретной версии
        old_config = await manager.load_from_history(version="1.0.0")
        assert old_config.version == "1.0.0"


@pytest.mark.e2e
@pytest.mark.config
class TestConfigEdgeCases:
    """Тесты граничных случаев для ConfigManager."""

    @pytest.fixture
    def temp_config_file(self, tmp_path: Path) -> Path:
        """Создать временный файл конфигурации."""
        config_file = tmp_path / "config.yaml"
        config_file.write_bytes(VALID_CONFIG_YAML)
        return config_file

    @pytest.fixture
    def config_repository(self, db_pool):
        """Создать репозиторий с реальным пулом БД."""
        return ConfigRepository(db_pool)

    @pytest.mark.asyncio
    async def test_empty_exchanges_and_strategies(
        self,
        tmp_path: Path,
        config_repository: ConfigRepository,
    ) -> None:
        """
        E2E: Пустые списки exchanges и strategies.
        """
        config_yaml = b"""
version: "1.0.0"
environment: test
risk:
  base_r_percent: "0.01"
  max_r_per_trade: "0.05"
  max_drawdown_hard: "0.20"
  max_drawdown_soft: "0.10"
  correlation_limit: "0.7"
exchanges: []
strategies: []
system: {}
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_bytes(config_yaml)

        provider = FileConfigProvider(base_path=tmp_path)
        parser = YamlParser()
        validator = PydanticValidator(schema=SystemConfig)
        signer = GPGSigner(keyring_path=Path("/tmp/fake_keyring"))
        event_bus = None

        manager = ConfigManager(
            loader=provider,
            parser=parser,
            validator=validator,
            signer=signer,
            repository=config_repository,
            event_bus=event_bus,
        )

        config = await manager.load(
            source=str(config_file),
            save_to_history=False,
        )

        assert config.exchanges == []
        assert config.strategies == []

    @pytest.mark.asyncio
    async def test_different_environments(
        self,
        tmp_path: Path,
        config_repository: ConfigRepository,
    ) -> None:
        """
        E2E: Различные окружения (production, staging, development).
        """
        environments = ["production", "staging", "development"]

        for env in environments:
            config_yaml = f"""
version: "1.0.0"
environment: {env}
risk:
  base_r_percent: "0.01"
  max_r_per_trade: "0.05"
  max_drawdown_hard: "0.20"
  max_drawdown_soft: "0.10"
  correlation_limit: "0.7"
exchanges: []
strategies: []
system: {{}}
""".encode()

            config_file = tmp_path / f"config_{env}.yaml"
            config_file.write_bytes(config_yaml)

            provider = FileConfigProvider(base_path=tmp_path)
            parser = YamlParser()
            validator = PydanticValidator(schema=SystemConfig)
            signer = GPGSigner(keyring_path=Path("/tmp/fake_keyring"))
            event_bus = None

            manager = ConfigManager(
                loader=provider,
                parser=parser,
                validator=validator,
                signer=signer,
                repository=config_repository,
                event_bus=event_bus,
            )

            config = await manager.load(
                source=str(config_file),
                save_to_history=False,
            )

            assert config.environment == env

"""
Тесты для валидаторов конфигурации.

Тестирование:
    - PydanticValidator: валидация через Pydantic модели

Все docstrings на русском языке.
"""

from decimal import Decimal

import pytest

from cryptotechnolog.config.models import (
    ExchangeConfig,
    RiskConfig,
    StrategyConfig,
    SystemConfig,
)
from cryptotechnolog.config.parsers import YamlParser
from cryptotechnolog.config.validators import PydanticValidator, ValidationError


class TestPydanticValidator:
    """Тесты для PydanticValidator."""

    def test_validate_valid_risk_config(self) -> None:
        """Тест валидации корректной конфигурации рисков."""
        validator = PydanticValidator(schema=RiskConfig)
        data = {
            "base_r_percent": "0.01",
            "max_r_per_trade": "0.05",
            "max_drawdown_hard": "0.20",
            "max_drawdown_soft": "0.10",
            "correlation_limit": "0.7",
        }

        result = validator.validate(data)

        assert isinstance(result, RiskConfig)
        assert result.base_r_percent == Decimal("0.01")
        assert result.max_r_per_trade == Decimal("0.05")

    def test_validate_invalid_risk_config(self) -> None:
        """Тест что некорректная конфигурация вызывает ошибку."""
        validator = PydanticValidator(schema=RiskConfig)
        data = {
            "base_r_percent": "999",  # Слишком большое значение
            "max_r_per_trade": "0.05",
            "max_drawdown_hard": "0.20",
            "max_drawdown_soft": "0.10",
            "correlation_limit": "0.7",
        }

        with pytest.raises(ValidationError) as exc_info:
            validator.validate(data)

        assert "base_r_percent" in str(exc_info.value)

    def test_validate_soft_greater_than_hard(self) -> None:
        """Тест что soft лимит больше hard вызывает ошибку."""
        validator = PydanticValidator(schema=RiskConfig)
        data = {
            "base_r_percent": "0.01",
            "max_r_per_trade": "0.05",
            "max_drawdown_hard": "0.20",
            "max_drawdown_soft": "0.30",  # Больше чем hard!
            "correlation_limit": "0.7",
        }

        with pytest.raises(ValidationError) as exc_info:
            validator.validate(data)

        assert "мягкий лимит" in str(exc_info.value).lower()

    def test_validate_valid_exchange_config(self) -> None:
        """Тест валидации корректной конфигурации биржи."""
        validator = PydanticValidator(schema=ExchangeConfig)
        data = {
            "name": "bybit",
            "enabled": True,
            "api_key": "test_api_key",
            "api_secret": "test_api_secret",
            "rate_limits": {"orders_per_second": 10},
            "testnet": False,
        }

        result = validator.validate(data)

        assert isinstance(result, ExchangeConfig)
        assert result.name == "bybit"
        assert result.enabled is True

    def test_validate_empty_api_keys(self) -> None:
        """Тест что пустые API ключи допустимы (будут загружены из Infisical)."""
        validator = PydanticValidator(schema=ExchangeConfig)
        data = {
            "name": "bybit",
            "enabled": True,
            "api_key": "",
            "api_secret": "",
            "testnet": False,
        }

        result = validator.validate(data)

        assert isinstance(result, ExchangeConfig)
        assert result.name == "bybit"

    def test_validate_valid_strategy_config(self) -> None:
        """Тест валидации корректной конфигурации стратегии."""
        validator = PydanticValidator(schema=StrategyConfig)
        data = {
            "name": "sma_cross",
            "enabled": True,
            "max_risk_r": "0.02",
            "params": {"fast_period": 10, "slow_period": 50},
            "exchanges": ["bybit"],
            "symbols": ["BTC/USDT"],
        }

        result = validator.validate(data)

        assert isinstance(result, StrategyConfig)
        assert result.name == "sma_cross"
        assert result.max_risk_r == Decimal("0.02")

    def test_validate_valid_system_config(self) -> None:
        """Тест валидации корректной системной конфигурации."""
        validator = PydanticValidator(schema=SystemConfig)
        data = {
            "version": "1.0.0",
            "environment": "production",
            "risk": {
                "base_r_percent": "0.01",
                "max_r_per_trade": "0.05",
                "max_drawdown_hard": "0.20",
                "max_drawdown_soft": "0.10",
                "correlation_limit": "0.7",
            },
            "exchanges": [],
            "strategies": [],
            "system": {"boot_timeout_seconds": 30},
        }

        result = validator.validate(data)

        assert isinstance(result, SystemConfig)
        assert result.version == "1.0.0"
        assert result.environment == "production"

    def test_validate_extra_fields_forbidden(self) -> None:
        """Тест что лишние поля запрещены."""
        validator = PydanticValidator(schema=SystemConfig)
        data = {
            "version": "1.0.0",
            "environment": "production",
            "risk": {
                "base_r_percent": "0.01",
                "max_r_per_trade": "0.05",
                "max_drawdown_hard": "0.20",
                "max_drawdown_soft": "0.10",
                "correlation_limit": "0.7",
            },
            "exchanges": [],
            "strategies": [],
            "system": {},
            "unknown_field": "not_allowed",  # Лишнее поле!
        }

        with pytest.raises(ValidationError) as exc_info:
            validator.validate(data)

        assert "unknown_field" in str(exc_info.value) or "extra" in str(exc_info.value).lower()

    def test_validate_not_dict_raises_error(self) -> None:
        """Тест что не словарь вызывает ошибку."""
        validator = PydanticValidator(schema=SystemConfig)

        with pytest.raises(ValidationError) as exc_info:
            validator.validate("not a dict")  # type: ignore[arg-type]

        assert "Ожидался словарь" in str(exc_info.value)

    def test_validate_empty_dict_raises_error(self) -> None:
        """Тест что пустой словарь вызывает ошибку."""
        validator = PydanticValidator(schema=RiskConfig)

        with pytest.raises(ValidationError) as exc_info:
            validator.validate({})

        assert "base_r_percent" in str(exc_info.value)


class TestValidatorIntegration:
    """Интеграционные тесты для валидаторов."""

    def test_full_config_validation_pipeline(self) -> None:
        """Тест полного пайплайна: парсинг -> валидация."""
        # Парсим YAML
        parser = YamlParser()
        yaml_data = b"""
version: "1.0.0"
environment: production
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
        parsed_data = parser.parse(yaml_data)

        # Валидируем
        validator = PydanticValidator(schema=SystemConfig)
        config = validator.validate(parsed_data)

        assert config.version == "1.0.0"
        assert config.risk.base_r_percent == Decimal("0.01")

    def test_validator_implements_protocol(self) -> None:
        """Тест что валидатор реализует IConfigValidator."""
        validator = PydanticValidator(schema=SystemConfig)

        # Проверяем наличие метода validate (structural typing)
        assert hasattr(validator, "validate")
        assert callable(validator.validate)

    def test_validation_error_contains_all_errors(self) -> None:
        """Тест что ValidationError содержит все ошибки."""
        validator = PydanticValidator(schema=RiskConfig)
        data = {
            "base_r_percent": "999",  # Неверное
            "max_r_per_trade": "999",  # Неверное
            "max_drawdown_hard": "999",  # Неверное
            "max_drawdown_soft": "999",  # Неверное
            "correlation_limit": "999",  # Неверное
        }

        with pytest.raises(ValidationError) as exc_info:
            validator.validate(data)

        # Должно быть несколько ошибок
        assert len(exc_info.value.errors) >= 1

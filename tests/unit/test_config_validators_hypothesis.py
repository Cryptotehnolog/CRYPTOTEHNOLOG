"""
Property-based тесты для валидаторов конфигурации.

Использует hypothesis для генерации случайных данных и проверки инвариантов.

Все docstrings на русском языке.
"""

from decimal import Decimal
from typing import Any

from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st
import pytest

from cryptotechnolog.config.models import (
    ExchangeConfig,
    RiskConfig,
    StrategyConfig,
    SystemConfig,
)
from cryptotechnolog.config.validators import PydanticValidator, ValidationError

# Стратегии для генерации данных


@st.composite
def valid_risk_config_strategy(draw: st.DrawFn) -> dict[str, Any]:
    """
    Генерировать валидную конфигурацию рисков.

    Гарантирует что max_drawdown_soft < max_drawdown_hard и все значения в допустимых пределах.
    """
    # Генерируем с запасом чтобы избежать проблем с precision
    base_r_percent = draw(st.decimals(min_value="0.001", max_value="0.04", places=3))
    max_r_per_trade = draw(st.decimals(min_value="0.005", max_value="0.08", places=3))
    max_drawdown_hard = draw(st.decimals(min_value="0.10", max_value="0.40", places=3))
    # Мягкий лимит должен быть меньше жесткого и не более 0.29
    max_drawdown_soft_value = min(float(max_drawdown_hard) - 0.02, 0.29)
    max_drawdown_soft = draw(
        st.decimals(min_value="0.03", max_value=str(max_drawdown_soft_value), places=3)
    )
    correlation_limit = draw(st.decimals(min_value="0.5", max_value="0.9", places=2))

    return {
        "base_r_percent": str(base_r_percent),
        "max_r_per_trade": str(max_r_per_trade),
        "max_drawdown_hard": str(max_drawdown_hard),
        "max_drawdown_soft": str(max_drawdown_soft),
        "correlation_limit": str(correlation_limit),
    }


@st.composite
def valid_exchange_config_strategy(draw: st.DrawFn) -> dict[str, Any]:
    """Генерировать валидную конфигурацию биржи (без Vault)."""
    name = draw(st.sampled_from(["bybit", "okx", "binance", "huobi", "gate"]))
    enabled = draw(st.booleans())
    testnet = draw(st.booleans())

    return {
        "name": name,
        "enabled": enabled,
        "api_key": "",
        "api_secret": "",
        "rate_limits": {"orders_per_second": 10, "requests_per_minute": 1200},
        "testnet": testnet,
    }


@st.composite
def valid_strategy_config_strategy(draw: st.DrawFn) -> dict[str, Any]:
    """Генерировать валидную конфигурацию стратегии."""
    name = draw(st.sampled_from(["sma_cross", "rsi_mean_reversion", "momentum", "breakout"]))
    enabled = draw(st.booleans())
    max_risk_r = draw(st.decimals(min_value="0.01", max_value="0.09", places=3))
    exchanges = draw(st.lists(st.sampled_from(["bybit", "okx", "binance"]), min_size=1, max_size=3))
    symbols = draw(
        st.lists(st.sampled_from(["BTC/USDT", "ETH/USDT", "SOL/USDT"]), min_size=1, max_size=5)
    )

    return {
        "name": name,
        "enabled": enabled,
        "max_risk_r": str(max_risk_r),
        "params": {},
        "exchanges": exchanges,
        "symbols": symbols,
    }


class TestPydanticValidatorPropertyBased:
    """Property-based тесты для PydanticValidator."""

    @given(data=valid_risk_config_strategy())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_valid_risk_config_always_passes(self, data: dict[str, Any]) -> None:
        """
        Property: Любая валидная конфигурация рисков должна проходить валидацию.

        Это гарантирует что стратегия генерации корректна.
        """
        validator = PydanticValidator(schema=RiskConfig)
        result = validator.validate(data)

        assert isinstance(result, RiskConfig)
        assert result.base_r_percent == Decimal(data["base_r_percent"])
        # Проверяем что мягкий лимит меньше жесткого
        assert result.max_drawdown_soft < result.max_drawdown_hard

    @given(base_r_percent=st.decimals(min_value="0.001", max_value="0.05", places=3))
    @settings(max_examples=20, suppress_health_check=[HealthCheck.too_slow])
    def test_base_r_percent_range_enforced(self, base_r_percent: Decimal) -> None:
        """Property: base_r_percent должен быть в пределах [0.001, 0.05]."""
        validator = PydanticValidator(schema=RiskConfig)
        data = {
            "base_r_percent": str(base_r_percent),
            "max_r_per_trade": "0.05",
            "max_drawdown_hard": "0.20",
            "max_drawdown_soft": "0.10",
            "correlation_limit": "0.7",
        }

        # Должно пройти валидацию
        result = validator.validate(data)
        assert Decimal("0.001") <= result.base_r_percent <= Decimal("0.05")

    @given(
        max_drawdown_hard=st.decimals(min_value="0.10", max_value="0.50", places=3),
        max_drawdown_soft=st.decimals(min_value="0.05", max_value="0.45", places=3),
    )
    @settings(
        max_examples=30, suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much]
    )
    def test_drawdown_soft_less_than_hard(
        self,
        max_drawdown_hard: Decimal,
        max_drawdown_soft: Decimal,
    ) -> None:
        """Property: max_drawdown_soft должен быть меньше max_drawdown_hard."""
        # Фильтруем только невалидные комбинации
        assume(max_drawdown_soft >= max_drawdown_hard)

        validator = PydanticValidator(schema=RiskConfig)
        data = {
            "base_r_percent": "0.01",
            "max_r_per_trade": "0.05",
            "max_drawdown_hard": str(max_drawdown_hard),
            "max_drawdown_soft": str(max_drawdown_soft),
            "correlation_limit": "0.7",
        }

        # Должно вызвать ошибку
        with pytest.raises(ValidationError):
            validator.validate(data)

    @given(correlation_limit=st.decimals(min_value="0.0", max_value="1.5", places=2))
    @settings(max_examples=20, suppress_health_check=[HealthCheck.too_slow])
    def test_correlation_limit_range(self, correlation_limit: Decimal) -> None:
        """Property: correlation_limit должен быть в пределах [0.5, 1.0]."""
        # Фильтруем только невалидные значения
        assume(correlation_limit < Decimal("0.5") or correlation_limit > Decimal("1.0"))

        validator = PydanticValidator(schema=RiskConfig)
        data = {
            "base_r_percent": "0.01",
            "max_r_per_trade": "0.05",
            "max_drawdown_hard": "0.20",
            "max_drawdown_soft": "0.10",
            "correlation_limit": str(correlation_limit),
        }

        # Должно вызвать ошибку
        with pytest.raises(ValidationError):
            validator.validate(data)

    @given(data=valid_strategy_config_strategy())
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    def test_valid_strategy_config_always_passes(self, data: dict[str, Any]) -> None:
        """Property: Любая валидная конфигурация стратегии должна проходить валидацию."""
        validator = PydanticValidator(schema=StrategyConfig)
        result = validator.validate(data)

        assert isinstance(result, StrategyConfig)
        assert result.name == data["name"]
        assert result.enabled == data["enabled"]
        assert Decimal("0.01") <= result.max_risk_r <= Decimal("0.10")

    @given(max_risk_r=st.decimals(min_value="0.00", max_value="0.20", places=3))
    @settings(max_examples=20, suppress_health_check=[HealthCheck.too_slow])
    def test_strategy_max_risk_r_range(self, max_risk_r: Decimal) -> None:
        """Property: max_risk_r должен быть в пределах [0.01, 0.10]."""
        # Фильтруем только невалидные значения
        assume(max_risk_r < Decimal("0.01") or max_risk_r > Decimal("0.10"))

        validator = PydanticValidator(schema=StrategyConfig)
        data = {
            "name": "sma_cross",
            "enabled": True,
            "max_risk_r": str(max_risk_r),
            "params": {},
            "exchanges": ["bybit"],
            "symbols": ["BTC/USDT"],
        }

        # Должно вызвать ошибку
        with pytest.raises(ValidationError):
            validator.validate(data)

    @given(
        risk_data=valid_risk_config_strategy(),
        exchange_data=st.lists(valid_exchange_config_strategy(), max_size=2),
        strategy_data=st.lists(valid_strategy_config_strategy(), max_size=2),
    )
    @settings(max_examples=20, suppress_health_check=[HealthCheck.too_slow])
    def test_system_config_accepts_nested_valid_configs(
        self,
        risk_data: dict[str, Any],
        exchange_data: list[dict[str, Any]],
        strategy_data: list[dict[str, Any]],
    ) -> None:
        """Property: SystemConfig принимает любые валидные вложенные конфигурации."""
        validator = PydanticValidator(schema=SystemConfig)
        data = {
            "version": "1.0.0",
            "environment": "production",
            "risk": risk_data,
            "exchanges": exchange_data,
            "strategies": strategy_data,
            "system": {},
        }

        result = validator.validate(data)

        assert isinstance(result, SystemConfig)
        assert result.version == "1.0.0"
        assert isinstance(result.risk, RiskConfig)
        assert isinstance(result.exchanges, list)
        assert isinstance(result.strategies, list)


class TestValidatorInvariants:
    """Тесты инвариантов валидаторов."""

    def test_risk_config_invariant_soft_less_than_hard(self) -> None:
        """
        Инвариант: max_drawdown_soft всегда должен быть меньше max_drawdown_hard.

        Проверяем что Pydantic валидатор корректно отклоняет нарушения инварианта.
        """
        validator = PydanticValidator(schema=RiskConfig)

        # Невалидные данные - мягкий больше или равен жесткому
        invalid_data = {
            "base_r_percent": "0.01",
            "max_r_per_trade": "0.05",
            "max_drawdown_hard": "0.20",
            "max_drawdown_soft": "0.25",  # Больше чем hard!
            "correlation_limit": "0.7",
        }

        with pytest.raises(ValidationError) as exc_info:
            validator.validate(invalid_data)

        assert "мягкий" in str(exc_info.value).lower()

    def test_strategy_config_invariant_risk_bounds(self) -> None:
        """
        Инвариант: max_risk_r всегда должен быть в пределах [0.01, 0.10].
        """
        validator = PydanticValidator(schema=StrategyConfig)

        # Значения за пределами допустимого диапазона
        invalid_values = ["0.005", "0.001", "0.15", "0.50", "1.0"]

        for value in invalid_values:
            data = {
                "name": "sma_cross",
                "enabled": True,
                "max_risk_r": value,
                "params": {},
                "exchanges": ["bybit"],
                "symbols": ["BTC/USDT"],
            }

            with pytest.raises(ValidationError):
                validator.validate(data)

    def test_system_config_invariant_no_extra_fields(self) -> None:
        """
        Инвариант: SystemConfig запрещает extra поля.
        """
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
            "extra_forbidden_field": "not allowed",
        }

        with pytest.raises(ValidationError) as exc_info:
            validator.validate(data)

        assert "extra" in str(exc_info.value).lower() or "unknown" in str(exc_info.value).lower()

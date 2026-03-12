"""
Pydantic модели для конфигурации системы CRYPTOTEHNOLOG.

Модели:
- RiskConfig: конфигурация управления рисками
- ExchangeConfig: конфигурация биржи
- StrategyConfig: конфигурация торговой стратегии
- SystemConfig: корневая конфигурация системы

Все docstrings и комментарии на русском языке.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, field_validator


class RiskConfig(BaseModel):
    """
    Конфигурация управления рисками.

    Атрибуты:
        base_r_percent: Базовый риск на сделку (0.1% - 5%)
        max_r_per_trade: Максимальный риск на одну сделку
        max_drawdown_hard: Жесткий лимит просадки (5% - 50%)
        max_drawdown_soft: Мягкий лимит просадки (предупреждение)
        correlation_limit: Лимит корреляции между позициями
    """

    base_r_percent: Decimal = Field(
        ge=Decimal("0.001"),
        le=Decimal("0.05"),
        description="Базовый риск на сделку (0.1% - 5%)",
    )

    max_r_per_trade: Decimal = Field(
        ge=Decimal("0.005"),
        le=Decimal("0.10"),
        description="Максимальный риск на одну сделку",
    )

    max_drawdown_hard: Decimal = Field(
        ge=Decimal("0.05"),
        le=Decimal("0.50"),
        description="Жесткий лимит просадки (5% - 50%)",
    )

    max_drawdown_soft: Decimal = Field(
        ge=Decimal("0.03"),
        le=Decimal("0.30"),
        description="Мягкий лимит просадки (предупреждение)",
    )

    correlation_limit: Decimal = Field(
        ge=Decimal("0.5"),
        le=Decimal("1.0"),
        description="Лимит корреляции между позициями",
    )

    @field_validator("max_drawdown_soft")
    @classmethod
    def validate_soft_less_than_hard(cls, v: Decimal, info: Any) -> Decimal:
        """
        Проверить что мягкий лимит меньше жесткого.

        Raises:
            ValueError: Если мягкий лимит >= жесткий
        """
        # Этот валидатор вызывается после max_drawdown_hard
        # Используем info.data для доступа к другим полям
        if "max_drawdown_hard" in info.data and v >= info.data["max_drawdown_hard"]:
            raise ValueError("Мягкий лимит просадки должен быть меньше жесткого")
        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "base_r_percent": "0.01",
                    "max_r_per_trade": "0.05",
                    "max_drawdown_hard": "0.20",
                    "max_drawdown_soft": "0.10",
                    "correlation_limit": "0.7",
                }
            ]
        }
    }


class ExchangeConfig(BaseModel):
    """
    Конфигурация биржи.

    Атрибуты:
        name: Имя биржи (bybit, okx, binance)
        enabled: Включена ли биржа
        api_key: API ключ (хранится в Infisical)
        api_secret: API secret (хранится в Infisical)
        rate_limits: Rate limits для биржи
        testnet: Использовать testnet
    """

    name: str = Field(description="Имя биржи (bybit, okx, binance)")
    enabled: bool = Field(description="Включена ли биржа")
    api_key: str = Field(default="", description="API ключ (из Infisical)")
    api_secret: str = Field(default="", description="API secret (из Infisical)")

    rate_limits: dict[str, int] = Field(
        default_factory=dict,
        description="Rate limits: {'orders_per_second': 10, 'requests_per_minute': 1200}",
    )

    testnet: bool = Field(default=False, description="Использовать testnet")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "bybit",
                    "enabled": True,
                    "api_key": "",
                    "api_secret": "",
                    "rate_limits": {"orders_per_second": 10, "requests_per_minute": 1200},
                    "testnet": False,
                }
            ]
        }
    }


class StrategyConfig(BaseModel):
    """
    Конфигурация торговой стратегии.

    Атрибуты:
        name: Имя стратегии
        enabled: Включена ли стратегия
        max_risk_r: Максимальный риск в R
        params: Параметры специфичные для стратегии
        exchanges: На каких биржах запускать
        symbols: Торговые пары
    """

    name: str = Field(description="Имя стратегии")
    enabled: bool = Field(description="Включена ли стратегия")
    max_risk_r: Decimal = Field(ge=Decimal("0.01"), le=Decimal("0.10"))
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Параметры специфичные для стратегии",
    )

    exchanges: list[str] = Field(description="На каких биржах запускать")
    symbols: list[str] = Field(description="Торговые пары")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "sma_cross",
                    "enabled": True,
                    "max_risk_r": "0.02",
                    "params": {"fast_period": 10, "slow_period": 50},
                    "exchanges": ["bybit"],
                    "symbols": ["BTC/USDT", "ETH/USDT"],
                }
            ]
        }
    }


class SystemConfig(BaseModel):
    """
    Корневая конфигурация системы.

    Атрибуты:
        version: Версия конфигурации (semver)
        environment: Окружение (dev, staging, production)
        risk: Конфигурация рисков
        exchanges: Список бирж
        strategies: Список стратегий
        system: Системные настройки
    """

    version: str = Field(description="Версия конфигурации (semver)")
    environment: str = Field(description="dev, staging, production")

    risk: RiskConfig
    exchanges: list[ExchangeConfig]
    strategies: list[StrategyConfig]

    system: dict[str, Any] = Field(
        default_factory=dict,
        description="Системные настройки",
    )

    model_config = {
        # Запретить лишние поля
        "extra": "forbid",
        "json_schema_extra": {
            "examples": [
                {
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
                }
            ]
        },
    }

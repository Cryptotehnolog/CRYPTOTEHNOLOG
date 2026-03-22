"""
Typed contracts shared analysis truth для corrective line C_7R.

Здесь живут только derived inputs, которые:
- не являются raw market-data truth;
- не принадлежат risk layer;
- не превращают DERYA-first Phase 7 в широкую indicator runtime line.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime
    from decimal import Decimal

    from cryptotechnolog.market_data import MarketDataTimeframe


class DerivedInputStatus(StrEnum):
    """Состояние готовности derived analysis input."""

    VALID = "valid"
    WARMING = "warming"
    INVALID = "invalid"


@dataclass(slots=True, frozen=True)
class DerivedInputValidity:
    """Typed semantics готовности derived analysis input."""

    status: DerivedInputStatus
    observed_bars: int
    required_bars: int
    invalid_reason: str | None = None

    @property
    def is_valid(self) -> bool:
        """Проверить, готов ли input к использованию consumers."""
        return self.status == DerivedInputStatus.VALID

    @property
    def is_warming(self) -> bool:
        """Проверить, находится ли input в warming-state."""
        return self.status == DerivedInputStatus.WARMING

    @property
    def bars_remaining(self) -> int:
        """Вернуть количество недостающих баров до valid-state."""
        return max(self.required_bars - self.observed_bars, 0)


@dataclass(slots=True, frozen=True)
class AtrSnapshot:
    """Shared analysis snapshot Average True Range."""

    symbol: str
    exchange: str
    timeframe: MarketDataTimeframe
    updated_at: datetime
    period: int
    value: Decimal | None
    validity: DerivedInputValidity
    smoothing_method: str = "wilder_rma"
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class AdxSnapshot:
    """Shared analysis snapshot Average Directional Index."""

    symbol: str
    exchange: str
    timeframe: MarketDataTimeframe
    updated_at: datetime
    period: int
    value: Decimal | None
    validity: DerivedInputValidity
    smoothing_method: str = "wilder_rma"
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class RiskDerivedInputsSnapshot:
    """
    Shared derived inputs для active risk contour.

    Этот контракт intentionally содержит только analysis-derived truth,
    которая затем может быть объединена с raw market-data в отдельном
    risk-specific publisher следующего шага.
    """

    symbol: str
    exchange: str
    timeframe: MarketDataTimeframe
    updated_at: datetime
    atr: AtrSnapshot
    adx: AdxSnapshot
    source_layer: str = "shared_analysis"
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def is_fully_ready(self) -> bool:
        """Проверить, готовы ли оба derived input для active risk contour."""
        return self.atr.validity.is_valid and self.adx.validity.is_valid


__all__ = [
    "AdxSnapshot",
    "AtrSnapshot",
    "DerivedInputStatus",
    "DerivedInputValidity",
    "RiskDerivedInputsSnapshot",
]

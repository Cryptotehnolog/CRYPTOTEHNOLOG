"""
Tick normalization и базовая quality-aware обработка.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .data_quality import DataQualityValidator, MarketDataValidationError, ensure_utc_timestamp
from .models import DataQualitySignal, MarketDataSide, TickContract

if TYPE_CHECKING:
    from datetime import datetime
    from decimal import Decimal


@dataclass(slots=True, frozen=True)
class TickProcessingResult:
    """Результат обработки одного нормализованного tick."""

    tick: TickContract
    quality_signals: tuple[DataQualitySignal, ...]


class TickHandler:
    """Foundation-компонент для нормализации и quality-aware обработки tick."""

    def __init__(self, quality_validator: DataQualityValidator | None = None) -> None:
        self._quality_validator = quality_validator or DataQualityValidator()

    @property
    def quality_validator(self) -> DataQualityValidator:
        """Доступ к validator для дальнейшего orchestration-слоя."""
        return self._quality_validator

    def normalize_tick(
        self,
        *,
        symbol: str,
        exchange: str,
        price: Decimal,
        quantity: Decimal,
        side: MarketDataSide | str,
        timestamp: datetime,
        trade_id: str,
        is_buyer_maker: bool = False,
    ) -> TickContract:
        """Нормализовать внешний tick-input в typed TickContract."""
        if not symbol:
            raise MarketDataValidationError("Tick должен содержать symbol")
        if not exchange:
            raise MarketDataValidationError("Tick должен содержать exchange")
        if not trade_id:
            raise MarketDataValidationError("Tick должен содержать trade_id")
        if price <= 0:
            raise MarketDataValidationError("Tick price должен быть положительным")
        if quantity <= 0:
            raise MarketDataValidationError("Tick quantity должен быть положительным")

        normalized_side = side if isinstance(side, MarketDataSide) else MarketDataSide(side.lower())
        normalized_timestamp = ensure_utc_timestamp(timestamp)
        return TickContract(
            symbol=symbol,
            exchange=exchange,
            price=price,
            quantity=quantity,
            side=normalized_side,
            timestamp=normalized_timestamp,
            trade_id=trade_id,
            is_buyer_maker=is_buyer_maker,
        )

    def process_tick(self, tick: TickContract, *, now: datetime | None = None) -> TickProcessingResult:
        """Обработать tick через quality foundation."""
        signals = self._quality_validator.validate_tick(tick, now=now)
        return TickProcessingResult(tick=tick, quality_signals=signals)

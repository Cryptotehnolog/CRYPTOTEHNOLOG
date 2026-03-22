"""
L2 foundation для orderbook snapshots и incremental updates.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from .data_quality import DataQualityValidator
from .models import DataQualitySignal, OrderBookLevel, OrderBookSnapshotContract

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(slots=True, frozen=True)
class OrderBookUpdateResult:
    """Результат snapshot/delta обновления orderbook."""

    snapshot: OrderBookSnapshotContract
    quality_signals: tuple[DataQualitySignal, ...]


class OrderBookManager:
    """L2 orderbook foundation с поддержкой snapshot и delta обновлений."""

    def __init__(
        self,
        *,
        max_levels: int = 20,
        quality_validator: DataQualityValidator | None = None,
    ) -> None:
        self._max_levels = max_levels
        self._quality_validator = quality_validator or DataQualityValidator()
        self._books: dict[tuple[str, str], OrderBookSnapshotContract] = {}

    def apply_snapshot(
        self,
        *,
        symbol: str,
        exchange: str,
        timestamp: datetime,
        bids: tuple[OrderBookLevel, ...],
        asks: tuple[OrderBookLevel, ...],
        checksum: str | None = None,
    ) -> OrderBookUpdateResult:
        """Установить новый snapshot стакана."""
        snapshot = self._build_snapshot(
            symbol=symbol,
            exchange=exchange,
            timestamp=timestamp,
            bids=bids,
            asks=asks,
            checksum=checksum,
        )
        self._books[(symbol, exchange)] = snapshot
        signals = self._quality_validator.validate_orderbook(snapshot)
        return OrderBookUpdateResult(snapshot=snapshot, quality_signals=signals)

    def apply_delta(
        self,
        *,
        symbol: str,
        exchange: str,
        timestamp: datetime,
        bid_updates: tuple[OrderBookLevel, ...] = (),
        ask_updates: tuple[OrderBookLevel, ...] = (),
        checksum: str | None = None,
    ) -> OrderBookUpdateResult:
        """Применить incremental update к уже существующему snapshot."""
        existing = self._books.get((symbol, exchange))
        if existing is None:
            raise ValueError("Нельзя применить delta без исходного snapshot стакана")

        merged_bids = self._merge_side(existing.bids, bid_updates, reverse=True)
        merged_asks = self._merge_side(existing.asks, ask_updates, reverse=False)
        snapshot = self._build_snapshot(
            symbol=symbol,
            exchange=exchange,
            timestamp=timestamp,
            bids=merged_bids,
            asks=merged_asks,
            checksum=checksum,
        )
        self._books[(symbol, exchange)] = snapshot
        signals = self._quality_validator.validate_orderbook(snapshot)
        return OrderBookUpdateResult(snapshot=snapshot, quality_signals=signals)

    def get_snapshot(self, symbol: str, exchange: str) -> OrderBookSnapshotContract | None:
        """Вернуть текущий snapshot стакана."""
        return self._books.get((symbol, exchange))

    def _build_snapshot(
        self,
        *,
        symbol: str,
        exchange: str,
        timestamp: datetime,
        bids: tuple[OrderBookLevel, ...],
        asks: tuple[OrderBookLevel, ...],
        checksum: str | None,
    ) -> OrderBookSnapshotContract:
        normalized_bids = self._normalize_side(bids, reverse=True)
        normalized_asks = self._normalize_side(asks, reverse=False)
        spread_bps = self._calculate_spread_bps(normalized_bids, normalized_asks)
        return OrderBookSnapshotContract(
            symbol=symbol,
            exchange=exchange,
            timestamp=timestamp,
            bids=normalized_bids,
            asks=normalized_asks,
            spread_bps=spread_bps,
            checksum=checksum,
        )

    def _normalize_side(
        self,
        levels: tuple[OrderBookLevel, ...],
        *,
        reverse: bool,
    ) -> tuple[OrderBookLevel, ...]:
        filtered = [level for level in levels if level.quantity > 0]
        sorted_levels = sorted(filtered, key=lambda item: item.price, reverse=reverse)
        return tuple(sorted_levels[: self._max_levels])

    def _merge_side(
        self,
        current_levels: tuple[OrderBookLevel, ...],
        updates: tuple[OrderBookLevel, ...],
        *,
        reverse: bool,
    ) -> tuple[OrderBookLevel, ...]:
        merged: dict[Decimal, OrderBookLevel] = {level.price: level for level in current_levels}
        for update in updates:
            if update.quantity <= 0:
                merged.pop(update.price, None)
            else:
                merged[update.price] = update
        return self._normalize_side(tuple(merged.values()), reverse=reverse)

    def _calculate_spread_bps(
        self,
        bids: tuple[OrderBookLevel, ...],
        asks: tuple[OrderBookLevel, ...],
    ) -> Decimal:
        if not bids or not asks:
            return Decimal("0")
        best_bid = bids[0].price
        best_ask = asks[0].price
        midpoint = (best_bid + best_ask) / Decimal("2")
        if midpoint <= 0:
            return Decimal("0")
        return ((best_ask - best_bid) / midpoint) * Decimal("10000")

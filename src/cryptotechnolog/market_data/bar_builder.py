"""
Инкрементальный builder свечей поверх typed tick contracts.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from .models import (
    DataQualitySignal,
    MarketDataSide,
    MarketDataTimeframe,
    OHLCVBarContract,
    TickContract,
)


def timeframe_to_timedelta(timeframe: MarketDataTimeframe) -> timedelta:
    """Преобразовать timeframe contract в timedelta."""
    mapping = {
        MarketDataTimeframe.M1: timedelta(minutes=1),
        MarketDataTimeframe.M5: timedelta(minutes=5),
        MarketDataTimeframe.M15: timedelta(minutes=15),
        MarketDataTimeframe.H1: timedelta(hours=1),
        MarketDataTimeframe.H4: timedelta(hours=4),
        MarketDataTimeframe.D1: timedelta(days=1),
    }
    return mapping[timeframe]


def align_timestamp_to_timeframe(timestamp: datetime, timeframe: MarketDataTimeframe) -> datetime:
    """Округлить timestamp вниз до границы выбранного timeframe."""
    aligned = timestamp.astimezone(UTC)
    if timeframe == MarketDataTimeframe.D1:
        return aligned.replace(hour=0, minute=0, second=0, microsecond=0)
    if timeframe == MarketDataTimeframe.H4:
        hour = (aligned.hour // 4) * 4
        return aligned.replace(hour=hour, minute=0, second=0, microsecond=0)
    if timeframe == MarketDataTimeframe.H1:
        return aligned.replace(minute=0, second=0, microsecond=0)

    minutes = {"1m": 1, "5m": 5, "15m": 15}[timeframe.value]
    minute = (aligned.minute // minutes) * minutes
    return aligned.replace(minute=minute, second=0, microsecond=0)


@dataclass(slots=True, frozen=True)
class BarUpdateResult:
    """Результат обработки tick внутри BarBuilder."""

    active_bar: OHLCVBarContract
    completed_bar: OHLCVBarContract | None
    quality_signals: tuple[DataQualitySignal, ...] = ()


class BarBuilder:
    """O(1)-builder свечей для одного timeframe."""

    def __init__(self, timeframe: MarketDataTimeframe) -> None:
        self._timeframe = timeframe
        self._duration = timeframe_to_timedelta(timeframe)
        self._active_bars: dict[tuple[str, str], OHLCVBarContract] = {}

    @property
    def timeframe(self) -> MarketDataTimeframe:
        """Вернуть timeframe текущего builder."""
        return self._timeframe

    def ingest_tick(self, tick: TickContract) -> BarUpdateResult:
        """Обновить активный бар по новому tick и вернуть completed bar при rollover."""
        key = (tick.symbol, tick.exchange)
        bar_open_time = align_timestamp_to_timeframe(tick.timestamp, self._timeframe)
        bar_close_time = bar_open_time + self._duration
        existing_bar = self._active_bars.get(key)

        if existing_bar is None:
            active_bar = self._build_new_bar(tick, bar_open_time, bar_close_time)
            self._active_bars[key] = active_bar
            return BarUpdateResult(active_bar=active_bar, completed_bar=None)

        if existing_bar.open_time == bar_open_time:
            updated_bar = self._merge_tick_into_bar(existing_bar, tick)
            self._active_bars[key] = updated_bar
            return BarUpdateResult(active_bar=updated_bar, completed_bar=None)

        gap_affected = (bar_open_time - existing_bar.open_time) > self._duration
        completed_bar = OHLCVBarContract(
            symbol=existing_bar.symbol,
            exchange=existing_bar.exchange,
            timeframe=existing_bar.timeframe,
            open_time=existing_bar.open_time,
            close_time=existing_bar.close_time,
            open=existing_bar.open,
            high=existing_bar.high,
            low=existing_bar.low,
            close=existing_bar.close,
            volume=existing_bar.volume,
            bid_volume=existing_bar.bid_volume,
            ask_volume=existing_bar.ask_volume,
            trades_count=existing_bar.trades_count,
            is_closed=True,
            is_gap_affected=existing_bar.is_gap_affected or gap_affected,
        )
        next_bar = self._build_new_bar(
            tick, bar_open_time, bar_close_time, is_gap_affected=gap_affected
        )
        self._active_bars[key] = next_bar
        return BarUpdateResult(active_bar=next_bar, completed_bar=completed_bar)

    def flush(self, symbol: str, exchange: str) -> OHLCVBarContract | None:
        """Закрыть текущий активный бар по symbol/exchange."""
        active_bar = self._active_bars.pop((symbol, exchange), None)
        if active_bar is None:
            return None
        return OHLCVBarContract(
            symbol=active_bar.symbol,
            exchange=active_bar.exchange,
            timeframe=active_bar.timeframe,
            open_time=active_bar.open_time,
            close_time=active_bar.close_time,
            open=active_bar.open,
            high=active_bar.high,
            low=active_bar.low,
            close=active_bar.close,
            volume=active_bar.volume,
            bid_volume=active_bar.bid_volume,
            ask_volume=active_bar.ask_volume,
            trades_count=active_bar.trades_count,
            is_closed=True,
            is_gap_affected=active_bar.is_gap_affected,
        )

    def _build_new_bar(
        self,
        tick: TickContract,
        open_time: datetime,
        close_time: datetime,
        *,
        is_gap_affected: bool = False,
    ) -> OHLCVBarContract:
        bid_volume, ask_volume = self._extract_aggressor_volumes(tick)
        return OHLCVBarContract(
            symbol=tick.symbol,
            exchange=tick.exchange,
            timeframe=self._timeframe,
            open_time=open_time,
            close_time=close_time,
            open=tick.price,
            high=tick.price,
            low=tick.price,
            close=tick.price,
            volume=tick.quantity,
            bid_volume=bid_volume,
            ask_volume=ask_volume,
            trades_count=1,
            is_closed=False,
            is_gap_affected=is_gap_affected,
        )

    def _merge_tick_into_bar(self, bar: OHLCVBarContract, tick: TickContract) -> OHLCVBarContract:
        bid_volume, ask_volume = self._extract_aggressor_volumes(tick)
        return OHLCVBarContract(
            symbol=bar.symbol,
            exchange=bar.exchange,
            timeframe=bar.timeframe,
            open_time=bar.open_time,
            close_time=bar.close_time,
            open=bar.open,
            high=max(bar.high, tick.price),
            low=min(bar.low, tick.price),
            close=tick.price,
            volume=bar.volume + tick.quantity,
            bid_volume=bar.bid_volume + bid_volume,
            ask_volume=bar.ask_volume + ask_volume,
            trades_count=bar.trades_count + 1,
            is_closed=False,
            is_gap_affected=bar.is_gap_affected,
        )

    def _extract_aggressor_volumes(self, tick: TickContract) -> tuple[Decimal, Decimal]:
        if tick.is_buyer_maker or tick.side == MarketDataSide.SELL:
            return tick.quantity, Decimal("0")
        return Decimal("0"), tick.quantity

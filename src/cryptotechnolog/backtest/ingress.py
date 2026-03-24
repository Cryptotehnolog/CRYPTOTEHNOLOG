"""
Historical input ingress foundation для Phase 20 Backtesting / Replay Foundation.

Этот модуль intentionally фиксирует только первый minimal ingress path:
- authoritative first ingress path = BAR_STREAM;
- explicit CSV/DataFrame ingestion discipline;
- deterministic normalization pipeline;
- narrow inventory truth вокруг загруженных historical inputs.

Модуль не реализует:
- full historical data platform;
- analytics / reporting outputs;
- optimization / comparison semantics;
- dashboard/operator surface.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING

import pandas as pd

from cryptotechnolog.market_data import MarketDataTimeframe

from .models import HistoricalInputContract, HistoricalInputKind, ReplayCoverageWindow

if TYPE_CHECKING:
    from pathlib import Path

    from pandas import DataFrame

    from .runtime import ReplayRuntime, ReplayRuntimeUpdate


type ReplayIngressStateKey = tuple[str, str, str]


class ReplayIngressPath(StrEnum):
    """Поддерживаемые ingress paths для replay foundation."""

    BAR_STREAM = "bar_stream"


class BarStreamIngressFormat(StrEnum):
    """Authoritative input format для первого ingress path."""

    CSV = "csv"
    DATAFRAME = "dataframe"


@dataclass(slots=True, frozen=True)
class BarStreamRecord:
    """Нормализованная bar record truth для первого replay ingress path."""

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    def __post_init__(self) -> None:
        if self.high < max(self.open, self.close, self.low):
            raise ValueError("high не может быть меньше OHLC границ")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError("low не может быть больше OHLC границ")
        if self.volume < 0:
            raise ValueError("volume не может быть отрицательным")


@dataclass(slots=True, frozen=True)
class HistoricalInputInventoryEntry:
    """Минимальная inventory truth для загруженного replay input."""

    input_id: str
    input_name: str
    symbol: str
    exchange: str
    timeframe: str
    ingress_path: ReplayIngressPath
    input_format: BarStreamIngressFormat
    source_reference: str | None
    coverage_start_at: datetime
    coverage_end_at: datetime
    observed_events: int
    expected_events: int

    @property
    def state_key(self) -> ReplayIngressStateKey:
        return (self.symbol, self.exchange, self.timeframe)


@dataclass(slots=True, frozen=True)
class LoadedHistoricalBarStream:
    """Нормализованный BAR_STREAM ingress result."""

    historical_input: HistoricalInputContract
    bars: tuple[BarStreamRecord, ...]
    inventory_entry: HistoricalInputInventoryEntry

    @property
    def state_key(self) -> ReplayIngressStateKey:
        return self.inventory_entry.state_key


@dataclass(slots=True, frozen=True)
class IntegratedReplayIngressResult:
    """Typed result для узкого ingress -> runtime integrated path."""

    loaded_stream: LoadedHistoricalBarStream
    runtime_update: ReplayRuntimeUpdate

    @property
    def state_key(self) -> ReplayIngressStateKey:
        return self.loaded_stream.state_key


@dataclass(slots=True, frozen=True)
class BarStreamCsvIngressConfig:
    """Минимальная конфигурация authoritative CSV BAR_STREAM loader."""

    input_name: str
    symbol: str
    exchange: str
    timeframe: MarketDataTimeframe
    source_path: str | Path
    timestamp_column: str = "timestamp"
    open_column: str = "open"
    high_column: str = "high"
    low_column: str = "low"
    close_column: str = "close"
    volume_column: str = "volume"


class HistoricalInputIngress:
    """Узкий ingress/tooling contour для первого replay input path."""

    def __init__(self) -> None:
        self._inventory: dict[ReplayIngressStateKey, HistoricalInputInventoryEntry] = {}

    def load_csv(self, config: BarStreamCsvIngressConfig) -> LoadedHistoricalBarStream:
        """Загрузить authoritative BAR_STREAM из CSV."""
        dataframe = pd.read_csv(
            config.source_path,
            parse_dates=[config.timestamp_column],
        )
        return self.load_dataframe(
            dataframe,
            input_name=config.input_name,
            symbol=config.symbol,
            exchange=config.exchange,
            timeframe=config.timeframe,
            source_reference=str(config.source_path),
            input_format=BarStreamIngressFormat.CSV,
            timestamp_column=config.timestamp_column,
            open_column=config.open_column,
            high_column=config.high_column,
            low_column=config.low_column,
            close_column=config.close_column,
            volume_column=config.volume_column,
        )

    def load_dataframe(
        self,
        dataframe: DataFrame,
        *,
        input_name: str,
        symbol: str,
        exchange: str,
        timeframe: MarketDataTimeframe,
        source_reference: str | None = None,
        input_format: BarStreamIngressFormat = BarStreamIngressFormat.DATAFRAME,
        timestamp_column: str = "timestamp",
        open_column: str = "open",
        high_column: str = "high",
        low_column: str = "low",
        close_column: str = "close",
        volume_column: str = "volume",
    ) -> LoadedHistoricalBarStream:
        """Нормализовать DataFrame в authoritative BAR_STREAM truth."""
        normalized = self._normalize_bar_dataframe(
            dataframe,
            timestamp_column=timestamp_column,
            open_column=open_column,
            high_column=high_column,
            low_column=low_column,
            close_column=close_column,
            volume_column=volume_column,
        )
        bars = tuple(
            BarStreamRecord(
                timestamp=row["timestamp"],
                open=row["open"],
                high=row["high"],
                low=row["low"],
                close=row["close"],
                volume=row["volume"],
            )
            for row in normalized.to_dict(orient="records")
        )
        if not bars:
            raise ValueError("BAR_STREAM ingress требует хотя бы один bar")

        coverage_window = ReplayCoverageWindow(
            start_at=bars[0].timestamp,
            end_at=bars[-1].timestamp,
            observed_events=len(bars),
            expected_events=self._expected_events(
                start_at=bars[0].timestamp,
                end_at=bars[-1].timestamp,
                timeframe=timeframe,
            ),
        )
        historical_input = HistoricalInputContract.candidate(
            input_name=input_name,
            symbol=symbol,
            exchange=exchange,
            kind=HistoricalInputKind.BAR_STREAM,
            timeframe=timeframe,
            coverage_window=coverage_window,
            source_reference=source_reference,
            metadata={"normalized_bar_count": len(bars)},
        )
        inventory_entry = HistoricalInputInventoryEntry(
            input_id=str(historical_input.input_id),
            input_name=historical_input.input_name,
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe.value,
            ingress_path=ReplayIngressPath.BAR_STREAM,
            input_format=input_format,
            source_reference=source_reference,
            coverage_start_at=coverage_window.start_at,
            coverage_end_at=coverage_window.end_at,
            observed_events=coverage_window.observed_events,
            expected_events=coverage_window.expected_events,
        )
        self._inventory[inventory_entry.state_key] = inventory_entry
        return LoadedHistoricalBarStream(
            historical_input=historical_input,
            bars=bars,
            inventory_entry=inventory_entry,
        )

    def load_csv_into_runtime(
        self,
        config: BarStreamCsvIngressConfig,
        *,
        runtime: ReplayRuntime,
        reference_time: datetime,
    ) -> IntegratedReplayIngressResult:
        """Загрузить BAR_STREAM из CSV и сразу ingest-ить его в ReplayRuntime."""
        loaded = self.load_csv(config)
        runtime_update = runtime.ingest_historical_input(
            historical_input=loaded.historical_input,
            reference_time=reference_time,
        )
        return IntegratedReplayIngressResult(
            loaded_stream=loaded,
            runtime_update=runtime_update,
        )

    def load_dataframe_into_runtime(
        self,
        dataframe: DataFrame,
        *,
        runtime: ReplayRuntime,
        reference_time: datetime,
        input_name: str,
        symbol: str,
        exchange: str,
        timeframe: MarketDataTimeframe,
        source_reference: str | None = None,
        timestamp_column: str = "timestamp",
        open_column: str = "open",
        high_column: str = "high",
        low_column: str = "low",
        close_column: str = "close",
        volume_column: str = "volume",
    ) -> IntegratedReplayIngressResult:
        """Нормализовать BAR_STREAM DataFrame и ingest-ить его в ReplayRuntime."""
        loaded = self.load_dataframe(
            dataframe,
            input_name=input_name,
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
            source_reference=source_reference,
            timestamp_column=timestamp_column,
            open_column=open_column,
            high_column=high_column,
            low_column=low_column,
            close_column=close_column,
            volume_column=volume_column,
        )
        runtime_update = runtime.ingest_historical_input(
            historical_input=loaded.historical_input,
            reference_time=reference_time,
        )
        return IntegratedReplayIngressResult(
            loaded_stream=loaded,
            runtime_update=runtime_update,
        )

    def get_inventory_entry(
        self,
        key: ReplayIngressStateKey,
    ) -> HistoricalInputInventoryEntry | None:
        """Вернуть inventory entry по canonical state key."""
        return self._inventory.get(key)

    def list_inventory(self) -> tuple[HistoricalInputInventoryEntry, ...]:
        """Вернуть всю текущую inventory truth."""
        return tuple(self._inventory.values())

    @staticmethod
    def _normalize_bar_dataframe(
        dataframe: DataFrame,
        *,
        timestamp_column: str,
        open_column: str,
        high_column: str,
        low_column: str,
        close_column: str,
        volume_column: str,
    ) -> DataFrame:
        required = {
            timestamp_column,
            open_column,
            high_column,
            low_column,
            close_column,
            volume_column,
        }
        missing = required - set(dataframe.columns)
        if missing:
            raise ValueError(f"BAR_STREAM ingress missing required columns: {sorted(missing)}")

        renamed = dataframe.rename(
            columns={
                timestamp_column: "timestamp",
                open_column: "open",
                high_column: "high",
                low_column: "low",
                close_column: "close",
                volume_column: "volume",
            }
        ).copy()
        renamed["timestamp"] = pd.to_datetime(renamed["timestamp"], utc=True, errors="raise")
        renamed = renamed.sort_values("timestamp").reset_index(drop=True)
        if renamed["timestamp"].duplicated().any():
            raise ValueError("BAR_STREAM ingress не допускает duplicate timestamps")

        for column in ("open", "high", "low", "close", "volume"):
            renamed[column] = renamed[column].astype("float64")

        return renamed[["timestamp", "open", "high", "low", "close", "volume"]]

    @staticmethod
    def _expected_events(
        *,
        start_at: datetime,
        end_at: datetime,
        timeframe: MarketDataTimeframe,
    ) -> int:
        step = {
            MarketDataTimeframe.M1: timedelta(minutes=1),
            MarketDataTimeframe.M5: timedelta(minutes=5),
            MarketDataTimeframe.M15: timedelta(minutes=15),
            MarketDataTimeframe.H1: timedelta(hours=1),
            MarketDataTimeframe.H4: timedelta(hours=4),
            MarketDataTimeframe.D1: timedelta(days=1),
        }[timeframe]
        start = start_at.astimezone(UTC)
        end = end_at.astimezone(UTC)
        return int((end - start) / step) + 1


__all__ = [
    "BarStreamCsvIngressConfig",
    "BarStreamIngressFormat",
    "BarStreamRecord",
    "HistoricalInputIngress",
    "HistoricalInputInventoryEntry",
    "IntegratedReplayIngressResult",
    "LoadedHistoricalBarStream",
    "ReplayIngressPath",
    "ReplayIngressStateKey",
]

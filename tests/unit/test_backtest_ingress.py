from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pandas as pd
import pytest

from cryptotechnolog.backtest import (
    BarStreamCsvIngressConfig,
    BarStreamIngressFormat,
    HistoricalInputIngress,
    HistoricalInputKind,
    ReplayDecision,
    ReplayIngressPath,
    ReplayRuntimeLifecycleState,
    ReplayStatus,
    ReplayValidityStatus,
    create_replay_runtime,
)
from cryptotechnolog.market_data import MarketDataTimeframe

if TYPE_CHECKING:
    from pathlib import Path


def _bars_dataframe() -> pd.DataFrame:
    return pd.DataFrame({
        "timestamp": [
            datetime(2026, 3, 24, 10, 2, tzinfo=UTC),
            datetime(2026, 3, 24, 10, 0, tzinfo=UTC),
            datetime(2026, 3, 24, 10, 1, tzinfo=UTC),
        ],
        "open": [102.0, 100.0, 101.0],
        "high": [103.0, 101.0, 102.0],
        "low": [101.0, 99.0, 100.0],
        "close": [102.5, 100.5, 101.5],
        "volume": [12.0, 10.0, 11.0],
    })


def test_historical_input_ingress_normalizes_bar_stream_dataframe() -> None:
    ingress = HistoricalInputIngress()

    loaded = ingress.load_dataframe(
        _bars_dataframe(),
        input_name="btcusdt_m1_bar_window",
        symbol="BTCUSDT",
        exchange="BINANCE",
        timeframe=MarketDataTimeframe.M1,
        source_reference="fixtures/bars.csv",
    )

    assert loaded.historical_input.kind == HistoricalInputKind.BAR_STREAM
    assert loaded.historical_input.timeframe == MarketDataTimeframe.M1
    assert tuple(bar.timestamp for bar in loaded.bars) == (
        datetime(2026, 3, 24, 10, 0, tzinfo=UTC),
        datetime(2026, 3, 24, 10, 1, tzinfo=UTC),
        datetime(2026, 3, 24, 10, 2, tzinfo=UTC),
    )
    assert loaded.inventory_entry.ingress_path == ReplayIngressPath.BAR_STREAM
    assert loaded.inventory_entry.input_format == BarStreamIngressFormat.DATAFRAME
    assert loaded.inventory_entry.observed_events == 3
    assert loaded.inventory_entry.expected_events == 3


def test_historical_input_ingress_tracks_inventory_by_state_key() -> None:
    ingress = HistoricalInputIngress()
    loaded = ingress.load_dataframe(
        _bars_dataframe(),
        input_name="btcusdt_m1_bar_window",
        symbol="BTCUSDT",
        exchange="BINANCE",
        timeframe=MarketDataTimeframe.M1,
    )

    key = ("BTCUSDT", "BINANCE", MarketDataTimeframe.M1.value)
    entry = ingress.get_inventory_entry(key)

    assert entry is not None
    assert entry.input_name == loaded.historical_input.input_name
    assert ingress.list_inventory() == (entry,)


def test_historical_input_ingress_rejects_duplicate_timestamps() -> None:
    ingress = HistoricalInputIngress()
    duplicated = _bars_dataframe()
    duplicated.loc[2, "timestamp"] = duplicated.loc[1, "timestamp"]

    with pytest.raises(ValueError, match="duplicate timestamps"):
        ingress.load_dataframe(
            duplicated,
            input_name="btcusdt_m1_bar_window",
            symbol="BTCUSDT",
            exchange="BINANCE",
            timeframe=MarketDataTimeframe.M1,
        )


def test_historical_input_ingress_load_csv_uses_authoritative_csv_format(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ingress = HistoricalInputIngress()
    captured_path: str | Path | None = None

    def _fake_read_csv(path: str | Path, *, parse_dates: list[str]) -> pd.DataFrame:
        nonlocal captured_path
        captured_path = path
        assert parse_dates == ["timestamp"]
        return _bars_dataframe()

    monkeypatch.setattr(pd, "read_csv", _fake_read_csv)

    loaded = ingress.load_csv(
        BarStreamCsvIngressConfig(
            input_name="btcusdt_m1_bar_window",
            symbol="BTCUSDT",
            exchange="BINANCE",
            timeframe=MarketDataTimeframe.M1,
            source_path="fixtures/bars.csv",
        )
    )

    assert captured_path == "fixtures/bars.csv"
    assert loaded.inventory_entry.source_reference == "fixtures/bars.csv"
    assert loaded.inventory_entry.input_format == BarStreamIngressFormat.CSV


@pytest.mark.asyncio
async def test_historical_input_ingress_integrates_dataframe_into_replay_runtime() -> None:
    ingress = HistoricalInputIngress()
    runtime = create_replay_runtime()
    await runtime.start()

    result = ingress.load_dataframe_into_runtime(
        _bars_dataframe(),
        runtime=runtime,
        reference_time=datetime(2026, 3, 24, 10, 3, tzinfo=UTC),
        input_name="btcusdt_m1_bar_window",
        symbol="BTCUSDT",
        exchange="BINANCE",
        timeframe=MarketDataTimeframe.M1,
        source_reference="fixtures/bars.csv",
    )

    assert result.loaded_stream.historical_input.kind == HistoricalInputKind.BAR_STREAM
    assert result.loaded_stream.inventory_entry.input_format == BarStreamIngressFormat.DATAFRAME
    assert result.runtime_update.context is not None
    assert result.runtime_update.replay_candidate is not None
    assert result.runtime_update.replay_candidate.status == ReplayStatus.REPLAYED
    assert result.runtime_update.replay_candidate.decision == ReplayDecision.REPLAY

    state_key = ("BTCUSDT", "BINANCE", MarketDataTimeframe.M1.value)
    assert ingress.get_inventory_entry(state_key) is not None
    assert runtime.get_input(state_key) is not None
    assert runtime.get_context(state_key) is not None
    assert runtime.get_candidate(state_key) is not None
    assert runtime.get_runtime_diagnostics()["lifecycle_state"] == (
        ReplayRuntimeLifecycleState.READY.value
    )


@pytest.mark.asyncio
async def test_historical_input_ingress_integrates_warming_path_into_runtime() -> None:
    ingress = HistoricalInputIngress()
    runtime = create_replay_runtime()
    await runtime.start()

    result = ingress.load_dataframe_into_runtime(
        _bars_dataframe().iloc[:2],
        runtime=runtime,
        reference_time=datetime(2026, 3, 24, 10, 3, tzinfo=UTC),
        input_name="btcusdt_m1_partial_window",
        symbol="BTCUSDT",
        exchange="BINANCE",
        timeframe=MarketDataTimeframe.M1,
    )

    assert result.runtime_update.context is not None
    assert result.runtime_update.context.validity.status == ReplayValidityStatus.WARMING
    assert result.runtime_update.replay_candidate is not None
    assert result.runtime_update.replay_candidate.status == ReplayStatus.CANDIDATE
    assert result.runtime_update.replay_candidate.decision == ReplayDecision.ABSTAIN

    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["ready"] is False
    assert "coverage_window_incomplete" in diagnostics["readiness_reasons"]


@pytest.mark.asyncio
async def test_historical_input_ingress_blocks_lookahead_runtime_path() -> None:
    ingress = HistoricalInputIngress()
    runtime = create_replay_runtime()
    await runtime.start()

    result = ingress.load_dataframe_into_runtime(
        _bars_dataframe(),
        runtime=runtime,
        reference_time=datetime(2026, 3, 24, 10, 1, tzinfo=UTC),
        input_name="btcusdt_m1_bar_window",
        symbol="BTCUSDT",
        exchange="BINANCE",
        timeframe=MarketDataTimeframe.M1,
    )

    assert result.runtime_update.context is not None
    assert result.runtime_update.context.validity.status == ReplayValidityStatus.INVALID
    assert result.runtime_update.context.validity.invalid_reason == (
        "historical_input_lookahead_detected"
    )
    assert result.runtime_update.replay_candidate is not None
    assert result.runtime_update.replay_candidate.status == ReplayStatus.ABSTAINED
    assert result.runtime_update.replay_candidate.decision == ReplayDecision.ABSTAIN

    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["ready"] is False
    assert diagnostics["last_failure_reason"] == "historical_input_lookahead_detected"


@pytest.mark.asyncio
async def test_historical_input_ingress_integrates_csv_into_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ingress = HistoricalInputIngress()
    runtime = create_replay_runtime()
    await runtime.start()

    monkeypatch.setattr(pd, "read_csv", lambda *args, **kwargs: _bars_dataframe())

    result = ingress.load_csv_into_runtime(
        BarStreamCsvIngressConfig(
            input_name="btcusdt_m1_bar_window",
            symbol="BTCUSDT",
            exchange="BINANCE",
            timeframe=MarketDataTimeframe.M1,
            source_path="fixtures/bars.csv",
        ),
        runtime=runtime,
        reference_time=datetime(2026, 3, 24, 10, 3, tzinfo=UTC),
    )

    assert result.loaded_stream.inventory_entry.source_reference == "fixtures/bars.csv"
    assert result.loaded_stream.inventory_entry.input_format == BarStreamIngressFormat.CSV
    assert result.runtime_update.replay_candidate is not None
    assert result.runtime_update.replay_candidate.status == ReplayStatus.REPLAYED

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from cryptotechnolog.analysis import SharedAnalysisRuntime, SharedAnalysisRuntimeConfig
from cryptotechnolog.market_data import MarketDataTimeframe, OHLCVBarContract


def _make_bar(
    *,
    index: int,
    high: str,
    low: str,
    close: str,
    open_: str | None = None,
) -> OHLCVBarContract:
    open_time = datetime(2026, 3, 20, 12, 0, tzinfo=UTC) + timedelta(minutes=index)
    close_time = open_time + timedelta(minutes=1)
    return OHLCVBarContract(
        symbol="BTC/USDT",
        exchange="bybit",
        timeframe=MarketDataTimeframe.M1,
        open_time=open_time,
        close_time=close_time,
        open=Decimal(open_ or close),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=Decimal("10"),
        is_closed=True,
    )


def test_shared_analysis_runtime_requires_explicit_start() -> None:
    runtime = SharedAnalysisRuntime()

    try:
        runtime.ingest_completed_bar(_make_bar(index=0, high="30", low="28", close="29"))
    except RuntimeError as exc:
        assert "SharedAnalysisRuntime не запущен" in str(exc)
    else:
        raise AssertionError("Ожидался RuntimeError до start()")


def test_shared_analysis_runtime_warms_atr_and_adx_without_claiming_full_readiness() -> None:
    runtime = SharedAnalysisRuntime(
        SharedAnalysisRuntimeConfig(
            atr_period=3,
            adx_period=3,
        )
    )

    asyncio.run(runtime.start())
    bars = [
        _make_bar(index=0, high="30", low="28", close="29"),
        _make_bar(index=1, high="32", low="29", close="31"),
        _make_bar(index=2, high="33", low="30", close="32"),
        _make_bar(index=3, high="34", low="31", close="33"),
    ]

    last_update = None
    for bar in bars:
        last_update = runtime.ingest_completed_bar(bar)

    assert last_update is not None
    snapshot = last_update.snapshot
    diagnostics = runtime.get_runtime_diagnostics()

    assert snapshot.atr.value == Decimal("3.0000")
    assert snapshot.atr.validity.is_valid is True
    assert snapshot.adx.value is None
    assert snapshot.adx.validity.is_warming is True
    assert snapshot.is_fully_ready is False
    assert diagnostics["ready"] is False
    assert diagnostics["lifecycle_state"] == "warming"
    assert diagnostics["tracked_keys"] == 1
    assert diagnostics["warming_keys"] == 1


def test_shared_analysis_runtime_reaches_fully_ready_atr_and_adx_state() -> None:
    runtime = SharedAnalysisRuntime(
        SharedAnalysisRuntimeConfig(
            atr_period=3,
            adx_period=3,
        )
    )

    asyncio.run(runtime.start())
    bars = [
        _make_bar(index=0, high="30", low="28", close="29"),
        _make_bar(index=1, high="32", low="29", close="31"),
        _make_bar(index=2, high="33", low="30", close="32"),
        _make_bar(index=3, high="34", low="31", close="33"),
        _make_bar(index=4, high="35", low="32", close="34"),
        _make_bar(index=5, high="34", low="31", close="32"),
    ]

    last_update = None
    for bar in bars:
        last_update = runtime.ingest_completed_bar(bar)

    assert last_update is not None
    snapshot = last_update.snapshot
    diagnostics = runtime.get_runtime_diagnostics()

    assert snapshot.atr.value == Decimal("3.0000")
    assert snapshot.adx.value == Decimal("80.6452")
    assert snapshot.atr.validity.is_valid is True
    assert snapshot.adx.validity.is_valid is True
    assert snapshot.is_fully_ready is True
    assert diagnostics["ready"] is True
    assert diagnostics["lifecycle_state"] == "ready"
    assert diagnostics["ready_keys"] == 1


def test_shared_analysis_runtime_exposes_query_surface_for_risk_derived_inputs() -> None:
    runtime = SharedAnalysisRuntime(
        SharedAnalysisRuntimeConfig(
            atr_period=3,
            adx_period=3,
        )
    )

    asyncio.run(runtime.start())
    for index, (high, low, close) in enumerate(
        (
            ("30", "28", "29"),
            ("32", "29", "31"),
            ("33", "30", "32"),
            ("34", "31", "33"),
            ("35", "32", "34"),
            ("34", "31", "32"),
        )
    ):
        runtime.ingest_completed_bar(_make_bar(index=index, high=high, low=low, close=close))

    snapshot = runtime.get_risk_derived_inputs(
        exchange="bybit",
        symbol="BTC/USDT",
        timeframe=MarketDataTimeframe.M1,
    )
    atr = runtime.get_atr_snapshot(
        exchange="bybit",
        symbol="BTC/USDT",
        timeframe=MarketDataTimeframe.M1,
    )
    adx = runtime.get_adx_snapshot(
        exchange="bybit",
        symbol="BTC/USDT",
        timeframe=MarketDataTimeframe.M1,
    )

    assert snapshot is not None
    assert atr is not None
    assert adx is not None
    assert snapshot.atr == atr
    assert snapshot.adx == adx
    assert snapshot.metadata["atr_required_bars"] == 4
    assert snapshot.metadata["adx_required_bars"] == 6


def test_shared_analysis_runtime_stop_resets_operator_visible_state() -> None:
    runtime = SharedAnalysisRuntime(
        SharedAnalysisRuntimeConfig(
            atr_period=3,
            adx_period=3,
        )
    )

    asyncio.run(runtime.start())
    runtime.ingest_completed_bar(_make_bar(index=0, high="30", low="28", close="29"))
    asyncio.run(runtime.stop())

    diagnostics = runtime.get_runtime_diagnostics()
    snapshot = runtime.get_risk_derived_inputs(
        exchange="bybit",
        symbol="BTC/USDT",
        timeframe=MarketDataTimeframe.M1,
    )

    assert diagnostics["started"] is False
    assert diagnostics["ready"] is False
    assert diagnostics["lifecycle_state"] == "stopped"
    assert diagnostics["tracked_keys"] == 0
    assert diagnostics["ready_keys"] == 0
    assert diagnostics["warming_keys"] == 0
    assert diagnostics["last_bar_at"] is None
    assert diagnostics["last_failure_reason"] is None
    assert diagnostics["readiness_reasons"] == ["runtime_stopped"]
    assert diagnostics["degraded_reasons"] == []
    assert snapshot is None


def test_shared_analysis_runtime_mark_degraded_exposes_failure_truth() -> None:
    runtime = SharedAnalysisRuntime()

    asyncio.run(runtime.start())
    runtime.mark_degraded("bar_ingest_failed:test_failure")

    diagnostics = runtime.get_runtime_diagnostics()

    assert diagnostics["started"] is True
    assert diagnostics["ready"] is False
    assert diagnostics["lifecycle_state"] == "degraded"
    assert diagnostics["last_failure_reason"] == "bar_ingest_failed:test_failure"
    assert diagnostics["degraded_reasons"] == ["bar_ingest_failed:test_failure"]

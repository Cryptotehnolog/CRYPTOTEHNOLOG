from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal

from cryptotechnolog.intelligence import (
    IntelligenceRuntime,
    IntelligenceRuntimeConfig,
)
from cryptotechnolog.market_data import MarketDataTimeframe, OHLCVBarContract
from cryptotechnolog.market_data.events import BarCompletedPayload


def _make_bar(index: int) -> OHLCVBarContract:
    open_time = datetime(2026, 3, 20, 12, index, tzinfo=UTC)
    close_time = datetime(2026, 3, 20, 12, index + 1, tzinfo=UTC)
    return OHLCVBarContract(
        symbol="BTC/USDT",
        exchange="bybit",
        timeframe=MarketDataTimeframe.M1,
        open_time=open_time,
        close_time=close_time,
        open=Decimal("100"),
        high=Decimal("110"),
        low=Decimal("100"),
        close=Decimal("109"),
        volume=Decimal("15"),
        bid_volume=Decimal("5"),
        ask_volume=Decimal("10"),
        trades_count=3,
        is_closed=True,
    )


def test_runtime_boundary_requires_explicit_start() -> None:
    runtime = IntelligenceRuntime()

    try:
        runtime.ingest_completed_bar(_make_bar(0))
    except RuntimeError as exc:
        assert "IntelligenceRuntime не запущен" in str(exc)
    else:
        raise AssertionError("Ожидался RuntimeError до start()")


def test_runtime_boundary_ingests_typed_bar_and_exposes_query_surface() -> None:
    runtime = IntelligenceRuntime(IntelligenceRuntimeConfig())

    asyncio.run(runtime.start())
    last_update = None
    for index in range(4):
        last_update = runtime.ingest_completed_bar(_make_bar(index))

    assert last_update is not None
    current = runtime.get_derya_assessment(
        exchange="bybit",
        symbol="BTC/USDT",
        timeframe=MarketDataTimeframe.M1,
    )
    diagnostics = runtime.get_runtime_diagnostics()

    assert current == last_update.assessment
    assert diagnostics["started"] is True
    assert diagnostics["tracked_derya_keys"] == 1
    assert diagnostics["last_bar_at"] is not None


def test_runtime_boundary_accepts_bar_completed_payload() -> None:
    runtime = IntelligenceRuntime()

    asyncio.run(runtime.start())
    payload = BarCompletedPayload.from_contract(_make_bar(0))
    update = runtime.ingest_bar_completed_payload(payload)

    assert update.assessment.symbol == "BTC/USDT"
    assert update.assessment.exchange == "bybit"


def test_runtime_boundary_stop_resets_operator_visible_state() -> None:
    runtime = IntelligenceRuntime()

    asyncio.run(runtime.start())
    runtime.ingest_completed_bar(_make_bar(0))
    asyncio.run(runtime.stop())

    diagnostics = runtime.get_runtime_diagnostics()

    assert diagnostics["started"] is False
    assert diagnostics["ready"] is False
    assert diagnostics["lifecycle_state"] == "stopped"
    assert diagnostics["last_bar_at"] is None
    assert diagnostics["last_derya_regime_event_type"] is None
    assert diagnostics["last_failure_reason"] is None
    assert diagnostics["readiness_reasons"] == ["runtime_stopped"]
    assert diagnostics["degraded_reasons"] == []


def test_runtime_boundary_mark_degraded_exposes_failure_reason() -> None:
    runtime = IntelligenceRuntime()

    asyncio.run(runtime.start())
    runtime.mark_degraded("bar_ingest_failed:test_failure")

    diagnostics = runtime.get_runtime_diagnostics()

    assert diagnostics["started"] is True
    assert diagnostics["ready"] is False
    assert diagnostics["lifecycle_state"] == "degraded"
    assert diagnostics["last_failure_reason"] == "bar_ingest_failed:test_failure"
    assert diagnostics["degraded_reasons"] == ["bar_ingest_failed:test_failure"]

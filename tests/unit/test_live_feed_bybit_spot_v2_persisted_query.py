from __future__ import annotations

from datetime import UTC, datetime

import pytest

from cryptotechnolog.live_feed.bybit_spot_v2_persisted_query import (
    BybitSpotV2PersistedQueryService,
    _WindowStats,
)


@pytest.mark.asyncio
async def test_spot_v2_persisted_query_combines_archive_and_live_residual_counts(monkeypatch) -> None:
    service = BybitSpotV2PersistedQueryService(db_manager=None)  # type: ignore[arg-type]

    async def fake_live_residual(*, symbols, window_started_at, observed_at):
        _ = (symbols, window_started_at, observed_at)
        return {
            "BTC/USDT": _WindowStats(2, datetime(2026, 4, 14, 20, 0, tzinfo=UTC), datetime(2026, 4, 14, 21, 0, tzinfo=UTC)),
            "ETH/USDT": _WindowStats(1, datetime(2026, 4, 14, 20, 30, tzinfo=UTC), datetime(2026, 4, 14, 20, 30, tzinfo=UTC)),
        }

    async def fake_archive(*, symbols, window_started_at, observed_at):
        _ = (symbols, window_started_at, observed_at)
        return {
            "BTC/USDT": _WindowStats(5, datetime(2026, 4, 13, 22, 0, tzinfo=UTC), datetime(2026, 4, 14, 0, 0, tzinfo=UTC)),
            "ETH/USDT": _WindowStats(7, datetime(2026, 4, 13, 22, 5, tzinfo=UTC), datetime(2026, 4, 14, 0, 5, tzinfo=UTC)),
        }

    monkeypatch.setattr(service, "_load_live_window_stats_after_archive_boundary", fake_live_residual)
    monkeypatch.setattr(service, "_load_archive_stats", fake_archive)

    snapshot = await service.query_rolling_window(
        symbols=("BTC/USDT", "ETH/USDT"),
        observed_at=datetime(2026, 4, 14, 21, 30, tzinfo=UTC),
    )

    assert snapshot.live_trade_count_24h == 3
    assert snapshot.archive_trade_count_24h == 12
    assert snapshot.persisted_trade_count_24h == 15
    assert snapshot.symbols_covered == ("BTC/USDT", "ETH/USDT")
    assert snapshot.coverage_status == "hybrid"
    assert snapshot.earliest_trade_at == datetime(2026, 4, 13, 22, 0, tzinfo=UTC)
    assert snapshot.latest_trade_at == datetime(2026, 4, 14, 21, 0, tzinfo=UTC)
    assert snapshot.symbols[0].coverage_status == "hybrid"
    assert snapshot.symbols[0].persisted_trade_count_24h == 7
    assert snapshot.symbols[1].persisted_trade_count_24h == 8


@pytest.mark.asyncio
async def test_spot_v2_persisted_query_reports_partial_when_one_symbol_is_empty(monkeypatch) -> None:
    service = BybitSpotV2PersistedQueryService(db_manager=None)  # type: ignore[arg-type]

    async def fake_live(*, symbols, window_started_at, observed_at):
        _ = (symbols, window_started_at, observed_at)
        return {
            "BTC/USDT": _WindowStats(1, datetime(2026, 4, 14, 21, 0, tzinfo=UTC), datetime(2026, 4, 14, 21, 0, tzinfo=UTC)),
        }

    async def fake_archive(*, symbols, window_started_at, observed_at):
        _ = (symbols, window_started_at, observed_at)
        return {}

    monkeypatch.setattr(service, "_load_live_window_stats_after_archive_boundary", fake_live)
    monkeypatch.setattr(service, "_load_archive_stats", fake_archive)

    snapshot = await service.query_rolling_window(
        symbols=("BTC/USDT", "ETH/USDT"),
        observed_at=datetime(2026, 4, 14, 21, 30, tzinfo=UTC),
    )

    assert snapshot.coverage_status == "pending_archive"
    assert snapshot.symbols_covered == ("BTC/USDT",)
    assert snapshot.symbols[0].coverage_status == "pending_archive"
    assert snapshot.symbols[1].coverage_status == "empty"


@pytest.mark.asyncio
async def test_spot_v2_persisted_query_uses_exact_rolling_24h_window_without_minute_alignment(
    monkeypatch,
) -> None:
    service = BybitSpotV2PersistedQueryService(db_manager=None)  # type: ignore[arg-type]
    captured_window_started: list[datetime] = []

    async def fake_archive(*, symbols, window_started_at, observed_at):
        _ = (symbols, observed_at)
        captured_window_started.append(window_started_at)
        return {}

    async def fake_live(*, symbols, window_started_at, observed_at):
        _ = (symbols, observed_at)
        captured_window_started.append(window_started_at)
        return {}

    monkeypatch.setattr(service, "_load_archive_stats", fake_archive)
    monkeypatch.setattr(service, "_load_live_window_stats_after_archive_boundary", fake_live)

    observed_at = datetime(2026, 4, 15, 14, 56, 37, 550653, tzinfo=UTC)
    snapshot = await service.query_rolling_window(
        symbols=("BTC/USDT",),
        observed_at=observed_at,
    )

    exact_window_started_at = datetime(2026, 4, 14, 14, 56, 37, 550653, tzinfo=UTC)
    assert snapshot.window_started_at == exact_window_started_at
    assert captured_window_started == [exact_window_started_at, exact_window_started_at]


@pytest.mark.asyncio
async def test_spot_v2_persisted_query_counts_archive_and_live_residual_from_same_window(monkeypatch) -> None:
    service = BybitSpotV2PersistedQueryService(db_manager=None)  # type: ignore[arg-type]
    observed_at = datetime(2026, 4, 15, 14, 27, tzinfo=UTC)
    aligned_window_started_at = datetime(2026, 4, 14, 14, 27, tzinfo=UTC)

    async def fake_archive(*, symbols, window_started_at, observed_at):
        _ = (symbols, window_started_at, observed_at)
        return {
            "BTC/USDT": _WindowStats(
                620646,
                datetime(2026, 4, 14, 14, 27, tzinfo=UTC),
                datetime(2026, 4, 14, 23, 59, 56, tzinfo=UTC),
            ),
        }

    calls: list[datetime] = []

    async def fake_live(*, symbols, window_started_at, observed_at):
        _ = (symbols, observed_at)
        calls.append(window_started_at)
        return {
            "BTC/USDT": _WindowStats(
                2950,
                datetime(2026, 4, 15, 0, 0, 0, 1000, tzinfo=UTC),
                datetime(2026, 4, 15, 14, 24, 25, tzinfo=UTC),
            ),
        }

    monkeypatch.setattr(service, "_load_archive_stats", fake_archive)
    monkeypatch.setattr(service, "_load_live_window_stats_after_archive_boundary", fake_live)

    snapshot = await service.query_rolling_window(
        symbols=("BTC/USDT",),
        observed_at=observed_at,
    )

    assert calls == [aligned_window_started_at]
    assert snapshot.archive_trade_count_24h == 620646
    assert snapshot.live_trade_count_24h == 2950
    assert snapshot.persisted_trade_count_24h == 623596


@pytest.mark.asyncio
async def test_spot_v2_persisted_query_live_stats_use_archive_boundary_inside_same_window() -> None:
    class _Connection:
        def __init__(self) -> None:
            self.sql: str | None = None
            self.params: tuple[object, ...] | None = None

        async def fetch(self, sql: str, *params: object):
            self.sql = sql
            self.params = params
            return [
                {
                    "normalized_symbol": "BTC/USDT",
                    "trade_count": 42,
                    "earliest_trade_at": datetime(2026, 4, 15, 0, 1, tzinfo=UTC),
                    "latest_trade_at": datetime(2026, 4, 15, 0, 2, tzinfo=UTC),
                }
            ]

    class _ConnectionContext:
        def __init__(self, connection: _Connection) -> None:
            self._connection = connection

        async def __aenter__(self) -> _Connection:
            return self._connection

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

    class _DbManager:
        def __init__(self, connection: _Connection) -> None:
            self._connection = connection

        def connection(self) -> _ConnectionContext:
            return _ConnectionContext(self._connection)

    connection = _Connection()
    service = BybitSpotV2PersistedQueryService(db_manager=_DbManager(connection))  # type: ignore[arg-type]
    window_started_at = datetime(2026, 4, 14, 14, 57, tzinfo=UTC)
    observed_at = datetime(2026, 4, 15, 14, 57, tzinfo=UTC)

    stats = await service._load_live_window_stats_after_archive_boundary(
        symbols=("BTC/USDT",),
        window_started_at=window_started_at,
        observed_at=observed_at,
    )

    assert connection.sql is not None
    assert "MAX(archive.exchange_trade_at)" in connection.sql
    assert "live.exchange_trade_at > boundary.live_started_at" in connection.sql
    assert connection.params == (["BTC/USDT"], window_started_at, observed_at)
    assert stats["BTC/USDT"].trade_count == 42


@pytest.mark.asyncio
async def test_spot_v2_trade_count_snapshots_use_archive_boundary_live_residual(monkeypatch) -> None:
    service = BybitSpotV2PersistedQueryService(db_manager=None)  # type: ignore[arg-type]

    async def fake_archive(*, symbols, window_started_at, observed_at):
        _ = (symbols, window_started_at, observed_at)
        return {
            "BTC/USDT": _WindowStats(
                100,
                datetime(2026, 4, 21, 0, 30, tzinfo=UTC),
                datetime(2026, 4, 21, 23, 59, 57, tzinfo=UTC),
            ),
            "ETH/USDT": _WindowStats(
                50,
                datetime(2026, 4, 21, 0, 30, tzinfo=UTC),
                datetime(2026, 4, 21, 23, 59, 58, tzinfo=UTC),
            ),
        }

    async def fake_live(*, symbols, window_started_at, observed_at):
        _ = (symbols, window_started_at, observed_at)
        return {
            "BTC/USDT": _WindowStats(
                7,
                datetime(2026, 4, 22, 0, 0, 1, tzinfo=UTC),
                datetime(2026, 4, 22, 0, 20, tzinfo=UTC),
            ),
            "ETH/USDT": _WindowStats(
                3,
                datetime(2026, 4, 22, 0, 0, 1, tzinfo=UTC),
                datetime(2026, 4, 22, 0, 10, tzinfo=UTC),
            ),
        }

    monkeypatch.setattr(service, "_load_archive_stats", fake_archive)
    monkeypatch.setattr(service, "_load_live_window_stats_after_archive_boundary", fake_live)

    snapshots = await service.query_rolling_trade_count_snapshots(
        symbols=("BTC/USDT", "ETH/USDT"),
        observed_at=datetime(2026, 4, 22, 0, 30, tzinfo=UTC),
    )

    assert snapshots["BTC/USDT"].archive_trade_count_24h == 100
    assert snapshots["BTC/USDT"].live_trade_count_24h == 7
    assert snapshots["BTC/USDT"].persisted_trade_count_24h == 107
    assert snapshots["BTC/USDT"].coverage_status == "hybrid"
    assert snapshots["ETH/USDT"].persisted_trade_count_24h == 53


@pytest.mark.asyncio
async def test_spot_v2_rolling_window_marks_pending_archive_when_closed_day_missing(
    monkeypatch,
) -> None:
    service = BybitSpotV2PersistedQueryService(db_manager=None)  # type: ignore[arg-type]

    async def fake_archive(*, symbols, window_started_at, observed_at):
        _ = (symbols, window_started_at, observed_at)
        return {
            "BTC/USDT": _WindowStats(
                0,
                None,
                datetime(2026, 4, 21, 23, 59, 57, tzinfo=UTC),
            ),
        }

    async def fake_live(*, symbols, window_started_at, observed_at):
        _ = (symbols, window_started_at, observed_at)
        return {
            "BTC/USDT": _WindowStats(
                42,
                datetime(2026, 4, 23, 0, 0, 1, tzinfo=UTC),
                datetime(2026, 4, 23, 0, 20, tzinfo=UTC),
            ),
        }

    monkeypatch.setattr(service, "_load_archive_stats", fake_archive)
    monkeypatch.setattr(service, "_load_live_window_stats_after_archive_boundary", fake_live)

    snapshot = await service.query_rolling_window(
        symbols=("BTC/USDT",),
        observed_at=datetime(2026, 4, 23, 0, 56, tzinfo=UTC),
    )

    assert snapshot.archive_trade_count_24h == 0
    assert snapshot.live_trade_count_24h == 42
    assert snapshot.coverage_status == "pending_archive"
    assert snapshot.symbols[0].coverage_status == "pending_archive"

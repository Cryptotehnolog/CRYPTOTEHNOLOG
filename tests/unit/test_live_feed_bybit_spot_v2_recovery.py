from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from unittest.mock import AsyncMock

from cryptotechnolog.live_feed.bybit_spot_v2_recovery import (
    BybitSpotV2RecoveryCoordinator,
)
from cryptotechnolog.live_feed.bybit_spot_v2_live_trade_ledger import (
    BybitSpotV2LiveTradeLedgerRecord,
)


@dataclass(slots=True, frozen=True)
class _PersistedSymbolSnapshot:
    archive_trade_count_24h: int
    latest_trade_at: datetime | None = None


@dataclass(slots=True, frozen=True)
class _PersistedWindowSnapshot:
    symbols: tuple[_PersistedSymbolSnapshot, ...]


@dataclass(slots=True, frozen=True)
class _ArchiveReport:
    status: str
    processed_archives: int
    written_archive_records: int
    skipped_archive_records: int
    archive_dates: tuple[str, ...]
    reason: str | None = None


class _StubPersistedQueryService:
    def __init__(
        self,
        *,
        archive_trade_count_24h: int,
        latest_trade_at: datetime | None = None,
    ) -> None:
        self.archive_trade_count_24h = archive_trade_count_24h
        self.latest_trade_at = latest_trade_at

    async def query_rolling_window(self, *, symbols, observed_at, window_hours):
        _ = (observed_at, window_hours)
        return _PersistedWindowSnapshot(
            symbols=tuple(
                _PersistedSymbolSnapshot(
                    archive_trade_count_24h=self.archive_trade_count_24h,
                    latest_trade_at=self.latest_trade_at,
                )
                for _symbol in symbols
            )
        )


class _FakeLiveTradeRepository:
    def __init__(
        self,
        latest_trade: BybitSpotV2LiveTradeLedgerRecord | None,
        earliest_trade: BybitSpotV2LiveTradeLedgerRecord | None = None,
    ) -> None:
        self.latest_trade = latest_trade
        self.earliest_trade = earliest_trade
        self.calls: list[tuple[str, datetime]] = []
        self.earliest_calls: list[tuple[str, datetime, datetime]] = []

    async def fetch_latest_trade_before(
        self,
        *,
        normalized_symbol: str,
        observed_at: datetime,
    ) -> BybitSpotV2LiveTradeLedgerRecord | None:
        self.calls.append((normalized_symbol, observed_at))
        if self.latest_trade is None:
            return None
        if self.latest_trade.exchange_trade_at >= observed_at:
            return None
        return self.latest_trade

    async def fetch_earliest_trade_after(
        self,
        *,
        normalized_symbol: str,
        trade_at: datetime,
        observed_at: datetime,
    ) -> BybitSpotV2LiveTradeLedgerRecord | None:
        self.earliest_calls.append((normalized_symbol, trade_at, observed_at))
        if self.earliest_trade is None:
            return None
        if self.earliest_trade.exchange_trade_at <= trade_at:
            return None
        if self.earliest_trade.exchange_trade_at >= observed_at:
            return None
        return self.earliest_trade

    async def upsert_live_trade(self, record) -> None:
        _ = record


class _FakeArchiveTradeRepository:
    def __init__(self, latest_trade) -> None:
        self.latest_trade = latest_trade
        self.calls: list[tuple[str, datetime]] = []

    async def fetch_latest_trade_before(
        self,
        *,
        normalized_symbol: str,
        observed_at: datetime,
    ):
        self.calls.append((normalized_symbol, observed_at))
        if self.latest_trade is None:
            return None
        if self.latest_trade.exchange_trade_at >= observed_at:
            return None
        return self.latest_trade


@dataclass(slots=True, frozen=True)
class _ArchiveTradeRecord:
    exchange_trade_at: datetime


class _RecordingRecoveryCoordinator(BybitSpotV2RecoveryCoordinator):
    def __init__(self, *args, legacy_rows: list[dict[str, object]], **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.legacy_rows = legacy_rows
        self.resume_calls: list[tuple[str, datetime, datetime]] = []

    async def _load_legacy_live_tail_rows(
        self,
        *,
        symbol: str,
        resume_after_trade_at: datetime,
        observed_at: datetime,
    ) -> list[dict[str, object]]:
        self.resume_calls.append((symbol, resume_after_trade_at, observed_at))
        return list(self.legacy_rows)


def _build_live_trade_record(*, exchange_trade_at: datetime) -> BybitSpotV2LiveTradeLedgerRecord:
    return BybitSpotV2LiveTradeLedgerRecord(
        exchange="bybit_spot_v2",
        normalized_symbol="BTC/USDT",
        live_trade_id="123",
        source_trade_identity="source:123",
        canonical_dedup_identity="dedup:123",
        identity_contract_version=1,
        exchange_trade_at=exchange_trade_at,
        side="buy",
        normalized_price=Decimal("1"),
        normalized_size=Decimal("1"),
        is_buyer_maker=False,
        source_metadata={"live_trade_id": "123"},
        created_at=exchange_trade_at,
        updated_at=exchange_trade_at,
    )


@pytest.mark.asyncio
async def test_spot_v2_recovery_skips_when_archive_window_already_present() -> None:
    loader_calls = 0

    async def archive_loader_runner(**kwargs):
        nonlocal loader_calls
        loader_calls += 1
        raise AssertionError(f"loader should not run: {kwargs}")

    coordinator = BybitSpotV2RecoveryCoordinator(
        symbols=("BTC/USDT", "ETH/USDT"),
        persisted_query_service=_StubPersistedQueryService(archive_trade_count_24h=5),
        archive_loader_runner=archive_loader_runner,
        observed_at_factory=lambda: datetime(2026, 4, 15, 12, 0, tzinfo=UTC),
    )

    await coordinator.run()
    diagnostics = coordinator.get_recovery_diagnostics()

    assert loader_calls == 0
    assert diagnostics["status"] == "skipped"
    assert diagnostics["stage"] == "skipped_archive_present"
    assert diagnostics["reason"] == "archive_window_already_present"
    assert diagnostics["ready"] is True


@pytest.mark.asyncio
async def test_spot_v2_recovery_runs_archive_loader_and_tracks_checkpoint() -> None:
    progress_messages: list[str] = []

    async def archive_loader_runner(**kwargs):
        progress_sink = kwargs["progress_sink"]
        progress_sink("[spot-v2-archive-load] checkpoint=archive_load_finished status=completed")
        progress_messages.append("archive_load_finished")
        return _ArchiveReport(
            status="completed",
            processed_archives=1,
            written_archive_records=3,
            skipped_archive_records=0,
            archive_dates=("2026-04-14",),
        )

    coordinator = BybitSpotV2RecoveryCoordinator(
        symbols=("BTC/USDT",),
        persisted_query_service=_StubPersistedQueryService(archive_trade_count_24h=0),
        archive_loader_runner=archive_loader_runner,
        observed_at_factory=lambda: datetime(2026, 4, 15, 12, 0, tzinfo=UTC),
    )

    await coordinator.run()
    diagnostics = coordinator.get_recovery_diagnostics()

    assert progress_messages == ["archive_load_finished"]
    assert diagnostics["status"] == "completed"
    assert diagnostics["stage"] == "completed"
    assert diagnostics["processed_archives"] == 1
    assert diagnostics["written_archive_records"] == 3
    assert diagnostics["archive_dates"] == ("2026-04-14",)
    assert diagnostics["last_progress_checkpoint"] == "archive_load_finished"
    assert diagnostics["ready"] is True


@pytest.mark.asyncio
async def test_spot_v2_recovery_marks_failures_explicitly() -> None:
    async def archive_loader_runner(**kwargs):
        _ = kwargs
        raise RuntimeError("archive_loader_failed")

    coordinator = BybitSpotV2RecoveryCoordinator(
        symbols=("BTC/USDT",),
        persisted_query_service=_StubPersistedQueryService(archive_trade_count_24h=0),
        archive_loader_runner=archive_loader_runner,
        observed_at_factory=lambda: datetime(2026, 4, 15, 12, 0, tzinfo=UTC),
    )

    await coordinator.run()
    diagnostics = coordinator.get_recovery_diagnostics()

    assert diagnostics["status"] == "failed"
    assert diagnostics["stage"] == "failed"
    assert diagnostics["last_error"] == "RuntimeError: archive_loader_failed"
    assert diagnostics["reason"] == "recovery_exception"
    assert diagnostics["ready"] is False


@pytest.mark.asyncio
async def test_spot_v2_recovery_resumes_live_tail_within_observed_window() -> None:
    observed_at = datetime(2026, 4, 15, 13, 44, 17, tzinfo=UTC)
    latest_v2_live = _build_live_trade_record(
        exchange_trade_at=datetime(2026, 4, 15, 14, 24, 25, tzinfo=UTC)
    )

    async def archive_loader_runner(**kwargs):
        _ = kwargs
        return _ArchiveReport(
            status="skipped",
            processed_archives=0,
            written_archive_records=0,
            skipped_archive_records=0,
            archive_dates=(),
            reason="archive_already_loaded",
        )

    coordinator = _RecordingRecoveryCoordinator(
        symbols=("BTC/USDT",),
        persisted_query_service=_StubPersistedQueryService(
            archive_trade_count_24h=100,
            latest_trade_at=datetime(2026, 4, 14, 23, 59, 59, tzinfo=UTC),
        ),
        archive_loader_runner=archive_loader_runner,
        db_manager=object(),
        archive_trade_repository=_FakeArchiveTradeRepository(
            _ArchiveTradeRecord(exchange_trade_at=datetime(2026, 4, 14, 23, 59, 59, tzinfo=UTC))
        ),
        live_trade_repository=_FakeLiveTradeRepository(
            latest_v2_live,
            earliest_trade=_build_live_trade_record(
                exchange_trade_at=datetime(2026, 4, 15, 0, 33, 52, tzinfo=UTC)
            ),
        ),
        observed_at_factory=lambda: observed_at,
        legacy_rows=[],
    )

    await coordinator.run()

    assert coordinator.resume_calls == [
        (
            "BTC/USDT",
            datetime(2026, 4, 15, 0, 0, tzinfo=UTC),
            observed_at,
        )
    ]


@pytest.mark.asyncio
async def test_spot_v2_recovery_async_diagnostics_refreshes_failed_coverage_when_window_is_now_closed() -> None:
    observed_at = datetime(2026, 4, 15, 13, 44, 17, tzinfo=UTC)

    async def archive_loader_runner(**kwargs):
        _ = kwargs
        return _ArchiveReport(
            status="skipped",
            processed_archives=0,
            written_archive_records=0,
            skipped_archive_records=0,
            archive_dates=(),
            reason="archive_already_loaded",
        )

    coordinator = BybitSpotV2RecoveryCoordinator(
        symbols=("BTC/USDT",),
        persisted_query_service=_StubPersistedQueryService(
            archive_trade_count_24h=100,
            latest_trade_at=datetime(2026, 4, 14, 23, 59, 59, tzinfo=UTC),
        ),
        archive_loader_runner=archive_loader_runner,
        db_manager=object(),
        archive_trade_repository=_FakeArchiveTradeRepository(
            _ArchiveTradeRecord(exchange_trade_at=datetime(2026, 4, 14, 23, 59, 59, tzinfo=UTC))
        ),
        live_trade_repository=_FakeLiveTradeRepository(
            latest_trade=_build_live_trade_record(
                exchange_trade_at=datetime(2026, 4, 15, 13, 43, 59, tzinfo=UTC)
            ),
            earliest_trade=_build_live_trade_record(
                exchange_trade_at=datetime(2026, 4, 15, 0, 2, 0, tzinfo=UTC)
            ),
        ),
        observed_at_factory=lambda: observed_at,
    )

    coordinator._snapshot = coordinator._snapshot.__class__(
        status="failed",
        stage="coverage_incomplete",
        target_symbols=("BTC/USDT",),
        observed_at=observed_at,
        window_started_at=observed_at.replace(hour=0, minute=0, second=0, microsecond=0),
        window_hours=24,
        started_at=observed_at,
        finished_at=observed_at,
        last_error="persisted_live_tail_incomplete",
        reason="persisted_live_tail_incomplete",
        last_progress_checkpoint="live_tail_rows_loaded",
    )

    diagnostics = await coordinator.get_recovery_diagnostics_async()

    assert diagnostics["status"] == "skipped"
    assert diagnostics["stage"] == "skipped_coverage_present"
    assert diagnostics["reason"] == "persisted_window_already_present"
    assert diagnostics["ready"] is True


@pytest.mark.asyncio
async def test_spot_v2_recovery_does_not_treat_live_only_window_as_closed_without_archive() -> None:
    observed_at = datetime(2026, 4, 15, 13, 44, 17, tzinfo=UTC)

    async def archive_loader_runner(**kwargs):
        _ = kwargs
        return _ArchiveReport(
            status="completed",
            processed_archives=1,
            written_archive_records=5,
            skipped_archive_records=0,
            archive_dates=("2026-04-14",),
        )

    coordinator = BybitSpotV2RecoveryCoordinator(
        symbols=("BTC/USDT",),
        persisted_query_service=_StubPersistedQueryService(archive_trade_count_24h=0),
        archive_loader_runner=archive_loader_runner,
        db_manager=object(),
        archive_trade_repository=_FakeArchiveTradeRepository(None),
        live_trade_repository=_FakeLiveTradeRepository(
            latest_trade=_build_live_trade_record(
                exchange_trade_at=datetime(2026, 4, 15, 13, 43, 59, tzinfo=UTC)
            ),
            earliest_trade=_build_live_trade_record(
                exchange_trade_at=datetime(2026, 4, 14, 13, 35, 0, tzinfo=UTC)
            ),
        ),
        observed_at_factory=lambda: observed_at,
    )
    coordinator._recover_persisted_live_tail = AsyncMock(return_value=0)  # type: ignore[method-assign]

    await coordinator.run()
    diagnostics = coordinator.get_recovery_diagnostics()

    assert diagnostics["processed_archives"] == 1
    assert diagnostics["status"] == "retry_scheduled"
    assert diagnostics["stage"] == "coverage_incomplete"
    assert diagnostics["reason"] == "persisted_live_tail_incomplete"


@pytest.mark.asyncio
async def test_spot_v2_recovery_prepare_storage_runs_48h_cleanup() -> None:
    archive_repository = AsyncMock()
    live_repository = AsyncMock()
    coordinator = BybitSpotV2RecoveryCoordinator(
        symbols=("BTC/USDT",),
        persisted_query_service=_StubPersistedQueryService(archive_trade_count_24h=0),
        archive_loader_runner=AsyncMock(),
        archive_trade_repository=archive_repository,
        live_trade_repository=live_repository,
    )

    await coordinator.prepare_storage()

    archive_repository.cleanup_retention.assert_awaited_once_with(retention_hours=48)
    live_repository.cleanup_retention.assert_awaited_once_with(retention_hours=48)

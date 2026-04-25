from __future__ import annotations

import gzip
from datetime import UTC, datetime
from urllib.error import HTTPError

import pytest

from cryptotechnolog.live_feed.bybit_spot_v2_archive_loader import (
    BybitSpotV2ArchiveLoadRequest,
    BybitSpotV2ArchiveLoader,
    _parse_args,
)
from cryptotechnolog.live_feed.bybit_spot_v2_archive_ledger import (
    build_bybit_spot_v2_archive_trade_ledger_record,
    write_bybit_spot_v2_archive_trade_to_ledger,
)
from cryptotechnolog.live_feed.bybit_trade_backfill import (
    BybitHistoricalTradeBackfillConfig,
    BybitHistoricalTradeBackfillService,
    extract_bybit_archive_trade_fact,
)
from cryptotechnolog.live_feed.bybit_trade_identity import build_bybit_trade_identity


class _InMemoryArchiveLedgerRepository:
    def __init__(self) -> None:
        self.records: list[object] = []

    async def upsert_archive_trade(self, record) -> None:
        self.records.append(record)

    async def upsert_archive_trades(self, records, *, chunk_size: int = 5000) -> None:
        _ = chunk_size
        self.records.extend(records)

    async def fetch_latest_trade(self, *, normalized_symbol: str):
        candidates = [
            record for record in self.records if record.normalized_symbol == normalized_symbol
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda record: (record.exchange_trade_at, record.updated_at))


@pytest.mark.asyncio
async def test_spot_v2_archive_loader_writes_archive_rows_into_separate_v2_repository() -> None:
    payload = gzip.compress(
        (
            "timestamp,price,volume,side,id,rpi\n"
            "2026-04-11T12:01:00+00:00,68000.10,0.100,Buy,spot-archive-1,false\n"
        ).encode("utf-8")
    )
    service = BybitHistoricalTradeBackfillService(
        config=BybitHistoricalTradeBackfillConfig(contour="spot", cache_dir=None),
        fetch_bytes=lambda url, timeout_seconds: payload,
    )
    repository = _InMemoryArchiveLedgerRepository()
    loader = BybitSpotV2ArchiveLoader(
        backfill_service=service,
        repository=repository,  # type: ignore[arg-type]
    )

    report = await loader.load_archive_window(
        request=BybitSpotV2ArchiveLoadRequest(
            symbols=("BTC/USDT",),
            observed_at=datetime(2026, 4, 12, 0, 0, tzinfo=UTC),
            covered_until_at=datetime(2026, 4, 12, 0, 0, tzinfo=UTC),
        )
    )

    assert report.status == "completed"
    assert report.processed_archives == 1
    assert report.written_archive_records == 1
    assert len(repository.records) == 1
    assert repository.records[0].normalized_symbol == "BTC/USDT"
    assert repository.records[0].archive_trade_id == "spot-archive-1"


@pytest.mark.asyncio
async def test_spot_v2_archive_loader_rewinds_one_day_when_latest_spot_archive_is_missing() -> None:
    payload = gzip.compress(
        (
            "timestamp,price,volume,side,id,rpi\n"
            "2026-04-13T12:01:00+00:00,2319.40,0.01136,Sell,eth-archive-1,false\n"
        ).encode("utf-8")
    )

    def fetch_bytes(url: str, timeout_seconds: int) -> bytes:
        _ = timeout_seconds
        if url.endswith("ETHUSDT_2026-04-14.csv.gz") or url.endswith("ETHUSDT-2026-04.csv.gz"):
            raise HTTPError(url, 404, "not found", hdrs=None, fp=None)
        if url.endswith("ETHUSDT_2026-04-13.csv.gz"):
            return payload
        raise AssertionError(f"unexpected url: {url}")

    service = BybitHistoricalTradeBackfillService(
        config=BybitHistoricalTradeBackfillConfig(contour="spot", cache_dir=None),
        fetch_bytes=fetch_bytes,
    )
    repository = _InMemoryArchiveLedgerRepository()
    loader = BybitSpotV2ArchiveLoader(
        backfill_service=service,
        repository=repository,  # type: ignore[arg-type]
    )

    report = await loader.load_archive_window(
        request=BybitSpotV2ArchiveLoadRequest(
            symbols=("ETH/USDT",),
            observed_at=datetime(2026, 4, 15, 0, 0, tzinfo=UTC),
        )
    )

    assert report.status == "completed"
    assert report.archive_dates == ("2026-04-13",)
    assert report.processed_archives == 1
    assert report.written_archive_records == 1
    assert len(repository.records) == 1
    assert repository.records[0].normalized_symbol == "ETH/USDT"
    assert repository.records[0].archive_trade_id == "eth-archive-1"


@pytest.mark.asyncio
async def test_spot_v2_archive_ledger_writer_skips_unidentifiable_trade_fact() -> None:
    repository = _InMemoryArchiveLedgerRepository()
    extraction = extract_bybit_archive_trade_fact(
        contour="spot",
        row=["2026-04-11T12:01:00+00:00", "68000.10", "0.100", "Buy", ""],
        raw_symbol_context="BTCUSDT",
        header_index={
            "timestamp": 0,
            "price": 1,
            "volume": 2,
            "side": 3,
            "id": 4,
        },
    )
    identity = build_bybit_trade_identity(extraction)

    write_result = await write_bybit_spot_v2_archive_trade_to_ledger(
        extraction=extraction,
        identity=identity,
        repository=repository,  # type: ignore[arg-type]
    )

    assert write_result.status == "skipped"
    assert write_result.record is None
    assert repository.records == []


def test_spot_v2_archive_loader_cli_accepts_timeout_seconds(monkeypatch) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [
            "bybit_spot_v2_archive_loader",
            "--symbols",
            "ETH/USDT",
            "--observed-at",
            "2026-04-15T00:00:00+00:00",
            "--timeout-seconds",
            "7",
        ],
    )

    args = _parse_args()

    assert args.symbols == ["ETH/USDT"]
    assert args.timeout_seconds == 7


def test_spot_v2_archive_ledger_record_builder_returns_record_for_identifiable_trade() -> None:
    extraction = extract_bybit_archive_trade_fact(
        contour="spot",
        row=["2026-04-11T12:01:00+00:00", "68000.10", "0.100", "Buy", "archive-id-1"],
        raw_symbol_context="BTCUSDT",
        header_index={
            "timestamp": 0,
            "price": 1,
            "volume": 2,
            "side": 3,
            "id": 4,
        },
    )
    identity = build_bybit_trade_identity(extraction)

    record = build_bybit_spot_v2_archive_trade_ledger_record(
        extraction=extraction,
        identity=identity,
    )

    assert record is not None
    assert record.normalized_symbol == "BTC/USDT"
    assert record.archive_trade_id == "archive-id-1"

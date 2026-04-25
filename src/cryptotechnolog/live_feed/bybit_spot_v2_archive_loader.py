"""Controlled archive load entrypoint for Bybit spot v2."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from cryptotechnolog.core.database import DatabaseManager

from .bybit_spot_v2_archive_ledger import (
    BybitSpotV2ArchiveTradeLedgerRepository,
    build_bybit_spot_v2_archive_trade_ledger_record,
    write_bybit_spot_v2_archive_trade_to_ledger,
)
from .bybit_trade_backfill import create_bybit_historical_trade_backfill_service
from .bybit_trade_identity import build_bybit_trade_identity

if TYPE_CHECKING:
    from collections.abc import Callable

    from .bybit_trade_backfill import BybitHistoricalTradeBackfillService


@dataclass(slots=True, frozen=True)
class BybitSpotV2ArchiveLoadRequest:
    symbols: tuple[str, ...]
    observed_at: datetime
    covered_until_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.symbols:
            raise ValueError("symbols не может быть пустым")
        object.__setattr__(self, "observed_at", self.observed_at.astimezone(UTC))
        if self.covered_until_at is not None:
            object.__setattr__(
                self,
                "covered_until_at",
                self.covered_until_at.astimezone(UTC),
            )


@dataclass(slots=True, frozen=True)
class BybitSpotV2ArchiveLoadReport:
    status: str
    observed_at: datetime
    symbols: tuple[str, ...]
    archive_dates: tuple[str, ...]
    processed_archives: int
    total_archives: int
    written_archive_records: int
    skipped_archive_records: int
    restored_window_started_at: datetime | None
    covered_until_at: datetime | None
    reason: str | None = None


class BybitSpotV2ArchiveLoader:
    """Narrow archive loader for separate spot v2 archive storage."""

    _WRITE_BATCH_SIZE = 25_000

    def __init__(
        self,
        *,
        backfill_service: BybitHistoricalTradeBackfillService,
        repository: BybitSpotV2ArchiveTradeLedgerRepository,
        progress_sink: Callable[[str], None] | None = None,
    ) -> None:
        self._backfill_service = backfill_service
        self._repository = repository
        self._progress_sink = progress_sink

    async def load_archive_window(
        self,
        *,
        request: BybitSpotV2ArchiveLoadRequest,
    ) -> BybitSpotV2ArchiveLoadReport:
        self._emit(
            "[spot-v2-archive-load] "
            f"checkpoint=entry_started observed_at={request.observed_at.isoformat()} "
            f"symbols={request.symbols}"
        )
        plan = self._backfill_service.build_recovery_plan(
            symbols=request.symbols,
            observed_at=request.observed_at,
            covered_until_at=request.covered_until_at,
        )
        self._emit(
            "[spot-v2-archive-load] "
            f"checkpoint=plan_built total_archives={plan.total_archives} "
            f"archive_dates={[day.isoformat() for day in plan.archive_dates]}"
        )
        plan, result = await self._load_with_spot_latest_archive_fallback(
            request=request,
            initial_plan=plan,
        )
        self._emit(
            "[spot-v2-archive-load] "
            f"checkpoint=archive_load_finished status={result.status} "
            f"processed_archives={result.processed_archives} total_archives={result.total_archives}"
        )
        written_archive_records = 0
        skipped_archive_records = 0
        for symbol, extractions in result.archive_trade_extractions_by_symbol.items():
            resume_after_trade_at = await self._load_resume_after_trade_at(symbol=symbol)
            if resume_after_trade_at is not None:
                self._emit(
                    "[spot-v2-archive-load] "
                    f"checkpoint=symbol_resume_detected symbol={symbol} "
                    f"resume_after_trade_at={resume_after_trade_at.isoformat()}"
                )
            self._emit(
                "[spot-v2-archive-load] "
                f"checkpoint=symbol_write_started symbol={symbol} extractions={len(extractions)}"
            )
            batch_records = []
            for extraction in extractions:
                trade_fact = extraction.trade_fact
                if (
                    resume_after_trade_at is not None
                    and trade_fact is not None
                    and trade_fact.exchange_trade_at < resume_after_trade_at
                ):
                    skipped_archive_records += 1
                    continue
                identity = build_bybit_trade_identity(extraction)
                record = build_bybit_spot_v2_archive_trade_ledger_record(
                    extraction=extraction,
                    identity=identity,
                )
                if record is None:
                    skipped_archive_records += 1
                else:
                    written_archive_records += 1
                    batch_records.append(record)
                    if len(batch_records) >= self._WRITE_BATCH_SIZE:
                        await self._repository.upsert_archive_trades(batch_records)
                        batch_records = []
            if batch_records:
                await self._repository.upsert_archive_trades(batch_records)
            self._emit(
                "[spot-v2-archive-load] "
                f"checkpoint=symbol_write_finished symbol={symbol} "
                f"written={written_archive_records} skipped={skipped_archive_records}"
            )
        return BybitSpotV2ArchiveLoadReport(
            status="completed" if written_archive_records > 0 else result.status,
            observed_at=request.observed_at,
            symbols=request.symbols,
            archive_dates=tuple(day.isoformat() for day in plan.archive_dates),
            processed_archives=result.processed_archives,
            total_archives=result.total_archives,
            written_archive_records=written_archive_records,
            skipped_archive_records=skipped_archive_records,
            restored_window_started_at=result.restored_window_started_at,
            covered_until_at=result.covered_until_at,
            reason=result.reason,
        )

    async def _load_resume_after_trade_at(self, *, symbol: str) -> datetime | None:
        latest_record = await self._repository.fetch_latest_trade(normalized_symbol=symbol)
        if latest_record is None:
            return None
        return latest_record.exchange_trade_at

    def _emit(self, message: str) -> None:
        if self._progress_sink is not None:
            self._progress_sink(message)

    async def _load_with_spot_latest_archive_fallback(
        self,
        *,
        request: BybitSpotV2ArchiveLoadRequest,
        initial_plan,
    ):
        result = await asyncio.to_thread(
            self._backfill_service.load_materialization_plan,
            plan=initial_plan,
        )
        if not self._should_retry_previous_spot_day(result=result, plan=initial_plan):
            return initial_plan, result
        fallback_plan = self._backfill_service.build_recovery_plan(
            symbols=request.symbols,
            observed_at=request.observed_at - timedelta(days=1),
        )
        self._emit(
            "[spot-v2-archive-load] "
            f"checkpoint=latest_archive_missing_retry "
            f"retry_archive_dates={[day.isoformat() for day in fallback_plan.archive_dates]}"
        )
        fallback_result = await asyncio.to_thread(
            self._backfill_service.load_materialization_plan,
            plan=fallback_plan,
        )
        return fallback_plan, fallback_result

    def _should_retry_previous_spot_day(self, *, result, plan) -> bool:
        reason = result.reason or ""
        if result.status != "skipped":
            return False
        if result.processed_archives != 0:
            return False
        if self._backfill_service.config.contour != "spot":
            return False
        if not reason.startswith("historical trade archive not found for spot:"):
            return False
        if not plan.archive_dates:
            return False
        return True


async def run_bybit_spot_v2_archive_loader(
    *,
    db_manager: DatabaseManager,
    request: BybitSpotV2ArchiveLoadRequest,
    progress_sink: Callable[[str], None] | None = None,
) -> BybitSpotV2ArchiveLoadReport:
    loader = BybitSpotV2ArchiveLoader(
        backfill_service=create_bybit_historical_trade_backfill_service(
            contour="spot",
            diagnostic_callback=progress_sink,
        ),
        repository=BybitSpotV2ArchiveTradeLedgerRepository(db_manager),
        progress_sink=progress_sink,
    )
    return await loader.load_archive_window(request=request)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Controlled Bybit spot v2 archive loader.",
    )
    parser.add_argument(
        "--symbols",
        nargs="+",
        required=True,
        help="Normalized symbols, e.g. BTC/USDT ETH/USDT",
    )
    parser.add_argument(
        "--observed-at",
        required=True,
        help="UTC timestamp in ISO-8601 format",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=30,
        help="Hard timeout for controlled CLI run",
    )
    return parser.parse_args()


async def _main() -> None:
    args = _parse_args()
    db_manager = DatabaseManager()
    try:
        try:
            report = await asyncio.wait_for(
                run_bybit_spot_v2_archive_loader(
                    db_manager=db_manager,
                    request=BybitSpotV2ArchiveLoadRequest(
                        symbols=tuple(args.symbols),
                        observed_at=datetime.fromisoformat(args.observed_at),
                    ),
                    progress_sink=print,
                ),
                timeout=args.timeout_seconds,
            )
        except asyncio.TimeoutError:
            print(
                "BybitSpotV2ArchiveLoadReport("
                "status='timed_out', "
                f"symbols={tuple(args.symbols)!r}, "
                f"observed_at={datetime.fromisoformat(args.observed_at)!r}, "
                f"reason='cli_timeout_{args.timeout_seconds}s'"
                ")"
            )
            return
        print(report)
    finally:
        await db_manager.close()


if __name__ == "__main__":
    asyncio.run(_main())

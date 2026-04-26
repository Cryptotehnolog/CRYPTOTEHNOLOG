"""
Archive-only bulk materialization path for canonical Bybit trade ledger.
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
import threading
from time import monotonic
from typing import TYPE_CHECKING, Literal

from cryptotechnolog.core.database import DatabaseManager

from .bybit_live_trade_fact import BybitLiveTradeFact, BybitLiveTradeFactBuildResult
from .bybit_live_trade_identity import build_bybit_live_trade_identity
from .bybit_trade_backfill import (
    BybitHistoricalTradeBackfillResult,
    BybitTradeBackfillContour,
    create_bybit_historical_trade_backfill_service,
)
from .bybit_trade_identity import build_bybit_trade_identity
from .bybit_trade_identity import build_bybit_archive_source_trade_identity
from .bybit_trade_ledger_persistence import BybitTradeLedgerRepository
from .bybit_trade_ledger_writer import write_archive_trade_fact_to_ledger
from .bybit_trade_overlap import compare_archive_and_live_trade

if TYPE_CHECKING:
    from collections.abc import Callable

    from .bybit_trade_ledger_contracts import BybitTradeLedgerRecord, IBybitTradeLedgerRepository


BybitArchiveBulkMaterializationStatus = Literal["completed", "skipped", "timed_out"]
BybitLiveOverlapCandidate = tuple[int, object, BybitLiveTradeFactBuildResult, object]


class _CheckpointMonitor:
    def __init__(
        self,
        *,
        progress_sink: Callable[[str], None] | None,
        heartbeat_seconds: int,
        timeout_seconds: int,
        hard_timeout_exit: bool,
    ) -> None:
        self._progress_sink = progress_sink
        self._heartbeat_seconds = heartbeat_seconds
        self._timeout_seconds = timeout_seconds
        self._hard_timeout_exit = hard_timeout_exit
        self._started_at = monotonic()
        self._checkpoint = "entry_started"
        self._stop_event = threading.Event()
        self._timeout_event = threading.Event()
        self._lock = threading.Lock()
        self._thread = threading.Thread(
            target=self._run,
            name="bybit-archive-bulk-monitor",
            daemon=True,
        )

    def start(self) -> None:
        self.emit_checkpoint("entry_started")
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._thread.join(timeout=1)

    def raise_if_timed_out(self) -> None:
        if self._timeout_event.is_set():
            raise TimeoutError(
                f"bybit archive bulk materialization timed out at checkpoint={self.current_checkpoint}"
            )

    def emit_checkpoint(self, checkpoint: str) -> None:
        with self._lock:
            self._checkpoint = checkpoint
        self._emit(f"checkpoint={checkpoint} elapsed_seconds={self.elapsed_seconds}")

    @property
    def elapsed_seconds(self) -> int:
        return int(monotonic() - self._started_at)

    @property
    def current_checkpoint(self) -> str:
        with self._lock:
            return self._checkpoint

    def _run(self) -> None:
        while not self._stop_event.wait(timeout=self._heartbeat_seconds):
            elapsed_seconds = self.elapsed_seconds
            checkpoint = self.current_checkpoint
            self._emit(
                f"heartbeat checkpoint={checkpoint} elapsed_seconds={elapsed_seconds}"
            )
            if elapsed_seconds >= self._timeout_seconds:
                self._emit(
                    f"timeout_dump checkpoint={checkpoint} elapsed_seconds={elapsed_seconds}"
                )
                self._timeout_event.set()
                if self._hard_timeout_exit:
                    self._emit(
                        "hard_timeout_exit_requested_but_suppressed=True "
                        f"checkpoint={checkpoint} elapsed_seconds={elapsed_seconds}"
                    )
                return

    def _emit(self, message: str) -> None:
        if self._progress_sink is not None:
            self._progress_sink(message)


@dataclass(slots=True, frozen=True)
class BybitArchiveBulkMaterializationRequest:
    contour: BybitTradeBackfillContour
    symbols: tuple[str, ...]
    observed_at: datetime
    window_hours: int = 24
    scope: str | None = None
    heartbeat_seconds: int = 10
    timeout_seconds: int = 120
    hard_timeout_exit: bool = False

    def __post_init__(self) -> None:
        if not self.symbols:
            raise ValueError("symbols не может быть пустым")
        if self.window_hours != 24:
            raise ValueError("первый working slice поддерживает только window_hours=24")
        if self.heartbeat_seconds <= 0:
            raise ValueError("heartbeat_seconds должен быть положительным")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds должен быть положительным")
        object.__setattr__(self, "observed_at", self.observed_at.astimezone(UTC))


@dataclass(slots=True, frozen=True)
class BybitArchiveBulkMaterializationReport:
    status: BybitArchiveBulkMaterializationStatus
    contour: str
    symbols: tuple[str, ...]
    observed_at: datetime
    restored_window_started_at: datetime | None
    covered_until_at: datetime | None
    processed_archives: int
    total_archives: int
    written_archive_records: int = 0
    skipped_archive_records: int = 0
    converged_pairs: int = 0
    removed_live_only_records: int = 0
    reason: str | None = None
    failure_stage: str | None = None


class BybitArchiveBulkMaterializer:
    def __init__(
        self,
        *,
        repository: IBybitTradeLedgerRepository,
        progress_sink: Callable[[str], None] | None = None,
    ) -> None:
        self._repository = repository
        self._progress_sink = progress_sink

    async def materialize_result(
        self,
        *,
        contour: str,
        symbols: tuple[str, ...],
        observed_at: datetime,
        result: BybitHistoricalTradeBackfillResult,
        timeout_checker: Callable[[], None] | None = None,
        per_step_timeout_seconds: int | None = None,
    ) -> BybitArchiveBulkMaterializationReport:
        if result.restored_window_started_at is None or result.covered_until_at is None:
            return BybitArchiveBulkMaterializationReport(
                status="skipped",
                contour=contour,
                symbols=symbols,
                observed_at=observed_at.astimezone(UTC),
                restored_window_started_at=result.restored_window_started_at,
                covered_until_at=result.covered_until_at,
                processed_archives=result.processed_archives,
                total_archives=result.total_archives,
                reason=result.reason or "archive_window_unavailable",
            )

        written_archive_records = 0
        skipped_archive_records = 0
        converged_pairs = 0
        removed_live_only_records = 0
        first_batch_finished = False

        for symbol, extractions in result.archive_trade_extractions_by_symbol.items():
            if timeout_checker is not None:
                timeout_checker()
            if not extractions:
                continue
            self._emit(
                "[archive-materialize] "
                f"checkpoint=symbol_batch_started symbol={symbol} extractions={len(extractions)}"
            )
            self._emit(
                "[archive-materialize] "
                f"checkpoint=existing_rows_load_started symbol={symbol} extractions={len(extractions)}"
            )
            try:
                prefetch = await asyncio.wait_for(
                    self._repository.prefetch_materialization_window(
                        exchange="bybit",
                        contour=contour,
                        normalized_symbol=symbol,
                        window_started_at=result.restored_window_started_at,
                        window_ended_at=result.covered_until_at,
                    ),
                    timeout=per_step_timeout_seconds,
                )
            except asyncio.TimeoutError as exc:
                raise TimeoutError("existing_rows_load_timeout") from exc
            if timeout_checker is not None:
                timeout_checker()
            existing_rows = prefetch.live_rows
            self._emit(
                "[archive-materialize] "
                f"checkpoint=existing_rows_load_finished symbol={symbol} "
                f"extractions={len(extractions)} existing_rows={len(existing_rows)}"
            )
            archive_source_identities = set(prefetch.archive_source_identities)
            live_candidates: list[BybitLiveOverlapCandidate] = [
                (index, *candidate)
                for index, candidate in enumerate(
                    (_build_live_overlap_candidate(row=row) for row in existing_rows)
                )
                if candidate is not None
            ]
            live_candidates_by_time: dict[datetime, list[BybitLiveOverlapCandidate]] = {}
            live_candidates_by_shape: dict[
                tuple[datetime, str, object, object],
                list[BybitLiveOverlapCandidate],
            ] = {}
            live_candidates_by_trade_id: dict[str, list[BybitLiveOverlapCandidate]] = {}
            live_candidates_by_index = {candidate[0]: candidate for candidate in live_candidates}
            unmatched_live_indices = {candidate[0] for candidate in live_candidates}
            for candidate in live_candidates:
                index, live_record, _, _ = candidate
                trade_at = getattr(live_record, "exchange_trade_at", None)
                side = getattr(live_record, "side", None)
                normalized_price = getattr(live_record, "normalized_price", None)
                normalized_size = getattr(live_record, "normalized_size", None)
                source_metadata = getattr(live_record, "source_metadata", {})
                live_trade_id = (
                    source_metadata.get("live_trade_id")
                    if isinstance(source_metadata, dict)
                    else None
                )
                if isinstance(trade_at, datetime):
                    live_candidates_by_time.setdefault(trade_at, []).append(candidate)
                    if (
                        isinstance(side, str)
                        and normalized_price is not None
                        and normalized_size is not None
                    ):
                        live_candidates_by_shape.setdefault(
                            (trade_at, side, normalized_price, normalized_size),
                            [],
                        ).append(candidate)
                if isinstance(live_trade_id, str) and live_trade_id:
                    live_candidates_by_trade_id.setdefault(live_trade_id, []).append(candidate)

            self._emit(
                "[archive-materialize] "
                f"symbol={symbol} extractions={len(extractions)} existing_rows={len(existing_rows)}"
            )

            for extraction in extractions:
                if timeout_checker is not None:
                    timeout_checker()
                archive_source_identity = build_bybit_archive_source_trade_identity(extraction)
                if (
                    archive_source_identity is None
                    or archive_source_identity in archive_source_identities
                ):
                    skipped_archive_records += 1
                    continue
                archive_identity = build_bybit_trade_identity(extraction)
                if archive_identity.verdict == "not_identifiable":
                    skipped_archive_records += 1
                    continue

                self._emit(
                    "[archive-materialize] "
                    f"checkpoint=archive_write_started symbol={symbol} "
                    f"source_trade_identity={archive_source_identity}"
                )
                archive_write_result = await write_archive_trade_fact_to_ledger(
                    extraction=extraction,
                    identity=archive_identity,
                    repository=self._repository,
                )
                if timeout_checker is not None:
                    timeout_checker()
                self._emit(
                    "[archive-materialize] "
                    f"checkpoint=archive_write_finished symbol={symbol} "
                    f"source_trade_identity={archive_source_identity} "
                    f"record_written={archive_write_result.record is not None}"
                )
                archive_record = archive_write_result.record
                if archive_record is None:
                    skipped_archive_records += 1
                    continue
                written_archive_records += 1

                archive_trade_at = None
                archive_side = None
                archive_price = None
                archive_size = None
                archive_trade_id = None
                if extraction.trade_fact is not None:
                    archive_trade_at = extraction.trade_fact.exchange_trade_at
                    archive_side = extraction.trade_fact.side
                    archive_price = extraction.trade_fact.normalized_price
                    archive_size = extraction.trade_fact.normalized_size
                    archive_trade_id = extraction.trade_fact.archive_trade_id

                if isinstance(archive_trade_id, str) and archive_trade_id:
                    candidate_pool = _filter_unmatched_candidates(
                        live_candidates_by_trade_id.get(archive_trade_id, []),
                        unmatched_live_indices=unmatched_live_indices,
                    )
                elif (
                    isinstance(archive_trade_at, datetime)
                    and isinstance(archive_side, str)
                    and archive_price is not None
                    and archive_size is not None
                ):
                    candidate_pool = _filter_unmatched_candidates(
                        live_candidates_by_shape.get(
                            (archive_trade_at, archive_side, archive_price, archive_size),
                            [],
                        ),
                        unmatched_live_indices=unmatched_live_indices,
                    )
                elif isinstance(archive_trade_at, datetime):
                    candidate_pool = _filter_unmatched_candidates(
                        live_candidates_by_time.get(archive_trade_at, []),
                        unmatched_live_indices=unmatched_live_indices,
                    )
                else:
                    candidate_pool = [
                        live_candidates_by_index[index]
                        for index in unmatched_live_indices
                    ]

                matched_candidate = _select_live_overlap_candidate(
                    archive_extraction=extraction,
                    archive_identity=archive_identity,
                    live_candidates=candidate_pool,
                )
                if matched_candidate is not None:
                    match_index, live_record, overlap_result = matched_candidate
                    self._emit(
                        "[archive-materialize] "
                        f"checkpoint=converge_started symbol={symbol} "
                        f"source_trade_identity={archive_source_identity}"
                    )
                    await self._repository.converge_trade_fact_pair(
                        archive_record=archive_record,
                        live_record=live_record,
                        overlap_result=overlap_result,
                    )
                    if timeout_checker is not None:
                        timeout_checker()
                    self._emit(
                        "[archive-materialize] "
                        f"checkpoint=converge_finished symbol={symbol} "
                        f"source_trade_identity={archive_source_identity}"
                    )
                    unmatched_live_indices.discard(match_index)
                    converged_pairs += 1
                archive_source_identities.add(archive_source_identity)

            for index in tuple(unmatched_live_indices):
                if timeout_checker is not None:
                    timeout_checker()
                _, live_record, _, _ = live_candidates_by_index[index]
                await self._repository.delete_trade_fact(
                    exchange=str(getattr(live_record, "exchange")),
                    contour=str(getattr(live_record, "contour")),
                    identity_contract_version=int(getattr(live_record, "identity_contract_version")),
                    canonical_dedup_identity=str(getattr(live_record, "canonical_dedup_identity")),
                )
                removed_live_only_records += 1
            if not first_batch_finished:
                self._emit(
                    f"checkpoint=materialization_first_batch_finished symbol={symbol}"
                )
                first_batch_finished = True

        return BybitArchiveBulkMaterializationReport(
            status="completed",
            contour=contour,
            symbols=symbols,
            observed_at=observed_at.astimezone(UTC),
            restored_window_started_at=result.restored_window_started_at,
            covered_until_at=result.covered_until_at,
            processed_archives=result.processed_archives,
            total_archives=result.total_archives,
            written_archive_records=written_archive_records,
            skipped_archive_records=skipped_archive_records,
            converged_pairs=converged_pairs,
            removed_live_only_records=removed_live_only_records,
            reason=result.reason,
        )

    def _emit(self, message: str) -> None:
        if self._progress_sink is not None:
            self._progress_sink(message)


async def run_bybit_archive_bulk_materialization(
    request: BybitArchiveBulkMaterializationRequest,
    *,
    progress_sink: Callable[[str], None] | None = None,
) -> BybitArchiveBulkMaterializationReport:
    monitor = _CheckpointMonitor(
        progress_sink=progress_sink,
        heartbeat_seconds=request.heartbeat_seconds,
        timeout_seconds=request.timeout_seconds,
        hard_timeout_exit=request.hard_timeout_exit,
    )
    monitor.start()
    db_manager = DatabaseManager()
    plan = None
    load_result: BybitHistoricalTradeBackfillResult | None = None
    try:
        await db_manager.connect()
        if db_manager.pool is None:
            raise RuntimeError("pool недоступен для bybit_trade_ledger")
        repository = BybitTradeLedgerRepository(db_manager.pool)
        backfill_service = create_bybit_historical_trade_backfill_service(
            contour=request.contour,
            diagnostic_callback=progress_sink,
        )
        monitor.emit_checkpoint("service_created")
        plan = backfill_service.build_recovery_plan(
            symbols=request.symbols,
            observed_at=request.observed_at,
            covered_until_at=request.observed_at,
        )
        monitor.emit_checkpoint("plan_built")
        if progress_sink is not None:
            progress_sink(
                "[archive-load] "
                f"contour={request.contour} symbols={','.join(request.symbols)} "
                f"observed_at={request.observed_at.isoformat()} total_archives={plan.total_archives}"
            )
        monitor.raise_if_timed_out()
        monitor.emit_checkpoint("load_plan_started")
        load_result = backfill_service.load_materialization_plan(
            plan=plan,
            progress_callback=(
                None
                if progress_sink is None
                else lambda processed, total: progress_sink(
                    f"[archive-load] progress={processed}/{total}"
                )
            ),
        )
        monitor.raise_if_timed_out()
        monitor.emit_checkpoint("load_plan_finished")
        materializer = BybitArchiveBulkMaterializer(
            repository=repository,
            progress_sink=progress_sink,
        )
        monitor.emit_checkpoint("materialization_started")
        report = await materializer.materialize_result(
            contour=request.contour,
            symbols=request.symbols,
            observed_at=request.observed_at,
            result=load_result,
            timeout_checker=monitor.raise_if_timed_out,
            per_step_timeout_seconds=request.timeout_seconds,
        )
        monitor.raise_if_timed_out()
        monitor.emit_checkpoint("materialization_finished")
        return report
    except TimeoutError as exc:
        stage = str(exc)
        if stage != "existing_rows_load_timeout":
            stage = None
        return BybitArchiveBulkMaterializationReport(
            status="timed_out",
            contour=request.contour,
            symbols=request.symbols,
            observed_at=request.observed_at.astimezone(UTC),
            restored_window_started_at=(
                load_result.restored_window_started_at if load_result is not None else None
            ),
            covered_until_at=(
                load_result.covered_until_at if load_result is not None else None
            ),
            processed_archives=(
                load_result.processed_archives if load_result is not None else 0
            ),
            total_archives=(
                load_result.total_archives
                if load_result is not None
                else (plan.total_archives if plan is not None else 0)
            ),
            reason=str(exc),
            failure_stage=stage,
        )
    finally:
        await db_manager.disconnect()
        monitor.stop()


def _archive_source_trade_identities_from_rows(*, rows: tuple[object, ...]) -> set[str]:
    identities: set[str] = set()
    for row in rows:
        source = getattr(row, "source", None)
        source_trade_identity = getattr(row, "source_trade_identity", None)
        if source == "bybit_public_archive" and isinstance(source_trade_identity, str):
            identities.add(source_trade_identity)
        provenance_metadata = getattr(row, "provenance_metadata", {})
        if not isinstance(provenance_metadata, dict):
            continue
        archive_metadata = provenance_metadata.get("archive")
        if not isinstance(archive_metadata, dict):
            continue
        provenance_source_trade_identity = archive_metadata.get("source_trade_identity")
        if isinstance(provenance_source_trade_identity, str):
            identities.add(provenance_source_trade_identity)
    return identities


def _build_live_overlap_candidate(
    *,
    row: object,
) -> tuple[object, BybitLiveTradeFactBuildResult, object] | None:
    if getattr(row, "source", None) != "live_public_trade":
        return None
    source_metadata = getattr(row, "source_metadata", {})
    if not isinstance(source_metadata, dict):
        return None
    live_trade_id = source_metadata.get("live_trade_id")
    if not isinstance(live_trade_id, str) or not live_trade_id:
        return None
    live_fact_result = BybitLiveTradeFactBuildResult(
        status="full_mappable",
        trade_fact=BybitLiveTradeFact(
            contour=str(getattr(row, "contour")),
            normalized_symbol=str(getattr(row, "normalized_symbol")),
            exchange_trade_at=getattr(row, "exchange_trade_at"),
            side=str(getattr(row, "side")),
            normalized_price=getattr(row, "normalized_price"),
            normalized_size=getattr(row, "normalized_size"),
            live_trade_id=live_trade_id,
            is_buyer_maker=False,
            raw_fields={},
            identity_strength="strong_candidate",
        ),
    )
    live_identity = build_bybit_live_trade_identity(live_fact_result)
    return row, live_fact_result, live_identity


def _filter_unmatched_candidates(
    candidates: list[BybitLiveOverlapCandidate],
    *,
    unmatched_live_indices: set[int],
) -> list[BybitLiveOverlapCandidate]:
    return [
        candidate
        for candidate in candidates
        if candidate[0] in unmatched_live_indices
    ]


def _select_live_overlap_candidate(
    *,
    archive_extraction,
    archive_identity,
    live_candidates: list[BybitLiveOverlapCandidate],
) -> tuple[int, BybitTradeLedgerRecord, object] | None:
    exact_matches: list[tuple[int, BybitTradeLedgerRecord, object]] = []
    fallback_matches: list[tuple[int, BybitTradeLedgerRecord, object]] = []
    ambiguous_found = False
    for index, live_record, live_fact_result, live_identity in live_candidates:
        overlap_result = compare_archive_and_live_trade(
            archive_extraction=archive_extraction,
            archive_identity=archive_identity,
            live_fact_result=live_fact_result,
            live_identity=live_identity,
        )
        if overlap_result.verdict == "exact_match_candidate":
            exact_matches.append((index, live_record, overlap_result))
        elif overlap_result.verdict == "fallback_match_candidate":
            fallback_matches.append((index, live_record, overlap_result))
        elif overlap_result.verdict == "ambiguous":
            ambiguous_found = True
    if not ambiguous_found and len(exact_matches) == 1:
        return exact_matches[0]
    if not ambiguous_found and not exact_matches and len(fallback_matches) == 1:
        return fallback_matches[0]
    return None


def _resolve_symbols(*, symbols: list[str] | None, scope: str | None) -> tuple[str, ...]:
    if symbols:
        return tuple(_normalize_cli_symbol(symbol) for symbol in symbols)
    if scope is None:
        raise ValueError("нужно указать --symbol или --scope")
    normalized_scope = scope.strip()
    if not normalized_scope.startswith("symbols:"):
        raise ValueError("scope поддерживается только формата symbols:BTC/USDT,ETH/USDT")
    payload = normalized_scope.removeprefix("symbols:")
    resolved = tuple(
        _normalize_cli_symbol(symbol)
        for symbol in payload.split(",")
        if symbol.strip()
    )
    if not resolved:
        raise ValueError("scope не содержит symbols")
    return resolved


def _normalize_cli_symbol(symbol: str) -> str:
    normalized = str(symbol).strip().upper()
    if not normalized:
        raise ValueError("symbol не может быть пустым")
    if "/" in normalized:
        return normalized
    if normalized.endswith("USDT") and len(normalized) > 4:
        return f"{normalized[:-4]}/USDT"
    if normalized.endswith("USDC") and len(normalized) > 4:
        return f"{normalized[:-4]}/USDC"
    return normalized


def _parse_datetime(value: str) -> datetime:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    return datetime.fromisoformat(normalized).astimezone(UTC)


def _parse_args(argv: list[str] | None = None) -> BybitArchiveBulkMaterializationRequest:
    parser = argparse.ArgumentParser(
        prog="python -m cryptotechnolog.live_feed.bybit_archive_bulk_materialization",
    )
    parser.add_argument("--contour", choices=("linear", "spot"), required=True)
    scope_group = parser.add_mutually_exclusive_group(required=True)
    scope_group.add_argument("--symbol", action="append", dest="symbols")
    scope_group.add_argument("--scope")
    parser.add_argument("--observed-at", required=True)
    parser.add_argument("--window-hours", type=int, default=24)
    parser.add_argument("--heartbeat-seconds", type=int, default=10)
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--hard-timeout-exit", action="store_true")
    args = parser.parse_args(argv)
    return BybitArchiveBulkMaterializationRequest(
        contour=args.contour,
        symbols=_resolve_symbols(symbols=args.symbols, scope=args.scope),
        observed_at=_parse_datetime(args.observed_at),
        window_hours=args.window_hours,
        scope=args.scope,
        heartbeat_seconds=args.heartbeat_seconds,
        timeout_seconds=args.timeout_seconds,
        hard_timeout_exit=bool(args.hard_timeout_exit),
    )


def _print_progress(message: str) -> None:
    print(message, flush=True)


async def _async_main(argv: list[str] | None = None) -> int:
    request = _parse_args(argv)
    report = await run_bybit_archive_bulk_materialization(
        request,
        progress_sink=_print_progress,
    )
    print(
        "[archive-materialize] "
        f"status={report.status} contour={report.contour} symbols={','.join(report.symbols)} "
        f"written={report.written_archive_records} skipped={report.skipped_archive_records} "
        f"converged={report.converged_pairs} removed_live_only={report.removed_live_only_records} "
        f"processed_archives={report.processed_archives}/{report.total_archives}",
        flush=True,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(_async_main(argv))


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any


def _spot_snapshot_trade_count(snapshot: object, attr: str) -> int:
    value = getattr(snapshot, attr, 0)
    return int(value) if isinstance(value, int) else 0


def _spot_snapshot_datetime(snapshot: object, attr: str) -> datetime | None:
    value = getattr(snapshot, attr, None)
    return value if isinstance(value, datetime) else None


def _spot_snapshot_persisted_total(snapshot: object) -> int:
    value = getattr(snapshot, "persisted_trade_count_24h", 0)
    return int(value) if isinstance(value, int) else 0


def _resolve_exact_window_coverage_status(
    *,
    observed_at: datetime,
    window_started_at: datetime,
    live_trade_count_24h: int,
    archive_trade_count_24h: int,
    symbol_coverage_statuses: tuple[str, ...] = (),
) -> str:
    archive_needed_until_at = observed_at.astimezone(UTC).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    if (
        window_started_at.astimezone(UTC) < archive_needed_until_at
        and archive_trade_count_24h == 0
        and live_trade_count_24h > 0
    ):
        return "pending_archive"
    if any(status == "pending_archive" for status in symbol_coverage_statuses):
        return "pending_archive"
    if live_trade_count_24h > 0 and archive_trade_count_24h > 0:
        return "hybrid"
    if archive_trade_count_24h > 0:
        return "archive_only"
    if live_trade_count_24h > 0:
        return "live_only"
    return "empty"


def _resolve_display_trade_count_for_snapshot(
    *,
    symbol: str,
    truth_trade_counts: dict[str, int],
    exact_snapshot: Any,
    module: Any,
) -> int | None:
    _ = (symbol, truth_trade_counts, module)
    exact_trade_count = int(getattr(exact_snapshot, "persisted_trade_count_24h", 0))
    return exact_trade_count


def _snapshot_passes_final_trade_filter_for_publication(
    *,
    exact_snapshot: Any,
    min_trade_count_24h: int,
    module: Any,
) -> bool:
    coverage_status = str(getattr(exact_snapshot, "coverage_status", "empty"))
    if module.is_snapshot_coverage_incomplete(coverage_status=coverage_status):
        return False
    exact_trade_count = int(getattr(exact_snapshot, "persisted_trade_count_24h", 0))
    if min_trade_count_24h > 0:
        return exact_trade_count >= min_trade_count_24h
    return exact_trade_count > 0 or coverage_status != "empty"


def _build_published_symbol_set_for_snapshots(
    *,
    candidate_symbols: tuple[str, ...],
    exact_trade_by_symbol: dict[str, Any],
    min_trade_count_24h: int,
    module: Any,
) -> tuple[str, ...]:
    return tuple(
        symbol
        for symbol in candidate_symbols
        if (
            (symbol_snapshot := exact_trade_by_symbol.get(symbol)) is not None
            and _snapshot_passes_final_trade_filter_for_publication(
                exact_snapshot=symbol_snapshot,
                min_trade_count_24h=min_trade_count_24h,
                module=module,
            )
        )
    )


def _build_published_snapshot_contract(
    *,
    candidate_symbols: tuple[str, ...],
    exact_trade_by_symbol: dict[str, Any],
    volume_by_symbol: dict[str, object],
    min_trade_count_24h: int,
    module: Any,
    observed_at: datetime,
) -> tuple[tuple[str, ...], list[dict[str, object]], dict[str, object]]:
    published_symbols = _build_published_symbol_set_for_snapshots(
        candidate_symbols=candidate_symbols,
        exact_trade_by_symbol=exact_trade_by_symbol,
        min_trade_count_24h=min_trade_count_24h,
        module=module,
    )
    instrument_rows = [
        {
            "symbol": symbol,
            "volume_24h_usd": volume_by_symbol.get(symbol),
            "trade_count_24h": _resolve_display_trade_count_for_snapshot(
                symbol=symbol,
                truth_trade_counts={},
                exact_snapshot=exact_trade_by_symbol[symbol],
                module=module,
            ),
        }
        for symbol in published_symbols
    ]
    live_total = 0
    archive_total = 0
    earliest_trade_at: datetime | None = None
    latest_trade_at: datetime | None = None
    for symbol in published_symbols:
        symbol_snapshot = exact_trade_by_symbol[symbol]
        live_total += _spot_snapshot_trade_count(symbol_snapshot, "live_trade_count_24h")
        archive_total += _spot_snapshot_trade_count(symbol_snapshot, "archive_trade_count_24h")
        symbol_earliest = _spot_snapshot_datetime(symbol_snapshot, "earliest_trade_at")
        symbol_latest = _spot_snapshot_datetime(symbol_snapshot, "latest_trade_at")
        if earliest_trade_at is None or (
            symbol_earliest is not None and symbol_earliest < earliest_trade_at
        ):
            earliest_trade_at = symbol_earliest
        if latest_trade_at is None or (
            symbol_latest is not None and symbol_latest > latest_trade_at
        ):
            latest_trade_at = symbol_latest
    persisted_total = live_total + archive_total
    if persisted_total == 0:
        persisted_total = sum(
            _spot_snapshot_persisted_total(exact_trade_by_symbol[symbol])
            for symbol in published_symbols
        )
    coverage_status = _resolve_exact_window_coverage_status(
        observed_at=observed_at,
        window_started_at=observed_at - timedelta(hours=24),
        live_trade_count_24h=live_total,
        archive_trade_count_24h=archive_total,
        symbol_coverage_statuses=tuple(
            str(getattr(exact_trade_by_symbol[symbol], "coverage_status", "empty"))
            for symbol in published_symbols
        ),
    )
    instrument_rows = _mask_trade_counts_for_pending_archive(
        instrument_rows=instrument_rows,
        coverage_status=coverage_status,
    )
    return published_symbols, instrument_rows, {
        "live_trade_count_24h": live_total,
        "archive_trade_count_24h": archive_total,
        "persisted_trade_count_24h": persisted_total,
        "first_persisted_trade_at": earliest_trade_at.isoformat() if earliest_trade_at else None,
        "last_persisted_trade_at": latest_trade_at.isoformat() if latest_trade_at else None,
        "coverage_status": coverage_status,
    }


def _published_snapshot_contract_is_consistent(
    *,
    published_symbols: tuple[str, ...],
    instrument_rows: list[dict[str, object]],
    min_trade_count_24h: int,
    coverage_status: str,
) -> bool:
    row_symbols = tuple(
        str(row.get("symbol"))
        for row in instrument_rows
        if isinstance(row, dict) and isinstance(row.get("symbol"), str)
    )
    if row_symbols != published_symbols:
        return False
    if coverage_status == "pending_archive":
        return all(
            isinstance(row, dict) and row.get("trade_count_24h") is None
            for row in instrument_rows
        )
    for row in instrument_rows:
        if not isinstance(row, dict):
            return False
        trade_count = row.get("trade_count_24h")
        if trade_count is None:
            continue
        if not isinstance(trade_count, int):
            return False
        if min_trade_count_24h > 0 and trade_count < min_trade_count_24h:
            return False
    return True


def _build_fallback_snapshot_contract(
    *,
    provisional_symbols: tuple[str, ...],
    volume_by_symbol: dict[str, object],
    module: Any,
) -> tuple[tuple[str, ...], list[dict[str, object]], dict[str, object]]:
    coverage_status = (
        "pending_recovery"
        if module.is_trade_truth_coverage_incomplete()
        else "pending_live"
    )
    instrument_rows = [
        {
            "symbol": symbol,
            "volume_24h_usd": volume_by_symbol.get(symbol),
            "trade_count_24h": None,
        }
        for symbol in provisional_symbols
    ]
    return provisional_symbols, instrument_rows, {
        "live_trade_count_24h": 0,
        "archive_trade_count_24h": 0,
        "persisted_trade_count_24h": 0,
        "first_persisted_trade_at": None,
        "last_persisted_trade_at": None,
        "coverage_status": coverage_status,
    }


def _fallback_snapshot_contract_is_consistent(
    *,
    provisional_symbols: tuple[str, ...],
    instrument_rows: list[dict[str, object]],
) -> bool:
    row_symbols = tuple(
        str(row.get("symbol"))
        for row in instrument_rows
        if isinstance(row, dict) and isinstance(row.get("symbol"), str)
    )
    if row_symbols != provisional_symbols:
        return False
    return all(
        isinstance(row, dict) and row.get("trade_count_24h") is None
        for row in instrument_rows
    )


def _mask_trade_counts_for_pending_archive(
    *,
    instrument_rows: list[dict[str, object]],
    coverage_status: str,
) -> list[dict[str, object]]:
    if coverage_status != "pending_archive":
        return instrument_rows
    return [
        {
            **row,
            "trade_count_24h": None,
        }
        for row in instrument_rows
    ]

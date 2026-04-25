from __future__ import annotations


def _resolve_runtime_screen_scope_reason(
    *,
    strict_published_symbols: tuple[str, ...],
    resolved_symbols: tuple[str, ...],
    coarse_symbols: tuple[str, ...],
    screen_symbols: tuple[str, ...],
    trade_truth_incomplete: bool,
) -> str:
    if screen_symbols:
        if strict_published_symbols and screen_symbols == strict_published_symbols:
            return "strict_published_scope"
        if trade_truth_incomplete and resolved_symbols and screen_symbols == resolved_symbols:
            return "resolved_scope_pending_exact"
        if trade_truth_incomplete and coarse_symbols and screen_symbols == coarse_symbols:
            return "coarse_scope_pending_exact"
        return "screen_scope_override"
    if trade_truth_incomplete and (resolved_symbols or coarse_symbols):
        return "waiting_for_screen_scope"
    return "empty_scope"


def _build_runtime_contract_flags(
    *,
    strict_published_symbols: tuple[str, ...],
    coarse_symbols: tuple[str, ...],
    screen_symbols: tuple[str, ...],
    trade_truth_incomplete: bool,
) -> dict[str, bool]:
    return {
        "trade_truth_incomplete": trade_truth_incomplete,
        "strict_published_scope_empty": not strict_published_symbols,
        "coarse_scope_nonempty": bool(coarse_symbols),
        "screen_scope_nonempty": bool(screen_symbols),
        "empty_screen_scope_with_live_coarse_universe": (
            trade_truth_incomplete and bool(coarse_symbols) and not screen_symbols
        ),
    }


def _resolve_product_snapshot_reason(
    *,
    symbols: tuple[str, ...],
    instrument_rows: list[dict[str, object]],
    persistence_24h: dict[str, object],
    runtime_status: dict[str, object],
) -> str:
    coverage_status = (
        str(persistence_24h.get("coverage_status", "empty"))
        if isinstance(persistence_24h, dict)
        else "empty"
    )
    if symbols and coverage_status == "pending_archive":
        return "strict_published_scope_pending_archive_masked"
    if instrument_rows and all(
        isinstance(row, dict) and row.get("trade_count_24h") is None
        for row in instrument_rows
    ):
        return "fallback_provisional_scope"
    if symbols:
        return "strict_published_scope"
    runtime_filtered = (
        int(runtime_status.get("filtered_symbols_count", 0))
        if isinstance(runtime_status.get("filtered_symbols_count"), int)
        else 0
    )
    runtime_volume = (
        int(runtime_status.get("volume_filtered_symbols_count", 0))
        if isinstance(runtime_status.get("volume_filtered_symbols_count"), int)
        else 0
    )
    if runtime_filtered > 0 or runtime_volume > 0:
        return "empty_scope_with_live_runtime"
    if coverage_status == "pending_archive":
        return "pending_archive_masked_scope"
    return "empty_scope"


def _build_product_snapshot_contract_flags(
    *,
    symbols: tuple[str, ...],
    instrument_rows: list[dict[str, object]],
    persistence_24h: dict[str, object],
    runtime_status: dict[str, object],
    min_trade_count_24h: int,
) -> dict[str, bool]:
    row_symbols = tuple(
        str(row.get("symbol"))
        for row in instrument_rows
        if isinstance(row, dict) and isinstance(row.get("symbol"), str)
    )
    coverage_status = (
        str(persistence_24h.get("coverage_status", "empty"))
        if isinstance(persistence_24h, dict)
        else "empty"
    )
    numeric_rows_respect_min_trade_count = True
    pending_archive_rows_masked = True
    for row in instrument_rows:
        if not isinstance(row, dict):
            numeric_rows_respect_min_trade_count = False
            pending_archive_rows_masked = False
            continue
        trade_count = row.get("trade_count_24h")
        if coverage_status == "pending_archive" and trade_count is not None:
            pending_archive_rows_masked = False
        if trade_count is None:
            continue
        if not isinstance(trade_count, int):
            numeric_rows_respect_min_trade_count = False
            continue
        if min_trade_count_24h > 0 and trade_count < min_trade_count_24h:
            numeric_rows_respect_min_trade_count = False
    runtime_filtered = (
        int(runtime_status.get("filtered_symbols_count", 0))
        if isinstance(runtime_status.get("filtered_symbols_count"), int)
        else 0
    )
    return {
        "row_count_matches_selected_symbols_count": len(instrument_rows) == len(symbols),
        "row_symbols_match_symbols": row_symbols == symbols,
        "pending_archive_rows_masked": pending_archive_rows_masked,
        "numeric_rows_respect_min_trade_count": numeric_rows_respect_min_trade_count,
        "runtime_scope_diverges_from_snapshot": runtime_filtered > 0 and len(symbols) == 0,
    }

from __future__ import annotations


def _resolve_snapshot_selected_count(payload: dict[str, object]) -> int:
    raw_selected = payload.get("selected_symbols_count")
    if isinstance(raw_selected, int):
        return raw_selected
    raw_symbols = payload.get("symbols")
    if isinstance(raw_symbols, (list, tuple)):
        return len(raw_symbols)
    return 0


def _resolve_snapshot_symbols(payload: dict[str, object]) -> tuple[str, ...]:
    raw_symbols = payload.get("symbols")
    if not isinstance(raw_symbols, (list, tuple)):
        return ()
    return tuple(str(symbol) for symbol in raw_symbols if isinstance(symbol, str))


def _resolve_snapshot_persisted_total(payload: dict[str, object]) -> int:
    cache_persistence = payload.get("persistence_24h")
    if not isinstance(cache_persistence, dict):
        return 0
    persisted_total = cache_persistence.get("persisted_trade_count_24h", 0)
    return int(persisted_total) if isinstance(persisted_total, int) else 0


def _resolve_snapshot_row_count(payload: dict[str, object]) -> int:
    cache_rows = payload.get("instrument_rows")
    return len(cache_rows) if isinstance(cache_rows, list) else 0


def _is_product_snapshot_cache_usable(
    *,
    cache_payload: dict[str, object],
    runtime_status: dict[str, object],
) -> bool:
    runtime_lifecycle = (
        str(runtime_status.get("lifecycle_state"))
        if isinstance(runtime_status.get("lifecycle_state"), str)
        else None
    )
    cache_lifecycle = (
        str(cache_payload.get("lifecycle_state"))
        if isinstance(cache_payload.get("lifecycle_state"), str)
        else None
    )
    if runtime_lifecycle == "connected_live":
        if cache_lifecycle != "connected_live":
            return False
        runtime_selected = (
            int(runtime_status.get("selected_symbols_count", 0))
            if isinstance(runtime_status.get("selected_symbols_count"), int)
            else 0
        )
        cache_selected = _resolve_snapshot_selected_count(cache_payload)
        if runtime_selected != cache_selected:
            return False
        runtime_symbols = _resolve_snapshot_symbols(runtime_status)
        cache_symbols = _resolve_snapshot_symbols(cache_payload)
        if runtime_symbols and cache_symbols and runtime_symbols != cache_symbols:
            return False
        row_count = _resolve_snapshot_row_count(cache_payload)
        persisted_total = _resolve_snapshot_persisted_total(cache_payload)
        if runtime_selected > 0 and row_count == 0 and persisted_total == 0:
            return False
    return True

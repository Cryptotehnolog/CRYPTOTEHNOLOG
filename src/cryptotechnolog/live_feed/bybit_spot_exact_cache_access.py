from __future__ import annotations

from datetime import datetime
from typing import Any


def _get_cached_exact_trade_counts_if_usable(
    *,
    symbols: tuple[str, ...],
    observed_at: datetime,
    cache_expires_at: datetime | None,
    cached_symbols: tuple[str, ...] | None,
    cached_by_symbol: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if (
        cached_by_symbol is not None
        and cached_symbols == symbols
        and isinstance(cache_expires_at, datetime)
        and cache_expires_at > observed_at
    ):
        return cached_by_symbol
    if (
        cached_by_symbol is not None
        and isinstance(cache_expires_at, datetime)
        and cache_expires_at > observed_at
        and set(symbols).issubset(cached_by_symbol.keys())
    ):
        return {symbol: cached_by_symbol[symbol] for symbol in symbols}
    return None


def _get_publishable_exact_snapshots(
    *,
    symbols: tuple[str, ...],
    cached_exact: dict[str, Any] | None,
    latest_symbols: tuple[str, ...] | None,
    latest_snapshots: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not symbols:
        return {}
    resolved_cached_exact = cached_exact or {}
    if set(symbols).issubset(resolved_cached_exact.keys()):
        return {symbol: resolved_cached_exact[symbol] for symbol in symbols}
    resolved_latest_symbols = latest_symbols or ()
    resolved_latest_snapshots = latest_snapshots or {}
    if resolved_latest_symbols == symbols and set(symbols).issubset(resolved_latest_snapshots.keys()):
        return {symbol: resolved_latest_snapshots[symbol] for symbol in symbols}
    return None

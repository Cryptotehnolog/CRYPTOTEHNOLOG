from __future__ import annotations

from typing import Any

from cryptotechnolog.config.settings import Settings


def _resolve_spot_min_trade_count_24h(*, settings: Settings) -> int:
    return int(settings.bybit_spot_universe_min_trade_count_24h)


def _resolve_snapshot_symbols_from_truth(*, truth: Any | None, settings: Settings) -> tuple[str, ...]:
    if truth is None:
        return ()
    min_trade_count_24h = _resolve_spot_min_trade_count_24h(settings=settings)
    if min_trade_count_24h <= 0:
        coarse_symbols = getattr(truth, "coarse_selected_symbols", ()) or ()
        if coarse_symbols:
            return tuple(str(symbol) for symbol in coarse_symbols if isinstance(symbol, str))
    selected_symbols = getattr(truth, "selected_symbols", ()) or ()
    if selected_symbols:
        return tuple(str(symbol) for symbol in selected_symbols if isinstance(symbol, str))
    coarse_symbols = getattr(truth, "coarse_selected_symbols", ()) or ()
    return tuple(str(symbol) for symbol in coarse_symbols if isinstance(symbol, str))


def _resolve_fallback_snapshot_symbols_from_truth(*, truth: Any | None) -> tuple[str, ...]:
    if truth is None:
        return ()
    coarse_symbols = getattr(truth, "coarse_selected_symbols", ()) or ()
    if coarse_symbols:
        return tuple(str(symbol) for symbol in coarse_symbols if isinstance(symbol, str))
    selected_symbols = getattr(truth, "selected_symbols", ()) or ()
    return tuple(str(symbol) for symbol in selected_symbols if isinstance(symbol, str))


def _resolve_scope_trade_counts_from_truth(*, truth: Any | None) -> dict[str, int]:
    if truth is None:
        return {}
    return {
        str(symbol): int(trade_count)
        for symbol, trade_count in getattr(truth, "selected_trade_count_24h_by_symbol", ()) or ()
        if isinstance(symbol, str)
    }

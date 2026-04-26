"""Shared Bybit symbol helpers that are safe to import from multiple modules."""

from __future__ import annotations

_KNOWN_QUOTE_SUFFIXES = ("USDT", "USDC", "USD", "BTC", "ETH")
_KNOWN_PERPETUAL_SUFFIX = "PERP"


def normalize_bybit_symbol(raw_symbol: str) -> str:
    """Normalize Bybit symbol into canonical internal symbol format."""
    symbol = raw_symbol.strip().upper()
    if not symbol:
        raise ValueError("Bybit symbol не может быть пустым")
    if "/" in symbol:
        return symbol
    if symbol.endswith(_KNOWN_PERPETUAL_SUFFIX) and len(symbol) > len(_KNOWN_PERPETUAL_SUFFIX):
        base = symbol[: -len(_KNOWN_PERPETUAL_SUFFIX)]
        return f"{base}/USDC"
    for quote in _KNOWN_QUOTE_SUFFIXES:
        if symbol.endswith(quote) and len(symbol) > len(quote):
            base = symbol[: -len(quote)]
            return f"{base}/{quote}"
    raise ValueError(f"Не удалось нормализовать Bybit symbol: {raw_symbol}")


__all__ = ["normalize_bybit_symbol"]

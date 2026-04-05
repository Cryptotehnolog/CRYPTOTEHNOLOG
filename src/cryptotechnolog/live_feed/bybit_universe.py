"""Narrow Bybit universe discovery and coarse prefilter layer above connector slices."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import json
from typing import Literal
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from cryptotechnolog.config import get_settings

from .bybit import normalize_bybit_symbol

BybitMarketContour = Literal["linear", "spot"]

_BYBIT_MAINNET_REST_URL = "https://api.bybit.com"
_BYBIT_TESTNET_REST_URL = "https://api-testnet.bybit.com"


@dataclass(slots=True, frozen=True)
class BybitUniverseInstrument:
    """Single instrument candidate from Bybit universe discovery."""

    symbol: str
    quote_volume_24h_usd: Decimal
    trade_count_24h: int | None


@dataclass(slots=True, frozen=True)
class BybitUniverseSelectionSummary:
    """Operator-facing summary for universe-based scope formation."""

    scope_mode: str
    total_instruments_discovered: int | None
    instruments_passed_coarse_filter: int | None
    selected_symbols: tuple[str, ...]


@dataclass(slots=True, frozen=True)
class BybitUniverseDiscoveryConfig:
    """Coarse discovery and prefilter configuration for one Bybit market contour."""

    contour: BybitMarketContour
    rest_base_url: str
    min_quote_volume_24h_usd: float
    min_trade_count_24h: int
    max_symbols_per_scope: int

    @classmethod
    def from_settings(
        cls,
        *,
        contour: BybitMarketContour,
    ) -> BybitUniverseDiscoveryConfig:
        settings = get_settings()
        return cls(
            contour=contour,
            rest_base_url=(
                _BYBIT_TESTNET_REST_URL if settings.bybit_testnet else _BYBIT_MAINNET_REST_URL
            ),
            min_quote_volume_24h_usd=settings.bybit_universe_min_quote_volume_24h_usd,
            min_trade_count_24h=settings.bybit_universe_min_trade_count_24h,
            max_symbols_per_scope=settings.bybit_universe_max_symbols_per_scope,
        )


def discover_bybit_universe(
    config: BybitUniverseDiscoveryConfig,
) -> BybitUniverseSelectionSummary:
    """Discover Bybit instruments, apply coarse prefilter, and return selected scope."""
    discovered_symbols = _fetch_active_symbols(config)
    tickers = _fetch_ticker_stats(config)

    candidates: list[BybitUniverseInstrument] = []
    for raw_symbol in discovered_symbols:
        ticker = tickers.get(raw_symbol)
        if ticker is None:
            continue
        quote_volume_24h_usd = _decimal_or_zero(
            ticker.get("turnover24h")
            or ticker.get("quoteVolume24h")
            or ticker.get("turnover24H")
            or ticker.get("quote_volume_24h"),
        )
        trade_count_24h = _optional_int(
            ticker.get("tradeCount24h") or ticker.get("trades24h") or ticker.get("trade_count_24h"),
        )
        if quote_volume_24h_usd < Decimal(str(config.min_quote_volume_24h_usd)):
            continue
        if config.min_trade_count_24h > 0 and (
            trade_count_24h is None or trade_count_24h < config.min_trade_count_24h
        ):
            continue
        candidates.append(
            BybitUniverseInstrument(
                symbol=normalize_bybit_symbol(raw_symbol),
                quote_volume_24h_usd=quote_volume_24h_usd,
                trade_count_24h=trade_count_24h,
            )
        )

    ranked = sorted(
        candidates,
        key=lambda item: (
            item.quote_volume_24h_usd,
            item.trade_count_24h if item.trade_count_24h is not None else -1,
            item.symbol,
        ),
        reverse=True,
    )
    selected = tuple(item.symbol for item in ranked[: max(0, config.max_symbols_per_scope)])
    return BybitUniverseSelectionSummary(
        scope_mode="universe",
        total_instruments_discovered=len(discovered_symbols),
        instruments_passed_coarse_filter=len(ranked),
        selected_symbols=selected,
    )


def _fetch_active_symbols(config: BybitUniverseDiscoveryConfig) -> tuple[str, ...]:
    items = _fetch_paginated_list(
        base_url=config.rest_base_url,
        path="/v5/market/instruments-info",
        params={"category": config.contour},
    )
    active_symbols: list[str] = []
    for item in items:
        raw_symbol = item.get("symbol")
        if not isinstance(raw_symbol, str) or not raw_symbol.strip():
            continue
        raw_status = str(item.get("status", item.get("symbolStatus", "Trading"))).strip().lower()
        if raw_status and raw_status not in {"trading", "tradable", "listed"}:
            continue
        active_symbols.append(raw_symbol)
    return tuple(dict.fromkeys(active_symbols))


def _fetch_ticker_stats(config: BybitUniverseDiscoveryConfig) -> dict[str, dict[str, object]]:
    payload = _fetch_json(
        base_url=config.rest_base_url,
        path="/v5/market/tickers",
        params={"category": config.contour},
    )
    result = payload.get("result")
    if not isinstance(result, dict):
        return {}
    raw_list = result.get("list")
    if not isinstance(raw_list, list):
        return {}
    tickers: dict[str, dict[str, object]] = {}
    for item in raw_list:
        if not isinstance(item, dict):
            continue
        raw_symbol = item.get("symbol")
        if not isinstance(raw_symbol, str) or not raw_symbol.strip():
            continue
        tickers[raw_symbol] = item
    return tickers


def _fetch_paginated_list(
    *,
    base_url: str,
    path: str,
    params: dict[str, object],
) -> list[dict[str, object]]:
    cursor: str | None = None
    aggregated: list[dict[str, object]] = []
    while True:
        request_params = dict(params)
        if cursor:
            request_params["cursor"] = cursor
        payload = _fetch_json(base_url=base_url, path=path, params=request_params)
        result = payload.get("result")
        if not isinstance(result, dict):
            break
        raw_items = result.get("list")
        if isinstance(raw_items, list):
            aggregated.extend(item for item in raw_items if isinstance(item, dict))
        next_cursor = result.get("nextPageCursor")
        cursor = next_cursor if isinstance(next_cursor, str) and next_cursor.strip() else None
        if cursor is None:
            break
    return aggregated


def _fetch_json(
    *,
    base_url: str,
    path: str,
    params: dict[str, object],
) -> dict[str, object]:
    query = urlencode(params)
    url = f"{base_url}{path}?{query}" if query else f"{base_url}{path}"
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "cryptotechnolog/bybit-universe-discovery",
        },
    )
    with urlopen(request, timeout=15) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Bybit universe discovery вернул не-object JSON payload")
    ret_code = payload.get("retCode")
    if ret_code not in {0, "0", None}:
        raise ValueError(f"Bybit universe discovery failed: retCode={ret_code}")
    return payload


def _decimal_or_zero(raw_value: object) -> Decimal:
    if raw_value is None:
        return Decimal("0")
    try:
        return Decimal(str(raw_value))
    except (ArithmeticError, InvalidOperation, ValueError):
        return Decimal("0")


def _optional_int(raw_value: object) -> int | None:
    if raw_value is None:
        return None
    normalized = str(raw_value).strip()
    if not normalized:
        return None
    try:
        return int(normalized)
    except ValueError:
        return None


__all__ = [
    "BybitMarketContour",
    "BybitUniverseDiscoveryConfig",
    "BybitUniverseInstrument",
    "BybitUniverseSelectionSummary",
    "discover_bybit_universe",
]

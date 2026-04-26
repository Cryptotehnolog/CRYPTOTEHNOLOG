"""Narrow Bybit universe discovery and coarse prefilter layer above connector slices."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import json
from typing import Literal
from urllib.parse import urlencode, urlsplit
from urllib.request import ProxyHandler, Request, build_opener, urlopen

from cryptotechnolog.config import get_settings

from .bybit_symbols import normalize_bybit_symbol

BybitMarketContour = Literal["linear", "spot"]
BybitSpotQuoteAssetFilter = Literal["usdt", "usdc", "usdt_usdc"]

_BYBIT_MAINNET_REST_URL = "https://api.bybit.com"
_BYBIT_TESTNET_REST_URL = "https://api-testnet.bybit.com"
_BYBIT_DISCOVERY_DIRECT_HOSTS = ("api.bybit.com", "api-testnet.bybit.com")


@dataclass(slots=True, frozen=True)
class BybitUniverseInstrument:
    """Single instrument candidate from Bybit universe discovery."""

    symbol: str
    quote_volume_24h_usd: Decimal
    has_recent_trading_24h: bool


@dataclass(slots=True, frozen=True)
class BybitUniverseSelectionSummary:
    """Operator-facing summary for universe-based scope formation."""

    scope_mode: str
    total_instruments_discovered: int | None
    instruments_passed_coarse_filter: int | None
    selected_symbols: tuple[str, ...]
    selected_quote_volume_24h_usd_by_symbol: tuple[tuple[str, str], ...] = ()


@dataclass(slots=True, frozen=True)
class BybitUniverseDiscoveryConfig:
    """Coarse discovery and prefilter configuration for one Bybit market contour."""

    contour: BybitMarketContour
    rest_base_url: str
    min_quote_volume_24h_usd: float
    min_trade_count_24h: int
    spot_quote_asset_filter: BybitSpotQuoteAssetFilter | None = None
    max_symbols_per_scope: int | None = None

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
            spot_quote_asset_filter=(
                settings.bybit_spot_quote_asset_filter if contour == "spot" else None
            ),
            max_symbols_per_scope=(
                settings.bybit_universe_max_symbols_per_scope if contour == "linear" else None
            ),
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
        try:
            normalized_symbol = normalize_bybit_symbol(raw_symbol)
        except ValueError:
            continue
        if config.contour == "spot" and not _spot_symbol_matches_quote_filter(
            normalized_symbol,
            config.spot_quote_asset_filter,
        ):
            continue
        quote_volume_24h_usd = _decimal_or_zero(
            ticker.get("turnover24h")
            or ticker.get("quoteVolume24h")
            or ticker.get("turnover24H")
            or ticker.get("quote_volume_24h"),
        )
        if quote_volume_24h_usd < Decimal(str(config.min_quote_volume_24h_usd)):
            continue
        traded_volume_24h = _decimal_or_zero(
            ticker.get("volume24h")
            or ticker.get("baseVolume24h")
            or ticker.get("volume24H")
            or ticker.get("base_volume_24h"),
        )
        has_recent_trading_24h = quote_volume_24h_usd > 0 or traded_volume_24h > 0
        candidates.append(
            BybitUniverseInstrument(
                symbol=normalized_symbol,
                quote_volume_24h_usd=quote_volume_24h_usd,
                has_recent_trading_24h=has_recent_trading_24h,
            )
        )

    ranked = sorted(
        candidates,
        key=lambda item: (
            item.quote_volume_24h_usd,
            item.symbol,
        ),
        reverse=True,
    )
    # Spot product filtering uses a dedicated final trade-count admission stage.
    # Keep coarse discovery as "volume-filtered universe" and do not cap the
    # user-facing spot result here.
    if config.contour == "spot":
        selected_items = ranked
    else:
        selected_items = ranked[: max(0, int(config.max_symbols_per_scope or 0))]
    selected = tuple(item.symbol for item in selected_items)
    selected_quote_volume_24h_usd_by_symbol = tuple(
        (item.symbol, str(item.quote_volume_24h_usd))
        for item in selected_items
    )
    return BybitUniverseSelectionSummary(
        scope_mode="universe",
        total_instruments_discovered=len(discovered_symbols),
        instruments_passed_coarse_filter=len(ranked),
        selected_symbols=selected,
        selected_quote_volume_24h_usd_by_symbol=selected_quote_volume_24h_usd_by_symbol,
    )


def fetch_bybit_quote_turnover_24h_by_symbol(
    *,
    contour: BybitMarketContour,
    rest_base_url: str,
    symbols: tuple[str, ...],
) -> dict[str, Decimal]:
    """Fetch current 24h quote turnover from Bybit tickers for the requested symbols."""
    if not symbols:
        return {}
    requested_symbols = {normalize_bybit_symbol(symbol) for symbol in symbols}
    tickers = _fetch_ticker_stats(
        BybitUniverseDiscoveryConfig(
            contour=contour,
            rest_base_url=rest_base_url,
            min_quote_volume_24h_usd=0,
            min_trade_count_24h=0,
            spot_quote_asset_filter=None,
        )
    )
    quote_turnover_by_symbol: dict[str, Decimal] = {}
    for raw_symbol, ticker in tickers.items():
        try:
            normalized_symbol = normalize_bybit_symbol(raw_symbol)
        except ValueError:
            continue
        if normalized_symbol not in requested_symbols:
            continue
        quote_turnover_by_symbol[normalized_symbol] = _decimal_or_zero(
            ticker.get("turnover24h")
            or ticker.get("quoteVolume24h")
            or ticker.get("turnover24H")
            or ticker.get("quote_volume_24h"),
        )
    return quote_turnover_by_symbol


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
    with _open_discovery_request(request, timeout=15) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Bybit universe discovery вернул не-object JSON payload")
    ret_code = payload.get("retCode")
    if ret_code not in {0, "0", None}:
        raise ValueError(f"Bybit universe discovery failed: retCode={ret_code}")
    return payload


def _open_discovery_request(request: Request, *, timeout: int):
    host = urlsplit(request.full_url).hostname
    if host in _BYBIT_DISCOVERY_DIRECT_HOSTS:
        opener = build_opener(ProxyHandler({}))
        return opener.open(request, timeout=timeout)
    return urlopen(request, timeout=timeout)


def _decimal_or_zero(raw_value: object) -> Decimal:
    if raw_value is None:
        return Decimal("0")
    try:
        return Decimal(str(raw_value))
    except (ArithmeticError, InvalidOperation, ValueError):
        return Decimal("0")


def _spot_symbol_matches_quote_filter(
    normalized_symbol: str,
    quote_asset_filter: BybitSpotQuoteAssetFilter | None,
) -> bool:
    if quote_asset_filter in (None, "usdt_usdc"):
        return normalized_symbol.endswith("/USDT") or normalized_symbol.endswith("/USDC")
    if quote_asset_filter == "usdt":
        return normalized_symbol.endswith("/USDT")
    if quote_asset_filter == "usdc":
        return normalized_symbol.endswith("/USDC")
    return False


__all__ = [
    "BybitMarketContour",
    "BybitUniverseDiscoveryConfig",
    "BybitUniverseInstrument",
    "BybitUniverseSelectionSummary",
    "discover_bybit_universe",
    "fetch_bybit_quote_turnover_24h_by_symbol",
]

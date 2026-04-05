"""
Узкий Bybit spot public market-data connector поверх existing live_feed foundations.

Этот модуль intentionally:
- выделяет отдельный spot slice без смешивания с linear/perpetual;
- переиспользует уже доказанные parser/projector/runtime pieces;
- не вводит общий Bybit framework заранее.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from cryptotechnolog.config import get_settings

from .bybit import (
    BybitMarketDataConnector,
    BybitMarketDataParser,
    BybitOrderBookProjector,
    BybitSubscriptionRegistry,
    BybitWebSocketConnection,
    normalize_bybit_symbol,
)
from .models import FeedSessionIdentity

if TYPE_CHECKING:
    from cryptotechnolog.config.settings import Settings
    from cryptotechnolog.market_data import MarketDataRuntime

_BYBIT_MAINNET_SPOT_PUBLIC_URL = "wss://stream.bybit.com/v5/public/spot"
_BYBIT_TESTNET_SPOT_PUBLIC_URL = "wss://stream-testnet.bybit.com/v5/public/spot"


@dataclass(slots=True, frozen=True)
class BybitSpotMarketDataConnectorConfig:
    """Конфигурация узкого Bybit spot public market-data slice."""

    public_stream_url: str = _BYBIT_MAINNET_SPOT_PUBLIC_URL
    orderbook_depth: int = 50
    ping_interval_seconds: int = 20
    ping_timeout_seconds: int = 20
    reconnect_delay_seconds: int = 5
    max_orderbook_levels: int = 50

    @classmethod
    def from_settings(cls, settings: Settings) -> BybitSpotMarketDataConnectorConfig:
        return cls(
            public_stream_url=(
                _BYBIT_TESTNET_SPOT_PUBLIC_URL
                if settings.bybit_testnet
                else _BYBIT_MAINNET_SPOT_PUBLIC_URL
            ),
            reconnect_delay_seconds=int(
                getattr(
                    settings,
                    "live_feed_retry_delay_seconds",
                    5,
                )
            ),
        )


class BybitSpotMarketDataConnector(BybitMarketDataConnector):
    """Отдельный Bybit spot connector slice поверх существующего runtime/parser split."""


def create_bybit_spot_market_data_connector(
    *,
    symbols: tuple[str, ...],
    market_data_runtime: MarketDataRuntime,
    config: BybitSpotMarketDataConnectorConfig | None = None,
) -> BybitSpotMarketDataConnector:
    session = FeedSessionIdentity(
        exchange="bybit_spot",
        stream_kind="market_data",
        subscription_scope=tuple(normalize_bybit_symbol(symbol) for symbol in symbols),
    )
    resolved_config = config or BybitSpotMarketDataConnectorConfig.from_settings(get_settings())
    return BybitSpotMarketDataConnector(
        session=session,
        market_data_runtime=market_data_runtime,
        config=resolved_config,
        parser=BybitMarketDataParser(max_orderbook_levels=resolved_config.max_orderbook_levels),
    )


__all__ = [
    "BybitMarketDataParser",
    "BybitOrderBookProjector",
    "BybitSpotMarketDataConnector",
    "BybitSpotMarketDataConnectorConfig",
    "BybitSubscriptionRegistry",
    "BybitWebSocketConnection",
    "create_bybit_spot_market_data_connector",
    "normalize_bybit_symbol",
]

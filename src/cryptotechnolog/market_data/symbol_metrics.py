"""
Foundation-слой расчёта symbol metrics для Phase 6.

Модуль не содержит orchestration/runtime loop.
Он детерминированно преобразует foundation market data в SymbolMetricsContract.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from .data_quality import MarketDataValidationError
from .models import OrderBookSnapshotContract, SymbolMetricsContract


@dataclass(slots=True, frozen=True)
class SymbolMetricsInput:
    """Нормализованный вход для расчёта symbol metrics."""

    symbol: str
    exchange: str
    calculated_at: datetime
    orderbook: OrderBookSnapshotContract
    last_trade_at: datetime
    tick_coverage_ratio: Decimal
    average_latency_ms: Decimal
    volume_24h_usd: Decimal | None = None
    open_interest_usd: Decimal | None = None
    funding_8h: Decimal | None = None


@dataclass(slots=True, frozen=True)
class SymbolMetricsConfig:
    """Пороговые и scoring-параметры расчёта symbol metrics."""

    depth_window_bps: Decimal = Decimal("5")
    max_freshness: timedelta = timedelta(seconds=3)
    target_latency_ms: Decimal = Decimal("150")
    target_spread_bps: Decimal = Decimal("15")
    target_top_depth_usd: Decimal = Decimal("100000")
    target_depth_window_usd: Decimal = Decimal("250000")


def clamp_decimal(value: Decimal, minimum: Decimal, maximum: Decimal) -> Decimal:
    """Ограничить decimal-значение в заданном диапазоне."""
    if value < minimum:
        return minimum
    if value > maximum:
        return maximum
    return value


def decimal_ratio(numerator: Decimal, denominator: Decimal) -> Decimal:
    """Безопасно рассчитать ratio для decimal-значений."""
    if denominator <= 0:
        return Decimal("0")
    return numerator / denominator


def calculate_depth_within_bps(
    orderbook: OrderBookSnapshotContract,
    *,
    window_bps: Decimal,
) -> Decimal:
    """Рассчитать суммарную глубину внутри окна bps от midpoint."""
    if not orderbook.bids or not orderbook.asks:
        return Decimal("0")

    best_bid = orderbook.bids[0].price
    best_ask = orderbook.asks[0].price
    midpoint = (best_bid + best_ask) / Decimal("2")
    if midpoint <= 0:
        return Decimal("0")

    bid_threshold = midpoint * (Decimal("1") - (window_bps / Decimal("10000")))
    ask_threshold = midpoint * (Decimal("1") + (window_bps / Decimal("10000")))

    bid_depth = sum(
        (level.price * level.quantity for level in orderbook.bids if level.price >= bid_threshold),
        start=Decimal("0"),
    )
    ask_depth = sum(
        (level.price * level.quantity for level in orderbook.asks if level.price <= ask_threshold),
        start=Decimal("0"),
    )
    return bid_depth + ask_depth


def calculate_top_of_book_depth(orderbook: OrderBookSnapshotContract) -> Decimal:
    """Рассчитать USD-глубину top-of-book."""
    if not orderbook.bids or not orderbook.asks:
        return Decimal("0")
    best_bid = orderbook.bids[0]
    best_ask = orderbook.asks[0]
    return (best_bid.price * best_bid.quantity) + (best_ask.price * best_ask.quantity)


class SymbolMetricsCollector:
    """Консервативный collector symbol metrics поверх foundation market data."""

    def __init__(self, config: SymbolMetricsConfig | None = None) -> None:
        self._config = config or SymbolMetricsConfig()

    @property
    def config(self) -> SymbolMetricsConfig:
        """Доступ к policy config collector-а."""
        return self._config

    def collect(self, metrics_input: SymbolMetricsInput) -> SymbolMetricsContract:
        """Построить deterministic SymbolMetricsContract из typed input."""
        if metrics_input.symbol != metrics_input.orderbook.symbol:
            raise MarketDataValidationError(
                "SymbolMetricsInput.symbol должен совпадать с orderbook.symbol"
            )
        if metrics_input.exchange != metrics_input.orderbook.exchange:
            raise MarketDataValidationError(
                "SymbolMetricsInput.exchange должен совпадать с orderbook.exchange"
            )

        calculated_at = metrics_input.calculated_at.astimezone(UTC)
        freshness_ms = int(
            (calculated_at - metrics_input.last_trade_at.astimezone(UTC)).total_seconds() * 1000
        )
        top_depth = calculate_top_of_book_depth(metrics_input.orderbook)
        depth_window = calculate_depth_within_bps(
            metrics_input.orderbook,
            window_bps=self._config.depth_window_bps,
        )
        quality_score = self._calculate_quality_score(
            spread_bps=metrics_input.orderbook.spread_bps,
            top_depth_usd=top_depth,
            depth_window_usd=depth_window,
            freshness_ms=freshness_ms,
            latency_ms=metrics_input.average_latency_ms,
            coverage_ratio=metrics_input.tick_coverage_ratio,
        )
        return SymbolMetricsContract(
            symbol=metrics_input.symbol,
            exchange=metrics_input.exchange,
            calculated_at=calculated_at,
            spread_bps=metrics_input.orderbook.spread_bps,
            top_of_book_depth_usd=top_depth,
            depth_5bps_usd=depth_window,
            latency_ms=metrics_input.average_latency_ms,
            coverage_ratio=metrics_input.tick_coverage_ratio,
            data_freshness_ms=max(freshness_ms, 0),
            quality_score=quality_score,
            funding_8h=metrics_input.funding_8h,
            volume_24h_usd=metrics_input.volume_24h_usd,
            open_interest_usd=metrics_input.open_interest_usd,
            metadata={
                "depth_window_bps": str(self._config.depth_window_bps),
                "freshness_threshold_ms": int(self._config.max_freshness.total_seconds() * 1000),
            },
        )

    def _calculate_quality_score(
        self,
        *,
        spread_bps: Decimal,
        top_depth_usd: Decimal,
        depth_window_usd: Decimal,
        freshness_ms: int,
        latency_ms: Decimal,
        coverage_ratio: Decimal,
    ) -> Decimal:
        freshness_target_ms = Decimal(str(int(self._config.max_freshness.total_seconds() * 1000)))
        spread_score = clamp_decimal(
            Decimal("1") - decimal_ratio(spread_bps, self._config.target_spread_bps),
            Decimal("0"),
            Decimal("1"),
        )
        top_depth_score = clamp_decimal(
            decimal_ratio(top_depth_usd, self._config.target_top_depth_usd),
            Decimal("0"),
            Decimal("1"),
        )
        depth_window_score = clamp_decimal(
            decimal_ratio(depth_window_usd, self._config.target_depth_window_usd),
            Decimal("0"),
            Decimal("1"),
        )
        freshness_score = clamp_decimal(
            Decimal("1") - decimal_ratio(Decimal(str(freshness_ms)), freshness_target_ms),
            Decimal("0"),
            Decimal("1"),
        )
        latency_score = clamp_decimal(
            Decimal("1") - decimal_ratio(latency_ms, self._config.target_latency_ms),
            Decimal("0"),
            Decimal("1"),
        )
        coverage_score = clamp_decimal(coverage_ratio, Decimal("0"), Decimal("1"))
        weighted_sum = (
            spread_score * Decimal("0.25")
            + top_depth_score * Decimal("0.20")
            + depth_window_score * Decimal("0.20")
            + freshness_score * Decimal("0.15")
            + latency_score * Decimal("0.10")
            + coverage_score * Decimal("0.10")
        )
        return weighted_sum.quantize(Decimal("0.0001"))

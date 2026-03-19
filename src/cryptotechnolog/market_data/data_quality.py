"""
Foundation-слой проверки качества рыночных данных.

Здесь нет orchestration и bootstrap-логики.
Модуль только формирует typed quality signals для tick/bar/orderbook path.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from .models import (
    DataQualityIssueType,
    DataQualitySeverity,
    DataQualitySignal,
    OrderBookSnapshotContract,
    TickContract,
)


class MarketDataValidationError(ValueError):
    """Ошибка валидации некорректного market data input."""


@dataclass(slots=True, frozen=True)
class DataQualityConfig:
    """Пороговые значения quality validation foundation."""

    gap_threshold: timedelta = timedelta(seconds=5)
    stale_after: timedelta = timedelta(seconds=3)
    max_price_deviation_bps: Decimal = Decimal("500")
    future_skew_tolerance: timedelta = timedelta(seconds=1)


def ensure_utc_timestamp(timestamp: datetime) -> datetime:
    """Нормализовать timestamp к aware UTC времени."""
    if timestamp.tzinfo is None:
        raise MarketDataValidationError("Timestamp market data должен быть timezone-aware")
    return timestamp.astimezone(UTC)


def calculate_price_deviation_bps(reference: Decimal, observed: Decimal) -> Decimal:
    """Рассчитать абсолютное отклонение цены в bps."""
    if reference <= 0 or observed <= 0:
        raise MarketDataValidationError("Цены для расчёта отклонения должны быть положительными")
    midpoint = (reference + observed) / Decimal("2")
    return abs((observed - reference) / midpoint) * Decimal("10000")


class DataQualityValidator:
    """Quality-aware validator для tick/orderbook/data-source foundation."""

    def __init__(self, config: DataQualityConfig | None = None) -> None:
        self._config = config or DataQualityConfig()
        self._last_tick_at: dict[tuple[str, str], datetime] = {}
        self._last_tick_price: dict[tuple[str, str], Decimal] = {}
        self._last_source_heartbeat: dict[tuple[str, str, str], datetime] = {}

    def validate_tick(
        self,
        tick: TickContract,
        *,
        now: datetime | None = None,
    ) -> tuple[DataQualitySignal, ...]:
        """Проверить tick на gap/outlier/out-of-order и обновить source heartbeat."""
        current_time = ensure_utc_timestamp(now or datetime.now(UTC))
        timestamp = ensure_utc_timestamp(tick.timestamp)
        if timestamp > current_time + self._config.future_skew_tolerance:
            raise MarketDataValidationError("Tick timestamp уходит слишком далеко в будущее")

        key = (tick.symbol, tick.exchange)
        signals: list[DataQualitySignal] = []
        previous_timestamp = self._last_tick_at.get(key)
        if previous_timestamp is not None:
            if timestamp < previous_timestamp:
                signals.append(
                    DataQualitySignal(
                        symbol=tick.symbol,
                        exchange=tick.exchange,
                        issue_type=DataQualityIssueType.OUT_OF_ORDER,
                        severity=DataQualitySeverity.WARNING,
                        detected_at=current_time,
                        feed="trades",
                        details={
                            "previous_timestamp": previous_timestamp.isoformat(),
                            "current_timestamp": timestamp.isoformat(),
                        },
                    )
                )

            gap_duration = timestamp - previous_timestamp
            if gap_duration > self._config.gap_threshold:
                signals.append(
                    DataQualitySignal(
                        symbol=tick.symbol,
                        exchange=tick.exchange,
                        issue_type=DataQualityIssueType.GAP,
                        severity=DataQualitySeverity.CRITICAL,
                        detected_at=current_time,
                        feed="trades",
                        gap_duration_ms=int(gap_duration.total_seconds() * 1000),
                        details={
                            "threshold_ms": int(self._config.gap_threshold.total_seconds() * 1000)
                        },
                    )
                )

        previous_price = self._last_tick_price.get(key)
        if previous_price is not None:
            deviation_bps = calculate_price_deviation_bps(previous_price, tick.price)
            if deviation_bps > self._config.max_price_deviation_bps:
                signals.append(
                    DataQualitySignal(
                        symbol=tick.symbol,
                        exchange=tick.exchange,
                        issue_type=DataQualityIssueType.OUTLIER,
                        severity=DataQualitySeverity.WARNING,
                        detected_at=current_time,
                        feed="trades",
                        outlier_score=deviation_bps,
                        details={
                            "previous_price": str(previous_price),
                            "current_price": str(tick.price),
                            "threshold_bps": str(self._config.max_price_deviation_bps),
                        },
                    )
                )

        self._last_tick_at[key] = timestamp
        self._last_tick_price[key] = tick.price
        self._last_source_heartbeat[(tick.symbol, tick.exchange, "trades")] = timestamp
        return tuple(signals)

    def detect_stale(
        self,
        *,
        symbol: str,
        exchange: str,
        feed: str,
        now: datetime | None = None,
    ) -> DataQualitySignal | None:
        """Проверить, не устарел ли последний heartbeat выбранного feed."""
        current_time = ensure_utc_timestamp(now or datetime.now(UTC))
        last_heartbeat = self._last_source_heartbeat.get((symbol, exchange, feed))
        if last_heartbeat is None:
            return None

        staleness = current_time - last_heartbeat
        if staleness <= self._config.stale_after:
            return None

        return DataQualitySignal(
            symbol=symbol,
            exchange=exchange,
            issue_type=DataQualityIssueType.STALE,
            severity=DataQualitySeverity.WARNING,
            detected_at=current_time,
            feed=feed,
            staleness_ms=int(staleness.total_seconds() * 1000),
            details={"threshold_ms": int(self._config.stale_after.total_seconds() * 1000)},
        )

    def validate_orderbook(
        self,
        snapshot: OrderBookSnapshotContract,
        *,
        feed: str = "orderbook",
        now: datetime | None = None,
    ) -> tuple[DataQualitySignal, ...]:
        """Проверить snapshot стакана на crossed-book и heartbeat freshness."""
        current_time = ensure_utc_timestamp(now or datetime.now(UTC))
        signals: list[DataQualitySignal] = []
        if snapshot.bids and snapshot.asks:
            best_bid = snapshot.bids[0].price
            best_ask = snapshot.asks[0].price
            if best_bid >= best_ask:
                signals.append(
                    DataQualitySignal(
                        symbol=snapshot.symbol,
                        exchange=snapshot.exchange,
                        issue_type=DataQualityIssueType.ORDERBOOK_CROSSED,
                        severity=DataQualitySeverity.CRITICAL,
                        detected_at=current_time,
                        feed=feed,
                        details={"best_bid": str(best_bid), "best_ask": str(best_ask)},
                    )
                )

        self._last_source_heartbeat[(snapshot.symbol, snapshot.exchange, feed)] = (
            ensure_utc_timestamp(snapshot.timestamp)
        )
        return tuple(signals)

    def build_source_degraded_signal(
        self,
        *,
        symbol: str,
        exchange: str,
        feed: str,
        reason: str,
        detected_at: datetime | None = None,
    ) -> DataQualitySignal:
        """Построить typed signal деградации feed/source."""
        occurred_at = ensure_utc_timestamp(detected_at or datetime.now(UTC))
        return DataQualitySignal(
            symbol=symbol,
            exchange=exchange,
            issue_type=DataQualityIssueType.SOURCE_DEGRADED,
            severity=DataQualitySeverity.CRITICAL,
            detected_at=occurred_at,
            feed=feed,
            details={"reason": reason},
        )

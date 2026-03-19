from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from cryptotechnolog.market_data import (
    DataQualityIssueType,
    DataQualitySeverity,
    DataQualitySignal,
    InstrumentType,
    MarketDataValidationError,
    OrderBookLevel,
    OrderBookSnapshotContract,
    RawUniverseSnapshot,
    SymbolContract,
    SymbolMetricsCollector,
    SymbolMetricsConfig,
    SymbolMetricsInput,
    UniverseConfidenceState,
    UniverseExclusionReason,
    UniversePolicy,
    UniversePolicyConfig,
    calculate_depth_within_bps,
    calculate_top_of_book_depth,
)


def build_orderbook(symbol: str) -> OrderBookSnapshotContract:
    timestamp = datetime(2026, 3, 19, 12, 0, tzinfo=UTC)
    return OrderBookSnapshotContract(
        symbol=symbol,
        exchange="bybit",
        timestamp=timestamp,
        bids=(
            OrderBookLevel(price=Decimal("50000"), quantity=Decimal("2")),
            OrderBookLevel(price=Decimal("49999"), quantity=Decimal("3")),
        ),
        asks=(
            OrderBookLevel(price=Decimal("50001"), quantity=Decimal("2.5")),
            OrderBookLevel(price=Decimal("50002"), quantity=Decimal("3.5")),
        ),
        spread_bps=Decimal("2"),
    )


def test_symbol_metrics_collector_builds_deterministic_contract() -> None:
    collector = SymbolMetricsCollector(
        SymbolMetricsConfig(
            depth_window_bps=Decimal("5"),
            target_top_depth_usd=Decimal("100000"),
            target_depth_window_usd=Decimal("200000"),
        )
    )
    orderbook = build_orderbook("BTC/USDT")
    metrics = collector.collect(
        SymbolMetricsInput(
            symbol="BTC/USDT",
            exchange="bybit",
            calculated_at=datetime(2026, 3, 19, 12, 0, 2, tzinfo=UTC),
            orderbook=orderbook,
            last_trade_at=datetime(2026, 3, 19, 12, 0, 1, tzinfo=UTC),
            tick_coverage_ratio=Decimal("0.97"),
            average_latency_ms=Decimal("45"),
            volume_24h_usd=Decimal("50000000"),
            funding_8h=Decimal("0.0001"),
        )
    )

    assert metrics.symbol == "BTC/USDT"
    assert metrics.top_of_book_depth_usd == calculate_top_of_book_depth(orderbook)
    assert metrics.depth_5bps_usd == calculate_depth_within_bps(orderbook, window_bps=Decimal("5"))
    assert metrics.quality_score > Decimal("0")
    assert metrics.data_freshness_ms == 1000


def test_symbol_metrics_collector_rejects_symbol_exchange_mismatch() -> None:
    collector = SymbolMetricsCollector()

    with pytest.raises(MarketDataValidationError, match=r"orderbook\.symbol"):
        collector.collect(
            SymbolMetricsInput(
                symbol="ETH/USDT",
                exchange="bybit",
                calculated_at=datetime(2026, 3, 19, 12, 0, 2, tzinfo=UTC),
                orderbook=build_orderbook("BTC/USDT"),
                last_trade_at=datetime(2026, 3, 19, 12, 0, 1, tzinfo=UTC),
                tick_coverage_ratio=Decimal("0.97"),
                average_latency_ms=Decimal("45"),
            )
        )

    with pytest.raises(MarketDataValidationError, match=r"orderbook\.exchange"):
        collector.collect(
            SymbolMetricsInput(
                symbol="BTC/USDT",
                exchange="okx",
                calculated_at=datetime(2026, 3, 19, 12, 0, 2, tzinfo=UTC),
                orderbook=build_orderbook("BTC/USDT"),
                last_trade_at=datetime(2026, 3, 19, 12, 0, 1, tzinfo=UTC),
                tick_coverage_ratio=Decimal("0.97"),
                average_latency_ms=Decimal("45"),
            )
        )


def test_universe_policy_builds_admissible_snapshot_and_ready_assessment() -> None:
    collector = SymbolMetricsCollector()
    raw_snapshot = RawUniverseSnapshot(
        version=1,
        created_at=datetime(2026, 3, 19, 12, 0, tzinfo=UTC),
        symbols=(
            SymbolContract(
                symbol="BTC/USDT",
                exchange="bybit",
                base_asset="BTC",
                quote_asset="USDT",
                instrument_type=InstrumentType.PERPETUAL,
            ),
        ),
    )
    metrics = collector.collect(
        SymbolMetricsInput(
            symbol="BTC/USDT",
            exchange="bybit",
            calculated_at=datetime(2026, 3, 19, 12, 0, 1, tzinfo=UTC),
            orderbook=build_orderbook("BTC/USDT"),
            last_trade_at=datetime(2026, 3, 19, 12, 0, 0, tzinfo=UTC),
            tick_coverage_ratio=Decimal("0.99"),
            average_latency_ms=Decimal("25"),
        )
    )
    policy = UniversePolicy(
        UniversePolicyConfig(
            min_admissible_count_ready=1,
            min_confidence_ready=Decimal("0.50"),
            min_confidence_degraded=Decimal("0.30"),
            min_admissible_ratio_degraded=Decimal("0.10"),
        )
    )

    result = policy.build_admissible_universe(
        raw_snapshot=raw_snapshot,
        metrics_by_identity={("BTC/USDT", "bybit"): metrics},
    )

    assert len(result.snapshot.symbols) == 1
    assert result.snapshot.is_admissible("BTC/USDT", "bybit") is True
    assert result.assessment.state == UniverseConfidenceState.READY
    assert result.assessment.admissible_count == 1


def test_universe_policy_excludes_symbols_with_quality_and_metrics_failures() -> None:
    collector = SymbolMetricsCollector()
    raw_snapshot = RawUniverseSnapshot(
        version=2,
        created_at=datetime(2026, 3, 19, 12, 0, tzinfo=UTC),
        symbols=(
            SymbolContract(
                symbol="BAD/USDT",
                exchange="bybit",
                base_asset="BAD",
                quote_asset="USDT",
                instrument_type=InstrumentType.PERPETUAL,
            ),
        ),
    )
    bad_orderbook = OrderBookSnapshotContract(
        symbol="BAD/USDT",
        exchange="bybit",
        timestamp=datetime(2026, 3, 19, 12, 0, tzinfo=UTC),
        bids=(OrderBookLevel(price=Decimal("10"), quantity=Decimal("1")),),
        asks=(OrderBookLevel(price=Decimal("10.2"), quantity=Decimal("1")),),
        spread_bps=Decimal("198"),
    )
    low_quality_metrics = collector.collect(
        SymbolMetricsInput(
            symbol="BAD/USDT",
            exchange="bybit",
            calculated_at=datetime(2026, 3, 19, 12, 0, 10, tzinfo=UTC),
            orderbook=bad_orderbook,
            last_trade_at=datetime(2026, 3, 19, 11, 59, 50, tzinfo=UTC),
            tick_coverage_ratio=Decimal("0.50"),
            average_latency_ms=Decimal("500"),
        )
    )
    policy = UniversePolicy()

    result = policy.build_admissible_universe(
        raw_snapshot=raw_snapshot,
        metrics_by_identity={("BAD/USDT", "bybit"): low_quality_metrics},
        quality_signals_by_identity={
            ("BAD/USDT", "bybit"): (
                DataQualitySignal(
                    symbol="BAD/USDT",
                    exchange="bybit",
                    issue_type=DataQualityIssueType.GAP,
                    severity=DataQualitySeverity.CRITICAL,
                    detected_at=datetime(2026, 3, 19, 12, 0, 9, tzinfo=UTC),
                    feed="trades",
                    gap_duration_ms=12000,
                ),
            )
        },
        measured_at=datetime(2026, 3, 19, 12, 0, 10, tzinfo=UTC),
    )

    assert result.snapshot.symbols == ()
    assert any(
        excluded.identity == ("BAD/USDT", "bybit")
        for excluded in result.snapshot.excluded_symbols
    )
    assert result.assessment.state == UniverseConfidenceState.BLOCKED
    assert UniverseExclusionReason.SPREAD_TOO_WIDE in result.exclusion_reasons[("BAD/USDT", "bybit")]
    assert UniverseExclusionReason.DATA_GAP in result.exclusion_reasons[("BAD/USDT", "bybit")]


def test_universe_policy_degraded_when_confidence_and_ratio_are_low_but_nonzero() -> None:
    raw_snapshot = RawUniverseSnapshot(
        version=3,
        created_at=datetime(2026, 3, 19, 12, 0, tzinfo=UTC),
        symbols=tuple(
            SymbolContract(
                symbol=f"S{i}/USDT",
                exchange="bybit",
                base_asset=f"S{i}",
                quote_asset="USDT",
                instrument_type=InstrumentType.PERPETUAL,
            )
            for i in range(10)
        ),
    )
    collector = SymbolMetricsCollector(
        SymbolMetricsConfig(max_freshness=timedelta(seconds=5), target_spread_bps=Decimal("20"))
    )
    metrics = collector.collect(
        SymbolMetricsInput(
            symbol="S0/USDT",
            exchange="bybit",
            calculated_at=datetime(2026, 3, 19, 12, 0, 2, tzinfo=UTC),
            orderbook=build_orderbook("S0/USDT"),
            last_trade_at=datetime(2026, 3, 19, 12, 0, 1, tzinfo=UTC),
            tick_coverage_ratio=Decimal("0.95"),
            average_latency_ms=Decimal("120"),
        )
    )
    policy = UniversePolicy(
        UniversePolicyConfig(
            min_admissible_count_ready=5,
            min_admissible_ratio_degraded=Decimal("0.05"),
            min_confidence_ready=Decimal("0.70"),
            min_confidence_degraded=Decimal("0.05"),
        )
    )

    result = policy.build_admissible_universe(
        raw_snapshot=raw_snapshot,
        metrics_by_identity={("S0/USDT", "bybit"): metrics},
        measured_at=datetime(2026, 3, 19, 12, 0, 2, tzinfo=UTC),
    )

    assert len(result.snapshot.symbols) == 1
    assert result.assessment.state == UniverseConfidenceState.DEGRADED
    assert result.assessment.confidence > Decimal("0")


def test_universe_policy_keeps_exclusions_identity_aware_for_same_symbol_on_two_exchanges() -> None:
    collector = SymbolMetricsCollector()
    raw_snapshot = RawUniverseSnapshot(
        version=4,
        created_at=datetime(2026, 3, 19, 12, 0, tzinfo=UTC),
        symbols=(
            SymbolContract(
                symbol="BTC/USDT",
                exchange="bybit",
                base_asset="BTC",
                quote_asset="USDT",
                instrument_type=InstrumentType.PERPETUAL,
            ),
            SymbolContract(
                symbol="BTC/USDT",
                exchange="okx",
                base_asset="BTC",
                quote_asset="USDT",
                instrument_type=InstrumentType.PERPETUAL,
            ),
        ),
    )
    good_metrics = collector.collect(
        SymbolMetricsInput(
            symbol="BTC/USDT",
            exchange="bybit",
            calculated_at=datetime(2026, 3, 19, 12, 0, 2, tzinfo=UTC),
            orderbook=build_orderbook("BTC/USDT"),
            last_trade_at=datetime(2026, 3, 19, 12, 0, 1, tzinfo=UTC),
            tick_coverage_ratio=Decimal("0.98"),
            average_latency_ms=Decimal("30"),
        )
    )
    bad_metrics = collector.collect(
        SymbolMetricsInput(
            symbol="BTC/USDT",
            exchange="okx",
            calculated_at=datetime(2026, 3, 19, 12, 0, 2, tzinfo=UTC),
            orderbook=OrderBookSnapshotContract(
                symbol="BTC/USDT",
                exchange="okx",
                timestamp=datetime(2026, 3, 19, 12, 0, 1, tzinfo=UTC),
                bids=(OrderBookLevel(price=Decimal("50000"), quantity=Decimal("0.5")),),
                asks=(OrderBookLevel(price=Decimal("50200"), quantity=Decimal("0.5")),),
                spread_bps=Decimal("39.9202"),
            ),
            last_trade_at=datetime(2026, 3, 19, 12, 0, 1, tzinfo=UTC),
            tick_coverage_ratio=Decimal("0.98"),
            average_latency_ms=Decimal("30"),
        )
    )

    result = UniversePolicy(
        UniversePolicyConfig(
            min_admissible_count_ready=1,
            min_confidence_ready=Decimal("0.50"),
            min_confidence_degraded=Decimal("0.30"),
            min_admissible_ratio_degraded=Decimal("0.10"),
        )
    ).build_admissible_universe(
        raw_snapshot=raw_snapshot,
        metrics_by_identity={
            ("BTC/USDT", "bybit"): good_metrics,
            ("BTC/USDT", "okx"): bad_metrics,
        },
    )

    assert result.snapshot.is_admissible("BTC/USDT", "bybit") is True
    assert result.snapshot.is_admissible("BTC/USDT", "okx") is False
    assert len(result.snapshot.excluded_symbols) == 1
    assert result.snapshot.excluded_symbols[0].identity == ("BTC/USDT", "okx")

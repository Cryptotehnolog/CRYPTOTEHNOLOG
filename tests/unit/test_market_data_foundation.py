from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from cryptotechnolog.market_data import (
    BarBuilder,
    DataQualityConfig,
    DataQualityIssueType,
    DataQualityValidator,
    MarketDataSide,
    MarketDataTimeframe,
    MarketDataValidationError,
    OrderBookLevel,
    OrderBookManager,
    TickHandler,
)


def test_tick_handler_normalizes_tick_and_detects_gap_outlier() -> None:
    validator = DataQualityValidator(
        DataQualityConfig(
            gap_threshold=timedelta(seconds=2),
            max_price_deviation_bps=Decimal("100"),
        )
    )
    handler = TickHandler(quality_validator=validator)

    first_tick = handler.normalize_tick(
        symbol="BTC/USDT",
        exchange="bybit",
        price=Decimal("50000"),
        quantity=Decimal("0.5"),
        side="buy",
        timestamp=datetime(2026, 3, 19, 12, 0, 0, tzinfo=UTC),
        trade_id="t-1",
    )
    second_tick = handler.normalize_tick(
        symbol="BTC/USDT",
        exchange="bybit",
        price=Decimal("51050"),
        quantity=Decimal("0.2"),
        side=MarketDataSide.SELL,
        timestamp=datetime(2026, 3, 19, 12, 0, 5, tzinfo=UTC),
        trade_id="t-2",
        is_buyer_maker=True,
    )

    first_result = handler.process_tick(first_tick)
    second_result = handler.process_tick(second_tick)

    assert first_result.quality_signals == ()
    assert second_result.tick.side == MarketDataSide.SELL
    assert {signal.issue_type for signal in second_result.quality_signals} == {
        DataQualityIssueType.GAP,
        DataQualityIssueType.OUTLIER,
    }


def test_tick_handler_rejects_invalid_tick_values() -> None:
    handler = TickHandler()

    with pytest.raises(MarketDataValidationError):
        handler.normalize_tick(
            symbol="BTC/USDT",
            exchange="bybit",
            price=Decimal("-1"),
            quantity=Decimal("0.1"),
            side="buy",
            timestamp=datetime(2026, 3, 19, 12, 0, tzinfo=UTC),
            trade_id="bad",
        )


def test_data_quality_validator_detects_stale_and_source_degraded() -> None:
    validator = DataQualityValidator(DataQualityConfig(stale_after=timedelta(seconds=3)))
    handler = TickHandler(quality_validator=validator)
    processed = handler.process_tick(
        handler.normalize_tick(
            symbol="ETH/USDT",
            exchange="okx",
            price=Decimal("3000"),
            quantity=Decimal("1"),
            side="buy",
            timestamp=datetime(2026, 3, 19, 12, 0, 0, tzinfo=UTC),
            trade_id="eth-1",
        )
    )

    stale_signal = validator.detect_stale(
        symbol=processed.tick.symbol,
        exchange=processed.tick.exchange,
        feed="trades",
        now=datetime(2026, 3, 19, 12, 0, 5, tzinfo=UTC),
    )
    degraded_signal = validator.build_source_degraded_signal(
        symbol="ETH/USDT",
        exchange="okx",
        feed="trades",
        reason="websocket_timeout",
        detected_at=datetime(2026, 3, 19, 12, 0, 6, tzinfo=UTC),
    )

    assert stale_signal is not None
    assert stale_signal.issue_type == DataQualityIssueType.STALE
    assert degraded_signal.issue_type == DataQualityIssueType.SOURCE_DEGRADED
    assert degraded_signal.details["reason"] == "websocket_timeout"


def test_bar_builder_builds_bid_ask_volume_and_closes_previous_bar() -> None:
    builder = BarBuilder(MarketDataTimeframe.M1)
    handler = TickHandler()

    tick_1 = handler.normalize_tick(
        symbol="SOL/USDT",
        exchange="bybit",
        price=Decimal("100"),
        quantity=Decimal("2"),
        side="buy",
        timestamp=datetime(2026, 3, 19, 12, 0, 10, tzinfo=UTC),
        trade_id="sol-1",
    )
    tick_2 = handler.normalize_tick(
        symbol="SOL/USDT",
        exchange="bybit",
        price=Decimal("101"),
        quantity=Decimal("1.5"),
        side="sell",
        timestamp=datetime(2026, 3, 19, 12, 0, 40, tzinfo=UTC),
        trade_id="sol-2",
        is_buyer_maker=True,
    )
    tick_3 = handler.normalize_tick(
        symbol="SOL/USDT",
        exchange="bybit",
        price=Decimal("102"),
        quantity=Decimal("3"),
        side="buy",
        timestamp=datetime(2026, 3, 19, 12, 1, 2, tzinfo=UTC),
        trade_id="sol-3",
    )

    result_1 = builder.ingest_tick(tick_1)
    result_2 = builder.ingest_tick(tick_2)
    result_3 = builder.ingest_tick(tick_3)

    assert result_1.active_bar.ask_volume == Decimal("2")
    assert result_2.active_bar.bid_volume == Decimal("1.5")
    assert result_2.active_bar.ask_volume == Decimal("2")
    assert result_3.completed_bar is not None
    assert result_3.completed_bar.is_closed is True
    assert result_3.completed_bar.close == Decimal("101")
    assert result_3.completed_bar.volume == Decimal("3.5")


def test_bar_builder_marks_gap_affected_when_bar_window_was_skipped() -> None:
    builder = BarBuilder(MarketDataTimeframe.M1)
    handler = TickHandler()

    first_tick = handler.normalize_tick(
        symbol="ADA/USDT",
        exchange="okx",
        price=Decimal("1"),
        quantity=Decimal("10"),
        side="buy",
        timestamp=datetime(2026, 3, 19, 12, 0, 0, tzinfo=UTC),
        trade_id="ada-1",
    )
    skipped_tick = handler.normalize_tick(
        symbol="ADA/USDT",
        exchange="okx",
        price=Decimal("1.1"),
        quantity=Decimal("5"),
        side="buy",
        timestamp=datetime(2026, 3, 19, 12, 2, 0, tzinfo=UTC),
        trade_id="ada-2",
    )

    builder.ingest_tick(first_tick)
    result = builder.ingest_tick(skipped_tick)

    assert result.completed_bar is not None
    assert result.completed_bar.is_gap_affected is True
    assert result.active_bar.is_gap_affected is True


def test_orderbook_manager_supports_snapshot_delta_and_crossed_book_detection() -> None:
    manager = OrderBookManager(max_levels=3)
    snapshot_result = manager.apply_snapshot(
        symbol="BTC/USDT",
        exchange="bybit",
        timestamp=datetime(2026, 3, 19, 12, 0, 0, tzinfo=UTC),
        bids=(
            OrderBookLevel(price=Decimal("50000"), quantity=Decimal("1.0")),
            OrderBookLevel(price=Decimal("49999"), quantity=Decimal("1.5")),
        ),
        asks=(
            OrderBookLevel(price=Decimal("50001"), quantity=Decimal("0.8")),
            OrderBookLevel(price=Decimal("50002"), quantity=Decimal("1.1")),
        ),
    )
    delta_result = manager.apply_delta(
        symbol="BTC/USDT",
        exchange="bybit",
        timestamp=datetime(2026, 3, 19, 12, 0, 1, tzinfo=UTC),
        bid_updates=(OrderBookLevel(price=Decimal("50000.5"), quantity=Decimal("2.0")),),
        ask_updates=(OrderBookLevel(price=Decimal("50002"), quantity=Decimal("0")),),
    )
    crossed_result = manager.apply_snapshot(
        symbol="ETH/USDT",
        exchange="okx",
        timestamp=datetime(2026, 3, 19, 12, 0, 2, tzinfo=UTC),
        bids=(OrderBookLevel(price=Decimal("3001"), quantity=Decimal("1")),),
        asks=(OrderBookLevel(price=Decimal("3000.5"), quantity=Decimal("1")),),
    )

    assert snapshot_result.snapshot.spread_bps > Decimal("0")
    assert delta_result.snapshot.bids[0].price == Decimal("50000.5")
    assert len(delta_result.snapshot.asks) == 1
    assert crossed_result.quality_signals
    assert crossed_result.quality_signals[0].issue_type == DataQualityIssueType.ORDERBOOK_CROSSED

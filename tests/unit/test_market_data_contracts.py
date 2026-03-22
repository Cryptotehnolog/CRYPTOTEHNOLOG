from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from cryptotechnolog.core.event import Priority, SystemEventSource, SystemEventType
from cryptotechnolog.market_data import (
    AdmissibleSymbolContract,
    AdmissibleUniverseSnapshot,
    DataQualityIssueType,
    DataQualitySeverity,
    DataQualitySignal,
    ExcludedUniverseSymbol,
    InstrumentType,
    MarketDataEventType,
    MarketDataSide,
    MarketDataTimeframe,
    OHLCVBarContract,
    OrderBookLevel,
    OrderBookSnapshotContract,
    RankedUniverseEntry,
    RankedUniverseSnapshot,
    RawUniverseSnapshot,
    SymbolContract,
    SymbolMetricsContract,
    TickContract,
    TickReceivedPayload,
    UniverseAdmissionReason,
    UniverseConfidenceState,
    UniverseQualityAssessment,
    UniverseQualityPayload,
    UniverseSnapshotPayload,
    build_market_data_event,
    default_priority_for_market_data_event,
)


def test_build_market_data_event_uses_existing_event_bus_contract() -> None:
    tick = TickContract(
        symbol="BTC/USDT",
        exchange="bybit",
        price=Decimal("50000"),
        quantity=Decimal("0.25"),
        side=MarketDataSide.BUY,
        timestamp=datetime(2026, 3, 19, 12, 0, tzinfo=UTC),
        trade_id="trade-1",
    )

    event = build_market_data_event(
        event_type=MarketDataEventType.TICK_RECEIVED,
        payload=TickReceivedPayload.from_contract(tick),
        correlation_id=uuid4(),
    )

    assert event.event_type == SystemEventType.TICK_RECEIVED
    assert event.source == SystemEventSource.MARKET_DATA_MANAGER
    assert event.priority == Priority.NORMAL
    assert event.payload["symbol"] == "BTC/USDT"
    assert event.correlation_id is not None


def test_market_data_critical_events_have_critical_priority() -> None:
    assert (
        default_priority_for_market_data_event(MarketDataEventType.UNIVERSE_CONFIDENCE_LOW)
        == Priority.CRITICAL
    )
    assert default_priority_for_market_data_event(MarketDataEventType.DATA_GAP_DETECTED) == (
        Priority.CRITICAL
    )


def test_universe_snapshot_payloads_keep_raw_admissible_ranked_semantics() -> None:
    created_at = datetime(2026, 3, 19, 12, 0, tzinfo=UTC)
    symbol = SymbolContract(
        symbol="BTC/USDT",
        exchange="bybit",
        base_asset="BTC",
        quote_asset="USDT",
        instrument_type=InstrumentType.PERPETUAL,
    )
    raw_payload = UniverseSnapshotPayload.from_raw_snapshot(
        RawUniverseSnapshot(version=3, created_at=created_at, symbols=(symbol,))
    )
    metrics = SymbolMetricsContract(
        symbol="BTC/USDT",
        exchange="bybit",
        calculated_at=created_at,
        spread_bps=Decimal("1.5"),
        top_of_book_depth_usd=Decimal("1000000"),
        depth_5bps_usd=Decimal("2500000"),
        latency_ms=Decimal("12"),
        coverage_ratio=Decimal("0.99"),
        data_freshness_ms=250,
        quality_score=Decimal("0.96"),
    )
    admissible_payload = UniverseSnapshotPayload.from_admissible_snapshot(
        AdmissibleUniverseSnapshot(
            version=3,
            created_at=created_at,
            symbols=(
                AdmissibleSymbolContract(
                    symbol=symbol,
                    metrics=metrics,
                    admitted_at=created_at,
                    admission_reasons=(UniverseAdmissionReason.LIQUIDITY_OK,),
                ),
            ),
            confidence=Decimal("0.82"),
            excluded_symbols=(ExcludedUniverseSymbol(symbol="XYZ/USDT", exchange="okx"),),
        )
    )
    ranked_payload = UniverseSnapshotPayload.from_ranked_snapshot(
        RankedUniverseSnapshot(
            version=4,
            created_at=created_at,
            upstream_admissible_version=3,
            entries=(RankedUniverseEntry(symbol=symbol, rank=1, score=Decimal("0.84")),),
        )
    )

    assert raw_payload.snapshot_type == "raw"
    assert raw_payload.symbols == (("BTC/USDT", "bybit"),)
    assert admissible_payload.snapshot_type == "admissible"
    assert admissible_payload.symbols == (("BTC/USDT", "bybit"),)
    assert admissible_payload.confidence == "0.82"
    assert admissible_payload.excluded_symbols == (("XYZ/USDT", "okx"),)
    assert ranked_payload.snapshot_type == "ranked"
    assert ranked_payload.upstream_admissible_version == 3
    assert ranked_payload.symbols == (("BTC/USDT", "bybit"),)


def test_universe_snapshot_payload_keeps_multi_exchange_symbol_identity() -> None:
    created_at = datetime(2026, 3, 19, 12, 0, tzinfo=UTC)
    symbol_bybit = SymbolContract(
        symbol="BTC/USDT",
        exchange="bybit",
        base_asset="BTC",
        quote_asset="USDT",
        instrument_type=InstrumentType.PERPETUAL,
    )
    symbol_okx = SymbolContract(
        symbol="BTC/USDT",
        exchange="okx",
        base_asset="BTC",
        quote_asset="USDT",
        instrument_type=InstrumentType.PERPETUAL,
    )

    raw_payload = UniverseSnapshotPayload.from_raw_snapshot(
        RawUniverseSnapshot(
            version=5,
            created_at=created_at,
            symbols=(symbol_bybit, symbol_okx),
        )
    )
    ranked_payload = UniverseSnapshotPayload.from_ranked_snapshot(
        RankedUniverseSnapshot(
            version=6,
            created_at=created_at,
            upstream_admissible_version=5,
            entries=(
                RankedUniverseEntry(symbol=symbol_bybit, rank=1, score=Decimal("0.9")),
                RankedUniverseEntry(symbol=symbol_okx, rank=2, score=Decimal("0.8")),
            ),
        )
    )

    assert raw_payload.symbols == (("BTC/USDT", "bybit"), ("BTC/USDT", "okx"))
    assert ranked_payload.symbols == (("BTC/USDT", "bybit"), ("BTC/USDT", "okx"))


def test_universe_quality_payload_preserves_confidence_contract() -> None:
    payload = UniverseQualityPayload.from_assessment(
        UniverseQualityAssessment(
            version=7,
            measured_at=datetime(2026, 3, 19, 12, 5, tzinfo=UTC),
            confidence=Decimal("0.58"),
            state=UniverseConfidenceState.DEGRADED,
            raw_count=120,
            admissible_count=18,
            ranked_count=0,
            blocking_reasons=("confidence_below_threshold",),
            worst_symbols=("XYZ/USDT",),
        )
    )

    assert payload.state == UniverseConfidenceState.DEGRADED.value
    assert payload.confidence == "0.58"
    assert payload.blocking_reasons == ("confidence_below_threshold",)


def test_contract_models_cover_quality_metrics_and_bar_orderbook_shape() -> None:
    signal = DataQualitySignal(
        symbol="ETH/USDT",
        exchange="okx",
        issue_type=DataQualityIssueType.STALE,
        severity=DataQualitySeverity.WARNING,
        detected_at=datetime(2026, 3, 19, 12, 10, tzinfo=UTC),
        feed="trades",
        staleness_ms=4500,
        details={"threshold_ms": 3000},
    )
    metrics = SymbolMetricsContract(
        symbol="ETH/USDT",
        exchange="okx",
        calculated_at=datetime(2026, 3, 19, 12, 10, tzinfo=UTC),
        spread_bps=Decimal("3.5"),
        top_of_book_depth_usd=Decimal("250000"),
        depth_5bps_usd=Decimal("800000"),
        latency_ms=Decimal("42"),
        coverage_ratio=Decimal("0.98"),
        data_freshness_ms=600,
        quality_score=Decimal("0.91"),
    )
    orderbook = OrderBookSnapshotContract(
        symbol="ETH/USDT",
        exchange="okx",
        timestamp=datetime(2026, 3, 19, 12, 10, tzinfo=UTC),
        bids=(OrderBookLevel(price=Decimal("3000"), quantity=Decimal("5.2")),),
        asks=(OrderBookLevel(price=Decimal("3000.5"), quantity=Decimal("4.8")),),
        spread_bps=Decimal("1.67"),
    )
    bar = OHLCVBarContract(
        symbol="ETH/USDT",
        exchange="okx",
        timeframe=MarketDataTimeframe.M1,
        open_time=datetime(2026, 3, 19, 12, 9, tzinfo=UTC),
        close_time=datetime(2026, 3, 19, 12, 10, tzinfo=UTC),
        open=Decimal("2998"),
        high=Decimal("3005"),
        low=Decimal("2995"),
        close=Decimal("3001"),
        volume=Decimal("123.45"),
    )

    assert signal.issue_type == DataQualityIssueType.STALE
    assert metrics.quality_score == Decimal("0.91")
    assert orderbook.spread_bps == Decimal("1.67")
    assert bar.timeframe == MarketDataTimeframe.M1
    assert UniverseAdmissionReason.QUALITY_OK.value == "quality_ok"

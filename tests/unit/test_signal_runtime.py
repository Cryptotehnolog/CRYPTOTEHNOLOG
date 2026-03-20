from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from cryptotechnolog.analysis import (
    AdxSnapshot,
    AtrSnapshot,
    DerivedInputStatus,
    DerivedInputValidity,
    RiskDerivedInputsSnapshot,
)
from cryptotechnolog.intelligence import (
    DEFAULT_DERYA_CLASSIFICATION_BASIS,
    DeryaAssessment,
    DeryaRegime,
    DeryaResolutionState,
    IndicatorValidity,
    IndicatorValueStatus,
)
from cryptotechnolog.market_data import (
    MarketDataTimeframe,
    OHLCVBarContract,
    OrderBookLevel,
    OrderBookSnapshotContract,
)
from cryptotechnolog.market_data.events import BarCompletedPayload
from cryptotechnolog.signals import (
    SignalDirection,
    SignalEventType,
    SignalReasonCode,
    SignalRuntime,
    SignalRuntimeConfig,
    SignalRuntimeLifecycleState,
    SignalStatus,
    SignalValidityStatus,
    create_signal_runtime,
)


def _make_bar(
    *,
    close: str = "102",
    open_price: str = "100",
    high: str = "103",
    low: str = "99",
) -> OHLCVBarContract:
    return OHLCVBarContract(
        symbol="BTC/USDT",
        exchange="bybit",
        timeframe=MarketDataTimeframe.M15,
        open_time=datetime(2026, 3, 21, 12, 0, tzinfo=UTC),
        close_time=datetime(2026, 3, 21, 12, 15, tzinfo=UTC),
        open=Decimal(open_price),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=Decimal("120"),
        bid_volume=Decimal("60"),
        ask_volume=Decimal("60"),
        trades_count=50,
        is_closed=True,
        is_gap_affected=False,
    )


def _make_orderbook() -> OrderBookSnapshotContract:
    return OrderBookSnapshotContract(
        symbol="BTC/USDT",
        exchange="bybit",
        timestamp=datetime(2026, 3, 21, 12, 15, tzinfo=UTC),
        bids=(OrderBookLevel(price=Decimal("101.9"), quantity=Decimal("10")),),
        asks=(OrderBookLevel(price=Decimal("102.1"), quantity=Decimal("11")),),
        spread_bps=Decimal("1.9608"),
        checksum=None,
        is_gap_affected=False,
    )


def _make_validity(status: DerivedInputStatus) -> DerivedInputValidity:
    return DerivedInputValidity(
        status=status,
        observed_bars=20,
        required_bars=14,
    )


def _make_derived_inputs(
    *,
    atr: str = "2",
    adx: str = "30",
    status: DerivedInputStatus = DerivedInputStatus.VALID,
) -> RiskDerivedInputsSnapshot:
    updated_at = datetime(2026, 3, 21, 12, 15, tzinfo=UTC)
    validity = _make_validity(status)
    return RiskDerivedInputsSnapshot(
        symbol="BTC/USDT",
        exchange="bybit",
        timeframe=MarketDataTimeframe.M15,
        updated_at=updated_at,
        atr=AtrSnapshot(
            symbol="BTC/USDT",
            exchange="bybit",
            timeframe=MarketDataTimeframe.M15,
            updated_at=updated_at,
            period=14,
            value=Decimal(atr) if status == DerivedInputStatus.VALID else None,
            validity=validity,
        ),
        adx=AdxSnapshot(
            symbol="BTC/USDT",
            exchange="bybit",
            timeframe=MarketDataTimeframe.M15,
            updated_at=updated_at,
            period=14,
            value=Decimal(adx) if status == DerivedInputStatus.VALID else None,
            validity=validity,
        ),
    )


def _make_derya(
    *,
    regime: DeryaRegime | None = DeryaRegime.EXPANSION,
    confidence: str | None = "0.7000",
    status: IndicatorValueStatus = IndicatorValueStatus.VALID,
) -> DeryaAssessment:
    updated_at = datetime(2026, 3, 21, 12, 15, tzinfo=UTC)
    return DeryaAssessment(
        symbol="BTC/USDT",
        exchange="bybit",
        timeframe=MarketDataTimeframe.M15,
        updated_at=updated_at,
        validity=IndicatorValidity(
            status=status,
            observed_bars=10,
            required_bars=4,
        ),
        confidence=Decimal(confidence) if confidence is not None else None,
        raw_efficiency=Decimal("0.8"),
        smoothed_efficiency=Decimal("0.75"),
        efficiency_slope=Decimal("0.03"),
        current_regime=regime,
        previous_regime=DeryaRegime.EXHAUSTION if regime is not None else None,
        resolution_state=DeryaResolutionState.STABLE,
        regime_duration_bars=4,
        regime_persistence_ratio=Decimal("1"),
        classification_basis=DEFAULT_DERYA_CLASSIFICATION_BASIS,
    )


def test_signal_runtime_requires_explicit_start() -> None:
    runtime = create_signal_runtime()

    with pytest.raises(RuntimeError, match="не запущен"):
        runtime.ingest_truths(
            bar=_make_bar(),
            derived_inputs=_make_derived_inputs(),
            derya=_make_derya(),
        )


def test_signal_runtime_start_and_stop_reset_operator_state() -> None:
    runtime = create_signal_runtime()

    asyncio.run(runtime.start())
    runtime.mark_degraded("synthetic_failure")
    runtime.ingest_truths(
        bar=_make_bar(),
        derived_inputs=_make_derived_inputs(),
        derya=_make_derya(),
    )
    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["started"] is True
    assert diagnostics["tracked_signal_keys"] == 1

    asyncio.run(runtime.stop())
    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["started"] is False
    assert diagnostics["tracked_signal_keys"] == 0
    assert diagnostics["lifecycle_state"] == SignalRuntimeLifecycleState.STOPPED.value
    assert diagnostics["active_signal_keys"] == 0
    assert diagnostics["invalidated_signal_keys"] == 0
    assert diagnostics["expired_signal_keys"] == 0
    assert diagnostics["last_context_at"] is None
    assert diagnostics["last_signal_id"] is None
    assert diagnostics["last_event_type"] is None
    assert diagnostics["last_failure_reason"] is None
    assert diagnostics["readiness_reasons"] == ["runtime_stopped"]
    assert diagnostics["degraded_reasons"] == []
    assert (
        runtime.get_signal(
            symbol="BTC/USDT",
            exchange="bybit",
            timeframe=MarketDataTimeframe.M15,
        )
        is None
    )
    assert (
        runtime.get_signal_context(
            symbol="BTC/USDT",
            exchange="bybit",
            timeframe=MarketDataTimeframe.M15,
        )
        is None
    )


def test_signal_runtime_assembles_warming_context_when_inputs_missing() -> None:
    runtime = create_signal_runtime()
    asyncio.run(runtime.start())
    update = runtime.ingest_truths(bar=_make_bar())
    context = update.context

    assert context.validity.is_warming
    assert context.validity.missing_inputs == ("analysis", "intelligence")
    assert update.event_type == SignalEventType.SIGNAL_SNAPSHOT_UPDATED
    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["ready"] is False
    assert diagnostics["lifecycle_state"] == SignalRuntimeLifecycleState.WARMING.value
    assert diagnostics["readiness_reasons"] == ["signal_context_warming"]


def test_signal_runtime_builds_active_buy_signal_from_valid_context() -> None:
    runtime = create_signal_runtime()
    asyncio.run(runtime.start())

    update = runtime.ingest_truths(
        bar=_make_bar(),
        orderbook=_make_orderbook(),
        derived_inputs=_make_derived_inputs(),
        derya=_make_derya(regime=DeryaRegime.EXPANSION, confidence="0.7000"),
    )

    assert update.signal is not None
    assert update.signal.status == SignalStatus.ACTIVE
    assert update.signal.direction == SignalDirection.BUY
    assert update.event_type == SignalEventType.SIGNAL_EMITTED
    assert update.emitted_payload is not None
    assert (
        runtime.get_signal(
            symbol="BTC/USDT",
            exchange="bybit",
            timeframe=MarketDataTimeframe.M15,
        )
        == update.signal
    )


def test_signal_runtime_returns_suppressed_signal_when_contour_conditions_not_met() -> None:
    runtime = create_signal_runtime()
    asyncio.run(runtime.start())

    update = runtime.ingest_truths(
        bar=_make_bar(close="100.2", open_price="100"),
        derived_inputs=_make_derived_inputs(adx="10"),
        derya=_make_derya(regime=DeryaRegime.EXPANSION, confidence="0.7000"),
    )

    assert update.signal is not None
    assert update.signal.status == SignalStatus.SUPPRESSED
    assert update.signal.direction is None
    assert update.event_type == SignalEventType.SIGNAL_SNAPSHOT_UPDATED


def test_signal_runtime_expires_signal_only_against_reference_time() -> None:
    runtime = create_signal_runtime(
        config=SignalRuntimeConfig(max_signal_age_seconds=60),
    )
    asyncio.run(runtime.start())

    update = runtime.ingest_truths(
        bar=_make_bar(),
        derived_inputs=_make_derived_inputs(),
        derya=_make_derya(),
    )
    context = update.context

    not_expired = runtime.get_signal(
        symbol="BTC/USDT",
        exchange="bybit",
        timeframe=MarketDataTimeframe.M15,
        reference_time=context.observed_at + timedelta(seconds=59),
    )
    assert not_expired is not None
    assert not_expired.status == SignalStatus.ACTIVE

    expired = runtime.get_signal(
        symbol="BTC/USDT",
        exchange="bybit",
        timeframe=MarketDataTimeframe.M15,
        reference_time=context.observed_at + timedelta(seconds=60),
    )
    assert expired is not None
    assert expired.status == SignalStatus.EXPIRED
    assert expired.reason_code == SignalReasonCode.SIGNAL_EXPIRED

    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["expired_signal_keys"] == 1
    assert diagnostics["last_event_type"] == SignalEventType.SIGNAL_INVALIDATED.value


def test_signal_runtime_marks_degraded_and_keeps_operator_truth_visible() -> None:
    runtime = SignalRuntime()

    asyncio.run(runtime.start())
    runtime.mark_degraded("context_assembly_failed")
    diagnostics = runtime.get_runtime_diagnostics()

    assert diagnostics["ready"] is False
    assert diagnostics["lifecycle_state"] == SignalRuntimeLifecycleState.DEGRADED.value
    assert diagnostics["last_failure_reason"] == "context_assembly_failed"
    assert diagnostics["degraded_reasons"] == ["context_assembly_failed"]


def test_signal_runtime_rejects_context_identity_mismatch() -> None:
    runtime = create_signal_runtime()
    asyncio.run(runtime.start())
    mismatch_inputs = _make_derived_inputs()
    mismatch_inputs = RiskDerivedInputsSnapshot(
        symbol="ETH/USDT",
        exchange=mismatch_inputs.exchange,
        timeframe=mismatch_inputs.timeframe,
        updated_at=mismatch_inputs.updated_at,
        atr=mismatch_inputs.atr,
        adx=mismatch_inputs.adx,
        metadata=mismatch_inputs.metadata,
    )

    update = runtime.ingest_truths(
        bar=_make_bar(),
        derived_inputs=mismatch_inputs,
        derya=_make_derya(),
    )
    context = update.context

    assert context.validity.status == SignalValidityStatus.INVALID
    assert context.validity.invalid_reason == "analysis_identity_mismatch"
    assert update.event_type == SignalEventType.SIGNAL_SNAPSHOT_UPDATED


def test_signal_runtime_boundary_ingests_existing_truths_without_external_context_assembly() -> (
    None
):
    runtime = create_signal_runtime()
    asyncio.run(runtime.start())

    update = runtime.ingest_truths(
        bar=_make_bar(),
        orderbook=_make_orderbook(),
        derived_inputs=_make_derived_inputs(),
        derya=_make_derya(),
    )

    assert update.context.bar.symbol == "BTC/USDT"
    assert update.context.derived_inputs is not None
    assert update.context.derya is not None


def test_signal_runtime_accepts_bar_completed_payload_boundary() -> None:
    runtime = create_signal_runtime()
    asyncio.run(runtime.start())

    update = runtime.ingest_bar_completed_payload(
        BarCompletedPayload.from_contract(_make_bar()),
        orderbook=_make_orderbook(),
        derived_inputs=_make_derived_inputs(),
        derya=_make_derya(),
    )

    assert update.signal is not None
    assert update.signal.status == SignalStatus.ACTIVE


def test_signal_runtime_re_evaluates_active_signal_into_suppressed_with_continuity() -> None:
    runtime = create_signal_runtime()
    asyncio.run(runtime.start())

    active = runtime.ingest_truths(
        bar=_make_bar(),
        orderbook=_make_orderbook(),
        derived_inputs=_make_derived_inputs(),
        derya=_make_derya(),
    ).signal
    assert active is not None
    assert active.status == SignalStatus.ACTIVE

    suppressed = runtime.ingest_truths(
        bar=_make_bar(close="100.2", open_price="100"),
        orderbook=_make_orderbook(),
        derived_inputs=_make_derived_inputs(adx="10"),
        derya=_make_derya(),
    ).signal

    assert suppressed is not None
    assert suppressed.status == SignalStatus.SUPPRESSED
    assert suppressed.signal_id == active.signal_id
    assert suppressed.direction is None
    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["active_signal_keys"] == 0
    assert diagnostics["invalidated_signal_keys"] == 0
    assert diagnostics["last_event_type"] == SignalEventType.SIGNAL_SNAPSHOT_UPDATED.value


def test_signal_runtime_invalidates_previously_active_signal_when_analysis_truth_disappears() -> (
    None
):
    runtime = create_signal_runtime()
    asyncio.run(runtime.start())

    active = runtime.ingest_truths(
        bar=_make_bar(),
        orderbook=_make_orderbook(),
        derived_inputs=_make_derived_inputs(),
        derya=_make_derya(),
    ).signal
    assert active is not None

    update = runtime.ingest_truths(
        bar=_make_bar(),
        orderbook=_make_orderbook(),
        derived_inputs=None,
        derya=_make_derya(),
    )
    invalidated = update.signal

    assert invalidated is not None
    assert invalidated.status == SignalStatus.INVALIDATED
    assert invalidated.signal_id == active.signal_id
    assert invalidated.reason_code == SignalReasonCode.SIGNAL_INVALIDATED
    assert invalidated.validity.status == SignalValidityStatus.WARMING
    assert update.event_type == SignalEventType.SIGNAL_INVALIDATED
    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["ready"] is False
    assert diagnostics["lifecycle_state"] == SignalRuntimeLifecycleState.WARMING.value
    assert diagnostics["invalidated_signal_keys"] == 1
    assert diagnostics["last_event_type"] == SignalEventType.SIGNAL_INVALIDATED.value


def test_signal_runtime_invalidates_previously_active_signal_on_identity_breakage() -> None:
    runtime = create_signal_runtime()
    asyncio.run(runtime.start())

    active = runtime.ingest_truths(
        bar=_make_bar(),
        orderbook=_make_orderbook(),
        derived_inputs=_make_derived_inputs(),
        derya=_make_derya(),
    ).signal
    assert active is not None

    mismatch_inputs = _make_derived_inputs()
    mismatch_inputs = RiskDerivedInputsSnapshot(
        symbol="ETH/USDT",
        exchange=mismatch_inputs.exchange,
        timeframe=mismatch_inputs.timeframe,
        updated_at=mismatch_inputs.updated_at,
        atr=mismatch_inputs.atr,
        adx=mismatch_inputs.adx,
        metadata=mismatch_inputs.metadata,
    )

    update = runtime.ingest_truths(
        bar=_make_bar(),
        orderbook=_make_orderbook(),
        derived_inputs=mismatch_inputs,
        derya=_make_derya(),
    )
    invalidated = update.signal

    assert invalidated is not None
    assert invalidated.status == SignalStatus.INVALIDATED
    assert invalidated.signal_id == active.signal_id
    assert invalidated.validity.status == SignalValidityStatus.INVALID
    assert invalidated.validity.invalid_reason == "analysis_identity_mismatch"
    assert update.event_type == SignalEventType.SIGNAL_INVALIDATED
    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["lifecycle_state"] == SignalRuntimeLifecycleState.DEGRADED.value
    assert diagnostics["invalidated_signal_keys"] == 1

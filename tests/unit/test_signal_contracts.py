from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from cryptotechnolog.core.event import Priority
from cryptotechnolog.market_data import MarketDataTimeframe
from cryptotechnolog.signals import (
    SignalDirection,
    SignalEventSource,
    SignalEventType,
    SignalFreshness,
    SignalReasonCode,
    SignalSnapshot,
    SignalSnapshotPayload,
    SignalStatus,
    SignalValidity,
    SignalValidityStatus,
    build_signal_event,
)


def test_signal_validity_exposes_readiness_semantics() -> None:
    validity = SignalValidity(
        status=SignalValidityStatus.WARMING,
        observed_inputs=2,
        required_inputs=3,
        missing_inputs=("analysis",),
    )

    assert not validity.is_valid
    assert validity.is_warming
    assert validity.missing_inputs_count == 1
    assert validity.readiness_ratio == Decimal("0.6667")


def test_signal_snapshot_enforces_basic_buy_invariants() -> None:
    snapshot = SignalSnapshot.candidate(
        contour_name="phase8_signal_contour",
        symbol="BTC/USDT",
        exchange="bybit",
        timeframe=MarketDataTimeframe.M15,
        freshness=SignalFreshness(generated_at=datetime(2026, 3, 20, tzinfo=UTC)),
        validity=SignalValidity(
            status=SignalValidityStatus.VALID,
            observed_inputs=3,
            required_inputs=3,
        ),
        direction=SignalDirection.BUY,
        confidence=Decimal("0.8100"),
        entry_price=Decimal("100"),
        stop_loss=Decimal("95"),
        take_profit=Decimal("110"),
        reason_code=SignalReasonCode.CONTEXT_READY,
    )

    assert snapshot.status == SignalStatus.ACTIVE
    assert snapshot.is_actionable


def test_signal_snapshot_rejects_invalid_sell_price_order() -> None:
    with pytest.raises(ValueError, match="SELL сигнал требует"):
        SignalSnapshot.candidate(
            contour_name="phase8_signal_contour",
            symbol="ETH/USDT",
            exchange="okx",
            timeframe=MarketDataTimeframe.H1,
            freshness=SignalFreshness(generated_at=datetime(2026, 3, 20, tzinfo=UTC)),
            validity=SignalValidity(
                status=SignalValidityStatus.VALID,
                observed_inputs=3,
                required_inputs=3,
            ),
            direction=SignalDirection.SELL,
            entry_price=Decimal("100"),
            stop_loss=Decimal("95"),
            take_profit=Decimal("90"),
        )


def test_signal_snapshot_payload_preserves_contract_shape() -> None:
    snapshot = SignalSnapshot.candidate(
        contour_name="phase8_signal_contour",
        symbol="SOL/USDT",
        exchange="binance",
        timeframe=MarketDataTimeframe.H4,
        freshness=SignalFreshness(
            generated_at=datetime(2026, 3, 20, tzinfo=UTC),
            expires_at=datetime(2026, 3, 20, 1, tzinfo=UTC),
        ),
        validity=SignalValidity(
            status=SignalValidityStatus.WARMING,
            observed_inputs=2,
            required_inputs=3,
            missing_inputs=("intelligence",),
        ),
        reason_code=SignalReasonCode.CONTEXT_INCOMPLETE,
        metadata={"source": "contract_lock"},
    )

    payload = SignalSnapshotPayload.from_snapshot(snapshot)

    assert payload.symbol == "SOL/USDT"
    assert payload.validity_status == SignalValidityStatus.WARMING.value
    assert payload.missing_inputs == ("intelligence",)
    assert payload.metadata["source"] == "contract_lock"


def test_signal_freshness_requires_reference_time_for_expiry_truth() -> None:
    freshness = SignalFreshness(
        generated_at=datetime(2026, 3, 20, 0, 0, tzinfo=UTC),
        expires_at=datetime(2026, 3, 20, 0, 5, tzinfo=UTC),
    )

    assert freshness.has_structurally_valid_expiry_window
    assert not freshness.is_expired_at(datetime(2026, 3, 20, 0, 4, 59, tzinfo=UTC))
    assert freshness.is_expired_at(datetime(2026, 3, 20, 0, 5, tzinfo=UTC))


def test_signal_snapshot_rejects_structurally_invalid_expiry_window() -> None:
    with pytest.raises(ValueError, match="expires_at >= generated_at"):
        SignalSnapshot.candidate(
            contour_name="phase8_signal_contour",
            symbol="SOL/USDT",
            exchange="binance",
            timeframe=MarketDataTimeframe.H4,
            freshness=SignalFreshness(
                generated_at=datetime(2026, 3, 20, 1, 0, tzinfo=UTC),
                expires_at=datetime(2026, 3, 20, 0, 59, tzinfo=UTC),
            ),
            validity=SignalValidity(
                status=SignalValidityStatus.WARMING,
                observed_inputs=2,
                required_inputs=3,
            ),
        )


def test_build_signal_event_uses_typed_vocabulary() -> None:
    snapshot = SignalSnapshot.candidate(
        contour_name="phase8_signal_contour",
        symbol="BTC/USDT",
        exchange="bybit",
        timeframe=MarketDataTimeframe.M5,
        freshness=SignalFreshness(generated_at=datetime(2026, 3, 20, tzinfo=UTC)),
        validity=SignalValidity(
            status=SignalValidityStatus.VALID,
            observed_inputs=3,
            required_inputs=3,
        ),
        direction=SignalDirection.BUY,
        entry_price=Decimal("101"),
        stop_loss=Decimal("99"),
        take_profit=Decimal("106"),
    )

    event = build_signal_event(
        event_type=SignalEventType.SIGNAL_EMITTED,
        source=SignalEventSource.SIGNAL_RUNTIME.value,
        payload=SignalSnapshotPayload.from_snapshot(snapshot),
    )

    assert event.event_type == SignalEventType.SIGNAL_EMITTED.value
    assert event.source == SignalEventSource.SIGNAL_RUNTIME.value
    assert event.priority == Priority.HIGH
    assert event.payload["symbol"] == "BTC/USDT"

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from cryptotechnolog.core.event import Priority
from cryptotechnolog.intelligence import (
    DEFAULT_DERYA_CLASSIFICATION_BASIS,
    DeryaAssessment,
    DeryaObservation,
    DeryaRegime,
    DeryaRegimeChangedPayload,
    DeryaResolutionState,
    IndicatorSnapshot,
    IndicatorUpdatedPayload,
    IndicatorValidity,
    IndicatorValueStatus,
    IntelligenceEventSource,
    IntelligenceEventType,
    build_intelligence_event,
    calculate_derya_confidence,
    classify_derya_regime_candidate,
    resolve_derya_regime,
)
from cryptotechnolog.market_data import MarketDataTimeframe


def test_indicator_validity_exposes_warming_semantics() -> None:
    validity = IndicatorValidity(
        status=IndicatorValueStatus.WARMING,
        observed_bars=8,
        required_bars=14,
    )

    assert not validity.is_valid
    assert validity.is_warming
    assert validity.warming_bars_remaining == 6


def test_indicator_event_payload_preserves_contract_shape() -> None:
    snapshot = IndicatorSnapshot(
        symbol="BTC/USDT",
        exchange="bybit",
        timeframe=MarketDataTimeframe.H1,
        indicator_name="RSI",
        value=Decimal("57.25"),
        updated_at=datetime(2026, 3, 20, 12, 0, tzinfo=UTC),
        validity=IndicatorValidity(
            status=IndicatorValueStatus.VALID,
            observed_bars=14,
            required_bars=14,
        ),
        parameters={"period": 14},
    )

    payload = IndicatorUpdatedPayload.from_snapshot(snapshot)
    event = build_intelligence_event(
        event_type=IntelligenceEventType.INDICATOR_UPDATED,
        payload=payload,
        source=IntelligenceEventSource.INDICATOR_ENGINE.value,
        correlation_id=uuid4(),
    )

    assert payload.timeframe == "1h"
    assert payload.value == "57.25"
    assert payload.validity_status == IndicatorValueStatus.VALID.value
    assert event.event_type == IntelligenceEventType.INDICATOR_UPDATED.value
    assert event.priority == Priority.NORMAL
    assert event.payload["indicator_name"] == "RSI"


def test_derya_candidate_classification_is_deterministic() -> None:
    basis = DEFAULT_DERYA_CLASSIFICATION_BASIS

    assert (
        classify_derya_regime_candidate(
            DeryaObservation(
                raw_efficiency=Decimal("0.74"),
                smoothed_efficiency=Decimal("0.72"),
                efficiency_slope=Decimal("0.03"),
                observed_bars=20,
            ),
            basis,
        )
        == DeryaRegime.EXPANSION
    )
    assert (
        classify_derya_regime_candidate(
            DeryaObservation(
                raw_efficiency=Decimal("0.70"),
                smoothed_efficiency=Decimal("0.69"),
                efficiency_slope=Decimal("0.00"),
                observed_bars=20,
            ),
            basis,
        )
        == DeryaRegime.EXHAUSTION
    )
    assert (
        classify_derya_regime_candidate(
            DeryaObservation(
                raw_efficiency=Decimal("0.28"),
                smoothed_efficiency=Decimal("0.29"),
                efficiency_slope=Decimal("-0.03"),
                observed_bars=20,
            ),
            basis,
        )
        == DeryaRegime.COLLAPSE
    )
    assert (
        classify_derya_regime_candidate(
            DeryaObservation(
                raw_efficiency=Decimal("0.30"),
                smoothed_efficiency=Decimal("0.31"),
                efficiency_slope=Decimal("-0.01"),
                observed_bars=20,
            ),
            basis,
        )
        == DeryaRegime.RECOVERY
    )


def test_derya_resolve_regime_holds_previous_regime_inside_hysteresis() -> None:
    regime = resolve_derya_regime(
        observation=DeryaObservation(
            raw_efficiency=Decimal("0.66"),
            smoothed_efficiency=Decimal("0.66"),
            efficiency_slope=Decimal("-0.04"),
            observed_bars=20,
        ),
        previous_regime=DeryaRegime.EXPANSION,
        previous_regime_duration_bars=5,
    )

    assert regime == DeryaRegime.EXPANSION


def test_derya_confidence_is_simple_distance_to_threshold() -> None:
    confidence = calculate_derya_confidence(
        regime=DeryaRegime.EXPANSION,
        observation=DeryaObservation(
            raw_efficiency=Decimal("0.80"),
            smoothed_efficiency=Decimal("0.70"),
            efficiency_slope=Decimal("0.02"),
            observed_bars=20,
        ),
    )

    assert confidence == Decimal("0.5000")


def test_derya_regime_changed_payload_keeps_contract_basis() -> None:
    assessment = DeryaAssessment(
        symbol="ETH/USDT",
        exchange="okx",
        timeframe=MarketDataTimeframe.H4,
        updated_at=datetime(2026, 3, 20, 12, 30, tzinfo=UTC),
        validity=IndicatorValidity(
            status=IndicatorValueStatus.VALID,
            observed_bars=30,
            required_bars=20,
        ),
        confidence=Decimal("0.7500"),
        raw_efficiency=Decimal("0.71"),
        smoothed_efficiency=Decimal("0.69"),
        efficiency_slope=Decimal("0.018"),
        current_regime=DeryaRegime.EXPANSION,
        previous_regime=DeryaRegime.RECOVERY,
        resolution_state=DeryaResolutionState.TRANSITIONED,
        regime_duration_bars=4,
        regime_persistence_ratio=Decimal("1"),
    )

    payload = DeryaRegimeChangedPayload.from_assessment(assessment)
    event = build_intelligence_event(
        event_type=IntelligenceEventType.DERYA_REGIME_CHANGED,
        payload=payload,
        source=IntelligenceEventSource.DERYA_ENGINE.value,
    )

    assert payload.current_regime == DeryaRegime.EXPANSION.value
    assert payload.previous_regime == DeryaRegime.RECOVERY.value
    assert payload.classification_basis["min_persistence_bars"] == 3
    assert event.priority == Priority.HIGH
    assert event.payload["smoothed_efficiency"] == "0.69"

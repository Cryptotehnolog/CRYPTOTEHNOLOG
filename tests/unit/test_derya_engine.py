from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from cryptotechnolog.intelligence import (
    DeryaEngine,
    DeryaEngineConfig,
    DeryaRegime,
    DeryaResolutionState,
)
from cryptotechnolog.market_data import MarketDataTimeframe, OHLCVBarContract


def _make_bar(
    *,
    index: int,
    open_: str,
    high: str,
    low: str,
    close: str,
) -> OHLCVBarContract:
    open_time = datetime(2026, 3, 20, 12, 0, tzinfo=UTC) + timedelta(minutes=index)
    close_time = open_time + timedelta(minutes=1)
    return OHLCVBarContract(
        symbol="BTC/USDT",
        exchange="bybit",
        timeframe=MarketDataTimeframe.M1,
        open_time=open_time,
        close_time=close_time,
        open=Decimal(open_),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=Decimal("10"),
        is_closed=True,
    )


def _build_engine() -> DeryaEngine:
    return DeryaEngine(
        DeryaEngineConfig(
            smoothing_window=3,
            history_limit=64,
            regime_history_limit=16,
        )
    )


def _seed_expansion_state(engine: DeryaEngine) -> None:
    closes = ["107", "108", "109", "110"]
    for i, close in enumerate(closes):
        engine.update_bar(_make_bar(index=i, open_="100", high="110", low="100", close=close))


def test_zero_range_bar_returns_zero_efficiency() -> None:
    engine = _build_engine()
    assessment = engine.update_bar(
        _make_bar(index=0, open_="100", high="100", low="100", close="100")
    )

    assert assessment.raw_efficiency == Decimal("0")
    assert assessment.smoothed_efficiency == Decimal("0.0000")
    assert assessment.resolution_state == DeryaResolutionState.NOT_READY


def test_insufficient_history_stays_non_ready() -> None:
    engine = _build_engine()

    first = engine.update_bar(_make_bar(index=0, open_="100", high="110", low="100", close="109"))
    second = engine.update_bar(_make_bar(index=1, open_="110", high="120", low="110", close="119"))
    third = engine.update_bar(_make_bar(index=2, open_="120", high="130", low="120", close="129"))

    assert first.validity.is_warming
    assert second.validity.is_warming
    assert third.validity.is_warming
    assert third.current_regime is None
    assert third.resolution_state == DeryaResolutionState.NOT_READY


def test_engine_reaches_stable_expansion_after_ready_state() -> None:
    engine = _build_engine()
    assessments = [
        engine.update_bar(_make_bar(index=i, open_="100", high="110", low="100", close=close))
        for i, close in enumerate(["107", "108", "109", "110"])
    ]

    assert assessments[-1].validity.is_valid
    assert assessments[-1].current_regime == DeryaRegime.EXPANSION
    assert assessments[-1].resolution_state == DeryaResolutionState.TRANSITIONED
    assert assessments[-1].confidence is not None


def test_engine_reaches_stable_collapse_after_ready_state() -> None:
    engine = _build_engine()
    closes = ["103", "102", "101", "100.5"]
    assessments = [
        engine.update_bar(_make_bar(index=i, open_="100", high="110", low="100", close=close))
        for i, close in enumerate(closes)
    ]

    assert assessments[-1].validity.is_valid
    assert assessments[-1].current_regime == DeryaRegime.COLLAPSE
    assert assessments[-1].resolution_state == DeryaResolutionState.TRANSITIONED


def test_hysteresis_holds_expansion_inside_neutral_band() -> None:
    engine = _build_engine()
    _seed_expansion_state(engine)

    assessment = engine.update_bar(
        _make_bar(index=5, open_="100", high="110", low="100", close="104")
    )

    assert assessment.current_regime == DeryaRegime.EXPANSION
    assert assessment.resolution_state == DeryaResolutionState.CARRIED_FORWARD


def test_transition_requires_persistence_before_switch() -> None:
    engine = _build_engine()
    _seed_expansion_state(engine)

    first_low = engine.update_bar(
        _make_bar(index=10, open_="100", high="110", low="100", close="100.5")
    )
    second_low = engine.update_bar(
        _make_bar(index=11, open_="100", high="110", low="100", close="100.4")
    )
    third_low = engine.update_bar(
        _make_bar(index=12, open_="100", high="110", low="100", close="100.3")
    )
    fourth_low = engine.update_bar(
        _make_bar(index=13, open_="100", high="110", low="100", close="100.2")
    )
    fifth_low = engine.update_bar(
        _make_bar(index=14, open_="100", high="110", low="100", close="100.1")
    )
    sixth_low = engine.update_bar(
        _make_bar(index=15, open_="100", high="110", low="100", close="100.1")
    )

    assert first_low.current_regime == DeryaRegime.EXPANSION
    assert first_low.resolution_state == DeryaResolutionState.CARRIED_FORWARD
    assert second_low.current_regime == DeryaRegime.EXPANSION
    assert second_low.resolution_state == DeryaResolutionState.CARRIED_FORWARD
    assert third_low.current_regime == DeryaRegime.EXPANSION
    assert third_low.resolution_state == DeryaResolutionState.CARRIED_FORWARD
    assert fourth_low.current_regime == DeryaRegime.EXPANSION
    assert fourth_low.resolution_state == DeryaResolutionState.CARRIED_FORWARD
    assert fifth_low.current_regime == DeryaRegime.EXPANSION
    assert fifth_low.resolution_state == DeryaResolutionState.CARRIED_FORWARD
    assert sixth_low.current_regime == DeryaRegime.RECOVERY
    assert sixth_low.resolution_state == DeryaResolutionState.TRANSITIONED


def test_borderline_bars_do_not_create_extra_flapping() -> None:
    engine = _build_engine()
    _seed_expansion_state(engine)

    borderline_closes = ["103.6", "104.0", "104.2", "103.8", "104.1"]
    assessments = [
        engine.update_bar(
            _make_bar(index=20 + idx, open_="100", high="110", low="100", close=close)
        )
        for idx, close in enumerate(borderline_closes)
    ]

    assert all(item.current_regime == DeryaRegime.EXPANSION for item in assessments)
    assert all(item.resolution_state != DeryaResolutionState.TRANSITIONED for item in assessments)


def test_query_surface_returns_current_assessment_history_and_series() -> None:
    engine = _build_engine()
    last = None
    for i, close in enumerate(["107", "108", "109", "110"]):
        last = engine.update_bar(
            _make_bar(index=i, open_="100", high="110", low="100", close=close)
        )

    current = engine.get_current_assessment(
        exchange="bybit",
        symbol="BTC/USDT",
        timeframe=MarketDataTimeframe.M1,
    )
    raw_series = engine.get_recent_efficiency_series(
        exchange="bybit",
        symbol="BTC/USDT",
        timeframe=MarketDataTimeframe.M1,
    )
    smoothed_series = engine.get_recent_smoothed_series(
        exchange="bybit",
        symbol="BTC/USDT",
        timeframe=MarketDataTimeframe.M1,
    )
    regime_history = engine.get_recent_regime_history(
        exchange="bybit",
        symbol="BTC/USDT",
        timeframe=MarketDataTimeframe.M1,
    )

    assert current == last
    assert len(raw_series) == 4
    assert len(smoothed_series) == 4
    assert regime_history[-1].current_regime == DeryaRegime.EXPANSION


def test_regime_changed_event_can_be_built_from_transition_assessment() -> None:
    engine = _build_engine()
    transition = None
    for i, close in enumerate(["107", "108", "109", "110"]):
        transition = engine.update_bar(
            _make_bar(index=i, open_="100", high="110", low="100", close=close)
        )

    assert transition is not None
    event = engine.build_regime_changed_event(transition)

    assert event is not None
    assert event.payload["current_regime"] == DeryaRegime.EXPANSION.value
    assert event.payload["resolution_state"] == DeryaResolutionState.TRANSITIONED.value

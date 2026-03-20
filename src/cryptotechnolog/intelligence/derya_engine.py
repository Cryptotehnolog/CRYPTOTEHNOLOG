"""
Stateful DERYA foundation machine для Phase 7.

Этот модуль реализует только bar-efficiency regime engine:
- OHLCV bar-efficiency proxy;
- smoothing и slope;
- deterministic 4-regime machine;
- persistence / hysteresis / carry-forward semantics;
- query surface для следующего шага runtime integration.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING

from cryptotechnolog.market_data import MarketDataTimeframe, OHLCVBarContract

from .events import (
    DeryaRegimeChangedPayload,
    IntelligenceEventSource,
    IntelligenceEventType,
    build_intelligence_event,
)
from .models import (
    DEFAULT_DERYA_CLASSIFICATION_BASIS,
    DeryaAssessment,
    DeryaClassificationBasis,
    DeryaObservation,
    DeryaRegime,
    DeryaResolutionState,
    IndicatorValidity,
    IndicatorValueStatus,
    calculate_derya_confidence,
    classify_derya_regime_candidate,
    resolve_derya_regime,
)

if TYPE_CHECKING:
    from datetime import datetime

    from cryptotechnolog.core.event import Event


type DeryaStateKey = tuple[str, str, MarketDataTimeframe]


@dataclass(slots=True, frozen=True)
class DeryaEngineConfig:
    """Конфигурация stateful DERYA foundation machine."""

    basis: DeryaClassificationBasis = field(
        default_factory=lambda: DEFAULT_DERYA_CLASSIFICATION_BASIS
    )
    smoothing_window: int = 3
    history_limit: int = 128
    regime_history_limit: int = 32

    @property
    def required_history_bars(self) -> int:
        """Минимальное количество баров для ready-state."""
        return max(self.smoothing_window + 1, self.basis.min_persistence_bars + 1)


@dataclass(slots=True, frozen=True)
class DeryaRegimeTransition:
    """Запись о подтверждённом regime transition."""

    symbol: str
    exchange: str
    timeframe: MarketDataTimeframe
    previous_regime: DeryaRegime | None
    current_regime: DeryaRegime
    transitioned_at: datetime
    regime_duration_bars: int


@dataclass(slots=True)
class _DeryaSeriesState:
    """Внутреннее состояние engine для одного exchange/symbol/timeframe."""

    raw_history: deque[Decimal]
    smoothed_history: deque[Decimal]
    assessment_history: deque[DeryaAssessment]
    regime_history: deque[DeryaRegimeTransition]
    current_regime: DeryaRegime | None = None
    regime_duration_bars: int = 0
    pending_regime: DeryaRegime | None = None
    pending_regime_bars: int = 0


class DeryaEngine:
    """Stateful foundation machine для DERYA поверх OHLCV bars."""

    def __init__(self, config: DeryaEngineConfig | None = None) -> None:
        self._config = config or DeryaEngineConfig()
        self._states: dict[DeryaStateKey, _DeryaSeriesState] = {}

    @property
    def config(self) -> DeryaEngineConfig:
        """Вернуть активную конфигурацию engine."""
        return self._config

    def update_bar(self, bar: OHLCVBarContract) -> DeryaAssessment:
        """Обновить state machine новым bar и вернуть текущий typed assessment."""
        key = self._build_key(bar.exchange, bar.symbol, bar.timeframe)
        state = self._states.get(key)
        if state is None:
            state = self._build_empty_state()
            self._states[key] = state

        raw_efficiency = self.calculate_bar_efficiency(bar)
        state.raw_history.append(raw_efficiency)
        smoothed_efficiency = self._calculate_smoothed_efficiency(state.raw_history)
        previous_smoothed = state.smoothed_history[-1] if state.smoothed_history else None
        state.smoothed_history.append(smoothed_efficiency)
        slope = (
            (smoothed_efficiency - previous_smoothed)
            if previous_smoothed is not None
            else Decimal("0")
        )
        observed_bars = len(state.raw_history)
        observation = DeryaObservation(
            raw_efficiency=raw_efficiency,
            smoothed_efficiency=smoothed_efficiency,
            efficiency_slope=slope,
            observed_bars=observed_bars,
        )

        validity = self._build_validity(observed_bars)
        previous_regime = state.current_regime

        if not validity.is_valid:
            assessment = self._build_assessment(
                bar=bar,
                validity=validity,
                observation=observation,
                current_regime=state.current_regime,
                previous_regime=previous_regime,
                resolution_state=DeryaResolutionState.NOT_READY,
                regime_duration_bars=state.regime_duration_bars,
            )
            state.assessment_history.append(assessment)
            return assessment

        resolved_regime, resolution_state = self._resolve_stateful_regime(
            observation=observation,
            state=state,
        )
        transition = (
            resolved_regime is not None
            and resolved_regime != previous_regime
            and resolution_state == DeryaResolutionState.TRANSITIONED
        )
        if transition and resolved_regime is not None:
            state.regime_history.append(
                DeryaRegimeTransition(
                    symbol=bar.symbol,
                    exchange=bar.exchange,
                    timeframe=bar.timeframe,
                    previous_regime=previous_regime,
                    current_regime=resolved_regime,
                    transitioned_at=bar.close_time,
                    regime_duration_bars=state.regime_duration_bars,
                )
            )

        assessment = self._build_assessment(
            bar=bar,
            validity=validity,
            observation=observation,
            current_regime=resolved_regime,
            previous_regime=previous_regime,
            resolution_state=resolution_state,
            regime_duration_bars=state.regime_duration_bars,
        )
        state.assessment_history.append(assessment)
        return assessment

    def get_current_assessment(
        self,
        *,
        exchange: str,
        symbol: str,
        timeframe: MarketDataTimeframe,
    ) -> DeryaAssessment | None:
        """Получить последний assessment для выбранного ключа."""
        state = self._states.get(self._build_key(exchange, symbol, timeframe))
        if state is None or not state.assessment_history:
            return None
        return state.assessment_history[-1]

    def get_recent_regime_history(
        self,
        *,
        exchange: str,
        symbol: str,
        timeframe: MarketDataTimeframe,
    ) -> tuple[DeryaRegimeTransition, ...]:
        """Получить recent regime transition history."""
        state = self._states.get(self._build_key(exchange, symbol, timeframe))
        if state is None:
            return ()
        return tuple(state.regime_history)

    def get_recent_efficiency_series(
        self,
        *,
        exchange: str,
        symbol: str,
        timeframe: MarketDataTimeframe,
    ) -> tuple[Decimal, ...]:
        """Получить recent raw efficiency series."""
        state = self._states.get(self._build_key(exchange, symbol, timeframe))
        if state is None:
            return ()
        return tuple(state.raw_history)

    def get_recent_smoothed_series(
        self,
        *,
        exchange: str,
        symbol: str,
        timeframe: MarketDataTimeframe,
    ) -> tuple[Decimal, ...]:
        """Получить recent smoothed efficiency series."""
        state = self._states.get(self._build_key(exchange, symbol, timeframe))
        if state is None:
            return ()
        return tuple(state.smoothed_history)

    def tracked_keys_count(self) -> int:
        """Вернуть количество tracked DERYA series внутри engine."""
        return len(self._states)

    def build_regime_changed_event(
        self,
        assessment: DeryaAssessment,
    ) -> Event | None:
        """Построить analysis event только для подтверждённого regime transition."""
        if assessment.resolution_state != DeryaResolutionState.TRANSITIONED:
            return None
        return build_intelligence_event(
            event_type=IntelligenceEventType.DERYA_REGIME_CHANGED,
            payload=DeryaRegimeChangedPayload.from_assessment(assessment),
            source=IntelligenceEventSource.DERYA_ENGINE.value,
        )

    @staticmethod
    def calculate_bar_efficiency(bar: OHLCVBarContract) -> Decimal:
        """
        Рассчитать bar-efficiency как OHLCV proxy.

        Формула:
        `abs(close - open) / (high - low)`
        """
        bar_range = bar.high - bar.low
        if bar_range <= 0:
            return Decimal("0")
        body = abs(bar.close - bar.open)
        efficiency = body / bar_range
        if efficiency < 0:
            return Decimal("0")
        if efficiency > 1:
            return Decimal("1")
        return efficiency.quantize(Decimal("0.0001"))

    def _calculate_smoothed_efficiency(self, raw_history: deque[Decimal]) -> Decimal:
        window = min(len(raw_history), self._config.smoothing_window)
        if window <= 0:
            return Decimal("0")
        values = list(raw_history)[-window:]
        return (sum(values, start=Decimal("0")) / Decimal(window)).quantize(Decimal("0.0001"))

    def _build_validity(self, observed_bars: int) -> IndicatorValidity:
        required_bars = self._config.required_history_bars
        if observed_bars < required_bars:
            return IndicatorValidity(
                status=IndicatorValueStatus.WARMING,
                observed_bars=observed_bars,
                required_bars=required_bars,
            )
        return IndicatorValidity(
            status=IndicatorValueStatus.VALID,
            observed_bars=observed_bars,
            required_bars=required_bars,
        )

    def _resolve_stateful_regime(  # noqa: PLR0911
        self,
        *,
        observation: DeryaObservation,
        state: _DeryaSeriesState,
    ) -> tuple[DeryaRegime | None, DeryaResolutionState]:
        candidate = classify_derya_regime_candidate(observation, self._config.basis)
        current_regime = state.current_regime

        if current_regime is None:
            if candidate is None:
                state.regime_duration_bars = 0
                state.pending_regime = None
                state.pending_regime_bars = 0
                return None, DeryaResolutionState.STABLE
            state.current_regime = candidate
            state.regime_duration_bars = 1
            state.pending_regime = None
            state.pending_regime_bars = 0
            return candidate, DeryaResolutionState.TRANSITIONED

        resolved = resolve_derya_regime(
            observation=observation,
            previous_regime=current_regime,
            previous_regime_duration_bars=state.regime_duration_bars,
            basis=self._config.basis,
        )

        if resolved is None:
            state.regime_duration_bars += 1
            state.pending_regime = None
            state.pending_regime_bars = 0
            return current_regime, DeryaResolutionState.CARRIED_FORWARD

        if resolved == current_regime:
            state.regime_duration_bars += 1
            if candidate == current_regime:
                state.pending_regime = None
                state.pending_regime_bars = 0
                return current_regime, DeryaResolutionState.STABLE
            state.pending_regime = None
            state.pending_regime_bars = 0
            return current_regime, DeryaResolutionState.CARRIED_FORWARD

        if state.pending_regime == resolved:
            state.pending_regime_bars += 1
        else:
            state.pending_regime = resolved
            state.pending_regime_bars = 1

        if state.pending_regime_bars < self._config.basis.min_persistence_bars:
            state.regime_duration_bars += 1
            return current_regime, DeryaResolutionState.CARRIED_FORWARD

        state.current_regime = resolved
        state.regime_duration_bars = 1
        state.pending_regime = None
        state.pending_regime_bars = 0
        return resolved, DeryaResolutionState.TRANSITIONED

    def _build_assessment(
        self,
        *,
        bar: OHLCVBarContract,
        validity: IndicatorValidity,
        observation: DeryaObservation,
        current_regime: DeryaRegime | None,
        previous_regime: DeryaRegime | None,
        resolution_state: DeryaResolutionState,
        regime_duration_bars: int,
    ) -> DeryaAssessment:
        persistence_ratio = Decimal("0")
        if current_regime is not None and self._config.basis.min_persistence_bars > 0:
            persistence_ratio = Decimal(regime_duration_bars) / Decimal(
                self._config.basis.min_persistence_bars
            )
            persistence_ratio = min(persistence_ratio, Decimal("1"))
            persistence_ratio = persistence_ratio.quantize(Decimal("0.0001"))

        confidence = None
        if validity.is_valid:
            confidence = calculate_derya_confidence(
                regime=current_regime,
                observation=observation,
                basis=self._config.basis,
            )

        metadata = {
            "observed_bars": observation.observed_bars,
            "required_bars": self._config.required_history_bars,
            "bar_efficiency_proxy": "ohlcv_body_over_range",
            "regime_carried_forward": resolution_state == DeryaResolutionState.CARRIED_FORWARD,
            "transition_confirmed": resolution_state == DeryaResolutionState.TRANSITIONED,
        }

        return DeryaAssessment(
            symbol=bar.symbol,
            exchange=bar.exchange,
            timeframe=bar.timeframe,
            updated_at=bar.close_time,
            validity=validity,
            confidence=confidence,
            metadata=metadata,
            raw_efficiency=observation.raw_efficiency,
            smoothed_efficiency=observation.smoothed_efficiency,
            efficiency_slope=observation.efficiency_slope,
            current_regime=current_regime,
            previous_regime=previous_regime,
            resolution_state=resolution_state,
            regime_duration_bars=regime_duration_bars,
            regime_persistence_ratio=persistence_ratio,
            classification_basis=self._config.basis,
        )

    def _build_empty_state(self) -> _DeryaSeriesState:
        return _DeryaSeriesState(
            raw_history=deque(maxlen=self._config.history_limit),
            smoothed_history=deque(maxlen=self._config.history_limit),
            assessment_history=deque(maxlen=self._config.history_limit),
            regime_history=deque(maxlen=self._config.regime_history_limit),
        )

    @staticmethod
    def _build_key(
        exchange: str,
        symbol: str,
        timeframe: MarketDataTimeframe,
    ) -> DeryaStateKey:
        return (exchange, symbol, timeframe)


__all__ = [
    "DeryaEngine",
    "DeryaEngineConfig",
    "DeryaRegimeTransition",
]

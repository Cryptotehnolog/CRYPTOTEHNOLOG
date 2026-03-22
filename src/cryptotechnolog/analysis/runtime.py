"""
Минимальный shared analysis runtime для corrective line C_7R.

Этот runtime:
- принимает completed bars;
- считает ATR и ADX детерминированно;
- хранит query/state-first truth;
- не публикует события и не делает hidden bootstrap.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from cryptotechnolog.market_data import MarketDataTimeframe, OHLCVBarContract

from .models import (
    AdxSnapshot,
    AtrSnapshot,
    DerivedInputStatus,
    DerivedInputValidity,
    RiskDerivedInputsSnapshot,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from cryptotechnolog.market_data.events import BarCompletedPayload


type AnalysisStateKey = tuple[str, str, MarketDataTimeframe]

_QUANT = Decimal("0.0001")


@dataclass(slots=True, frozen=True)
class SharedAnalysisRuntimeConfig:
    """Конфигурация shared analysis runtime для derived bar inputs."""

    atr_period: int = 14
    adx_period: int = 14

    def __post_init__(self) -> None:
        if self.atr_period <= 0:
            raise ValueError("atr_period должен быть положительным")
        if self.adx_period <= 0:
            raise ValueError("adx_period должен быть положительным")

    @property
    def atr_required_bars(self) -> int:
        """Минимум баров для valid ATR."""
        return self.atr_period + 1

    @property
    def adx_required_bars(self) -> int:
        """Минимум баров для valid ADX."""
        return self.adx_period * 2


@dataclass(slots=True)
class SharedAnalysisRuntimeDiagnostics:
    """Operator-facing diagnostics foundation для shared analysis runtime."""

    started: bool = False
    ready: bool = False
    lifecycle_state: str = "built"
    tracked_keys: int = 0
    ready_keys: int = 0
    warming_keys: int = 0
    last_bar_at: str | None = None
    last_failure_reason: str | None = None
    readiness_reasons: tuple[str, ...] = ()
    degraded_reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        """Преобразовать diagnostics в runtime-truth friendly словарь."""
        return {
            "started": self.started,
            "ready": self.ready,
            "lifecycle_state": self.lifecycle_state,
            "tracked_keys": self.tracked_keys,
            "ready_keys": self.ready_keys,
            "warming_keys": self.warming_keys,
            "last_bar_at": self.last_bar_at,
            "last_failure_reason": self.last_failure_reason,
            "readiness_reasons": list(self.readiness_reasons),
            "degraded_reasons": list(self.degraded_reasons),
        }


@dataclass(slots=True, frozen=True)
class SharedAnalysisRuntimeUpdate:
    """Результат одного ingest cycle shared analysis runtime."""

    snapshot: RiskDerivedInputsSnapshot


@dataclass(slots=True)
class _AtrState:
    """Внутреннее состояние расчёта ATR по Уайлдеру."""

    tr_values: list[Decimal] = field(default_factory=list)
    smoothed_tr: Decimal | None = None
    current_value: Decimal | None = None


@dataclass(slots=True)
class _AdxState:
    """Внутреннее состояние расчёта ADX по Уайлдеру."""

    tr_values: list[Decimal] = field(default_factory=list)
    plus_dm_values: list[Decimal] = field(default_factory=list)
    minus_dm_values: list[Decimal] = field(default_factory=list)
    smoothed_tr: Decimal | None = None
    smoothed_plus_dm: Decimal | None = None
    smoothed_minus_dm: Decimal | None = None
    dx_values: list[Decimal] = field(default_factory=list)
    current_value: Decimal | None = None


@dataclass(slots=True)
class _SeriesState:
    """In-memory состояние derived inputs для одного symbol/exchange/timeframe."""

    observed_bars: int = 0
    previous_bar: OHLCVBarContract | None = None
    atr_state: _AtrState = field(default_factory=_AtrState)
    adx_state: _AdxState = field(default_factory=_AdxState)
    latest_snapshot: RiskDerivedInputsSnapshot | None = None


class SharedAnalysisRuntime:
    """Explicit runtime foundation для shared derived analysis inputs."""

    def __init__(
        self,
        config: SharedAnalysisRuntimeConfig | None = None,
        *,
        diagnostics_sink: Callable[[dict[str, object]], None] | None = None,
    ) -> None:
        self.config = config or SharedAnalysisRuntimeConfig()
        self._diagnostics_sink = diagnostics_sink
        self._diagnostics = SharedAnalysisRuntimeDiagnostics()
        self._started = False
        self._states: dict[AnalysisStateKey, _SeriesState] = {}
        self._push_diagnostics()

    @property
    def is_started(self) -> bool:
        """Проверить, активирован ли runtime."""
        return self._started

    async def start(self) -> None:
        """Активировать runtime без hidden bootstrap."""
        if self._started:
            return
        self._started = True
        self._refresh_diagnostics(
            lifecycle_state="warming",
            ready=False,
            last_failure_reason=None,
            readiness_reasons=("no_completed_bars_processed",),
            degraded_reasons=(),
        )

    async def stop(self) -> None:
        """Остановить runtime и сбросить operator-facing state."""
        if not self._started:
            return
        self._started = False
        self._states = {}
        self._refresh_diagnostics(
            lifecycle_state="stopped",
            ready=False,
            tracked_keys=0,
            ready_keys=0,
            warming_keys=0,
            last_bar_at=None,
            last_failure_reason=None,
            readiness_reasons=("runtime_stopped",),
            degraded_reasons=(),
        )

    def mark_degraded(self, reason: str) -> None:
        """Зафиксировать деградацию ingest/runtime path без скрытого fallback."""
        self._refresh_diagnostics(
            ready=False,
            lifecycle_state="degraded",
            last_failure_reason=reason,
            degraded_reasons=(reason,),
        )

    def get_runtime_diagnostics(self) -> dict[str, object]:
        """Вернуть diagnostics shared analysis runtime."""
        return self._diagnostics.to_dict()

    def ingest_completed_bar(self, bar: OHLCVBarContract) -> SharedAnalysisRuntimeUpdate:
        """Принять completed bar и обновить shared derived inputs."""
        self._ensure_started("ingest_completed_bar")
        if not bar.is_closed:
            raise ValueError("SharedAnalysisRuntime принимает только completed bars")

        key = (bar.exchange, bar.symbol, bar.timeframe)
        state = self._states.get(key)
        if state is None:
            state = _SeriesState()
            self._states[key] = state

        state.observed_bars += 1
        snapshot = self._build_snapshot(bar=bar, state=state)
        state.latest_snapshot = snapshot
        state.previous_bar = bar
        self._refresh_runtime_state(last_bar_at=bar.close_time.astimezone(UTC).isoformat())
        return SharedAnalysisRuntimeUpdate(snapshot=snapshot)

    def ingest_bar_completed_payload(
        self,
        payload: BarCompletedPayload,
    ) -> SharedAnalysisRuntimeUpdate:
        """Принять typed BAR_COMPLETED payload и обновить shared derived inputs."""
        return self.ingest_completed_bar(self._bar_from_payload(payload))

    def get_risk_derived_inputs(
        self,
        *,
        exchange: str,
        symbol: str,
        timeframe: MarketDataTimeframe,
    ) -> RiskDerivedInputsSnapshot | None:
        """Получить последний shared derived inputs snapshot."""
        state = self._states.get((exchange, symbol, timeframe))
        if state is None:
            return None
        return state.latest_snapshot

    def get_atr_snapshot(
        self,
        *,
        exchange: str,
        symbol: str,
        timeframe: MarketDataTimeframe,
    ) -> AtrSnapshot | None:
        """Получить последний ATR snapshot."""
        snapshot = self.get_risk_derived_inputs(
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
        )
        return snapshot.atr if snapshot is not None else None

    def get_adx_snapshot(
        self,
        *,
        exchange: str,
        symbol: str,
        timeframe: MarketDataTimeframe,
    ) -> AdxSnapshot | None:
        """Получить последний ADX snapshot."""
        snapshot = self.get_risk_derived_inputs(
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
        )
        return snapshot.adx if snapshot is not None else None

    def _build_snapshot(
        self,
        *,
        bar: OHLCVBarContract,
        state: _SeriesState,
    ) -> RiskDerivedInputsSnapshot:
        previous_bar = state.previous_bar
        atr_value: Decimal | None = None
        adx_value: Decimal | None = None

        if previous_bar is not None:
            tr = self._calculate_true_range(bar, previous_bar)
            atr_value = self._update_atr(state.atr_state, tr)
            plus_dm, minus_dm = self._calculate_directional_movement(bar, previous_bar)
            adx_value = self._update_adx(state.adx_state, tr, plus_dm, minus_dm)

        updated_at = bar.close_time
        atr_validity = self._build_validity(
            observed_bars=state.observed_bars,
            required_bars=self.config.atr_required_bars,
            has_value=atr_value is not None,
        )
        adx_validity = self._build_validity(
            observed_bars=state.observed_bars,
            required_bars=self.config.adx_required_bars,
            has_value=adx_value is not None,
        )

        atr_snapshot = AtrSnapshot(
            symbol=bar.symbol,
            exchange=bar.exchange,
            timeframe=bar.timeframe,
            updated_at=updated_at,
            period=self.config.atr_period,
            value=atr_value,
            validity=atr_validity,
            metadata={
                "source_layer": "shared_analysis",
                "calculation_basis": "true_range",
            },
        )
        adx_snapshot = AdxSnapshot(
            symbol=bar.symbol,
            exchange=bar.exchange,
            timeframe=bar.timeframe,
            updated_at=updated_at,
            period=self.config.adx_period,
            value=adx_value,
            validity=adx_validity,
            metadata={
                "source_layer": "shared_analysis",
                "calculation_basis": "directional_movement_index",
            },
        )
        return RiskDerivedInputsSnapshot(
            symbol=bar.symbol,
            exchange=bar.exchange,
            timeframe=bar.timeframe,
            updated_at=updated_at,
            atr=atr_snapshot,
            adx=adx_snapshot,
            metadata={
                "observed_bars": state.observed_bars,
                "atr_required_bars": self.config.atr_required_bars,
                "adx_required_bars": self.config.adx_required_bars,
            },
        )

    def _update_atr(self, state: _AtrState, tr: Decimal) -> Decimal | None:
        period = self.config.atr_period
        if state.smoothed_tr is None:
            state.tr_values.append(tr)
            if len(state.tr_values) < period:
                return None
            state.smoothed_tr = sum(state.tr_values, start=Decimal("0"))
        else:
            state.smoothed_tr = self._wilder_smooth(state.smoothed_tr, tr, period)

        state.current_value = (state.smoothed_tr / Decimal(period)).quantize(_QUANT)
        return state.current_value

    def _update_adx(
        self,
        state: _AdxState,
        tr: Decimal,
        plus_dm: Decimal,
        minus_dm: Decimal,
    ) -> Decimal | None:
        period = self.config.adx_period

        if state.smoothed_tr is None:
            state.tr_values.append(tr)
            state.plus_dm_values.append(plus_dm)
            state.minus_dm_values.append(minus_dm)
            if len(state.tr_values) < period:
                return None
            state.smoothed_tr = sum(state.tr_values, start=Decimal("0"))
            state.smoothed_plus_dm = sum(state.plus_dm_values, start=Decimal("0"))
            state.smoothed_minus_dm = sum(state.minus_dm_values, start=Decimal("0"))
        else:
            state.smoothed_tr = self._wilder_smooth(state.smoothed_tr, tr, period)
            state.smoothed_plus_dm = self._wilder_smooth(
                state.smoothed_plus_dm or Decimal("0"),
                plus_dm,
                period,
            )
            state.smoothed_minus_dm = self._wilder_smooth(
                state.smoothed_minus_dm or Decimal("0"),
                minus_dm,
                period,
            )

        if state.smoothed_tr <= 0:
            dx = Decimal("0")
        else:
            plus_di = (
                Decimal("100") * (state.smoothed_plus_dm or Decimal("0"))
            ) / state.smoothed_tr
            minus_di = (
                Decimal("100") * (state.smoothed_minus_dm or Decimal("0"))
            ) / state.smoothed_tr
            di_sum = plus_di + minus_di
            dx = (
                Decimal("0") if di_sum <= 0 else (Decimal("100") * abs(plus_di - minus_di) / di_sum)
            )

        if state.current_value is None:
            state.dx_values.append(dx)
            if len(state.dx_values) < period:
                return None
            state.current_value = (
                sum(state.dx_values, start=Decimal("0")) / Decimal(period)
            ).quantize(_QUANT)
            return state.current_value

        state.current_value = (
            ((state.current_value * Decimal(period - 1)) + dx) / Decimal(period)
        ).quantize(_QUANT)
        return state.current_value

    def _refresh_runtime_state(self, *, last_bar_at: str) -> None:
        tracked_keys = len(self._states)
        ready_keys = sum(
            1
            for state in self._states.values()
            if state.latest_snapshot is not None and state.latest_snapshot.is_fully_ready
        )
        warming_keys = max(tracked_keys - ready_keys, 0)

        readiness_reasons: list[str] = []
        lifecycle_state = "ready"
        ready = True

        if tracked_keys == 0:
            lifecycle_state = "warming"
            ready = False
            readiness_reasons.append("no_completed_bars_processed")
        elif warming_keys > 0:
            lifecycle_state = "warming"
            ready = False
            readiness_reasons.append("derived_inputs_warming")

        self._refresh_diagnostics(
            ready=ready,
            lifecycle_state=lifecycle_state,
            tracked_keys=tracked_keys,
            ready_keys=ready_keys,
            warming_keys=warming_keys,
            last_bar_at=last_bar_at,
            last_failure_reason=None,
            readiness_reasons=tuple(readiness_reasons),
            degraded_reasons=(),
        )

    @staticmethod
    def _calculate_true_range(bar: OHLCVBarContract, previous_bar: OHLCVBarContract) -> Decimal:
        return max(
            bar.high - bar.low,
            abs(bar.high - previous_bar.close),
            abs(bar.low - previous_bar.close),
        )

    @staticmethod
    def _calculate_directional_movement(
        bar: OHLCVBarContract,
        previous_bar: OHLCVBarContract,
    ) -> tuple[Decimal, Decimal]:
        up_move = bar.high - previous_bar.high
        down_move = previous_bar.low - bar.low
        plus_dm = up_move if up_move > down_move and up_move > 0 else Decimal("0")
        minus_dm = down_move if down_move > up_move and down_move > 0 else Decimal("0")
        return plus_dm, minus_dm

    @staticmethod
    def _wilder_smooth(previous_smoothed: Decimal, value: Decimal, period: int) -> Decimal:
        return previous_smoothed - (previous_smoothed / Decimal(period)) + value

    @staticmethod
    def _build_validity(
        *,
        observed_bars: int,
        required_bars: int,
        has_value: bool,
    ) -> DerivedInputValidity:
        if not has_value:
            return DerivedInputValidity(
                status=DerivedInputStatus.WARMING,
                observed_bars=observed_bars,
                required_bars=required_bars,
            )
        return DerivedInputValidity(
            status=DerivedInputStatus.VALID,
            observed_bars=observed_bars,
            required_bars=required_bars,
        )

    def _ensure_started(self, operation: str) -> None:
        if not self._started:
            raise RuntimeError(
                f"SharedAnalysisRuntime не запущен. Операция {operation} недоступна до start()."
            )

    @staticmethod
    def _bar_from_payload(payload: BarCompletedPayload) -> OHLCVBarContract:
        return OHLCVBarContract(
            symbol=payload.symbol,
            exchange=payload.exchange,
            timeframe=MarketDataTimeframe(payload.timeframe),
            open_time=datetime.fromisoformat(payload.open_time),
            close_time=datetime.fromisoformat(payload.close_time),
            open=Decimal(payload.open),
            high=Decimal(payload.high),
            low=Decimal(payload.low),
            close=Decimal(payload.close),
            volume=Decimal(payload.volume),
            bid_volume=Decimal(payload.bid_volume),
            ask_volume=Decimal(payload.ask_volume),
            trades_count=payload.trades_count,
            is_closed=payload.is_closed,
            is_gap_affected=payload.is_gap_affected,
        )

    def _refresh_diagnostics(self, **updates: object) -> None:
        current: dict[str, Any] = asdict(self._diagnostics)
        current.update(updates)
        self._diagnostics = SharedAnalysisRuntimeDiagnostics(
            started=self._started,
            ready=bool(current["ready"]),
            lifecycle_state=str(current["lifecycle_state"]),
            tracked_keys=int(current["tracked_keys"]),
            ready_keys=int(current["ready_keys"]),
            warming_keys=int(current["warming_keys"]),
            last_bar_at=str(current["last_bar_at"]) if current["last_bar_at"] is not None else None,
            last_failure_reason=(
                str(current["last_failure_reason"])
                if current["last_failure_reason"] is not None
                else None
            ),
            readiness_reasons=tuple(current.get("readiness_reasons", [])),
            degraded_reasons=tuple(current.get("degraded_reasons", [])),
        )
        self._push_diagnostics()

    def _push_diagnostics(self) -> None:
        if self._diagnostics_sink is not None:
            self._diagnostics_sink(self.get_runtime_diagnostics())


def create_shared_analysis_runtime(
    *,
    config: SharedAnalysisRuntimeConfig | None = None,
    diagnostics_sink: Callable[[dict[str, object]], None] | None = None,
) -> SharedAnalysisRuntime:
    """Собрать explicit runtime foundation shared analysis layer."""
    return SharedAnalysisRuntime(
        config=config,
        diagnostics_sink=diagnostics_sink,
    )


__all__ = [
    "SharedAnalysisRuntime",
    "SharedAnalysisRuntimeConfig",
    "SharedAnalysisRuntimeDiagnostics",
    "SharedAnalysisRuntimeUpdate",
    "create_shared_analysis_runtime",
]

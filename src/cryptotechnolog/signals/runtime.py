"""
Узкий explicit runtime foundation для Phase 8 Signal Generation Foundation.

Этот runtime:
- стартует и останавливается явно;
- не делает hidden bootstrap;
- собирает typed signal context из существующих truth sources;
- поддерживает один минимальный deterministic signal contour;
- хранит query/state-first truth и operator-visible diagnostics.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from cryptotechnolog.config import get_settings
from cryptotechnolog.intelligence import DeryaRegime
from cryptotechnolog.market_data import MarketDataTimeframe, OHLCVBarContract

from .events import SignalEventType, SignalSnapshotPayload
from .models import (
    SignalContext,
    SignalDirection,
    SignalFreshness,
    SignalReasonCode,
    SignalSnapshot,
    SignalStatus,
    SignalValidity,
    SignalValidityStatus,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from cryptotechnolog.analysis import RiskDerivedInputsSnapshot
    from cryptotechnolog.config.settings import Settings
    from cryptotechnolog.intelligence import DeryaAssessment
    from cryptotechnolog.market_data import OrderBookSnapshotContract
    from cryptotechnolog.market_data.events import BarCompletedPayload


type SignalStateKey = tuple[str, str, MarketDataTimeframe, str]


class SignalRuntimeLifecycleState(StrEnum):
    """Lifecycle-состояние signal runtime."""

    NOT_STARTED = "not_started"
    WARMING = "warming"
    READY = "ready"
    DEGRADED = "degraded"
    STOPPED = "stopped"


@dataclass(slots=True, frozen=True)
class SignalRuntimeConfig:
    """Typed runtime-конфигурация следующего шага P_8."""

    contour_name: str = "phase8_signal_contour"
    max_signal_age_seconds: int = 300
    required_context_sources: tuple[str, ...] = ("market_data", "analysis", "intelligence")
    min_adx_for_activation: Decimal = Decimal("20")
    min_derya_confidence: Decimal = Decimal("0.5000")
    risk_reward_multiple: Decimal = Decimal("2")

    def __post_init__(self) -> None:
        if self.max_signal_age_seconds <= 0:
            raise ValueError("max_signal_age_seconds должен быть положительным")
        if self.min_adx_for_activation < 0:
            raise ValueError("min_adx_for_activation не может быть отрицательным")
        if not (Decimal("0") <= self.min_derya_confidence <= Decimal("1")):
            raise ValueError("min_derya_confidence должен находиться в диапазоне [0, 1]")
        if self.risk_reward_multiple <= 0:
            raise ValueError("risk_reward_multiple должен быть положительным")

    @classmethod
    def from_settings(cls, settings: Settings) -> SignalRuntimeConfig:
        """Build signal runtime config from canonical project settings."""
        return cls(
            max_signal_age_seconds=settings.signal_max_age_seconds,
            min_adx_for_activation=Decimal(str(settings.signal_min_trend_strength)),
            min_derya_confidence=Decimal(str(settings.signal_min_regime_confidence)),
            risk_reward_multiple=Decimal(str(settings.signal_target_risk_reward)),
        )


@dataclass(slots=True)
class SignalRuntimeDiagnostics:
    """Operator-visible diagnostics contract signal runtime."""

    started: bool = False
    ready: bool = False
    lifecycle_state: SignalRuntimeLifecycleState = SignalRuntimeLifecycleState.NOT_STARTED
    tracked_signal_keys: int = 0
    active_signal_keys: int = 0
    invalidated_signal_keys: int = 0
    expired_signal_keys: int = 0
    last_context_at: str | None = None
    last_signal_id: str | None = None
    last_event_type: str | None = None
    last_failure_reason: str | None = None
    readiness_reasons: list[str] = field(default_factory=list)
    degraded_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        """Сконвертировать diagnostics в transport-neutral словарь."""
        return {
            "started": self.started,
            "ready": self.ready,
            "lifecycle_state": self.lifecycle_state.value,
            "tracked_signal_keys": self.tracked_signal_keys,
            "active_signal_keys": self.active_signal_keys,
            "invalidated_signal_keys": self.invalidated_signal_keys,
            "expired_signal_keys": self.expired_signal_keys,
            "last_context_at": self.last_context_at,
            "last_signal_id": self.last_signal_id,
            "last_event_type": self.last_event_type,
            "last_failure_reason": self.last_failure_reason,
            "readiness_reasons": list(self.readiness_reasons),
            "degraded_reasons": list(self.degraded_reasons),
        }


@dataclass(slots=True, frozen=True)
class SignalRuntimeUpdate:
    """Typed update contract signal runtime foundation."""

    context: SignalContext
    signal: SignalSnapshot | None
    event_type: SignalEventType | None = None
    emitted_payload: SignalSnapshotPayload | None = None


class SignalRuntime:
    """Explicit runtime foundation для signal layer Phase 8."""

    def __init__(
        self,
        config: SignalRuntimeConfig | None = None,
        *,
        diagnostics_sink: Callable[[dict[str, object]], None] | None = None,
    ) -> None:
        self.config = config or SignalRuntimeConfig()
        self._diagnostics_sink = diagnostics_sink
        self._diagnostics = SignalRuntimeDiagnostics()
        self._started = False
        self._contexts: dict[SignalStateKey, SignalContext] = {}
        self._signals: dict[SignalStateKey, SignalSnapshot] = {}
        self._push_diagnostics()

    @property
    def is_started(self) -> bool:
        """Проверить, активирован ли runtime."""
        return self._started

    async def start(self) -> None:
        """Поднять runtime без hidden bootstrap."""
        if self._started:
            return
        self._started = True
        self._refresh_diagnostics(
            lifecycle_state=SignalRuntimeLifecycleState.WARMING,
            ready=False,
            last_failure_reason=None,
            readiness_reasons=("no_signal_context_processed",),
            degraded_reasons=(),
        )

    async def stop(self) -> None:
        """Остановить runtime и очистить operator-visible state."""
        if not self._started:
            return
        self._started = False
        self._contexts = {}
        self._signals = {}
        self._refresh_diagnostics(
            lifecycle_state=SignalRuntimeLifecycleState.STOPPED,
            ready=False,
            tracked_signal_keys=0,
            active_signal_keys=0,
            invalidated_signal_keys=0,
            expired_signal_keys=0,
            last_context_at=None,
            last_signal_id=None,
            last_event_type=None,
            last_failure_reason=None,
            readiness_reasons=("runtime_stopped",),
            degraded_reasons=(),
        )

    def mark_degraded(self, reason: str) -> None:
        """Зафиксировать деградацию runtime/ingest path."""
        self._refresh_diagnostics(
            lifecycle_state=SignalRuntimeLifecycleState.DEGRADED,
            ready=False,
            last_failure_reason=reason,
            degraded_reasons=(reason,),
        )

    def get_runtime_diagnostics(self) -> dict[str, object]:
        """Вернуть operator-visible diagnostics."""
        return self._diagnostics.to_dict()

    def ingest_truths(
        self,
        *,
        bar: OHLCVBarContract,
        orderbook: OrderBookSnapshotContract | None = None,
        derived_inputs: RiskDerivedInputsSnapshot | None = None,
        derya: DeryaAssessment | None = None,
        metadata: dict[str, object] | None = None,
        reference_time: datetime | None = None,
    ) -> SignalRuntimeUpdate:
        """
        Принять existing truth sources, собрать SignalContext внутри signal layer
        и обновить signal state.
        """
        self._ensure_started("ingest_truths")
        context = self._assemble_signal_context(
            bar=bar,
            orderbook=orderbook,
            derived_inputs=derived_inputs,
            derya=derya,
            metadata=metadata,
        )
        return self._ingest_signal_context(context, reference_time=reference_time)

    def ingest_bar_completed_payload(
        self,
        payload: BarCompletedPayload,
        *,
        orderbook: OrderBookSnapshotContract | None = None,
        derived_inputs: RiskDerivedInputsSnapshot | None = None,
        derya: DeryaAssessment | None = None,
        metadata: dict[str, object] | None = None,
        reference_time: datetime | None = None,
    ) -> SignalRuntimeUpdate:
        """Принять typed BAR_COMPLETED payload и existing truths без внешней сборки context."""
        return self.ingest_truths(
            bar=self._bar_from_payload(payload),
            orderbook=orderbook,
            derived_inputs=derived_inputs,
            derya=derya,
            metadata=metadata,
            reference_time=reference_time,
        )

    def _assemble_signal_context(
        self,
        *,
        bar: OHLCVBarContract,
        orderbook: OrderBookSnapshotContract | None = None,
        derived_inputs: RiskDerivedInputsSnapshot | None = None,
        derya: DeryaAssessment | None = None,
        metadata: dict[str, object] | None = None,
    ) -> SignalContext:
        """Детерминированно собрать typed signal context из существующих truth sources."""
        missing_inputs: list[str] = []
        observed_inputs = 0
        invalid_reason: str | None = None

        if not bar.is_closed:
            invalid_reason = "bar_not_completed"
        else:
            observed_inputs += 1

        if orderbook is not None and not self._matches_market_identity(
            symbol=bar.symbol,
            exchange=bar.exchange,
            orderbook=orderbook,
        ):
            invalid_reason = "orderbook_identity_mismatch"

        if derived_inputs is None:
            missing_inputs.append("analysis")
        elif not self._matches_analysis_identity(bar=bar, derived_inputs=derived_inputs):
            invalid_reason = "analysis_identity_mismatch"
        elif derived_inputs.is_fully_ready:
            observed_inputs += 1
        else:
            missing_inputs.append("analysis")

        if derya is None:
            missing_inputs.append("intelligence")
        elif not self._matches_intelligence_identity(bar=bar, derya=derya):
            invalid_reason = "intelligence_identity_mismatch"
        elif derya.validity.is_valid and derya.current_regime is not None:
            observed_inputs += 1
        else:
            missing_inputs.append("intelligence")

        validity = self._build_context_validity(
            observed_inputs=observed_inputs,
            missing_inputs=tuple(dict.fromkeys(missing_inputs)),
            invalid_reason=invalid_reason,
        )
        return SignalContext(
            symbol=bar.symbol,
            exchange=bar.exchange,
            timeframe=bar.timeframe,
            observed_at=bar.close_time,
            bar=bar,
            orderbook=orderbook,
            derived_inputs=derived_inputs,
            derya=derya,
            validity=validity,
            metadata={} if metadata is None else metadata.copy(),
        )

    def _ingest_signal_context(
        self,
        context: SignalContext,
        *,
        reference_time: datetime | None = None,
    ) -> SignalRuntimeUpdate:
        """Принять typed signal context, обновить signal state и вернуть runtime update."""
        effective_time = reference_time or context.observed_at
        key = self._build_state_key(
            exchange=context.exchange,
            symbol=context.symbol,
            timeframe=context.timeframe,
        )
        self._contexts[key] = context
        previous_signal = self._signals.get(key)
        signal = self._build_signal_from_context(
            context=context,
            previous_signal=previous_signal,
        )
        signal = self._expire_snapshot_if_needed(signal, reference_time=effective_time)
        self._signals[key] = signal

        payload = SignalSnapshotPayload.from_snapshot(signal)
        event_type = self._resolve_event_type(signal=signal, previous_signal=previous_signal)
        self._refresh_runtime_state(signal=signal, context=context, event_type=event_type)
        return SignalRuntimeUpdate(
            context=context,
            signal=signal,
            event_type=event_type,
            emitted_payload=payload,
        )

    def expire_signals(self, *, reference_time: datetime) -> tuple[SignalSnapshot, ...]:
        """Перевести истёкшие snapshots в `EXPIRED` по явному reference time."""
        self._ensure_started("expire_signals")
        expired: list[SignalSnapshot] = []
        for key, snapshot in tuple(self._signals.items()):
            updated = self._expire_snapshot_if_needed(snapshot, reference_time=reference_time)
            if updated is not snapshot:
                self._signals[key] = updated
                expired.append(updated)
                context = self._contexts.get(key)
                if context is not None:
                    self._refresh_runtime_state(
                        signal=updated,
                        context=context,
                        event_type=SignalEventType.SIGNAL_INVALIDATED,
                    )
        return tuple(expired)

    def get_signal(
        self,
        *,
        symbol: str,
        exchange: str,
        timeframe: MarketDataTimeframe,
        reference_time: datetime | None = None,
    ) -> SignalSnapshot | None:
        """Вернуть текущий signal snapshot по ключу с optional expiry refresh."""
        key = self._build_state_key(exchange=exchange, symbol=symbol, timeframe=timeframe)
        snapshot = self._signals.get(key)
        if snapshot is None:
            return None
        if reference_time is None:
            return snapshot
        updated = self._expire_snapshot_if_needed(snapshot, reference_time=reference_time)
        if updated is not snapshot:
            self._signals[key] = updated
            context = self._contexts.get(key)
            if context is not None:
                self._refresh_runtime_state(
                    signal=updated,
                    context=context,
                    event_type=SignalEventType.SIGNAL_INVALIDATED,
                )
            return updated
        return snapshot

    def get_signal_context(
        self,
        *,
        symbol: str,
        exchange: str,
        timeframe: MarketDataTimeframe,
    ) -> SignalContext | None:
        """Вернуть последний typed signal context по ключу."""
        return self._contexts.get(
            self._build_state_key(exchange=exchange, symbol=symbol, timeframe=timeframe)
        )

    def _build_signal_from_context(
        self,
        *,
        context: SignalContext,
        previous_signal: SignalSnapshot | None,
    ) -> SignalSnapshot:
        freshness = SignalFreshness(
            generated_at=context.observed_at,
            expires_at=context.observed_at + timedelta(seconds=self.config.max_signal_age_seconds),
        )
        if context.validity.status == SignalValidityStatus.INVALID:
            if self._should_invalidate_previous_signal(previous_signal):
                assert previous_signal is not None
                return self._build_invalidated_signal(
                    context=context,
                    freshness=freshness,
                    previous_signal=previous_signal,
                )
            return SignalSnapshot.candidate(
                contour_name=self.config.contour_name,
                symbol=context.symbol,
                exchange=context.exchange,
                timeframe=context.timeframe,
                freshness=freshness,
                validity=context.validity,
                reason_code=SignalReasonCode.SIGNAL_RULE_BLOCKED,
                metadata={"invalid_reason": context.validity.invalid_reason},
            )
        if context.validity.status == SignalValidityStatus.WARMING:
            if self._should_invalidate_previous_signal(previous_signal):
                assert previous_signal is not None
                return self._build_invalidated_signal(
                    context=context,
                    freshness=freshness,
                    previous_signal=previous_signal,
                )
            return SignalSnapshot.candidate(
                contour_name=self.config.contour_name,
                symbol=context.symbol,
                exchange=context.exchange,
                timeframe=context.timeframe,
                freshness=freshness,
                validity=context.validity,
                reason_code=SignalReasonCode.CONTEXT_INCOMPLETE,
                metadata={"missing_inputs": context.validity.missing_inputs},
            )

        contour_signal = self._evaluate_minimal_contour(
            context=context,
            freshness=freshness,
            previous_signal=previous_signal,
        )
        if contour_signal is not None:
            return contour_signal

        return SignalSnapshot(
            signal_id=self._resolve_signal_id(previous_signal),
            contour_name=self.config.contour_name,
            symbol=context.symbol,
            exchange=context.exchange,
            timeframe=context.timeframe,
            freshness=freshness,
            validity=context.validity,
            status=SignalStatus.SUPPRESSED,
            reason_code=SignalReasonCode.SIGNAL_RULE_BLOCKED,
            metadata={"suppression_reason": "contour_conditions_not_met"},
        )

    def _build_invalidated_signal(
        self,
        *,
        context: SignalContext,
        freshness: SignalFreshness,
        previous_signal: SignalSnapshot,
    ) -> SignalSnapshot:
        metadata = previous_signal.metadata.copy()
        if context.validity.invalid_reason is not None:
            metadata["invalid_reason"] = context.validity.invalid_reason
        if context.validity.missing_inputs:
            metadata["missing_inputs"] = context.validity.missing_inputs
        metadata["invalidation_reason"] = (
            context.validity.invalid_reason or "signal_input_truth_lost"
        )

        return SignalSnapshot(
            signal_id=previous_signal.signal_id,
            contour_name=self.config.contour_name,
            symbol=context.symbol,
            exchange=context.exchange,
            timeframe=context.timeframe,
            freshness=freshness,
            validity=context.validity,
            status=SignalStatus.INVALIDATED,
            direction=previous_signal.direction,
            confidence=previous_signal.confidence,
            entry_price=previous_signal.entry_price,
            stop_loss=previous_signal.stop_loss,
            take_profit=previous_signal.take_profit,
            reason_code=SignalReasonCode.SIGNAL_INVALIDATED,
            metadata=metadata,
        )

    def _evaluate_minimal_contour(
        self,
        *,
        context: SignalContext,
        freshness: SignalFreshness,
        previous_signal: SignalSnapshot | None,
    ) -> SignalSnapshot | None:
        assert context.derived_inputs is not None
        assert context.derya is not None

        adx_value = context.derived_inputs.adx.value
        atr_value = context.derived_inputs.atr.value
        derya_confidence = context.derya.confidence or Decimal("0")
        close = context.bar.close
        open_price = context.bar.open

        if adx_value is None or atr_value is None or atr_value <= 0:
            return None
        if adx_value < self.config.min_adx_for_activation:
            return None
        if derya_confidence < self.config.min_derya_confidence:
            return None

        direction: SignalDirection | None = None
        if context.derya.current_regime == DeryaRegime.EXPANSION and close > open_price:
            direction = SignalDirection.BUY
        elif context.derya.current_regime == DeryaRegime.COLLAPSE and close < open_price:
            direction = SignalDirection.SELL

        if direction is None:
            return None
        regime = context.derya.current_regime
        assert regime is not None

        entry_price = close
        if direction == SignalDirection.BUY:
            stop_loss = entry_price - atr_value
            take_profit = entry_price + (atr_value * self.config.risk_reward_multiple)
        else:
            stop_loss = entry_price + atr_value
            take_profit = entry_price - (atr_value * self.config.risk_reward_multiple)

        confidence = min(
            derya_confidence + (adx_value / Decimal("100")),
            Decimal("1"),
        ).quantize(Decimal("0.0001"))
        spread_bps = None
        if context.orderbook is not None:
            spread_bps = str(context.orderbook.spread_bps)

        return SignalSnapshot(
            signal_id=self._resolve_signal_id(previous_signal),
            contour_name=self.config.contour_name,
            symbol=context.symbol,
            exchange=context.exchange,
            timeframe=context.timeframe,
            freshness=freshness,
            validity=context.validity,
            status=SignalStatus.ACTIVE,
            direction=direction,
            confidence=confidence,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            reason_code=SignalReasonCode.CONTEXT_READY,
            metadata={
                "derya_regime": regime.value,
                "derya_confidence": str(derya_confidence),
                "adx": str(adx_value),
                "atr": str(atr_value),
                "spread_bps": spread_bps,
            },
        )

    def _expire_snapshot_if_needed(
        self,
        snapshot: SignalSnapshot,
        *,
        reference_time: datetime,
    ) -> SignalSnapshot:
        if snapshot.status == SignalStatus.EXPIRED:
            return snapshot
        if not snapshot.freshness.is_expired_at(reference_time):
            return snapshot
        expired_validity = snapshot.validity
        if expired_validity.is_valid:
            expired_validity = replace(
                expired_validity,
                status=SignalValidityStatus.INVALID,
                invalid_reason="signal_expired",
            )
        return replace(
            snapshot,
            status=SignalStatus.EXPIRED,
            validity=expired_validity,
            reason_code=SignalReasonCode.SIGNAL_EXPIRED,
        )

    def _resolve_event_type(
        self,
        *,
        signal: SignalSnapshot,
        previous_signal: SignalSnapshot | None,
    ) -> SignalEventType:
        if signal.status in {SignalStatus.INVALIDATED, SignalStatus.EXPIRED}:
            return SignalEventType.SIGNAL_INVALIDATED
        if signal.status == SignalStatus.ACTIVE:
            return SignalEventType.SIGNAL_EMITTED
        return SignalEventType.SIGNAL_SNAPSHOT_UPDATED

    def _refresh_runtime_state(
        self,
        *,
        signal: SignalSnapshot,
        context: SignalContext,
        event_type: SignalEventType,
    ) -> None:
        tracked_signal_keys = len(self._signals)
        active_signal_keys = sum(
            1 for snapshot in self._signals.values() if snapshot.status == SignalStatus.ACTIVE
        )
        invalidated_signal_keys = sum(
            1 for snapshot in self._signals.values() if snapshot.status == SignalStatus.INVALIDATED
        )
        expired_signal_keys = sum(
            1 for snapshot in self._signals.values() if snapshot.status == SignalStatus.EXPIRED
        )

        ready = True
        lifecycle_state = SignalRuntimeLifecycleState.READY
        readiness_reasons: list[str] = []
        degraded_reasons: list[str] = []

        if tracked_signal_keys == 0:
            ready = False
            lifecycle_state = SignalRuntimeLifecycleState.WARMING
            readiness_reasons.append("no_signal_context_processed")
        elif context.validity.status == SignalValidityStatus.WARMING:
            ready = False
            lifecycle_state = SignalRuntimeLifecycleState.WARMING
            readiness_reasons.append("signal_context_warming")
        elif context.validity.status == SignalValidityStatus.INVALID:
            ready = False
            lifecycle_state = SignalRuntimeLifecycleState.DEGRADED
            readiness_reasons.append("signal_context_invalid")
            if context.validity.invalid_reason is not None:
                degraded_reasons.append(context.validity.invalid_reason)

        self._refresh_diagnostics(
            ready=ready,
            lifecycle_state=lifecycle_state,
            tracked_signal_keys=tracked_signal_keys,
            active_signal_keys=active_signal_keys,
            invalidated_signal_keys=invalidated_signal_keys,
            expired_signal_keys=expired_signal_keys,
            last_context_at=context.observed_at.astimezone(UTC).isoformat(),
            last_signal_id=str(signal.signal_id),
            last_event_type=event_type.value,
            last_failure_reason=None,
            readiness_reasons=tuple(readiness_reasons),
            degraded_reasons=tuple(degraded_reasons),
        )

    def _build_context_validity(
        self,
        *,
        observed_inputs: int,
        missing_inputs: tuple[str, ...],
        invalid_reason: str | None,
    ) -> SignalValidity:
        required_inputs = len(self.config.required_context_sources)
        if invalid_reason is not None:
            return SignalValidity(
                status=SignalValidityStatus.INVALID,
                observed_inputs=observed_inputs,
                required_inputs=required_inputs,
                missing_inputs=missing_inputs,
                invalid_reason=invalid_reason,
            )
        if missing_inputs:
            return SignalValidity(
                status=SignalValidityStatus.WARMING,
                observed_inputs=observed_inputs,
                required_inputs=required_inputs,
                missing_inputs=missing_inputs,
            )
        return SignalValidity(
            status=SignalValidityStatus.VALID,
            observed_inputs=observed_inputs,
            required_inputs=required_inputs,
        )

    def _build_state_key(
        self,
        *,
        exchange: str,
        symbol: str,
        timeframe: MarketDataTimeframe,
    ) -> SignalStateKey:
        return (exchange, symbol, timeframe, self.config.contour_name)

    @staticmethod
    def _should_invalidate_previous_signal(previous_signal: SignalSnapshot | None) -> bool:
        return (
            previous_signal is not None
            and previous_signal.validity.is_valid
            and previous_signal.status not in {SignalStatus.EXPIRED, SignalStatus.INVALIDATED}
        )

    @staticmethod
    def _resolve_signal_id(previous_signal: SignalSnapshot | None) -> UUID:
        if previous_signal is not None:
            return previous_signal.signal_id
        return uuid4()

    @staticmethod
    def _matches_market_identity(
        *,
        symbol: str,
        exchange: str,
        orderbook: OrderBookSnapshotContract,
    ) -> bool:
        return orderbook.symbol == symbol and orderbook.exchange == exchange

    @staticmethod
    def _matches_analysis_identity(
        *,
        bar: OHLCVBarContract,
        derived_inputs: RiskDerivedInputsSnapshot,
    ) -> bool:
        return (
            derived_inputs.symbol == bar.symbol
            and derived_inputs.exchange == bar.exchange
            and derived_inputs.timeframe == bar.timeframe
        )

    @staticmethod
    def _matches_intelligence_identity(
        *,
        bar: OHLCVBarContract,
        derya: DeryaAssessment,
    ) -> bool:
        return (
            derya.symbol == bar.symbol
            and derya.exchange == bar.exchange
            and derya.timeframe == bar.timeframe
        )

    def _ensure_started(self, operation: str) -> None:
        if not self._started:
            raise RuntimeError(
                f"SignalRuntime не запущен. Операция {operation} недоступна до start()."
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

    def _refresh_diagnostics(self, **updates: Any) -> None:
        current = asdict(self._diagnostics)
        current.update(updates)
        self._diagnostics = SignalRuntimeDiagnostics(
            started=self._started,
            ready=bool(current["ready"]),
            lifecycle_state=SignalRuntimeLifecycleState(current["lifecycle_state"]),
            tracked_signal_keys=int(current["tracked_signal_keys"]),
            active_signal_keys=int(current["active_signal_keys"]),
            invalidated_signal_keys=int(current["invalidated_signal_keys"]),
            expired_signal_keys=int(current["expired_signal_keys"]),
            last_context_at=current["last_context_at"],
            last_signal_id=current["last_signal_id"],
            last_event_type=current["last_event_type"],
            last_failure_reason=current["last_failure_reason"],
            readiness_reasons=list(current.get("readiness_reasons", [])),
            degraded_reasons=list(current.get("degraded_reasons", [])),
        )
        self._push_diagnostics()

    def _push_diagnostics(self) -> None:
        if self._diagnostics_sink is not None:
            self._diagnostics_sink(self.get_runtime_diagnostics())


def create_signal_runtime(
    *,
    config: SignalRuntimeConfig | None = None,
    diagnostics_sink: Callable[[dict[str, object]], None] | None = None,
) -> SignalRuntime:
    """Собрать explicit signal runtime foundation."""
    return SignalRuntime(
        config=config or SignalRuntimeConfig.from_settings(get_settings()),
        diagnostics_sink=diagnostics_sink,
    )


__all__ = [
    "SignalRuntime",
    "SignalRuntimeConfig",
    "SignalRuntimeDiagnostics",
    "SignalRuntimeLifecycleState",
    "SignalRuntimeUpdate",
    "create_signal_runtime",
]

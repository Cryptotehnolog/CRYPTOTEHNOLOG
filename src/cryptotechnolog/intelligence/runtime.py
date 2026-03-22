"""
Узкий runtime boundary для Phase 7 Intelligence Foundation.

Этот модуль не реализует широкий orchestration layer.
Он фиксирует форму следующего шага:
- explicit runtime entrypoint intelligence-layer;
- ingest path от `BAR_COMPLETED`;
- обновление `DeryaEngine`;
- query surface и diagnostics без hidden bootstrap.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from cryptotechnolog.market_data import MarketDataTimeframe, OHLCVBarContract

from .derya_engine import DeryaEngine, DeryaEngineConfig, DeryaRegimeTransition
from .events import IntelligenceEventType

if TYPE_CHECKING:
    from collections.abc import Callable

    from cryptotechnolog.market_data.events import BarCompletedPayload

    from .models import DeryaAssessment


@dataclass(slots=True, frozen=True)
class IntelligenceRuntimeConfig:
    """Конфигурация узкого runtime boundary Phase 7."""

    derya: DeryaEngineConfig = field(default_factory=DeryaEngineConfig)


@dataclass(slots=True)
class IntelligenceRuntimeDiagnostics:
    """Operator-facing diagnostics для следующего intelligence runtime step."""

    started: bool = False
    ready: bool = False
    lifecycle_state: str = "built"
    last_bar_at: str | None = None
    tracked_derya_keys: int = 0
    last_derya_regime_event_type: str | None = None
    last_failure_reason: str | None = None
    readiness_reasons: tuple[str, ...] = ()
    degraded_reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        """Преобразовать diagnostics в словарь для runtime truth."""
        return {
            "started": self.started,
            "ready": self.ready,
            "lifecycle_state": self.lifecycle_state,
            "last_bar_at": self.last_bar_at,
            "tracked_derya_keys": self.tracked_derya_keys,
            "last_derya_regime_event_type": self.last_derya_regime_event_type,
            "last_failure_reason": self.last_failure_reason,
            "readiness_reasons": list(self.readiness_reasons),
            "degraded_reasons": list(self.degraded_reasons),
        }


@dataclass(slots=True, frozen=True)
class IntelligenceRuntimeUpdate:
    """Результат одного intelligence update cycle."""

    assessment: DeryaAssessment
    regime_changed_event: Any | None = None


class IntelligenceRuntime:
    """
    Узкий explicit runtime entrypoint для intelligence-layer.

    На текущем шаге runtime:
    - не подписывается сам на Event Bus;
    - не знает о composition root;
    - не запускает background tasks;
    - принимает completed bars через явный API.
    """

    def __init__(
        self,
        config: IntelligenceRuntimeConfig | None = None,
        *,
        diagnostics_sink: Callable[[dict[str, object]], None] | None = None,
    ) -> None:
        self.config = config or IntelligenceRuntimeConfig()
        self.derya_engine = DeryaEngine(self.config.derya)
        self._diagnostics_sink = diagnostics_sink
        self._diagnostics = IntelligenceRuntimeDiagnostics()
        self._started = False
        self._push_diagnostics()

    @property
    def is_started(self) -> bool:
        """Проверить, активирован ли runtime boundary."""
        return self._started

    def get_runtime_diagnostics(self) -> dict[str, object]:
        """Вернуть diagnostics для operator/runtime truth."""
        return self._diagnostics.to_dict()

    async def start(self) -> None:
        """Активировать runtime boundary без hidden bootstrap."""
        if self._started:
            return
        self._started = True
        self._refresh_diagnostics(
            lifecycle_state="warming",
            ready=False,
            readiness_reasons=("no_completed_bars_processed",),
            degraded_reasons=(),
        )

    async def stop(self) -> None:
        """Остановить runtime boundary без скрытого фонового состояния."""
        if not self._started:
            return
        self._started = False
        self._refresh_diagnostics(
            lifecycle_state="stopped",
            ready=False,
            last_bar_at=None,
            last_derya_regime_event_type=None,
            last_failure_reason=None,
            readiness_reasons=("runtime_stopped",),
            degraded_reasons=(),
        )

    def mark_degraded(self, reason: str) -> None:
        """Зафиксировать деградацию ingest/runtime path без hidden fallback."""
        self._refresh_diagnostics(
            ready=False,
            lifecycle_state="degraded",
            last_failure_reason=reason,
            degraded_reasons=(reason,),
        )

    def ingest_completed_bar(self, bar: OHLCVBarContract) -> IntelligenceRuntimeUpdate:
        """Обновить intelligence state typed completed bar-ом."""
        self._ensure_started("ingest_completed_bar")
        assessment = self.derya_engine.update_bar(bar)
        regime_event = self.derya_engine.build_regime_changed_event(assessment)
        self._refresh_from_assessment(assessment, regime_event_present=regime_event is not None)
        return IntelligenceRuntimeUpdate(
            assessment=assessment,
            regime_changed_event=regime_event,
        )

    def ingest_bar_completed_payload(
        self,
        payload: BarCompletedPayload,
    ) -> IntelligenceRuntimeUpdate:
        """
        Принять typed `BAR_COMPLETED` payload и преобразовать его в bar contract.

        Этот метод фиксирует ingest boundary следующего шага runtime integration:
        upstream market-data runtime поставляет `BAR_COMPLETED`, а intelligence runtime
        работает на typed contract и не зависит от произвольных dict.
        """
        return self.ingest_completed_bar(self._bar_from_payload(payload))

    def get_derya_assessment(
        self,
        *,
        exchange: str,
        symbol: str,
        timeframe: MarketDataTimeframe,
    ) -> DeryaAssessment | None:
        """Экспонировать текущий DERYA assessment наружу."""
        return self.derya_engine.get_current_assessment(
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
        )

    def get_derya_regime_history(
        self,
        *,
        exchange: str,
        symbol: str,
        timeframe: MarketDataTimeframe,
    ) -> tuple[DeryaRegimeTransition, ...]:
        """Экспонировать regime history DERYA наружу."""
        return self.derya_engine.get_recent_regime_history(
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
        )

    def get_derya_efficiency_series(
        self,
        *,
        exchange: str,
        symbol: str,
        timeframe: MarketDataTimeframe,
    ) -> tuple[Decimal, ...]:
        """Экспонировать raw efficiency series наружу."""
        return self.derya_engine.get_recent_efficiency_series(
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
        )

    def get_derya_smoothed_series(
        self,
        *,
        exchange: str,
        symbol: str,
        timeframe: MarketDataTimeframe,
    ) -> tuple[Decimal, ...]:
        """Экспонировать smoothed efficiency series наружу."""
        return self.derya_engine.get_recent_smoothed_series(
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
        )

    def _refresh_from_assessment(
        self,
        assessment: DeryaAssessment,
        *,
        regime_event_present: bool,
    ) -> None:
        readiness_reasons: list[str] = []
        degraded_reasons: list[str] = []
        lifecycle_state = "ready"
        ready = True

        if assessment.validity.is_warming:
            lifecycle_state = "warming"
            ready = False
            readiness_reasons.append("derya_history_warming")

        if assessment.current_regime is None and assessment.validity.is_valid:
            lifecycle_state = "degraded"
            ready = False
            readiness_reasons.append("derya_regime_not_acquired")

        self._refresh_diagnostics(
            ready=ready,
            lifecycle_state=lifecycle_state,
            last_bar_at=assessment.updated_at.astimezone(UTC).isoformat(),
            tracked_derya_keys=self._tracked_derya_keys_count(),
            last_derya_regime_event_type=(
                IntelligenceEventType.DERYA_REGIME_CHANGED.value
                if regime_event_present
                else self._diagnostics.last_derya_regime_event_type
            ),
            last_failure_reason=None,
            readiness_reasons=tuple(dict.fromkeys(readiness_reasons)),
            degraded_reasons=tuple(dict.fromkeys(degraded_reasons)),
        )

    def _tracked_derya_keys_count(self) -> int:
        return self.derya_engine.tracked_keys_count()

    def _bar_from_payload(self, payload: BarCompletedPayload) -> OHLCVBarContract:
        timeframe = MarketDataTimeframe(payload.timeframe)
        return OHLCVBarContract(
            symbol=payload.symbol,
            exchange=payload.exchange,
            timeframe=timeframe,
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

    def _ensure_started(self, operation: str) -> None:
        if not self._started:
            raise RuntimeError(
                f"IntelligenceRuntime не запущен. Операция {operation} недоступна до start()."
            )

    def _refresh_diagnostics(self, **updates: object) -> None:
        current: dict[str, Any] = asdict(self._diagnostics)
        current.update(updates)
        self._diagnostics = IntelligenceRuntimeDiagnostics(
            started=self._started,
            ready=bool(current["ready"]),
            lifecycle_state=str(current["lifecycle_state"]),
            last_bar_at=str(current["last_bar_at"]) if current["last_bar_at"] is not None else None,
            tracked_derya_keys=int(current["tracked_derya_keys"]),
            last_derya_regime_event_type=(
                str(current["last_derya_regime_event_type"])
                if current["last_derya_regime_event_type"] is not None
                else None
            ),
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


def create_intelligence_runtime(
    *,
    config: IntelligenceRuntimeConfig | None = None,
    diagnostics_sink: Callable[[dict[str, object]], None] | None = None,
) -> IntelligenceRuntime:
    """Собрать explicit runtime boundary для intelligence-layer."""
    return IntelligenceRuntime(
        config=config,
        diagnostics_sink=diagnostics_sink,
    )


__all__ = [
    "IntelligenceRuntime",
    "IntelligenceRuntimeConfig",
    "IntelligenceRuntimeDiagnostics",
    "IntelligenceRuntimeUpdate",
    "create_intelligence_runtime",
]

"""
Runtime integration слой для Market Data Layer Фазы 6.

Этот модуль собирает foundation-компоненты Phase 6 в один явный runtime path:
- без скрытого bootstrap;
- без второго event style;
- без прямых system-state transitions.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from cryptotechnolog.config import get_logger, get_settings
from cryptotechnolog.core.event import SystemEventSource

from .bar_builder import BarBuilder, BarUpdateResult
from .data_quality import DataQualityConfig, DataQualityValidator, MarketDataValidationError
from .events import (
    BarCompletedPayload,
    DataQualitySignalPayload,
    MarketDataEventType,
    OrderBookUpdatedPayload,
    SupportsEventPayload,
    SymbolMetricsUpdatedPayload,
    SymbolUniverseChangePayload,
    TickReceivedPayload,
    UniverseQualityPayload,
    UniverseSnapshotPayload,
    build_market_data_event,
)
from .models import (
    AdmissibleUniverseSnapshot,
    DataQualityIssueType,
    DataQualitySignal,
    MarketDataTimeframe,
    OrderBookLevel,
    OrderBookSnapshotContract,
    RawUniverseSnapshot,
    SymbolIdentity,
    SymbolMetricsContract,
    TickContract,
    UniverseConfidenceState,
    UniverseExclusionReason,
    UniverseQualityAssessment,
    build_symbol_identity,
)
from .orderbook_manager import OrderBookManager, OrderBookUpdateResult
from .symbol_metrics import SymbolMetricsCollector, SymbolMetricsConfig, SymbolMetricsInput
from .tick_handler import TickHandler, TickProcessingResult
from .universe_policy import UniversePolicy, UniversePolicyConfig, UniversePolicyResult

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from decimal import Decimal
    from uuid import UUID

    from cryptotechnolog.core.enhanced_event_bus import EnhancedEventBus
    from cryptotechnolog.core.system_controller import SystemController


logger = get_logger(__name__)


@dataclass(slots=True, frozen=True)
class MarketDataRuntimeConfig:
    """Конфигурация runtime integration слоя Phase 6."""

    bar_timeframes: tuple[MarketDataTimeframe, ...] = (MarketDataTimeframe.M1,)
    quality: DataQualityConfig = field(default_factory=DataQualityConfig)
    metrics: SymbolMetricsConfig = field(default_factory=SymbolMetricsConfig)
    universe_policy: UniversePolicyConfig = field(default_factory=UniversePolicyConfig)
    orderbook_max_levels: int = 20

    @classmethod
    def from_settings(cls) -> MarketDataRuntimeConfig:
        """Собрать market-data runtime config из project settings."""
        settings = get_settings()
        return cls(
            quality=DataQualityConfig(),
            metrics=SymbolMetricsConfig(),
            universe_policy=UniversePolicyConfig.from_settings(settings),
        )


@dataclass(slots=True)
class MarketDataRuntimeState:
    """In-memory состояние runtime integration слоя."""

    raw_snapshot: RawUniverseSnapshot | None = None
    admissible_snapshot: AdmissibleUniverseSnapshot | None = None
    quality_assessment: UniverseQualityAssessment | None = None
    metrics_by_identity: dict[SymbolIdentity, SymbolMetricsContract] = field(default_factory=dict)
    quality_signals_by_identity: dict[SymbolIdentity, tuple[DataQualitySignal, ...]] = field(
        default_factory=dict
    )
    last_trade_at: dict[tuple[str, str], datetime] = field(default_factory=dict)


@dataclass(slots=True)
class MarketDataRuntimeDiagnostics:
    """Operator-facing diagnostics для lifecycle/readiness semantics Phase 6."""

    started: bool = False
    ready: bool = False
    lifecycle_state: str = "built"
    raw_snapshot_version: int | None = None
    admissible_snapshot_version: int | None = None
    quality_assessment_version: int | None = None
    raw_symbols_count: int = 0
    admissible_symbols_count: int = 0
    metrics_count: int = 0
    quality_signal_identities_count: int = 0
    universe_confidence_state: str | None = None
    universe_confidence: str | None = None
    last_tick_at: str | None = None
    last_universe_update_at: str | None = None
    readiness_reasons: tuple[str, ...] = ()
    degraded_reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        """Преобразовать diagnostics в словарь для health/runtime truth."""
        return {
            "started": self.started,
            "ready": self.ready,
            "lifecycle_state": self.lifecycle_state,
            "raw_snapshot_version": self.raw_snapshot_version,
            "admissible_snapshot_version": self.admissible_snapshot_version,
            "quality_assessment_version": self.quality_assessment_version,
            "raw_symbols_count": self.raw_symbols_count,
            "admissible_symbols_count": self.admissible_symbols_count,
            "metrics_count": self.metrics_count,
            "quality_signal_identities_count": self.quality_signal_identities_count,
            "universe_confidence_state": self.universe_confidence_state,
            "universe_confidence": self.universe_confidence,
            "last_tick_at": self.last_tick_at,
            "last_universe_update_at": self.last_universe_update_at,
            "readiness_reasons": list(self.readiness_reasons),
            "degraded_reasons": list(self.degraded_reasons),
        }


@dataclass(slots=True, frozen=True)
class TickRuntimeUpdate:
    """Результат ingest path для tick."""

    tick_result: TickProcessingResult
    bar_updates: dict[MarketDataTimeframe, BarUpdateResult]


@dataclass(slots=True, frozen=True)
class UniverseRuntimeUpdate:
    """Результат refresh path для raw/admissible universe."""

    policy_result: UniversePolicyResult
    admitted_symbols: tuple[SymbolIdentity, ...]
    removed_symbols: tuple[SymbolIdentity, ...]


class MarketDataRuntime:
    """Явный runtime path для foundation-компонентов Phase 6."""

    def __init__(
        self,
        *,
        event_bus: EnhancedEventBus,
        config: MarketDataRuntimeConfig | None = None,
        controller: SystemController | None = None,
        diagnostics_sink: Callable[[dict[str, object]], None] | None = None,
    ) -> None:
        self.event_bus = event_bus
        self.config = config or MarketDataRuntimeConfig.from_settings()
        self.controller = controller
        self._diagnostics_sink = diagnostics_sink

        quality_validator = DataQualityValidator(self.config.quality)
        self.tick_handler = TickHandler(quality_validator=quality_validator)
        self.orderbook_manager = OrderBookManager(
            max_levels=self.config.orderbook_max_levels,
            quality_validator=quality_validator,
        )
        self.bar_builders = {
            timeframe: BarBuilder(timeframe) for timeframe in self.config.bar_timeframes
        }
        self.symbol_metrics_collector = SymbolMetricsCollector(self.config.metrics)
        self.universe_policy = UniversePolicy(self.config.universe_policy)
        self.state = MarketDataRuntimeState()
        self._diagnostics = MarketDataRuntimeDiagnostics()
        self._started = False
        self._push_diagnostics()

    @property
    def is_started(self) -> bool:
        """Проверить, активирован ли runtime path."""
        return self._started

    def get_runtime_diagnostics(self) -> dict[str, object]:
        """Вернуть operator-facing diagnostics для Market Data runtime."""
        return self._diagnostics.to_dict()

    async def start(self) -> None:
        """Активировать runtime path без скрытого background-loop."""
        if self._started:
            return
        self._started = True
        self._refresh_diagnostics(
            lifecycle_state="starting",
            readiness_reasons=("no_raw_universe_snapshot", "no_universe_quality_assessment"),
        )
        self._refresh_diagnostics(
            lifecycle_state="not_ready",
            readiness_reasons=("no_raw_universe_snapshot", "no_universe_quality_assessment"),
        )
        logger.info(
            "Market Data runtime активирован",
            bar_timeframes=[timeframe.value for timeframe in self.bar_builders],
            orderbook_max_levels=self.config.orderbook_max_levels,
        )

    async def stop(self) -> None:
        """Остановить runtime path и зафиксировать shutdown state."""
        if not self._started:
            return
        self._started = False
        self.state = MarketDataRuntimeState()
        self._refresh_diagnostics(
            lifecycle_state="stopped",
            ready=False,
            raw_snapshot_version=None,
            admissible_snapshot_version=None,
            quality_assessment_version=None,
            raw_symbols_count=0,
            admissible_symbols_count=0,
            metrics_count=0,
            quality_signal_identities_count=0,
            universe_confidence_state=None,
            universe_confidence=None,
            last_tick_at=None,
            last_universe_update_at=None,
            readiness_reasons=("runtime_stopped",),
            degraded_reasons=(),
        )
        logger.info("Market Data runtime остановлен")

    async def ingest_tick(
        self,
        tick: TickContract,
        *,
        correlation_id: UUID | None = None,
    ) -> TickRuntimeUpdate:
        """Обработать typed tick и опубликовать runtime signals."""
        self._ensure_started("ingest_tick")
        tick_result = self.tick_handler.process_tick(tick)
        self.state.last_trade_at[(tick.symbol, tick.exchange)] = tick.timestamp.astimezone(UTC)
        self._refresh_diagnostics(last_tick_at=tick.timestamp.astimezone(UTC).isoformat())

        await self._publish_event(
            event_type=MarketDataEventType.TICK_RECEIVED,
            payload=TickReceivedPayload.from_contract(tick_result.tick),
            source=SystemEventSource.MARKET_DATA_MANAGER,
            correlation_id=correlation_id,
        )
        await self._publish_quality_signals(
            tick_result.quality_signals,
            correlation_id=correlation_id,
        )

        bar_updates: dict[MarketDataTimeframe, BarUpdateResult] = {}
        for timeframe, builder in self.bar_builders.items():
            update = builder.ingest_tick(tick_result.tick)
            bar_updates[timeframe] = update
            if update.completed_bar is not None:
                await self._publish_event(
                    event_type=MarketDataEventType.BAR_COMPLETED,
                    payload=BarCompletedPayload.from_contract(update.completed_bar),
                    source=SystemEventSource.MARKET_DATA_MANAGER,
                    correlation_id=correlation_id,
                )

        return TickRuntimeUpdate(tick_result=tick_result, bar_updates=bar_updates)

    async def ingest_orderbook_snapshot(
        self,
        snapshot: OrderBookSnapshotContract,
        *,
        correlation_id: UUID | None = None,
    ) -> OrderBookUpdateResult:
        """Установить typed snapshot стакана и опубликовать runtime signals."""
        self._ensure_started("ingest_orderbook_snapshot")
        result = self.orderbook_manager.apply_snapshot(
            symbol=snapshot.symbol,
            exchange=snapshot.exchange,
            timestamp=snapshot.timestamp,
            bids=snapshot.bids,
            asks=snapshot.asks,
            checksum=snapshot.checksum,
        )
        await self._publish_event(
            event_type=MarketDataEventType.ORDERBOOK_UPDATED,
            payload=OrderBookUpdatedPayload.from_contract(result.snapshot),
            source=SystemEventSource.MARKET_DATA_MANAGER,
            correlation_id=correlation_id,
        )
        await self._publish_quality_signals(
            result.quality_signals,
            correlation_id=correlation_id,
        )
        return result

    async def apply_orderbook_delta(
        self,
        *,
        symbol: str,
        exchange: str,
        timestamp: datetime,
        bid_updates: tuple[OrderBookLevel, ...] = (),
        ask_updates: tuple[OrderBookLevel, ...] = (),
        checksum: str | None = None,
        correlation_id: UUID | None = None,
    ) -> OrderBookUpdateResult:
        """Применить delta к существующему orderbook и опубликовать runtime signals."""
        self._ensure_started("apply_orderbook_delta")
        result = self.orderbook_manager.apply_delta(
            symbol=symbol,
            exchange=exchange,
            timestamp=timestamp,
            bid_updates=bid_updates,
            ask_updates=ask_updates,
            checksum=checksum,
        )
        await self._publish_event(
            event_type=MarketDataEventType.ORDERBOOK_UPDATED,
            payload=OrderBookUpdatedPayload.from_contract(result.snapshot),
            source=SystemEventSource.MARKET_DATA_MANAGER,
            correlation_id=correlation_id,
        )
        await self._publish_quality_signals(
            result.quality_signals,
            correlation_id=correlation_id,
        )
        return result

    async def check_staleness(
        self,
        *,
        symbol: str,
        exchange: str,
        feed: str,
        now: datetime | None = None,
        correlation_id: UUID | None = None,
    ) -> DataQualitySignal | None:
        """Проверить staleness выбранного feed и опубликовать сигнал при необходимости."""
        self._ensure_started("check_staleness")
        signal = self.tick_handler.quality_validator.detect_stale(
            symbol=symbol,
            exchange=exchange,
            feed=feed,
            now=now,
        )
        if signal is not None:
            await self._publish_quality_signals((signal,), correlation_id=correlation_id)
        return signal

    async def mark_source_degraded(
        self,
        *,
        symbol: str,
        exchange: str,
        feed: str,
        reason: str,
        detected_at: datetime | None = None,
        correlation_id: UUID | None = None,
    ) -> DataQualitySignal:
        """Зафиксировать деградацию feed/source как typed runtime signal."""
        self._ensure_started("mark_source_degraded")
        signal = self.tick_handler.quality_validator.build_source_degraded_signal(
            symbol=symbol,
            exchange=exchange,
            feed=feed,
            reason=reason,
            detected_at=detected_at,
        )
        await self._publish_quality_signals((signal,), correlation_id=correlation_id)
        return signal

    async def collect_symbol_metrics(
        self,
        *,
        symbol: str,
        exchange: str,
        calculated_at: datetime,
        tick_coverage_ratio: Decimal,
        average_latency_ms: Decimal,
        volume_24h_usd: Decimal | None = None,
        open_interest_usd: Decimal | None = None,
        funding_8h: Decimal | None = None,
        correlation_id: UUID | None = None,
    ) -> SymbolMetricsContract:
        """Собрать typed symbol metrics из runtime foundation state."""
        self._ensure_started("collect_symbol_metrics")
        orderbook = self.orderbook_manager.get_snapshot(symbol, exchange)
        if orderbook is None:
            raise MarketDataValidationError(
                "Нельзя собрать SymbolMetricsContract без orderbook snapshot"
            )

        last_trade_at = self.state.last_trade_at.get((symbol, exchange))
        if last_trade_at is None:
            raise MarketDataValidationError(
                "Нельзя собрать SymbolMetricsContract без последнего trade timestamp"
            )

        metrics = self.symbol_metrics_collector.collect(
            SymbolMetricsInput(
                symbol=symbol,
                exchange=exchange,
                calculated_at=calculated_at,
                orderbook=orderbook,
                last_trade_at=last_trade_at,
                tick_coverage_ratio=tick_coverage_ratio,
                average_latency_ms=average_latency_ms,
                volume_24h_usd=volume_24h_usd,
                open_interest_usd=open_interest_usd,
                funding_8h=funding_8h,
            )
        )
        self.state.metrics_by_identity[build_symbol_identity(symbol, exchange)] = metrics
        self._refresh_diagnostics(metrics_count=len(self.state.metrics_by_identity))
        await self._publish_event(
            event_type=MarketDataEventType.SYMBOL_METRICS_UPDATED,
            payload=SymbolMetricsUpdatedPayload.from_contract(metrics),
            source=SystemEventSource.SYMBOL_METRICS_COLLECTOR,
            correlation_id=correlation_id,
        )
        return metrics

    async def refresh_universe(
        self,
        *,
        raw_snapshot: RawUniverseSnapshot,
        measured_at: datetime | None = None,
        correlation_id: UUID | None = None,
    ) -> UniverseRuntimeUpdate:
        """Обновить raw/admissible/quality state и опубликовать Phase 6 universe events."""
        self._ensure_started("refresh_universe")
        previous_snapshot = self.state.admissible_snapshot
        policy_result = self.universe_policy.build_admissible_universe(
            raw_snapshot=raw_snapshot,
            metrics_by_identity=self.state.metrics_by_identity,
            quality_signals_by_identity=self.state.quality_signals_by_identity,
            measured_at=measured_at,
        )

        self.state.raw_snapshot = raw_snapshot
        self.state.admissible_snapshot = policy_result.snapshot
        self.state.quality_assessment = policy_result.assessment
        self._refresh_readiness_from_state()

        await self._publish_event(
            event_type=MarketDataEventType.UNIVERSE_RAW_UPDATED,
            payload=UniverseSnapshotPayload.from_raw_snapshot(raw_snapshot),
            source=SystemEventSource.UNIVERSE_ENGINE,
            correlation_id=correlation_id,
        )
        await self._publish_event(
            event_type=MarketDataEventType.UNIVERSE_ADMISSIBLE_UPDATED,
            payload=UniverseSnapshotPayload.from_admissible_snapshot(policy_result.snapshot),
            source=SystemEventSource.UNIVERSE_ENGINE,
            correlation_id=correlation_id,
        )
        await self._publish_event(
            event_type=MarketDataEventType.UNIVERSE_CONFIDENCE_UPDATED,
            payload=UniverseQualityPayload.from_assessment(policy_result.assessment),
            source=SystemEventSource.UNIVERSE_ENGINE,
            correlation_id=correlation_id,
        )

        admitted_symbols, removed_symbols = await self._publish_universe_deltas(
            previous_snapshot=previous_snapshot,
            current_snapshot=policy_result.snapshot,
            exclusion_reasons=policy_result.exclusion_reasons,
            changed_at=policy_result.snapshot.created_at,
            correlation_id=correlation_id,
        )

        if policy_result.assessment.requires_degraded_mode():
            await self._publish_event(
                event_type=MarketDataEventType.UNIVERSE_CONFIDENCE_LOW,
                payload=UniverseQualityPayload.from_assessment(policy_result.assessment),
                source=SystemEventSource.UNIVERSE_ENGINE,
                correlation_id=correlation_id,
            )

        if policy_result.assessment.admissible_count == 0:
            await self._publish_event(
                event_type=MarketDataEventType.UNIVERSE_EMPTY,
                payload=UniverseQualityPayload.from_assessment(policy_result.assessment),
                source=SystemEventSource.UNIVERSE_ENGINE,
                correlation_id=correlation_id,
            )
        elif policy_result.assessment.state == UniverseConfidenceState.READY:
            await self._publish_event(
                event_type=MarketDataEventType.UNIVERSE_READY,
                payload=UniverseQualityPayload.from_assessment(policy_result.assessment),
                source=SystemEventSource.UNIVERSE_ENGINE,
                correlation_id=correlation_id,
            )

        return UniverseRuntimeUpdate(
            policy_result=policy_result,
            admitted_symbols=admitted_symbols,
            removed_symbols=removed_symbols,
        )

    async def _publish_universe_deltas(
        self,
        *,
        previous_snapshot: AdmissibleUniverseSnapshot | None,
        current_snapshot: AdmissibleUniverseSnapshot,
        exclusion_reasons: Mapping[SymbolIdentity, tuple[UniverseExclusionReason, ...]],
        changed_at: datetime,
        correlation_id: UUID | None,
    ) -> tuple[tuple[SymbolIdentity, ...], tuple[SymbolIdentity, ...]]:
        previous_map = (
            {item.symbol.identity: item for item in previous_snapshot.symbols}
            if previous_snapshot is not None
            else {}
        )
        current_map = {item.symbol.identity: item for item in current_snapshot.symbols}

        admitted_symbols = tuple(
            identity for identity in current_map if identity not in previous_map
        )
        removed_symbols = tuple(
            identity for identity in previous_map if identity not in current_map
        )

        for identity in admitted_symbols:
            admitted = current_map[identity]
            await self._publish_event(
                event_type=MarketDataEventType.SYMBOL_ADMITTED_TO_UNIVERSE,
                payload=SymbolUniverseChangePayload(
                    symbol=admitted.symbol.symbol,
                    exchange=admitted.symbol.exchange,
                    version=current_snapshot.version,
                    changed_at=changed_at.isoformat(),
                    reasons=tuple(reason.value for reason in admitted.admission_reasons),
                ),
                source=SystemEventSource.UNIVERSE_ENGINE,
                correlation_id=correlation_id,
            )

        for identity in removed_symbols:
            previous = previous_map[identity]
            await self._publish_event(
                event_type=MarketDataEventType.SYMBOL_REMOVED_FROM_UNIVERSE,
                payload=SymbolUniverseChangePayload(
                    symbol=previous.symbol.symbol,
                    exchange=previous.symbol.exchange,
                    version=current_snapshot.version,
                    changed_at=changed_at.isoformat(),
                    reasons=tuple(
                        getattr(reason, "value", str(reason))
                        for reason in exclusion_reasons.get(identity, ())
                    ),
                ),
                source=SystemEventSource.UNIVERSE_ENGINE,
                correlation_id=correlation_id,
            )

        return admitted_symbols, removed_symbols

    async def _publish_quality_signals(
        self,
        signals: tuple[DataQualitySignal, ...],
        *,
        correlation_id: UUID | None = None,
    ) -> None:
        if not signals:
            return

        self._record_quality_signals(signals)
        for signal in signals:
            event_type = self._map_quality_signal_to_event_type(signal.issue_type)
            if event_type is None:
                continue
            await self._publish_event(
                event_type=event_type,
                payload=DataQualitySignalPayload.from_signal(signal),
                source=SystemEventSource.DATA_QUALITY_MONITOR,
                correlation_id=correlation_id,
            )

    def _record_quality_signals(self, signals: tuple[DataQualitySignal, ...]) -> None:
        by_symbol: dict[SymbolIdentity, dict[DataQualityIssueType, DataQualitySignal]] = {}
        for identity, existing_signals in self.state.quality_signals_by_identity.items():
            by_symbol[identity] = {signal.issue_type: signal for signal in existing_signals}

        for signal in signals:
            by_symbol.setdefault(signal.identity, {})[signal.issue_type] = signal

        self.state.quality_signals_by_identity = {
            identity: tuple(issues.values()) for identity, issues in by_symbol.items()
        }
        self._refresh_diagnostics(
            quality_signal_identities_count=len(self.state.quality_signals_by_identity)
        )

    def _map_quality_signal_to_event_type(
        self,
        issue_type: DataQualityIssueType,
    ) -> MarketDataEventType | None:
        mapping = {
            DataQualityIssueType.GAP: MarketDataEventType.DATA_GAP_DETECTED,
            DataQualityIssueType.STALE: MarketDataEventType.MARKET_DATA_STALE,
            DataQualityIssueType.OUTLIER: MarketDataEventType.MARKET_DATA_OUTLIER_DETECTED,
            DataQualityIssueType.OUT_OF_ORDER: MarketDataEventType.MARKET_DATA_OUTLIER_DETECTED,
            DataQualityIssueType.ORDERBOOK_CROSSED: MarketDataEventType.MARKET_DATA_OUTLIER_DETECTED,
            DataQualityIssueType.SOURCE_DEGRADED: MarketDataEventType.MARKET_DATA_SOURCE_DEGRADED,
        }
        return mapping.get(issue_type)

    async def _publish_event(
        self,
        *,
        event_type: MarketDataEventType,
        payload: SupportsEventPayload,
        source: str,
        correlation_id: UUID | None,
    ) -> None:
        await self.event_bus.publish(
            build_market_data_event(
                event_type=event_type,
                payload=payload,
                source=source,
                correlation_id=correlation_id,
            )
        )

    def _ensure_started(self, operation: str) -> None:
        if not self._started:
            raise RuntimeError(
                f"MarketDataRuntime не запущен. Операция {operation} недоступна до start()."
            )

    def _refresh_readiness_from_state(self) -> None:
        raw_snapshot = self.state.raw_snapshot
        admissible_snapshot = self.state.admissible_snapshot
        assessment = self.state.quality_assessment

        readiness_reasons: list[str] = []
        degraded_reasons: list[str] = []
        lifecycle_state = "not_ready"
        ready = False

        if raw_snapshot is None:
            readiness_reasons.append("no_raw_universe_snapshot")
        if admissible_snapshot is None:
            readiness_reasons.append("no_admissible_universe_snapshot")
        if assessment is None:
            readiness_reasons.append("no_universe_quality_assessment")
        elif assessment.state == UniverseConfidenceState.READY:
            lifecycle_state = "ready"
            ready = True
        elif assessment.state == UniverseConfidenceState.DEGRADED:
            lifecycle_state = "degraded"
            readiness_reasons.append("universe_confidence_degraded")
            degraded_reasons.extend(assessment.blocking_reasons)
        elif assessment.state == UniverseConfidenceState.BLOCKED:
            lifecycle_state = "blocked"
            readiness_reasons.append("universe_confidence_blocked")
            degraded_reasons.extend(assessment.blocking_reasons)

        self._refresh_diagnostics(
            ready=ready,
            lifecycle_state=lifecycle_state,
            raw_snapshot_version=raw_snapshot.version if raw_snapshot is not None else None,
            admissible_snapshot_version=(
                admissible_snapshot.version if admissible_snapshot is not None else None
            ),
            quality_assessment_version=assessment.version if assessment is not None else None,
            raw_symbols_count=len(raw_snapshot.symbols) if raw_snapshot is not None else 0,
            admissible_symbols_count=(
                len(admissible_snapshot.symbols) if admissible_snapshot is not None else 0
            ),
            universe_confidence_state=assessment.state.value if assessment is not None else None,
            universe_confidence=(str(assessment.confidence) if assessment is not None else None),
            last_universe_update_at=(
                raw_snapshot.created_at.astimezone(UTC).isoformat()
                if raw_snapshot is not None
                else None
            ),
            readiness_reasons=tuple(dict.fromkeys(readiness_reasons)),
            degraded_reasons=tuple(dict.fromkeys(degraded_reasons)),
        )

    def _refresh_diagnostics(
        self,
        **updates: object,
    ) -> None:
        current: dict[str, Any] = asdict(self._diagnostics)
        current.update(updates)
        self._diagnostics = MarketDataRuntimeDiagnostics(
            started=self._started,
            ready=bool(current["ready"]),
            lifecycle_state=str(current["lifecycle_state"]),
            raw_snapshot_version=current["raw_snapshot_version"],
            admissible_snapshot_version=current["admissible_snapshot_version"],
            quality_assessment_version=current["quality_assessment_version"],
            raw_symbols_count=int(current["raw_symbols_count"]),
            admissible_symbols_count=int(current["admissible_symbols_count"]),
            metrics_count=int(current["metrics_count"]),
            quality_signal_identities_count=int(current["quality_signal_identities_count"]),
            universe_confidence_state=(
                str(current["universe_confidence_state"])
                if current["universe_confidence_state"] is not None
                else None
            ),
            universe_confidence=(
                str(current["universe_confidence"])
                if current["universe_confidence"] is not None
                else None
            ),
            last_tick_at=(
                str(current["last_tick_at"]) if current["last_tick_at"] is not None else None
            ),
            last_universe_update_at=(
                str(current["last_universe_update_at"])
                if current["last_universe_update_at"] is not None
                else None
            ),
            readiness_reasons=tuple(current.get("readiness_reasons", [])),
            degraded_reasons=tuple(current.get("degraded_reasons", [])),
        )
        self._push_diagnostics()

    def _push_diagnostics(self) -> None:
        if self._diagnostics_sink is not None:
            self._diagnostics_sink(self.get_runtime_diagnostics())


def create_market_data_runtime(
    *,
    event_bus: EnhancedEventBus,
    controller: SystemController | None = None,
    config: MarketDataRuntimeConfig | None = None,
    diagnostics_sink: Callable[[dict[str, object]], None] | None = None,
) -> MarketDataRuntime:
    """Собрать explicit runtime path для Market Data Layer Phase 6."""
    return MarketDataRuntime(
        event_bus=event_bus,
        config=config,
        controller=controller,
        diagnostics_sink=diagnostics_sink,
    )

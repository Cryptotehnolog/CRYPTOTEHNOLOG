"""Overview facade для read-only dashboard snapshot."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cryptotechnolog.config import get_logger
from cryptotechnolog.core.health import ComponentHealth, HealthStatus, SystemHealth

from ..dto.backtest import BacktestAvailabilityItemDTO, BacktestSummaryDTO
from ..dto.execution import ExecutionAvailabilityItemDTO, ExecutionSummaryDTO
from ..dto.manager import ManagerAvailabilityItemDTO, ManagerSummaryDTO
from ..dto.oms import OmsAvailabilityItemDTO, OmsSummaryDTO
from ..dto.opportunity import OpportunityAvailabilityItemDTO, OpportunitySummaryDTO
from ..dto.orchestration import (
    OrchestrationAvailabilityItemDTO,
    OrchestrationSummaryDTO,
)
from ..dto.overview import (
    CircuitBreakerSummaryDTO,
    EventSummaryDTO,
    HealthSummaryDTO,
    ModuleAvailabilityDTO,
    OverviewSnapshotDTO,
    PendingApprovalsSummaryDTO,
    SystemStateSummaryDTO,
)
from ..dto.paper import PaperAvailabilityItemDTO, PaperSummaryDTO
from ..dto.portfolio_governor import (
    PortfolioGovernorAvailabilityItemDTO,
    PortfolioGovernorSummaryDTO,
)
from ..dto.position_expansion import (
    PositionExpansionAvailabilityItemDTO,
    PositionExpansionSummaryDTO,
)
from ..dto.positions import (
    OpenPositionDTO,
    OpenPositionsDTO,
    PositionHistoryDTO,
    PositionHistoryRecordDTO,
)
from ..dto.reporting import (
    ReportingCatalogCountsDTO,
    ReportingLastArtifactDTO,
    ReportingLastBundleDTO,
    ReportingSummaryDTO,
)
from ..dto.risk import RiskConstraintDTO, RiskSummaryDTO
from ..dto.signals import SignalAvailabilityItemDTO, SignalsSummaryDTO
from ..dto.strategy import StrategyAvailabilityItemDTO, StrategySummaryDTO
from ..dto.validation import ValidationAvailabilityItemDTO, ValidationSummaryDTO

if TYPE_CHECKING:
    from .composition import OverviewCompositionRoot
    from .contracts import (
        BacktestSummarySnapshot,
        ExecutionSummarySnapshot,
        ManagerSummarySnapshot,
        OmsSummarySnapshot,
        OpportunitySummarySnapshot,
        OrchestrationSummarySnapshot,
        PaperSummarySnapshot,
        PortfolioGovernorSummarySnapshot,
        PositionExpansionSummarySnapshot,
        ReportingSummarySnapshot,
        SignalSummarySnapshot,
        StrategySummarySnapshot,
        ValidationSummarySnapshot,
    )

from .sources import parse_circuit_breaker_snapshots

logger = get_logger(__name__)


class OverviewFacade:
    """Facade для агрегации overview snapshot панели."""

    def __init__(self, composition_root: OverviewCompositionRoot) -> None:
        self._composition_root = composition_root

    async def get_overview_snapshot(self) -> OverviewSnapshotDTO:
        """Получить полный overview snapshot."""
        system_status = await self._composition_root.system_status_source.get_system_status()
        health = await self._get_health_snapshot(system_status.components)
        approvals = (
            await self._composition_root.pending_approvals_source.get_pending_approvals_summary()
        )
        event_summary = await self._composition_root.event_summary_source.get_event_summary()
        module_availability = (
            await self._composition_root.module_availability_source.get_module_availability()
        )
        circuit_breakers = parse_circuit_breaker_snapshots(system_status.circuit_breakers)

        return OverviewSnapshotDTO(
            system_state=SystemStateSummaryDTO(
                is_running=system_status.is_running,
                is_shutting_down=system_status.is_shutting_down,
                current_state=system_status.current_state.value,
                startup_phase=system_status.startup_phase.value,
                shutdown_phase=system_status.shutdown_phase.value,
                uptime_seconds=system_status.uptime_seconds,
                trade_allowed=system_status.current_state.is_trading_allowed,
                last_error=system_status.last_error,
            ),
            health_summary=HealthSummaryDTO(
                overall_status=health.overall_status.value,
                component_count=len(health.components),
                unhealthy_components=health.get_unhealthy_components(),
                timestamp=health.timestamp,
            ),
            pending_approvals=PendingApprovalsSummaryDTO(
                pending_count=approvals.pending_count,
                total_requests=approvals.total_requests,
                request_timeout_minutes=approvals.request_timeout_minutes,
            ),
            event_summary=EventSummaryDTO(
                total_published=event_summary.total_published,
                total_delivered=event_summary.total_delivered,
                total_dropped=event_summary.total_dropped,
                total_rate_limited=event_summary.total_rate_limited,
                subscriber_count=event_summary.subscriber_count,
                persistence_enabled=event_summary.persistence_enabled,
                backpressure_strategy=event_summary.backpressure_strategy,
            ),
            circuit_breaker_summary=[
                CircuitBreakerSummaryDTO(
                    name=item.name,
                    state=item.state,
                    failure_count=item.failure_count,
                    success_count=item.success_count,
                    failure_threshold=item.failure_threshold,
                    recovery_timeout=item.recovery_timeout,
                )
                for item in circuit_breakers
            ],
            module_availability=[
                ModuleAvailabilityDTO(
                    key=module.key,
                    title=module.title,
                    description=module.description,
                    route=module.route,
                    status=module.status.value,
                    phase=module.phase,
                    status_reason=module.status_reason,
                )
                for module in module_availability
            ],
        )

    async def get_risk_summary(self) -> RiskSummaryDTO:
        """Получить узкий read-only risk summary snapshot."""
        system_status = await self._composition_root.system_status_source.get_system_status()
        module_availability = (
            await self._composition_root.module_availability_source.get_module_availability()
        )
        risk_runtime = await self._composition_root.risk_runtime_source.get_risk_runtime_snapshot()
        risk_config = await self._composition_root.risk_config_source.get_risk_config_snapshot()

        risk_module = next(
            (module for module in module_availability if module.key == "risk"),
            None,
        )

        global_status, limiting_state = self._derive_risk_status(
            trade_allowed=system_status.current_state.is_trading_allowed,
            risk_multiplier=risk_runtime.risk_multiplier,
            allow_new_positions=risk_runtime.allow_new_positions,
        )

        summary_reason = system_status.last_error

        return RiskSummaryDTO(
            module_status=(risk_module.status.value if risk_module is not None else "inactive"),
            current_state=system_status.current_state.value,
            global_status=global_status,
            limiting_state=limiting_state,
            trading_blocked=not system_status.current_state.is_trading_allowed,
            active_risk_path=risk_runtime.active_risk_path,
            state_note=risk_runtime.policy_description,
            summary_reason=summary_reason,
            constraints=[
                RiskConstraintDTO(
                    key="new_positions",
                    label="Новые позиции",
                    value="разрешены" if risk_runtime.allow_new_positions else "заблокированы",
                    status="normal" if risk_runtime.allow_new_positions else "blocked",
                    note=(
                        "Текущее состояние допускает набор новых позиций."
                        if risk_runtime.allow_new_positions
                        else "Набор новых позиций ограничен текущим runtime state."
                    ),
                ),
                RiskConstraintDTO(
                    key="new_orders",
                    label="Новые ордера",
                    value="разрешены" if risk_runtime.allow_new_orders else "заблокированы",
                    status="normal" if risk_runtime.allow_new_orders else "blocked",
                    note=(
                        "Снимок отражает текущее правило state-machine без action UI."
                        if risk_runtime.allow_new_orders
                        else "Подача новых ордеров запрещена текущим runtime state."
                    ),
                ),
                RiskConstraintDTO(
                    key="risk_multiplier",
                    label="Risk multiplier",
                    value=f"{risk_runtime.risk_multiplier:.2f}x",
                    status=(
                        "normal"
                        if risk_runtime.risk_multiplier >= 1
                        else "limited"
                        if risk_runtime.risk_multiplier > 0
                        else "blocked"
                    ),
                    note="Множитель берётся из state-machine policy текущего состояния.",
                ),
                RiskConstraintDTO(
                    key="max_positions",
                    label="Лимит позиций",
                    value=str(risk_runtime.max_positions),
                    status="limited",
                    note="Текущее ограничение на количество позиций из state policy.",
                ),
                RiskConstraintDTO(
                    key="max_order_size",
                    label="Макс. размер ордера",
                    value=f"{risk_runtime.max_order_size:.2%}",
                    status="limited",
                    note="Доля портфеля, допустимая для одного ордера в текущем состоянии.",
                ),
                RiskConstraintDTO(
                    key="max_r_per_trade",
                    label="Макс. R на сделку",
                    value=f"{risk_config.max_r_per_trade:.2f} R",
                    status="limited",
                    note="Глобальный settings-based лимит без per-symbol breakdown.",
                ),
                RiskConstraintDTO(
                    key="max_portfolio_r",
                    label="Макс. portfolio R",
                    value=f"{risk_config.max_portfolio_r:.2f} R",
                    status="limited",
                    note="Агрегированный риск портфеля из текущего settings path.",
                ),
                RiskConstraintDTO(
                    key="max_total_exposure",
                    label="Макс. суммарная экспозиция",
                    value=f"${risk_config.max_total_exposure_usd:,.0f}",
                    status="limited",
                    note="Общий USD cap без детального exposures explorer.",
                ),
                RiskConstraintDTO(
                    key="max_position_size",
                    label="Макс. размер позиции",
                    value=f"${risk_config.max_position_size_usd:,.0f}",
                    status="limited",
                    note="Глобальный размер позиции из runtime settings.",
                ),
                RiskConstraintDTO(
                    key="base_r_percent",
                    label="Базовый риск",
                    value=f"{risk_config.base_r_percent:.2%}",
                    status="info",
                    note="Базовая risk truth из settings, без policy editor.",
                ),
                RiskConstraintDTO(
                    key="kill_switch",
                    label="Kill switch",
                    value="включён" if risk_config.kill_switch_enabled else "выключен",
                    status="normal" if risk_config.kill_switch_enabled else "warning",
                    note="Показывается только глобальный флаг без управляющих действий.",
                ),
                RiskConstraintDTO(
                    key="manual_approval",
                    label="Ручное подтверждение",
                    value=("требуется" if risk_runtime.require_manual_approval else "не требуется"),
                    status="limited" if risk_runtime.require_manual_approval else "normal",
                    note="Флаг берётся из state policy текущего состояния.",
                ),
            ],
        )

    async def get_open_positions(self) -> OpenPositionsDTO:
        """Получить узкий read-only snapshot открытых позиций."""
        open_positions = (
            await self._composition_root.open_positions_source.get_open_positions_snapshot()
        )
        return OpenPositionsDTO(
            positions=[
                OpenPositionDTO(
                    position_id=item.position_id,
                    symbol=item.symbol,
                    exchange=item.exchange,
                    strategy=item.strategy,
                    side=item.side,
                    entry_price=item.entry_price,
                    quantity=item.quantity,
                    initial_stop=item.initial_stop,
                    current_stop=item.current_stop,
                    current_risk_usd=item.current_risk_usd,
                    current_risk_r=item.current_risk_r,
                    current_price=item.current_price,
                    unrealized_pnl_usd=item.unrealized_pnl_usd,
                    unrealized_pnl_percent=item.unrealized_pnl_percent,
                    trailing_state=item.trailing_state,
                    opened_at=item.opened_at.isoformat(),
                    updated_at=item.updated_at.isoformat(),
                )
                for item in open_positions.positions
            ]
        )

    async def get_position_history(self) -> PositionHistoryDTO:
        """Получить узкий read-only snapshot истории закрытых позиций."""
        if self._composition_root.position_history_source is None:
            raise RuntimeError("Position history source не подключён в composition root")
        position_history = (
            await self._composition_root.position_history_source.get_position_history_snapshot()
        )
        return PositionHistoryDTO(
            positions=[
                PositionHistoryRecordDTO(
                    position_id=item.position_id,
                    symbol=item.symbol,
                    exchange=item.exchange,
                    strategy=item.strategy,
                    side=item.side,
                    entry_price=item.entry_price,
                    quantity=item.quantity,
                    initial_stop=item.initial_stop,
                    current_stop=item.current_stop,
                    trailing_state=item.trailing_state,
                    opened_at=item.opened_at.isoformat(),
                    closed_at=item.closed_at.isoformat(),
                    exit_price=item.exit_price,
                    exit_reason=item.exit_reason,
                    realized_pnl_r=item.realized_pnl_r,
                    realized_pnl_usd=item.realized_pnl_usd,
                    realized_pnl_percent=item.realized_pnl_percent,
                )
                for item in position_history.positions
            ]
        )

    async def get_signals_summary(self) -> SignalsSummaryDTO:
        """Получить узкий read-only signals summary snapshot."""
        module_availability = (
            await self._composition_root.module_availability_source.get_module_availability()
        )
        signal_summary = (
            await self._composition_root.signal_summary_source.get_signal_summary_snapshot()
        )

        signals_module = next(
            (module for module in module_availability if module.key == "signals"),
            None,
        )

        global_status = self._derive_signals_global_status(
            started=signal_summary.started,
            ready=signal_summary.ready,
            lifecycle_state=signal_summary.lifecycle_state,
        )
        summary_note = self._build_signal_summary_note(signal_summary)
        summary_reason = self._build_signal_summary_reason(signal_summary)

        return SignalsSummaryDTO(
            module_status=(
                signals_module.status.value if signals_module is not None else "inactive"
            ),
            global_status=global_status,
            lifecycle_state=signal_summary.lifecycle_state,
            started=signal_summary.started,
            ready=signal_summary.ready,
            tracked_signal_keys=signal_summary.tracked_signal_keys,
            active_signal_keys=signal_summary.active_signal_keys,
            last_signal_id=signal_summary.last_signal_id,
            last_event_type=signal_summary.last_event_type,
            last_context_at=signal_summary.last_context_at,
            active_signal_path=signal_summary.active_signal_path,
            freshness_state=self._derive_signal_freshness_state(signal_summary),
            summary_note=summary_note,
            summary_reason=summary_reason,
            availability=[
                SignalAvailabilityItemDTO(
                    key="runtime_started",
                    label="Signal runtime",
                    value="started" if signal_summary.started else "not started",
                    status="normal" if signal_summary.started else "warning",
                    note="Глобальный runtime flag без signal actions.",
                ),
                SignalAvailabilityItemDTO(
                    key="runtime_ready",
                    label="Readiness",
                    value="ready" if signal_summary.ready else "not ready",
                    status="normal" if signal_summary.ready else "warning",
                    note="Readiness отражает только surfaced diagnostics signal runtime.",
                ),
                SignalAvailabilityItemDTO(
                    key="tracked_signal_keys",
                    label="Tracked signal keys",
                    value=str(signal_summary.tracked_signal_keys),
                    status="info",
                    note="Количество signal keys в текущем runtime snapshot.",
                ),
                SignalAvailabilityItemDTO(
                    key="active_signal_keys",
                    label="Active signal keys",
                    value=str(signal_summary.active_signal_keys),
                    status="normal" if signal_summary.active_signal_keys > 0 else "info",
                    note="Только агрегированный счётчик без candidate explorer.",
                ),
                SignalAvailabilityItemDTO(
                    key="invalidated_signal_keys",
                    label="Invalidated signal keys",
                    value=str(signal_summary.invalidated_signal_keys),
                    status="warning" if signal_summary.invalidated_signal_keys > 0 else "info",
                    note="Показывается как surfaced counter без history browser.",
                ),
                SignalAvailabilityItemDTO(
                    key="expired_signal_keys",
                    label="Expired signal keys",
                    value=str(signal_summary.expired_signal_keys),
                    status="warning" if signal_summary.expired_signal_keys > 0 else "info",
                    note="Сводный freshness indicator без live stream.",
                ),
                SignalAvailabilityItemDTO(
                    key="last_context_at",
                    label="Last context at",
                    value=signal_summary.last_context_at or "not surfaced",
                    status="normal" if signal_summary.last_context_at is not None else "info",
                    note="Последний observed context timestamp, если surfaced runtime truth.",
                ),
                SignalAvailabilityItemDTO(
                    key="last_signal_id",
                    label="Last signal id",
                    value=signal_summary.last_signal_id or "not surfaced",
                    status="normal" if signal_summary.last_signal_id is not None else "info",
                    note="Последний signal id без разворачивания signal details.",
                ),
                SignalAvailabilityItemDTO(
                    key="last_event_type",
                    label="Last event type",
                    value=signal_summary.last_event_type or "not surfaced",
                    status="normal" if signal_summary.last_event_type is not None else "info",
                    note="Последний surfaced signal event type.",
                ),
            ],
        )

    async def get_strategy_summary(self) -> StrategySummaryDTO:
        """Получить узкий read-only strategy summary snapshot."""
        module_availability = (
            await self._composition_root.module_availability_source.get_module_availability()
        )
        strategy_summary = (
            await self._composition_root.strategy_summary_source.get_strategy_summary_snapshot()
        )

        strategy_module = next(
            (module for module in module_availability if module.key == "strategy"),
            None,
        )

        global_status = self._derive_strategy_global_status(
            started=strategy_summary.started,
            ready=strategy_summary.ready,
            lifecycle_state=strategy_summary.lifecycle_state,
        )
        summary_note = self._build_strategy_summary_note(strategy_summary)
        summary_reason = self._build_strategy_summary_reason(strategy_summary)

        return StrategySummaryDTO(
            module_status=(
                strategy_module.status.value if strategy_module is not None else "inactive"
            ),
            global_status=global_status,
            lifecycle_state=strategy_summary.lifecycle_state,
            started=strategy_summary.started,
            ready=strategy_summary.ready,
            tracked_context_keys=strategy_summary.tracked_context_keys,
            tracked_candidate_keys=strategy_summary.tracked_candidate_keys,
            actionable_candidate_keys=strategy_summary.actionable_candidate_keys,
            last_signal_id=strategy_summary.last_signal_id,
            last_candidate_id=strategy_summary.last_candidate_id,
            last_event_type=strategy_summary.last_event_type,
            active_strategy_path=strategy_summary.active_strategy_path,
            strategy_source=strategy_summary.strategy_source,
            freshness_state=self._derive_strategy_freshness_state(strategy_summary),
            summary_note=summary_note,
            summary_reason=summary_reason,
            availability=[
                StrategyAvailabilityItemDTO(
                    key="runtime_started",
                    label="Strategy runtime",
                    value="started" if strategy_summary.started else "not started",
                    status="normal" if strategy_summary.started else "warning",
                    note="Глобальный runtime flag без strategy actions.",
                ),
                StrategyAvailabilityItemDTO(
                    key="runtime_ready",
                    label="Readiness",
                    value="ready" if strategy_summary.ready else "not ready",
                    status="normal" if strategy_summary.ready else "warning",
                    note="Readiness отражает только surfaced diagnostics strategy runtime.",
                ),
                StrategyAvailabilityItemDTO(
                    key="tracked_context_keys",
                    label="Tracked context keys",
                    value=str(strategy_summary.tracked_context_keys),
                    status="info",
                    note="Количество strategy context keys в текущем runtime snapshot.",
                ),
                StrategyAvailabilityItemDTO(
                    key="tracked_candidate_keys",
                    label="Tracked candidate keys",
                    value=str(strategy_summary.tracked_candidate_keys),
                    status="info",
                    note="Суммарный счётчик strategy candidates без history browser.",
                ),
                StrategyAvailabilityItemDTO(
                    key="actionable_candidate_keys",
                    label="Actionable candidate keys",
                    value=str(strategy_summary.actionable_candidate_keys),
                    status=("normal" if strategy_summary.actionable_candidate_keys > 0 else "info"),
                    note="Показывается только агрегированный actionable counter.",
                ),
                StrategyAvailabilityItemDTO(
                    key="invalidated_candidate_keys",
                    label="Invalidated candidate keys",
                    value=str(strategy_summary.invalidated_candidate_keys),
                    status=(
                        "warning" if strategy_summary.invalidated_candidate_keys > 0 else "info"
                    ),
                    note="Показывается как surfaced counter без details explorer.",
                ),
                StrategyAvailabilityItemDTO(
                    key="expired_candidate_keys",
                    label="Expired candidate keys",
                    value=str(strategy_summary.expired_candidate_keys),
                    status=("warning" if strategy_summary.expired_candidate_keys > 0 else "info"),
                    note="Сводный freshness indicator без candidate history browser.",
                ),
                StrategyAvailabilityItemDTO(
                    key="last_signal_id",
                    label="Last signal id",
                    value=strategy_summary.last_signal_id or "not surfaced",
                    status="normal" if strategy_summary.last_signal_id is not None else "info",
                    note="Последний surfaced signal reference для strategy contour.",
                ),
                StrategyAvailabilityItemDTO(
                    key="last_candidate_id",
                    label="Last candidate id",
                    value=strategy_summary.last_candidate_id or "not surfaced",
                    status=("normal" if strategy_summary.last_candidate_id is not None else "info"),
                    note="Последний surfaced strategy candidate без candidate explorer.",
                ),
            ],
        )

    async def get_execution_summary(self) -> ExecutionSummaryDTO:
        """Получить узкий read-only execution summary snapshot."""
        module_availability = (
            await self._composition_root.module_availability_source.get_module_availability()
        )
        execution_summary = (
            await self._composition_root.execution_summary_source.get_execution_summary_snapshot()
        )

        execution_module = next(
            (module for module in module_availability if module.key == "execution"),
            None,
        )

        global_status = self._derive_execution_global_status(
            started=execution_summary.started,
            ready=execution_summary.ready,
            lifecycle_state=execution_summary.lifecycle_state,
        )
        summary_note = self._build_execution_summary_note(execution_summary)
        summary_reason = self._build_execution_summary_reason(execution_summary)

        return ExecutionSummaryDTO(
            module_status=(
                execution_module.status.value if execution_module is not None else "inactive"
            ),
            global_status=global_status,
            lifecycle_state=execution_summary.lifecycle_state,
            started=execution_summary.started,
            ready=execution_summary.ready,
            tracked_context_keys=execution_summary.tracked_context_keys,
            tracked_intent_keys=execution_summary.tracked_intent_keys,
            executable_intent_keys=execution_summary.executable_intent_keys,
            last_candidate_id=execution_summary.last_candidate_id,
            last_intent_id=execution_summary.last_intent_id,
            last_event_type=execution_summary.last_event_type,
            active_execution_path=execution_summary.active_execution_path,
            execution_source=execution_summary.execution_source,
            freshness_state=self._derive_execution_freshness_state(execution_summary),
            summary_note=summary_note,
            summary_reason=summary_reason,
            availability=[
                ExecutionAvailabilityItemDTO(
                    key="runtime_started",
                    label="Execution runtime",
                    value="started" if execution_summary.started else "not started",
                    status="normal" if execution_summary.started else "warning",
                    note="Глобальный runtime flag без execution actions.",
                ),
                ExecutionAvailabilityItemDTO(
                    key="runtime_ready",
                    label="Readiness",
                    value="ready" if execution_summary.ready else "not ready",
                    status="normal" if execution_summary.ready else "warning",
                    note="Readiness отражает только surfaced diagnostics execution runtime.",
                ),
                ExecutionAvailabilityItemDTO(
                    key="tracked_context_keys",
                    label="Tracked context keys",
                    value=str(execution_summary.tracked_context_keys),
                    status="info",
                    note="Количество execution context keys в текущем runtime snapshot.",
                ),
                ExecutionAvailabilityItemDTO(
                    key="tracked_intent_keys",
                    label="Tracked intent keys",
                    value=str(execution_summary.tracked_intent_keys),
                    status="info",
                    note="Суммарный счётчик execution intents без history browser.",
                ),
                ExecutionAvailabilityItemDTO(
                    key="executable_intent_keys",
                    label="Executable intent keys",
                    value=str(execution_summary.executable_intent_keys),
                    status=("normal" if execution_summary.executable_intent_keys > 0 else "info"),
                    note="Показывается только агрегированный executable counter.",
                ),
                ExecutionAvailabilityItemDTO(
                    key="invalidated_intent_keys",
                    label="Invalidated intent keys",
                    value=str(execution_summary.invalidated_intent_keys),
                    status=("warning" if execution_summary.invalidated_intent_keys > 0 else "info"),
                    note="Показывается как surfaced counter без details explorer.",
                ),
                ExecutionAvailabilityItemDTO(
                    key="expired_intent_keys",
                    label="Expired intent keys",
                    value=str(execution_summary.expired_intent_keys),
                    status=("warning" if execution_summary.expired_intent_keys > 0 else "info"),
                    note="Сводный freshness indicator без intent history browser.",
                ),
                ExecutionAvailabilityItemDTO(
                    key="last_candidate_id",
                    label="Last candidate id",
                    value=execution_summary.last_candidate_id or "not surfaced",
                    status=(
                        "normal" if execution_summary.last_candidate_id is not None else "info"
                    ),
                    note="Последний surfaced strategy candidate reference для execution contour.",
                ),
                ExecutionAvailabilityItemDTO(
                    key="last_intent_id",
                    label="Last intent id",
                    value=execution_summary.last_intent_id or "not surfaced",
                    status=("normal" if execution_summary.last_intent_id is not None else "info"),
                    note="Последний surfaced execution intent без отдельного обозревателя.",
                ),
            ],
        )

    async def get_opportunity_summary(self) -> OpportunitySummaryDTO:
        """Получить узкий read-only opportunity summary snapshot."""
        module_availability = (
            await self._composition_root.module_availability_source.get_module_availability()
        )
        opportunity_summary = await self._composition_root.opportunity_summary_source.get_opportunity_summary_snapshot()

        opportunity_module = next(
            (module for module in module_availability if module.key == "opportunity"),
            None,
        )

        global_status = self._derive_opportunity_global_status(
            started=opportunity_summary.started,
            ready=opportunity_summary.ready,
            lifecycle_state=opportunity_summary.lifecycle_state,
        )
        summary_note = self._build_opportunity_summary_note(opportunity_summary)
        summary_reason = self._build_opportunity_summary_reason(opportunity_summary)

        return OpportunitySummaryDTO(
            module_status=(
                opportunity_module.status.value if opportunity_module is not None else "inactive"
            ),
            global_status=global_status,
            lifecycle_state=opportunity_summary.lifecycle_state,
            started=opportunity_summary.started,
            ready=opportunity_summary.ready,
            tracked_context_keys=opportunity_summary.tracked_context_keys,
            tracked_selection_keys=opportunity_summary.tracked_selection_keys,
            selected_keys=opportunity_summary.selected_keys,
            last_intent_id=opportunity_summary.last_intent_id,
            last_selection_id=opportunity_summary.last_selection_id,
            last_event_type=opportunity_summary.last_event_type,
            active_opportunity_path=opportunity_summary.active_opportunity_path,
            opportunity_source=opportunity_summary.opportunity_source,
            freshness_state=self._derive_opportunity_freshness_state(opportunity_summary),
            summary_note=summary_note,
            summary_reason=summary_reason,
            availability=[
                OpportunityAvailabilityItemDTO(
                    key="runtime_started",
                    label="Opportunity runtime",
                    value="started" if opportunity_summary.started else "not started",
                    status="normal" if opportunity_summary.started else "warning",
                    note="Глобальный runtime flag без selection actions.",
                ),
                OpportunityAvailabilityItemDTO(
                    key="runtime_ready",
                    label="Readiness",
                    value="ready" if opportunity_summary.ready else "not ready",
                    status="normal" if opportunity_summary.ready else "warning",
                    note="Readiness отражает только surfaced diagnostics opportunity runtime.",
                ),
                OpportunityAvailabilityItemDTO(
                    key="tracked_context_keys",
                    label="Tracked context keys",
                    value=str(opportunity_summary.tracked_context_keys),
                    status="info",
                    note="Количество ключей opportunity context в текущем runtime snapshot.",
                ),
                OpportunityAvailabilityItemDTO(
                    key="tracked_selection_keys",
                    label="Tracked selection keys",
                    value=str(opportunity_summary.tracked_selection_keys),
                    status="info",
                    note="Суммарный счётчик selection keys без широкого opportunity browser.",
                ),
                OpportunityAvailabilityItemDTO(
                    key="selected_keys",
                    label="Selected keys",
                    value=str(opportunity_summary.selected_keys),
                    status="normal" if opportunity_summary.selected_keys > 0 else "info",
                    note="Показывается только агрегированный счётчик текущих selected opportunities.",
                ),
                OpportunityAvailabilityItemDTO(
                    key="invalidated_selection_keys",
                    label="Invalidated selection keys",
                    value=str(opportunity_summary.invalidated_selection_keys),
                    status=(
                        "warning" if opportunity_summary.invalidated_selection_keys > 0 else "info"
                    ),
                    note="Показывается как выведенный счётчик без обозревателя деталей.",
                ),
                OpportunityAvailabilityItemDTO(
                    key="expired_selection_keys",
                    label="Expired selection keys",
                    value=str(opportunity_summary.expired_selection_keys),
                    status=(
                        "warning" if opportunity_summary.expired_selection_keys > 0 else "info"
                    ),
                    note="Сводный индикатор свежести без обозревателя истории selection.",
                ),
                OpportunityAvailabilityItemDTO(
                    key="last_intent_id",
                    label="Last intent id",
                    value=opportunity_summary.last_intent_id or "not surfaced",
                    status="normal" if opportunity_summary.last_intent_id is not None else "info",
                    note="Последняя surfaced ссылка на execution intent для opportunity-контура.",
                ),
                OpportunityAvailabilityItemDTO(
                    key="last_selection_id",
                    label="Last selection id",
                    value=opportunity_summary.last_selection_id or "not surfaced",
                    status=(
                        "normal" if opportunity_summary.last_selection_id is not None else "info"
                    ),
                    note="Последний surfaced opportunity selection без отдельного обозревателя.",
                ),
                OpportunityAvailabilityItemDTO(
                    key="last_event_type",
                    label="Last event type",
                    value=opportunity_summary.last_event_type or "not surfaced",
                    status="normal" if opportunity_summary.last_event_type is not None else "info",
                    note="Последний surfaced opportunity event type.",
                ),
            ],
        )

    def _derive_opportunity_global_status(
        self,
        *,
        started: bool,
        ready: bool,
        lifecycle_state: str,
    ) -> str:
        if not started:
            return "inactive"
        if ready and lifecycle_state == "ready":
            return "ready"
        if lifecycle_state == "degraded":
            return "degraded"
        return "warming"

    def _derive_opportunity_freshness_state(
        self,
        opportunity_summary: OpportunitySummarySnapshot,
    ) -> str:
        if opportunity_summary.last_selection_id is None:
            return "not_surfaced"
        if opportunity_summary.expired_selection_keys > 0:
            return "expired_selections_present"
        if opportunity_summary.selected_keys > 0:
            return "selected_opportunity_surfaced"
        if opportunity_summary.tracked_selection_keys > 0:
            return "selection_recently_surfaced"
        return "selection_state_surfaced"

    def _build_opportunity_summary_note(
        self,
        opportunity_summary: OpportunitySummarySnapshot,
    ) -> str:
        if opportunity_summary.degraded_reasons:
            return (
                "Opportunity runtime surfaced degraded reasons: "
                f"{', '.join(opportunity_summary.degraded_reasons)}"
            )
        if opportunity_summary.readiness_reasons:
            return (
                "Opportunity runtime surfaced readiness reasons: "
                f"{', '.join(opportunity_summary.readiness_reasons)}"
            )
        return "Opportunity runtime не surfaced дополнительных notes beyond current diagnostics."

    def _build_opportunity_summary_reason(
        self,
        opportunity_summary: OpportunitySummarySnapshot,
    ) -> str | None:
        if opportunity_summary.last_failure_reason is not None:
            return opportunity_summary.last_failure_reason
        if opportunity_summary.degraded_reasons:
            return ", ".join(opportunity_summary.degraded_reasons)
        return None

    async def get_orchestration_summary(self) -> OrchestrationSummaryDTO:
        """Получить узкий read-only orchestration summary snapshot."""
        module_availability = (
            await self._composition_root.module_availability_source.get_module_availability()
        )
        if self._composition_root.orchestration_summary_source is None:
            raise RuntimeError("Orchestration summary source is not configured")
        orchestration_summary = await self._composition_root.orchestration_summary_source.get_orchestration_summary_snapshot()

        orchestration_module = next(
            (module for module in module_availability if module.key == "orchestration"),
            None,
        )

        global_status = self._derive_orchestration_global_status(
            started=orchestration_summary.started,
            ready=orchestration_summary.ready,
            lifecycle_state=orchestration_summary.lifecycle_state,
        )
        summary_note = self._build_orchestration_summary_note(orchestration_summary)
        summary_reason = self._build_orchestration_summary_reason(orchestration_summary)

        return OrchestrationSummaryDTO(
            module_status=(
                orchestration_module.status.value
                if orchestration_module is not None
                else "inactive"
            ),
            global_status=global_status,
            lifecycle_state=orchestration_summary.lifecycle_state,
            started=orchestration_summary.started,
            ready=orchestration_summary.ready,
            tracked_context_keys=orchestration_summary.tracked_context_keys,
            tracked_decision_keys=orchestration_summary.tracked_decision_keys,
            forwarded_keys=orchestration_summary.forwarded_keys,
            abstained_keys=orchestration_summary.abstained_keys,
            invalidated_decision_keys=orchestration_summary.invalidated_decision_keys,
            expired_decision_keys=orchestration_summary.expired_decision_keys,
            last_selection_id=orchestration_summary.last_selection_id,
            last_decision_id=orchestration_summary.last_decision_id,
            last_event_type=orchestration_summary.last_event_type,
            active_orchestration_path=orchestration_summary.active_orchestration_path,
            orchestration_source=orchestration_summary.orchestration_source,
            freshness_state=self._derive_orchestration_freshness_state(orchestration_summary),
            summary_note=summary_note,
            summary_reason=summary_reason,
            availability=[
                OrchestrationAvailabilityItemDTO(
                    key="runtime_started",
                    label="Orchestration runtime",
                    value="started" if orchestration_summary.started else "not started",
                    status="normal" if orchestration_summary.started else "warning",
                    note="Глобальный runtime flag без действий над оркестрацией.",
                ),
                OrchestrationAvailabilityItemDTO(
                    key="runtime_ready",
                    label="Readiness",
                    value="ready" if orchestration_summary.ready else "not ready",
                    status="normal" if orchestration_summary.ready else "warning",
                    note="Readiness отражает только surfaced diagnostics orchestration runtime.",
                ),
                OrchestrationAvailabilityItemDTO(
                    key="tracked_context_keys",
                    label="Tracked context keys",
                    value=str(orchestration_summary.tracked_context_keys),
                    status="info",
                    note="Количество ключей orchestration context в текущем runtime snapshot.",
                ),
                OrchestrationAvailabilityItemDTO(
                    key="tracked_decision_keys",
                    label="Tracked decision keys",
                    value=str(orchestration_summary.tracked_decision_keys),
                    status="info",
                    note="Суммарный счётчик decision keys без широкого orchestration browser.",
                ),
                OrchestrationAvailabilityItemDTO(
                    key="forwarded_keys",
                    label="Forwarded keys",
                    value=str(orchestration_summary.forwarded_keys),
                    status="normal" if orchestration_summary.forwarded_keys > 0 else "info",
                    note="Показывается только агрегированный счётчик переданных решений.",
                ),
                OrchestrationAvailabilityItemDTO(
                    key="abstained_keys",
                    label="Abstained keys",
                    value=str(orchestration_summary.abstained_keys),
                    status="warning" if orchestration_summary.abstained_keys > 0 else "info",
                    note="Сводный счётчик воздержавшихся решений без детального обозревателя.",
                ),
                OrchestrationAvailabilityItemDTO(
                    key="invalidated_decision_keys",
                    label="Invalidated decision keys",
                    value=str(orchestration_summary.invalidated_decision_keys),
                    status=(
                        "warning" if orchestration_summary.invalidated_decision_keys > 0 else "info"
                    ),
                    note="Показывается как выведенный счётчик без обозревателя деталей.",
                ),
                OrchestrationAvailabilityItemDTO(
                    key="expired_decision_keys",
                    label="Expired decision keys",
                    value=str(orchestration_summary.expired_decision_keys),
                    status=(
                        "warning" if orchestration_summary.expired_decision_keys > 0 else "info"
                    ),
                    note="Сводный индикатор свежести без обозревателя истории решений.",
                ),
                OrchestrationAvailabilityItemDTO(
                    key="last_selection_id",
                    label="Last selection id",
                    value=orchestration_summary.last_selection_id or "not surfaced",
                    status=(
                        "normal" if orchestration_summary.last_selection_id is not None else "info"
                    ),
                    note="Последняя surfaced ссылка на opportunity selection для контура оркестрации.",
                ),
                OrchestrationAvailabilityItemDTO(
                    key="last_decision_id",
                    label="Last decision id",
                    value=orchestration_summary.last_decision_id or "not surfaced",
                    status=(
                        "normal" if orchestration_summary.last_decision_id is not None else "info"
                    ),
                    note="Последнее surfaced orchestration decision без отдельного обозревателя.",
                ),
                OrchestrationAvailabilityItemDTO(
                    key="last_event_type",
                    label="Last event type",
                    value=orchestration_summary.last_event_type or "not surfaced",
                    status="normal"
                    if orchestration_summary.last_event_type is not None
                    else "info",
                    note="Последний surfaced orchestration event type.",
                ),
            ],
        )

    def _derive_orchestration_global_status(
        self,
        *,
        started: bool,
        ready: bool,
        lifecycle_state: str,
    ) -> str:
        if not started:
            return "inactive"
        if ready and lifecycle_state == "ready":
            return "ready"
        if lifecycle_state == "degraded":
            return "degraded"
        return "warming"

    def _derive_orchestration_freshness_state(
        self,
        orchestration_summary: OrchestrationSummarySnapshot,
    ) -> str:
        if orchestration_summary.last_decision_id is None:
            return "not_surfaced"
        if orchestration_summary.expired_decision_keys > 0:
            return "expired_decisions_present"
        if orchestration_summary.forwarded_keys > 0:
            return "forwarded_decision_surfaced"
        if orchestration_summary.tracked_decision_keys > 0:
            return "decision_recently_surfaced"
        return "decision_state_surfaced"

    def _build_orchestration_summary_note(
        self,
        orchestration_summary: OrchestrationSummarySnapshot,
    ) -> str:
        if orchestration_summary.degraded_reasons:
            return (
                "Orchestration runtime surfaced degraded reasons: "
                f"{', '.join(orchestration_summary.degraded_reasons)}"
            )
        if orchestration_summary.readiness_reasons:
            return (
                "Orchestration runtime surfaced readiness reasons: "
                f"{', '.join(orchestration_summary.readiness_reasons)}"
            )
        return "Orchestration runtime не surfaced дополнительных notes beyond current diagnostics."

    def _build_orchestration_summary_reason(
        self,
        orchestration_summary: OrchestrationSummarySnapshot,
    ) -> str | None:
        if orchestration_summary.last_failure_reason is not None:
            return orchestration_summary.last_failure_reason
        if orchestration_summary.degraded_reasons:
            return ", ".join(orchestration_summary.degraded_reasons)
        return None

    async def get_position_expansion_summary(self) -> PositionExpansionSummaryDTO:
        """Получить узкий read-only position-expansion summary snapshot."""
        module_availability = (
            await self._composition_root.module_availability_source.get_module_availability()
        )
        if self._composition_root.position_expansion_summary_source is None:
            raise RuntimeError("Position expansion summary source is not configured")
        position_expansion_summary = await self._composition_root.position_expansion_summary_source.get_position_expansion_summary_snapshot()

        position_expansion_module = next(
            (module for module in module_availability if module.key == "position-expansion"),
            None,
        )

        global_status = self._derive_position_expansion_global_status(
            started=position_expansion_summary.started,
            ready=position_expansion_summary.ready,
            lifecycle_state=position_expansion_summary.lifecycle_state,
        )
        summary_note = self._build_position_expansion_summary_note(position_expansion_summary)
        summary_reason = self._build_position_expansion_summary_reason(position_expansion_summary)

        return PositionExpansionSummaryDTO(
            module_status=(
                position_expansion_module.status.value
                if position_expansion_module is not None
                else "inactive"
            ),
            global_status=global_status,
            lifecycle_state=position_expansion_summary.lifecycle_state,
            started=position_expansion_summary.started,
            ready=position_expansion_summary.ready,
            tracked_context_keys=position_expansion_summary.tracked_context_keys,
            tracked_expansion_keys=position_expansion_summary.tracked_expansion_keys,
            expandable_keys=position_expansion_summary.expandable_keys,
            abstained_keys=position_expansion_summary.abstained_keys,
            rejected_keys=position_expansion_summary.rejected_keys,
            invalidated_expansion_keys=position_expansion_summary.invalidated_expansion_keys,
            expired_expansion_keys=position_expansion_summary.expired_expansion_keys,
            last_decision_id=position_expansion_summary.last_decision_id,
            last_expansion_id=position_expansion_summary.last_expansion_id,
            last_event_type=position_expansion_summary.last_event_type,
            active_position_expansion_path=position_expansion_summary.active_position_expansion_path,
            position_expansion_source=position_expansion_summary.position_expansion_source,
            freshness_state=self._derive_position_expansion_freshness_state(
                position_expansion_summary
            ),
            summary_note=summary_note,
            summary_reason=summary_reason,
            availability=[
                PositionExpansionAvailabilityItemDTO(
                    key="runtime_started",
                    label="Position expansion runtime",
                    value="started" if position_expansion_summary.started else "not started",
                    status="normal" if position_expansion_summary.started else "warning",
                    note="Глобальный runtime flag без add-to-position actions.",
                ),
                PositionExpansionAvailabilityItemDTO(
                    key="runtime_ready",
                    label="Readiness",
                    value="ready" if position_expansion_summary.ready else "not ready",
                    status="normal" if position_expansion_summary.ready else "warning",
                    note="Readiness отражает только surfaced diagnostics position-expansion runtime.",
                ),
                PositionExpansionAvailabilityItemDTO(
                    key="tracked_context_keys",
                    label="Tracked context keys",
                    value=str(position_expansion_summary.tracked_context_keys),
                    status="info",
                    note="Количество ключей контекста расширения позиции в текущем runtime snapshot.",
                ),
                PositionExpansionAvailabilityItemDTO(
                    key="tracked_expansion_keys",
                    label="Tracked expansion keys",
                    value=str(position_expansion_summary.tracked_expansion_keys),
                    status="info",
                    note="Суммарный счётчик expansion keys без широкого position browser.",
                ),
                PositionExpansionAvailabilityItemDTO(
                    key="expandable_keys",
                    label="Expandable keys",
                    value=str(position_expansion_summary.expandable_keys),
                    status="normal" if position_expansion_summary.expandable_keys > 0 else "info",
                    note="Показывается только агрегированный счётчик кандидатов на расширение позиции.",
                ),
                PositionExpansionAvailabilityItemDTO(
                    key="abstained_keys",
                    label="Abstained keys",
                    value=str(position_expansion_summary.abstained_keys),
                    status="warning" if position_expansion_summary.abstained_keys > 0 else "info",
                    note="Сводный счётчик воздержавшихся решений без детального обозревателя.",
                ),
                PositionExpansionAvailabilityItemDTO(
                    key="rejected_keys",
                    label="Rejected keys",
                    value=str(position_expansion_summary.rejected_keys),
                    status="warning" if position_expansion_summary.rejected_keys > 0 else "info",
                    note="Сводный счётчик отклонённых кандидатов расширения позиции.",
                ),
                PositionExpansionAvailabilityItemDTO(
                    key="invalidated_expansion_keys",
                    label="Invalidated expansion keys",
                    value=str(position_expansion_summary.invalidated_expansion_keys),
                    status="warning"
                    if position_expansion_summary.invalidated_expansion_keys > 0
                    else "info",
                    note="Показывается как выведенный счётчик без обозревателя деталей.",
                ),
                PositionExpansionAvailabilityItemDTO(
                    key="expired_expansion_keys",
                    label="Expired expansion keys",
                    value=str(position_expansion_summary.expired_expansion_keys),
                    status="warning"
                    if position_expansion_summary.expired_expansion_keys > 0
                    else "info",
                    note="Сводный индикатор свежести без обозревателя истории расширений позиции.",
                ),
                PositionExpansionAvailabilityItemDTO(
                    key="last_decision_id",
                    label="Last decision id",
                    value=position_expansion_summary.last_decision_id or "not surfaced",
                    status="normal"
                    if position_expansion_summary.last_decision_id is not None
                    else "info",
                    note="Последняя surfaced ссылка на решение оркестрации для контура расширения позиции.",
                ),
                PositionExpansionAvailabilityItemDTO(
                    key="last_expansion_id",
                    label="Last expansion id",
                    value=position_expansion_summary.last_expansion_id or "not surfaced",
                    status="normal"
                    if position_expansion_summary.last_expansion_id is not None
                    else "info",
                    note="Последний surfaced expansion id без отдельного обозревателя.",
                ),
                PositionExpansionAvailabilityItemDTO(
                    key="last_event_type",
                    label="Last event type",
                    value=position_expansion_summary.last_event_type or "not surfaced",
                    status="normal"
                    if position_expansion_summary.last_event_type is not None
                    else "info",
                    note="Последний surfaced position-expansion event type.",
                ),
            ],
        )

    def _derive_position_expansion_global_status(
        self,
        *,
        started: bool,
        ready: bool,
        lifecycle_state: str,
    ) -> str:
        if not started:
            return "inactive"
        if ready and lifecycle_state == "ready":
            return "ready"
        if lifecycle_state == "degraded":
            return "degraded"
        return "warming"

    def _derive_position_expansion_freshness_state(
        self,
        position_expansion_summary: PositionExpansionSummarySnapshot,
    ) -> str:
        if position_expansion_summary.last_expansion_id is None:
            return "not_surfaced"
        if position_expansion_summary.expired_expansion_keys > 0:
            return "expired_expansions_present"
        if position_expansion_summary.expandable_keys > 0:
            return "expandable_position_surfaced"
        if position_expansion_summary.tracked_expansion_keys > 0:
            return "expansion_recently_surfaced"
        return "expansion_state_surfaced"

    def _build_position_expansion_summary_note(
        self,
        position_expansion_summary: PositionExpansionSummarySnapshot,
    ) -> str:
        if position_expansion_summary.degraded_reasons:
            return (
                "Position expansion runtime surfaced degraded reasons: "
                f"{', '.join(position_expansion_summary.degraded_reasons)}"
            )
        if position_expansion_summary.readiness_reasons:
            return (
                "Position expansion runtime surfaced readiness reasons: "
                f"{', '.join(position_expansion_summary.readiness_reasons)}"
            )
        return "Position expansion runtime не surfaced дополнительных notes beyond current diagnostics."

    def _build_position_expansion_summary_reason(
        self,
        position_expansion_summary: PositionExpansionSummarySnapshot,
    ) -> str | None:
        if position_expansion_summary.last_failure_reason is not None:
            return position_expansion_summary.last_failure_reason
        if position_expansion_summary.degraded_reasons:
            return ", ".join(position_expansion_summary.degraded_reasons)
        return None

    async def get_oms_summary(self) -> OmsSummaryDTO:
        """Получить узкий read-only OMS summary snapshot."""
        module_availability = (
            await self._composition_root.module_availability_source.get_module_availability()
        )
        oms_summary = await self._composition_root.oms_summary_source.get_oms_summary_snapshot()

        oms_module = next(
            (module for module in module_availability if module.key == "oms"),
            None,
        )

        global_status = self._derive_oms_global_status(
            started=oms_summary.started,
            ready=oms_summary.ready,
            lifecycle_state=oms_summary.lifecycle_state,
        )
        summary_note = self._build_oms_summary_note(oms_summary)
        summary_reason = self._build_oms_summary_reason(oms_summary)

        return OmsSummaryDTO(
            module_status=(oms_module.status.value if oms_module is not None else "inactive"),
            global_status=global_status,
            lifecycle_state=oms_summary.lifecycle_state,
            started=oms_summary.started,
            ready=oms_summary.ready,
            tracked_contexts=oms_summary.tracked_contexts,
            tracked_active_orders=oms_summary.tracked_active_orders,
            tracked_historical_orders=oms_summary.tracked_historical_orders,
            last_intent_id=oms_summary.last_intent_id,
            last_order_id=oms_summary.last_order_id,
            last_event_type=oms_summary.last_event_type,
            active_oms_path=oms_summary.active_oms_path,
            oms_source=oms_summary.oms_source,
            freshness_state=self._derive_oms_freshness_state(oms_summary),
            summary_note=summary_note,
            summary_reason=summary_reason,
            availability=[
                OmsAvailabilityItemDTO(
                    key="runtime_started",
                    label="OMS runtime",
                    value="started" if oms_summary.started else "not started",
                    status="normal" if oms_summary.started else "warning",
                    note="Глобальный runtime flag без действий над ордерами.",
                ),
                OmsAvailabilityItemDTO(
                    key="runtime_ready",
                    label="Readiness",
                    value="ready" if oms_summary.ready else "not ready",
                    status="normal" if oms_summary.ready else "warning",
                    note="Readiness отражает только surfaced diagnostics OMS runtime.",
                ),
                OmsAvailabilityItemDTO(
                    key="tracked_contexts",
                    label="Tracked contexts",
                    value=str(oms_summary.tracked_contexts),
                    status="info",
                    note="Количество OMS context entries в текущем runtime snapshot.",
                ),
                OmsAvailabilityItemDTO(
                    key="tracked_active_orders",
                    label="Tracked active orders",
                    value=str(oms_summary.tracked_active_orders),
                    status=("normal" if oms_summary.tracked_active_orders > 0 else "info"),
                    note="Суммарный счётчик активных ордеров без обозревателя ордеров.",
                ),
                OmsAvailabilityItemDTO(
                    key="tracked_historical_orders",
                    label="Tracked historical orders",
                    value=str(oms_summary.tracked_historical_orders),
                    status=("info" if oms_summary.tracked_historical_orders >= 0 else "warning"),
                    note="Сводный historical counter без браузера истории ордеров.",
                ),
                OmsAvailabilityItemDTO(
                    key="last_intent_id",
                    label="Last intent id",
                    value=oms_summary.last_intent_id or "not surfaced",
                    status="normal" if oms_summary.last_intent_id is not None else "info",
                    note="Последний surfaced execution intent для OMS-контура.",
                ),
                OmsAvailabilityItemDTO(
                    key="last_order_id",
                    label="Last order id",
                    value=oms_summary.last_order_id or "not surfaced",
                    status="normal" if oms_summary.last_order_id is not None else "info",
                    note="Последний surfaced OMS order id без order explorer.",
                ),
            ],
        )

    async def get_manager_summary(self) -> ManagerSummaryDTO:
        """Получить узкий read-only manager summary snapshot."""
        module_availability = (
            await self._composition_root.module_availability_source.get_module_availability()
        )
        manager_summary = (
            await self._composition_root.manager_summary_source.get_manager_summary_snapshot()
        )

        manager_module = next(
            (module for module in module_availability if module.key == "manager"),
            None,
        )

        global_status = self._derive_manager_global_status(
            started=manager_summary.started,
            ready=manager_summary.ready,
            lifecycle_state=manager_summary.lifecycle_state,
        )
        summary_note = self._build_manager_summary_note(manager_summary)
        summary_reason = self._build_manager_summary_reason(manager_summary)

        return ManagerSummaryDTO(
            module_status=(
                manager_module.status.value if manager_module is not None else "inactive"
            ),
            global_status=global_status,
            lifecycle_state=manager_summary.lifecycle_state,
            started=manager_summary.started,
            ready=manager_summary.ready,
            tracked_contexts=manager_summary.tracked_contexts,
            tracked_active_workflows=manager_summary.tracked_active_workflows,
            tracked_historical_workflows=manager_summary.tracked_historical_workflows,
            last_workflow_id=manager_summary.last_workflow_id,
            last_event_type=manager_summary.last_event_type,
            active_manager_path=manager_summary.active_manager_path,
            manager_source=manager_summary.manager_source,
            freshness_state=self._derive_manager_freshness_state(manager_summary),
            summary_note=summary_note,
            summary_reason=summary_reason,
            availability=[
                ManagerAvailabilityItemDTO(
                    key="runtime_started",
                    label="Manager runtime",
                    value="started" if manager_summary.started else "not started",
                    status="normal" if manager_summary.started else "warning",
                    note="Глобальный runtime flag без workflow actions.",
                ),
                ManagerAvailabilityItemDTO(
                    key="runtime_ready",
                    label="Readiness",
                    value="ready" if manager_summary.ready else "not ready",
                    status="normal" if manager_summary.ready else "warning",
                    note="Readiness отражает только surfaced diagnostics manager runtime.",
                ),
                ManagerAvailabilityItemDTO(
                    key="tracked_contexts",
                    label="Tracked contexts",
                    value=str(manager_summary.tracked_contexts),
                    status="info",
                    note="Количество manager context entries в текущем runtime snapshot.",
                ),
                ManagerAvailabilityItemDTO(
                    key="tracked_active_workflows",
                    label="Tracked active workflows",
                    value=str(manager_summary.tracked_active_workflows),
                    status=("normal" if manager_summary.tracked_active_workflows > 0 else "info"),
                    note="Суммарный счётчик активных workflow без workflow browser.",
                ),
                ManagerAvailabilityItemDTO(
                    key="tracked_historical_workflows",
                    label="Tracked historical workflows",
                    value=str(manager_summary.tracked_historical_workflows),
                    status="info",
                    note="Сводный historical counter без браузера workflow history.",
                ),
                ManagerAvailabilityItemDTO(
                    key="last_workflow_id",
                    label="Last workflow id",
                    value=manager_summary.last_workflow_id or "not surfaced",
                    status="normal" if manager_summary.last_workflow_id is not None else "info",
                    note="Последний surfaced workflow id без coordination explorer.",
                ),
                ManagerAvailabilityItemDTO(
                    key="last_event_type",
                    label="Last event type",
                    value=manager_summary.last_event_type or "not surfaced",
                    status="normal" if manager_summary.last_event_type is not None else "info",
                    note="Последний surfaced manager event type.",
                ),
            ],
        )

    async def get_validation_summary(self) -> ValidationSummaryDTO:
        """Получить узкий read-only validation summary snapshot."""
        module_availability = (
            await self._composition_root.module_availability_source.get_module_availability()
        )
        validation_summary = (
            await self._composition_root.validation_summary_source.get_validation_summary_snapshot()
        )

        validation_module = next(
            (module for module in module_availability if module.key == "validation"),
            None,
        )

        global_status = self._derive_validation_global_status(
            started=validation_summary.started,
            ready=validation_summary.ready,
            lifecycle_state=validation_summary.lifecycle_state,
        )
        summary_note = self._build_validation_summary_note(validation_summary)
        summary_reason = self._build_validation_summary_reason(validation_summary)

        return ValidationSummaryDTO(
            module_status=(
                validation_module.status.value if validation_module is not None else "inactive"
            ),
            global_status=global_status,
            lifecycle_state=validation_summary.lifecycle_state,
            started=validation_summary.started,
            ready=validation_summary.ready,
            tracked_contexts=validation_summary.tracked_contexts,
            tracked_active_reviews=validation_summary.tracked_active_reviews,
            tracked_historical_reviews=validation_summary.tracked_historical_reviews,
            last_review_id=validation_summary.last_review_id,
            last_event_type=validation_summary.last_event_type,
            active_validation_path=validation_summary.active_validation_path,
            validation_source=validation_summary.validation_source,
            freshness_state=self._derive_validation_freshness_state(validation_summary),
            summary_note=summary_note,
            summary_reason=summary_reason,
            availability=[
                ValidationAvailabilityItemDTO(
                    key="runtime_started",
                    label="Validation runtime",
                    value="started" if validation_summary.started else "not started",
                    status="normal" if validation_summary.started else "warning",
                    note="Глобальный runtime flag без review actions.",
                ),
                ValidationAvailabilityItemDTO(
                    key="runtime_ready",
                    label="Readiness",
                    value="ready" if validation_summary.ready else "not ready",
                    status="normal" if validation_summary.ready else "warning",
                    note="Readiness отражает только surfaced diagnostics validation runtime.",
                ),
                ValidationAvailabilityItemDTO(
                    key="tracked_contexts",
                    label="Tracked contexts",
                    value=str(validation_summary.tracked_contexts),
                    status="info",
                    note="Количество validation context entries в текущем runtime snapshot.",
                ),
                ValidationAvailabilityItemDTO(
                    key="tracked_active_reviews",
                    label="Tracked active reviews",
                    value=str(validation_summary.tracked_active_reviews),
                    status=("normal" if validation_summary.tracked_active_reviews > 0 else "info"),
                    note="Суммарный счётчик активных review без review browser.",
                ),
                ValidationAvailabilityItemDTO(
                    key="tracked_historical_reviews",
                    label="Tracked historical reviews",
                    value=str(validation_summary.tracked_historical_reviews),
                    status="info",
                    note="Сводный historical counter без браузера review history.",
                ),
                ValidationAvailabilityItemDTO(
                    key="last_review_id",
                    label="Last review id",
                    value=validation_summary.last_review_id or "not surfaced",
                    status="normal" if validation_summary.last_review_id is not None else "info",
                    note="Последний surfaced review id без review explorer.",
                ),
                ValidationAvailabilityItemDTO(
                    key="last_event_type",
                    label="Last event type",
                    value=validation_summary.last_event_type or "not surfaced",
                    status="normal" if validation_summary.last_event_type is not None else "info",
                    note="Последний surfaced validation event type.",
                ),
            ],
        )

    async def _get_health_snapshot(
        self,
        components: dict[str, ComponentHealth],
    ) -> SystemHealth:
        source = self._composition_root.health_snapshot_source
        if source is not None:
            health = await source.get_health_snapshot()
            if health is not None:
                return health

        return self._build_health_from_components(components)

    def _build_health_from_components(
        self,
        components: dict[str, ComponentHealth],
    ) -> SystemHealth:
        if not components:
            overall_status = HealthStatus.UNKNOWN
        else:
            statuses = {item.status for item in components.values()}
            if HealthStatus.UNHEALTHY in statuses:
                overall_status = HealthStatus.UNHEALTHY
            elif HealthStatus.DEGRADED in statuses or HealthStatus.UNKNOWN in statuses:
                overall_status = HealthStatus.DEGRADED
            else:
                overall_status = HealthStatus.HEALTHY

        logger.debug(
            "Построен fallback health snapshot для overview",
            components=len(components),
            overall_status=overall_status.value,
        )
        return SystemHealth(overall_status=overall_status, components=components)

    def _derive_risk_status(
        self,
        *,
        trade_allowed: bool,
        risk_multiplier: float,
        allow_new_positions: bool,
    ) -> tuple[str, str]:
        if not trade_allowed or risk_multiplier <= 0:
            return "blocked", "trading-blocked"
        if risk_multiplier < 1 or not allow_new_positions:
            return "limited", "risk-limited"
        return "normal", "within-envelope"

    def _derive_signals_global_status(
        self,
        *,
        started: bool,
        ready: bool,
        lifecycle_state: str,
    ) -> str:
        if not started:
            return "inactive"
        if ready and lifecycle_state == "ready":
            return "ready"
        if lifecycle_state == "degraded":
            return "degraded"
        return "warming"

    def _derive_signal_freshness_state(self, signal_summary: SignalSummarySnapshot) -> str:
        if signal_summary.last_context_at is None:
            return "not_surfaced"
        if signal_summary.expired_signal_keys > 0:
            return "expired_signals_present"
        return "context_recently_surfaced"

    def _build_signal_summary_note(self, signal_summary: SignalSummarySnapshot) -> str:
        if signal_summary.degraded_reasons:
            return (
                "Signal runtime surfaced degraded reasons: "
                f"{', '.join(signal_summary.degraded_reasons)}"
            )
        if signal_summary.readiness_reasons:
            return (
                "Signal runtime surfaced readiness reasons: "
                f"{', '.join(signal_summary.readiness_reasons)}"
            )
        return "Signal runtime не surfaced дополнительных notes beyond current diagnostics."

    def _build_signal_summary_reason(
        self,
        signal_summary: SignalSummarySnapshot,
    ) -> str | None:
        if signal_summary.last_failure_reason is not None:
            return signal_summary.last_failure_reason
        if signal_summary.degraded_reasons:
            return ", ".join(signal_summary.degraded_reasons)
        return None

    def _derive_strategy_global_status(
        self,
        *,
        started: bool,
        ready: bool,
        lifecycle_state: str,
    ) -> str:
        if not started:
            return "inactive"
        if ready and lifecycle_state == "ready":
            return "ready"
        if lifecycle_state == "degraded":
            return "degraded"
        return "warming"

    def _derive_strategy_freshness_state(
        self,
        strategy_summary: StrategySummarySnapshot,
    ) -> str:
        if strategy_summary.last_candidate_id is None:
            return "not_surfaced"
        if strategy_summary.expired_candidate_keys > 0:
            return "expired_candidates_present"
        if strategy_summary.actionable_candidate_keys > 0:
            return "actionable_candidate_surfaced"
        return "candidate_recently_surfaced"

    def _build_strategy_summary_note(
        self,
        strategy_summary: StrategySummarySnapshot,
    ) -> str:
        if strategy_summary.degraded_reasons:
            return (
                "Strategy runtime surfaced degraded reasons: "
                f"{', '.join(strategy_summary.degraded_reasons)}"
            )
        if strategy_summary.readiness_reasons:
            return (
                "Strategy runtime surfaced readiness reasons: "
                f"{', '.join(strategy_summary.readiness_reasons)}"
            )
        return "Strategy runtime не surfaced дополнительных notes beyond current diagnostics."

    def _build_strategy_summary_reason(
        self,
        strategy_summary: StrategySummarySnapshot,
    ) -> str | None:
        if strategy_summary.last_failure_reason is not None:
            return strategy_summary.last_failure_reason
        if strategy_summary.degraded_reasons:
            return ", ".join(strategy_summary.degraded_reasons)
        return None

    def _derive_execution_global_status(
        self,
        *,
        started: bool,
        ready: bool,
        lifecycle_state: str,
    ) -> str:
        if not started:
            return "inactive"
        if ready and lifecycle_state == "ready":
            return "ready"
        if lifecycle_state == "degraded":
            return "degraded"
        return "warming"

    def _derive_execution_freshness_state(
        self,
        execution_summary: ExecutionSummarySnapshot,
    ) -> str:
        if execution_summary.last_intent_id is None:
            return "not_surfaced"
        if execution_summary.expired_intent_keys > 0:
            return "expired_intents_present"
        if execution_summary.executable_intent_keys > 0:
            return "executable_intent_surfaced"
        return "intent_recently_surfaced"

    def _build_execution_summary_note(
        self,
        execution_summary: ExecutionSummarySnapshot,
    ) -> str:
        if execution_summary.degraded_reasons:
            return (
                "Execution runtime surfaced degraded reasons: "
                f"{', '.join(execution_summary.degraded_reasons)}"
            )
        if execution_summary.readiness_reasons:
            return (
                "Execution runtime surfaced readiness reasons: "
                f"{', '.join(execution_summary.readiness_reasons)}"
            )
        return "Execution runtime не surfaced дополнительных notes beyond current diagnostics."

    def _build_execution_summary_reason(
        self,
        execution_summary: ExecutionSummarySnapshot,
    ) -> str | None:
        if execution_summary.last_failure_reason is not None:
            return execution_summary.last_failure_reason
        if execution_summary.degraded_reasons:
            return ", ".join(execution_summary.degraded_reasons)
        return None

    def _derive_oms_global_status(
        self,
        *,
        started: bool,
        ready: bool,
        lifecycle_state: str,
    ) -> str:
        if not started:
            return "inactive"
        if ready and lifecycle_state == "ready":
            return "ready"
        if lifecycle_state == "degraded":
            return "degraded"
        return "warming"

    def _derive_oms_freshness_state(
        self,
        oms_summary: OmsSummarySnapshot,
    ) -> str:
        if oms_summary.last_order_id is None:
            return "not_surfaced"
        if oms_summary.tracked_active_orders > 0:
            return "active_order_surfaced"
        if oms_summary.tracked_historical_orders > 0:
            return "historical_order_surfaced"
        return "order_recently_surfaced"

    def _build_oms_summary_note(
        self,
        oms_summary: OmsSummarySnapshot,
    ) -> str:
        if oms_summary.degraded_reasons:
            return (
                f"OMS runtime surfaced degraded reasons: {', '.join(oms_summary.degraded_reasons)}"
            )
        if oms_summary.readiness_reasons:
            return f"OMS runtime surfaced readiness reasons: {', '.join(oms_summary.readiness_reasons)}"
        return "OMS runtime не surfaced дополнительных notes beyond current diagnostics."

    def _build_oms_summary_reason(
        self,
        oms_summary: OmsSummarySnapshot,
    ) -> str | None:
        if oms_summary.last_failure_reason is not None:
            return oms_summary.last_failure_reason
        if oms_summary.degraded_reasons:
            return ", ".join(oms_summary.degraded_reasons)
        return None

    def _derive_manager_global_status(
        self,
        *,
        started: bool,
        ready: bool,
        lifecycle_state: str,
    ) -> str:
        if not started:
            return "inactive"
        if ready and lifecycle_state == "ready":
            return "ready"
        if lifecycle_state == "degraded":
            return "degraded"
        return "warming"

    def _derive_manager_freshness_state(
        self,
        manager_summary: ManagerSummarySnapshot,
    ) -> str:
        if manager_summary.last_workflow_id is None:
            return "not_surfaced"
        if manager_summary.tracked_active_workflows > 0:
            return "active_workflow_surfaced"
        if manager_summary.tracked_historical_workflows > 0:
            return "historical_workflow_surfaced"
        return "workflow_recently_surfaced"

    def _build_manager_summary_note(
        self,
        manager_summary: ManagerSummarySnapshot,
    ) -> str:
        if manager_summary.degraded_reasons:
            return (
                "Manager runtime surfaced degraded reasons: "
                f"{', '.join(manager_summary.degraded_reasons)}"
            )
        if manager_summary.readiness_reasons:
            return (
                "Manager runtime surfaced readiness reasons: "
                f"{', '.join(manager_summary.readiness_reasons)}"
            )
        return "Manager runtime не surfaced дополнительных notes beyond current diagnostics."

    def _build_manager_summary_reason(
        self,
        manager_summary: ManagerSummarySnapshot,
    ) -> str | None:
        if manager_summary.last_failure_reason is not None:
            return manager_summary.last_failure_reason
        if manager_summary.degraded_reasons:
            return ", ".join(manager_summary.degraded_reasons)
        return None

    def _derive_validation_global_status(
        self,
        *,
        started: bool,
        ready: bool,
        lifecycle_state: str,
    ) -> str:
        if not started:
            return "inactive"
        if ready and lifecycle_state == "ready":
            return "ready"
        if lifecycle_state == "degraded":
            return "degraded"
        return "warming"

    def _derive_validation_freshness_state(
        self,
        validation_summary: ValidationSummarySnapshot,
    ) -> str:
        if validation_summary.last_review_id is None:
            return "not_surfaced"
        if validation_summary.tracked_active_reviews > 0:
            return "active_review_surfaced"
        if validation_summary.tracked_historical_reviews > 0:
            return "historical_review_surfaced"
        return "review_recently_surfaced"

    def _build_validation_summary_note(
        self,
        validation_summary: ValidationSummarySnapshot,
    ) -> str:
        if validation_summary.degraded_reasons:
            return (
                "Validation runtime surfaced degraded reasons: "
                f"{', '.join(validation_summary.degraded_reasons)}"
            )
        if validation_summary.readiness_reasons:
            return (
                "Validation runtime surfaced readiness reasons: "
                f"{', '.join(validation_summary.readiness_reasons)}"
            )
        return "Validation runtime не surfaced дополнительных notes beyond current diagnostics."

    def _build_validation_summary_reason(
        self,
        validation_summary: ValidationSummarySnapshot,
    ) -> str | None:
        if validation_summary.last_failure_reason is not None:
            return validation_summary.last_failure_reason
        if validation_summary.degraded_reasons:
            return ", ".join(validation_summary.degraded_reasons)
        return None

    async def get_paper_summary(self) -> PaperSummaryDTO:
        """Получить узкий read-only paper summary snapshot."""
        module_availability = (
            await self._composition_root.module_availability_source.get_module_availability()
        )
        paper_summary = (
            await self._composition_root.paper_summary_source.get_paper_summary_snapshot()
        )

        paper_module = next(
            (module for module in module_availability if module.key == "paper"),
            None,
        )

        global_status = self._derive_paper_global_status(
            started=paper_summary.started,
            ready=paper_summary.ready,
            lifecycle_state=paper_summary.lifecycle_state,
        )
        summary_note = self._build_paper_summary_note(paper_summary)
        summary_reason = self._build_paper_summary_reason(paper_summary)

        return PaperSummaryDTO(
            module_status=(paper_module.status.value if paper_module is not None else "inactive"),
            global_status=global_status,
            lifecycle_state=paper_summary.lifecycle_state,
            started=paper_summary.started,
            ready=paper_summary.ready,
            tracked_contexts=paper_summary.tracked_contexts,
            tracked_active_rehearsals=paper_summary.tracked_active_rehearsals,
            tracked_historical_rehearsals=paper_summary.tracked_historical_rehearsals,
            last_rehearsal_id=paper_summary.last_rehearsal_id,
            last_event_type=paper_summary.last_event_type,
            active_paper_path=paper_summary.active_paper_path,
            paper_source=paper_summary.paper_source,
            freshness_state=self._derive_paper_freshness_state(paper_summary),
            summary_note=summary_note,
            summary_reason=summary_reason,
            availability=[
                PaperAvailabilityItemDTO(
                    key="runtime_started",
                    label="Paper runtime",
                    value="started" if paper_summary.started else "not started",
                    status="normal" if paper_summary.started else "warning",
                    note="Глобальный runtime flag без paper actions.",
                ),
                PaperAvailabilityItemDTO(
                    key="runtime_ready",
                    label="Readiness",
                    value="ready" if paper_summary.ready else "not ready",
                    status="normal" if paper_summary.ready else "warning",
                    note="Readiness отражает только surfaced diagnostics paper runtime.",
                ),
                PaperAvailabilityItemDTO(
                    key="tracked_contexts",
                    label="Tracked contexts",
                    value=str(paper_summary.tracked_contexts),
                    status="info",
                    note="Количество paper context entries в текущем runtime snapshot.",
                ),
                PaperAvailabilityItemDTO(
                    key="tracked_active_rehearsals",
                    label="Tracked active rehearsals",
                    value=str(paper_summary.tracked_active_rehearsals),
                    status=("normal" if paper_summary.tracked_active_rehearsals > 0 else "info"),
                    note="Суммарный счётчик активных rehearsal без rehearsal browser.",
                ),
                PaperAvailabilityItemDTO(
                    key="tracked_historical_rehearsals",
                    label="Tracked historical rehearsals",
                    value=str(paper_summary.tracked_historical_rehearsals),
                    status="info",
                    note="Сводный historical counter без браузера rehearsal history.",
                ),
                PaperAvailabilityItemDTO(
                    key="last_rehearsal_id",
                    label="Last rehearsal id",
                    value=paper_summary.last_rehearsal_id or "not surfaced",
                    status="normal" if paper_summary.last_rehearsal_id is not None else "info",
                    note="Последний surfaced rehearsal id без rehearsal explorer.",
                ),
                PaperAvailabilityItemDTO(
                    key="last_event_type",
                    label="Last event type",
                    value=paper_summary.last_event_type or "not surfaced",
                    status="normal" if paper_summary.last_event_type is not None else "info",
                    note="Последний surfaced paper event type.",
                ),
            ],
        )

    def _derive_paper_global_status(
        self,
        *,
        started: bool,
        ready: bool,
        lifecycle_state: str,
    ) -> str:
        if not started:
            return "inactive"
        if ready and lifecycle_state == "ready":
            return "ready"
        if lifecycle_state == "degraded":
            return "degraded"
        return "warming"

    def _derive_paper_freshness_state(self, paper_summary: PaperSummarySnapshot) -> str:
        if paper_summary.last_rehearsal_id is None:
            return "not_surfaced"
        if paper_summary.tracked_active_rehearsals > 0:
            return "active_rehearsal_surfaced"
        if paper_summary.tracked_historical_rehearsals > 0:
            return "historical_rehearsal_surfaced"
        return "rehearsal_recently_surfaced"

    def _build_paper_summary_note(
        self,
        paper_summary: PaperSummarySnapshot,
    ) -> str:
        if paper_summary.degraded_reasons:
            return (
                "Paper runtime surfaced degraded reasons: "
                f"{', '.join(paper_summary.degraded_reasons)}"
            )
        if paper_summary.readiness_reasons:
            return (
                "Paper runtime surfaced readiness reasons: "
                f"{', '.join(paper_summary.readiness_reasons)}"
            )
        return "Paper runtime не surfaced дополнительных notes beyond current diagnostics."

    def _build_paper_summary_reason(
        self,
        paper_summary: PaperSummarySnapshot,
    ) -> str | None:
        if paper_summary.last_failure_reason is not None:
            return paper_summary.last_failure_reason
        if paper_summary.degraded_reasons:
            return ", ".join(paper_summary.degraded_reasons)
        return None

    async def get_backtest_summary(self) -> BacktestSummaryDTO:
        """Получить узкий read-only backtest summary snapshot."""
        module_availability = (
            await self._composition_root.module_availability_source.get_module_availability()
        )
        if self._composition_root.backtest_summary_source is None:
            raise RuntimeError("Backtest summary source не подключён в composition root")
        backtest_summary = (
            await self._composition_root.backtest_summary_source.get_backtest_summary_snapshot()
        )

        backtest_module = next(
            (module for module in module_availability if module.key == "backtest"),
            None,
        )

        global_status = self._derive_backtest_global_status(
            started=backtest_summary.started,
            ready=backtest_summary.ready,
            lifecycle_state=backtest_summary.lifecycle_state,
        )
        summary_note = self._build_backtest_summary_note(backtest_summary)
        summary_reason = self._build_backtest_summary_reason(backtest_summary)

        return BacktestSummaryDTO(
            module_status=(
                backtest_module.status.value if backtest_module is not None else "inactive"
            ),
            global_status=global_status,
            lifecycle_state=backtest_summary.lifecycle_state,
            started=backtest_summary.started,
            ready=backtest_summary.ready,
            tracked_inputs=backtest_summary.tracked_inputs,
            tracked_contexts=backtest_summary.tracked_contexts,
            tracked_active_replays=backtest_summary.tracked_active_replays,
            tracked_historical_replays=backtest_summary.tracked_historical_replays,
            last_replay_id=backtest_summary.last_replay_id,
            last_event_type=backtest_summary.last_event_type,
            active_backtest_path=backtest_summary.active_backtest_path,
            backtest_source=backtest_summary.backtest_source,
            freshness_state=self._derive_backtest_freshness_state(backtest_summary),
            summary_note=summary_note,
            summary_reason=summary_reason,
            availability=[
                BacktestAvailabilityItemDTO(
                    key="runtime_started",
                    label="Backtest runtime",
                    value="started" if backtest_summary.started else "not started",
                    status="normal" if backtest_summary.started else "warning",
                    note="Глобальный runtime flag без manual replay controls.",
                ),
                BacktestAvailabilityItemDTO(
                    key="runtime_ready",
                    label="Readiness",
                    value="ready" if backtest_summary.ready else "not ready",
                    status="normal" if backtest_summary.ready else "warning",
                    note="Readiness отражает только surfaced diagnostics backtest runtime.",
                ),
                BacktestAvailabilityItemDTO(
                    key="tracked_inputs",
                    label="Tracked inputs",
                    value=str(backtest_summary.tracked_inputs),
                    status="info",
                    note="Количество historical inputs в текущем runtime snapshot.",
                ),
                BacktestAvailabilityItemDTO(
                    key="tracked_contexts",
                    label="Tracked contexts",
                    value=str(backtest_summary.tracked_contexts),
                    status="info",
                    note="Количество backtest contexts в текущем runtime snapshot.",
                ),
                BacktestAvailabilityItemDTO(
                    key="tracked_active_replays",
                    label="Tracked active replays",
                    value=str(backtest_summary.tracked_active_replays),
                    status=("normal" if backtest_summary.tracked_active_replays > 0 else "info"),
                    note="Суммарный счётчик активных replay-контуров без replay controls.",
                ),
                BacktestAvailabilityItemDTO(
                    key="tracked_historical_replays",
                    label="Tracked historical replays",
                    value=str(backtest_summary.tracked_historical_replays),
                    status="info",
                    note="Сводный historical counter без replay history browser.",
                ),
                BacktestAvailabilityItemDTO(
                    key="last_replay_id",
                    label="Last replay id",
                    value=backtest_summary.last_replay_id or "not surfaced",
                    status="normal" if backtest_summary.last_replay_id is not None else "info",
                    note="Последний surfaced replay id без replay explorer.",
                ),
                BacktestAvailabilityItemDTO(
                    key="last_event_type",
                    label="Last event type",
                    value=backtest_summary.last_event_type or "not surfaced",
                    status="normal" if backtest_summary.last_event_type is not None else "info",
                    note="Последний surfaced backtest event type.",
                ),
            ],
        )

    def _derive_backtest_global_status(
        self,
        *,
        started: bool,
        ready: bool,
        lifecycle_state: str,
    ) -> str:
        if not started:
            return "inactive"
        if ready and lifecycle_state == "ready":
            return "ready"
        if lifecycle_state == "degraded":
            return "degraded"
        return "warming"

    def _derive_backtest_freshness_state(
        self,
        backtest_summary: BacktestSummarySnapshot,
    ) -> str:
        if backtest_summary.last_replay_id is None:
            return "not_surfaced"
        if backtest_summary.tracked_active_replays > 0:
            return "active_replay_surfaced"
        if backtest_summary.tracked_historical_replays > 0:
            return "historical_replay_surfaced"
        return "replay_recently_surfaced"

    def _build_backtest_summary_note(
        self,
        backtest_summary: BacktestSummarySnapshot,
    ) -> str:
        if backtest_summary.degraded_reasons:
            return (
                "Backtest runtime surfaced degraded reasons: "
                f"{', '.join(backtest_summary.degraded_reasons)}"
            )
        if backtest_summary.readiness_reasons:
            return (
                "Backtest runtime surfaced readiness reasons: "
                f"{', '.join(backtest_summary.readiness_reasons)}"
            )
        return "Backtest runtime не surfaced дополнительных notes beyond current diagnostics."

    def _build_backtest_summary_reason(
        self,
        backtest_summary: BacktestSummarySnapshot,
    ) -> str | None:
        if backtest_summary.last_failure_reason is not None:
            return backtest_summary.last_failure_reason
        if backtest_summary.degraded_reasons:
            return ", ".join(backtest_summary.degraded_reasons)
        return None

    async def get_portfolio_governor_summary(self) -> PortfolioGovernorSummaryDTO:
        """Получить узкий read-only portfolio-governor summary snapshot."""
        module_availability = (
            await self._composition_root.module_availability_source.get_module_availability()
        )
        if self._composition_root.portfolio_governor_summary_source is None:
            raise RuntimeError("Portfolio governor summary source не подключён в composition root")
        governor_summary = await self._composition_root.portfolio_governor_summary_source.get_portfolio_governor_summary_snapshot()

        governor_module = next(
            (module for module in module_availability if module.key == "portfolio-governor"),
            None,
        )

        global_status = self._derive_portfolio_governor_global_status(
            started=governor_summary.started,
            ready=governor_summary.ready,
            lifecycle_state=governor_summary.lifecycle_state,
        )
        summary_note = self._build_portfolio_governor_summary_note(governor_summary)
        summary_reason = self._build_portfolio_governor_summary_reason(governor_summary)

        return PortfolioGovernorSummaryDTO(
            module_status=(
                governor_module.status.value if governor_module is not None else "inactive"
            ),
            global_status=global_status,
            lifecycle_state=governor_summary.lifecycle_state,
            started=governor_summary.started,
            ready=governor_summary.ready,
            tracked_context_keys=governor_summary.tracked_context_keys,
            tracked_governor_keys=governor_summary.tracked_governor_keys,
            approved_keys=governor_summary.approved_keys,
            abstained_keys=governor_summary.abstained_keys,
            rejected_keys=governor_summary.rejected_keys,
            invalidated_governor_keys=governor_summary.invalidated_governor_keys,
            expired_governor_keys=governor_summary.expired_governor_keys,
            last_expansion_id=governor_summary.last_expansion_id,
            last_governor_id=governor_summary.last_governor_id,
            last_event_type=governor_summary.last_event_type,
            active_portfolio_governor_path=governor_summary.active_portfolio_governor_path,
            portfolio_governor_source=governor_summary.portfolio_governor_source,
            freshness_state=self._derive_portfolio_governor_freshness_state(governor_summary),
            summary_note=summary_note,
            summary_reason=summary_reason,
            availability=[
                PortfolioGovernorAvailabilityItemDTO(
                    key="runtime_started",
                    label="Portfolio governor runtime",
                    value="started" if governor_summary.started else "not started",
                    status="normal" if governor_summary.started else "warning",
                    note="Глобальный runtime flag без allocation actions.",
                ),
                PortfolioGovernorAvailabilityItemDTO(
                    key="runtime_ready",
                    label="Readiness",
                    value="ready" if governor_summary.ready else "not ready",
                    status="normal" if governor_summary.ready else "warning",
                    note="Readiness отражает только surfaced diagnostics portfolio governor runtime.",
                ),
                PortfolioGovernorAvailabilityItemDTO(
                    key="tracked_context_keys",
                    label="Tracked context keys",
                    value=str(governor_summary.tracked_context_keys),
                    status="info",
                    note="Количество governor context keys в текущем runtime snapshot.",
                ),
                PortfolioGovernorAvailabilityItemDTO(
                    key="tracked_governor_keys",
                    label="Tracked governor keys",
                    value=str(governor_summary.tracked_governor_keys),
                    status="info",
                    note="Суммарный счётчик governor candidates без capital governance browser.",
                ),
                PortfolioGovernorAvailabilityItemDTO(
                    key="approved_keys",
                    label="Approved keys",
                    value=str(governor_summary.approved_keys),
                    status="normal" if governor_summary.approved_keys > 0 else "info",
                    note="Показывается только агрегированный счётчик одобренных решений без allocation actions.",
                ),
                PortfolioGovernorAvailabilityItemDTO(
                    key="abstained_keys",
                    label="Abstained keys",
                    value=str(governor_summary.abstained_keys),
                    status="info",
                    note="Сводный счётчик воздержавшихся решений без governance overrides.",
                ),
                PortfolioGovernorAvailabilityItemDTO(
                    key="rejected_keys",
                    label="Rejected keys",
                    value=str(governor_summary.rejected_keys),
                    status="warning" if governor_summary.rejected_keys > 0 else "info",
                    note="Сводный счётчик отклонённых governor-кандидатов без обозревателя деталей.",
                ),
                PortfolioGovernorAvailabilityItemDTO(
                    key="invalidated_governor_keys",
                    label="Invalidated governor keys",
                    value=str(governor_summary.invalidated_governor_keys),
                    status="warning" if governor_summary.invalidated_governor_keys > 0 else "info",
                    note="Показывается как surfaced counter без browser исторических изменений.",
                ),
                PortfolioGovernorAvailabilityItemDTO(
                    key="expired_governor_keys",
                    label="Expired governor keys",
                    value=str(governor_summary.expired_governor_keys),
                    status="warning" if governor_summary.expired_governor_keys > 0 else "info",
                    note="Сводный индикатор свежести без live mutation controls.",
                ),
                PortfolioGovernorAvailabilityItemDTO(
                    key="last_expansion_id",
                    label="Last expansion id",
                    value=governor_summary.last_expansion_id or "not surfaced",
                    status="normal" if governor_summary.last_expansion_id is not None else "info",
                    note="Последняя surfaced ссылка на расширение позиции без связанного обозревателя.",
                ),
                PortfolioGovernorAvailabilityItemDTO(
                    key="last_governor_id",
                    label="Last governor id",
                    value=governor_summary.last_governor_id or "not surfaced",
                    status="normal" if governor_summary.last_governor_id is not None else "info",
                    note="Последний surfaced governor id без отдельного browser слоя.",
                ),
                PortfolioGovernorAvailabilityItemDTO(
                    key="last_event_type",
                    label="Last event type",
                    value=governor_summary.last_event_type or "not surfaced",
                    status="normal" if governor_summary.last_event_type is not None else "info",
                    note="Последний surfaced portfolio governor event type.",
                ),
            ],
        )

    def _derive_portfolio_governor_global_status(
        self,
        *,
        started: bool,
        ready: bool,
        lifecycle_state: str,
    ) -> str:
        if not started:
            return "inactive"
        if ready and lifecycle_state == "ready":
            return "ready"
        if lifecycle_state == "degraded":
            return "degraded"
        return "warming"

    def _derive_portfolio_governor_freshness_state(
        self,
        governor_summary: PortfolioGovernorSummarySnapshot,
    ) -> str:
        if governor_summary.last_governor_id is None:
            return "not_surfaced"
        if governor_summary.approved_keys > 0:
            return "approved_governor_surfaced"
        if governor_summary.invalidated_governor_keys > 0:
            return "invalidated_governor_present"
        if governor_summary.expired_governor_keys > 0:
            return "expired_governor_present"
        return "governor_recently_surfaced"

    def _build_portfolio_governor_summary_note(
        self,
        governor_summary: PortfolioGovernorSummarySnapshot,
    ) -> str:
        if governor_summary.degraded_reasons:
            return (
                "Portfolio governor runtime surfaced degraded reasons: "
                f"{', '.join(governor_summary.degraded_reasons)}"
            )
        if governor_summary.readiness_reasons:
            return (
                "Portfolio governor runtime surfaced readiness reasons: "
                f"{', '.join(governor_summary.readiness_reasons)}"
            )
        return "Portfolio governor runtime не surfaced дополнительных notes beyond current diagnostics."

    def _build_portfolio_governor_summary_reason(
        self,
        governor_summary: PortfolioGovernorSummarySnapshot,
    ) -> str | None:
        if governor_summary.last_failure_reason is not None:
            return governor_summary.last_failure_reason
        if governor_summary.degraded_reasons:
            return ", ".join(governor_summary.degraded_reasons)
        return None

    async def get_reporting_summary(self) -> ReportingSummaryDTO:
        """Получить узкий read-only reporting artifact catalog summary snapshot."""
        module_availability = (
            await self._composition_root.module_availability_source.get_module_availability()
        )
        if self._composition_root.reporting_summary_source is None:
            raise RuntimeError("Reporting summary source не подключён в composition root")
        reporting_summary = (
            await self._composition_root.reporting_summary_source.get_reporting_summary_snapshot()
        )

        reporting_module = next(
            (module for module in module_availability if module.key == "reporting"),
            None,
        )

        return ReportingSummaryDTO(
            module_status=(
                reporting_module.status.value if reporting_module is not None else "inactive"
            ),
            global_status=self._derive_reporting_global_status(reporting_summary),
            catalog_counts=ReportingCatalogCountsDTO(
                total_artifacts=reporting_summary.catalog_counts.total_artifacts,
                total_bundles=reporting_summary.catalog_counts.total_bundles,
                validation_artifacts=reporting_summary.catalog_counts.validation_artifacts,
                paper_artifacts=reporting_summary.catalog_counts.paper_artifacts,
                replay_artifacts=reporting_summary.catalog_counts.replay_artifacts,
            ),
            last_artifact_snapshot=(
                ReportingLastArtifactDTO(
                    kind=reporting_summary.last_artifact_snapshot.kind,
                    status=reporting_summary.last_artifact_snapshot.status,
                    source_layer=reporting_summary.last_artifact_snapshot.source_layer,
                    generated_at=reporting_summary.last_artifact_snapshot.generated_at.isoformat(),
                )
                if reporting_summary.last_artifact_snapshot is not None
                else None
            ),
            last_bundle_snapshot=(
                ReportingLastBundleDTO(
                    reporting_name=reporting_summary.last_bundle_snapshot.reporting_name,
                    generated_at=reporting_summary.last_bundle_snapshot.generated_at.isoformat(),
                    artifact_count=reporting_summary.last_bundle_snapshot.artifact_count,
                )
                if reporting_summary.last_bundle_snapshot is not None
                else None
            ),
            summary_note=self._build_reporting_summary_note(reporting_summary),
            summary_reason=self._build_reporting_summary_reason(reporting_summary),
        )

    def _derive_reporting_global_status(
        self,
        reporting_summary: ReportingSummarySnapshot,
    ) -> str:
        if reporting_summary.catalog_counts.total_artifacts == 0:
            return "inactive"
        if reporting_summary.catalog_counts.total_bundles > 0:
            return "ready"
        return "warming"

    def _build_reporting_summary_note(
        self,
        reporting_summary: ReportingSummarySnapshot,
    ) -> str:
        counts = reporting_summary.catalog_counts
        surfaced_layers = [
            layer
            for layer, count in (
                ("validation", counts.validation_artifacts),
                ("paper", counts.paper_artifacts),
                ("replay", counts.replay_artifacts),
            )
            if count > 0
        ]

        if counts.total_artifacts == 0:
            return (
                "Каталог reporting artifacts пока не вывел ни одного surfaced artifact или bundle."
            )
        if counts.total_bundles > 0:
            return (
                "Каталог reporting artifacts уже вывел как минимум один bundle и остаётся "
                "read-only summary surface без delivery или export semantics."
            )
        if surfaced_layers:
            return (
                "Каталог reporting artifacts уже вывел отдельные artifacts по слоям "
                f"{', '.join(surfaced_layers)}, но bundle truth ещё не surfaced."
            )
        return "Каталог reporting artifacts остаётся в промежуточном surfaced состоянии."

    def _build_reporting_summary_reason(
        self,
        reporting_summary: ReportingSummarySnapshot,
    ) -> str | None:
        if reporting_summary.last_artifact_snapshot is None:
            return None
        return reporting_summary.last_artifact_snapshot.source_reason_code

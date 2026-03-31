"""FastAPI router для read-only dashboard snapshot endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException

from cryptotechnolog.config import get_logger, get_settings, update_settings

from ..dto.backtest import BacktestSummaryDTO
from ..dto.execution import ExecutionSummaryDTO
from ..dto.manager import ManagerSummaryDTO
from ..dto.oms import OmsSummaryDTO
from ..dto.opportunity import OpportunitySummaryDTO
from ..dto.orchestration import OrchestrationSummaryDTO
from ..dto.overview import OverviewSnapshotDTO
from ..dto.paper import PaperSummaryDTO
from ..dto.portfolio_governor import PortfolioGovernorSummaryDTO
from ..dto.position_expansion import PositionExpansionSummaryDTO
from ..dto.positions import OpenPositionsDTO, PositionHistoryDTO
from ..dto.reporting import ReportingSummaryDTO
from ..dto.risk import RiskSummaryDTO
from ..dto.settings import (
    CorrelationPolicySettingsDTO,
    DecisionChainSettingsDTO,
    EventBusPolicySettingsDTO,
    FundingPolicySettingsDTO,
    HealthPolicySettingsDTO,
    LiveFeedPolicySettingsDTO,
    ManualApprovalPolicySettingsDTO,
    ProtectionPolicySettingsDTO,
    ReliabilityPolicySettingsDTO,
    RiskLimitsSettingsDTO,
    SystemStatePolicySettingsDTO,
    SystemStateTimeoutSettingsDTO,
    TrailingPolicySettingsDTO,
    UniversePolicySettingsDTO,
    WorkflowTimeoutsSettingsDTO,
)
from ..dto.signals import SignalsSummaryDTO
from ..dto.strategy import StrategySummaryDTO
from ..dto.validation import ValidationSummaryDTO

if TYPE_CHECKING:
    from ..facade.overview_facade import OverviewFacade

logger = get_logger(__name__)


def create_dashboard_router(facade: OverviewFacade) -> APIRouter:
    """
    Создать router панели управления.

    Аргументы:
        facade: Facade для агрегации overview snapshot.
    """
    router = APIRouter(prefix="/dashboard", tags=["dashboard"])

    @router.get(
        "/overview",
        response_model=OverviewSnapshotDTO,
        summary="Получить snapshot overview панели",
    )
    async def get_overview_snapshot() -> OverviewSnapshotDTO:
        logger.debug("Запрошен overview snapshot панели")
        return await facade.get_overview_snapshot()

    @router.get(
        "/risk-summary",
        response_model=RiskSummaryDTO,
        summary="Получить узкий risk summary snapshot панели",
    )
    async def get_risk_summary() -> RiskSummaryDTO:
        logger.debug("Запрошен risk summary snapshot панели")
        return await facade.get_risk_summary()

    @router.get(
        "/signals-summary",
        response_model=SignalsSummaryDTO,
        summary="Получить узкий signals summary snapshot панели",
    )
    async def get_signals_summary() -> SignalsSummaryDTO:
        logger.debug("Запрошен signals summary snapshot панели")
        return await facade.get_signals_summary()

    @router.get(
        "/strategy-summary",
        response_model=StrategySummaryDTO,
        summary="Получить узкий strategy summary snapshot панели",
    )
    async def get_strategy_summary() -> StrategySummaryDTO:
        logger.debug("Запрошен strategy summary snapshot панели")
        return await facade.get_strategy_summary()

    @router.get(
        "/execution-summary",
        response_model=ExecutionSummaryDTO,
        summary="Получить узкий execution summary snapshot панели",
    )
    async def get_execution_summary() -> ExecutionSummaryDTO:
        logger.debug("Запрошен execution summary snapshot панели")
        return await facade.get_execution_summary()

    @router.get(
        "/opportunity-summary",
        response_model=OpportunitySummaryDTO,
        summary="Получить узкий opportunity summary snapshot панели",
    )
    async def get_opportunity_summary() -> OpportunitySummaryDTO:
        logger.debug("Запрошен opportunity summary snapshot панели")
        return await facade.get_opportunity_summary()

    @router.get(
        "/orchestration-summary",
        response_model=OrchestrationSummaryDTO,
        summary="Получить узкий orchestration summary snapshot панели",
    )
    async def get_orchestration_summary() -> OrchestrationSummaryDTO:
        logger.debug("Запрошен orchestration summary snapshot панели")
        return await facade.get_orchestration_summary()

    @router.get(
        "/position-expansion-summary",
        response_model=PositionExpansionSummaryDTO,
        summary="Получить узкий position-expansion summary snapshot панели",
    )
    async def get_position_expansion_summary() -> PositionExpansionSummaryDTO:
        logger.debug("Запрошен position-expansion summary snapshot панели")
        return await facade.get_position_expansion_summary()

    @router.get(
        "/open-positions",
        response_model=OpenPositionsDTO,
        summary="Получить узкий snapshot открытых позиций панели",
    )
    async def get_open_positions() -> OpenPositionsDTO:
        logger.debug("Запрошен open positions snapshot панели")
        return await facade.get_open_positions()

    @router.get(
        "/position-history",
        response_model=PositionHistoryDTO,
        summary="Получить узкий snapshot истории закрытых позиций панели",
    )
    async def get_position_history() -> PositionHistoryDTO:
        logger.debug("Запрошен position history snapshot панели")
        return await facade.get_position_history()

    @router.get(
        "/settings/universe-policy",
        response_model=UniversePolicySettingsDTO,
        summary="Получить текущие настройки фильтра рынка и допуска инструментов",
    )
    async def get_universe_policy_settings() -> UniversePolicySettingsDTO:
        logger.debug("Запрошены текущие universe policy settings")
        return UniversePolicySettingsDTO.from_settings(get_settings())

    @router.put(
        "/settings/universe-policy",
        response_model=UniversePolicySettingsDTO,
        summary="Обновить настройки фильтра рынка и допуска инструментов",
    )
    async def update_universe_policy_settings(
        payload: UniversePolicySettingsDTO,
    ) -> UniversePolicySettingsDTO:
        logger.info("Обновляются universe policy settings")
        try:
            settings = update_settings(payload.to_settings_update())
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return UniversePolicySettingsDTO.from_settings(settings)

    @router.get(
        "/settings/decision-thresholds",
        response_model=DecisionChainSettingsDTO,
        summary="Получить текущие пороги сигналов и принятия решений",
    )
    async def get_decision_chain_settings() -> DecisionChainSettingsDTO:
        logger.debug("Запрошены current decision chain settings")
        return DecisionChainSettingsDTO.from_settings(get_settings())

    @router.put(
        "/settings/decision-thresholds",
        response_model=DecisionChainSettingsDTO,
        summary="Обновить пороги сигналов и принятия решений",
    )
    async def update_decision_chain_settings(
        payload: DecisionChainSettingsDTO,
    ) -> DecisionChainSettingsDTO:
        logger.info("Обновляются decision chain settings")
        try:
            settings = update_settings(payload.to_settings_update())
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return DecisionChainSettingsDTO.from_settings(settings)

    @router.get(
        "/settings/risk-limits",
        response_model=RiskLimitsSettingsDTO,
        summary="Получить текущие базовые лимиты риска",
    )
    async def get_risk_limits_settings() -> RiskLimitsSettingsDTO:
        logger.debug("Запрошены current risk limit settings")
        return RiskLimitsSettingsDTO.from_settings(get_settings())

    @router.put(
        "/settings/risk-limits",
        response_model=RiskLimitsSettingsDTO,
        summary="Обновить базовые лимиты риска",
    )
    async def update_risk_limits_settings(
        payload: RiskLimitsSettingsDTO,
    ) -> RiskLimitsSettingsDTO:
        logger.info("Обновляются risk limit settings")
        try:
            settings = update_settings(payload.to_settings_update())
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return RiskLimitsSettingsDTO.from_settings(settings)

    @router.get(
        "/settings/trailing-policy",
        response_model=TrailingPolicySettingsDTO,
        summary="Получить текущие настройки трейлинга и сопровождения позиции",
    )
    async def get_trailing_policy_settings() -> TrailingPolicySettingsDTO:
        logger.debug("Запрошены current trailing policy settings")
        return TrailingPolicySettingsDTO.from_settings(get_settings())

    @router.put(
        "/settings/trailing-policy",
        response_model=TrailingPolicySettingsDTO,
        summary="Обновить настройки трейлинга и сопровождения позиции",
    )
    async def update_trailing_policy_settings(
        payload: TrailingPolicySettingsDTO,
    ) -> TrailingPolicySettingsDTO:
        logger.info("Обновляются trailing policy settings")
        try:
            settings = update_settings(payload.to_settings_update())
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return TrailingPolicySettingsDTO.from_settings(settings)

    @router.get(
        "/settings/correlation-policy",
        response_model=CorrelationPolicySettingsDTO,
        summary="Получить текущие настройки корреляции и диверсификации",
    )
    async def get_correlation_policy_settings() -> CorrelationPolicySettingsDTO:
        logger.debug("Запрошены current correlation policy settings")
        return CorrelationPolicySettingsDTO.from_settings(get_settings())

    @router.put(
        "/settings/correlation-policy",
        response_model=CorrelationPolicySettingsDTO,
        summary="Обновить настройки корреляции и диверсификации",
    )
    async def update_correlation_policy_settings(
        payload: CorrelationPolicySettingsDTO,
    ) -> CorrelationPolicySettingsDTO:
        logger.info("Обновляются correlation policy settings")
        try:
            settings = update_settings(payload.to_settings_update())
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return CorrelationPolicySettingsDTO.from_settings(settings)

    @router.get(
        "/settings/protection-policy",
        response_model=ProtectionPolicySettingsDTO,
        summary="Получить текущие настройки аварийной защиты и заморозки",
    )
    async def get_protection_policy_settings() -> ProtectionPolicySettingsDTO:
        logger.debug("Запрошены current protection policy settings")
        return ProtectionPolicySettingsDTO.from_settings(get_settings())

    @router.put(
        "/settings/protection-policy",
        response_model=ProtectionPolicySettingsDTO,
        summary="Обновить настройки аварийной защиты и заморозки",
    )
    async def update_protection_policy_settings(
        payload: ProtectionPolicySettingsDTO,
    ) -> ProtectionPolicySettingsDTO:
        logger.info("Обновляются protection policy settings")
        try:
            settings = update_settings(payload.to_settings_update())
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return ProtectionPolicySettingsDTO.from_settings(settings)

    @router.get(
        "/settings/funding-policy",
        response_model=FundingPolicySettingsDTO,
        summary="Получить текущие настройки funding arbitrage и межбиржевых возможностей",
    )
    async def get_funding_policy_settings() -> FundingPolicySettingsDTO:
        logger.debug("Запрошены current funding policy settings")
        return FundingPolicySettingsDTO.from_settings(get_settings())

    @router.put(
        "/settings/funding-policy",
        response_model=FundingPolicySettingsDTO,
        summary="Обновить настройки funding arbitrage и межбиржевых возможностей",
    )
    async def update_funding_policy_settings(
        payload: FundingPolicySettingsDTO,
    ) -> FundingPolicySettingsDTO:
        logger.info("Обновляются funding policy settings")
        try:
            settings = update_settings(payload.to_settings_update())
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return FundingPolicySettingsDTO.from_settings(settings)

    @router.get(
        "/settings/system-state-policy",
        response_model=SystemStatePolicySettingsDTO,
        summary="Получить текущие настройки режимов системы и ограничений",
    )
    async def get_system_state_policy_settings() -> SystemStatePolicySettingsDTO:
        logger.debug("Запрошены current system state policy settings")
        return SystemStatePolicySettingsDTO.from_settings(get_settings())

    @router.put(
        "/settings/system-state-policy",
        response_model=SystemStatePolicySettingsDTO,
        summary="Обновить настройки режимов системы и ограничений",
    )
    async def update_system_state_policy_settings(
        payload: SystemStatePolicySettingsDTO,
    ) -> SystemStatePolicySettingsDTO:
        logger.info("Обновляются system state policy settings")
        try:
            settings = update_settings(payload.to_settings_update())
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return SystemStatePolicySettingsDTO.from_settings(settings)

    @router.get(
        "/settings/system-state-timeouts",
        response_model=SystemStateTimeoutSettingsDTO,
        summary="Получить текущие таймауты состояний системы",
    )
    async def get_system_state_timeout_settings() -> SystemStateTimeoutSettingsDTO:
        logger.debug("Запрошены current system state timeout settings")
        return SystemStateTimeoutSettingsDTO.from_settings(get_settings())

    @router.put(
        "/settings/system-state-timeouts",
        response_model=SystemStateTimeoutSettingsDTO,
        summary="Обновить таймауты состояний системы",
    )
    async def update_system_state_timeout_settings(
        payload: SystemStateTimeoutSettingsDTO,
    ) -> SystemStateTimeoutSettingsDTO:
        logger.info("Обновляются system state timeout settings")
        try:
            settings = update_settings(payload.to_settings_update())
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return SystemStateTimeoutSettingsDTO.from_settings(settings)

    @router.get(
        "/settings/reliability-policy",
        response_model=ReliabilityPolicySettingsDTO,
        summary="Получить текущие настройки надёжности и восстановления системы",
    )
    async def get_reliability_policy_settings() -> ReliabilityPolicySettingsDTO:
        logger.debug("Запрошены current reliability policy settings")
        return ReliabilityPolicySettingsDTO.from_settings(get_settings())

    @router.put(
        "/settings/reliability-policy",
        response_model=ReliabilityPolicySettingsDTO,
        summary="Обновить настройки надёжности и восстановления системы",
    )
    async def update_reliability_policy_settings(
        payload: ReliabilityPolicySettingsDTO,
    ) -> ReliabilityPolicySettingsDTO:
        logger.info("Обновляются reliability policy settings")
        try:
            settings = update_settings(payload.to_settings_update())
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return ReliabilityPolicySettingsDTO.from_settings(settings)

    @router.get(
        "/settings/health-policy",
        response_model=HealthPolicySettingsDTO,
        summary="Получить текущие настройки здоровья системы и проверок готовности",
    )
    async def get_health_policy_settings() -> HealthPolicySettingsDTO:
        logger.debug("Запрошены current health policy settings")
        return HealthPolicySettingsDTO.from_settings(get_settings())

    @router.put(
        "/settings/health-policy",
        response_model=HealthPolicySettingsDTO,
        summary="Обновить настройки здоровья системы и проверок готовности",
    )
    async def update_health_policy_settings(
        payload: HealthPolicySettingsDTO,
    ) -> HealthPolicySettingsDTO:
        logger.info("Обновляются health policy settings")
        try:
            settings = update_settings(payload.to_settings_update())
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return HealthPolicySettingsDTO.from_settings(settings)

    @router.get(
        "/settings/event-bus-policy",
        response_model=EventBusPolicySettingsDTO,
        summary="Получить текущие настройки очередей событий и backpressure",
    )
    async def get_event_bus_policy_settings() -> EventBusPolicySettingsDTO:
        logger.debug("Запрошены current event bus policy settings")
        return EventBusPolicySettingsDTO.from_settings(get_settings())

    @router.put(
        "/settings/event-bus-policy",
        response_model=EventBusPolicySettingsDTO,
        summary="Обновить настройки очередей событий и backpressure",
    )
    async def update_event_bus_policy_settings(
        payload: EventBusPolicySettingsDTO,
    ) -> EventBusPolicySettingsDTO:
        logger.info("Обновляются event bus policy settings")
        try:
            settings = update_settings(payload.to_settings_update())
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return EventBusPolicySettingsDTO.from_settings(settings)

    @router.get(
        "/settings/manual-approval-policy",
        response_model=ManualApprovalPolicySettingsDTO,
        summary="Получить текущие настройки ручного подтверждения действий",
    )
    async def get_manual_approval_policy_settings() -> ManualApprovalPolicySettingsDTO:
        logger.debug("Запрошены current manual approval policy settings")
        return ManualApprovalPolicySettingsDTO.from_settings(get_settings())

    @router.put(
        "/settings/manual-approval-policy",
        response_model=ManualApprovalPolicySettingsDTO,
        summary="Обновить настройки ручного подтверждения действий",
    )
    async def update_manual_approval_policy_settings(
        payload: ManualApprovalPolicySettingsDTO,
    ) -> ManualApprovalPolicySettingsDTO:
        logger.info("Обновляются manual approval policy settings")
        try:
            settings = update_settings(payload.to_settings_update())
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return ManualApprovalPolicySettingsDTO.from_settings(settings)

    @router.get(
        "/settings/workflow-timeouts",
        response_model=WorkflowTimeoutsSettingsDTO,
        summary="Получить текущие сроки жизни workflow и служебных контуров",
    )
    async def get_workflow_timeouts_settings() -> WorkflowTimeoutsSettingsDTO:
        logger.debug("Запрошены current workflow timeout settings")
        return WorkflowTimeoutsSettingsDTO.from_settings(get_settings())

    @router.put(
        "/settings/workflow-timeouts",
        response_model=WorkflowTimeoutsSettingsDTO,
        summary="Обновить сроки жизни workflow и служебных контуров",
    )
    async def update_workflow_timeouts_settings(
        payload: WorkflowTimeoutsSettingsDTO,
    ) -> WorkflowTimeoutsSettingsDTO:
        logger.info("Обновляются workflow timeout settings")
        try:
            settings = update_settings(payload.to_settings_update())
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return WorkflowTimeoutsSettingsDTO.from_settings(settings)

    @router.get(
        "/settings/live-feed-policy",
        response_model=LiveFeedPolicySettingsDTO,
        summary="Получить текущие настройки подключения к рынку и переподключения",
    )
    async def get_live_feed_policy_settings() -> LiveFeedPolicySettingsDTO:
        logger.debug("Запрошены current live feed policy settings")
        return LiveFeedPolicySettingsDTO.from_settings(get_settings())

    @router.put(
        "/settings/live-feed-policy",
        response_model=LiveFeedPolicySettingsDTO,
        summary="Обновить настройки подключения к рынку и переподключения",
    )
    async def update_live_feed_policy_settings(
        payload: LiveFeedPolicySettingsDTO,
    ) -> LiveFeedPolicySettingsDTO:
        logger.info("Обновляются live feed policy settings")
        try:
            settings = update_settings(payload.to_settings_update())
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return LiveFeedPolicySettingsDTO.from_settings(settings)

    @router.get(
        "/portfolio-governor-summary",
        response_model=PortfolioGovernorSummaryDTO,
        summary="Получить узкий portfolio-governor summary snapshot панели",
    )
    async def get_portfolio_governor_summary() -> PortfolioGovernorSummaryDTO:
        logger.debug("Запрошен portfolio-governor summary snapshot панели")
        return await facade.get_portfolio_governor_summary()

    @router.get(
        "/oms-summary",
        response_model=OmsSummaryDTO,
        summary="Получить узкий OMS summary snapshot панели",
    )
    async def get_oms_summary() -> OmsSummaryDTO:
        logger.debug("Запрошен OMS summary snapshot панели")
        return await facade.get_oms_summary()

    @router.get(
        "/manager-summary",
        response_model=ManagerSummaryDTO,
        summary="Получить узкий manager summary snapshot панели",
    )
    async def get_manager_summary() -> ManagerSummaryDTO:
        logger.debug("Запрошен manager summary snapshot панели")
        return await facade.get_manager_summary()

    @router.get(
        "/validation-summary",
        response_model=ValidationSummaryDTO,
        summary="Получить узкий validation summary snapshot панели",
    )
    async def get_validation_summary() -> ValidationSummaryDTO:
        logger.debug("Запрошен validation summary snapshot панели")
        return await facade.get_validation_summary()

    @router.get(
        "/paper-summary",
        response_model=PaperSummaryDTO,
        summary="Получить узкий paper summary snapshot панели",
    )
    async def get_paper_summary() -> PaperSummaryDTO:
        logger.debug("Запрошен paper summary snapshot панели")
        return await facade.get_paper_summary()

    @router.get(
        "/backtest-summary",
        response_model=BacktestSummaryDTO,
        summary="Получить узкий backtest summary snapshot панели",
    )
    async def get_backtest_summary() -> BacktestSummaryDTO:
        logger.debug("Запрошен backtest summary snapshot панели")
        return await facade.get_backtest_summary()

    @router.get(
        "/reporting-summary",
        response_model=ReportingSummaryDTO,
        summary="Получить узкий reporting artifact catalog summary панели",
    )
    async def get_reporting_summary() -> ReportingSummaryDTO:
        logger.debug("Запрошен reporting artifact catalog summary панели")
        return await facade.get_reporting_summary()

    return router

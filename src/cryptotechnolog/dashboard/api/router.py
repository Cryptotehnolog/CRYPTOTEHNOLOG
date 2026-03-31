"""FastAPI router для read-only dashboard snapshot endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter

from cryptotechnolog.config import get_logger

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

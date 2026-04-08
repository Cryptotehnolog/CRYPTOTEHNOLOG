"""FastAPI router для read-only dashboard snapshot endpoints."""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any, Protocol

from fastapi import APIRouter, HTTPException

from cryptotechnolog.config import (
    get_logger,
    get_settings,
)
from cryptotechnolog.config import (
    persist_settings_updates as update_settings,
)

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
    BybitConnectorDiagnosticsDTO,
    BybitConnectorToggleDTO,
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
    from collections.abc import Awaitable, Callable

    from ..facade.overview_facade import OverviewFacade

logger = get_logger(__name__)


class SettingsDTOContract(Protocol):
    @classmethod
    def from_settings(cls, settings: Any) -> SettingsDTOContract: ...

    def to_settings_update(self) -> dict[str, Any]: ...


def _update_settings_dto(
    payload: SettingsDTOContract,
    log_message: str,
    dto_type: type[SettingsDTOContract],
) -> SettingsDTOContract:
    logger.info(log_message)
    try:
        settings = update_settings(payload.to_settings_update())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return dto_type.from_settings(settings)


def _register_summary_route(
    router: APIRouter,
    path: str,
    response_model: type[object],
    summary: str,
    log_message: str,
    handler: Callable[[], Awaitable[object]],
) -> None:
    @router.get(path, response_model=response_model, summary=summary)
    async def get_summary() -> object:
        logger.debug(log_message)
        return await handler()


def _build_settings_get_handler(
    dto_type: type[SettingsDTOContract],
    get_log: str,
) -> Any:
    async def get_settings_snapshot() -> Any:
        logger.debug(get_log)
        return dto_type.from_settings(get_settings())

    return get_settings_snapshot


def _build_settings_put_handler(
    dto_type: type[SettingsDTOContract],
    update_log: str,
) -> Any:
    async def update_settings_snapshot(payload: Any) -> Any:
        return _update_settings_dto(payload, update_log, dto_type)

    update_settings_snapshot.__signature__ = inspect.Signature(
        parameters=[
            inspect.Parameter(
                "payload",
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=dto_type,
            )
        ],
        return_annotation=dto_type,
    )
    return update_settings_snapshot


def _register_settings_routes(
    router: APIRouter,
    live_feed_policy_get_handler: Callable[[], Awaitable[LiveFeedPolicySettingsDTO]] | None = None,
    live_feed_policy_update_handler: Callable[
        [LiveFeedPolicySettingsDTO], Awaitable[LiveFeedPolicySettingsDTO]
    ]
    | None = None,
) -> None:
    def register_pair(
        path: str,
        dto_type: type[SettingsDTOContract],
        get_summary: str,
        get_log: str,
        update_summary: str,
        update_log: str,
    ) -> None:
        router.add_api_route(
            path,
            _build_settings_get_handler(dto_type, get_log),
            methods=["GET"],
            response_model=dto_type,
            summary=get_summary,
        )
        router.add_api_route(
            path,
            _build_settings_put_handler(dto_type, update_log),
            methods=["PUT"],
            response_model=dto_type,
            summary=update_summary,
        )

    register_pair(
        "/settings/universe-policy",
        UniversePolicySettingsDTO,
        "Получить текущие настройки фильтра рынка и допуска инструментов",
        "Запрошены текущие universe policy settings",
        "Обновить настройки фильтра рынка и допуска инструментов",
        "Обновляются universe policy settings",
    )
    register_pair(
        "/settings/decision-thresholds",
        DecisionChainSettingsDTO,
        "Получить текущие пороги сигналов и принятия решений",
        "Запрошены current decision chain settings",
        "Обновить пороги сигналов и принятия решений",
        "Обновляются decision chain settings",
    )
    register_pair(
        "/settings/risk-limits",
        RiskLimitsSettingsDTO,
        "Получить текущие базовые лимиты риска",
        "Запрошены current risk limit settings",
        "Обновить базовые лимиты риска",
        "Обновляются risk limit settings",
    )
    register_pair(
        "/settings/trailing-policy",
        TrailingPolicySettingsDTO,
        "Получить текущие настройки трейлинга и сопровождения позиции",
        "Запрошены current trailing policy settings",
        "Обновить настройки трейлинга и сопровождения позиции",
        "Обновляются trailing policy settings",
    )
    register_pair(
        "/settings/correlation-policy",
        CorrelationPolicySettingsDTO,
        "Получить текущие настройки корреляции и диверсификации",
        "Запрошены current correlation policy settings",
        "Обновить настройки корреляции и диверсификации",
        "Обновляются correlation policy settings",
    )
    register_pair(
        "/settings/protection-policy",
        ProtectionPolicySettingsDTO,
        "Получить текущие настройки аварийной защиты и заморозки",
        "Запрошены current protection policy settings",
        "Обновить настройки аварийной защиты и заморозки",
        "Обновляются protection policy settings",
    )
    register_pair(
        "/settings/funding-policy",
        FundingPolicySettingsDTO,
        "Получить текущие настройки funding arbitrage и межбиржевых возможностей",
        "Запрошены current funding policy settings",
        "Обновить настройки funding arbitrage и межбиржевых возможностей",
        "Обновляются funding policy settings",
    )
    register_pair(
        "/settings/system-state-policy",
        SystemStatePolicySettingsDTO,
        "Получить текущие настройки режимов системы и ограничений",
        "Запрошены current system state policy settings",
        "Обновить настройки режимов системы и ограничений",
        "Обновляются system state policy settings",
    )
    register_pair(
        "/settings/system-state-timeouts",
        SystemStateTimeoutSettingsDTO,
        "Получить текущие таймауты состояний системы",
        "Запрошены current system state timeout settings",
        "Обновить таймауты состояний системы",
        "Обновляются system state timeout settings",
    )
    register_pair(
        "/settings/reliability-policy",
        ReliabilityPolicySettingsDTO,
        "Получить текущие настройки надёжности и восстановления системы",
        "Запрошены current reliability policy settings",
        "Обновить настройки надёжности и восстановления системы",
        "Обновляются reliability policy settings",
    )
    register_pair(
        "/settings/health-policy",
        HealthPolicySettingsDTO,
        "Получить текущие настройки здоровья системы и проверок готовности",
        "Запрошены current health policy settings",
        "Обновить настройки здоровья системы и проверок готовности",
        "Обновляются health policy settings",
    )
    register_pair(
        "/settings/event-bus-policy",
        EventBusPolicySettingsDTO,
        "Получить текущие настройки очередей событий и backpressure",
        "Запрошены current event bus policy settings",
        "Обновить настройки очередей событий и backpressure",
        "Обновляются event bus policy settings",
    )
    register_pair(
        "/settings/manual-approval-policy",
        ManualApprovalPolicySettingsDTO,
        "Получить текущие настройки ручного подтверждения действий",
        "Запрошены current manual approval policy settings",
        "Обновить настройки ручного подтверждения действий",
        "Обновляются manual approval policy settings",
    )
    register_pair(
        "/settings/workflow-timeouts",
        WorkflowTimeoutsSettingsDTO,
        "Получить текущие сроки жизни workflow и служебных контуров",
        "Запрошены current workflow timeout settings",
        "Обновить сроки жизни workflow и служебных контуров",
        "Обновляются workflow timeout settings",
    )
    if live_feed_policy_get_handler is None:
        router.add_api_route(
            "/settings/live-feed-policy",
            _build_settings_get_handler(
                LiveFeedPolicySettingsDTO,
                "Запрошены current live feed policy settings",
            ),
            methods=["GET"],
            response_model=LiveFeedPolicySettingsDTO,
            summary="Получить текущие настройки подключения к рынку и переподключения",
        )
    else:

        async def get_live_feed_policy_settings() -> LiveFeedPolicySettingsDTO:
            logger.debug("Запрошены current live feed policy settings")
            return await live_feed_policy_get_handler()

        router.add_api_route(
            "/settings/live-feed-policy",
            get_live_feed_policy_settings,
            methods=["GET"],
            response_model=LiveFeedPolicySettingsDTO,
            summary="Получить текущие настройки подключения к рынку и переподключения",
        )

    if live_feed_policy_update_handler is None:
        router.add_api_route(
            "/settings/live-feed-policy",
            _build_settings_put_handler(
                LiveFeedPolicySettingsDTO,
                "Обновляются live feed policy settings",
            ),
            methods=["PUT"],
            response_model=LiveFeedPolicySettingsDTO,
            summary="Обновить настройки подключения к рынку и переподключения",
        )
    else:

        async def update_live_feed_policy_settings(
            payload: LiveFeedPolicySettingsDTO,
        ) -> LiveFeedPolicySettingsDTO:
            logger.info("Обновляются live feed policy settings")
            try:
                return await live_feed_policy_update_handler(payload)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            except RuntimeError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc

        router.add_api_route(
            "/settings/live-feed-policy",
            update_live_feed_policy_settings,
            methods=["PUT"],
            response_model=LiveFeedPolicySettingsDTO,
            summary="Обновить настройки подключения к рынку и переподключения",
        )


def _register_connector_diagnostics_routes(
    router: APIRouter,
    runtime_diagnostics_supplier: Callable[[], dict[str, Any]] | None,
    bybit_connector_toggle_handler: Callable[[bool], Awaitable[dict[str, Any]]] | None,
    bybit_spot_connector_toggle_handler: Callable[[bool], Awaitable[dict[str, Any]]] | None,
) -> None:
    @router.get(
        "/settings/bybit-connector-diagnostics",
        response_model=BybitConnectorDiagnosticsDTO,
        summary="Получить read-only diagnostics snapshot Bybit connector-а",
    )
    async def get_bybit_connector_diagnostics() -> BybitConnectorDiagnosticsDTO:
        logger.debug("Запрошен Bybit connector diagnostics snapshot")
        diagnostics = (
            runtime_diagnostics_supplier() if runtime_diagnostics_supplier is not None else {}
        )
        return BybitConnectorDiagnosticsDTO.from_runtime_diagnostics(diagnostics)

    @router.put(
        "/settings/bybit-connector-enabled",
        response_model=BybitConnectorDiagnosticsDTO,
        summary="Включить или выключить canonical Bybit connector",
    )
    async def update_bybit_connector_enabled(
        payload: BybitConnectorToggleDTO,
    ) -> BybitConnectorDiagnosticsDTO:
        logger.info("Обновляется canonical Bybit connector enabled flag", enabled=payload.enabled)
        if bybit_connector_toggle_handler is None:
            raise HTTPException(
                status_code=503,
                detail="Canonical backend runtime недоступен для управления Bybit connector-ом",
            )
        try:
            diagnostics = await bybit_connector_toggle_handler(payload.enabled)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return BybitConnectorDiagnosticsDTO.from_runtime_diagnostics(diagnostics)

    @router.get(
        "/settings/bybit-spot-connector-diagnostics",
        response_model=BybitConnectorDiagnosticsDTO,
        summary="Получить read-only diagnostics snapshot Bybit spot connector-а",
    )
    async def get_bybit_spot_connector_diagnostics() -> BybitConnectorDiagnosticsDTO:
        logger.debug("Запрошен Bybit spot connector diagnostics snapshot")
        diagnostics = (
            runtime_diagnostics_supplier() if runtime_diagnostics_supplier is not None else {}
        )
        connector_diagnostics = dict(diagnostics)
        connector_diagnostics["bybit_market_data_connector"] = diagnostics.get(
            "bybit_spot_market_data_connector",
            {},
        )
        return BybitConnectorDiagnosticsDTO.from_runtime_diagnostics(connector_diagnostics)

    @router.put(
        "/settings/bybit-spot-connector-enabled",
        response_model=BybitConnectorDiagnosticsDTO,
        summary="Включить или выключить canonical Bybit spot connector",
    )
    async def update_bybit_spot_connector_enabled(
        payload: BybitConnectorToggleDTO,
    ) -> BybitConnectorDiagnosticsDTO:
        logger.info(
            "Обновляется canonical Bybit spot connector enabled flag",
            enabled=payload.enabled,
        )
        if bybit_spot_connector_toggle_handler is None:
            raise HTTPException(
                status_code=503,
                detail="Canonical backend runtime недоступен для управления Bybit spot connector-ом",
            )
        try:
            diagnostics = await bybit_spot_connector_toggle_handler(payload.enabled)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        connector_diagnostics = dict(diagnostics)
        connector_diagnostics["bybit_market_data_connector"] = diagnostics.get(
            "bybit_spot_market_data_connector",
            {},
        )
        return BybitConnectorDiagnosticsDTO.from_runtime_diagnostics(connector_diagnostics)


def _register_core_summary_routes(router: APIRouter, facade: OverviewFacade) -> None:
    _register_summary_route(
        router,
        "/overview",
        OverviewSnapshotDTO,
        "Получить snapshot overview панели",
        "Запрошен overview snapshot панели",
        facade.get_overview_snapshot,
    )
    _register_summary_route(
        router,
        "/risk-summary",
        RiskSummaryDTO,
        "Получить узкий risk summary snapshot панели",
        "Запрошен risk summary snapshot панели",
        facade.get_risk_summary,
    )
    _register_summary_route(
        router,
        "/signals-summary",
        SignalsSummaryDTO,
        "Получить узкий signals summary snapshot панели",
        "Запрошен signals summary snapshot панели",
        facade.get_signals_summary,
    )
    _register_summary_route(
        router,
        "/strategy-summary",
        StrategySummaryDTO,
        "Получить узкий strategy summary snapshot панели",
        "Запрошен strategy summary snapshot панели",
        facade.get_strategy_summary,
    )
    _register_summary_route(
        router,
        "/execution-summary",
        ExecutionSummaryDTO,
        "Получить узкий execution summary snapshot панели",
        "Запрошен execution summary snapshot панели",
        facade.get_execution_summary,
    )
    _register_summary_route(
        router,
        "/opportunity-summary",
        OpportunitySummaryDTO,
        "Получить узкий opportunity summary snapshot панели",
        "Запрошен opportunity summary snapshot панели",
        facade.get_opportunity_summary,
    )
    _register_summary_route(
        router,
        "/orchestration-summary",
        OrchestrationSummaryDTO,
        "Получить узкий orchestration summary snapshot панели",
        "Запрошен orchestration summary snapshot панели",
        facade.get_orchestration_summary,
    )
    _register_summary_route(
        router,
        "/position-expansion-summary",
        PositionExpansionSummaryDTO,
        "Получить узкий position-expansion summary snapshot панели",
        "Запрошен position-expansion summary snapshot панели",
        facade.get_position_expansion_summary,
    )


def _register_positions_routes(router: APIRouter, facade: OverviewFacade) -> None:
    _register_summary_route(
        router,
        "/open-positions",
        OpenPositionsDTO,
        "Получить узкий snapshot открытых позиций панели",
        "Запрошен open positions snapshot панели",
        facade.get_open_positions,
    )
    _register_summary_route(
        router,
        "/position-history",
        PositionHistoryDTO,
        "Получить узкий snapshot истории закрытых позиций панели",
        "Запрошен position history snapshot панели",
        facade.get_position_history,
    )


def _register_operational_summary_routes(router: APIRouter, facade: OverviewFacade) -> None:
    _register_summary_route(
        router,
        "/portfolio-governor-summary",
        PortfolioGovernorSummaryDTO,
        "Получить узкий portfolio-governor summary snapshot панели",
        "Запрошен portfolio-governor summary snapshot панели",
        facade.get_portfolio_governor_summary,
    )
    _register_summary_route(
        router,
        "/oms-summary",
        OmsSummaryDTO,
        "Получить узкий OMS summary snapshot панели",
        "Запрошен OMS summary snapshot панели",
        facade.get_oms_summary,
    )
    _register_summary_route(
        router,
        "/manager-summary",
        ManagerSummaryDTO,
        "Получить узкий manager summary snapshot панели",
        "Запрошен manager summary snapshot панели",
        facade.get_manager_summary,
    )
    _register_summary_route(
        router,
        "/validation-summary",
        ValidationSummaryDTO,
        "Получить узкий validation summary snapshot панели",
        "Запрошен validation summary snapshot панели",
        facade.get_validation_summary,
    )
    _register_summary_route(
        router,
        "/paper-summary",
        PaperSummaryDTO,
        "Получить узкий paper summary snapshot панели",
        "Запрошен paper summary snapshot панели",
        facade.get_paper_summary,
    )
    _register_summary_route(
        router,
        "/backtest-summary",
        BacktestSummaryDTO,
        "Получить узкий backtest summary snapshot панели",
        "Запрошен backtest summary snapshot панели",
        facade.get_backtest_summary,
    )
    _register_summary_route(
        router,
        "/reporting-summary",
        ReportingSummaryDTO,
        "Получить узкий reporting artifact catalog summary панели",
        "Запрошен reporting artifact catalog summary панели",
        facade.get_reporting_summary,
    )


def create_dashboard_router(
    facade: OverviewFacade,
    runtime_diagnostics_supplier: Callable[[], dict[str, Any]] | None = None,
    live_feed_policy_get_handler: Callable[[], Awaitable[LiveFeedPolicySettingsDTO]] | None = None,
    live_feed_policy_update_handler: Callable[
        [LiveFeedPolicySettingsDTO], Awaitable[LiveFeedPolicySettingsDTO]
    ]
    | None = None,
    bybit_connector_toggle_handler: Callable[[bool], Awaitable[dict[str, Any]]] | None = None,
    bybit_spot_connector_toggle_handler: Callable[[bool], Awaitable[dict[str, Any]]] | None = None,
) -> APIRouter:
    """
    Создать router панели управления.

    Аргументы:
        facade: Facade для агрегации overview snapshot.
    """
    router = APIRouter(prefix="/dashboard", tags=["dashboard"])

    _register_core_summary_routes(router, facade)
    _register_positions_routes(router, facade)
    _register_settings_routes(
        router,
        live_feed_policy_get_handler,
        live_feed_policy_update_handler,
    )
    _register_connector_diagnostics_routes(
        router,
        runtime_diagnostics_supplier,
        bybit_connector_toggle_handler,
        bybit_spot_connector_toggle_handler,
    )
    _register_operational_summary_routes(router, facade)

    return router

"""
Runtime/composition integration для нового Risk Engine Фазы 5.

Этот модуль собирает современный risk-контур как отдельную ветку архитектуры:
- без опоры на legacy `core.listeners.risk`;
- с явным wiring `RiskEngineListener`;
- с optional persistence repository;
- с отдельным FundingManager как готовым доменным компонентом.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from importlib import import_module
from typing import TYPE_CHECKING, cast

from cryptotechnolog.config import get_logger, get_settings
from cryptotechnolog.core import SystemController, get_event_bus
from cryptotechnolog.core.database import get_db_pool
from cryptotechnolog.core.state_machine_enums import SystemState

from .correlation import CorrelationConfig, CorrelationEvaluator
from .drawdown_monitor import DrawdownMonitor, DrawdownMonitorConfig
from .engine import RiskEngine, RiskEngineConfig
from .funding_manager import FundingManager, FundingManagerConfig
from .listeners import RiskEngineListener, RiskEngineListenerConfig
from .portfolio_state import PortfolioState
from .position_sizing import PositionSizer
from .risk_ledger import RiskLedger
from .trailing_policy import TrailingPolicy, TrailingPolicyConfig

if TYPE_CHECKING:
    import asyncpg

    from cryptotechnolog.config.settings import Settings
    from cryptotechnolog.core.enhanced_event_bus import EnhancedEventBus

    from .persistence_contracts import IRiskPersistenceRepository

logger = get_logger(__name__)


@dataclass(slots=True, frozen=True)
class RiskRuntimeConfig:
    """Явная runtime-конфигурация нового risk-контура Фазы 5."""

    engine: RiskEngineConfig
    drawdown: DrawdownMonitorConfig
    correlation: CorrelationConfig
    trailing: TrailingPolicyConfig
    funding: FundingManagerConfig
    starting_equity: Decimal
    funding_feature_enabled: bool
    enable_persistence: bool

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        *,
        enable_persistence: bool = False,
    ) -> RiskRuntimeConfig:
        """Собрать runtime-конфигурацию из текущих project settings."""
        return cls(
            engine=RiskEngineConfig(
                base_r_percent=Decimal(str(settings.base_r_percent)),
                max_r_per_trade=Decimal(str(settings.max_r_per_trade)),
                max_total_r=Decimal(str(settings.max_portfolio_r)),
                max_total_exposure_usd=Decimal(str(settings.risk_max_total_exposure_usd)),
                max_position_size=Decimal(str(settings.max_position_size)),
            ),
            drawdown=DrawdownMonitorConfig(),
            correlation=CorrelationConfig(),
            trailing=TrailingPolicyConfig(),
            funding=FundingManagerConfig(),
            starting_equity=Decimal(str(settings.risk_starting_equity)),
            funding_feature_enabled=settings.feature_funding_rate_arbitrage,
            enable_persistence=enable_persistence,
        )


@dataclass(slots=True)
class RiskRuntime:
    """Собранный runtime нового Risk Engine Фазы 5."""

    event_bus: EnhancedEventBus
    risk_engine: RiskEngine
    risk_listener: RiskEngineListener
    funding_manager: FundingManager
    position_sizer: PositionSizer
    risk_ledger: RiskLedger
    portfolio_state: PortfolioState
    drawdown_monitor: DrawdownMonitor
    correlation_evaluator: CorrelationEvaluator
    trailing_policy: TrailingPolicy
    persistence_repository: IRiskPersistenceRepository | None
    config: RiskRuntimeConfig
    controller: SystemController | None = None
    _listener_registered: bool = False

    async def start(self) -> None:
        """
        Подключить новый listener к event-driven контуру.

        Legacy risk listener здесь не регистрируется:
        controlled coexistence остаётся явным на уровне bootstrap.
        """
        if self._listener_registered:
            return
        self.event_bus.register_listener(self.risk_listener)
        self._listener_registered = True
        logger.info(
            "Runtime нового Risk Engine подключён к Event Bus",
            listener=self.risk_listener.name,
            persistence_enabled=self.persistence_repository is not None,
            funding_feature_enabled=self.config.funding_feature_enabled,
        )

    async def stop(self) -> None:
        """Отключить listener нового risk-контура от Event Bus."""
        if not self._listener_registered:
            return
        self.event_bus.unregister_listener(self.risk_listener.name)
        self._listener_registered = False
        logger.info("Runtime нового Risk Engine отключён от Event Bus")


async def create_risk_runtime(
    *,
    event_bus: EnhancedEventBus | None = None,
    controller: SystemController | None = None,
    settings: Settings | None = None,
    db_pool: asyncpg.Pool | None = None,
    enable_persistence: bool = False,
) -> RiskRuntime:
    """
    Собрать новый risk-контур Фазы 5 как отдельный runtime path.

    Важно:
    - не использует legacy `core.listeners.risk` как основу;
    - optional repository подключается только при явном запросе;
    - FundingManager собирается как отдельный доменный компонент.
    """
    runtime_settings = settings or get_settings()
    runtime_config = RiskRuntimeConfig.from_settings(
        runtime_settings,
        enable_persistence=enable_persistence,
    )
    runtime_event_bus = event_bus or get_event_bus()

    risk_ledger = RiskLedger()
    portfolio_state = PortfolioState()
    drawdown_monitor = DrawdownMonitor(
        starting_equity=runtime_config.starting_equity,
        config=runtime_config.drawdown,
    )
    correlation_evaluator = CorrelationEvaluator(runtime_config.correlation)
    position_sizer = PositionSizer()
    trailing_policy = TrailingPolicy(risk_ledger=risk_ledger, config=runtime_config.trailing)
    funding_manager = FundingManager(config=runtime_config.funding)

    persistence_repository = await _create_persistence_repository_if_enabled(
        enable_persistence=runtime_config.enable_persistence,
        db_pool=db_pool,
    )

    initial_system_state = controller.current_state if controller is not None else SystemState.TRADING
    risk_engine = RiskEngine(
        config=runtime_config.engine,
        correlation_evaluator=correlation_evaluator,
        position_sizer=position_sizer,
        portfolio_state=portfolio_state,
        drawdown_monitor=drawdown_monitor,
        risk_ledger=risk_ledger,
        trailing_policy=trailing_policy,
        persistence_repository=persistence_repository,
        initial_system_state=initial_system_state,
    )
    risk_listener = RiskEngineListener(
        risk_engine=risk_engine,
        publisher=runtime_event_bus.publish,
        config=RiskEngineListenerConfig(),
    )

    runtime = RiskRuntime(
        event_bus=runtime_event_bus,
        risk_engine=risk_engine,
        risk_listener=risk_listener,
        funding_manager=funding_manager,
        position_sizer=position_sizer,
        risk_ledger=risk_ledger,
        portfolio_state=portfolio_state,
        drawdown_monitor=drawdown_monitor,
        correlation_evaluator=correlation_evaluator,
        trailing_policy=trailing_policy,
        persistence_repository=persistence_repository,
        config=runtime_config,
        controller=controller,
    )

    if controller is not None:
        _register_runtime_components(controller=controller, runtime=runtime)

    return runtime


async def _create_persistence_repository_if_enabled(
    *,
    enable_persistence: bool,
    db_pool: asyncpg.Pool | None,
) -> IRiskPersistenceRepository | None:
    """Создать optional repository только там, где persistence уже готова."""
    if not enable_persistence:
        return None

    pool = db_pool or await get_db_pool()

    # Ленивая импортная граница сохраняет orchestration truly optional к asyncpg.
    repository_cls = import_module("cryptotechnolog.risk.persistence").RiskPersistenceRepository
    return cast("IRiskPersistenceRepository", repository_cls(pool))


def _register_runtime_components(
    *,
    controller: SystemController,
    runtime: RiskRuntime,
) -> None:
    """Зарегистрировать компоненты нового risk-контура в SystemController."""
    controller.register_component(
        name="phase5_risk_engine",
        component=runtime.risk_engine,
        required=False,
        health_check_enabled=False,
    )
    controller.register_component(
        name="phase5_risk_listener",
        component=runtime.risk_listener,
        required=False,
        health_check_enabled=False,
    )
    controller.register_component(
        name="phase5_funding_manager",
        component=runtime.funding_manager,
        required=False,
        health_check_enabled=False,
    )

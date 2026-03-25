"""Системный registry доступности модулей панели."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from threading import RLock


class DashboardModuleStatus(StrEnum):
    """Фазовые статусы dashboard-модуля."""

    INACTIVE = "inactive"
    READ_ONLY = "read-only"
    ACTIVE = "active"
    RESTRICTED = "restricted"


@dataclass(frozen=True, slots=True)
class DashboardModuleDefinition:
    """Описание модуля панели как системной сущности."""

    key: str
    title: str
    description: str
    route: str
    phase: str
    default_status: DashboardModuleStatus = DashboardModuleStatus.INACTIVE


@dataclass(frozen=True, slots=True)
class ModuleAvailabilityRecord:
    """Snapshot доступности модуля панели."""

    key: str
    title: str
    description: str
    route: str
    phase: str
    status: DashboardModuleStatus
    status_reason: str | None = None


class ModuleAvailabilityRegistry:
    """Системный registry доступности модулей панели."""

    def __init__(self, definitions: list[DashboardModuleDefinition] | None = None) -> None:
        self._definitions: dict[str, DashboardModuleDefinition] = {}
        self._statuses: dict[str, tuple[DashboardModuleStatus, str | None]] = {}
        self._lock = RLock()

        for definition in definitions or []:
            self.register_module(definition)

    def register_module(self, definition: DashboardModuleDefinition) -> None:
        """Зарегистрировать модуль панели."""
        with self._lock:
            self._definitions[definition.key] = definition
            self._statuses.setdefault(
                definition.key,
                (definition.default_status, None),
            )

    def set_status(
        self,
        key: str,
        status: DashboardModuleStatus,
        reason: str | None = None,
    ) -> None:
        """Установить фазовый статус модуля."""
        with self._lock:
            if key not in self._definitions:
                raise KeyError(f"Модуль панели '{key}' не зарегистрирован")
            self._statuses[key] = (status, reason)

    def get_module(self, key: str) -> ModuleAvailabilityRecord:
        """Получить snapshot доступности одного модуля."""
        with self._lock:
            definition = self._definitions[key]
            status, reason = self._statuses[key]
            return ModuleAvailabilityRecord(
                key=definition.key,
                title=definition.title,
                description=definition.description,
                route=definition.route,
                phase=definition.phase,
                status=status,
                status_reason=reason,
            )

    def list_modules(self) -> list[ModuleAvailabilityRecord]:
        """Получить snapshot доступности всех модулей."""
        with self._lock:
            return [self.get_module(key) for key in self._definitions]


def create_default_module_registry() -> ModuleAvailabilityRegistry:
    """Создать registry с базовой картой модулей панели."""
    registry = ModuleAvailabilityRegistry(
        definitions=[
            DashboardModuleDefinition(
                key="overview",
                title="Overview",
                description="Глобальный обзор состояния платформы",
                route="/overview",
                phase="v1",
                default_status=DashboardModuleStatus.READ_ONLY,
            ),
            DashboardModuleDefinition(
                key="control-plane",
                title="Контур управления",
                description="Жизненный цикл системы и runtime discipline",
                route="/control-plane",
                phase="core",
                default_status=DashboardModuleStatus.READ_ONLY,
            ),
            DashboardModuleDefinition(
                key="health-observability",
                title="Здоровье и наблюдаемость",
                description="Техническое состояние и деградации компонентов",
                route="/health",
                phase="core",
                default_status=DashboardModuleStatus.READ_ONLY,
            ),
            DashboardModuleDefinition(
                key="operator-gate",
                title="Операторский контур",
                description="Pending approvals и dual control workflows",
                route="/operator-gate",
                phase="core",
                default_status=DashboardModuleStatus.READ_ONLY,
            ),
            DashboardModuleDefinition(
                key="config-events",
                title="Конфигурация и события",
                description="Snapshot конфигурации и поток системных событий",
                route="/config-events",
                phase="v1.4.0",
                default_status=DashboardModuleStatus.READ_ONLY,
            ),
            DashboardModuleDefinition(
                key="risk",
                title="Риск",
                description="Риск, лимиты и ограничения платформы",
                route="/risk",
                phase="v1.5.1",
                default_status=DashboardModuleStatus.READ_ONLY,
            ),
            DashboardModuleDefinition(
                key="signals",
                title="Сигналы",
                description="Signal Generation Foundation и signal truth",
                route="/signals",
                phase="v1.8.0",
                default_status=DashboardModuleStatus.READ_ONLY,
            ),
            DashboardModuleDefinition(
                key="strategy",
                title="Стратегия",
                description="Strategy Foundation и strategy candidate truth",
                route="/strategy",
                phase="v1.9.0",
                default_status=DashboardModuleStatus.READ_ONLY,
            ),
            DashboardModuleDefinition(
                key="execution",
                title="Исполнение",
                description="Execution Foundation и execution intent truth",
                route="/execution",
                phase="v1.10.0",
                default_status=DashboardModuleStatus.READ_ONLY,
            ),
            DashboardModuleDefinition(
                key="oms",
                title="OMS",
                description="OMS Foundation и order-state truth",
                route="/oms",
                phase="v1.16.0",
                default_status=DashboardModuleStatus.READ_ONLY,
            ),
            DashboardModuleDefinition(
                key="manager",
                title="Manager",
                description="Manager Foundation и workflow truth",
                route="/manager",
                phase="v1.17.0",
                default_status=DashboardModuleStatus.READ_ONLY,
            ),
            DashboardModuleDefinition(
                key="validation",
                title="Validation",
                description="Validation Foundation и review truth",
                route="/validation",
                phase="v1.18.0",
                default_status=DashboardModuleStatus.READ_ONLY,
            ),
            DashboardModuleDefinition(
                key="paper",
                title="Paper",
                description="Paper Foundation и rehearsal truth",
                route="/paper",
                phase="v1.19.0",
                default_status=DashboardModuleStatus.READ_ONLY,
            ),
            DashboardModuleDefinition(
                key="backtest",
                title="Бэктест",
                description="Контур бэктеста и состояние прогонов",
                route="/backtest",
                phase="v1.20.0",
                default_status=DashboardModuleStatus.READ_ONLY,
            ),
            DashboardModuleDefinition(
                key="reporting",
                title="Отчётность",
                description="Каталог отчётных артефактов и bundle-снимков",
                route="/reporting",
                phase="v1.21.0",
                default_status=DashboardModuleStatus.READ_ONLY,
            ),
            DashboardModuleDefinition(
                key="opportunity",
                title="Возможности",
                description="Контур возможностей и состояние отбора",
                route="/opportunity",
                phase="v1.11.0",
                default_status=DashboardModuleStatus.READ_ONLY,
            ),
            DashboardModuleDefinition(
                key="orchestration",
                title="Оркестрация",
                description="Контур оркестрации и состояние решений",
                route="/orchestration",
                phase="v1.12.0",
                default_status=DashboardModuleStatus.READ_ONLY,
            ),
            DashboardModuleDefinition(
                key="position-expansion",
                title="Расширение позиции",
                description="Контур расширения позиции и состояние кандидатов",
                route="/position-expansion",
                phase="v1.13.0",
                default_status=DashboardModuleStatus.READ_ONLY,
            ),
            DashboardModuleDefinition(
                key="portfolio-governor",
                title="Портфельный контур",
                description="Контур управления капиталом и портфелем",
                route="/portfolio-governor",
                phase="v1.14.0",
                default_status=DashboardModuleStatus.READ_ONLY,
            ),
        ]
    )
    return registry

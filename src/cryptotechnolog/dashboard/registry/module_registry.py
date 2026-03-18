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
                title="Control Plane",
                description="Управление жизненным циклом системы",
                route="/control-plane",
                phase="v1",
            ),
            DashboardModuleDefinition(
                key="health-observability",
                title="Health & Observability",
                description="Техническое состояние и деградации компонентов",
                route="/health",
                phase="v1",
            ),
            DashboardModuleDefinition(
                key="operator-gate",
                title="Operator Gate",
                description="Pending approvals и dual control workflows",
                route="/operator-gate",
                phase="v1",
            ),
            DashboardModuleDefinition(
                key="config-events",
                title="Config & Events",
                description="Snapshot конфигурации и поток системных событий",
                route="/config-events",
                phase="v1",
            ),
            DashboardModuleDefinition(
                key="risk",
                title="Risk",
                description="Риск, лимиты и ограничения платформы",
                route="/risk",
                phase="v2",
            ),
            DashboardModuleDefinition(
                key="portfolio",
                title="Portfolio & Capital",
                description="Портфель, капитал и агрегированная экспозиция",
                route="/portfolio",
                phase="v2",
            ),
            DashboardModuleDefinition(
                key="strategies",
                title="Strategies & Signals",
                description="Состояние стратегий и поток сигналов",
                route="/strategies",
                phase="v2",
            ),
            DashboardModuleDefinition(
                key="execution",
                title="Execution & Orders",
                description="Исполнение, ордера и latency view",
                route="/execution",
                phase="v3",
            ),
            DashboardModuleDefinition(
                key="exchanges",
                title="Exchanges",
                description="Контроль внешних торговых интеграций",
                route="/exchanges",
                phase="v3",
            ),
            DashboardModuleDefinition(
                key="advanced-config",
                title="Advanced Config",
                description="Управляемые config workflows и approvals",
                route="/advanced-config",
                phase="v4",
            ),
            DashboardModuleDefinition(
                key="audit-compliance",
                title="Audit & Compliance",
                description="Audit trail, replay и compliance surfaces",
                route="/audit",
                phase="v4",
            ),
            DashboardModuleDefinition(
                key="analytics",
                title="Models & Analytics",
                description="Поздние исследовательские и аналитические модули",
                route="/analytics",
                phase="v5",
            ),
        ]
    )
    return registry

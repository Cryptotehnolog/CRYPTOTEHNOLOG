from cryptotechnolog.dashboard.registry import (
    DashboardModuleDefinition,
    DashboardModuleStatus,
    ModuleAvailabilityRegistry,
    create_default_module_registry,
)


class TestModuleAvailabilityRegistry:
    def test_default_registry_contains_overview(self):
        registry = create_default_module_registry()

        overview = registry.get_module("overview")

        assert overview.key == "overview"
        assert overview.status == DashboardModuleStatus.READ_ONLY

    def test_set_status_updates_system_registry(self):
        registry = ModuleAvailabilityRegistry(
            definitions=[
                DashboardModuleDefinition(
                    key="risk",
                    title="Risk",
                    description="Risk module",
                    route="/risk",
                    phase="v2",
                )
            ]
        )

        registry.set_status(
            "risk",
            DashboardModuleStatus.RESTRICTED,
            reason="Требуется отдельная роль оператора",
        )

        risk = registry.get_module("risk")
        assert risk.status == DashboardModuleStatus.RESTRICTED
        assert risk.status_reason == "Требуется отдельная роль оператора"

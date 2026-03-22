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

    def test_default_registry_reflects_current_mainline_contours(self):
        registry = create_default_module_registry()

        module_keys = {module.key for module in registry.list_modules()}

        assert "opportunity" in module_keys
        assert "orchestration" in module_keys
        assert "position-expansion" in module_keys
        assert "portfolio-governor" in module_keys
        assert "portfolio" not in module_keys
        assert "strategies" not in module_keys

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

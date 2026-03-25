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

    def test_default_registry_marks_control_plane_as_read_only(self):
        registry = create_default_module_registry()

        control_plane = registry.get_module("control-plane")

        assert control_plane.key == "control-plane"
        assert control_plane.status == DashboardModuleStatus.READ_ONLY

    def test_default_registry_marks_health_observability_as_read_only(self):
        registry = create_default_module_registry()

        health_observability = registry.get_module("health-observability")

        assert health_observability.key == "health-observability"
        assert health_observability.status == DashboardModuleStatus.READ_ONLY

    def test_default_registry_marks_config_events_as_read_only(self):
        registry = create_default_module_registry()

        config_events = registry.get_module("config-events")

        assert config_events.key == "config-events"
        assert config_events.status == DashboardModuleStatus.READ_ONLY

    def test_default_registry_marks_operator_gate_as_read_only(self):
        registry = create_default_module_registry()

        operator_gate = registry.get_module("operator-gate")

        assert operator_gate.key == "operator-gate"
        assert operator_gate.status == DashboardModuleStatus.READ_ONLY

    def test_default_registry_marks_risk_as_read_only(self):
        registry = create_default_module_registry()

        risk = registry.get_module("risk")

        assert risk.key == "risk"
        assert risk.status == DashboardModuleStatus.READ_ONLY

    def test_default_registry_marks_signals_as_read_only(self):
        registry = create_default_module_registry()

        signals = registry.get_module("signals")

        assert signals.key == "signals"
        assert signals.status == DashboardModuleStatus.READ_ONLY

    def test_default_registry_marks_strategy_as_read_only(self):
        registry = create_default_module_registry()

        strategy = registry.get_module("strategy")

        assert strategy.key == "strategy"
        assert strategy.status == DashboardModuleStatus.READ_ONLY

    def test_default_registry_marks_execution_as_read_only(self):
        registry = create_default_module_registry()

        execution = registry.get_module("execution")

        assert execution.key == "execution"
        assert execution.status == DashboardModuleStatus.READ_ONLY

    def test_default_registry_marks_oms_as_read_only(self):
        registry = create_default_module_registry()

        oms = registry.get_module("oms")

        assert oms.key == "oms"
        assert oms.status == DashboardModuleStatus.READ_ONLY

    def test_default_registry_marks_manager_as_read_only(self):
        registry = create_default_module_registry()

        manager = registry.get_module("manager")

        assert manager.key == "manager"
        assert manager.status == DashboardModuleStatus.READ_ONLY

    def test_default_registry_marks_validation_as_read_only(self):
        registry = create_default_module_registry()

        validation = registry.get_module("validation")

        assert validation.key == "validation"
        assert validation.status == DashboardModuleStatus.READ_ONLY

    def test_default_registry_marks_paper_as_read_only(self):
        registry = create_default_module_registry()

        paper = registry.get_module("paper")

        assert paper.key == "paper"
        assert paper.status == DashboardModuleStatus.READ_ONLY

    def test_default_registry_marks_backtest_as_read_only(self):
        registry = create_default_module_registry()

        backtest = registry.get_module("backtest")

        assert backtest.key == "backtest"
        assert backtest.status == DashboardModuleStatus.READ_ONLY

    def test_default_registry_marks_reporting_as_read_only(self):
        registry = create_default_module_registry()

        reporting = registry.get_module("reporting")

        assert reporting.key == "reporting"
        assert reporting.status == DashboardModuleStatus.READ_ONLY

    def test_default_registry_marks_opportunity_as_read_only(self):
        registry = create_default_module_registry()

        opportunity = registry.get_module("opportunity")

        assert opportunity.key == "opportunity"
        assert opportunity.status == DashboardModuleStatus.READ_ONLY

    def test_default_registry_marks_orchestration_as_read_only(self):
        registry = create_default_module_registry()

        orchestration = registry.get_module("orchestration")

        assert orchestration.key == "orchestration"
        assert orchestration.status == DashboardModuleStatus.READ_ONLY

    def test_default_registry_marks_position_expansion_as_read_only(self):
        registry = create_default_module_registry()

        position_expansion = registry.get_module("position-expansion")

        assert position_expansion.key == "position-expansion"
        assert position_expansion.status == DashboardModuleStatus.READ_ONLY

    def test_default_registry_marks_portfolio_governor_as_read_only(self):
        registry = create_default_module_registry()

        portfolio_governor = registry.get_module("portfolio-governor")

        assert portfolio_governor.key == "portfolio-governor"
        assert portfolio_governor.status == DashboardModuleStatus.READ_ONLY

    def test_default_registry_reflects_current_mainline_contours(self):
        registry = create_default_module_registry()

        module_keys = {module.key for module in registry.list_modules()}

        assert "opportunity" in module_keys
        assert "oms" in module_keys
        assert "manager" in module_keys
        assert "validation" in module_keys
        assert "paper" in module_keys
        assert "backtest" in module_keys
        assert "reporting" in module_keys
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

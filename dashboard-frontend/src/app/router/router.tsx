import { createBrowserRouter } from "react-router-dom";

import { DashboardShell } from "../layout/DashboardShell";
import { TerminalShell } from "../layout/TerminalShell";
import { OverviewPage } from "../../modules/overview/pages/OverviewPage";
import { ControlPlanePage } from "../../modules/control-plane/pages/ControlPlanePage";
import { HealthObservabilityPage } from "../../modules/health-observability/pages/HealthObservabilityPage";
import { ConfigurationEventsPage } from "../../modules/configuration-events/pages/ConfigurationEventsPage";
import { OperatorGatePage } from "../../modules/operator-gate/pages/OperatorGatePage";
import { RiskPage } from "../../modules/risk/pages/RiskPage";
import { SignalsPage } from "../../modules/signals/pages/SignalsPage";
import { StrategyPage } from "../../modules/strategy/pages/StrategyPage";
import { ExecutionPage } from "../../modules/execution/pages/ExecutionPage";
import { OpportunityPage } from "../../modules/opportunity/pages/OpportunityPage";
import { OrchestrationPage } from "../../modules/orchestration/pages/OrchestrationPage";
import { PositionExpansionPage } from "../../modules/position-expansion/pages/PositionExpansionPage";
import { PortfolioGovernorPage } from "../../modules/portfolio-governor/pages/PortfolioGovernorPage";
import { OmsPage } from "../../modules/oms/pages/OmsPage";
import { ManagerPage } from "../../modules/manager/pages/ManagerPage";
import { ValidationPage } from "../../modules/validation/pages/ValidationPage";
import { PaperPage } from "../../modules/paper/pages/PaperPage";
import { BacktestPage } from "../../modules/backtest/pages/BacktestPage";
import { ReportingPage } from "../../modules/reporting/pages/ReportingPage";
import { TerminalPage } from "../../modules/terminal/pages/TerminalPage";
import { TerminalPositionsPage } from "../../modules/terminal/pages/TerminalPositionsPage";
import { TerminalSettingsPage } from "../../modules/terminal/pages/TerminalSettingsPage";
import { ModulePlaceholderPage } from "../../modules/placeholder/pages/ModulePlaceholderPage";
import { navigationItems } from "../../shared/config/navigation";

const placeholderRoutes = navigationItems
  .filter(
    (item) =>
      item.key !== "overview" &&
      item.key !== "control-plane" &&
      item.key !== "health-observability" &&
      item.key !== "config-events" &&
      item.key !== "operator-gate" &&
      item.key !== "risk" &&
      item.key !== "signals" &&
      item.key !== "strategy" &&
      item.key !== "execution" &&
      item.key !== "opportunity" &&
      item.key !== "orchestration" &&
      item.key !== "position-expansion" &&
      item.key !== "portfolio-governor" &&
      item.key !== "oms" &&
      item.key !== "manager" &&
      item.key !== "validation" &&
      item.key !== "paper" &&
      item.key !== "backtest" &&
      item.key !== "reporting",
  )
  .map((item) => ({
    path: item.route.slice(1),
    element: <ModulePlaceholderPage item={item} />,
  }));

export const router = createBrowserRouter([
  {
    path: "/terminal",
    element: <TerminalShell />,
    children: [
      {
        index: true,
        element: <TerminalPage />,
      },
      {
        path: "positions",
        element: <TerminalPositionsPage />,
      },
      {
        path: "settings",
        element: <TerminalSettingsPage />,
      },
    ],
  },
  {
    path: "/",
    element: <DashboardShell />,
    children: [
      {
        index: true,
        element: <OverviewPage />,
      },
      {
        path: "overview",
        element: <OverviewPage />,
      },
      {
        path: "control-plane",
        element: <ControlPlanePage />,
      },
      {
        path: "health",
        element: <HealthObservabilityPage />,
      },
      {
        path: "config-events",
        element: <ConfigurationEventsPage />,
      },
      {
        path: "operator-gate",
        element: <OperatorGatePage />,
      },
      {
        path: "risk",
        element: <RiskPage />,
      },
      {
        path: "signals",
        element: <SignalsPage />,
      },
      {
        path: "strategy",
        element: <StrategyPage />,
      },
      {
        path: "execution",
        element: <ExecutionPage />,
      },
      {
        path: "opportunity",
        element: <OpportunityPage />,
      },
      {
        path: "orchestration",
        element: <OrchestrationPage />,
      },
      {
        path: "position-expansion",
        element: <PositionExpansionPage />,
      },
      {
        path: "portfolio-governor",
        element: <PortfolioGovernorPage />,
      },
      {
        path: "oms",
        element: <OmsPage />,
      },
      {
        path: "manager",
        element: <ManagerPage />,
      },
      {
        path: "validation",
        element: <ValidationPage />,
      },
      {
        path: "paper",
        element: <PaperPage />,
      },
      {
        path: "backtest",
        element: <BacktestPage />,
      },
      {
        path: "reporting",
        element: <ReportingPage />,
      },
      ...placeholderRoutes,
    ],
  },
]);

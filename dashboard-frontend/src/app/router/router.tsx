import { createBrowserRouter } from "react-router-dom";

import { DashboardShell } from "../layout/DashboardShell";
import { OverviewPage } from "../../modules/overview/pages/OverviewPage";
import { ModulePlaceholderPage } from "../../modules/placeholder/pages/ModulePlaceholderPage";
import { navigationItems } from "../../shared/config/navigation";

const placeholderRoutes = navigationItems
  .filter((item) => item.key !== "overview")
  .map((item) => ({
    path: item.route.slice(1),
    element: <ModulePlaceholderPage item={item} />,
  }));

export const router = createBrowserRouter([
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
      ...placeholderRoutes,
    ],
  },
]);

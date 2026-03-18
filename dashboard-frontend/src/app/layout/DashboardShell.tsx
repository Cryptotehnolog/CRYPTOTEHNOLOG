import { Outlet, useLocation } from "react-router-dom";

import { SideNavigation } from "./SideNavigation";
import { TopStatusBar } from "./TopStatusBar";
import {
  contentArea,
  contentViewport,
  shellLayout,
  sideRail,
} from "./DashboardShell.css";

export function DashboardShell() {
  const location = useLocation();

  return (
    <div className={shellLayout}>
      <aside className={sideRail}>
        <SideNavigation currentPath={location.pathname} />
      </aside>
      <div className={contentArea}>
        <TopStatusBar currentPath={location.pathname} />
        <main className={contentViewport}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}

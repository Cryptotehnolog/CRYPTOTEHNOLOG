import { Outlet } from "react-router-dom";

import { SideNavigation } from "./SideNavigation";
import { TopStatusBar } from "./TopStatusBar";
import {
  contentArea,
  contentViewport,
  shellLayout,
  sideRail,
} from "./DashboardShell.css";

export function DashboardShell() {
  return (
    <div className={shellLayout}>
      <aside className={sideRail}>
        <SideNavigation />
      </aside>
      <div className={contentArea}>
        <TopStatusBar />
        <main className={contentViewport}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}

import { getJson } from "../../../shared/api/dashboardClient";
import type { ManagerSummaryResponse } from "../../../shared/types/dashboard";

export function getManagerSummary() {
  return getJson<ManagerSummaryResponse>("/dashboard/manager-summary");
}

import { getJson } from "../../../shared/api/dashboardClient";
import type { OrchestrationSummaryResponse } from "../../../shared/types/dashboard";

export function getOrchestrationSummary() {
  return getJson<OrchestrationSummaryResponse>("/dashboard/orchestration-summary");
}

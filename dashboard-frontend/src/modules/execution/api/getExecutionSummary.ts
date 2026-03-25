import { getJson } from "../../../shared/api/dashboardClient";
import type { ExecutionSummaryResponse } from "../../../shared/types/dashboard";

export function getExecutionSummary() {
  return getJson<ExecutionSummaryResponse>("/dashboard/execution-summary");
}

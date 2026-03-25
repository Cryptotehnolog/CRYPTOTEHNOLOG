import { getJson } from "../../../shared/api/dashboardClient";
import type { RiskSummaryResponse } from "../../../shared/types/dashboard";

export function getRiskSummary() {
  return getJson<RiskSummaryResponse>("/dashboard/risk-summary");
}

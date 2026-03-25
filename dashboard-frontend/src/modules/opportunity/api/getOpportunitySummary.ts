import { getJson } from "../../../shared/api/dashboardClient";
import type { OpportunitySummaryResponse } from "../../../shared/types/dashboard";

export function getOpportunitySummary() {
  return getJson<OpportunitySummaryResponse>("/dashboard/opportunity-summary");
}

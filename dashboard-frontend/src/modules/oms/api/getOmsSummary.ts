import { getJson } from "../../../shared/api/dashboardClient";
import type { OmsSummaryResponse } from "../../../shared/types/dashboard";

export function getOmsSummary() {
  return getJson<OmsSummaryResponse>("/dashboard/oms-summary");
}

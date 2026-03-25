import { getJson } from "../../../shared/api/dashboardClient";
import type { ReportingSummaryResponse } from "../../../shared/types/dashboard";

export function getReportingSummary(): Promise<ReportingSummaryResponse> {
  return getJson<ReportingSummaryResponse>("/dashboard/reporting-summary");
}

import { getJson } from "../../../shared/api/dashboardClient";
import type { PaperSummaryResponse } from "../../../shared/types/dashboard";

export function getPaperSummary() {
  return getJson<PaperSummaryResponse>("/dashboard/paper-summary");
}

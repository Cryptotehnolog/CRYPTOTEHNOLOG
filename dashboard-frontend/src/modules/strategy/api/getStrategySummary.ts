import { getJson } from "../../../shared/api/dashboardClient";
import type { StrategySummaryResponse } from "../../../shared/types/dashboard";

export function getStrategySummary() {
  return getJson<StrategySummaryResponse>("/dashboard/strategy-summary");
}

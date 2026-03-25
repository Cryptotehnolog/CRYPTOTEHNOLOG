import { getJson } from "../../../shared/api/dashboardClient";
import type { SignalsSummaryResponse } from "../../../shared/types/dashboard";

export function getSignalsSummary() {
  return getJson<SignalsSummaryResponse>("/dashboard/signals-summary");
}

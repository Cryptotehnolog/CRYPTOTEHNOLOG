import { getJson } from "../../../shared/api/dashboardClient";
import type { OpenPositionsResponse } from "../../../shared/types/dashboard";

export function getOpenPositions() {
  return getJson<OpenPositionsResponse>("/dashboard/open-positions");
}

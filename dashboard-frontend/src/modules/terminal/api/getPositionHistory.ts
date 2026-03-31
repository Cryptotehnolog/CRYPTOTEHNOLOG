import { getJson } from "../../../shared/api/dashboardClient";
import type { PositionHistoryResponse } from "../../../shared/types/dashboard";

export function getPositionHistory() {
  return getJson<PositionHistoryResponse>("/dashboard/position-history");
}

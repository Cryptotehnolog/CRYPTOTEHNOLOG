import { getJson } from "../../../shared/api/dashboardClient";
import type { OverviewSnapshotResponse } from "../../../shared/types/dashboard";

export function getOverview() {
  return getJson<OverviewSnapshotResponse>("/dashboard/overview");
}

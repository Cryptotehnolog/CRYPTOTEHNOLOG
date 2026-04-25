import { getJson } from "../../../shared/api/dashboardClient";
import type { BybitSpotRuntimeStatusResponse } from "../../../shared/types/connectors";

export function getBybitSpotRuntimeStatus(): Promise<BybitSpotRuntimeStatusResponse> {
  return getJson<BybitSpotRuntimeStatusResponse>("/dashboard/settings/bybit-spot-runtime-status");
}

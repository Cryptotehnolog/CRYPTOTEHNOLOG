import { getJson } from "../../../shared/api/dashboardClient";
import type { BybitSpotV2DiagnosticsResponse } from "../../../shared/types/connectors";

export function getBybitSpotV2Diagnostics(): Promise<BybitSpotV2DiagnosticsResponse> {
  return getJson<BybitSpotV2DiagnosticsResponse>(
    "/dashboard/settings/bybit-spot-v2-diagnostics",
  );
}

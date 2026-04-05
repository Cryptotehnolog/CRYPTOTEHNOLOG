import { getJson } from "../../../shared/api/dashboardClient";
import type { BybitSpotConnectorDiagnosticsResponse } from "../../../shared/types/dashboard";

export function getBybitSpotConnectorDiagnostics(): Promise<BybitSpotConnectorDiagnosticsResponse> {
  return getJson<BybitSpotConnectorDiagnosticsResponse>(
    "/dashboard/settings/bybit-spot-connector-diagnostics",
  );
}

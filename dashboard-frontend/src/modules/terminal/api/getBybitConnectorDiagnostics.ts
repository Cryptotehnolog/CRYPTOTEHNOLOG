import { getJson } from "../../../shared/api/dashboardClient";
import type { BybitConnectorDiagnosticsResponse } from "../../../shared/types/dashboard";

export function getBybitConnectorDiagnostics(): Promise<BybitConnectorDiagnosticsResponse> {
  return getJson<BybitConnectorDiagnosticsResponse>(
    "/dashboard/settings/bybit-connector-diagnostics",
  );
}

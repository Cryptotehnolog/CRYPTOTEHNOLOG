import { putJson } from "../../../shared/api/dashboardClient";
import type { BybitConnectorDiagnosticsResponse } from "../../../shared/types/dashboard";

type BybitConnectorTogglePayload = {
  enabled: boolean;
};

export function updateBybitConnectorEnabled(
  payload: BybitConnectorTogglePayload,
): Promise<BybitConnectorDiagnosticsResponse> {
  return putJson<BybitConnectorDiagnosticsResponse, BybitConnectorTogglePayload>(
    "/dashboard/settings/bybit-connector-enabled",
    payload,
  );
}

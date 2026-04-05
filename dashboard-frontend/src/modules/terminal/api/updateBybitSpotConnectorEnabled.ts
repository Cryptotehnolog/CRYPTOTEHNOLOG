import { putJson } from "../../../shared/api/dashboardClient";
import type { BybitSpotConnectorDiagnosticsResponse } from "../../../shared/types/dashboard";

type BybitSpotConnectorTogglePayload = {
  enabled: boolean;
};

export function updateBybitSpotConnectorEnabled(
  payload: BybitSpotConnectorTogglePayload,
): Promise<BybitSpotConnectorDiagnosticsResponse> {
  return putJson<BybitSpotConnectorDiagnosticsResponse, BybitSpotConnectorTogglePayload>(
    "/dashboard/settings/bybit-spot-connector-enabled",
    payload,
  );
}

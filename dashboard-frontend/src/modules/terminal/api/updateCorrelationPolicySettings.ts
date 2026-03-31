import { putJson } from "../../../shared/api/dashboardClient";
import type { CorrelationPolicySettingsResponse } from "../../../shared/types/dashboard";

export function updateCorrelationPolicySettings(payload: CorrelationPolicySettingsResponse) {
  return putJson<CorrelationPolicySettingsResponse, CorrelationPolicySettingsResponse>(
    "/dashboard/settings/correlation-policy",
    payload,
  );
}

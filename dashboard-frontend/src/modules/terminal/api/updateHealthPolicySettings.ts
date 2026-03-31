import { putJson } from "../../../shared/api/dashboardClient";
import type { HealthPolicySettingsResponse } from "../../../shared/types/dashboard";

export function updateHealthPolicySettings(payload: HealthPolicySettingsResponse) {
  return putJson<HealthPolicySettingsResponse, HealthPolicySettingsResponse>(
    "/dashboard/settings/health-policy",
    payload,
  );
}

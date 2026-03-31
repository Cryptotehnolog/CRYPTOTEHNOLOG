import { putJson } from "../../../shared/api/dashboardClient";
import type { SystemStatePolicySettingsResponse } from "../../../shared/types/dashboard";

export function updateSystemStatePolicySettings(payload: SystemStatePolicySettingsResponse) {
  return putJson<SystemStatePolicySettingsResponse, SystemStatePolicySettingsResponse>(
    "/dashboard/settings/system-state-policy",
    payload,
  );
}

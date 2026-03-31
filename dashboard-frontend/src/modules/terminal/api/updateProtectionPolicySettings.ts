import { putJson } from "../../../shared/api/dashboardClient";
import type { ProtectionPolicySettingsResponse } from "../../../shared/types/dashboard";

export function updateProtectionPolicySettings(payload: ProtectionPolicySettingsResponse) {
  return putJson<ProtectionPolicySettingsResponse, ProtectionPolicySettingsResponse>(
    "/dashboard/settings/protection-policy",
    payload,
  );
}

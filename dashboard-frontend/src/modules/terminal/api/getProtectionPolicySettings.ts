import { getJson } from "../../../shared/api/dashboardClient";
import type { ProtectionPolicySettingsResponse } from "../../../shared/types/dashboard";

export function getProtectionPolicySettings() {
  return getJson<ProtectionPolicySettingsResponse>("/dashboard/settings/protection-policy");
}

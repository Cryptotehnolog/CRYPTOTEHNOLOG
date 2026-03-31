import { getJson } from "../../../shared/api/dashboardClient";
import type { HealthPolicySettingsResponse } from "../../../shared/types/dashboard";

export function getHealthPolicySettings() {
  return getJson<HealthPolicySettingsResponse>("/dashboard/settings/health-policy");
}

import { getJson } from "../../../shared/api/dashboardClient";
import type { SystemStatePolicySettingsResponse } from "../../../shared/types/dashboard";

export function getSystemStatePolicySettings() {
  return getJson<SystemStatePolicySettingsResponse>("/dashboard/settings/system-state-policy");
}

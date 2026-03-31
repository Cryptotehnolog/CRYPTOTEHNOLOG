import { getJson } from "../../../shared/api/dashboardClient";
import type { ReliabilityPolicySettingsResponse } from "../../../shared/types/dashboard";

export function getReliabilityPolicySettings() {
  return getJson<ReliabilityPolicySettingsResponse>("/dashboard/settings/reliability-policy");
}

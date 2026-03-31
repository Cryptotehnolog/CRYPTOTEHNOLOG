import { getJson } from "../../../shared/api/dashboardClient";
import type { CorrelationPolicySettingsResponse } from "../../../shared/types/dashboard";

export function getCorrelationPolicySettings() {
  return getJson<CorrelationPolicySettingsResponse>("/dashboard/settings/correlation-policy");
}

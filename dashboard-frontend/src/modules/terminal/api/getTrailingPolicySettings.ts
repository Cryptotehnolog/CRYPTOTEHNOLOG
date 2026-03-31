import { getJson } from "../../../shared/api/dashboardClient";
import type { TrailingPolicySettingsResponse } from "../../../shared/types/dashboard";

export function getTrailingPolicySettings() {
  return getJson<TrailingPolicySettingsResponse>("/dashboard/settings/trailing-policy");
}

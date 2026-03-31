import { getJson } from "../../../shared/api/dashboardClient";
import type { UniversePolicySettingsResponse } from "../../../shared/types/dashboard";

export function getUniversePolicySettings() {
  return getJson<UniversePolicySettingsResponse>("/dashboard/settings/universe-policy");
}

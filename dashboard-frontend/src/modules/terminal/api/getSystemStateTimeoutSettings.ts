import { getJson } from "../../../shared/api/dashboardClient";
import type { SystemStateTimeoutSettingsResponse } from "../../../shared/types/dashboard";

export function getSystemStateTimeoutSettings() {
  return getJson<SystemStateTimeoutSettingsResponse>("/dashboard/settings/system-state-timeouts");
}

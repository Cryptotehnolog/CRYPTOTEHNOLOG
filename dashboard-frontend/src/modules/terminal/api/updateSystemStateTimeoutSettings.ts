import { putJson } from "../../../shared/api/dashboardClient";
import type { SystemStateTimeoutSettingsResponse } from "../../../shared/types/dashboard";

export function updateSystemStateTimeoutSettings(payload: SystemStateTimeoutSettingsResponse) {
  return putJson<SystemStateTimeoutSettingsResponse, SystemStateTimeoutSettingsResponse>(
    "/dashboard/settings/system-state-timeouts",
    payload,
  );
}

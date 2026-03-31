import { putJson } from "../../../shared/api/dashboardClient";
import type { UniversePolicySettingsResponse } from "../../../shared/types/dashboard";

export function updateUniversePolicySettings(payload: UniversePolicySettingsResponse) {
  return putJson<UniversePolicySettingsResponse, UniversePolicySettingsResponse>(
    "/dashboard/settings/universe-policy",
    payload,
  );
}

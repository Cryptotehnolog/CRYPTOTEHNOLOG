import { putJson } from "../../../shared/api/dashboardClient";
import type { TrailingPolicySettingsResponse } from "../../../shared/types/dashboard";

export function updateTrailingPolicySettings(payload: TrailingPolicySettingsResponse) {
  return putJson<TrailingPolicySettingsResponse, TrailingPolicySettingsResponse>(
    "/dashboard/settings/trailing-policy",
    payload,
  );
}

import { putJson } from "../../../shared/api/dashboardClient";
import type { ReliabilityPolicySettingsResponse } from "../../../shared/types/dashboard";

export function updateReliabilityPolicySettings(payload: ReliabilityPolicySettingsResponse) {
  return putJson<ReliabilityPolicySettingsResponse, ReliabilityPolicySettingsResponse>(
    "/dashboard/settings/reliability-policy",
    payload,
  );
}

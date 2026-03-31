import { getJson } from "../../../shared/api/dashboardClient";
import type { ManualApprovalPolicySettingsResponse } from "../../../shared/types/dashboard";

export function getManualApprovalPolicySettings() {
  return getJson<ManualApprovalPolicySettingsResponse>(
    "/dashboard/settings/manual-approval-policy",
  );
}

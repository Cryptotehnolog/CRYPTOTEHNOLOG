import { putJson } from "../../../shared/api/dashboardClient";
import type { ManualApprovalPolicySettingsResponse } from "../../../shared/types/dashboard";

export function updateManualApprovalPolicySettings(
  payload: ManualApprovalPolicySettingsResponse,
) {
  return putJson<ManualApprovalPolicySettingsResponse, ManualApprovalPolicySettingsResponse>(
    "/dashboard/settings/manual-approval-policy",
    payload,
  );
}

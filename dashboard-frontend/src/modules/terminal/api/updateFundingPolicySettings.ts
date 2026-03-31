import { putJson } from "../../../shared/api/dashboardClient";
import type { FundingPolicySettingsResponse } from "../../../shared/types/dashboard";

export function updateFundingPolicySettings(payload: FundingPolicySettingsResponse) {
  return putJson<FundingPolicySettingsResponse, FundingPolicySettingsResponse>(
    "/dashboard/settings/funding-policy",
    payload,
  );
}

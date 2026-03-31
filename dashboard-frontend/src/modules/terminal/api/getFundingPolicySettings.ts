import { getJson } from "../../../shared/api/dashboardClient";
import type { FundingPolicySettingsResponse } from "../../../shared/types/dashboard";

export function getFundingPolicySettings() {
  return getJson<FundingPolicySettingsResponse>("/dashboard/settings/funding-policy");
}

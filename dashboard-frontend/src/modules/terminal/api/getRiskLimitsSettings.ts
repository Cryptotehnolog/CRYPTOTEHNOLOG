import { getJson } from "../../../shared/api/dashboardClient";
import type { RiskLimitsSettingsResponse } from "../../../shared/types/dashboard";

export function getRiskLimitsSettings() {
  return getJson<RiskLimitsSettingsResponse>("/dashboard/settings/risk-limits");
}

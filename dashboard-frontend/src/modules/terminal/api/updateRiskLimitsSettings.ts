import { putJson } from "../../../shared/api/dashboardClient";
import type { RiskLimitsSettingsResponse } from "../../../shared/types/dashboard";

export function updateRiskLimitsSettings(payload: RiskLimitsSettingsResponse) {
  return putJson<RiskLimitsSettingsResponse, RiskLimitsSettingsResponse>(
    "/dashboard/settings/risk-limits",
    payload,
  );
}

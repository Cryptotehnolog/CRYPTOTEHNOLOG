import { getJson } from "../../../shared/api/dashboardClient";
import type { DecisionChainSettingsResponse } from "../../../shared/types/dashboard";

export function getDecisionChainSettings() {
  return getJson<DecisionChainSettingsResponse>("/dashboard/settings/decision-thresholds");
}

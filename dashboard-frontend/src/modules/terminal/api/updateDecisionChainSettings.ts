import { putJson } from "../../../shared/api/dashboardClient";
import type { DecisionChainSettingsResponse } from "../../../shared/types/dashboard";

export function updateDecisionChainSettings(payload: DecisionChainSettingsResponse) {
  return putJson<DecisionChainSettingsResponse, DecisionChainSettingsResponse>(
    "/dashboard/settings/decision-thresholds",
    payload,
  );
}

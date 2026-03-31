import type { WorkflowTimeoutsSettingsResponse } from "../../../shared/types/dashboard";
import { getJson } from "../../../shared/api/dashboardClient";

export function getWorkflowTimeoutSettings(): Promise<WorkflowTimeoutsSettingsResponse> {
  return getJson<WorkflowTimeoutsSettingsResponse>("/dashboard/settings/workflow-timeouts");
}

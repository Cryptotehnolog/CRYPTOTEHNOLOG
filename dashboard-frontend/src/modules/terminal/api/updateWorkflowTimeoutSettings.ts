import type { WorkflowTimeoutsSettingsResponse } from "../../../shared/types/dashboard";
import { putJson } from "../../../shared/api/dashboardClient";

export function updateWorkflowTimeoutSettings(
  payload: WorkflowTimeoutsSettingsResponse,
): Promise<WorkflowTimeoutsSettingsResponse> {
  return putJson<WorkflowTimeoutsSettingsResponse, WorkflowTimeoutsSettingsResponse>(
    "/dashboard/settings/workflow-timeouts",
    payload,
  );
}

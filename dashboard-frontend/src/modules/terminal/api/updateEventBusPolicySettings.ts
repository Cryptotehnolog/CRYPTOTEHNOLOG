import { putJson } from "../../../shared/api/dashboardClient";
import type { EventBusPolicySettingsResponse } from "../../../shared/types/dashboard";

export function updateEventBusPolicySettings(payload: EventBusPolicySettingsResponse) {
  return putJson<EventBusPolicySettingsResponse, EventBusPolicySettingsResponse>(
    "/dashboard/settings/event-bus-policy",
    payload,
  );
}

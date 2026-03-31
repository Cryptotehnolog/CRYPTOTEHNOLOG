import { getJson } from "../../../shared/api/dashboardClient";
import type { EventBusPolicySettingsResponse } from "../../../shared/types/dashboard";

export function getEventBusPolicySettings() {
  return getJson<EventBusPolicySettingsResponse>("/dashboard/settings/event-bus-policy");
}

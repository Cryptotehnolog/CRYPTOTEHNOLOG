import { getJson } from "../../../shared/api/dashboardClient";
import type { LiveFeedPolicySettingsResponse } from "../../../shared/types/dashboard";

export function getLiveFeedPolicySettings(): Promise<LiveFeedPolicySettingsResponse> {
  return getJson<LiveFeedPolicySettingsResponse>("/dashboard/settings/live-feed-policy");
}

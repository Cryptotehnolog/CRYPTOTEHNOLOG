import { putJson } from "../../../shared/api/dashboardClient";
import type { LiveFeedPolicySettingsResponse } from "../../../shared/types/dashboard";

export function updateLiveFeedPolicySettings(
  payload: LiveFeedPolicySettingsResponse,
): Promise<LiveFeedPolicySettingsResponse> {
  return putJson<LiveFeedPolicySettingsResponse, LiveFeedPolicySettingsResponse>(
    "/dashboard/settings/live-feed-policy",
    payload,
  );
}

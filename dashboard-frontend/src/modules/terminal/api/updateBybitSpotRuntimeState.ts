import { putJson } from "../../../shared/api/dashboardClient";
import type { BybitSpotRuntimeStatusResponse } from "../../../shared/types/connectors";

type BybitSpotRuntimeStatePayload = {
  enabled: boolean;
};

export function updateBybitSpotRuntimeState(
  payload: BybitSpotRuntimeStatePayload,
): Promise<BybitSpotRuntimeStatusResponse> {
  return putJson<BybitSpotRuntimeStatusResponse, BybitSpotRuntimeStatePayload>(
    "/dashboard/settings/bybit-spot-runtime-state",
    payload,
  );
}

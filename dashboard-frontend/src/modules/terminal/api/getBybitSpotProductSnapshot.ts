import { getJson } from "../../../shared/api/dashboardClient";
import type { BybitSpotProductSnapshotResponse } from "../../../shared/types/connectors";

export function getBybitSpotProductSnapshot(): Promise<BybitSpotProductSnapshotResponse> {
  return getJson<BybitSpotProductSnapshotResponse>(
    "/dashboard/settings/bybit-spot-product-snapshot",
  );
}

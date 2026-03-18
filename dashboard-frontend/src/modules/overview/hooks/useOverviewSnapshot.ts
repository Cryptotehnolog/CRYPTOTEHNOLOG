import { useQuery } from "@tanstack/react-query";

import { getOverview } from "../api/getOverview";

export function useOverviewSnapshot() {
  return useQuery({
    queryKey: ["dashboard", "overview"],
    queryFn: getOverview,
  });
}

import { useQuery } from "@tanstack/react-query";

import { getPositionHistory } from "../api/getPositionHistory";

export function usePositionHistory() {
  return useQuery({
    queryKey: ["dashboard", "position-history"],
    queryFn: getPositionHistory,
  });
}

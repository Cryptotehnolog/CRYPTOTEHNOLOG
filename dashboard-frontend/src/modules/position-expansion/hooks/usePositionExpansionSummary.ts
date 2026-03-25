import { useQuery } from "@tanstack/react-query";

import { getPositionExpansionSummary } from "../api/getPositionExpansionSummary";

export function usePositionExpansionSummary() {
  return useQuery({
    queryKey: ["dashboard", "position-expansion-summary"],
    queryFn: getPositionExpansionSummary,
  });
}

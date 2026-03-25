import { useQuery } from "@tanstack/react-query";

import { getOpportunitySummary } from "../api/getOpportunitySummary";

export function useOpportunitySummary() {
  return useQuery({
    queryKey: ["dashboard", "opportunity-summary"],
    queryFn: getOpportunitySummary,
  });
}

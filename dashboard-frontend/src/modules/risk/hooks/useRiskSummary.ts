import { useQuery } from "@tanstack/react-query";

import { getRiskSummary } from "../api/getRiskSummary";

export function useRiskSummary() {
  return useQuery({
    queryKey: ["dashboard", "risk-summary"],
    queryFn: getRiskSummary,
  });
}

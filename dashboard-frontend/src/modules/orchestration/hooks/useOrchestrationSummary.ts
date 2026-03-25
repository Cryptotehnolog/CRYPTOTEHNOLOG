import { useQuery } from "@tanstack/react-query";

import { getOrchestrationSummary } from "../api/getOrchestrationSummary";

export function useOrchestrationSummary() {
  return useQuery({
    queryKey: ["dashboard", "orchestration-summary"],
    queryFn: getOrchestrationSummary,
  });
}

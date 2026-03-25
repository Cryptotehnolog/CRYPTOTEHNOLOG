import { useQuery } from "@tanstack/react-query";

import { getExecutionSummary } from "../api/getExecutionSummary";

export function useExecutionSummary() {
  return useQuery({
    queryKey: ["dashboard", "execution-summary"],
    queryFn: getExecutionSummary,
  });
}

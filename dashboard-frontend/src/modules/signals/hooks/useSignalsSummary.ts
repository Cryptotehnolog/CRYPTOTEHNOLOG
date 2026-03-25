import { useQuery } from "@tanstack/react-query";

import { getSignalsSummary } from "../api/getSignalsSummary";

export function useSignalsSummary() {
  return useQuery({
    queryKey: ["dashboard", "signals-summary"],
    queryFn: getSignalsSummary,
  });
}

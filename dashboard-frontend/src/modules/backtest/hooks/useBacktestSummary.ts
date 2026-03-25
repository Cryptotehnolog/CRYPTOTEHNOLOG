import { useQuery } from "@tanstack/react-query";

import { getBacktestSummary } from "../api/getBacktestSummary";

export function useBacktestSummary() {
  return useQuery({
    queryKey: ["dashboard", "backtest-summary"],
    queryFn: getBacktestSummary,
    staleTime: 15_000,
  });
}

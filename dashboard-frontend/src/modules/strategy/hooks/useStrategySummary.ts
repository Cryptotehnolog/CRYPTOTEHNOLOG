import { useQuery } from "@tanstack/react-query";

import { getStrategySummary } from "../api/getStrategySummary";

export function useStrategySummary() {
  return useQuery({
    queryKey: ["dashboard", "strategy-summary"],
    queryFn: getStrategySummary,
  });
}

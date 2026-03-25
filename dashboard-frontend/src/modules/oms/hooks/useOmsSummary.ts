import { useQuery } from "@tanstack/react-query";

import { getOmsSummary } from "../api/getOmsSummary";

export function useOmsSummary() {
  return useQuery({
    queryKey: ["dashboard", "oms-summary"],
    queryFn: getOmsSummary,
  });
}

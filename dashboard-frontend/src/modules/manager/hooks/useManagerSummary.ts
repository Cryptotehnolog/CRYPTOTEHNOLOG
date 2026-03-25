import { useQuery } from "@tanstack/react-query";

import { getManagerSummary } from "../api/getManagerSummary";

export function useManagerSummary() {
  return useQuery({
    queryKey: ["dashboard", "manager-summary"],
    queryFn: getManagerSummary,
  });
}

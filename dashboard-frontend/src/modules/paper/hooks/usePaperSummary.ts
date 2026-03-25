import { useQuery } from "@tanstack/react-query";

import { getPaperSummary } from "../api/getPaperSummary";

export function usePaperSummary() {
  return useQuery({
    queryKey: ["dashboard", "paper-summary"],
    queryFn: getPaperSummary,
    staleTime: 15_000,
  });
}

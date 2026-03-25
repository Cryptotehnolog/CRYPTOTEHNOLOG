import { useQuery } from "@tanstack/react-query";

import { getPortfolioGovernorSummary } from "../api/getPortfolioGovernorSummary";

export function usePortfolioGovernorSummary() {
  return useQuery({
    queryKey: ["dashboard", "portfolio-governor-summary"],
    queryFn: getPortfolioGovernorSummary,
  });
}

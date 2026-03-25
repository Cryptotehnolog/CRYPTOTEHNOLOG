import { useQuery } from "@tanstack/react-query";

import { getReportingSummary } from "../api/getReportingSummary";

export function useReportingSummary() {
  return useQuery({
    queryKey: ["dashboard", "reporting-summary"],
    queryFn: getReportingSummary,
  });
}

import { useQuery } from "@tanstack/react-query";

import { getValidationSummary } from "../api/getValidationSummary";

export function useValidationSummary() {
  return useQuery({
    queryKey: ["dashboard", "validation-summary"],
    queryFn: getValidationSummary,
    staleTime: 15_000,
  });
}

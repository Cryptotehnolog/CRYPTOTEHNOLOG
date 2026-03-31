import { useQuery } from "@tanstack/react-query";

import { getOpenPositions } from "../api/getOpenPositions";

export function useOpenPositions() {
  return useQuery({
    queryKey: ["dashboard", "open-positions"],
    queryFn: getOpenPositions,
  });
}

import type { PositionExpansionSummaryResponse } from "../../../shared/types/dashboard";

export async function getPositionExpansionSummary(): Promise<PositionExpansionSummaryResponse> {
  const response = await fetch("/dashboard/position-expansion-summary");

  if (!response.ok) {
    throw new Error("Не удалось загрузить сводку по расширению позиции.");
  }

  return (await response.json()) as PositionExpansionSummaryResponse;
}

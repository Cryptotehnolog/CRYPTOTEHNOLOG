import type { PortfolioGovernorSummaryResponse } from "../../../shared/types/dashboard";

export async function getPortfolioGovernorSummary(): Promise<PortfolioGovernorSummaryResponse> {
  const response = await fetch("/dashboard/portfolio-governor-summary");

  if (!response.ok) {
    throw new Error("Не удалось загрузить сводку по портфельному контуру.");
  }

  return (await response.json()) as PortfolioGovernorSummaryResponse;
}

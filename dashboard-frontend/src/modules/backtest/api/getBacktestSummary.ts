import { getJson } from "../../../shared/api/dashboardClient";
import type { BacktestSummaryResponse } from "../../../shared/types/dashboard";

export function getBacktestSummary() {
  return getJson<BacktestSummaryResponse>("/dashboard/backtest-summary");
}

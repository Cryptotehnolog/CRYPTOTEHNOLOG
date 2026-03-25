import { getJson } from "../../../shared/api/dashboardClient";
import type { ValidationSummaryResponse } from "../../../shared/types/dashboard";

export function getValidationSummary() {
  return getJson<ValidationSummaryResponse>("/dashboard/validation-summary");
}

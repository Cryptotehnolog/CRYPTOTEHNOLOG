import type { OverviewSnapshotResponse } from "../../../shared/types/dashboard";
import {
  formatCircuitBreakerState,
  formatHealthStatus,
} from "../../../shared/lib/dashboardText";

export type HealthObservabilityViewModel = {
  moduleState: "inactive" | "read-only" | "active" | "restricted";
  statusBadges: Array<{
    label: string;
    tone: "neutral" | "accent" | "success" | "warning" | "danger";
  }>;
  healthSummary: Array<{ label: string; value: string | number }>;
  unhealthyComponents: string[];
  circuitBreakers: Array<{
    name: string;
    state: string;
    failureCount: number;
    successCount: number;
    failureThreshold: number;
    recoveryTimeout: number;
  }>;
};

function mapHealthTone(
  overallStatus: string,
): "neutral" | "accent" | "success" | "warning" | "danger" {
  if (overallStatus === "healthy") {
    return "success";
  }
  if (overallStatus === "degraded") {
    return "warning";
  }
  if (overallStatus === "unhealthy") {
    return "danger";
  }
  return "neutral";
}

export function mapHealthObservability(
  snapshot: OverviewSnapshotResponse,
): HealthObservabilityViewModel {
  const module =
    snapshot.module_availability.find((item) => item.key === "health-observability") ??
    null;

  return {
    moduleState: module?.status ?? "inactive",
    statusBadges: [
      {
        label: formatHealthStatus(snapshot.health_summary.overall_status),
        tone: mapHealthTone(snapshot.health_summary.overall_status),
      },
      {
        label:
          snapshot.circuit_breaker_summary.length > 0
            ? `защитных выключателей: ${snapshot.circuit_breaker_summary.length}`
            : "защитные выключатели: нет",
        tone:
          snapshot.circuit_breaker_summary.length > 0
            ? "warning"
            : "neutral",
      },
    ],
    healthSummary: [
      {
        label: "Общее состояние",
        value: formatHealthStatus(snapshot.health_summary.overall_status),
      },
      {
        label: "Компонентов под контролем",
        value: snapshot.health_summary.component_count,
      },
      {
        label: "Время снимка",
        value:
          snapshot.health_summary.timestamp === null
            ? "нет данных"
            : new Date(snapshot.health_summary.timestamp * 1000).toLocaleTimeString(
                "ru-RU",
              ),
      },
    ],
    unhealthyComponents: snapshot.health_summary.unhealthy_components,
    circuitBreakers: snapshot.circuit_breaker_summary.map((item) => ({
      name: item.name,
      state: formatCircuitBreakerState(item.state),
      failureCount: item.failure_count,
      successCount: item.success_count,
      failureThreshold: item.failure_threshold,
      recoveryTimeout: item.recovery_timeout,
    })),
  };
}

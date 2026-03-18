import type { OverviewSnapshotResponse } from "../../../shared/types/dashboard";
import {
  formatHealthStatus,
  formatLifecyclePhase,
  formatSystemState,
  formatTradingState,
  getModuleCopy,
} from "../../../shared/lib/dashboardText";

export type OverviewViewModel = {
  moduleState: "inactive" | "read-only" | "active" | "restricted";
  system: Array<{ label: string; value: string | number }>;
  health: Array<{ label: string; value: string | number }>;
  approvals: Array<{ label: string; value: string | number }>;
  events: Array<{ label: string; value: string | number }>;
  circuitBreakers: OverviewSnapshotResponse["circuit_breaker_summary"];
  modules: OverviewSnapshotResponse["module_availability"];
  alertsPlaceholder: OverviewSnapshotResponse["alerts_summary"];
  unhealthyComponents: string[];
};

export function mapOverview(
  snapshot: OverviewSnapshotResponse,
): OverviewViewModel {
  const overviewModule =
    snapshot.module_availability.find((item) => item.key === "overview") ??
    null;

  return {
    moduleState: overviewModule?.status ?? "inactive",
    system: [
      {
        label: "Текущее состояние",
        value: formatSystemState(snapshot.system_state.current_state),
      },
      {
        label: "Фаза запуска",
        value: formatLifecyclePhase(snapshot.system_state.startup_phase),
      },
      {
        label: "Фаза остановки",
        value: formatLifecyclePhase(snapshot.system_state.shutdown_phase),
      },
      {
        label: "Время работы",
        value: `${snapshot.system_state.uptime_seconds} с`,
      },
      {
        label: "Торговля",
        value: formatTradingState(snapshot.system_state.trade_allowed),
      },
    ],
    health: [
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
    approvals: [
      {
        label: "Ожидают подтверждения",
        value: snapshot.pending_approvals.pending_count,
      },
      {
        label: "Всего запросов",
        value: snapshot.pending_approvals.total_requests,
      },
      {
        label: "Таймаут",
        value: `${snapshot.pending_approvals.request_timeout_minutes} мин`,
      },
    ],
    events: [
      { label: "Опубликовано", value: snapshot.event_summary.total_published },
      { label: "Доставлено", value: snapshot.event_summary.total_delivered },
      { label: "Отброшено", value: snapshot.event_summary.total_dropped },
      {
        label: "Ограничено по скорости",
        value: snapshot.event_summary.total_rate_limited,
      },
      {
        label: "Подписчиков",
        value: snapshot.event_summary.subscriber_count,
      },
    ],
    circuitBreakers: snapshot.circuit_breaker_summary,
    modules: snapshot.module_availability.map((module) => ({
      ...module,
      ...getModuleCopy(module.key, module.title, module.description),
    })),
    alertsPlaceholder: snapshot.alerts_summary,
    unhealthyComponents: snapshot.health_summary.unhealthy_components,
  };
}

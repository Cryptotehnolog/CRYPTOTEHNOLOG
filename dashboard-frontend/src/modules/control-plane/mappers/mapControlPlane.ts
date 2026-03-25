import type { OverviewSnapshotResponse } from "../../../shared/types/dashboard";
import {
  formatBooleanWord,
  formatLifecyclePhase,
  formatSystemState,
  formatTradingState,
} from "../../../shared/lib/dashboardText";

export type ControlPlaneViewModel = {
  moduleState: "inactive" | "read-only" | "active" | "restricted";
  statusBadges: Array<{
    label: string;
    tone: "neutral" | "accent" | "success" | "warning" | "danger";
  }>;
  lifecycle: Array<{ label: string; value: string | number }>;
  runtimeFlags: Array<{ label: string; value: string | number }>;
  errorState: {
    hasError: boolean;
    message: string;
  };
};

function mapCurrentStateTone(
  currentState: string,
): "neutral" | "accent" | "success" | "warning" | "danger" {
  if (currentState === "running") {
    return "success";
  }
  if (currentState === "degraded" || currentState === "shutdown") {
    return "warning";
  }
  if (currentState === "error") {
    return "danger";
  }
  if (currentState === "boot") {
    return "accent";
  }
  return "neutral";
}

export function mapControlPlane(
  snapshot: OverviewSnapshotResponse,
): ControlPlaneViewModel {
  const controlPlaneModule =
    snapshot.module_availability.find((item) => item.key === "control-plane") ??
    null;

  return {
    moduleState: controlPlaneModule?.status ?? "inactive",
    statusBadges: [
      {
        label: formatSystemState(snapshot.system_state.current_state),
        tone: mapCurrentStateTone(snapshot.system_state.current_state),
      },
      {
        label: snapshot.system_state.trade_allowed
          ? "торговля разрешена"
          : "торговля заблокирована",
        tone: snapshot.system_state.trade_allowed ? "success" : "danger",
      },
    ],
    lifecycle: [
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
    ],
    runtimeFlags: [
      {
        label: "Контур исполнения запущен",
        value: formatBooleanWord(snapshot.system_state.is_running),
      },
      {
        label: "Остановка выполняется",
        value: formatBooleanWord(snapshot.system_state.is_shutting_down),
      },
      {
        label: "Торговля",
        value: formatTradingState(snapshot.system_state.trade_allowed),
      },
    ],
    errorState: {
      hasError: snapshot.system_state.last_error !== null,
      message:
        snapshot.system_state.last_error ??
        "Последняя ошибка отсутствует в текущем снимке контура управления.",
    },
  };
}

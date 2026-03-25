import type { RiskConstraintResponse, RiskSummaryResponse } from "../../../shared/types/dashboard";
import { formatModuleStatus, formatSystemState, formatTradingState } from "../../../shared/lib/dashboardText";

export type RiskViewModel = {
  moduleState: "inactive" | "read-only" | "active" | "restricted";
  statusBadges: Array<{
    label: string;
    tone: "neutral" | "accent" | "success" | "warning" | "danger";
  }>;
  summary: Array<{ label: string; value: string | number }>;
  runtimeBoundary: Array<{ label: string; value: string | number }>;
  constraints: Array<{
    key: string;
    label: string;
    value: string;
    note: string | null;
    tone: "neutral" | "accent" | "success" | "warning" | "danger";
  }>;
  reason: {
    hasReason: boolean;
    message: string;
  };
};

function mapGlobalStatusTone(
  status: RiskSummaryResponse["global_status"],
): "neutral" | "accent" | "success" | "warning" | "danger" {
  if (status === "blocked") {
    return "danger";
  }
  if (status === "limited") {
    return "warning";
  }
  return "success";
}

function formatGlobalStatus(status: RiskSummaryResponse["global_status"]): string {
  if (status === "blocked") {
    return "риск заблокирован";
  }
  if (status === "limited") {
    return "риск ограничен";
  }
  return "в пределах допустимого";
}

function mapConstraintTone(
  status: RiskConstraintResponse["status"],
): "neutral" | "accent" | "success" | "warning" | "danger" {
  if (status === "blocked") {
    return "danger";
  }
  if (status === "limited" || status === "warning") {
    return "warning";
  }
  if (status === "normal") {
    return "success";
  }
  return "accent";
}

export function mapRisk(snapshot: RiskSummaryResponse): RiskViewModel {
  return {
    moduleState: snapshot.module_status,
    statusBadges: [
      {
        label: formatModuleStatus(snapshot.module_status),
        tone: snapshot.module_status === "read-only" ? "accent" : "neutral",
      },
      {
        label: formatGlobalStatus(snapshot.global_status),
        tone: mapGlobalStatusTone(snapshot.global_status),
      },
      {
        label: snapshot.trading_blocked
          ? "торговля заблокирована"
          : `торговля ${formatTradingState(!snapshot.trading_blocked)}`,
        tone: snapshot.trading_blocked ? "danger" : "success",
      },
    ],
    summary: [
      {
        label: "Глобальный статус риска",
        value: formatGlobalStatus(snapshot.global_status),
      },
      {
        label: "Системное состояние",
        value: formatSystemState(snapshot.current_state),
      },
      {
        label: "Лимитирующее состояние",
        value: snapshot.limiting_state,
      },
      {
        label: "Активный путь риска",
        value: snapshot.active_risk_path ?? "не выведен",
      },
    ],
    runtimeBoundary: [
      {
        label: "Торговля",
        value: formatTradingState(!snapshot.trading_blocked),
      },
      {
        label: "Примечание к состоянию",
        value: snapshot.state_note,
      },
      {
        label: "Причина сводки",
        value: snapshot.summary_reason ?? "дополнительная причина не выведена",
      },
    ],
    constraints: snapshot.constraints.map((item) => ({
      key: item.key,
      label: item.label,
      value: item.value,
      note: item.note,
      tone: mapConstraintTone(item.status),
    })),
    reason: {
      hasReason: snapshot.summary_reason !== null,
      message:
        snapshot.summary_reason ??
        "Сводка по риску не содержит выведенной причины. Страница показывает только примечание к состоянию и текущие ограничения.",
    },
  };
}

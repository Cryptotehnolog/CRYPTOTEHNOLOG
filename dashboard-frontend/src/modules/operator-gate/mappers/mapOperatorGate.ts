import type { OverviewSnapshotResponse } from "../../../shared/types/dashboard";

export type OperatorGateViewModel = {
  moduleState: "inactive" | "read-only" | "active" | "restricted";
  statusBadges: Array<{
    label: string;
    tone: "neutral" | "accent" | "success" | "warning" | "danger";
  }>;
  approvalSummary: Array<{ label: string; value: string | number }>;
  boundarySummary: Array<{ label: string; value: string | number }>;
};

export function mapOperatorGate(
  snapshot: OverviewSnapshotResponse,
): OperatorGateViewModel {
  const module =
    snapshot.module_availability.find((item) => item.key === "operator-gate") ?? null;

  return {
    moduleState: module?.status ?? "inactive",
    statusBadges: [
      {
        label:
          snapshot.pending_approvals.pending_count > 0
            ? `в ожидании: ${snapshot.pending_approvals.pending_count}`
            : "в ожидании: нет",
        tone:
          snapshot.pending_approvals.pending_count > 0 ? "warning" : "success",
      },
      {
        label: `таймаут: ${snapshot.pending_approvals.request_timeout_minutes} мин`,
        tone: "neutral",
      },
    ],
    approvalSummary: [
      {
        label: "Ожидают подтверждения",
        value: snapshot.pending_approvals.pending_count,
      },
      {
        label: "Всего запросов",
        value: snapshot.pending_approvals.total_requests,
      },
      {
        label: "Таймаут запроса",
        value: `${snapshot.pending_approvals.request_timeout_minutes} мин`,
      },
    ],
    boundarySummary: [
      {
        label: "Текущее состояние страницы",
        value: "только сводка",
      },
      {
        label: "Подтвердить / отклонить",
        value: "вне границ страницы",
      },
      {
        label: "Детали запроса",
        value: "не выведены",
      },
    ],
  };
}

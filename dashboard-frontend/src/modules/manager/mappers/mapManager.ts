import type {
  ManagerAvailabilityItemResponse,
  ManagerSummaryResponse,
} from "../../../shared/types/dashboard";
import { formatModuleStatus } from "../../../shared/lib/dashboardText";

export type ManagerViewModel = {
  moduleState: "inactive" | "read-only" | "active" | "restricted";
  statusBadges: Array<{
    label: string;
    tone: "neutral" | "accent" | "success" | "warning" | "danger";
  }>;
  summary: Array<{ label: string; value: string | number }>;
  freshness: Array<{ label: string; value: string | number }>;
  availability: Array<{
    key: string;
    label: string;
    value: string;
    note: string | null;
    tone: "neutral" | "accent" | "success" | "warning" | "danger";
  }>;
  note: {
    hasReason: boolean;
    message: string;
    summaryNote: string;
  };
};

function mapGlobalTone(
  status: ManagerSummaryResponse["global_status"],
): "neutral" | "accent" | "success" | "warning" | "danger" {
  if (status === "ready") {
    return "success";
  }
  if (status === "degraded") {
    return "danger";
  }
  if (status === "warming") {
    return "warning";
  }
  return "neutral";
}

function formatGlobalStatus(status: ManagerSummaryResponse["global_status"]): string {
  if (status === "ready") {
    return "контур готов";
  }
  if (status === "degraded") {
    return "контур в деградации";
  }
  if (status === "warming") {
    return "контур прогревается";
  }
  return "контур неактивен";
}

function formatManagerLifecycleState(state: string): string {
  if (state === "warming") {
    return "прогрев";
  }
  if (state === "ready") {
    return "готов";
  }
  if (state === "degraded") {
    return "деградация";
  }
  if (state === "stopped") {
    return "остановлен";
  }
  if (state === "started") {
    return "запущен";
  }
  if (state === "not_started") {
    return "не запущен";
  }
  if (state === "not_ready" || state === "not ready") {
    return "не готов";
  }
  return state;
}

function formatSurfacedState(value: string): string {
  if (value === "not surfaced" || value === "not_surfaced") {
    return "не выведено";
  }
  if (value === "surfaced") {
    return "выведено";
  }
  if (value === "started") {
    return "запущен";
  }
  if (value === "not started") {
    return "не запущен";
  }
  if (value === "ready") {
    return "готов";
  }
  if (value === "not ready") {
    return "не готов";
  }
  if (value === "active_workflow_surfaced") {
    return "выведен активный рабочий процесс";
  }
  if (value === "historical_workflow_surfaced") {
    return "выведен исторический рабочий процесс";
  }
  if (value === "workflow_recently_surfaced") {
    return "рабочий процесс недавно выведен";
  }
  return value;
}

function formatAvailabilityLabel(key: string, fallbackLabel: string): string {
  if (key === "runtime_started") {
    return "Контур менеджера";
  }
  if (key === "runtime_ready") {
    return "Готовность";
  }
  if (key === "tracked_contexts") {
    return "Отслеживаемые контексты";
  }
  if (key === "tracked_active_workflows") {
    return "Отслеживаемые активные рабочие процессы";
  }
  if (key === "tracked_historical_workflows") {
    return "Отслеживаемые исторические рабочие процессы";
  }
  if (key === "last_workflow_id") {
    return "Последний идентификатор рабочего процесса";
  }
  if (key === "last_event_type") {
    return "Последний тип события";
  }
  return fallbackLabel;
}

function formatAvailabilityNote(key: string, note: string | null): string | null {
  if (note === null) {
    return null;
  }
  if (key === "runtime_started") {
    return "Глобальный флаг выполнения без действий над рабочими процессами.";
  }
  if (key === "runtime_ready") {
    return "Готовность отражает только выведенные диагностические данные контура менеджера.";
  }
  if (key === "tracked_contexts") {
    return "Количество контекстов менеджера в текущем диагностическом снимке.";
  }
  if (key === "tracked_active_workflows") {
    return "Суммарный счётчик активных рабочих процессов без отдельного обозревателя.";
  }
  if (key === "tracked_historical_workflows") {
    return "Суммарный счётчик исторических рабочих процессов без браузера истории.";
  }
  if (key === "last_workflow_id") {
    return "Последний выведенный идентификатор рабочего процесса без отдельного обозревателя.";
  }
  if (key === "last_event_type") {
    return "Последний выведенный тип события контура менеджера.";
  }
  return note;
}

function formatManagerReasonToken(token: string): string {
  const trimmed = token.trim();
  const reasonMap: Record<string, string> = {
    no_manager_workflow_processed:
      "рабочий процесс менеджера ещё не был обработан в текущем диагностическом снимке",
    runtime_stopped: "контур менеджера остановлен",
    runtime_degraded: "контур менеджера находится в деградации",
    manager_context_incomplete: "контекст менеджера пока неполный",
    manager_context_invalid: "контекст менеджера находится в невалидном состоянии",
    workflow_ingest_failed: "обработка рабочего процесса завершилась ошибкой",
    manager_candidate_expired: "кандидат менеджера устарел до текущего снимка",
    protection: "часть входов менеджера ещё не выведена на защитном контуре",
    orchestration: "часть входов менеджера ещё не выведена на контуре оркестрации",
    opportunity: "часть входов менеджера ещё не выведена на контуре возможностей",
    position_expansion: "часть входов менеджера ещё не выведена на контуре расширения позиции",
    portfolio_governor: "часть входов менеджера ещё не выведена на портфельном контуре",
  };

  return reasonMap[trimmed] ?? "контур вернул непереведённую техническую причину";
}

function formatManagerReasonDetails(details: string): string {
  return details
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => formatManagerReasonToken(item))
    .join(", ");
}

function formatSummaryNote(note: string): string {
  if (note.startsWith("Manager runtime surfaced degraded reasons: ")) {
    return `Контур менеджера вывел причины деградации: ${formatManagerReasonDetails(
      note.slice("Manager runtime surfaced degraded reasons: ".length),
    )}`;
  }

  if (note.startsWith("Manager runtime surfaced readiness reasons: ")) {
    return `Контур менеджера вывел причины неготовности: ${formatManagerReasonDetails(
      note.slice("Manager runtime surfaced readiness reasons: ".length),
    )}`;
  }

  if (
    note ===
    "Manager runtime не surfaced дополнительных notes beyond current diagnostics."
  ) {
    return "Контур менеджера не вывел дополнительных пояснений сверх текущих диагностических данных.";
  }

  return note;
}

function formatSummaryReason(reason: string | null): string {
  if (reason === null) {
    return "Сводка по менеджеру не содержит выведенной причины. Страница показывает только текущее состояние контура и счётчики доступности.";
  }
  return formatManagerReasonDetails(reason);
}

function mapAvailabilityTone(
  status: ManagerAvailabilityItemResponse["status"],
): "neutral" | "accent" | "success" | "warning" | "danger" {
  if (status === "normal") {
    return "success";
  }
  if (status === "warning") {
    return "warning";
  }
  return "accent";
}

export function mapManager(snapshot: ManagerSummaryResponse): ManagerViewModel {
  return {
    moduleState: snapshot.module_status,
    statusBadges: [
      {
        label: formatModuleStatus(snapshot.module_status),
        tone: snapshot.module_status === "read-only" ? "accent" : "neutral",
      },
      {
        label: formatGlobalStatus(snapshot.global_status),
        tone: mapGlobalTone(snapshot.global_status),
      },
      {
        label: snapshot.ready
          ? "состояние менеджера выведено"
          : "состояние менеджера прогревается",
        tone: snapshot.ready ? "success" : "warning",
      },
    ],
    summary: [
      {
        label: "Глобальный контур менеджера",
        value: formatGlobalStatus(snapshot.global_status),
      },
      {
        label: "Состояние жизненного цикла",
        value: formatManagerLifecycleState(snapshot.lifecycle_state),
      },
      {
        label: "Контур менеджера запущен",
        value: snapshot.started ? "да" : "нет",
      },
      {
        label: "Активный путь менеджера",
        value: formatSurfacedState(snapshot.active_manager_path),
      },
      {
        label: "Источник менеджера",
        value: formatSurfacedState(snapshot.manager_source),
      },
    ],
    freshness: [
      {
        label: "Состояние свежести",
        value: formatSurfacedState(snapshot.freshness_state),
      },
      {
        label: "Последний идентификатор рабочего процесса",
        value: snapshot.last_workflow_id ?? "не выведен",
      },
      {
        label: "Последний тип события",
        value: snapshot.last_event_type ?? "не выведен",
      },
    ],
    availability: snapshot.availability.map((item) => ({
      key: item.key,
      label: formatAvailabilityLabel(item.key, item.label),
      value: formatSurfacedState(item.value),
      note: formatAvailabilityNote(item.key, item.note),
      tone: mapAvailabilityTone(item.status),
    })),
    note: {
      hasReason: snapshot.summary_reason !== null,
      message: formatSummaryReason(snapshot.summary_reason),
      summaryNote: formatSummaryNote(snapshot.summary_note),
    },
  };
}

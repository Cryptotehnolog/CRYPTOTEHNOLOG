import type {
  OrchestrationAvailabilityItemResponse,
  OrchestrationSummaryResponse,
} from "../../../shared/types/dashboard";
import { formatModuleStatus } from "../../../shared/lib/dashboardText";

export type OrchestrationViewModel = {
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
  status: OrchestrationSummaryResponse["global_status"],
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

function formatGlobalStatus(status: OrchestrationSummaryResponse["global_status"]): string {
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

function formatOrchestrationLifecycleState(state: string): string {
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
  if (value === "expired_decisions_present") {
    return "есть истёкшие решения";
  }
  if (value === "forwarded_decision_surfaced") {
    return "выведено переданное решение";
  }
  if (value === "decision_recently_surfaced") {
    return "решение недавно выведено";
  }
  if (value === "decision_state_surfaced") {
    return "состояние решения выведено";
  }
  return value;
}

function formatAvailabilityLabel(key: string, fallbackLabel: string): string {
  if (key === "runtime_started") {
    return "Контур оркестрации";
  }
  if (key === "runtime_ready") {
    return "Готовность";
  }
  if (key === "tracked_context_keys") {
    return "Отслеживаемые ключи контекста";
  }
  if (key === "tracked_decision_keys") {
    return "Отслеживаемые ключи решений";
  }
  if (key === "forwarded_keys") {
    return "Ключи переданных решений";
  }
  if (key === "abstained_keys") {
    return "Ключи воздержавшихся решений";
  }
  if (key === "invalidated_decision_keys") {
    return "Инвалидированные ключи решений";
  }
  if (key === "expired_decision_keys") {
    return "Истёкшие ключи решений";
  }
  if (key === "last_selection_id") {
    return "Последний идентификатор отбора";
  }
  if (key === "last_decision_id") {
    return "Последний идентификатор решения";
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
    return "Глобальный флаг runtime без действий над оркестрацией.";
  }
  if (key === "runtime_ready") {
    return "Готовность отражает только выведенные диагностические данные контура оркестрации.";
  }
  if (key === "tracked_context_keys") {
    return "Количество ключей контекста оркестрации в текущем runtime-снимке.";
  }
  if (key === "tracked_decision_keys") {
    return "Суммарный счётчик решений без широкого обозревателя оркестрации.";
  }
  if (key === "forwarded_keys") {
    return "Показывается только агрегированный счётчик решений, переданных дальше по контуру.";
  }
  if (key === "abstained_keys") {
    return "Сводный счётчик воздержавшихся решений без детального обозревателя.";
  }
  if (key === "invalidated_decision_keys") {
    return "Показывается как выведенный счётчик без обозревателя деталей.";
  }
  if (key === "expired_decision_keys") {
    return "Сводный индикатор свежести без обозревателя истории решений.";
  }
  if (key === "last_selection_id") {
    return "Последняя выведенная ссылка на opportunity selection для контура оркестрации.";
  }
  if (key === "last_decision_id") {
    return "Последнее выведенное решение оркестрации без отдельного обозревателя.";
  }
  if (key === "last_event_type") {
    return "Последний выведенный тип события контура оркестрации.";
  }
  return note;
}

function formatOrchestrationReasonDetails(details: string): string {
  const reasonMap: Record<string, string> = {
    no_orchestration_context_processed:
      "контекст оркестрации ещё не был обработан в текущем runtime-снимке",
    runtime_stopped: "runtime оркестрации остановлен",
    selection_ingest_failed: "обработка данных отбора завершилась ошибкой",
    orchestration_context_invalid:
      "контекст оркестрации находится в невалидном состоянии",
    selection_confidence_below_threshold:
      "у отбора недостаточная уверенность для передачи решения дальше",
    priority_score_below_threshold:
      "приоритет решения оркестрации ниже допустимого порога",
  };

  return details
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => reasonMap[item] ?? item)
    .join(", ");
}

function formatSummaryNote(note: string): string {
  if (note.startsWith("Orchestration runtime surfaced degraded reasons: ")) {
    return `Контур оркестрации вывел причины деградации: ${formatOrchestrationReasonDetails(
      note.slice("Orchestration runtime surfaced degraded reasons: ".length),
    )}`;
  }

  if (note.startsWith("Orchestration runtime surfaced readiness reasons: ")) {
    return `Контур оркестрации вывел причины неготовности: ${formatOrchestrationReasonDetails(
      note.slice("Orchestration runtime surfaced readiness reasons: ".length),
    )}`;
  }

  if (
    note ===
    "Orchestration runtime не surfaced дополнительных notes beyond current diagnostics."
  ) {
    return "Контур оркестрации не вывел дополнительных пояснений сверх текущих диагностических данных.";
  }

  return note;
}

function mapAvailabilityTone(
  status: OrchestrationAvailabilityItemResponse["status"],
): "neutral" | "accent" | "success" | "warning" | "danger" {
  if (status === "normal") {
    return "success";
  }
  if (status === "warning") {
    return "warning";
  }
  return "accent";
}

export function mapOrchestration(snapshot: OrchestrationSummaryResponse): OrchestrationViewModel {
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
          ? "состояние оркестрации выведено"
          : "состояние оркестрации прогревается",
        tone: snapshot.ready ? "success" : "warning",
      },
    ],
    summary: [
      { label: "Глобальный контур оркестрации", value: formatGlobalStatus(snapshot.global_status) },
      { label: "Состояние жизненного цикла", value: formatOrchestrationLifecycleState(snapshot.lifecycle_state) },
      { label: "Контур оркестрации запущен", value: snapshot.started ? "да" : "нет" },
      { label: "Активный путь оркестрации", value: snapshot.active_orchestration_path },
      { label: "Источник оркестрации", value: snapshot.orchestration_source },
    ],
    freshness: [
      { label: "Состояние свежести", value: formatSurfacedState(snapshot.freshness_state) },
      { label: "Последний идентификатор отбора", value: snapshot.last_selection_id ?? "не выведен" },
      { label: "Последний идентификатор решения", value: snapshot.last_decision_id ?? "не выведен" },
      { label: "Последний тип события", value: snapshot.last_event_type ?? "не выведен" },
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
      summaryNote: formatSummaryNote(snapshot.summary_note),
      message:
        snapshot.summary_reason ??
        "Сводка по оркестрации не содержит выведенной причины. Страница показывает только текущее состояние контура и счётчики доступности.",
    },
  };
}

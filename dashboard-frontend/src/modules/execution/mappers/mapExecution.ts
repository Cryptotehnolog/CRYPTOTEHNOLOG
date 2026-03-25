import type {
  ExecutionAvailabilityItemResponse,
  ExecutionSummaryResponse,
} from "../../../shared/types/dashboard";
import { formatModuleStatus } from "../../../shared/lib/dashboardText";

export type ExecutionViewModel = {
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
  status: ExecutionSummaryResponse["global_status"],
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

function formatGlobalStatus(status: ExecutionSummaryResponse["global_status"]): string {
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

function formatExecutionLifecycleState(state: string): string {
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
  if (value === "expired_intents_present") {
    return "есть истёкшие намерения";
  }
  if (value === "executable_intent_surfaced") {
    return "выведено намерение, готовое к исполнению";
  }
  if (value === "intent_recently_surfaced") {
    return "намерение недавно выведено";
  }
  return value;
}

function formatAvailabilityLabel(key: string, fallbackLabel: string): string {
  if (key === "runtime_started") {
    return "Контур исполнения";
  }
  if (key === "runtime_ready") {
    return "Готовность";
  }
  if (key === "tracked_context_keys") {
    return "Отслеживаемые ключи контекста";
  }
  if (key === "tracked_intent_keys") {
    return "Отслеживаемые ключи намерений";
  }
  if (key === "executable_intent_keys") {
    return "Ключи намерений, готовых к исполнению";
  }
  if (key === "invalidated_intent_keys") {
    return "Инвалидированные ключи намерений";
  }
  if (key === "expired_intent_keys") {
    return "Истёкшие ключи намерений";
  }
  if (key === "last_candidate_id") {
    return "Последний идентификатор кандидата";
  }
  if (key === "last_intent_id") {
    return "Последний идентификатор намерения";
  }
  return fallbackLabel;
}

function formatAvailabilityNote(key: string, note: string | null): string | null {
  if (note === null) {
    return null;
  }
  if (key === "runtime_started") {
    return "Глобальный флаг runtime без действий над исполнением.";
  }
  if (key === "runtime_ready") {
    return "Готовность отражает только выведенные диагностические данные контура исполнения.";
  }
  if (key === "tracked_context_keys") {
    return "Количество ключей контекста исполнения в текущем runtime-снимке.";
  }
  if (key === "tracked_intent_keys") {
    return "Суммарный счётчик execution intents без обозревателя истории.";
  }
  if (key === "executable_intent_keys") {
    return "Показывается только агрегированный счётчик намерений, готовых к исполнению.";
  }
  if (key === "invalidated_intent_keys") {
    return "Показывается как выведенный счётчик без обозревателя деталей.";
  }
  if (key === "expired_intent_keys") {
    return "Сводный индикатор свежести без обозревателя истории намерений.";
  }
  if (key === "last_candidate_id") {
    return "Последняя выведенная ссылка на стратегический кандидат для контура исполнения.";
  }
  if (key === "last_intent_id") {
    return "Последнее выведенное execution intent без отдельного обозревателя.";
  }
  return note;
}

function formatExecutionReasonDetails(details: string): string {
  const reasonMap: Record<string, string> = {
    no_execution_context_processed:
      "контекст исполнения ещё не был обработан в текущем runtime-снимке",
    execution_context_warming: "контекст исполнения ещё прогревается",
    execution_context_invalid: "контекст исполнения находится в невалидном состоянии",
    runtime_stopped: "runtime исполнения остановлен",
    candidate_ingest_failed: "обработка кандидата исполнения завершилась ошибкой",
    strategy_candidate_expired: "стратегический кандидат устарел до формирования намерения",
    strategy_candidate_invalidated:
      "стратегический кандидат был инвалидирован до формирования намерения",
    strategy_candidate_not_actionable:
      "стратегический кандидат не находится в состоянии, готовом к исполнению",
  };

  return details
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => reasonMap[item] ?? item)
    .join(", ");
}

function formatSummaryNote(note: string): string {
  if (note.startsWith("Execution runtime surfaced degraded reasons: ")) {
    return `Контур исполнения вывел причины деградации: ${formatExecutionReasonDetails(
      note.slice("Execution runtime surfaced degraded reasons: ".length),
    )}`;
  }

  if (note.startsWith("Execution runtime surfaced readiness reasons: ")) {
    return `Контур исполнения вывел причины неготовности: ${formatExecutionReasonDetails(
      note.slice("Execution runtime surfaced readiness reasons: ".length),
    )}`;
  }

  if (
    note ===
    "Execution runtime не surfaced дополнительных notes beyond current diagnostics."
  ) {
    return "Контур исполнения не вывел дополнительных пояснений сверх текущих диагностических данных.";
  }

  return note;
}

function mapAvailabilityTone(
  status: ExecutionAvailabilityItemResponse["status"],
): "neutral" | "accent" | "success" | "warning" | "danger" {
  if (status === "normal") {
    return "success";
  }
  if (status === "warning") {
    return "warning";
  }
  return "accent";
}

export function mapExecution(snapshot: ExecutionSummaryResponse): ExecutionViewModel {
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
          ? "состояние исполнения выведено"
          : "состояние исполнения прогревается",
        tone: snapshot.ready ? "success" : "warning",
      },
    ],
    summary: [
      {
        label: "Глобальный контур исполнения",
        value: formatGlobalStatus(snapshot.global_status),
      },
      {
        label: "Состояние жизненного цикла",
        value: formatExecutionLifecycleState(snapshot.lifecycle_state),
      },
      {
        label: "Контур исполнения запущен",
        value: snapshot.started ? "да" : "нет",
      },
      {
        label: "Активный путь исполнения",
        value: formatSurfacedState(snapshot.active_execution_path),
      },
      {
        label: "Источник исполнения",
        value: formatSurfacedState(snapshot.execution_source),
      },
    ],
    freshness: [
      {
        label: "Состояние свежести",
        value: formatSurfacedState(snapshot.freshness_state),
      },
      {
        label: "Последний идентификатор кандидата",
        value: snapshot.last_candidate_id ?? "не выведен",
      },
      {
        label: "Последний идентификатор намерения",
        value: snapshot.last_intent_id ?? "не выведен",
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
      message:
        snapshot.summary_reason ??
        "Сводка по исполнению не содержит выведенной причины. Страница показывает только текущее состояние контура и счётчики доступности.",
      summaryNote: formatSummaryNote(snapshot.summary_note),
    },
  };
}

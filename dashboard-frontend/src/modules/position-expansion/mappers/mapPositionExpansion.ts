import type {
  PositionExpansionAvailabilityItemResponse,
  PositionExpansionSummaryResponse,
} from "../../../shared/types/dashboard";
import { formatModuleStatus } from "../../../shared/lib/dashboardText";

export type PositionExpansionViewModel = {
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
  status: PositionExpansionSummaryResponse["global_status"],
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

function formatGlobalStatus(status: PositionExpansionSummaryResponse["global_status"]): string {
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

function formatLifecycleState(state: string): string {
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
  if (value === "expired_expansions_present") {
    return "есть истёкшие расширения";
  }
  if (value === "expandable_position_surfaced") {
    return "выведен кандидат на расширение позиции";
  }
  if (value === "expansion_recently_surfaced") {
    return "расширение позиции недавно выведено";
  }
  if (value === "expansion_state_surfaced") {
    return "состояние расширения позиции выведено";
  }
  return value;
}

function formatAvailabilityLabel(key: string, fallbackLabel: string): string {
  if (key === "runtime_started") {
    return "Контур расширения позиции";
  }
  if (key === "runtime_ready") {
    return "Готовность";
  }
  if (key === "tracked_context_keys") {
    return "Отслеживаемые ключи контекста";
  }
  if (key === "tracked_expansion_keys") {
    return "Отслеживаемые ключи расширения";
  }
  if (key === "expandable_keys") {
    return "Ключи доступных расширений";
  }
  if (key === "abstained_keys") {
    return "Ключи воздержавшихся решений";
  }
  if (key === "rejected_keys") {
    return "Ключи отклонённых расширений";
  }
  if (key === "invalidated_expansion_keys") {
    return "Инвалидированные ключи расширения";
  }
  if (key === "expired_expansion_keys") {
    return "Истёкшие ключи расширения";
  }
  if (key === "last_decision_id") {
    return "Последний идентификатор решения";
  }
  if (key === "last_expansion_id") {
    return "Последний идентификатор расширения";
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
    return "Глобальный флаг контура без действий по расширению позиции.";
  }
  if (key === "runtime_ready") {
    return "Готовность отражает только выведенные диагностические данные контура расширения позиции.";
  }
  if (key === "tracked_context_keys") {
    return "Количество ключей контекста расширения позиции в текущем снимке контура.";
  }
  if (key === "tracked_expansion_keys") {
    return "Суммарный счётчик расширений позиции без широкого обозревателя.";
  }
  if (key === "expandable_keys") {
    return "Показывается только агрегированный счётчик кандидатов на расширение позиции.";
  }
  if (key === "abstained_keys") {
    return "Сводный счётчик воздержавшихся решений без детального обозревателя.";
  }
  if (key === "rejected_keys") {
    return "Сводный счётчик отклонённых кандидатов расширения позиции.";
  }
  if (key === "invalidated_expansion_keys") {
    return "Показывается как выведенный счётчик без обозревателя деталей.";
  }
  if (key === "expired_expansion_keys") {
    return "Сводный индикатор свежести без обозревателя истории расширений.";
  }
  if (key === "last_decision_id") {
    return "Последняя выведенная ссылка на решение оркестрации для контура расширения позиции.";
  }
  if (key === "last_expansion_id") {
    return "Последний выведенный идентификатор расширения позиции без отдельного обозревателя.";
  }
  if (key === "last_event_type") {
    return "Последний выведенный тип события контура расширения позиции.";
  }
  return note;
}

function formatReasonDetails(details: string): string {
  const reasonMap: Record<string, string> = {
    no_position_expansion_context_processed:
      "контекст расширения позиции ещё не был обработан в текущем снимке контура",
    runtime_stopped: "контур расширения позиции остановлен",
    decision_ingest_failed: "обработка решения оркестрации завершилась ошибкой",
    expansion_context_invalid: "контекст расширения позиции находится в невалидном состоянии",
    confidence_below_threshold:
      "у кандидата недостаточная уверенность для расширения позиции",
    priority_score_below_threshold:
      "приоритет кандидата расширения позиции ниже допустимого порога",
    position_expansion_not_admissible:
      "кандидат расширения позиции не находится в допустимом состоянии",
  };

  return details
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => reasonMap[item] ?? item)
    .join(", ");
}

function formatSummaryNote(note: string): string {
  if (note.startsWith("Position expansion runtime surfaced degraded reasons: ")) {
    return `Контур расширения позиции вывел причины деградации: ${formatReasonDetails(
      note.slice("Position expansion runtime surfaced degraded reasons: ".length),
    )}`;
  }

  if (note.startsWith("Position expansion runtime surfaced readiness reasons: ")) {
    return `Контур расширения позиции вывел причины неготовности: ${formatReasonDetails(
      note.slice("Position expansion runtime surfaced readiness reasons: ".length),
    )}`;
  }

  if (
    note ===
    "Position expansion runtime не surfaced дополнительных notes beyond current diagnostics."
  ) {
    return "Контур расширения позиции не вывел дополнительных пояснений сверх текущих диагностических данных.";
  }

  return note;
}

function mapAvailabilityTone(
  status: PositionExpansionAvailabilityItemResponse["status"],
): "neutral" | "accent" | "success" | "warning" | "danger" {
  if (status === "normal") {
    return "success";
  }
  if (status === "warning") {
    return "warning";
  }
  return "accent";
}

export function mapPositionExpansion(
  snapshot: PositionExpansionSummaryResponse,
): PositionExpansionViewModel {
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
          ? "состояние расширения позиции выведено"
          : "состояние расширения позиции прогревается",
        tone: snapshot.ready ? "success" : "warning",
      },
    ],
    summary: [
      {
        label: "Глобальный контур расширения позиции",
        value: formatGlobalStatus(snapshot.global_status),
      },
      {
        label: "Состояние жизненного цикла",
        value: formatLifecycleState(snapshot.lifecycle_state),
      },
      {
        label: "Контур расширения позиции запущен",
        value: snapshot.started ? "да" : "нет",
      },
      {
        label: "Активный путь расширения позиции",
        value: snapshot.active_position_expansion_path,
      },
      {
        label: "Источник расширения позиции",
        value: snapshot.position_expansion_source,
      },
    ],
    freshness: [
      {
        label: "Состояние свежести",
        value: formatSurfacedState(snapshot.freshness_state),
      },
      {
        label: "Последний идентификатор решения",
        value: snapshot.last_decision_id ?? "не выведен",
      },
      {
        label: "Последний идентификатор расширения",
        value: snapshot.last_expansion_id ?? "не выведен",
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
      summaryNote: formatSummaryNote(snapshot.summary_note),
      message:
        snapshot.summary_reason ??
        "Сводка по расширению позиции не содержит выведенной причины. Страница показывает только текущее состояние контура и счётчики доступности.",
    },
  };
}

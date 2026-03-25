import type {
  StrategyAvailabilityItemResponse,
  StrategySummaryResponse,
} from "../../../shared/types/dashboard";
import { formatModuleStatus } from "../../../shared/lib/dashboardText";

export type StrategyViewModel = {
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
  status: StrategySummaryResponse["global_status"],
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

function formatGlobalStatus(status: StrategySummaryResponse["global_status"]): string {
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

function formatStrategyLifecycleState(state: string): string {
  if (state === "warming") {
    return "прогрев";
  }
  if (state === "started") {
    return "запущен";
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
  if (value === "expired_candidates_present") {
    return "есть истёкшие кандидаты";
  }
  if (value === "actionable_candidate_surfaced") {
    return "выведен кандидат, готовый к действию";
  }
  if (value === "candidate_recently_surfaced") {
    return "кандидат недавно выведен";
  }
  return value;
}

function formatAvailabilityLabel(key: string, fallbackLabel: string): string {
  if (key === "runtime_started") {
    return "Стратегический контур";
  }
  if (key === "runtime_ready") {
    return "Готовность";
  }
  if (key === "tracked_context_keys") {
    return "Отслеживаемые ключи контекста";
  }
  if (key === "tracked_candidate_keys") {
    return "Отслеживаемые ключи кандидатов";
  }
  if (key === "actionable_candidate_keys") {
    return "Ключи кандидатов, готовых к действию";
  }
  if (key === "invalidated_candidate_keys") {
    return "Инвалидированные ключи кандидатов";
  }
  if (key === "expired_candidate_keys") {
    return "Истёкшие ключи кандидатов";
  }
  if (key === "last_signal_id") {
    return "Последний идентификатор сигнала";
  }
  if (key === "last_candidate_id") {
    return "Последний идентификатор кандидата";
  }
  return fallbackLabel;
}

function formatAvailabilityNote(key: string, note: string | null): string | null {
  if (note === null) {
    return null;
  }
  if (key === "runtime_started") {
    return "Глобальный флаг runtime без действий над стратегией.";
  }
  if (key === "runtime_ready") {
    return "Готовность отражает только выведенные диагностические данные стратегического контура.";
  }
  if (key === "tracked_context_keys") {
    return "Количество ключей стратегического контекста в текущем runtime-снимке.";
  }
  if (key === "tracked_candidate_keys") {
    return "Суммарный счётчик стратегических кандидатов без обозревателя истории.";
  }
  if (key === "actionable_candidate_keys") {
    return "Показывается только агрегированный счётчик кандидатов, готовых к действию.";
  }
  if (key === "invalidated_candidate_keys") {
    return "Показывается как выведенный счётчик без обозревателя деталей.";
  }
  if (key === "expired_candidate_keys") {
    return "Сводный индикатор свежести без обозревателя истории кандидатов.";
  }
  if (key === "last_signal_id") {
    return "Последняя выведенная ссылка на сигнал для стратегического контура.";
  }
  if (key === "last_candidate_id") {
    return "Последний выведенный стратегический кандидат без отдельного обозревателя.";
  }
  return note;
}

function formatSummaryNote(note: string): string {
  if (
    note.startsWith("Strategy runtime surfaced degraded reasons: ")
  ) {
    return `Стратегический контур вывел причины деградации: ${note.slice(
      "Strategy runtime surfaced degraded reasons: ".length,
    )}`;
  }

  if (
    note.startsWith("Strategy runtime surfaced readiness reasons: ")
  ) {
    return `Стратегический контур вывел причины неготовности: ${formatStrategyReasonDetails(
      note.slice("Strategy runtime surfaced readiness reasons: ".length),
    )}`;
  }

  if (
    note ===
    "Strategy runtime не surfaced дополнительных notes beyond current diagnostics."
  ) {
    return "Стратегический контур не вывел дополнительных пояснений сверх текущих диагностических данных.";
  }

  return note;
}

function formatStrategyReasonDetails(details: string): string {
  const reasonMap: Record<string, string> = {
    no_strategy_context_processed:
      "стратегический контекст ещё не был обработан в текущем runtime-снимке",
  };

  return details
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => reasonMap[item] ?? item)
    .join(", ");
}

function mapAvailabilityTone(
  status: StrategyAvailabilityItemResponse["status"],
): "neutral" | "accent" | "success" | "warning" | "danger" {
  if (status === "normal") {
    return "success";
  }
  if (status === "warning") {
    return "warning";
  }
  return "accent";
}

export function mapStrategy(snapshot: StrategySummaryResponse): StrategyViewModel {
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
          ? "стратегическое состояние выведено"
          : "стратегическое состояние прогревается",
        tone: snapshot.ready ? "success" : "warning",
      },
    ],
    summary: [
      {
        label: "Глобальный стратегический контур",
        value: formatGlobalStatus(snapshot.global_status),
      },
      {
        label: "Состояние жизненного цикла",
        value: formatStrategyLifecycleState(snapshot.lifecycle_state),
      },
      {
        label: "Стратегический контур запущен",
        value: snapshot.started ? "да" : "нет",
      },
      {
        label: "Активный путь стратегии",
        value: formatSurfacedState(snapshot.active_strategy_path),
      },
      {
        label: "Источник стратегии",
        value: formatSurfacedState(snapshot.strategy_source),
      },
    ],
    freshness: [
      {
        label: "Состояние свежести",
        value: formatSurfacedState(snapshot.freshness_state),
      },
      {
        label: "Последний идентификатор сигнала",
        value: snapshot.last_signal_id ?? "не выведен",
      },
      {
        label: "Последний идентификатор кандидата",
        value: snapshot.last_candidate_id ?? "не выведен",
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
        "Сводка по стратегии не содержит выведенной причины. Страница показывает только текущее состояние контура и счётчики доступности.",
      summaryNote: formatSummaryNote(snapshot.summary_note),
    },
  };
}

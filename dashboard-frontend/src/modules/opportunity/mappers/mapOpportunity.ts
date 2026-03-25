import type {
  OpportunityAvailabilityItemResponse,
  OpportunitySummaryResponse,
} from "../../../shared/types/dashboard";
import { formatModuleStatus } from "../../../shared/lib/dashboardText";

export type OpportunityViewModel = {
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
  status: OpportunitySummaryResponse["global_status"],
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

function formatGlobalStatus(status: OpportunitySummaryResponse["global_status"]): string {
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

function formatOpportunityLifecycleState(state: string): string {
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
  if (value === "expired_selections_present") {
    return "есть истёкшие selections";
  }
  if (value === "selected_opportunity_surfaced") {
    return "выведена отобранная возможность";
  }
  if (value === "selection_recently_surfaced") {
    return "selection недавно выведен";
  }
  if (value === "selection_state_surfaced") {
    return "состояние selection выведено";
  }
  return value;
}

function formatAvailabilityLabel(key: string, fallbackLabel: string): string {
  if (key === "runtime_started") {
    return "Контур возможностей";
  }
  if (key === "runtime_ready") {
    return "Готовность";
  }
  if (key === "tracked_context_keys") {
    return "Отслеживаемые ключи контекста";
  }
  if (key === "tracked_selection_keys") {
    return "Отслеживаемые ключи отбора";
  }
  if (key === "selected_keys") {
    return "Ключи отобранных возможностей";
  }
  if (key === "invalidated_selection_keys") {
    return "Инвалидированные ключи отбора";
  }
  if (key === "expired_selection_keys") {
    return "Истёкшие ключи отбора";
  }
  if (key === "last_intent_id") {
    return "Последний идентификатор намерения";
  }
  if (key === "last_selection_id") {
    return "Последний идентификатор отбора";
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
    return "Глобальный флаг runtime без действий над отбором возможностей.";
  }
  if (key === "runtime_ready") {
    return "Готовность отражает только выведенные диагностические данные контура возможностей.";
  }
  if (key === "tracked_context_keys") {
    return "Количество ключей opportunity context в текущем runtime-снимке.";
  }
  if (key === "tracked_selection_keys") {
    return "Суммарный счётчик selection keys без широкого обозревателя возможностей.";
  }
  if (key === "selected_keys") {
    return "Показывается только агрегированный счётчик текущих отобранных возможностей.";
  }
  if (key === "invalidated_selection_keys") {
    return "Показывается как выведенный счётчик без обозревателя деталей.";
  }
  if (key === "expired_selection_keys") {
    return "Сводный индикатор свежести без обозревателя истории отбора.";
  }
  if (key === "last_intent_id") {
    return "Последняя выведенная ссылка на execution intent для контура возможностей.";
  }
  if (key === "last_selection_id") {
    return "Последний выведенный opportunity selection без отдельного обозревателя.";
  }
  if (key === "last_event_type") {
    return "Последний выведенный тип события контура возможностей.";
  }
  return note;
}

function formatOpportunityReasonDetails(details: string): string {
  const reasonMap: Record<string, string> = {
    no_selection_context_processed:
      "контекст возможностей ещё не был обработан в текущем runtime-снимке",
    runtime_stopped: "runtime возможностей остановлен",
    runtime_degraded: "контур возможностей находится в деградированном состоянии",
    intent_ingest_failed: "обработка execution intent завершилась ошибкой",
    execution_context_warming: "execution context ещё прогревается",
    execution_context_invalid: "execution context находится в невалидном состоянии",
    priority_score_below_threshold: "приоритет возможности ниже допустимого порога",
    intent_confidence_below_threshold:
      "у намерения исполнения недостаточная уверенность для отбора возможности",
  };

  return details
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => reasonMap[item] ?? item)
    .join(", ");
}

function formatSummaryNote(note: string): string {
  if (note.startsWith("Opportunity runtime surfaced degraded reasons: ")) {
    return `Контур возможностей вывел причины деградации: ${formatOpportunityReasonDetails(
      note.slice("Opportunity runtime surfaced degraded reasons: ".length),
    )}`;
  }

  if (note.startsWith("Opportunity runtime surfaced readiness reasons: ")) {
    return `Контур возможностей вывел причины неготовности: ${formatOpportunityReasonDetails(
      note.slice("Opportunity runtime surfaced readiness reasons: ".length),
    )}`;
  }

  if (
    note ===
    "Opportunity runtime не surfaced дополнительных notes beyond current diagnostics."
  ) {
    return "Контур возможностей не вывел дополнительных пояснений сверх текущих диагностических данных.";
  }

  return note;
}

function mapAvailabilityTone(
  status: OpportunityAvailabilityItemResponse["status"],
): "neutral" | "accent" | "success" | "warning" | "danger" {
  if (status === "normal") {
    return "success";
  }
  if (status === "warning") {
    return "warning";
  }
  return "accent";
}

export function mapOpportunity(snapshot: OpportunitySummaryResponse): OpportunityViewModel {
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
          ? "состояние возможностей выведено"
          : "состояние возможностей прогревается",
        tone: snapshot.ready ? "success" : "warning",
      },
    ],
    summary: [
      {
        label: "Глобальный контур возможностей",
        value: formatGlobalStatus(snapshot.global_status),
      },
      {
        label: "Состояние жизненного цикла",
        value: formatOpportunityLifecycleState(snapshot.lifecycle_state),
      },
      {
        label: "Контур возможностей запущен",
        value: snapshot.started ? "да" : "нет",
      },
      {
        label: "Активный путь возможностей",
        value: formatSurfacedState(snapshot.active_opportunity_path),
      },
      {
        label: "Источник отбора",
        value: formatSurfacedState(snapshot.opportunity_source),
      },
    ],
    freshness: [
      {
        label: "Состояние свежести",
        value: formatSurfacedState(snapshot.freshness_state),
      },
      {
        label: "Последний идентификатор намерения",
        value: snapshot.last_intent_id ?? "не выведен",
      },
      {
        label: "Последний идентификатор отбора",
        value: snapshot.last_selection_id ?? "не выведен",
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
        "Сводка по возможностям не содержит выведенной причины. Страница показывает только текущее состояние контура и счётчики доступности.",
      summaryNote: formatSummaryNote(snapshot.summary_note),
    },
  };
}

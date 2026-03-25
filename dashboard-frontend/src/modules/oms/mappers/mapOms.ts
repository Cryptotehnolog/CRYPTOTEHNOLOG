import type {
  OmsAvailabilityItemResponse,
  OmsSummaryResponse,
} from "../../../shared/types/dashboard";
import { formatModuleStatus } from "../../../shared/lib/dashboardText";

export type OmsViewModel = {
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
  status: OmsSummaryResponse["global_status"],
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

function formatGlobalStatus(status: OmsSummaryResponse["global_status"]): string {
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

function formatOmsLifecycleState(state: string): string {
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
  if (value === "active_order_surfaced") {
    return "выведен активный ордер";
  }
  if (value === "historical_order_surfaced") {
    return "выведен исторический ордер";
  }
  if (value === "order_recently_surfaced") {
    return "ордер недавно выведен";
  }
  return value;
}

function formatAvailabilityLabel(key: string, fallbackLabel: string): string {
  if (key === "runtime_started") {
    return "Контур OMS";
  }
  if (key === "runtime_ready") {
    return "Готовность";
  }
  if (key === "tracked_contexts") {
    return "Отслеживаемые контексты";
  }
  if (key === "tracked_active_orders") {
    return "Отслеживаемые активные ордера";
  }
  if (key === "tracked_historical_orders") {
    return "Отслеживаемые исторические ордера";
  }
  if (key === "last_intent_id") {
    return "Последний идентификатор намерения";
  }
  if (key === "last_order_id") {
    return "Последний идентификатор ордера";
  }
  return fallbackLabel;
}

function formatAvailabilityNote(key: string, note: string | null): string | null {
  if (note === null) {
    return null;
  }
  if (key === "runtime_started") {
    return "Глобальный флаг runtime без действий над ордерами.";
  }
  if (key === "runtime_ready") {
    return "Готовность отражает только выведенные диагностические данные OMS-контура.";
  }
  if (key === "tracked_contexts") {
    return "Количество OMS-контекстов в текущем runtime-снимке.";
  }
  if (key === "tracked_active_orders") {
    return "Суммарный счётчик активных ордеров без обозревателя ордеров.";
  }
  if (key === "tracked_historical_orders") {
    return "Суммарный счётчик исторических ордеров без браузера истории.";
  }
  if (key === "last_intent_id") {
    return "Последнее выведенное execution intent для OMS-контура.";
  }
  if (key === "last_order_id") {
    return "Последний выведенный OMS order id без order explorer.";
  }
  return note;
}

function formatOmsReasonToken(token: string): string {
  const trimmed = token.trim();
  const reasonMap: Record<string, string> = {
    no_execution_intent_processed:
      "намерение исполнения ещё не было обработано в текущем runtime-снимке",
    execution_intent_invalid: "намерение исполнения находится в невалидном состоянии",
    runtime_stopped: "runtime OMS остановлен",
    runtime_degraded: "runtime OMS находится в деградации",
    intent_ingest_failed: "обработка намерения исполнения завершилась ошибкой",
    execution_intent_invalidated: "намерение исполнения было инвалидировано",
    executable_execution_intent: "в контуре выведено исполнимое намерение",
  };

  return reasonMap[trimmed] ?? "runtime вернул непереведённую техническую причину";
}

function formatOmsReasonDetails(details: string): string {
  return details
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => formatOmsReasonToken(item))
    .join(", ");
}

function formatSummaryNote(note: string): string {
  if (note.startsWith("OMS runtime surfaced degraded reasons: ")) {
    return `Контур OMS вывел причины деградации: ${formatOmsReasonDetails(
      note.slice("OMS runtime surfaced degraded reasons: ".length),
    )}`;
  }

  if (note.startsWith("OMS runtime surfaced readiness reasons: ")) {
    return `Контур OMS вывел причины неготовности: ${formatOmsReasonDetails(
      note.slice("OMS runtime surfaced readiness reasons: ".length),
    )}`;
  }

  if (note === "OMS runtime не surfaced дополнительных notes beyond current diagnostics.") {
    return "Контур OMS не вывел дополнительных пояснений сверх текущих диагностических данных.";
  }

  return note;
}

function formatSummaryReason(reason: string | null): string {
  if (reason === null) {
    return "Сводка по OMS не содержит выведенной причины. Страница показывает только текущее состояние контура и счётчики доступности.";
  }
  return formatOmsReasonDetails(reason);
}

function mapAvailabilityTone(
  status: OmsAvailabilityItemResponse["status"],
): "neutral" | "accent" | "success" | "warning" | "danger" {
  if (status === "normal") {
    return "success";
  }
  if (status === "warning") {
    return "warning";
  }
  return "accent";
}

export function mapOms(snapshot: OmsSummaryResponse): OmsViewModel {
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
        label: snapshot.ready ? "состояние OMS выведено" : "состояние OMS прогревается",
        tone: snapshot.ready ? "success" : "warning",
      },
    ],
    summary: [
      {
        label: "Глобальный контур OMS",
        value: formatGlobalStatus(snapshot.global_status),
      },
      {
        label: "Состояние жизненного цикла",
        value: formatOmsLifecycleState(snapshot.lifecycle_state),
      },
      {
        label: "Контур OMS запущен",
        value: snapshot.started ? "да" : "нет",
      },
      {
        label: "Активный путь OMS",
        value: formatSurfacedState(snapshot.active_oms_path),
      },
      {
        label: "Источник OMS",
        value: formatSurfacedState(snapshot.oms_source),
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
        label: "Последний идентификатор ордера",
        value: snapshot.last_order_id ?? "не выведен",
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

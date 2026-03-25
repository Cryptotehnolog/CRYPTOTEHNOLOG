import type {
  ValidationAvailabilityItemResponse,
  ValidationSummaryResponse,
} from "../../../shared/types/dashboard";
import { formatModuleStatus } from "../../../shared/lib/dashboardText";

export type ValidationViewModel = {
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
  status: ValidationSummaryResponse["global_status"],
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

function formatGlobalStatus(status: ValidationSummaryResponse["global_status"]): string {
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

function formatValidationLifecycleState(state: string): string {
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
  if (value === "active_review_surfaced") {
    return "выведена активная проверка";
  }
  if (value === "historical_review_surfaced") {
    return "выведена историческая проверка";
  }
  if (value === "review_recently_surfaced") {
    return "проверка недавно выведена";
  }
  return value;
}

function formatAvailabilityLabel(key: string, fallbackLabel: string): string {
  if (key === "runtime_started") {
    return "Контур валидации";
  }
  if (key === "runtime_ready") {
    return "Готовность";
  }
  if (key === "tracked_contexts") {
    return "Отслеживаемые контексты";
  }
  if (key === "tracked_active_reviews") {
    return "Отслеживаемые активные проверки";
  }
  if (key === "tracked_historical_reviews") {
    return "Отслеживаемые исторические проверки";
  }
  if (key === "last_review_id") {
    return "Последний идентификатор проверки";
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
    return "Глобальный флаг выполнения без действий над проверками.";
  }
  if (key === "runtime_ready") {
    return "Готовность отражает только выведенные диагностические данные контура валидации.";
  }
  if (key === "tracked_contexts") {
    return "Количество контекстов валидации в текущем диагностическом снимке.";
  }
  if (key === "tracked_active_reviews") {
    return "Суммарный счётчик активных проверок без отдельного обозревателя.";
  }
  if (key === "tracked_historical_reviews") {
    return "Суммарный счётчик исторических проверок без браузера истории.";
  }
  if (key === "last_review_id") {
    return "Последний выведенный идентификатор проверки без отдельного обозревателя.";
  }
  if (key === "last_event_type") {
    return "Последний выведенный тип события контура валидации.";
  }
  return note;
}

function formatValidationReasonToken(token: string): string {
  const trimmed = token.trim();
  const reasonMap: Record<string, string> = {
    no_validation_review_processed:
      "проверка валидации ещё не была обработана в текущем диагностическом снимке",
    runtime_stopped: "контур валидации остановлен",
    runtime_degraded: "контур валидации находится в деградации",
    validation_context_invalid: "контекст валидации находится в невалидном состоянии",
    validation_candidate_expired: "кандидат валидации устарел до текущего снимка",
    review_ingest_failed: "обработка проверки завершилась ошибкой",
    protection: "часть входов валидации ещё не выведена на защитном контуре",
    manager: "часть входов валидации ещё не выведена на контуре менеджера",
    portfolio_governor: "часть входов валидации ещё не выведена на портфельном контуре",
    oms: "часть входов валидации ещё не выведена на контуре OMS",
  };

  return reasonMap[trimmed] ?? "контур вернул непереведённую техническую причину";
}

function formatValidationReasonDetails(details: string): string {
  return details
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => formatValidationReasonToken(item))
    .join(", ");
}

function formatSummaryNote(note: string): string {
  if (note.startsWith("Validation runtime surfaced degraded reasons: ")) {
    return `Контур валидации вывел причины деградации: ${formatValidationReasonDetails(
      note.slice("Validation runtime surfaced degraded reasons: ".length),
    )}`;
  }

  if (note.startsWith("Validation runtime surfaced readiness reasons: ")) {
    return `Контур валидации вывел причины неготовности: ${formatValidationReasonDetails(
      note.slice("Validation runtime surfaced readiness reasons: ".length),
    )}`;
  }

  if (
    note ===
    "Validation runtime не surfaced дополнительных notes beyond current diagnostics."
  ) {
    return "Контур валидации не вывел дополнительных пояснений сверх текущих диагностических данных.";
  }

  return note;
}

function formatSummaryReason(reason: string | null): string {
  if (reason === null) {
    return "Сводка по валидации не содержит выведенной причины. Страница показывает только текущее состояние контура и счётчики доступности.";
  }
  return formatValidationReasonDetails(reason);
}

function mapAvailabilityTone(
  status: ValidationAvailabilityItemResponse["status"],
): "neutral" | "accent" | "success" | "warning" | "danger" {
  if (status === "normal") {
    return "success";
  }
  if (status === "warning") {
    return "warning";
  }
  return "accent";
}

export function mapValidation(snapshot: ValidationSummaryResponse): ValidationViewModel {
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
          ? "состояние валидации выведено"
          : "состояние валидации прогревается",
        tone: snapshot.ready ? "success" : "warning",
      },
    ],
    summary: [
      {
        label: "Глобальный контур валидации",
        value: formatGlobalStatus(snapshot.global_status),
      },
      {
        label: "Состояние жизненного цикла",
        value: formatValidationLifecycleState(snapshot.lifecycle_state),
      },
      {
        label: "Контур валидации запущен",
        value: snapshot.started ? "да" : "нет",
      },
      {
        label: "Активный путь валидации",
        value: formatSurfacedState(snapshot.active_validation_path),
      },
      {
        label: "Источник валидации",
        value: formatSurfacedState(snapshot.validation_source),
      },
    ],
    freshness: [
      {
        label: "Состояние свежести",
        value: formatSurfacedState(snapshot.freshness_state),
      },
      {
        label: "Последний идентификатор проверки",
        value: snapshot.last_review_id ?? "не выведен",
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

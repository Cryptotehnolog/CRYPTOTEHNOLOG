import type {
  PaperAvailabilityItemResponse,
  PaperSummaryResponse,
} from "../../../shared/types/dashboard";
import { formatModuleStatus } from "../../../shared/lib/dashboardText";

export type PaperViewModel = {
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
  status: PaperSummaryResponse["global_status"],
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

function formatGlobalStatus(status: PaperSummaryResponse["global_status"]): string {
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

function formatPaperLifecycleState(state: string): string {
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
  if (value === "active_rehearsal_surfaced") {
    return "выведена активная репетиция";
  }
  if (value === "historical_rehearsal_surfaced") {
    return "выведена историческая репетиция";
  }
  if (value === "rehearsal_recently_surfaced") {
    return "репетиция недавно выведена";
  }
  return value;
}

function formatAvailabilityLabel(key: string, fallbackLabel: string): string {
  if (key === "runtime_started") {
    return "Пейпер-контур";
  }
  if (key === "runtime_ready") {
    return "Готовность";
  }
  if (key === "tracked_contexts") {
    return "Отслеживаемые контексты";
  }
  if (key === "tracked_active_rehearsals") {
    return "Отслеживаемые активные репетиции";
  }
  if (key === "tracked_historical_rehearsals") {
    return "Отслеживаемые исторические репетиции";
  }
  if (key === "last_rehearsal_id") {
    return "Последний идентификатор репетиции";
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
    return "Глобальный флаг выполнения без действий пейпер-контура.";
  }
  if (key === "runtime_ready") {
    return "Готовность отражает только выведенные диагностические данные пейпер-контура.";
  }
  if (key === "tracked_contexts") {
    return "Количество пейпер-контекстов в текущем диагностическом снимке.";
  }
  if (key === "tracked_active_rehearsals") {
    return "Суммарный счётчик активных репетиций без обозревателя репетиций.";
  }
  if (key === "tracked_historical_rehearsals") {
    return "Суммарный счётчик исторических репетиций без браузера истории.";
  }
  if (key === "last_rehearsal_id") {
    return "Последний выведенный идентификатор репетиции без обозревателя репетиций.";
  }
  if (key === "last_event_type") {
    return "Последний выведенный тип пейпер-события.";
  }
  return note;
}

function formatPaperReasonToken(token: string): string {
  const trimmed = token.trim();
  const reasonMap: Record<string, string> = {
    no_paper_rehearsal_processed:
      "репетиция пейпер-контура ещё не была обработана в текущем диагностическом снимке",
    runtime_stopped: "пейпер-контур остановлен",
    paper_context_invalid: "пейпер-контекст находится в невалидном состоянии",
    paper_candidate_expired: "пейпер-кандидат устарел до текущего снимка",
    paper_truths_missing_coordinates:
      "пейпер-контур не получил достаточные координаты из вышестоящих данных",
    no_active_paper_rehearsal: "в текущем диагностическом снимке нет активной пейпер-репетиции",
    rehearsal_ingest_failed: "обработка репетиции завершилась ошибкой",
    manager: "часть пейпер-входов ещё не выведена на контуре менеджера",
    validation: "часть пейпер-входов ещё не выведена на контуре валидации",
    oms: "часть пейпер-входов ещё не выведена на OMS-контуре",
    manager_not_coordinated: "контур менеджера ещё не выдал согласованное состояние",
    validation_not_ready: "контур валидации ещё не выдал готовое состояние",
    upstream_paper_truth_invalidated:
      "один из вышестоящих источников для пейпер-контура был инвалидирован",
    upstream_paper_truth_expired:
      "один из вышестоящих источников для пейпер-контура устарел до текущего снимка",
    paper_context_incomplete: "пейпер-контекст пока неполный",
  };

  if (trimmed.startsWith("rehearsal_ingest_failed:")) {
    return "обработка репетиции завершилась ошибкой";
  }

  return reasonMap[trimmed] ?? "контур вернул непереведённую техническую причину";
}

function formatPaperReasonDetails(details: string): string {
  return details
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => formatPaperReasonToken(item))
    .join(", ");
}

function formatSummaryNote(note: string): string {
  if (note.startsWith("Paper runtime surfaced degraded reasons: ")) {
    return `Пейпер-контур вывел причины деградации: ${formatPaperReasonDetails(
      note.slice("Paper runtime surfaced degraded reasons: ".length),
    )}`;
  }

  if (note.startsWith("Paper runtime surfaced readiness reasons: ")) {
    return `Пейпер-контур вывел причины неготовности: ${formatPaperReasonDetails(
      note.slice("Paper runtime surfaced readiness reasons: ".length),
    )}`;
  }

  if (note === "Paper runtime не surfaced дополнительных notes beyond current diagnostics.") {
    return "Пейпер-контур не вывел дополнительных пояснений сверх текущих диагностических данных.";
  }

  return note;
}

function formatSummaryReason(reason: string | null): string {
  if (reason === null) {
    return "Сводка по пейпер-контуру не содержит выведенной причины. Страница показывает только текущее состояние контура и счётчики доступности.";
  }
  return formatPaperReasonDetails(reason);
}

function mapAvailabilityTone(
  status: PaperAvailabilityItemResponse["status"],
): "neutral" | "accent" | "success" | "warning" | "danger" {
  if (status === "normal") {
    return "success";
  }
  if (status === "warning") {
    return "warning";
  }
  return "accent";
}

export function mapPaper(snapshot: PaperSummaryResponse): PaperViewModel {
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
        label:
          snapshot.ready
            ? "состояние пейпер-контура выведено"
            : "состояние пейпер-контура прогревается",
        tone: snapshot.ready ? "success" : "warning",
      },
    ],
    summary: [
      {
        label: "Глобальный пейпер-контур",
        value: formatGlobalStatus(snapshot.global_status),
      },
      {
        label: "Состояние жизненного цикла",
        value: formatPaperLifecycleState(snapshot.lifecycle_state),
      },
      {
        label: "Пейпер-контур запущен",
        value: snapshot.started ? "да" : "нет",
      },
      {
        label: "Активный путь пейпер-контура",
        value: formatSurfacedState(snapshot.active_paper_path),
      },
      {
        label: "Источник пейпер-контура",
        value: formatSurfacedState(snapshot.paper_source),
      },
    ],
    freshness: [
      {
        label: "Состояние свежести",
        value: formatSurfacedState(snapshot.freshness_state),
      },
      {
        label: "Последний идентификатор репетиции",
        value: snapshot.last_rehearsal_id ?? "не выведен",
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

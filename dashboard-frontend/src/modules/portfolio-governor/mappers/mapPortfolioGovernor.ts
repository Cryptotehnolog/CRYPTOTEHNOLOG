import type {
  PortfolioGovernorAvailabilityItemResponse,
  PortfolioGovernorSummaryResponse,
} from "../../../shared/types/dashboard";
import { formatModuleStatus } from "../../../shared/lib/dashboardText";

export type PortfolioGovernorViewModel = {
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
  status: PortfolioGovernorSummaryResponse["global_status"],
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

function formatGlobalStatus(status: PortfolioGovernorSummaryResponse["global_status"]): string {
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
  if (value === "approved_governor_surfaced") {
    return "выведено одобренное решение портфельного контура";
  }
  if (value === "invalidated_governor_present") {
    return "есть инвалидированные решения";
  }
  if (value === "expired_governor_present") {
    return "есть истёкшие решения";
  }
  if (value === "governor_recently_surfaced") {
    return "решение портфельного контура недавно выведено";
  }
  return value;
}

function formatAvailabilityLabel(key: string, fallbackLabel: string): string {
  if (key === "runtime_started") {
    return "Портфельный контур";
  }
  if (key === "runtime_ready") {
    return "Готовность";
  }
  if (key === "tracked_context_keys") {
    return "Отслеживаемые ключи контекста";
  }
  if (key === "tracked_governor_keys") {
    return "Отслеживаемые ключи решений";
  }
  if (key === "approved_keys") {
    return "Одобренные ключи";
  }
  if (key === "abstained_keys") {
    return "Ключи воздержавшихся решений";
  }
  if (key === "rejected_keys") {
    return "Ключи отклонённых решений";
  }
  if (key === "invalidated_governor_keys") {
    return "Инвалидированные ключи решений";
  }
  if (key === "expired_governor_keys") {
    return "Истёкшие ключи решений";
  }
  if (key === "last_expansion_id") {
    return "Последний идентификатор расширения";
  }
  if (key === "last_governor_id") {
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
    return "Глобальный флаг контура без действий перераспределения капитала.";
  }
  if (key === "runtime_ready") {
    return "Готовность отражает только выведенные диагностические данные портфельного контура.";
  }
  if (key === "tracked_context_keys") {
    return "Количество ключей контекста портфельного контура в текущем снимке.";
  }
  if (key === "tracked_governor_keys") {
    return "Суммарный счётчик решений портфельного контура без широкого обозревателя.";
  }
  if (key === "approved_keys") {
    return "Показывается только агрегированный счётчик одобренных решений без действий по распределению капитала.";
  }
  if (key === "abstained_keys") {
    return "Сводный счётчик воздержавшихся решений без операторских переопределений.";
  }
  if (key === "rejected_keys") {
    return "Сводный счётчик отклонённых решений портфельного контура.";
  }
  if (key === "invalidated_governor_keys") {
    return "Показывается как выведенный счётчик без обозревателя деталей.";
  }
  if (key === "expired_governor_keys") {
    return "Сводный индикатор свежести без истории решений и без логики живых изменений.";
  }
  if (key === "last_expansion_id") {
    return "Последняя выведенная ссылка на расширение позиции для портфельного контура.";
  }
  if (key === "last_governor_id") {
    return "Последний выведенный идентификатор решения без отдельного обозревателя.";
  }
  if (key === "last_event_type") {
    return "Последний выведенный тип события портфельного контура.";
  }
  return note;
}

function formatReasonDetails(details: string): string {
  const reasonMap: Record<string, string> = {
    no_portfolio_governor_context_processed:
      "контекст портфельного контура ещё не был обработан в текущем снимке",
    runtime_stopped: "портфельный контур остановлен",
    runtime_degraded: "портфельный контур находится в деградации",
    position_expansion_expired: "источник расширения позиции уже истёк",
    position_expansion_invalidated: "источник расширения позиции был инвалидирован",
    position_expansion_rejected: "источник расширения позиции был отклонён",
    position_expansion_abstained: "источник расширения позиции завершился воздержанием",
    approvable_expansion: "контур ещё ожидает подтверждаемое расширение позиции",
  };

  return details
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => reasonMap[item] ?? item)
    .join(", ");
}

function formatSummaryNote(note: string): string {
  if (note.startsWith("Portfolio governor runtime surfaced degraded reasons: ")) {
    return `Портфельный контур вывел причины деградации: ${formatReasonDetails(
      note.slice("Portfolio governor runtime surfaced degraded reasons: ".length),
    )}`;
  }

  if (note.startsWith("Portfolio governor runtime surfaced readiness reasons: ")) {
    return `Портфельный контур вывел причины неготовности: ${formatReasonDetails(
      note.slice("Portfolio governor runtime surfaced readiness reasons: ".length),
    )}`;
  }

  if (
    note ===
    "Portfolio governor runtime не surfaced дополнительных notes beyond current diagnostics."
  ) {
    return "Портфельный контур не вывел дополнительных пояснений сверх текущих диагностических данных.";
  }

  return note;
}

function mapAvailabilityTone(
  status: PortfolioGovernorAvailabilityItemResponse["status"],
): "neutral" | "accent" | "success" | "warning" | "danger" {
  if (status === "normal") {
    return "success";
  }
  if (status === "warning") {
    return "warning";
  }
  return "accent";
}

export function mapPortfolioGovernor(
  snapshot: PortfolioGovernorSummaryResponse,
): PortfolioGovernorViewModel {
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
          ? "состояние портфельного контура выведено"
          : "состояние портфельного контура прогревается",
        tone: snapshot.ready ? "success" : "warning",
      },
    ],
    summary: [
      {
        label: "Глобальный портфельный контур",
        value: formatGlobalStatus(snapshot.global_status),
      },
      {
        label: "Состояние жизненного цикла",
        value: formatLifecycleState(snapshot.lifecycle_state),
      },
      {
        label: "Портфельный контур запущен",
        value: snapshot.started ? "да" : "нет",
      },
      {
        label: "Активный путь портфельного контура",
        value: snapshot.active_portfolio_governor_path,
      },
      {
        label: "Источник портфельного контура",
        value: snapshot.portfolio_governor_source,
      },
    ],
    freshness: [
      {
        label: "Состояние свежести",
        value: formatSurfacedState(snapshot.freshness_state),
      },
      {
        label: "Последний идентификатор расширения",
        value: snapshot.last_expansion_id ?? "не выведен",
      },
      {
        label: "Последний идентификатор решения",
        value: snapshot.last_governor_id ?? "не выведен",
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
        "Сводка по портфельному контуру не содержит выведенной причины. Страница показывает только текущее состояние контура и счётчики доступности.",
    },
  };
}

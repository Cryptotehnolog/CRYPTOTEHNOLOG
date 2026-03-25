import type {
  BacktestAvailabilityItemResponse,
  BacktestSummaryResponse,
} from "../../../shared/types/dashboard";
import { formatModuleStatus } from "../../../shared/lib/dashboardText";

export type BacktestViewModel = {
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
  status: BacktestSummaryResponse["global_status"],
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

function formatGlobalStatus(status: BacktestSummaryResponse["global_status"]): string {
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

function formatBacktestLifecycleState(state: string): string {
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
  if (state === "not_started") {
    return "не запущен";
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
  if (value === "active_replay_surfaced") {
    return "выведен активный прогон";
  }
  if (value === "historical_replay_surfaced") {
    return "выведен исторический прогон";
  }
  if (value === "replay_recently_surfaced") {
    return "прогон недавно выведен";
  }
  return value;
}

function formatAvailabilityLabel(key: string, fallbackLabel: string): string {
  if (key === "runtime_started") {
    return "Бэктест-контур";
  }
  if (key === "runtime_ready") {
    return "Готовность";
  }
  if (key === "tracked_inputs") {
    return "Отслеживаемые входы";
  }
  if (key === "tracked_contexts") {
    return "Отслеживаемые контексты";
  }
  if (key === "tracked_active_replays") {
    return "Отслеживаемые активные прогоны";
  }
  if (key === "tracked_historical_replays") {
    return "Отслеживаемые исторические прогоны";
  }
  if (key === "last_replay_id") {
    return "Последний идентификатор прогона";
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
    return "Глобальный флаг выполнения без ручного управления прогонами.";
  }
  if (key === "runtime_ready") {
    return "Готовность отражает только выведенные диагностические данные бэктест-контура.";
  }
  if (key === "tracked_inputs") {
    return "Количество исторических входов в текущем диагностическом снимке.";
  }
  if (key === "tracked_contexts") {
    return "Количество бэктест-контекстов в текущем диагностическом снимке.";
  }
  if (key === "tracked_active_replays") {
    return "Суммарный счётчик активных прогонов без ручного управления.";
  }
  if (key === "tracked_historical_replays") {
    return "Суммарный счётчик исторических прогонов без браузера истории.";
  }
  if (key === "last_replay_id") {
    return "Последний выведенный идентификатор прогона без обозревателя прогонов.";
  }
  if (key === "last_event_type") {
    return "Последний выведенный тип события бэктест-контура.";
  }
  return note;
}

function formatBacktestReasonToken(token: string): string {
  const trimmed = token.trim();
  const reasonMap: Record<string, string> = {
    no_replay_processed: "исторический прогон ещё не был обработан в текущем диагностическом снимке",
    runtime_stopped: "бэктест-контур остановлен",
    replay_candidate_expired: "кандидат прогона устарел до текущего снимка",
    replay_context_invalid: "контекст прогона находится в невалидном состоянии",
    no_active_replay: "в текущем диагностическом снимке нет активного прогона",
    coverage_window_incomplete: "историческое окно покрытия пока неполное",
    historical_input_empty_or_invalid: "исторический вход пустой или невалидный",
    historical_input_lookahead_detected: "обнаружено заглядывание вперёд в историческом входе",
    historical_input_window_regressed: "историческое окно данных регрессировало",
    historical_input_coverage_drift_detected:
      "обнаружен дрейф покрытия в исторических данных",
    manual_replay_degraded: "контур зафиксировал деградацию контура прогонов",
  };

  return reasonMap[trimmed] ?? "контур вернул непереведённую техническую причину";
}

function formatBacktestReasonDetails(details: string): string {
  return details
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => formatBacktestReasonToken(item))
    .join(", ");
}

function formatSummaryNote(note: string): string {
  if (note.startsWith("Backtest runtime surfaced degraded reasons: ")) {
    return `Бэктест-контур вывел причины деградации: ${formatBacktestReasonDetails(
      note.slice("Backtest runtime surfaced degraded reasons: ".length),
    )}`;
  }

  if (note.startsWith("Backtest runtime surfaced readiness reasons: ")) {
    return `Бэктест-контур вывел причины неготовности: ${formatBacktestReasonDetails(
      note.slice("Backtest runtime surfaced readiness reasons: ".length),
    )}`;
  }

  if (note === "Backtest runtime не surfaced дополнительных notes beyond current diagnostics.") {
    return "Бэктест-контур не вывел дополнительных пояснений сверх текущих диагностических данных.";
  }

  return note;
}

function formatSummaryReason(reason: string | null): string {
  if (reason === null) {
    return "Сводка по бэктест-контуру не содержит выведенной причины. Страница показывает только текущее состояние контура и счётчики доступности.";
  }
  return formatBacktestReasonDetails(reason);
}

function mapAvailabilityTone(
  status: BacktestAvailabilityItemResponse["status"],
): "neutral" | "accent" | "success" | "warning" | "danger" {
  if (status === "normal") {
    return "success";
  }
  if (status === "warning") {
    return "warning";
  }
  return "accent";
}

export function mapBacktest(snapshot: BacktestSummaryResponse): BacktestViewModel {
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
          ? "состояние бэктест-контура выведено"
          : "состояние бэктест-контура прогревается",
        tone: snapshot.ready ? "success" : "warning",
      },
    ],
    summary: [
      {
        label: "Глобальный бэктест-контур",
        value: formatGlobalStatus(snapshot.global_status),
      },
      {
        label: "Состояние жизненного цикла",
        value: formatBacktestLifecycleState(snapshot.lifecycle_state),
      },
      {
        label: "Бэктест-контур запущен",
        value: snapshot.started ? "да" : "нет",
      },
      {
        label: "Активный путь бэктест-контура",
        value: formatSurfacedState(snapshot.active_backtest_path),
      },
      {
        label: "Источник бэктест-контура",
        value: formatSurfacedState(snapshot.backtest_source),
      },
    ],
    freshness: [
      {
        label: "Состояние свежести",
        value: formatSurfacedState(snapshot.freshness_state),
      },
      {
        label: "Последний идентификатор прогона",
        value: snapshot.last_replay_id ?? "не выведен",
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

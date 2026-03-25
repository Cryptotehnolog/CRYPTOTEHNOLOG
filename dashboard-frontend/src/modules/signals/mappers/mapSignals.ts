import type { SignalAvailabilityItemResponse, SignalsSummaryResponse } from "../../../shared/types/dashboard";
import { formatModuleStatus } from "../../../shared/lib/dashboardText";

export type SignalsViewModel = {
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
  reason: {
    hasReason: boolean;
    message: string;
  };
};

function mapGlobalTone(
  status: SignalsSummaryResponse["global_status"],
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

function formatGlobalStatus(status: SignalsSummaryResponse["global_status"]): string {
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

function formatSignalLifecycleState(state: string): string {
  if (state === "warming") {
    return "прогрев";
  }
  if (state === "started") {
    return "запущен";
  }
  if (state === "ready") {
    return "готов";
  }
  if (state === "not ready") {
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
  if (value === "warming") {
    return "прогрев";
  }
  if (value === "not ready") {
    return "не готов";
  }
  return value;
}

function formatAvailabilityLabel(key: string, fallbackLabel: string): string {
  if (key === "runtime_started") {
    return "Сигнальный контур";
  }
  if (key === "runtime_ready") {
    return "Готовность";
  }
  if (key === "tracked_signal_keys") {
    return "Отслеживаемые ключи сигналов";
  }
  if (key === "active_signal_keys") {
    return "Активные ключи сигналов";
  }
  if (key === "invalidated_signal_keys") {
    return "Инвалидированные ключи сигналов";
  }
  if (key === "expired_signal_keys") {
    return "Истёкшие ключи сигналов";
  }
  if (key === "last_context_at") {
    return "Последний контекст";
  }
  if (key === "last_signal_id") {
    return "Последний идентификатор сигнала";
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
    return "Глобальный флаг runtime без действий над сигналами.";
  }
  if (key === "runtime_ready") {
    return "Готовность отражает только выведенные диагностические данные сигнального контура.";
  }
  if (key === "tracked_signal_keys") {
    return "Количество ключей сигналов в текущем runtime-снимке.";
  }
  if (key === "active_signal_keys") {
    return "Только агрегированный счётчик без обозревателя кандидатов.";
  }
  if (key === "invalidated_signal_keys") {
    return "Показывается как выведенный счётчик без обозревателя истории.";
  }
  if (key === "expired_signal_keys") {
    return "Сводный индикатор свежести без потокового просмотра.";
  }
  if (key === "last_context_at") {
    return "Последняя наблюдаемая отметка контекста, если она выведена в текущем runtime-состоянии.";
  }
  if (key === "last_signal_id") {
    return "Последний идентификатор сигнала, если он выведен в текущем runtime-состоянии.";
  }
  if (key === "last_event_type") {
    return "Последний тип события, если он выведен в текущем runtime-состоянии.";
  }
  return note;
}

function mapAvailabilityTone(
  status: SignalAvailabilityItemResponse["status"],
): "neutral" | "accent" | "success" | "warning" | "danger" {
  if (status === "normal") {
    return "success";
  }
  if (status === "warning") {
    return "warning";
  }
  return "accent";
}

export function mapSignals(snapshot: SignalsSummaryResponse): SignalsViewModel {
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
        label: snapshot.ready ? "сигнальное состояние выведено" : "сигнальное состояние прогревается",
        tone: snapshot.ready ? "success" : "warning",
      },
    ],
    summary: [
      {
        label: "Глобальный сигнальный контур",
        value: formatGlobalStatus(snapshot.global_status),
      },
      {
        label: "Состояние жизненного цикла",
        value: formatSignalLifecycleState(snapshot.lifecycle_state),
      },
      {
        label: "Сигнальный контур запущен",
        value: snapshot.started ? "да" : "нет",
      },
      {
        label: "Активный путь сигналов",
        value: snapshot.active_signal_path,
      },
    ],
    freshness: [
      {
        label: "Состояние свежести",
        value: formatSurfacedState(snapshot.freshness_state),
      },
      {
        label: "Последний контекст",
        value: snapshot.last_context_at ?? "не выведен",
      },
      {
        label: "Последний идентификатор сигнала",
        value: snapshot.last_signal_id ?? "не выведен",
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
    reason: {
      hasReason: snapshot.summary_reason !== null,
      message:
        snapshot.summary_reason ??
        "Сводка по сигналам не содержит выведенной причины. Страница показывает только текущее состояние контура и счётчики доступности.",
    },
  };
}

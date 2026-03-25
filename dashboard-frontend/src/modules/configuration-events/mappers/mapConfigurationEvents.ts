import type { OverviewSnapshotResponse } from "../../../shared/types/dashboard";
import { formatBooleanWord } from "../../../shared/lib/dashboardText";

export type ConfigurationEventsViewModel = {
  moduleState: "inactive" | "read-only" | "active" | "restricted";
  statusBadges: Array<{
    label: string;
    tone: "neutral" | "accent" | "success" | "warning" | "danger";
  }>;
  eventCounters: Array<{ label: string; value: string | number }>;
  deliveryTruth: Array<{ label: string; value: string | number }>;
  configurationTruth: Array<{ label: string; value: string | number }>;
};

function formatBackpressureStrategy(value: string): string {
  if (value === "drop_low") {
    return "сбрасывать низкий приоритет";
  }
  if (value === "drop_normal") {
    return "сбрасывать обычный приоритет";
  }
  if (value === "overflow_normal") {
    return "переполнение для обычного приоритета";
  }
  if (value === "block_critical") {
    return "блокировать критический поток";
  }
  if (value === "unknown") {
    return "неизвестно";
  }
  return value;
}

export function mapConfigurationEvents(
  snapshot: OverviewSnapshotResponse,
): ConfigurationEventsViewModel {
  const module =
    snapshot.module_availability.find((item) => item.key === "config-events") ?? null;

  return {
    moduleState: module?.status ?? "inactive",
    statusBadges: [
      {
        label: snapshot.event_summary.persistence_enabled
          ? "персистентность включена"
          : "персистентность выключена",
        tone: snapshot.event_summary.persistence_enabled ? "accent" : "neutral",
      },
      {
        label: `стратегия обратного давления: ${formatBackpressureStrategy(
          snapshot.event_summary.backpressure_strategy,
        )}`,
        tone: snapshot.event_summary.total_rate_limited > 0 ? "warning" : "neutral",
      },
    ],
    eventCounters: [
      {
        label: "Опубликовано",
        value: snapshot.event_summary.total_published,
      },
      {
        label: "Доставлено",
        value: snapshot.event_summary.total_delivered,
      },
      {
        label: "Отброшено",
        value: snapshot.event_summary.total_dropped,
      },
      {
        label: "Ограничено по скорости",
        value: snapshot.event_summary.total_rate_limited,
      },
    ],
    deliveryTruth: [
      {
        label: "Подписчиков",
        value: snapshot.event_summary.subscriber_count,
      },
      {
        label: "Персистентность",
        value: formatBooleanWord(snapshot.event_summary.persistence_enabled),
      },
      {
        label: "Стратегия обратного давления",
        value: formatBackpressureStrategy(snapshot.event_summary.backpressure_strategy),
      },
    ],
    configurationTruth: [
      {
        label: "Снимок конфигурации",
        value: "не выведен",
      },
      {
        label: "Секреты и редактор",
        value: "вне границ страницы",
      },
      {
        label: "Текущее состояние страницы",
        value: "только сводка событий",
      },
    ],
  };
}

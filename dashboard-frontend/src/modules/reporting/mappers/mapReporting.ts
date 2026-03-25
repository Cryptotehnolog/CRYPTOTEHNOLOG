import type { ReportingSummaryResponse } from "../../../shared/types/dashboard";
import { formatModuleStatus } from "../../../shared/lib/dashboardText";

export type ReportingViewModel = {
  moduleState: "inactive" | "read-only" | "active" | "restricted";
  statusBadges: Array<{
    label: string;
    tone: "neutral" | "accent" | "success" | "warning" | "danger";
  }>;
  summary: Array<{ label: string; value: string | number }>;
  counts: Array<{ label: string; value: string | number }>;
  lastArtifact: Array<{ label: string; value: string | number }>;
  lastBundle: Array<{ label: string; value: string | number }>;
  note: {
    hasReason: boolean;
    message: string;
    summaryNote: string;
  };
};

function mapGlobalTone(
  status: ReportingSummaryResponse["global_status"],
): "neutral" | "accent" | "success" | "warning" | "danger" {
  if (status === "ready") {
    return "success";
  }
  if (status === "warming") {
    return "warning";
  }
  return "neutral";
}

function formatGlobalStatus(status: ReportingSummaryResponse["global_status"]): string {
  if (status === "ready") {
    return "bundle выведен";
  }
  if (status === "warming") {
    return "каталог прогревается";
  }
  return "каталог пуст";
}

function formatArtifactKind(value: string): string {
  if (value === "validation_report") {
    return "отчёт по валидации";
  }
  if (value === "paper_report") {
    return "отчёт по пейпер-контуру";
  }
  if (value === "replay_report") {
    return "отчёт по бэктесту";
  }
  return value;
}

function formatArtifactStatus(value: string): string {
  if (value === "ready") {
    return "готов";
  }
  if (value === "warming") {
    return "прогревается";
  }
  if (value === "invalid") {
    return "невалиден";
  }
  return value;
}

function formatSourceLayer(value: string): string {
  if (value === "validation") {
    return "валидация";
  }
  if (value === "paper") {
    return "пейпер";
  }
  if (value === "replay") {
    return "бэктест";
  }
  return value;
}

function formatTimestamp(value: string | null): string {
  if (value === null) {
    return "не выведено";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleString("ru-RU");
}

function formatReasonToken(value: string): string {
  if (value === "paper_warming") {
    return "артефакт пейпер-контура ещё прогревается";
  }
  if (value === "review_warming") {
    return "артефакт валидации ещё прогревается";
  }
  if (value === "replay_warming") {
    return "артефакт бэктеста ещё прогревается";
  }
  if (value === "paper_invalid") {
    return "артефакт пейпер-контура признан невалидным";
  }
  if (value === "review_invalid") {
    return "артефакт валидации признан невалидным";
  }
  if (value === "replay_invalid") {
    return "артефакт бэктеста признан невалидным";
  }
  return `сервер вернул код причины: ${value}`;
}

function formatSummaryNote(note: string): string {
  if (
    note ===
    "Каталог reporting artifacts пока не вывел ни одного surfaced artifact или bundle."
  ) {
    return "Каталог отчётных артефактов пока не вывел ни одного артефакта или bundle-снимка.";
  }
  if (
    note ===
    "Каталог reporting artifacts уже вывел как минимум один bundle и остаётся read-only summary surface без delivery или export semantics."
  ) {
    return "Каталог отчётных артефактов уже вывел как минимум один bundle-снимок и остаётся поверхностью только для чтения без доставки или выгрузки.";
  }
  if (
    note ===
    "Каталог reporting artifacts уже вывел отдельные artifacts по слоям validation, paper, replay, но bundle truth ещё не surfaced."
  ) {
    return "Каталог отчётных артефактов уже вывел отдельные артефакты по слоям валидации, пейпер-контура и бэктеста, но bundle-снимок ещё не выведен.";
  }
  if (note === "Каталог reporting artifacts остаётся в промежуточном surfaced состоянии.") {
    return "Каталог отчётных артефактов остаётся в промежуточном выведенном состоянии.";
  }
  return note;
}

function formatSummaryReason(reason: string | null): string {
  if (reason === null) {
    return "Сводка по отчётности не содержит отдельной выведенной причины. Страница показывает только текущее состояние каталога и краткие счётчики.";
  }
  return formatReasonToken(reason);
}

export function mapReporting(snapshot: ReportingSummaryResponse): ReportingViewModel {
  const lastArtifact = snapshot.last_artifact_snapshot;
  const lastBundle = snapshot.last_bundle_snapshot;

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
          snapshot.catalog_counts.total_bundles > 0
            ? "bundle-снимок выведен"
            : snapshot.catalog_counts.total_artifacts > 0
              ? "артефакты выведены"
              : "каталог ещё пуст",
        tone:
          snapshot.catalog_counts.total_bundles > 0
            ? "success"
            : snapshot.catalog_counts.total_artifacts > 0
              ? "warning"
              : "neutral",
      },
    ],
    summary: [
      {
        label: "Статус модуля",
        value: formatModuleStatus(snapshot.module_status),
      },
      {
        label: "Глобальный статус каталога",
        value: formatGlobalStatus(snapshot.global_status),
      },
      {
        label: "Всего артефактов",
        value: snapshot.catalog_counts.total_artifacts,
      },
      {
        label: "Всего bundle-снимков",
        value: snapshot.catalog_counts.total_bundles,
      },
    ],
    counts: [
      {
        label: "Артефакты валидации",
        value: snapshot.catalog_counts.validation_artifacts,
      },
      {
        label: "Артефакты пейпер-контура",
        value: snapshot.catalog_counts.paper_artifacts,
      },
      {
        label: "Артефакты бэктеста",
        value: snapshot.catalog_counts.replay_artifacts,
      },
    ],
    lastArtifact: [
      {
        label: "Последний тип артефакта",
        value: lastArtifact ? formatArtifactKind(lastArtifact.kind) : "не выведен",
      },
      {
        label: "Статус артефакта",
        value: lastArtifact ? formatArtifactStatus(lastArtifact.status) : "не выведен",
      },
      {
        label: "Исходный слой",
        value: lastArtifact ? formatSourceLayer(lastArtifact.source_layer) : "не выведен",
      },
      {
        label: "Время генерации",
        value: formatTimestamp(lastArtifact?.generated_at ?? null),
      },
    ],
    lastBundle: [
      {
        label: "Имя bundle-снимка",
        value: lastBundle?.reporting_name ?? "не выведен",
      },
      {
        label: "Время генерации bundle-снимка",
        value: formatTimestamp(lastBundle?.generated_at ?? null),
      },
      {
        label: "Артефактов внутри",
        value: lastBundle?.artifact_count ?? "не выведено",
      },
    ],
    note: {
      hasReason: snapshot.summary_reason !== null,
      message: formatSummaryReason(snapshot.summary_reason),
      summaryNote: formatSummaryNote(snapshot.summary_note),
    },
  };
}

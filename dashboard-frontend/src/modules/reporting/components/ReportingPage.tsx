import { Badge } from "../../../shared/ui/primitives/Badge";
import { KeyValueList } from "../../../shared/ui/primitives/KeyValueList";
import { Panel } from "../../../shared/ui/primitives/Panel";
import { EmptyState } from "../../../shared/ui/states/EmptyState";
import { ErrorState } from "../../../shared/ui/states/ErrorState";
import { LoadingState } from "../../../shared/ui/states/LoadingState";
import { ModuleStateCard } from "../../../shared/ui/states/ModuleStateCard";
import { useReportingSummary } from "../hooks/useReportingSummary";
import { mapReporting } from "../mappers/mapReporting";
import {
  availabilityHeader,
  availabilityItem,
  availabilityLabel,
  availabilityList,
  availabilityMeta,
  availabilityNote,
  pageStack,
  sectionGrid,
  topBanner,
} from "./ReportingPage.css";

export function ReportingPage() {
  const reportingQuery = useReportingSummary();

  if (reportingQuery.isLoading) {
    return (
      <LoadingState
        title="Загрузка сводки по отчётности"
        caption="Панель запрашивает узкий снимок каталога отчётных артефактов в режиме только чтения без выгрузки, доставки и управляющих действий."
        message="Интерфейс ожидает сводку по отчётности из серверного контура панели."
      />
    );
  }

  if (reportingQuery.isError) {
    const message =
      reportingQuery.error instanceof Error
        ? reportingQuery.error.message
        : "Не удалось загрузить сводку по отчётности.";

    return (
      <ErrorState
        title="Ошибка загрузки сводки по отчётности"
        caption="Страница отчётности остаётся поддерживающей поверхностью только для чтения и зависит только от узкой сводки каталога отчётных артефактов."
        message={message}
      />
    );
  }

  if (!reportingQuery.data) {
    return (
      <EmptyState
        title="Сводка по отчётности недоступна"
        message="Сервер панели не вернул модель чтения сводки по отчётности."
      />
    );
  }

  const model = mapReporting(reportingQuery.data);

  if (model.moduleState === "inactive") {
    return (
      <ModuleStateCard
        title="Отчётность"
        status="inactive"
        message="Страница отчётности предусмотрена в основе панели, но снимок только для чтения для неё ещё не подключён."
      />
    );
  }

  return (
    <div className={pageStack}>
      <div className={topBanner}>
        {model.statusBadges.map((badge) => (
          <Badge key={`${badge.label}-${badge.tone}`} tone={badge.tone}>
            {badge.label}
          </Badge>
        ))}
      </div>

      <div className={sectionGrid}>
        <Panel
          title="Состояние каталога отчётности"
          caption="Глобальный снимок каталога отчётных артефактов в режиме только чтения без обозревателя, выгрузки или семантики доставки."
        >
          <KeyValueList items={model.summary} />
        </Panel>

        <Panel
          title="Последний выведенный артефакт"
          caption="Показывается только последний честно выведенный артефакт, если он уже выведен серверным каталогом."
        >
          <KeyValueList items={model.lastArtifact} />
        </Panel>
      </div>

      <div className={sectionGrid}>
        <Panel
          title="Последний выведенный bundle-снимок"
          caption="Показывается только последний честно выведенный bundle-снимок, если он уже выведен серверным каталогом."
        >
          <KeyValueList items={model.lastBundle} />
        </Panel>

        <Panel
          title="Счётчики каталога"
          caption="Короткий список агрегированных счётчиков каталога без обозревателя артефактов и без разворачивания содержимого bundle-снимков."
          aside={
            <Badge tone={model.counts.some((item) => Number(item.value) > 0) ? "warning" : "neutral"}>
              {model.counts.some((item) => Number(item.value) > 0)
                ? `выведено: ${model.counts.length}`
                : "каталог пуст"}
            </Badge>
          }
        >
          {model.counts.length > 0 ? (
            <div className={availabilityList}>
              {model.counts.map((item) => (
                <div key={item.label} className={availabilityItem}>
                  <div className={availabilityHeader}>
                    <div className={availabilityMeta}>
                      <span className={availabilityLabel}>{item.label}</span>
                      <span>{item.value}</span>
                    </div>
                    <Badge tone={Number(item.value) > 0 ? "warning" : "neutral"}>
                      {item.value}
                    </Badge>
                  </div>
                  <p className={availabilityNote}>
                    Показан только агрегированный счётчик каталога без детального режима обозревателя.
                  </p>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState
              title="Счётчики отчётности не выведены"
              message="Текущий серверный контур не вернул ни одного агрегированного счётчика для страницы отчётности."
            />
          )}
        </Panel>
      </div>

      <Panel
        title="Примечание и причина"
        caption="Показываются только выведенные примечание и причина или честно фиксируется отсутствие дополнительного пояснения."
        aside={
          <Badge tone={model.note.hasReason ? "warning" : "neutral"}>
            {model.note.hasReason ? "причина выведена" : "причина отсутствует"}
          </Badge>
        }
      >
        <KeyValueList
          items={[
            {
              label: "Примечание каталога",
              value: model.note.summaryNote,
            },
            {
              label: "Причина сводки",
              value: model.note.message,
            },
          ]}
        />
      </Panel>
    </div>
  );
}

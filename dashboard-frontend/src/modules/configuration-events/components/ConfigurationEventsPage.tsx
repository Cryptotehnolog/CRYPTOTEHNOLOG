import { Badge } from "../../../shared/ui/primitives/Badge";
import { KeyValueList } from "../../../shared/ui/primitives/KeyValueList";
import { Panel } from "../../../shared/ui/primitives/Panel";
import { EmptyState } from "../../../shared/ui/states/EmptyState";
import { ErrorState } from "../../../shared/ui/states/ErrorState";
import { LoadingState } from "../../../shared/ui/states/LoadingState";
import { ModuleStateCard } from "../../../shared/ui/states/ModuleStateCard";
import { formatModuleStatus } from "../../../shared/lib/dashboardText";
import { useOverviewSnapshot } from "../../overview/hooks/useOverviewSnapshot";
import { mapConfigurationEvents } from "../mappers/mapConfigurationEvents";
import { pageStack, sectionGrid, topBanner } from "./ConfigurationEventsPage.css";

export function ConfigurationEventsPage() {
  const overviewQuery = useOverviewSnapshot();

  if (overviewQuery.isLoading) {
    return <LoadingState />;
  }

  if (overviewQuery.isError) {
    const message =
      overviewQuery.error instanceof Error
        ? overviewQuery.error.message
        : "Не удалось загрузить снимок конфигурации и событий.";

    return <ErrorState message={message} />;
  }

  if (!overviewQuery.data) {
    return (
      <EmptyState
        title="Контур конфигурации и событий недоступен"
        message="Сервер панели не вернул снимок событий только для чтения для этой страницы."
      />
    );
  }

  const model = mapConfigurationEvents(overviewQuery.data);

  if (model.moduleState === "inactive") {
    return (
      <ModuleStateCard
        title="Конфигурация и события"
        status="inactive"
        message="Страница конфигурации и событий предусмотрена в dashboard foundation, но снимок только для чтения для неё ещё не подключён."
      />
    );
  }

  return (
    <div className={pageStack}>
      <div className={topBanner}>
        <Badge tone="accent">{formatModuleStatus(model.moduleState)}</Badge>
        {model.statusBadges.map((badge) => (
          <Badge key={`${badge.label}-${badge.tone}`} tone={badge.tone}>
            {badge.label}
          </Badge>
        ))}
      </div>

      <div className={sectionGrid}>
        <Panel
          title="Счётчики событий"
          caption="Системные счётчики event bus в режиме только чтения, уже выведенные текущим снимком панели."
        >
          <KeyValueList items={model.eventCounters} />
        </Panel>

        <Panel
          title="Состояние доставки"
          caption="Базовый срез состояния контура доставки без просмотрщика потоков и без расширения истории событий."
        >
          <KeyValueList items={model.deliveryTruth} />
        </Panel>
      </div>

      <Panel
        title="Граница конфигурации"
        caption="Конфигурация на этой странице трактуется узко и честно: показывается только текущая граница снимка без редактора конфигурации и интерфейса для секретов."
      >
        <KeyValueList items={model.configurationTruth} />
      </Panel>
    </div>
  );
}

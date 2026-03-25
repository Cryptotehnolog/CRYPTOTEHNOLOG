import { Badge } from "../../../shared/ui/primitives/Badge";
import { KeyValueList } from "../../../shared/ui/primitives/KeyValueList";
import { Panel } from "../../../shared/ui/primitives/Panel";
import { EmptyState } from "../../../shared/ui/states/EmptyState";
import { ErrorState } from "../../../shared/ui/states/ErrorState";
import { LoadingState } from "../../../shared/ui/states/LoadingState";
import { ModuleStateCard } from "../../../shared/ui/states/ModuleStateCard";
import { formatModuleStatus } from "../../../shared/lib/dashboardText";
import { useOverviewSnapshot } from "../../overview/hooks/useOverviewSnapshot";
import { mapOperatorGate } from "../mappers/mapOperatorGate";
import { pageStack, sectionGrid, topBanner } from "./OperatorGatePage.css";

export function OperatorGatePage() {
  const overviewQuery = useOverviewSnapshot();

  if (overviewQuery.isLoading) {
    return <LoadingState />;
  }

  if (overviewQuery.isError) {
    const message =
      overviewQuery.error instanceof Error
        ? overviewQuery.error.message
        : "Не удалось загрузить сводку операторского контура.";

    return <ErrorState message={message} />;
  }

  if (!overviewQuery.data) {
    return (
      <EmptyState
        title="Операторский контур недоступен"
        message="Сервер панели не вернул сводный снимок только для чтения для этой страницы."
      />
    );
  }

  const model = mapOperatorGate(overviewQuery.data);

  if (model.moduleState === "inactive") {
    return (
      <ModuleStateCard
        title="Операторский контур"
        status="inactive"
        message="Страница операторского контура предусмотрена в dashboard foundation, но сводка только для чтения для неё ещё не подключена."
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
          title="Сводка по подтверждениям"
          caption="Сводка операторского контура в режиме только чтения без списка запросов и действий по сценариям."
        >
          <KeyValueList items={model.approvalSummary} />
        </Panel>

        <Panel
          title="Граница сводки"
          caption="Эта страница честно показывает только текущее состояние сводки операторского контура без обозревателя деталей и интерфейса двойного контроля."
        >
          <KeyValueList items={model.boundarySummary} />
        </Panel>
      </div>
    </div>
  );
}
